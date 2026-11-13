#!/usr/bin/env bash
# Test published ports and the complete pipeline in a disposable Compose project.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
SKIP_BUILD=false
if [[ ${1:-} == --skip-build && $# == 1 ]]; then
  SKIP_BUILD=true
elif (( $# != 0 )); then
  echo "Usage: ./tests/e2e-check.sh [--skip-build]" >&2
  exit 2
fi
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
DBCLEANUP_BATCH_SIZE=2
DBCLEANUP_BATCH_PAUSE=0
SYSLOG_LOG_STORAGE=./data/syslog-ng/logs
SYSLOG_LOG_RAM_SIZE=128m
LOGROTATE_CRON="0 * * * *"
LOGROTATE_SIZE=50M
LOGROTATE_ROTATIONS=7
ENV

# Start with only the shipped standard route, regardless of local enabled files.
mkdir "$TEST_DIR/syslog-config" "$TEST_DIR/logs"
cp data/syslog-ng/config/10-syslogsrv.conf data/syslog-ng/config/90-default.conf "$TEST_DIR/syslog-config/"
if "$SKIP_BUILD"; then
  SYSLOG_IMAGE=syslogng-mysql:latest
  LOGANALYZER_IMAGE=loganalyzer:dev
  CLEANUP_IMAGE=dbcleanup:latest
else
  SYSLOG_IMAGE=${TEST_PROJECT}-syslogng:test
  LOGANALYZER_IMAGE=${TEST_PROJECT}-loganalyzer:test
  CLEANUP_IMAGE=${TEST_PROJECT}-dbcleanup:test
fi
cat > "$TEST_DIR/override.yml" <<YAML
services:
  syslogng:
    image: ${SYSLOG_IMAGE}
    volumes:
      - ${TEST_DIR}/syslog-config:/etc/syslog-ng/conf.d/:ro
      - ${TEST_DIR}/logs:/var/log
  loganalyzer:
    image: ${LOGANALYZER_IMAGE}
  dbcleanup:
    image: ${CLEANUP_IMAGE}
YAML

"${COMPOSE[@]}" config --quiet
if ! "$SKIP_BUILD"; then
  "${COMPOSE[@]}" build --pull --no-cache
fi
"${COMPOSE[@]}" pull database
"${COMPOSE[@]}" up --no-build --pull never --wait --wait-timeout 180
"${COMPOSE[@]}" exec -T loganalyzer php -l /var/www/html/config.php
"${COMPOSE[@]}" exec -T syslogng syslog-ng --syntax-only --no-caps
"${COMPOSE[@]}" exec -T dbcleanup supercronic -test /app/dbcleanup.cron
"${COMPOSE[@]}" exec -T syslogng supercronic -test /etc/cron.d/syslogrotate
python3 tests/e2e.py "$TEST_PROJECT" "$TEST_DIR"
