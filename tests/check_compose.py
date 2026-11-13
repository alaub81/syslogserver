#!/usr/bin/env python3
"""Validate standalone Compose files and prevent runtime configuration drift."""

import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
APPLICATION_IMAGES = {
    "syslogng": "syslogng-mysql:latest",
    "loganalyzer": "loganalyzer:dev",
    "dbcleanup": "dbcleanup:latest",
}


def configuration(filename):
    result = subprocess.run([
        "docker", "compose", "--env-file", ".env.example", "-f", filename,
        "config", "--format", "json",
    ], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    production = configuration("docker-compose.yml")
    development = configuration("docker-compose.dev.yml")
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
        raise SystemExit("Compose runtime settings differ: sync development with production")
    print("PASS: both standalone Compose files are valid and have identical runtime settings.")


if __name__ == "__main__":
    main()
