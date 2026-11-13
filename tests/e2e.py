#!/usr/bin/env python3
"""Exercise real published UDP/TCP/HTTP ports, Shelly parsing and SQL retention."""

import datetime
from collections import Counter
import html
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class Stack:
    def __init__(self, project, directory):
        self.directory = Path(directory)
        self.config = self.directory / "syslog-config"
        self.prefix = project
        self.compose = [
            "docker", "compose", "--project-name", project,
            "--env-file", str(self.directory / "stack.env"),
            "-f", str(ROOT / "docker-compose.dev.yml"),
            "-f", str(self.directory / "override.yml"),
        ]
        self.udp_port = self.port("syslogng", 514, "udp")
        self.tcp_port = self.port("syslogng", 514, "tcp")
        self.http_port = self.port("loganalyzer", 80, "tcp")
        self.expected = {}

    def run(self, *args, **kwargs):
        return subprocess.run(self.compose + list(args), check=True, capture_output=True,
                              text=True, **kwargs).stdout.strip()

    def port(self, service, port, protocol):
        address = self.run("port", "--protocol", protocol, service, str(port))
        if not address.startswith("127.0.0.1:"):
            raise AssertionError(f"Test port must be loopback-only: {address}")
        return int(address.rsplit(":", 1)[1])

    def query(self, sql):
        return self.run("exec", "-T", "database", "sh", "-ec", '''
exec mariadb --connect-timeout=5 --user="$MARIADB_USER" --password="$MARIADB_PASSWORD" \
  --database="$MARIADB_DATABASE" --batch --raw --skip-column-names
''', input=sql)

    def udp(self, payload):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.sendto(payload.encode("utf-8"), ("127.0.0.1", self.udp_port))

    def tcp(self, messages):
        with socket.create_connection(("127.0.0.1", self.tcp_port), timeout=5) as connection:
            for message in messages:
                payload = message.encode("utf-8")
                connection.sendall(str(len(payload)).encode("ascii") + b" " + payload)

    def expect(self, message, **fields):
        if message in self.expected:
            raise AssertionError(f"Duplicate test expectation: {message}")
        self.expected[message] = fields

    def rows(self):
        # Test identifiers contain only letters, numbers and hyphens.
        result = self.query(f"""
SELECT JSON_OBJECT('message', Message, 'host', FromHost, 'tag', SysLogTag,
                   'pid', ProcessID, 'priority', Priority, 'facility', Facility,
                   'source', EventSource,
                   'recent', ABS(TIMESTAMPDIFF(SECOND, ReceivedAt, DeviceReportedTime)) < 60)
FROM SystemEvents WHERE Message LIKE '%{self.prefix}%' ORDER BY ID;
""")
        return [json.loads(line) for line in result.splitlines() if line]

    def verify(self, label):
        deadline = time.monotonic() + 30
        while True:
            rows = self.rows()
            if len(rows) >= len(self.expected) or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        actual = {}
        for row in rows:
            message = row.pop("message")
            if message in actual:
                raise AssertionError(f"Duplicate database row: {message!r}")
            actual[message] = row
        if actual.keys() != self.expected.keys():
            raise AssertionError(f"{label}: expected {self.expected.keys()}, got {actual.keys()}")
        for message, fields in self.expected.items():
            for key, value in fields.items():
                if actual[message][key] != value:
                    raise AssertionError(f"{message!r}: {key}={actual[message][key]!r}, expected {value!r}")
        print(f"PASS: {label} ({len(rows)} exact rows, no duplicates).", flush=True)
        return actual

    def standard(self, phase):
        stamp = datetime.datetime.now(datetime.timezone.utc)
        udp = f"{self.prefix}-{phase}-udp"
        tcp = f"{self.prefix}-{phase}-tcp Grüße 🌡\nsecond line  "
        tcp_second = f"{self.prefix}-{phase}-tcp-second"
        self.udp(f"<14>{stamp.strftime('%b %e %T')} ci-host ci-udp: {udp}")
        self.tcp([
            f"<14>1 {stamp.strftime('%Y-%m-%dT%H:%M:%SZ')} ci-host ci-tcp 42 - - {tcp}",
            f"<14>1 {stamp.strftime('%Y-%m-%dT%H:%M:%SZ')} ci-host ci-tcp 43 - - {tcp_second}",
        ])
        self.expect(udp, host="ci-host", tag="ci-udp", priority=6, facility=1)
        self.expect(tcp, host="ci-host", tag="ci-tcp", pid=42, priority=6, facility=1)
        self.expect(tcp_second, host="ci-host", tag="ci-tcp", pid=43, priority=6, facility=1)

    def reload(self, mode, diagnostics=False):
        module = (ROOT / "data/syslog-ng/config/20-shelly.conf.disabled").read_text()
        module = module.replace('@define shelly-host-mode "sender"', f'@define shelly-host-mode "{mode}"')
        (self.config / "20-shelly.conf").write_text(module)
        if diagnostics:
            shutil.copyfile(ROOT / "data/syslog-ng/config/15-rawlog.conf.disabled",
                            self.config / "15-rawlog.conf")
            (self.config / "shelly-debug").mkdir(exist_ok=True)
            shutil.copyfile(ROOT / "data/syslog-ng/config/shelly-debug/30-debug.conf.disabled",
                            self.config / "shelly-debug/30-debug.conf")
        self.run("exec", "-T", "syslogng", "syslog-ng", "--syntax-only", "--no-caps")
        output = self.run("exec", "-T", "syslogng", "syslog-ng-ctl", "reload")
        if "success" not in output.lower():
            raise AssertionError(f"Reload failed: {output}")

    def shelly(self, mode):
        device = "shellyplus1-aabbccddeeff"
        fields = {"host": device} if mode == "device" else {}
        frames = []
        for level, priority in enumerate((3, 4, 6, 7, 7)):
            message = f"{self.prefix}-{mode}-level-{level}"
            frames.append(f"{device} {level} 123.456 2 {level}|shelly_main.cpp:123 {message}")
            self.expect(message, tag="shelly_main.cpp", source="shelly_main.cpp:123",
                        pid=0, priority=priority, recent=1, **fields)
        for channel in (101, 102):
            message = f'{self.prefix}-{mode}-script-{channel} "quoted" Grüße 🌡\nnext line  '
            frames.append(f"{device} 20 124.5 {channel} 2|{message}")
            self.expect(message, tag="shelly-script", pid=0, priority=6, **fields)
        fragment = f'{device} {self.prefix}-{mode}-fragment {{"partial":'
        frames.append(fragment)
        self.expect(fragment, tag="shelly-other", pid=0, **fields)
        unfamiliar = f"{self.prefix}-{mode}-unknown-channel"
        frames.append(f"{device} 21 125.5 999 1|{unfamiliar}")
        self.expect(unfamiliar, tag="shelly-other", priority=4, **fields)
        # Multiple records, empty separators and a trailing NUL in one UDP datagram.
        self.udp("\0\0".join(frames) + "\0")
        older = f"{self.prefix}-{mode}-older-header"
        self.tcp([f"{device} 22 126.5 2|shelly_old.cpp:7 {older}"])
        self.expect(older, tag="shelly_old.cpp", source="shelly_old.cpp:7", pid=0,
                    priority=6, **fields)
        self.standard(mode)
        rows = self.verify(f"Shelly {mode} mode, NUL framing, UTF-8, metadata and standard syslog")
        if mode == "sender":
            hosts = {row["host"] for message, row in rows.items() if f"-{mode}-" in message
                     and "-tcp" not in message and "-udp" not in message}
            if len(hosts) != 1 or not next(iter(hosts)) or device in hosts:
                raise AssertionError(f"Sender mode must retain the transport sender: {hosts}")

    def dns_module(self):
        def send(label, host):
            message = f"{self.prefix}-{label}"
            payload = f"shellyplus1-aabbccddeeff 30 130.5 2 2|ci-dns.cpp:1 {message}"
            self.run("exec", "-T", "-e", f"TEST_PAYLOAD={payload}", "syslogng", "sh", "-ec",
                     'printf "%s" "$TEST_PAYLOAD" | nc -u -s 127.0.0.42 -w 1 127.0.0.1 514')
            self.expect(message, host=host, tag="ci-dns.cpp", source="ci-dns.cpp:1", priority=6, pid=0)

        send("dns-default-off", "127.0.0.42")
        self.verify("DNS is disabled by default")
        module = self.config / "11-dns.conf"
        shutil.copyfile(ROOT / "data/syslog-ng/config/11-dns.conf.disabled", module)
        self.reload("sender")
        send("dns-enabled", "dns-e2e.example.test")
        self.standard("dns")
        self.verify("Copied DNS module resolves sender FQDNs and preserves supplied syslog hostnames")
        module.unlink()
        self.reload("sender")
        send("dns-disabled-again", "127.0.0.42")
        self.verify("Removing the DNS module restores sender IPs without changing existing rows")
        self.check_file_history()

    def check_ui(self):
        # Query through the host-published HTTP port, without relying on a health probe.
        with urllib.request.urlopen(f"http://127.0.0.1:{self.http_port}/index.php", timeout=30) as response:
            page = html.unescape(response.read().decode("utf-8", errors="replace"))
        for marker in ("standard-udp", "standard-tcp", "sender-level-0", "device-script-101", "device-fragment"):
            if f"{self.prefix}-{marker}" not in page:
                raise AssertionError(f"LogAnalyzer does not display {marker}")
        print("PASS: LogAnalyzer displays standard and Shelly messages through published HTTP.", flush=True)

    def retention(self):
        # More rows than the configured batch size force multiple real transactions.
        for index in range(5):
            self.query(f"""
INSERT INTO SystemEvents (ReceivedAt, DeviceReportedTime, Facility, Priority, FromHost, Message)
VALUES (NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY, 1, 6, 'ci-host', '{self.prefix}-expired-{index}');
""")
        self.run("exec", "-T", "dbcleanup", "/app/dbcleanup.sh")
        self.verify("Retention removes all five expired rows and preserves every fresh row")

    def check_diagnostics(self):
        raw = self.run("exec", "-T", "syslogng", "cat", "/var/log/raw-udp.log")
        normalized = self.run("exec", "-T", "syslogng", "cat", "/var/log/shelly.log")
        if f"{self.prefix}-device-level-0" not in raw or f"{self.prefix}-device-level-0" not in normalized:
            raise AssertionError("Enabled raw and Shelly diagnostic outputs must contain the test messages")
        print("PASS: Optional raw and normalized Shelly diagnostics receive messages.", flush=True)



    def file_rows(self):
        output = self.run("exec", "-T", "syslogng", "sh", "-ec", '''
for path in /var/log/events.log /var/log/rotated/events.log-*; do
  [ -f "$path" ] || continue
  case "$path" in
    *.gz) gzip -cd -- "$path" ;;
    *) cat -- "$path" ;;
  esac
done
''')
        return [row for line in output.splitlines() if line
                and self.prefix in (row := json.loads(line)).get("MESSAGE", "")]

    def check_file_history(self, expected=None):
        expected = self.expected if expected is None else expected
        deadline = time.monotonic() + 15
        while True:
            rows = self.file_rows()
            actual = Counter(row["MESSAGE"] for row in rows)
            if actual == Counter(expected.keys()) or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        if actual != Counter(expected.keys()):
            raise AssertionError(f"File history differs from SQL expectations: {actual}")
        mapping = {"host": "HOST", "tag": "PROGRAM", "priority": "LEVEL_NUM", "pid": "PID"}
        for row in rows:
            for field, key in mapping.items():
                if field in expected[row["MESSAGE"]]:
                    value = int(row[key]) if field in ("priority", "pid") else row[key]
                    if value != expected[row["MESSAGE"]][field]:
                        raise AssertionError(f"File metadata mismatch: {field} in {row}")
        print(f"PASS: JSON file history contains {len(rows)} exact normalized records without duplicates.", flush=True)

    def restart_collector(self):
        self.run("restart", "--timeout", "10", "syslogng")
        self.run("up", "--no-deps", "--no-build", "--pull", "never", "--wait",
                 "--wait-timeout", "90", "syslogng")
        # Docker can allocate different ephemeral published ports after restart.
        self.udp_port = self.port("syslogng", 514, "udp")
        self.tcp_port = self.port("syslogng", 514, "tcp")

    def persistent_files(self):
        rule = self.run("exec", "-T", "syslogng", "cat", "/etc/logrotate.d/syslogserver")
        if "size 50M" not in rule or "rotate 7" not in rule:
            raise AssertionError("Persistent logging must use the standard 50M/7 rotation settings")
        self.check_file_history()
        self.run("exec", "-T", "syslogng", "logrotate", "--state",
                 "/var/lib/logrotate/status", "/etc/logrotate.d/syslogserver")
        self.run("exec", "-T", "syslogng", "logrotate", "--force", "--state",
                 "/var/lib/logrotate/e2e-status", "/etc/logrotate.d/syslogserver")
        # A forced rotation must reopen the active file and keep the old history.
        self.standard("rotated")
        self.verify("SQL ingestion continues after file rotation")
        self.check_file_history()
        self.restart_collector()
        self.standard("file-restart")
        self.verify("SQL ingestion continues after collector restart")
        self.check_file_history()
        print("PASS: Persistent file history survives rotation and container restart.", flush=True)

    def ram_files(self):
        override = self.directory / "override.yml"
        original = override.read_text()
        mount = f"- {self.directory}/logs:/var/log"
        if mount not in original:
            raise AssertionError("Missing isolated test log directory")
        override.write_text(original.replace(mount, "- ramlogs:/var/log"))
        env = self.directory / "stack.env"
        content = env.read_text().replace('LOGROTATE_CRON="0 * * * *"', 'LOGROTATE_CRON="*/5 * * * *"')
        content = content.replace("LOGROTATE_SIZE=50M", "LOGROTATE_SIZE=2M")
        content = content.replace("LOGROTATE_ROTATIONS=7", "LOGROTATE_ROTATIONS=2")
        content = content.replace("SYSLOG_LOG_STORAGE=./data/syslog-ng/logs", "SYSLOG_LOG_STORAGE=ramlogs")
        env.write_text(content)
        self.run("up", "--no-deps", "--no-build", "--pull", "never", "--force-recreate",
                 "--wait", "--wait-timeout", "90", "syslogng")
        self.udp_port = self.port("syslogng", 514, "udp")
        self.tcp_port = self.port("syslogng", 514, "tcp")
        filesystem = self.run("exec", "-T", "syslogng", "stat", "-f", "-c", "%T", "/var/log")
        capacity = self.run("exec", "-T", "syslogng", "df", "-kP", "/var/log").splitlines()[-1].split()[1]
        if filesystem != "tmpfs" or int(capacity) != 128 * 1024:
            raise AssertionError(f"Expected a 128 MiB tmpfs, got {filesystem}/{capacity} KiB")
        if self.file_rows():
            raise AssertionError("RAM mode must not import persistent log history")
        rule = self.run("exec", "-T", "syslogng", "cat", "/etc/logrotate.d/syslogserver")
        schedule = self.run("exec", "-T", "syslogng", "cat", "/etc/cron.d/syslogrotate")
        if "size 2M" not in rule or "rotate 2" not in rule or not schedule.startswith("*/5 * * * * "):
            raise AssertionError("RAM logging must use 2M/2 rotation checked every five minutes")
        previous = set(self.expected)
        self.standard("ram")
        self.verify("RAM file mode preserves the database and accepts new messages")
        self.check_file_history({key: value for key, value in self.expected.items() if key not in previous})
        self.restart_collector()
        if self.file_rows():
            raise AssertionError("RAM file history must be discarded when the collector stops")
        previous = set(self.expected)
        self.standard("ram-restart")
        self.verify("Database history survives RAM log reset")
        self.check_file_history({key: value for key, value in self.expected.items() if key not in previous})
        if not list((self.directory / "logs/rotated").glob("events.log-*")):
            raise AssertionError("Switching to RAM must leave persistent archives on the host intact")
        print("PASS: 128 MiB RAM logs are ephemeral; persistent host archives and SQL history are retained.", flush=True)


def main():
    stack = Stack(*sys.argv[1:])
    stack.standard("standard")
    unparsed = f"shellyplus1-aabbccddeeff 1 123.456 2 2|{stack.prefix}-disabled"
    stack.udp(unparsed)
    stack.expect(unparsed.split(" ", 1)[1])
    stack.verify("Default configuration with Shelly disabled and published UDP/TCP ports")
    stack.reload("sender")
    stack.shelly("sender")
    stack.dns_module()
    stack.reload("device", diagnostics=True)
    stack.shelly("device")
    stack.check_ui()
    stack.check_diagnostics()
    stack.persistent_files()
    stack.ram_files()
    stack.retention()


if __name__ == "__main__":
    main()
