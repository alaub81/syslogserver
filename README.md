# Syslog Server with LogAnalyzer

A Docker Compose stack that receives syslog over UDP/TCP, stores messages in
MariaDB, and displays them in LogAnalyzer. Optional Shelly parsing handles the
nonstandard debug logs sent by Shelly devices entirely inside syslog-ng.

**Shelly parsing and raw file logging are disabled by default.**

## Components

| Service | Purpose |
| --- | --- |
| `syslogng` | Receives UDP/TCP on container port 514 and writes to `SystemEvents`. |
| `database` | MariaDB with a persistent named volume, `dbdata`. |
| `loganalyzer` | Web UI using the same database; configured through environment variables. |
| `dbcleanup` | Deletes expired rows in small batches on a configurable schedule. |

```text
Clients ── UDP/TCP ──> syslog-ng ── SQL ──> MariaDB
                                            ^
Browser ── HTTP ──> LogAnalyzer ── SQL ────────┤
                   dbcleanup ── retention ────┘
```

## Requirements

- Docker Engine 25+ and Docker Compose v2.20.2+ for the configured startup health checks.
- Available UDP/TCP listener ports and an HTTP port on the host.
- Access to GHCR/Docker Hub, or local builds using the supplied Dockerfiles.

## Quick start

```bash
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
cp .env.example .env
# Edit .env: set your passwords, ports, timezone and retention.
docker compose up -d
```

Open `http://<server>:8181`, or the port set in `LOGANALYZER_PORT`.
The included LogAnalyzer configuration already reads `DB_HOST`, `DB_NAME`,
`DB_USER` and `DB_PASSWORD` and uses the `SystemEvents` table; no installation
wizard is needed for this setup.

Send ordinary syslog to the host's `SYSLOG_UDP_PORT` or `SYSLOG_TCP_PORT`.
Both are 514 in `.env.example`.

### Build locally

`docker-compose.dev.yml` remains available for building all application images:

```bash
docker compose -f docker-compose.dev.yml --env-file .env up -d --build
```

Use the same Compose files and project name for subsequent commands. LogAnalyzer
build version and download URL are defined in `resources/loganalyzer/Dockerfile`
for both local and CI builds. The local LogAnalyzer image is tagged `loganalyzer:dev`.

Each application image has its own build context under `resources/`:

```text
resources/
├── syslogng/
│   ├── Dockerfile
│   └── syslogng-entrypoint.sh
├── loganalyzer/
│   ├── Dockerfile
│   ├── php-overrides.ini
│   └── apache-pi.conf
└── dbcleanup/
    ├── Dockerfile
    ├── dbcleanup.sh
    └── dbcleanup-entrypoint.sh
```

Deployment configuration and database initialization files remain under `data/`.

## Configuration

`.env.example` documents the settings. The main groups are:

