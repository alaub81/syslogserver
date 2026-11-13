#!/usr/bin/env bash
# Build this checkout in a disposable Compose project and verify the core pipeline.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
TEST_DIR=$(mktemp -d)
TEST_PROJECT="syslogserver-e2e-$(date +%s)-$$"
COMPOSE=(docker compose --project-name "$TEST_PROJECT" --env-file "$TEST_DIR/stack.env"
  -f "$PROJECT_DIR/docker-compose.dev.yml" -f "$TEST_DIR/override.yml")

cleanup() {
  local status=$?
  trap - EXIT
  if (( status != 0 )); then
    "${COMPOSE[@]}" ps -a || true
    "${COMPOSE[@]}" logs --no-color --tail=200 || true
  fi
  # Only the unique project created by this test is torn down, including its DB.
  if ! "${COMPOSE[@]}" down --volumes --remove-orphans; then
    status=1
  fi
  rm -rf -- "$TEST_DIR"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cat > "$TEST_DIR/stack.env" <<'ENV'
TZ=UTC
DB_NAME=syslogdb
DB_USER=syslog
DB_PASSWORD=e2e-only-password
DB_ROOT_PASSWORD=e2e-only-root-password
SYSLOG_UDP_PORT=127.0.0.1:0
SYSLOG_TCP_PORT=127.0.0.1:0
LOGANALYZER_PORT=127.0.0.1:0
LOG_RETENTION_DAYS=7
DBCLEANUP_CRON="0 0 1 1 *"
ENV

# Exercise the shipped standard route, excluding local enabled vendor/debug files.
mkdir "$TEST_DIR/syslog-config"
cp data/syslog-ng/config/10-syslogsrv.conf data/syslog-ng/config/90-default.conf "$TEST_DIR/syslog-config/"
cat > "$TEST_DIR/override.yml" <<YAML
services:
  syslogng:
    image: ${TEST_PROJECT}-syslogng:test
    volumes:
      - ${TEST_DIR}/syslog-config:/etc/syslog-ng/conf.d/:ro
  loganalyzer:
    image: ${TEST_PROJECT}-loganalyzer:test
  dbcleanup:
    image: ${TEST_PROJECT}-dbcleanup:test
YAML

"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build --pull
"${COMPOSE[@]}" up --wait --wait-timeout 180
"${COMPOSE[@]}" ps

TEST_MESSAGE="${TEST_PROJECT}-message"
# Variables in these commands are expanded inside the container.
# shellcheck disable=SC2016
"${COMPOSE[@]}" exec -T -e TEST_MESSAGE="$TEST_MESSAGE" syslogng sh -ec '
  printf "<14>%s ci-host ci-test: %s-udp\n" "$(date "+%b %e %T")" "$TEST_MESSAGE" |
    nc -u -w 1 127.0.0.1 514
  tcp_message=$(printf "<14>1 %s ci-host ci-test 1 - - %s-tcp" "$(date -u "+%Y-%m-%dT%H:%M:%SZ")" "$TEST_MESSAGE")
  # The syslog() TCP listener uses RFC6587 octet-counted framing.
  printf "%s %s" "${#tcp_message}" "$tcp_message" | nc -N -w 1 127.0.0.1 514
'

db_query() {
  # shellcheck disable=SC2016
  "${COMPOSE[@]}" exec -T database sh -ec '
    exec mariadb --connect-timeout=5 --user="$MARIADB_USER" --password="$MARIADB_PASSWORD" \
      --database="$MARIADB_DATABASE" --batch --skip-column-names
  '
}

# syslog-ng commits low-volume SQL batches after about one second.
received=0
for _ in {1..30}; do
  received=$(db_query <<SQL
SELECT
  EXISTS(SELECT 1 FROM SystemEvents WHERE Message LIKE '%${TEST_MESSAGE}-udp%') +
  EXISTS(SELECT 1 FROM SystemEvents WHERE Message LIKE '%${TEST_MESSAGE}-tcp%');
SQL
  )
  [[ "$received" == 2 ]] && break
  sleep 1
done
if [[ "$received" != 2 ]]; then
  echo "Expected both UDP and TCP messages in MariaDB; found $received protocols." >&2
  exit 1
fi
echo "PASS: UDP and TCP messages reached MariaDB."

"${COMPOSE[@]}" exec -T loganalyzer curl -fsS --max-time 30 --compressed \
  http://127.0.0.1/index.php > "$TEST_DIR/index.html"
grep -Fq "${TEST_MESSAGE}-udp" "$TEST_DIR/index.html"
grep -Fq "${TEST_MESSAGE}-tcp" "$TEST_DIR/index.html"
echo "PASS: LogAnalyzer displays both messages."

db_query <<SQL
INSERT INTO SystemEvents
  (ReceivedAt, DeviceReportedTime, Facility, Priority, FromHost, Message)
VALUES (NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY, 1, 6, 'ci-host', '${TEST_MESSAGE}-expired');
SQL
"${COMPOSE[@]}" exec -T dbcleanup /app/dbcleanup.sh
remaining=$(db_query <<SQL
SELECT
  (SELECT COUNT(*) FROM SystemEvents WHERE Message LIKE '%${TEST_MESSAGE}-expired%'),
  (SELECT COUNT(*) FROM SystemEvents WHERE Message LIKE '%${TEST_MESSAGE}-udp%' OR Message LIKE '%${TEST_MESSAGE}-tcp%');
SQL
)
if [[ "$remaining" != $'0\t2' ]]; then
  echo "Retention must remove the expired row and preserve both fresh messages; got: $remaining" >&2
  exit 1
fi
echo "PASS: Retention removed the expired row and preserved fresh messages."
