#!/usr/bin/env python3
"""Scan local image IDs, then publish only those exact configs and platform digests."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from release_plan import build_paths

ROOT = Path(__file__).resolve().parents[1]
ARCHES = ("amd64", "arm64")


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def local_tag(entry, arch):
    return f"release-{entry['image']}:{arch}"


def identity(tag, arch, execute=run):
    image = json.loads(execute("docker", "image", "inspect", tag))[0]
    descriptor = image.get("Descriptor")
    if descriptor:
        # Containerd-backed Docker stores expose manifest/index IDs. Select the
        # platform manifest explicitly instead of confusing that ID with a config.
        image = json.loads(
            execute("docker", "image", "inspect", "--platform", f"linux/{arch}", tag)
        )[0]
        descriptor = image.get("Descriptor", {})
        if not descriptor.get("mediaType", "").endswith("manifest.v1+json") and not descriptor.get(
            "mediaType", ""
        ).endswith("manifest.v2+json"):
            raise ValueError(f"Expected a single-platform manifest for {tag}")
    if image["Os"] != "linux" or image["Architecture"] != arch:
        raise ValueError(f"Wrong platform for {tag}")
    return {"id": image["Id"], "kind": "manifest" if descriptor else "config"}


def prepare(entry, source):
    context, dockerfile = build_paths(source, entry["image"])
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"context={context}\ndockerfile={dockerfile}\n")
        modern = re.search(r"(?im)^FROM .* AS os-packages$", Path(dockerfile).read_text())
        output.write(f"full_refresh={str(not bool(modern)).lower()}\n")
    if entry["mode"] == "reuse":
        for arch in ARCHES:
            run("docker", "pull", "--platform", f"linux/{arch}", entry["source"])
            run("docker", "tag", entry["source"], local_tag(entry, arch))
            identity(local_tag(entry, arch), arch)


def scan(entry, reports, execute=run):
    reports = Path(reports).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    receipt = reports / "checked-images.json"
    receipt.unlink(missing_ok=True)
    checked = {}
    failures = []
    probes = {
        "syslogng": ("syslog-ng", "--version"),
        "loganalyzer": ("php", "--version"),
        "dbcleanup": ("bash", "-n", "/app/dbcleanup.sh"),
    }
    for arch in ARCHES:
        try:
            tag = local_tag(entry, arch)
            checked_identity = identity(tag, arch, execute)
            image_id = checked_identity["id"]
            executable, *arguments = probes[entry["image"]]
            execute(
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--platform",
                f"linux/{arch}",
                "--entrypoint",
                executable,
                image_id,
                *arguments,
            )
            execute(
                "bash",
                str(ROOT / "tests/scan-images.sh"),
                str(reports),
                f"{entry['image']}-{arch}={image_id}",
                cwd=ROOT,
                env=dict(
                    os.environ,
                    SCAN_CATEGORY=f"{entry['ref']}-{arch}",
                    SCAN_PLATFORM=f"linux/{arch}",
                ),
            )
            # Refuse a changed tag even if a concurrent local operation retagged it.
            if identity(tag, arch, execute) != checked_identity:
                raise ValueError(f"Image changed during scanning: {tag}")
            checked[arch] = checked_identity
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            failures.append(f"{arch}: {error}")
    if failures:
        raise ValueError("Image validation failed: " + "; ".join(failures))
    receipt.write_text(json.dumps({"entry": entry, "images": checked}, indent=2) + "\n")


def publish(entry, reports, execute=run):
    receipt = json.loads((Path(reports) / "checked-images.json").read_text())
    if receipt["entry"] != entry or set(receipt["images"]) != set(ARCHES):
        raise ValueError("No complete scan receipt for this release plan")
    for arch in ARCHES:
        if identity(local_tag(entry, arch), arch, execute) != receipt["images"][arch]:
            raise ValueError("The local image differs from the successfully scanned image")
    repository = entry["repository"]
    sources = []
    for arch in ARCHES:
        # Staging tags are unique to the run and are never public release aliases.
        tag = f"{repository}:checked-{os.environ['GITHUB_RUN_ID']}-{arch}"
        execute("docker", "tag", receipt["images"][arch]["id"], tag)
        execute("docker", "push", tag)
        manifest = json.loads(
            execute(
                "docker", "buildx", "imagetools", "inspect", tag, "--format", "{{json .Manifest}}"
            )
        )
        digest = manifest.get("digest", "")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise ValueError("Invalid pushed platform digest")
        reference = f"{repository}@{digest}"
        raw = json.loads(execute("docker", "buildx", "imagetools", "inspect", reference, "--raw"))
        checked = receipt["images"][arch]
        observed = digest if checked["kind"] == "manifest" else raw.get("config", {}).get("digest")
        if observed != checked["id"]:
            raise ValueError("Registry image config/manifest differs from scanned image ID")
        sources.append(reference)
    # Verify the candidate index before moving any stable aliases.
    candidate = f"{repository}:checked-{os.environ['GITHUB_RUN_ID']}"
    execute("docker", "buildx", "imagetools", "create", "--tag", candidate, *sources)
    manifest = json.loads(
        execute(
            "docker", "buildx", "imagetools", "inspect", candidate, "--format", "{{json .Manifest}}"
        )
    )
    found = {m.get("digest") for m in manifest.get("manifests", [])}
    if found != {source.split("@", 1)[1] for source in sources}:
        raise ValueError("Candidate index does not contain exactly the checked platform digests")
    args = ["docker", "buildx", "imagetools", "create"]
    for alias in entry["aliases"]:
        args.extend(("--tag", f"{repository}:{alias}"))
    execute(*args, f"{repository}@{manifest['digest']}")
    (Path(reports) / "published.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "scan", "publish"))
    parser.add_argument("--entry", default=os.environ.get("RELEASE_ENTRY"), required=False)
    parser.add_argument("--source", default="source")
    parser.add_argument("--reports", default="reports")
    args = parser.parse_args()
    entry = json.loads(args.entry)
    if args.operation == "prepare":
        prepare(entry, args.source)
    elif args.operation == "scan":
        scan(entry, args.reports)
    else:
        publish(entry, args.reports)


if __name__ == "__main__":
    main()
