# Syslog Server Docker Stack with Web UI (LogAnalyzer)

A production‑ready, multi‑container stack to ingest syslog over UDP/TCP with **syslog‑ng**, persist logs in **MariaDB**, and explore them via the **LogAnalyzer** web UI. It also ships with an optional **dbcleanup** sidecar to prune old rows and a built‑in **logrotate** scheduler for file outputs.

> This README matches the provided repository snapshot. See `docker-compose.yml` (prebuilt images from GHCR) and `docker-compose.dev.yml` (build locally) for two usage modes.

---

## Features

- **syslog‑ng + MySQL (MariaDB) output**
  - Listens on UDP/TCP 514, parses Shelly device messages, writes into `SystemEvents`.
  - Healthcheck and optional log rotation via supercronic + logrotate.
- **MariaDB** with one‑time bootstrap from `data/init.sql` (schema + indexes + daily OPTIMIZE event).
- **LogAnalyzer (PHP/Apache)** served from `loganalyzer` container with a bind‑mounted `config.php`.
- **Cleanup sidecar** (`dbcleanup`) that deletes old rows on a cron schedule and optimizes the table.
- **Environment‑driven configuration** via `.env`.
- **Multi‑arch images** (amd64/arm64) & CI pipeline (lint, build, scan, e2e).

---

## Architecture

```txt
+-------------+     UDP/TCP 514     +------------+    SQL (MySQL)    +-----------+
|  Clients    |  ─────────────────▶ |  syslog-ng | ────────────────▶ |  MariaDB  |
+-------------+                     +------------+                   +-----------+
                                           │                                ▲
                                           │                                │
                                           └────────── HTTP 80 ─────────────┘
                                                          |
                                                     +----------+
                                                     |LogAnalyzer|
                                                     +----------+

Optional: dbcleanup -> runs scheduled DELETE/OPTIMIZE against MariaDB
```

Containers & key files:

- `syslogng` (image: `ghcr.io/alaub81/syslogng` or built via `Dockerfile-syslogng`)
  - Config: `data/syslog-ng/config/*.conf`
  - Entry: `resources/syslogng-entrypoint.sh` (renders logrotate, starts supercronic + syslog‑ng)
- `database` (image: `mariadb:latest`)
  - Init SQL: `data/init.sql` (schema, indexes, daily OPTIMIZE event)
  - Volume: `dbdata` (persistent)
- `loganalyzer` (image: `ghcr.io/alaub81/loganalyzer` or built via `Dockerfile-loganalyzer`)
  - Config: `data/loganalyzer/config/config.php` (bind‑mounted to `/var/www/html/config.php`)
- `dbcleanup` (optional; image: `ghcr.io/alaub81/dbcleanup` or built via `Dockerfile-dbcleanup`)
  - Script: `resources/dbcleanup.sh`
  - Entrypoint: `resources/dbcleanup-entrypoint.sh`

---

## Requirements

- Docker Engine 24+ and Docker Compose v2
- Open ports 514/udp and 514/tcp on the host (or customize via `.env`)
- Outbound access to GHCR/Docker Hub (unless you build locally)

---

## Quick start

### 1) Clone & configure

```bash
cd /opt
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
cp .env.example .env
# Edit .env as needed (ports, DB credentials, retention, cron)
```

### 2a) Run with prebuilt images (recommended)

This uses `docker-compose.yml` and pulls images from GHCR.

```bash
docker compose up -d
```

### 2b) Develop locally (build from Dockerfiles)

This uses `docker-compose.dev.yml` to build images on your machine.

```bash
docker compose -f docker-compose.dev.yml --env-file .env up -d --build
```

### 3) LogAnalyzer setup (first run, if config.php does not exist)

Open `http://localhost:${LOGANALYZER_PORT}` (default 8181) and follow the wizard:

- DB Type: **MySQL** (MariaDB)
- Host: `database`  ·  DB: `${DB_NAME}`  ·  User: `${DB_USER}`  ·  Password: `${DB_PASSWORD}`
- Source table: `SystemEvents`

> The file `data/loganalyzer/config/config.php` is bind‑mounted as `/var/www/html/config.php`; changes persist in your working tree.

---

## Configuration (.env)

See `.env.example` for documented defaults. Most common settings:

