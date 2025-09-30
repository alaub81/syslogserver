#!/bin/sh
set -eu

# --- ENV Defaults (per .env/compose überschreibbar) ---
: "${LOGROTATE_CRON:=0 0 * * *}"         # täglich 00:00
: "${LOGROTATE_SIZE:=50M}"                # ab Größe rotieren
: "${LOGROTATE_MAX_AGE_DAYS:=30}"         # rotierte Files > X Tage löschen
: "${LOGROTATE_ROTATIONS:=7}"             # Anzahl der Backups

# --- Logrotate-Regel (reopen statt copytruncate) ---
# Tipp: olddir trennt aktive von rotierten Files
mkdir -p /var/log/rotated /var/lib/logrotate
cat >/etc/logrotate.d/syslogserver <<EOF
/var/log/*.log {
    daily
    size ${LOGROTATE_SIZE}
    rotate ${LOGROTATE_ROTATIONS}
    maxage ${LOGROTATE_MAX_AGE_DAYS}
    missingok
    notifempty
    compress
    delaycompress
    dateext
    dateformat -%Y%m%d-%s
    sharedscripts
    olddir /var/log/rotated
    postrotate
        /usr/sbin/syslog-ng-ctl reopen >/dev/null 2>&1 || kill -USR1 1 >/dev/null 2>&1 || true
    endscript
}
EOF

# --- Supercronic-Schedule schreiben ---
printf '%s %s\n' "${LOGROTATE_CRON}" "/usr/sbin/logrotate -s /var/lib/logrotate/status /etc/logrotate.conf" \
  > /etc/cron.d/syslogrotate

echo "[entrypoint] logrotate schedule: ${LOGROTATE_CRON}"
echo "[entrypoint] size=${LOGROTATE_SIZE}, maxage=${LOGROTATE_MAX_AGE_DAYS}, rotations=${LOGROTATE_ROTATIONS}"

# --- Supercronic im Hintergrund starten (schreibt hübsche JSON-Logs) --- 
# Wichtig: Supercronic darf nicht PID 1 sein, damit SIGTERM an syslog-ng geht.
nohup /usr/local/bin/supercronic -json /etc/cron.d/syslogrotate >/proc/1/fd/1 2>/proc/1/fd/2 &

# --- syslog-ng als Vordergrundprozess ---
exec syslog-ng -F --no-caps