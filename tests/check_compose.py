#!/usr/bin/env python3
"""Validate standalone Compose files and prevent runtime configuration drift."""

import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
APPLICATION_IMAGES = {
    "syslogng": "syslogng-mysql:latest",
    "loganalyzer": "loganalyzer:dev",
    "dbcleanup": "dbcleanup:latest",
}


def configuration(filename, storage):
    result = subprocess.run([
        "docker", "compose", "--env-file", ".env.example", "-f", filename,
        "config", "--format", "json",
    ], cwd=ROOT, check=True, capture_output=True, text=True,
       env=dict(os.environ, SYSLOG_LOG_STORAGE=storage, SYSLOG_LOG_RAM_SIZE="128m"))
    return json.loads(result.stdout)


def main():
    for storage in ("./data/syslog-ng/logs", "ramlogs"):
        production = configuration("docker-compose.yml", storage)
        development = configuration("docker-compose.dev.yml", storage)
        for service, image in APPLICATION_IMAGES.items():
            build = development["services"][service].pop("build")
            context = ROOT / "resources" / service
            if Path(build["context"]).resolve() != context or build["dockerfile"] != "Dockerfile":
                raise SystemExit(f"{service}: unexpected development build context/Dockerfile")
            if not (context / build["dockerfile"]).is_file():
                raise SystemExit(f"{service}: missing Dockerfile")
            if development["services"][service]["image"] != image:
                raise SystemExit(f"{service}: unexpected development image name")
            development["services"][service]["image"] = production["services"][service]["image"]
        if production != development:
            raise SystemExit(f"Compose runtime settings differ for storage={storage}")
        mount = next(v for v in production["services"]["syslogng"]["volumes"] if v["target"] == "/var/log")
        if storage == "ramlogs":
            if mount["type"] != "volume" or mount["source"] != "ramlogs":
                raise SystemExit("RAM logging must use the ramlogs volume")
            options = production["volumes"]["ramlogs"]["driver_opts"]
            if options != {"type": "tmpfs", "device": "tmpfs", "o": "size=128m,mode=0755"}:
                raise SystemExit("RAM logging must use a bounded 128 MiB tmpfs")
        elif mount["type"] != "bind" or Path(mount["source"]) != ROOT / "data/syslog-ng/logs":
            raise SystemExit("Standard logging must persist in ./data/syslog-ng/logs")
        print(f"PASS: standalone Compose files match with storage={storage}.")


if __name__ == "__main__":
    main()
