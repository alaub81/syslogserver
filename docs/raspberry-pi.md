# Raspberry Pi: storage and CPU tuning

The ingestion path uses SQL transactions of up to **100 records**, with a
**1,000 ms** timeout for incomplete batches. This reduces commit/sync overhead;
it still executes one INSERT per record. Reverse DNS is disabled in syslog-ng
and LogAnalyzer. Shelly device IDs and hostnames supplied in standard syslog
messages remain available. For sender mode, the base listener now uses IPs.
Records waiting in syslog-ng's RAM queues or an uncommitted batch can be lost
if the collector crashes. Graceful stop/reload flushes pending batches when
the destination is available; UDP itself provides no delivery guarantee.

Retention deletes up to `DBCLEANUP_BATCH_SIZE=1000` old rows per transaction,
pausing `DBCLEANUP_BATCH_PAUSE=0.1` seconds between full batches. It uses a
fixed cutoff and the `ReceivedAt` index. SQL errors fail the job; its summary
and errors are in `docker compose logs dbcleanup`. Routine `OPTIMIZE TABLE`
and the daily database event have been removed: InnoDB reuses freed pages
without rebuilding the table. The data file may retain its high-water size.

New databases omit the `Message` FULLTEXT index: the shipped LogAnalyzer uses
`LIKE`/`REGEXP` searches, which do not benefit from it. Ordinary filter indexes
are retained. Existing databases are not modified automatically. After a
backup, run the optional migration during a maintenance window to remove the
old daily event and FULLTEXT index:

```bash
docker compose exec -T database sh -c \
  'mariadb -u"$MARIADB_USER" --password="$MARIADB_PASSWORD" -D "$MARIADB_DATABASE"' \
  < data/migrations/001-sdcard-tuning.sql
```

Review the migration first if other applications query this database: they
might use `MATCH(Message) AGAINST(...)`. Altering indexes can take time and
additional disk space. Updated `init.sql` runs only on a fresh database volume.
Do not delete an existing volume to apply tuning.

### Why disable reverse DNS and the FULLTEXT index?

Reverse DNS looks up a name for an address, for example `192.168.1.42` to
`shelly-kitchen.example`. syslog-ng previously performed sender-name resolution;
LogAnalyzer also resolved IPs found inside messages. Disabling those lookups
avoids lookup/cache work and delays when a DNS server is unavailable. It does
not disable Docker's DNS: the services still resolve `database` normally.
Hostnames already present in standard syslog and the optional Shelly device-ID
mode still work; sender mode normally shows the sender IP.

The FULLTEXT index is a separate word-search structure over `Message`, which
MariaDB must maintain as records arrive and expire. It accelerates queries
using `MATCH(Message) AGAINST(...)`. The shipped LogAnalyzer builds substring
and regex filters (`LIKE '%text%'` / `REGEXP`), so it does not use that structure.
Omitting it saves index storage and maintenance work without changing those
search results. Text searches across a long retention window can still scan
many rows; narrow by time/host where possible. The ordinary host/time/filter
indexes remain. Existing databases require the optional migration above.

### File storage modes

Both standalone Compose files support the following settings through `.env`.
Keep the same Compose project name when switching modes so the existing
`dbdata` volume is reused. MariaDB and its retention are unchanged by this choice.

**Standard: persistent host files** (the shipped `.env.example` defaults):

```dotenv
SYSLOG_LOG_STORAGE=./data/syslog-ng/logs
SYSLOG_LOG_RAM_SIZE=128m
LOGROTATE_CRON="0 * * * *"
LOGROTATE_SIZE=50M
LOGROTATE_ROTATIONS=7
```

Normalized messages go to `./data/syslog-ng/logs/events.log` as JSON Lines,
with archives in `./data/syslog-ng/logs/rotated/`. Files survive container
replacement and `docker compose down --volumes`; deleting the host directory
removes this history. The seven archives plus the active file can approach
400 MiB per log before compression, and files can grow beyond the threshold
between checks. `SYSLOG_LOG_RAM_SIZE` is unused in this mode.

**Pi SD-saving trial: 128 MiB RAM logs**:

