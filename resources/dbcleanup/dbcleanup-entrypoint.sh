#!/bin/sh
set -eu

# Default: daily at 03:00 in the configured timezone.
: "${DBCLEANUP_CRON:=0 3 * * *}"

# Generate the cron file (one job per line).
# Supercronic expects no user field, unlike system /etc/cron.d files.
printf '%s %s\n' "${DBCLEANUP_CRON}" "/app/dbcleanup.sh" > /app/dbcleanup.cron

echo "[entrypoint] using schedule: ${DBCLEANUP_CRON} /app/dbcleanup.sh"

# Run Supercronic with JSON logs.
exec /usr/local/bin/supercronic -json /app/dbcleanup.cron
