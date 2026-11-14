# Syslog Server with LogAnalyzer

Receive syslog over UDP/TCP, store messages in MariaDB and rotating files, and
browse them in LogAnalyzer. Optional Shelly support separates NUL-delimited debug
records and stores normalized messages in SQL and file logs. Run the complete
stack with Docker Compose on Linux amd64 or arm64, including Raspberry Pi systems.

## Features

- Collector, database, web viewer and scheduled retention in one Compose stack.
- [Shelly debug ingestion](#shelly-support) on the regular syslog UDP port,
  including script messages, sender/device host names and an optional Shelly logfile.
- Optional reverse DNS and raw UDP diagnostics.
- Persistent file logging or a bounded RAM volume for SD-card-friendly operation.
- Healthchecks, configurable ports and isolated end-to-end regression tests.

| Service | Purpose |
| --- | --- |
| `syslogng` | Receives UDP/TCP syslog and writes to MariaDB and `events.log`. |
| `database` | Stores messages persistently in MariaDB through the `dbdata` volume. |
| `loganalyzer` | Provides the web UI for browsing and searching messages. |
| `dbcleanup` | Deletes expired messages in bounded, scheduled batches. |

## Requirements and compatibility

Use Docker Engine 25+ and Compose 2.20.2+, Git and a 64-bit Linux host.
Allow at least 2 GiB RAM. The default listeners use UDP/TCP port 514 and the
web viewer uses port 8181. The stack currently uses MariaDB 13.

**The web UI has no login by default, and syslog listeners accept network input.**
Restrict access to trusted networks or use an authenticated reverse proxy for
HTTP. Do not expose the stack publicly without an appropriate access policy.

## Quick start

### 1. Prepare a new installation

```bash
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
cp .env.example .env
chmod 600 .env
```

Generate **two different database passwords**: one for the application account
(`DB_PASSWORD`), shared by the collector, viewer and cleanup service, and one for
the database administrator (`DB_ROOT_PASSWORD`). Run the command separately for
each password:

```bash
# Generate a value for DB_PASSWORD.
openssl rand -hex 32
# Generate a different value for DB_ROOT_PASSWORD.
openssl rand -hex 32
```

Each invocation prints a new password made from 32 random bytes (64 hexadecimal
characters). Edit `.env` and replace the corresponding example values with the
two outputs; do not reuse the same value for both accounts. Then adjust ports,
timezone and retention. Keep existing `.env` files, credentials and volumes when
updating an installation. Changing `.env` does not change passwords in an
already initialized database.

### 2. Validate and start

```bash
docker compose config --quiet
docker compose pull
docker compose up -d --wait
docker compose ps
```

The collector, database and viewer should become healthy; the scheduled cleanup
service remains running. Open `http://YOURSERVER:8181` and send syslog to UDP or
TCP port 514. LogAnalyzer is preconfigured, so no installation wizard is needed.
If startup fails, inspect `docker compose logs --tail=100` before changing data.

## Build locally

To build the images from this checkout, use the standalone development file
instead of the production pull/start commands above. Prepare the same `.env`
first, then run:

```bash
docker compose -f compose.dev.yml up -d --build --wait
docker compose -f compose.dev.yml ps
```

The build needs no compiler installed on the host. VS Code users can also run
the `compose:dev:up` build task. Use `docker compose -f compose.dev.yml` for
subsequent logs, exec, stop and update commands, and keep the same project name
and `.env` so the existing database volume is reused. The default project name
is derived from the checkout directory; preserve any existing explicit `-p` or
`COMPOSE_PROJECT_NAME` setting.

## Advanced

Shelly parsing, reverse DNS and extra diagnostic files are **disabled by default**.
Enable only the features you need by copying their `.conf.disabled` templates
to the active `.conf` names below, then apply the configuration as described below.
Active copies are Git-ignored: enable them separately on each host, including
your Raspberry Pi. Keep existing customized `.conf` files when upgrading;
copying a template over them replaces your local settings.

### Shelly support

Shelly devices send their debug output to the same **UDP port 514** as ordinary
syslog. Enable framing and parsing into MariaDB and the shared `events.log`:

```bash
cp data/syslog-ng/config/20-shelly.conf.disabled data/syslog-ng/config/20-shelly.conf
```

The default `shelly-host-mode "sender"` keeps the sender IP/hostname. Set it to
`"device"` in the active file to use Shelly hardware IDs instead.
See [Shelly configuration](docs/operations.md#enable-shelly-support) for details.

### Reverse DNS

```bash
cp data/syslog-ng/config/11-dns.conf.disabled data/syslog-ng/config/11-dns.conf
```

This enables `use_dns(yes)`, `use_fqdn(yes)` and `dns_cache(yes)`. The container's
resolver must know the sender's reverse DNS record. For Shelly names, keep
`shelly-host-mode "sender"`. Resolved names are stored for **new** records in
MariaDB and `events.log`; existing history is unchanged. Unresolved senders keep
their IP. See [reverse DNS](docs/operations.md#optional-reverse-dns).

### Separate Shelly logfile

Enable Shelly support above first, then enable the additional normalized
`/var/log/shelly.log` file:

```bash
cp data/syslog-ng/config/shelly-debug/30-debug.conf.disabled \
   data/syslog-ng/config/shelly-debug/30-debug.conf
```

The `shelly-debug/` subfolder is included only by the active Shelly module,
because this output depends on its sources and parser. The file is created
when the first matching message arrives. After applying the configuration,
follow it with:

```bash
docker compose exec syslogng tail -F /var/log/shelly.log
```

Without this extra output, Shelly messages already appear in MariaDB and the
shared `events.log` when Shelly support is enabled.
If an older active `20-shelly.conf` writes only to MariaDB, add
`destination(d_events_file);` immediately after `destination(d_mysql);` in its
normalized Shelly route, then validate and reload. `git pull` updates the
template but leaves your active copy unchanged; preserve its other settings.
See [upgrading file history](docs/operations.md#normal-file-history).

### Raw UDP diagnostics

```bash
cp data/syslog-ng/config/15-rawlog.conf.disabled data/syslog-ng/config/15-rawlog.conf
```

This writes incoming UDP messages to `/var/log/raw-udp.log` before vendor
parsing. It works independently of Shelly support and adds a diagnostic copy;
normal processing continues. Disable extra files after troubleshooting to save
space and writes. See [file diagnostics](docs/operations.md#optional-file-diagnostics).

### Apply or disable optional configuration

Before the first start, copy the desired templates and run `docker compose up -d --wait`.
For a running stack, validate syntax and reload only if the check succeeds:

```bash
docker compose exec -T syslogng syslog-ng --syntax-only --no-caps && \
  docker compose exec -T syslogng syslog-ng-ctl reload
```

No image rebuild is needed. To disable a feature, rename its active file so it
no longer ends in `.conf` (or remove only that active copy), then validate and
reload again. Keep the shipped `.disabled` templates. For a development stack,
use `docker compose -f compose.dev.yml` consistently for these commands.

### File storage

All logfiles above live under `/var/log/` **inside the collector container** and
share the same storage and rotation settings. Choose a preset in `.env`:

| Variable | Standard: persistent host files | Pi: fewer SD-card writes |
| --- | --- | --- |
| `SYSLOG_LOG_STORAGE` | `./data/syslog-ng/logs` | `ramlogs` |
| `SYSLOG_LOG_RAM_SIZE` | `128m` (unused in this mode) | `128m` |
| `LOGROTATE_CRON` | `"0 * * * *"` | `"*/5 * * * *"` |
| `LOGROTATE_SIZE` | `50M` | `2M` |
| `LOGROTATE_ROTATIONS` | `7` | `2` |

Apply storage or rotation changes by recreating the collector:

```bash
docker compose up -d --wait syslogng
```

In standard mode, `events.log`, enabled diagnostic files and `rotated/` archives
are visible under `./data/syslog-ng/logs/` on the host. RAM mode uses a temporary
128 MiB volume instead, so these files do **not** appear in that host directory
and disappear when the collector stops. Existing RAM files are not copied when
switching modes; export them first if needed. MariaDB history stays persistent
in both modes. See [storage modes and RAM snapshots](docs/raspberry-pi.md#file-storage-modes).

## Configuration and operation

- [.env.example](.env.example): all supported settings and defaults.
- [Operating guide](docs/operations.md): updates, backup/restore and diagnostics.
- [Documentation index](docs/README.md): complete operator and developer guides.

Changing `.env` credentials does not change accounts in an existing MariaDB
volume. Preserve the Compose project name and `dbdata` volume when updating.
The production file is `compose.yml`; `compose.dev.yml` builds locally.
After upgrading from the old `docker-compose*.yml` names, use the new files
consistently and keep the same project name and env settings.

## Development and checks

```bash
./tests/linter-check.sh
./tests/test-check.sh
./tests/e2e-check.sh
```

The first two commands run static/offline and Compose checks. The last command
builds and tests an isolated disposable stack; it never uses the production
project or its volumes. Tool setup may download pinned dependencies.
See [development and releases](docs/development.md) and [test coverage](tests/README.md).

## Help and security

Start with [operating and troubleshooting guidance](docs/operations.md).
[Report a reproducible issue](https://github.com/alaub81/syslogserver/issues)
with the image version, architecture and sanitized logs. Keep passwords and
private log messages out of reports. Follow [SECURITY.md](SECURITY.md) for
security-sensitive issues.

## Support this project

If this project is useful to you, you can [buy me a coffee](https://www.buymeacoffee.com/alaub81).

## License and credits

The repository's original code and documentation use the [MIT License](LICENSE).
External images and bundled projects retain their respective licenses.