```dotenv
SYSLOG_LOG_STORAGE=ramlogs
SYSLOG_LOG_RAM_SIZE=128m
LOGROTATE_CRON="*/5 * * * *"
LOGROTATE_SIZE=2M
LOGROTATE_ROTATIONS=2
```

The project-scoped `ramlogs` named volume uses Docker's `local` driver with
`type=tmpfs`. Despite its volume name, its files are temporary and disappear
when the last container using it stops. No RAM is reserved up front; 128 MiB
is the filesystem ceiling. This is the same volatile-log approach as before,
with four times the previous 32 MiB ceiling and more frequent size checks.
SQL history remains persistent and follows `LOG_RETENTION_DAYS`.

Apply either preset by recreating the collector:

```bash
docker compose up -d --wait syslogng
# For locally built images, use the standalone development file instead:
docker compose -f docker-compose.dev.yml up -d --build --wait syslogng
```

Normal file history is enabled by the shipped syslog-ng configuration. Raw UDP
and extra Shelly debug files remain optional. All use the selected storage and
share its space. The rotation threshold is not a hard cap; busy diagnostics can
fill even 128 MiB between checks. Disable unnecessary diagnostic copies after
testing. Rotated files are compressed, with the newest archive kept uncompressed
until the next rotation so syslog-ng can finish reopening it.

When changing only the RAM size later, recreate the disposable RAM volume:

```bash
docker compose stop syslogng
docker compose rm -f syslogng
# Replace syslogserver if you use a different Compose project name.
docker volume rm syslogserver_ramlogs
docker compose up -d --wait syslogng
```

Use `-f docker-compose.dev.yml` consistently for a development stack. This removes
only temporary RAM files; do not remove `dbdata`. Switching to RAM does not
remove existing host logs, and switching back makes those files available again;
RAM-only records are not automatically copied to the host directory. Copy a
snapshot before stopping the RAM collector if you need to preserve its files.

Check the effective storage after startup:

```bash
docker compose exec syslogng df -h /var/log
docker compose exec syslogng cat /etc/logrotate.d/syslogserver
```

### Common low-memory defaults

Both files retain the settings below for a **64-bit Pi with at least 2 GiB RAM**.
The former Pi overlay is not needed. PHP/Apache settings and the cleanup script
are mounted from the checkout; SQL batching and normalized file routing come
from the shared syslog-ng snippets. Use current application images or build the
development images to get the current entrypoint/rotation defaults.

| Component | Standard setting | Effect / tradeoff |
| --- | --- | --- |
| MariaDB | `DB_BUFFER_POOL_SIZE=256M` | Caches hot data and indexes in RAM; not a total MariaDB memory limit. |
| MariaDB commits | `DB_FLUSH_AT_COMMIT=1` | Keeps durable committed transactions; batching already reduces sync frequency. |
| MariaDB binlog | Disabled | Avoids a second persistent change stream; no replication or point-in-time recovery. |
| MariaDB connections | Maximum 30 | Bounds per-connection memory for this small stack. |
| syslog-ng files | Persistent `./data/syslog-ng/logs/` by default; optional 128 MiB RAM mode | Disk mode keeps file history; RAM mode avoids persistent file writes but loses that history on stop. |
| Temporary files | Bounded tmpfs, including MariaDB `/tmp` (64 MiB) | Avoids temporary disk writes; large sorts/exports may exhaust this space. |
| Docker service logs | `local`, 3 × 10 MiB per service, no compression | Bounds diagnostic storage and avoids rotation compression CPU cost; still writes to disk. |
| Apache | At most 8 PHP worker processes | Reserves RAM for ingestion; intended for a few UI users. |
| PHP | 64 MiB shared OPcache, JIT off | Caches PHP bytecode in RAM; no on-disk opcode cache. |

The **256 MiB buffer pool** holds frequently accessed database pages and
indexes. Repeated reads can be served from RAM, and changed pages can be
combined before writeback. It is not a 256 MiB limit on MariaDB's total RAM
and does not keep the complete log history in memory. Redo logging and durable
commits remain enabled, so this is not a promise to avoid all disk writes.

