# 🛰️ SyslogServer – Dockerized rsyslog + MariaDB + Loganalyzer

A self-contained, Docker-based syslog server stack with:

- 📬 **rsyslog** – high-performance log receiver and SQL output
- 🐬 **MariaDB** – stores structured log entries
- 📊 **LogAnalyzer** – PHP web interface for searching, filtering and viewing logs
- 🐳 **Docker Compose** – orchestrates everything in isolated containers

---

## 🔧 Use Cases

- Centralized syslog collection for multiple devices or servers (via UDP or TCP)
- Database-backed log storage for long-term analysis
- Web-based interface for live log inspection and filtering
- Ideal for homelab monitoring, testing environments, or small-scale infrastructure

---

## 🚀 Quick Start

### 1. Clone this repository

```bash
git clone https://github.com/alaub81/syslogserver.git
cd syslogserver
```

### 2. Create `.env` from example

```bash
cp .env.example .env
# Then adjust ports, DB credentials, timezone etc.
```

### 3. Run setup script

```bash
chmod +x setup.sh
./setup.sh
```

> Or force re-download of Loganalyzer:
```bash
./setup.sh --force-download
```

---

## 🌐 Access

- **LogAnalyzer Web UI**: [http://localhost:8181](http://localhost:8181) (default value, configurable)
- **Syslog Input Ports**:
  - UDP: `514` (default value, configurable)
  - TCP: `514` (default value, configurable)

---

## ⚙️ Configuration Overview

### `.env`

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

# Loganalyzer Version
LOGANALYZER_VERSION=4.1.13
```

### `rsyslog.conf`

- Configured to **receive via UDP & TCP**
- Writes only to **MySQL database**, not to local log files
- Automatically disables `imklog` for container compatibility

### `init.sql`

- Creates:
  - Database: `syslogdb`
  - User: `syslog@%`
  - Table: `SystemEvents` (compatible with Loganalyzer)
  - Optional: `SystemEventsProperties`

---

## 🧪 Logging Test

Send a test message:

```bash
logger --server 127.0.0.1 --port 514 --udp "Hello from test syslog!"
```

Check in Web UI → new entry should appear.

---

## 🔐 Security Notes

- Passwords are stored via `.env` – do **not** commit secrets.
- Do not expose the database or syslog ports directly without firewall/NAT protection.
- MariaDB allows access from all containers via `%` host match – restrict as needed.

---

## 📜 License

This project is under the GPL-3.0 License. Loganalyzer is © by Adiscon GmbH.

---

## 🙌 Credits

Created by [@alaub81](https://github.com/alaub81)

LogAnalyzer by Adiscon  
rsyslog by Rainer Gerhards  
MariaDB by the MariaDB Foundation
