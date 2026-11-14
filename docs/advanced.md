# Optional integrations and logging modes

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
See [Shelly configuration](operations.md#enable-shelly-support) for details.

### Reverse DNS

```bash
cp data/syslog-ng/config/11-dns.conf.disabled data/syslog-ng/config/11-dns.conf
```

This enables `use_dns(yes)`, `use_fqdn(yes)` and `dns_cache(yes)`. The container's
resolver must know the sender's reverse DNS record. For Shelly names, keep
`shelly-host-mode "sender"`. Resolved names are stored for **new** records in
MariaDB and `events.log`; existing history is unchanged. Unresolved senders keep
their IP. See [reverse DNS](operations.md#optional-reverse-dns).

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
See [upgrading file history](operations.md#normal-file-history).

### Raw UDP diagnostics

```bash
cp data/syslog-ng/config/15-rawlog.conf.disabled data/syslog-ng/config/15-rawlog.conf
```

This writes incoming UDP messages to `/var/log/raw-udp.log` before vendor
parsing. It works independently of Shelly support and adds a diagnostic copy;
normal processing continues. Disable extra files after troubleshooting to save
space and writes. See [file diagnostics](operations.md#optional-file-diagnostics).

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
in both modes. See [storage modes and RAM snapshots](raspberry-pi.md#file-storage-modes).
