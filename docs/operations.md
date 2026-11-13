# Configuration and operations

## Configuration

[`.env.example`](../.env.example) documents the settings. The main groups are:

| Variables | Purpose |
| --- | --- |
| `SYSLOG_UDP_PORT`, `SYSLOG_TCP_PORT`, `LOGANALYZER_PORT` | Host listener and web ports. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD` | MariaDB database and credentials. |
| `TZ` | Container timezone. |
| `LOG_RETENTION_DAYS`, `DBCLEANUP_CRON` | Retention period and cleanup schedule. |
| `DBCLEANUP_BATCH_SIZE`, `DBCLEANUP_BATCH_PAUSE` | Rows per cleanup transaction and pause between full batches. |
| `DB_BUFFER_POOL_SIZE`, `DB_FLUSH_AT_COMMIT` | MariaDB RAM and commit durability. |
| `SYSLOG_LOG_STORAGE`, `SYSLOG_LOG_RAM_SIZE` | Persistent host files or a bounded RAM log volume. |
| `LOGROTATE_*` | File rotation threshold, schedule, age and archive count. |

The schema in `data/init.sql` runs only when MariaDB initializes a **new** volume.
Changing `.env` credentials does not update accounts in an existing database.
Keep the existing Compose project name when upgrading so the same `dbdata`
volume is reused. Back up the database before applying migrations; do not
remove an existing volume to apply configuration or schema changes.

All database clients (`syslogng`, `loganalyzer`, `dbcleanup`) use
`depends_on: database` with `condition: service_healthy`. There is no dependency
between those clients: each can operate independently once MariaDB is ready.
The development file is a standalone copy of production with local builds.
An automated Compose comparison prevents runtime settings from drifting.

## syslog-ng configuration

Snippets under `data/syslog-ng/config/` are loaded in filename order:

| File | Purpose |
| --- | --- |
| `10-syslogsrv.conf` | Shared listeners, standard parsers and SQL/file destinations. |
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

### Normal file history

All ingested messages are written to `/var/log/events.log` alongside MariaDB.
It uses JSON Lines so Unicode, embedded newlines and trailing spaces remain
unambiguous. Standard syslog and enabled Shelly parsing use the same normalized
fields in the SQL and file paths. File retention and SQL retention are separate.

By default `/var/log` is bound to `./data/syslog-ng/logs/`, including its
`rotated/` archives. Files survive container replacement and a Compose volume
reset because this is a host directory. The directory is excluded from Git.
Selecting `SYSLOG_LOG_STORAGE=ramlogs` uses the optional 128 MiB tmpfs instead;
these files disappear when the last container using that volume stops.
See [storage modes](raspberry-pi.md#file-storage-modes) for both complete presets.

If an existing local `20-shelly.conf` predates normal file history, add
`destination(d_events_file);` immediately after `destination(d_mysql);` in
its normalized Shelly log path, or update it from the shipped template while
preserving your host-mode/custom settings. Existing active copies are not
silently overwritten during an upgrade.

### Optional file diagnostics

```bash
cp data/syslog-ng/config/15-rawlog.conf.disabled data/syslog-ng/config/15-rawlog.conf
cp data/syslog-ng/config/shelly-debug/30-debug.conf.disabled data/syslog-ng/config/shelly-debug/30-debug.conf
```

Raw UDP diagnostics work independently of Shelly support. Shelly diagnostics
are loaded only by the active Shelly module. All `.log` files and the internal
syslog/messages/error/debug files share the configured rotation policy.
Diagnostic files use the same persistent directory or RAM volume as `events.log`.
To copy a diagnostic snapshot out of RAM mode:

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

Both Compose files retain modest PHP/Apache and MariaDB memory settings,
bounded scratch tmpfs and bounded Docker logs for a 64-bit Raspberry Pi with
at least 2 GiB RAM. File storage defaults to disk; select `ramlogs` and the
small-file preset to avoid persistent syslog file writes. No Pi overlay is needed.
Use the normal production or development command in the
[quick start](../README.md#quick-start) and keep the same project name when upgrading.

SQL ingestion uses transactions of up to 100 records with a 1,000 ms batch
timeout. Retention deletes bounded batches using a fixed cutoff and the
`ReceivedAt` index. Routine table rebuilds and the daily optimization event
are no longer part of new installations. Existing databases are not changed
automatically.

See [Raspberry Pi tuning](raspberry-pi.md) for the optional migration,
durability and RAM tradeoffs, and storage sizing. Durable MariaDB commits remain
the default; pending RAM queues or uncommitted batches can be lost after a crash.

## Health checks and troubleshooting

| Service | Check | Normal interval |
| --- | --- | --- |
| `syslogng` | Daemon responsiveness through `syslog-ng-ctl healthcheck`. | 1 minute |
| `database` | Local TCP `SELECT 1` with the configured application user. | 1 minute |
| `loganalyzer` | HTTP GET through curl. | 5 minutes |

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