```dotenv
# Timezone inside containers
TZ=Europe/Berlin

# Syslog listener ports on the HOST
SYSLOG_UDP_PORT=514
SYSLOG_TCP_PORT=514

# LogAnalyzer (HTTP) port on the HOST
LOGANALYZER_PORT=8181

# MariaDB credentials
DB_NAME=syslogdb
DB_USER=syslog
DB_PASSWORD=changeMe!
DB_ROOT_PASSWORD=changeRoot!   # only used at initial bootstrap

# Log cleanup (dbcleanup container)
LOG_RETENTION_DAYS=30          # delete rows older than N days
DBCLEANUP_CRON=0 3 * * *       # daily at 03:00

# syslog-ng file rotation (if file destinations used)
LOGROTATE_CRON=0 * * * *       # hourly
LOGROTATE_SIZE=50M             # rotate at ~50 MB
LOGROTATE_MAX_AGE_DAYS=14      # delete rotated files older than N days
LOGROTATE_ROTATIONS=7          # keep N rotated files

# Only needed when you like to build localy with docker-compose.dev.yml
# Loganalyzer Version (https://loganalyzer.adiscon.com/download/)
LOGANALYZER_VERSION=4.1.13
# Configure loganalyzers Download-URL (TGZ)
LOGANALYZER_URL=https://download.adiscon.com/loganalyzer/loganalyzer-${LOGANALYZER_VERSION}.tar.gz
```

> **Tip – ServerName warning**: If Apache logs `Could not reliably determine the server's FQDN`, set `ServerName` (e.g., via a tiny conf) or ignore – it’s harmless.

---

## Configuration syslogng

If you like to have a debug log for the shelly devices or a raw dump log, just copy the disabled config files under `./data/syslog-ng/config/`

```bash
cp ./data/syslog-ng/config/20-shellylog.conf.disabled ./data/syslog-ng/config/20-shellylog.conf
cp ./data/syslog-ng/config/90-rawlog.conf.disabled ./data/syslog-ng/config/90-rawlog.conf
```

and if application is already running, just restart syslogng container:

```bash
docker compose restart syslogng
```

---

## Testing the setup

### Send a test message (UDP)

From another container on the same compose network:

```bash
docker run --rm --network $(docker network ls --format '{{.Name}}' | grep syslogserver) debian:trixie-slim bash -lc 'logger -n syslogng -P 514 -d "hello-from-ci-$(date +%s)"'
```

### Or with netcat (UDP)

```bash
echo "hello-from-nc" | nc -u -w1 127.0.0.1 "${SYSLOG_UDP_PORT}"
```

### Verify in DB

```bash
docker compose exec -T database sh -lc 'mariadb -u"$MARIADB_USER" --password="$MARIADB_PASSWORD" -D "$MARIADB_DATABASE" -e "SELECT COUNT(*) FROM SystemEvents;"'
```

### Verify in loganalyzer

just open up loganalyzer ui with your browser and check if the message appears.

---

## Health checks

- **syslog-ng**: checks `syslog-ng-ctl stats` or UDP 514 socket accessible.
- **database**: waits until MariaDB is ready & answers SQL.
- **loganalyzer**: HTTP probe on `/`.

If a service is stuck unhealthy, inspect logs:

```bash
docker compose logs --no-color syslogng database loganalyzer
```

---

## Security notes

- Replace all default passwords in `.env` before exposing ports on public networks.
- Restrict inbound 514/udp + 514/tcp to trusted networks.
- Keep images updated (CI can rebuild weekly and on base‑image changes).

---

## Development (local build)

```bash
docker compose -f docker-compose.dev.yml --env-file .env up -d --build
# Logs
docker compose logs -f --tail=200 syslogng
```

To run linters locally (optional):

- Dockerfiles: `hadolint`
- Shell scripts: `shellcheck`
- YAML: `yamllint`

---

## Troubleshooting

- **No rows in DB**: check `syslogng` logs for SQL errors (credentials, table names).
- **DeviceReportedTime/ReceivedAt errors**: ensure timestamps are passed as `YYYY-MM-DD HH:MM:SS` to MariaDB.
- **Messages also written to files**: remove or disable file destinations in `data/syslog-ng/config/*.conf`.
- **LogAnalyzer shows missing columns**: confirm your table matches `data/init.sql` (e.g., `ProcessID`, `EventLogType`, etc.).
- **Healthcheck fails for syslog‑ng**: ensure `syslog-ng-ctl` exists inside the image; optionally install `netcat` if you use the fallback.

---

## License & Security

- License: MIT (see `LICENSE`)
- Security Policy: see `SECURITY.md` (how to report vulnerabilities)

---

## Changelog

See Git commit history and release notes.
