#!/bin/sh
set -eu

# Defaults (überschreibbar via .env / compose environment)
: "${LOGROTATE_CRON:=0 0 * * *}"          # täglich um 00:00
: "${LOGROTATE_SIZE:=50M}"                # rotiere ab 50 MB
: "${LOGROTATE_MAX_AGE_DAYS:=30}"         # lösche rotierte Logs > X Tage
: "${LOGROTATE_ROTATIONS:=7}"             # zusätzlich Anzahl-Backupfiles, falls gewünscht

# Logrotate-Regel generieren
# Hinweis: copytruncate vermeidet HUP; alternativ unten "reopen" nutzen (siehe Kommentar).
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
    copytruncate
    sharedscripts
    # postrotate
    #   # Falls du statt 'copytruncate' lieber echte Reopen-Logik möchtest:
    #   /usr/sbin/syslog-ng-ctl reopen >/dev/null 2>&1 || kill -USR1 \$(pidof syslog-ng) >/dev/null 2>&1 || true
    # endscript
}
EOF

# Crontab für Supercronic (ein Eintrag reicht)
printf '%s %s\n' "${LOGROTATE_CRON}" "/usr/sbin/logrotate -s /var/lib/logrotate/status /etc/logrotate.conf" \
  > /etc/cron.d/syslogrotate

echo "[entrypoint] schedule: ${LOGROTATE_CRON}  (/usr/sbin/logrotate ...)"
echo "[entrypoint] size: ${LOGROTATE_SIZE}, maxage: ${LOGROTATE_MAX_AGE_DAYS}d, rotations: ${LOGROTATE_ROTATIONS}"

# Supercronic im Hintergrund starten (schreibt hübsche JSON-Logs)
# Wichtig: Supercronic darf nicht PID 1 sein, damit SIGTERM an syslog-ng geht.
nohup /usr/local/bin/supercronic -json /etc/cron.d/syslogrotate >/proc/1/fd/1 2>/proc/1/fd/2 &

# syslog-ng als Vordergrundprozess
exec syslog-ng -F --no-caps