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

### Standard Raspberry Pi defaults

Both Compose files include the tuning below for a **64-bit Pi with at least
2 GiB RAM**. After configuring `.env`, the production command is simply:

```bash
docker compose up -d
```

Local development uses `docker compose -f docker-compose.dev.yml up -d --build`.
The former `docker-compose.pi.yml` overlay is no longer needed and has been
removed. PHP/Apache configuration and the executable cleanup script are mounted
from this checkout, so the standard prebuilt images also use these settings
without waiting for a new image release.

Keep the same Compose project name (`-p`/`COMPOSE_PROJECT_NAME`) when upgrading,
so Compose reuses the existing `dbdata` volume. Recreating containers applies
these settings; existing volumes are retained. Existing `.env` values override
the defaults: consider replacing old `LOGROTATE_SIZE=50M` / `ROTATIONS=7` values
with `2M` / `2` for the 32 MiB RAM log directory. File rotation is checked hourly
by default; heavy raw/debug output can still fill this directory between checks.

| Component | Standard setting | Effect / tradeoff |
| --- | --- | --- |
| MariaDB | `DB_BUFFER_POOL_SIZE=256M` | Caches hot data and indexes in RAM; not a total MariaDB memory limit. |
| MariaDB commits | `DB_FLUSH_AT_COMMIT=1` | Keeps durable committed transactions; batching already reduces sync frequency. |
| MariaDB binlog | Disabled | Avoids a second persistent change stream; no replication or point-in-time recovery. |
| MariaDB connections | Maximum 30 | Bounds per-connection memory for this small stack. |
| syslog-ng files | `/var/log` in 32 MiB tmpfs | Optional file diagnostics disappear on restart; database rows stay persistent. |
| Temporary files | Bounded tmpfs, including MariaDB `/tmp` (64 MiB) | Avoids temporary disk writes; large sorts/exports may exhaust this space. |
| Docker service logs | `local`, 3 × 10 MiB per service, no compression | Bounds diagnostic storage and avoids rotation compression CPU cost; still writes to disk. |
| Apache | At most 8 PHP worker processes | Reserves RAM for ingestion; intended for a few UI users. |
| PHP | 64 MiB shared OPcache, JIT off | Caches PHP bytecode in RAM; no on-disk opcode cache. |

The **256 MiB buffer pool** holds frequently accessed database pages and
indexes. Repeated reads can be served from RAM, and changed pages can be
combined before writeback. It is not a 256 MiB limit on MariaDB's total RAM
and does not keep the complete log history in memory. Redo logging and durable
commits remain enabled, so this is not a promise to avoid all disk writes.

**tmpfs** makes scratch files and syslog-ng file diagnostics temporary RAM
files. The configured sizes are upper bounds, not memory reserved up front.
Stopping the container discards these files, including PHP sessions under
`/tmp`; the `dbdata` volume and its ingested application logs remain persistent.
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

