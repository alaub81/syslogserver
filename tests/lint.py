#!/usr/bin/env python3
"""Run the same read-only repository checks locally and in CI."""

import json
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_linter_versions():
    """Keep Python tools aligned with the versions used by CI."""
    passed = True
    for line in (ROOT / "tests/requirements-lint.txt").read_text().splitlines():
        if "==" not in line:
            continue
        package, expected = line.split("==", 1)
        try:
            actual = version(package)
        except PackageNotFoundError:
            actual = "not installed"
        if actual != expected:
            print(f"{package}: expected {expected}, found {actual}", flush=True)
            passed = False
    return passed


def project_files():
    """Include new source files, excluding ignored artifacts and deleted paths."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        {
            name.decode("utf-8")
            for name in result.stdout.split(b"\0")
            if name and (ROOT / name.decode("utf-8")).is_file()
        }
    )


def check_text(files):
    passed = True
    for name in files:
        raw = (ROOT / name).read_bytes()
        # Binary assets are outside the text hygiene check.
        if b"\0" in raw:
            continue
        try:
            content = raw.decode("utf-8")
        except UnicodeError:
            print(f"{name}: invalid UTF-8", flush=True)
            passed = False
            continue
        issues = []
        if "\r" in content:
            issues.append("use LF line endings")
        if content and not content.endswith("\n"):
            issues.append("missing final newline")
        for number, line in enumerate(content.splitlines(), 1):
            if re.match(r"^(<{7}|={7}|>{7})(?: |$)", line):
                issues.append(f"line {number}: unresolved merge marker")
            if not name.endswith(".md") and line.rstrip() != line:
                issues.append(f"line {number}: trailing whitespace")
        for issue in issues:
            print(f"{name}: {issue}", flush=True)
        passed = passed and not issues
    return passed


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def check_json(files):
    passed = True
    for name in files:
        try:
            json.loads((ROOT / name).read_text(), object_pairs_hook=unique_keys)
        except (ValueError, UnicodeError) as error:
            print(f"{name}: {error}", flush=True)
            passed = False
    return passed


def main():
    if len(sys.argv) != 1:
        print("Usage: ./tests/linter-check.sh", file=sys.stderr)
        return 2
    if not check_linter_versions():
        print("Prepare tools with ./tests/linter-check.sh", file=sys.stderr)
        return 1
    files = project_files()
    if not files:
        print("No project files found.", file=sys.stderr)
        return 1
    results = []

    def check(label, paths, command=None, function=None):
        if not paths:
            return
        print(f"\n==> {label} ({len(paths)} files)", flush=True)
        if function:
            passed = function(paths)
        elif not shutil.which(command[0]):
            print(f"Missing tool: {command[0]}; run ./tests/linter-check.sh", flush=True)
            passed = False
        else:
            passed = subprocess.run(command + paths, cwd=ROOT, check=False).returncode == 0
        results.append((label, passed))

    check("Text hygiene", files, function=check_text)
    # VS Code settings permit JSON comments and are not strict JSON.
    check(
        "JSON",
        [p for p in files if p.endswith(".json") and p != ".vscode/settings.json"],
        function=check_json,
    )
    check("ShellCheck", [p for p in files if p.endswith(".sh")], command=["shellcheck"])
    check(
        "Hadolint",
        [p for p in files if Path(p).name.startswith("Dockerfile")],
        command=["hadolint", "--config", ".hadolint.yaml", "--failure-threshold", "warning"],
    )
    check(
        "YAML",
        [p for p in files if p.endswith((".yml", ".yaml"))],
        command=["yamllint", "--strict", "--config-file", ".yamllint.yaml"],
    )
    check(
        "GitHub Actions",
        [p for p in files if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))],
        command=["actionlint", "-pyflakes="],
    )
    check(
        "Python / Ruff",
        [p for p in files if p.endswith(".py")],
        command=["ruff", "check", "--no-cache", "--config", "ruff.toml"],
    )
    print("\n================ Summary ================", flush=True)
    for label, passed in results:
        print(f"{'PASS' if passed else 'FAIL'}  {label}", flush=True)
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nLint checks interrupted.", file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Lint checks failed: {error}", file=sys.stderr)
        sys.exit(1)
