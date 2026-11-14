# Syslog Server with LogAnalyzer

Receive syslog over UDP/TCP, store messages in MariaDB and rotating files, and
browse them in LogAnalyzer. Run the complete stack with Docker Compose on
Linux amd64 or arm64, including Raspberry Pi systems.

## Features

- Collector, database, web viewer and scheduled retention in one Compose stack.
- Optional Shelly message parsing, reverse DNS and diagnostic log files.
- Persistent file logging or a bounded RAM volume for SD-card-friendly operation.
- Healthchecks, configurable ports and isolated end-to-end regression tests.

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
openssl rand -hex 32
```

Edit `.env`: generate a separate random value for each database password, then
adjust ports, timezone and retention. Keep existing `.env` files and volumes
when updating an installation.

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

## Optional integrations

Shelly parsing, reverse DNS and extra diagnostic logs are disabled by default.
Use [optional integrations and logging modes](docs/advanced.md) to enable them.
For a Raspberry Pi, see [RAM logging and SD-card tuning](docs/raspberry-pi.md).

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