**tmpfs** makes scratch files, and logs when RAM mode is selected, temporary
RAM files. The configured sizes are upper bounds, not memory reserved up front.
Stopping the container discards scratch files, including PHP sessions under
`/tmp`. RAM-mode log files are also discarded; disk-mode log files and the
`dbdata` volume remain persistent.
The 64 MiB database `/tmp` can constrain large disk-spilling sorts/exports.

The **Docker log limit** applies to container stdout/stderr (startup messages,
errors, Apache access logs and cleanup reports), not the Shelly rows in MariaDB.
The `local` driver rotates three files of approximately 10 MiB each per service
and removes the oldest. Compression is disabled to avoid compression work;
these bounded service logs are still stored on disk.

**Eight Apache workers** bound concurrent web requests and PHP process memory.
This is independent of the number of Shelly devices: devices send to syslog-ng,
not Apache. A few users can browse normally; extra concurrent requests wait
for an available worker. Only two workers start, with two to four kept spare.

**OPcache** stores compiled PHP code in shared RAM so page requests can reuse
it. It is configured for a 64 MiB opcode cache, shared across Apache workers,
not 64 MiB for each worker. Database results and rendered pages are still fresh.
PHP checks for changed code every two seconds, and JIT is disabled to avoid
additional compilation/memory overhead for this small UI.

`DB_FLUSH_AT_COMMIT=2` is an **explicit optional durability tradeoff**: MariaDB
writes redo on commit but normally syncs it about once per second. An OS crash
or power loss can lose recent committed records; this interval is not a hard
loss bound. The default remains `1`. Neither doublewrite nor redo logging is
disabled. PHP configuration edits remain visible with timestamp revalidation.

Leave sufficient RAM for syslog-ng queues, PHP workers, tmpfs and the OS.
A 256 MiB buffer pool is a starting point, not a whole-stack sizing guarantee.
On a 4+ GiB Pi, consider `DB_BUFFER_POOL_SIZE=512M` after measuring available
RAM. tmpfs can spill into host swap: SD-backed swap can undo the intended I/O
saving. Inspect swap usage and consider RAM-backed zram on the target host.
Host journald and other services also write independently of this stack.

### Expected load and measurement

Size retention from the actual message rate of your devices. For example,
15 records/s produces about 1.3 million records/day, before database rows,
indexes, redo/undo and filesystem overhead are considered. Script output and
bursts can change the rate substantially. This profile is not a Raspberry Pi
throughput benchmark.

Measure on the actual Pi under ingestion and while browsing/searching:
`docker stats`, `iostat -xz 5`, and `syslog-ng-ctl stats` (dropped/queued records).
Check MariaDB `Innodb_buffer_pool_reads`, `Innodb_buffer_pool_read_requests`,
`Innodb_data_written`, `Innodb_os_log_written`, and actual table/index sizes
over a representative interval. Compare with the same input and durability
settings. Check queue drain and burst handling, not only average CPU. Use repeatable
input when comparing configurations; local capture and replay artifacts are
not part of the distributed stack.

A named Docker volume still writes to the SD card if Docker's data directory
is on that card. For sustained storage of millions of rows, moving MariaDB's
persistent volume to a USB SSD removes the main SD write workload. Plan an
explicit backed-up migration; the default configuration keeps the current volume intact.
Reducing chatty Shelly/script logging at the source saves additional network,
CPU and storage; no records or severity levels are filtered by this tuning.
Time partitioning may be worthwhile later if retention deletes become the
bottleneck, but requires a separate schema/LogAnalyzer compatibility review.
No Redis/Memcached or HTTP result cache is needed for this write-heavy path.

References: [syslog-ng SQL batching](https://syslog-ng.github.io/admin-guide/070_Destinations/270_sql/003_sql_destination_options),
[MariaDB large deletes](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/query-optimizations/big-deletes),
[MariaDB durability settings](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-system-variables),
[Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/),
[Docker local logs](https://docs.docker.com/engine/logging/drivers/local/),
[PHP OPcache](https://www.php.net/manual/en/opcache.configuration.php).

