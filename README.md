# Syslog Server with LogAnalyzer

A Docker Compose stack that receives syslog over UDP/TCP, stores messages in
MariaDB, and displays them in LogAnalyzer. Optional Shelly support handles
NUL-delimited debug output entirely inside syslog-ng.

| Service | Purpose |
| --- | --- |
| `syslogng` | Receives UDP/TCP on port 514 and writes messages to MariaDB. |
| `database` | MariaDB with persistent storage in the `dbdata` volume. |
| `loganalyzer` | Web UI for browsing and searching the collected messages. |
| `dbcleanup` | Deletes expired messages in small, scheduled batches. |

## Requirements

- Docker Engine 25+ and Docker Compose v2.20.2+.
- Available UDP/TCP port 514 and HTTP port 8181 (configurable).
- A 64-bit host; defaults also suit a Raspberry Pi with at least 2 GiB RAM.

## Quick start

```bash
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
cp .env.example .env
# Generate a separate password for each DB password variable:
openssl rand -hex 32
# Edit .env: replace both example passwords and adjust ports/timezone/retention.
docker compose up -d --wait
```

Open `http://<server>:8181`. LogAnalyzer is preconfigured; no installation wizard
is needed. Send ordinary syslog to the server's UDP or TCP port **514**.
All three database clients wait for MariaDB to become healthy before starting.

### Shelly devices

Shelly devices send their debug output to the same **UDP port 514**.
Enable the optional parser before starting the stack:

```bash
cp data/syslog-ng/config/20-shelly.conf.disabled data/syslog-ng/config/20-shelly.conf
docker compose up -d --wait
```

If the stack is already running, validate and reload the enabled module:

```bash
docker compose exec -T syslogng syslog-ng --syntax-only --no-caps
docker compose exec -T syslogng syslog-ng-ctl reload
```

Shelly parsing and diagnostic file logging are disabled by default.

### Build locally

```bash
docker compose -f docker-compose.dev.yml up -d --build --wait
```

The development file is standalone and can also be started directly from
VS Code using the `compose:dev:up` build task. No extra parameters are needed.
Use the same Compose file and project name for subsequent commands.

## Documentation

- [Environment variables](.env.example): descriptions and example values for every setting.
- [Configuration and operations](docs/operations.md): Shelly parsing, diagnostics, health checks and troubleshooting.
- [Raspberry Pi tuning](docs/raspberry-pi.md): storage, retention, durability and existing-database migration.
- [Development and dependency updates](docs/development.md): local builds, CI, releases and Renovate.
- [Tests](tests/README.md): linters, regression tests and isolated end-to-end tests.
- [Security policy](SECURITY.md) and [license](LICENSE).

Changing `.env` credentials does not change accounts in an existing MariaDB
volume. Back up before upgrades or migrations and keep the existing project
name so the same `dbdata` volume is reused.

The web UI has no login enabled by default. Restrict it and the syslog listeners
to trusted networks, or put the UI behind an authenticated reverse proxy.
