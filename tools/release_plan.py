#!/usr/bin/env python3
"""Require exact-commit CI and plan per-image builds or immutable image reuse."""

import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

from change_plan import IMAGES, affected_images, changed_files
from release_tags import select_tags


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def require_ci(runs, sha, branch="main"):
    eligible = [
        run
        for run in runs
        if run.get("head_sha") == sha
        and run.get("event") == "push"
        and run.get("head_branch") == branch
    ]
    if not eligible:
        raise ValueError(f"No trusted main-branch CI run for {sha}; push and finish CI first")
    latest = max(eligible, key=lambda run: (run.get("run_number", 0), run.get("run_attempt", 0)))
    if latest.get("status") != "completed" or latest.get("conclusion") != "success":
        raise ValueError(f"CI did not succeed for {sha}: {latest.get('html_url', '')}")


def fetch_ci(repository, sha):
    query = urllib.parse.urlencode({"head_sha": sha, "event": "push", "per_page": 100})
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/ci.yml/runs?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["workflow_runs"]


def registry_source(reference):
    """Only an actually missing source image permits a build fallback."""
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", reference, "--format", "{{json .Manifest}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        if any(
            word in result.stderr.lower()
            for word in ("manifest unknown", "not found", "name unknown")
        ):
            return None
        raise ValueError("Cannot verify the source image; registry authentication/network error")
    manifest = json.loads(result.stdout)
    digest = manifest.get("digest", "")
    platforms = {
        m.get("platform", {}).get("architecture")
        for m in manifest.get("manifests", [])
        if m.get("platform", {}).get("os") == "linux"
    }
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise ValueError("Registry returned an invalid image digest")
    if not {"amd64", "arm64"} <= platforms:
        return None
    return reference.rsplit(":", 1)[0] + "@" + digest


def plan_images(release, sha, previous, files, owner, inspect=registry_source, refresh=False):
    affected = set(IMAGES if refresh or not previous else affected_images(files))
    entries = []
    for image in IMAGES:
        repository = f"ghcr.io/{owner.lower()}/{image}"
        source = None if image in affected else inspect(f"{repository}:{previous[1:]}")
        entries.append(
            {
                **release,
                "sha": sha,
                "image": image,
                "repository": repository,
                "source": source or "",
                "mode": "reuse" if source else "build",
            }
        )
    return entries


def build_paths(root, image):
    root = Path(root)
    path = root / "resources" / image / "Dockerfile"
    if path.is_file():
        return str(path.parent), str(path)
    path = root / f"Dockerfile-{image}"
    if path.is_file():
        return str(root), str(path)
    raise ValueError(f"No Dockerfile for {image} in the selected source commit")


def main():
    tags = command("git", "tag", "--list").splitlines()
    requested = os.environ.get("RELEASE_TAG") or None
    selected = select_tags(tags, requested, int(os.environ.get("REBUILD_COUNT") or "1"))
    stable = sorted(
        (
            tag
            for tag in tags
            if re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag)
        ),
        key=lambda tag: tuple(map(int, tag[1:].split("."))),
    )
    entries = []
    for release in selected:
        ref = release["ref"]
        sha = command("git", "rev-parse", f"{ref}^{{commit}}")
        require_ci(
            fetch_ci(os.environ["GITHUB_REPOSITORY"], sha),
            sha,
            os.environ.get("DEFAULT_BRANCH", "main"),
        )
        index = stable.index(ref)
        previous = stable[index - 1] if index else None
        files = changed_files(previous, ref) if previous else None
        entries.extend(
            plan_images(
                release,
                sha,
                previous,
                files,
                os.environ["GITHUB_REPOSITORY_OWNER"],
                refresh=not requested,
            )
        )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write("matrix=" + json.dumps({"include": entries}, separators=(",", ":")) + "\n")
        output.write(f"has_images={'true' if entries else 'false'}\n")
    summary = "## Release plan\n\n" + "\n".join(
        f"- {entry['ref']} / {entry['image']}: {entry['mode']} ({entry['sha']})"
        for entry in entries
    )
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as output:
            output.write(summary + "\n")


if __name__ == "__main__":
    main()
