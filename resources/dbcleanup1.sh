#!/bin/sh
LOGTAG="dbcleanup-job"
SYSLOG_SERVER="syslogng"     # Docker-Service-Name
SYSLOG_PORT=514              # UDP-Port

log() {
  #echo "$1" | logger -n "$SYSLOG_SERVER" -P "$SYSLOG_PORT" -t "$LOGTAG"
  logger -n "$SYSLOG_SERVER" -P "$SYSLOG_PORT" -t "$LOGTAG" "$1"
}

log "Running Database cleanup script... $DB_HOST"

# Connect to MariaDB and execute SQL statements
mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" <<EOF
DELETE FROM SystemEvents WHERE ReceivedAt < NOW() - INTERVAL $LOG_RETENTION_DAYS DAY;
OPTIMIZE TABLE SystemEvents;
EOF

log "Database cleanup complete. $DB_HOST"