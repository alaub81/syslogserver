#!/bin/sh
set -eu

# Defaults can be overridden through .env or Compose.
: "${LOGROTATE_CRON:=0 * * * *}"          # hourly
: "${LOGROTATE_SIZE:=50M}"                 # persistent file mode; use 2M for RAM logs
: "${LOGROTATE_MAX_AGE_DAYS:=30}"         # maximum age of rotated files in days
: "${LOGROTATE_ROTATIONS:=7}"             # number of rotated files

# Reopen logs after rotation instead of using copytruncate.
# Keep rotated files separate from active logs.
mkdir -p /var/log/rotated /var/lib/logrotate
cat >/etc/logrotate.d/syslogserver <<EOF
/var/log/*.log /var/log/syslog /var/log/messages /var/log/error /var/log/debug {
    size ${LOGROTATE_SIZE}
    rotate ${LOGROTATE_ROTATIONS}
    maxage ${LOGROTATE_MAX_AGE_DAYS}
    missingok
    notifempty
    compress
    delaycompress
    dateext
    dateformat -%Y%m%d-%H%M%S
    sharedscripts
    olddir /var/log/rotated
    postrotate
        /usr/sbin/syslog-ng-ctl reopen >/dev/null 2>&1 || kill -USR1 1 >/dev/null 2>&1 || true
    endscript
}
EOF

# Run only our rule; distribution rules can overlap its top-level log files.
printf '%s %s\n' "${LOGROTATE_CRON}" "/usr/sbin/logrotate -s /var/lib/logrotate/status /etc/logrotate.d/syslogserver" \
  > /etc/cron.d/syslogrotate

echo "[entrypoint] logrotate schedule: ${LOGROTATE_CRON}"
echo "[entrypoint] size=${LOGROTATE_SIZE}, maxage=${LOGROTATE_MAX_AGE_DAYS}, rotations=${LOGROTATE_ROTATIONS}"

# Run Supercronic in the background with JSON logs.
# Keep syslog-ng as PID 1 so it receives SIGTERM directly.
nohup /usr/local/bin/supercronic -json /etc/cron.d/syslogrotate >/proc/1/fd/1 2>/proc/1/fd/2 &

# Replace the shell with syslog-ng in the foreground.
exec syslog-ng -F --no-caps
