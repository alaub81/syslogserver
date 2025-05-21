# 🛰️ SyslogServer (with syslog-ng, MariaDB & Loganalyzer)

A modular Docker-based syslog collection and analysis stack with:

- 🔧 **syslog-ng** (with custom parsers) – structured syslog intake over UDP/TCP and SQL output
- 🐬 **MariaDB** – stores logs in the `SystemEvents` table
- 📊 **LogAnalyzer** – web UI for browsing, filtering and analyzing log messages
- 🧹 **Database Cleanup Service** -  daily cleanup tasks on the `SystemEvents` table

This syslog stack is also optimized for use with **Shelly** devices, whose raw debug messages are parsed and normalized before insertion.

---

## 🧱 Components

| Service      | Description                                 |
|--------------|---------------------------------------------|
| `syslogng`   | Receives, parses and classifies syslog data and sends it to the database |
| `mariadb`    | Stores structured events (Adiscon schema)   |
| `loganalyzer`| PHP UI for web-based log inspection         |
| `cleanupdb`  | supercronic powered database cleanup maintenance service  |

---

## 🚀 Getting Started

### 1. Clone this repository

```bash
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
```

### 2. Configure `.env`

```bash
cp .env.example .env
# Then adjust ports, DB credentials, timezone etc.
```

### 3. Run setup

```bash
chmod +x setup.sh
./setup.sh
```

> Will build images, download Loganalyzer, initialize DB, and start all containers.
> Or force re-download of Loganalyzer:

```bash
./setup.sh --force-download
```

---

## 🌐 Access & Ports

- **LogAnalyzer**: [http://localhost:8181](http://localhost:8181)
- **Syslog UDP**: `514/udp`
- **Syslog TCP**: `514/tcp`

## ⚙️ Configuration Overview

### `.env`

The loganalyzer version can be checked here: [https://loganalyzer.adiscon.com/download/](https://loganalyzer.adiscon.com/download/)

All key settings are externalized:

```env
# Timezone
TZ=Europe/Berlin

# Ports
SYSLOG_UDP_PORT=514
SYSLOG_TCP_PORT=514
LOGANALYZER_PORT=8181

# Database
DB_ROOT_PASSWORD=supersecurepassword
## Delete Database entries older then:
LOG_RETENTION_DAYS=30

# Loganalyzer Version (https://loganalyzer.adiscon.com/download/)
LOGANALYZER_VERSION=4.1.13
```

### `./data/syslog-ng/config/10-syslogsrv.conf`

- Configured to **receive via UDP & TCP**
- Writes to **MariaDB database**
- Shelly parsers

### `init.sql`

- Creates:
  - Database: `syslogdb`
  - User: `syslog@%`
  - Table: `SystemEvents` (compatible with Loganalyzer)
  - Optional: `SystemEventsProperties`

### ⏰ Database Retention Scheduling

The cleanup schedule is defined in the `resources/dbcleanup.cron` file using standard cron syntax.

```cron
5 10 * * * /app/dbcleanup.sh
```

This example runs the cleanup job daily at **10:05 AM** container time. If you change it, you have to rebuild the dbcleanup container.

---

## 🧩 syslog-ng Features

- Parses Shelly logs using `regexp-parser` blocks
- Extracts fields like `LEVEL`, `PROGRAM`, `MESSAGE`, `PID` from raw payload
- Logs are normalized into classic syslog fields
- Output is written into MariaDB using:

```sql
INSERT INTO SystemEvents (
  ReceivedAt, DeviceReportedTime,
  Facility, Priority,
  FromHost, Message, SysLogTag, Importance
)
```

---

## 🧠 Shelly Parser Example

Located in `data/syslog-ng/config/10-syslogsrv.conf`:

```syslog-ng
parser p_shelly_level {
  regexp-parser(
    pattern("^(?P<LEVEL>[A-Z]+)")
    ...
  );
};
```

→ Used in `log { ... parser(p_shelly_level); };` block

---

## 🗃️ Database Schema

SystemEvents follows Adiscon LogAnalyzer format:

| Field            | Description                 |
|------------------|-----------------------------|
| `ReceivedAt`     | Timestamp at syslog-ng      |
| `FromHost`       | IP/hostname from device     |
| `Message`        | Cleaned-up log payload      |
| `SysLogTag`      | Program name (if present)   |
| `Importance`     | Drives "Message Type" column in UI |
| `EventLogType`   | Used in detailed view, optional |

---

## 🧪 Test a log

Send a test message:

```bash
logger -n 127.0.0.1 -P 514 -d "DEBUG test log from shell"
```

Then check Loganalyzer.

---

## ⚙️ Customization

- Shelly-specific parsing rules → `data/syslog-ng/config/10-syslogsrv.conf`
- SQL output fields can be adapted in the `sql()` block
- To map `Importance`, add dynamic rules or static override (`Importance => 0`)

---

## 🧹 Database Cleanup Service (`dbcleanup`)

This project includes a maintenance container called `dbcleanup`, which performs daily cleanup tasks on the `SystemEvents` table inside the MariaDB instance.

### ✨ Purpose

- Deletes old syslog entries older than a defined number of days.
- Optimizes the `SystemEvents` table after cleanup.
- Logs all actions to the syslog server (`syslog-ng`), visible in LogAnalyzer.

---

## 🔐 Security Notes

- Passwords are stored via `.env` – do **not** commit secrets.
- Do not expose the database or syslog ports directly without firewall/NAT protection.
- MariaDB allows access from all containers via `%` host match – restrict as needed.

---

## 📜 License

This project: GPL-3.0 License
LogAnalyzer: © Adiscon GmbH  
syslog-ng: © One Identity

---

## 🙌 Credits

Maintained by [@alaub81](https://github.com/alaub81)  
Log parsing magic powered by `syslog-ng` + `regexp-parser`
LogAnalyzer by Adiscon
MariaDB by the MariaDB Foundation
