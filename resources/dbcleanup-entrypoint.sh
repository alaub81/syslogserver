#!/bin/sh
set -eu

# Default: täglich 03:00
: "${DBCLEANUP_CRON:=0 3 * * *}"

# Cronfile generieren (ein Job pro Zeile möglich)
# Achtung: Supercronic erwartet KEIN Benutzerfeld (anders als /etc/cron.d/*)
printf '%s %s\n' "${DBCLEANUP_CRON}" "/app/dbcleanup.sh" > /app/dbcleanup.cron

echo "[entrypoint] using schedule: ${DBCLEANUP_CRON} /app/dbcleanup.sh"

# Supercronic starten (optional mit JSON-Logs)
exec /usr/local/bin/supercronic -json /app/dbcleanup.cron