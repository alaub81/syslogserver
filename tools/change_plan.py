#!/usr/bin/env python3
"""Plan affected images and conservatively close the stack-test dependency graph."""

import json
import os
from pathlib import Path
import subprocess

IMAGES = ("syslogng", "loganalyzer", "dbcleanup")
CHECK_ONLY = {
    "renovate.json",
    ".github/dependabot.yml",
    "lint-tools.json",
    "ruff.toml",
    ".hadolint.yaml",
    ".yamllint.yaml",
    "tests/linter-check.sh",
    "tests/lint.py",
    "tests/requirements-lint.txt",
    "tests/install_lint_tools.py",
    "tests/test_install_lint_tools.py",
    "tests/test_dependency_config.py",
}


def changed_files(base, head="HEAD", directory=None):
    """An unavailable diff must never turn into a documentation-only pass."""
    if not base or set(base) == {"0"}:
        return None
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, head, "--"],
        cwd=directory,
        capture_output=True,
        check=False,
    )
    return result.stdout.decode().strip("\0").split("\0") if result.returncode == 0 else None


def affected_images(files):
    """Unknown files and automation changes invalidate every image assumption."""
    if files is None:
        return list(IMAGES)
    affected = set()
    for name in filter(None, files):
        if name.endswith(".md") or name == "LICENSE" or name.startswith(".vscode/"):
            continue
        if name.startswith(".github/ISSUE_TEMPLATE/") or name == ".github/FUNDING.yml":
            continue
        if name in CHECK_ONLY or name in {".editorconfig", ".gitignore"}:
            continue
        matched = next((image for image in IMAGES if name.startswith(f"resources/{image}/")), None)
        if matched:
            affected.add(matched)
        else:
            return list(IMAGES)
    return sorted(affected)


def ci_plan(files):
    affected = affected_images(files)
    docs_only = files is not None and all(
        not name
        or name.endswith(".md")
        or name == "LICENSE"
        or name.startswith(".vscode/")
        or name.startswith(".github/ISSUE_TEMPLATE/")
        or name == ".github/FUNDING.yml"
        for name in files
    )
    # The collector, UI and cleanup share one database schema. Testing any changed
    # service requires the current source versions of all three, never stale GHCR tags.
    return {
        "runtime": bool(affected),
        "tests": not docs_only,
        "affected": affected,
        "build": list(IMAGES) if affected else [],
    }


def main():
    plan = ci_plan(changed_files(os.environ.get("BASE_SHA"), os.environ.get("HEAD_SHA") or "HEAD"))
    print(json.dumps(plan, indent=2))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        for key, value in plan.items():
            output.write(f"{key}={json.dumps(value, separators=(',', ':'))}\n")


if __name__ == "__main__":
    main()
