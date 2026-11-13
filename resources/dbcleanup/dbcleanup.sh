#!/bin/bash
# Bound retention work to small transactions. InnoDB reuses deleted space;
# rebuilding the table with OPTIMIZE after every cleanup causes needless I/O.
set -euo pipefail

: "${LOG_RETENTION_DAYS:=30}"
: "${DBCLEANUP_BATCH_SIZE:=1000}"
: "${DBCLEANUP_BATCH_PAUSE:=0.1}"
: "${DB_HOST:=database}"
: "${DB_NAME:=syslogdb}"
: "${DB_USER:=syslog}"
: "${DB_PASSWORD:?DB_PASSWORD is required}"

positive_integer() {
    [[ "$1" =~ ^[1-9][0-9]{0,8}$ ]]
}

if ! positive_integer "$LOG_RETENTION_DAYS"; then
    echo "LOG_RETENTION_DAYS must be a positive integer." >&2
    exit 1
fi
if ! positive_integer "$DBCLEANUP_BATCH_SIZE" || (( DBCLEANUP_BATCH_SIZE > 10000 )); then
    echo "DBCLEANUP_BATCH_SIZE must be an integer between 1 and 10000." >&2
    exit 1
fi
if [[ ! "$DBCLEANUP_BATCH_PAUSE" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "DBCLEANUP_BATCH_PAUSE must be a non-negative number of seconds." >&2
    exit 1
fi

query() {
    # Keep cron output in Docker's bounded service logs, including SQL failures.
    mariadb --protocol=tcp --host="$DB_HOST" \
        --connect-timeout=10 --user="$DB_USER" --password="$DB_PASSWORD" --database="$DB_NAME" \
        --batch --skip-column-names --execute="$1"
}

# A fixed cutoff prevents a long run from chasing newly expiring records.
cutoff=$(query "SELECT DATE_FORMAT(NOW() - INTERVAL $LOG_RETENTION_DAYS DAY, '%Y-%m-%d %H:%i:%s');")
echo "Deleting logs received before $cutoff in batches of $DBCLEANUP_BATCH_SIZE..."
total=0
while true; do
    deleted=$(query "DELETE FROM SystemEvents
        WHERE ReceivedAt < '$cutoff'
        ORDER BY ReceivedAt, ID LIMIT $DBCLEANUP_BATCH_SIZE;
        SELECT ROW_COUNT();")
    if [[ ! "$deleted" =~ ^[0-9]+$ ]]; then
        echo "Unexpected cleanup row count: $deleted" >&2
        exit 1
    fi
    total=$((total + deleted))
    if (( deleted < DBCLEANUP_BATCH_SIZE )); then
        break
    fi
    sleep "$DBCLEANUP_BATCH_PAUSE"
done
echo "Cleanup complete: deleted $total row(s); no table rebuild."
