#!/bin/bash

##############################################################################
# dbcleanup.sh
# Description: Deletes old log entries from the SystemEvents table in MariaDB
#              and optimizes the table.
# Logging: All output (stdout + stderr) is redirected to syslog-ng via logger.
##############################################################################

LOGTAG="dbcleanup-job"
SYSLOG_SERVER="syslogng"   # Must match docker-compose service name or IP
SYSLOG_PORT=514

# Redirect all stdout and stderr to syslog via logger
exec > >(logger -n "$SYSLOG_SERVER" -P "$SYSLOG_PORT" -t "$LOGTAG" --id=$$) 2>&1

echo "Starting cleanup script..."

# Default fallback for retention period
# : "${LOG_RETENTION_DAYS:=30}"
# : "${DB_HOST:=database}"
# : "${DB_NAME:=syslogdb}"
# : "${DB_USER:=syslog}"
# : "${DB_PASSWORD:=syslogpass}"

echo "Deleting logs older than $LOG_RETENTION_DAYS day(s)..."

# Execute SQL commands
mysql -h "$DB_HOST" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" <<EOF
DELETE FROM SystemEvents WHERE ReceivedAt < NOW() - INTERVAL $LOG_RETENTION_DAYS DAY;
OPTIMIZE TABLE SystemEvents;
EOF

echo "Cleanup complete."