| Variables | Purpose |
| --- | --- |
| `SYSLOG_UDP_PORT`, `SYSLOG_TCP_PORT`, `LOGANALYZER_PORT` | Host listener and web ports. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD` | MariaDB database and credentials. |
| `TZ` | Container timezone. |
| `LOG_RETENTION_DAYS`, `DBCLEANUP_CRON` | Retention period and cleanup schedule. |
| `DBCLEANUP_BATCH_SIZE`, `DBCLEANUP_BATCH_PAUSE` | Rows per cleanup transaction and pause between full batches. |
| `LOGROTATE_*` | Rotation settings for optional file diagnostics. |

The schema in `data/init.sql` runs only when MariaDB initializes a **new** volume.
Changing `.env` credentials does not update accounts in an existing database.
Keep the existing Compose project name when upgrading so the same `dbdata`
volume is reused. Back up the database before applying migrations; do not
remove an existing volume to apply configuration or schema changes.

## syslog-ng configuration

Snippets under `data/syslog-ng/config/` are loaded in filename order:

| File | Purpose |
| --- | --- |
| `10-syslogsrv.conf` | Shared listeners, standard parsers and SQL destination. |
| `15-rawlog.conf.disabled` | Optional raw UDP file logging before vendor routing. |
| `20-shelly.conf.disabled` | Optional Shelly detection, framing, parsing and routing. |
| `shelly-debug/30-debug.conf.disabled` | Optional Shelly diagnostics, included only by the enabled Shelly module. |
| `90-default.conf` | Standard RFC3164/RFC5424 routing and local syslog-ng messages. |

With just the active `10-syslogsrv.conf` and `90-default.conf`, this is an
ordinary syslog server. Files ending in `.disabled` are templates and are not
loaded automatically. Their active local copies are excluded from Git.

### Enable Shelly support

```bash
cp data/syslog-ng/config/20-shelly.conf.disabled data/syslog-ng/config/20-shelly.conf
```

Shelly devices can then send UDP debug output to the normal syslog UDP port.
The module separates NUL-delimited records inside a datagram using an internal,
byte-counted TCP connection on loopback port 1514. That port is not published.
Each record is retained, including script text, fragments and unknown formats.
Fragments remain separate records; no speculative concatenation is performed.

The active module contains the Host-column policy:

```conf
@define shelly-host-mode "sender"
```

- `sender` is the template default: preserve the sender hostname/IP from the
  shared listener. Reverse DNS is disabled by default, so normally an IP is
  displayed. Enable DNS in the base listener if resolved names are required.
- `device` uses the Shelly hardware ID. This is useful when Docker Desktop or
  another intermediary translates all devices to the same source address.

The module cannot recover original sender addresses hidden by NAT. LogAnalyzer
reads its Host column from `FromHost`. Shelly levels 0–4 map to syslog severities
3/4/6/7/7. Optional `file:line` data maps to `SysLogTag` and `EventSource`;
`ProcessID=0` means no PID was supplied. Normal syslog retains supplied PIDs.
Shelly UDP uptime is not treated as a Unix timestamp; reception time is used.
Known script channels 101/102 receive the `shelly-script` tag; other unfamiliar
formats remain visible under `shelly-other`.

### Optional file diagnostics

```bash
cp data/syslog-ng/config/15-rawlog.conf.disabled data/syslog-ng/config/15-rawlog.conf
cp data/syslog-ng/config/shelly-debug/30-debug.conf.disabled data/syslog-ng/config/shelly-debug/30-debug.conf
```

Raw UDP diagnostics work independently of Shelly support. Shelly diagnostics
are loaded only by the active Shelly module. File output is rotated by the
syslog-ng container's logrotate scheduler. These files live in a bounded
32 MiB RAM directory and disappear when the container stops. To retain a
diagnostic snapshot after enabling the corresponding output:

```bash
mkdir -p .local/logs
docker compose cp syslogng:/var/log/raw-udp.log .local/logs/raw-udp.log
```

To disable a feature, remove its local active `.conf` copy or move it to a
backup name that does not end in `.conf`; retain the shipped `.disabled`
template. Changes to templates do not overwrite existing local active copies.

After editing configuration, check syntax before reloading:

```bash
docker compose exec -T syslogng syslog-ng --syntax-only --no-caps
docker compose exec -T syslogng syslog-ng-ctl reload
```

For older installations, retire active `20-shellylog.conf` and `90-rawlog.conf`
files by changing their suffix to `.conf.legacy`, then use the current templates.

## Raspberry Pi and database retention

Both Compose files include SD-card-friendly defaults for a 64-bit Raspberry Pi
with at least 2 GiB RAM: bounded tmpfs storage, smaller PHP/Apache limits,
MariaDB memory settings and bounded Docker logs. No additional Pi overlay is
required. Use the normal production or development command above and keep the
same project name when upgrading.

SQL ingestion uses transactions of up to 100 records with a 1,000 ms batch
timeout. Retention deletes bounded batches using a fixed cutoff and the
`ReceivedAt` index. Routine table rebuilds and the daily optimization event
are no longer part of new installations. Existing databases are not changed
automatically.

See [Raspberry Pi tuning](docs/raspberry-pi.md) for the optional migration,
durability and RAM tradeoffs, and storage sizing. Durable MariaDB commits remain
the default; pending RAM queues or uncommitted batches can be lost after a crash.

## Health checks and troubleshooting

| Service | Check | Normal interval |
| --- | --- | --- |
| `syslogng` | Daemon responsiveness through `syslog-ng-ctl healthcheck`. | 1 minute |
| `database` | Local TCP `SELECT 1` with the configured application user. | 1 minute |
| `loganalyzer` | HTTP GET through PHP. | 5 minutes |

Startup checks run more frequently. These probes do not establish end-to-end
log delivery, and an unhealthy status alone does not restart a container.

```bash
docker compose ps
docker compose logs --tail=100 syslogng database loganalyzer dbcleanup
```

For a simple UDP check, replace the host and port as needed:

```bash
printf '<14>syslog-check: delivery-test\n' | nc -u -w 1 127.0.0.1 514
```

Look for `delivery-test` in LogAnalyzer. For missing rows, inspect SQL errors
and `syslog-ng-ctl stats` for queued/dropped records. For unexpected file output,
check which optional `.conf` files are enabled. Database text columns must
support `utf8mb4` for full Unicode messages.

## Development and local artifacts

The Dockerfiles, development Compose file, runtime resources, CI configuration
and automated regression tests remain in the repository. Run the cleanup
regressions without a live database:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the same lint checks as CI (or the VS Code task `lint:all`):

```bash
./tests/linter-check.sh
```

The command prepares isolated, pinned tools and reports PASS/FAIL for text
hygiene, JSON, ShellCheck, Hadolint, strict YAML, GitHub Actions and Python
correctness checks. It includes new, non-ignored files and never fixes source
files. See [tests/README.md](tests/README.md) for setup and scope.

Local packet captures, copied live logs, replay outputs, one-off diagnostic
scripts and downloaded vendor archives belong under **`.local/`**. This directory
is excluded from Git and normal Docker build contexts and is not required to
run or build the stack. Local active configuration files and `.env` remain in
their documented locations and are also Git-ignored.

## Dependency updates

Renovate manages version-update PRs for GitHub Actions, Dockerfiles, Compose
images, Python and native lint tools, LogAnalyzer and Supercronic. Supercronic's
download URLs in the syslogng and dbcleanup Dockerfiles are updated together.
New update branches are scheduled for Mondays before 06:00 Europe/Berlin.
Minor and patch updates are grouped separately for Actions and Python lint
dependencies; Docker images and major upgrades are reviewed per dependency.
Automerge is disabled. The Dependency Dashboard tracks pending updates.

The three application Dockerfiles refresh package lists and upgrade installed
Debian packages before installing their dependencies. Their official base images
already enable the matching Debian security repository. CI and release builds
re-run the `os-packages` stage with `no-cache-filters`; local fresh builds can use
`docker compose -f docker-compose.dev.yml --env-file .env build --pull --no-cache`.
This picks up available package fixes even before a base image is republished.
Rebuilding an older release tag still uses that tag's Dockerfiles.

Both Compose files use `mariadb:13`. Pulling this tag can install newer minor
and patch releases within MariaDB 13; Renovate proposes later major versions
as PRs. Before deploying a new release series, review the
[MariaDB upgrade guide](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/upgrading)
and back up the database.

The explicit `ignorePaths` in `renovate.json` keeps `tests/requirements-lint.txt`
included despite the recommended preset's default exclusion of test directories.
Native linter updates in `lint-tools.json` include release tags and SHA-256
checksums for every listed platform in the same PR. Download filenames are
derived from the release version; the installer rejects mixed platform versions.

Dependabot version-update PRs are disabled with `open-pull-requests-limit: 0`.
Keep Dependabot alerts and, if desired, security-update PRs enabled in GitHub's
repository security settings. Renovate's vulnerability-alert PRs are disabled
to leave alert-driven security updates to Dependabot.

The Renovate GitHub App must be enabled for this repository, and these
configuration changes must be on the default branch before they take effect.

PRs and main pushes run lint/regression checks, fresh image builds, Trivy scans
and an isolated [end-to-end stack test](tests/README.md#end-to-end-stack-test).
Fixable HIGH/CRITICAL findings fail CI. Set `CI required` as a required status
check in GitHub's main branch rules to enforce the checks before merging.

## Security and license

Change the example passwords before deployment. Limit the syslog listeners and
web UI to trusted networks, or protect the UI with appropriate authentication.
See [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE).
