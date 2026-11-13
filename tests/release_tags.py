#!/usr/bin/env python3
"""Select stable releases without moving major/minor/latest aliases backwards."""

import json
import os
import re
import subprocess


def select_tags(tags, requested=None, count=1):
    versions = {}
    for tag in tags:
        match = re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag)
        if match:
            versions[tag] = tuple(map(int, match.groups()))
    ordered = sorted(versions, key=versions.get, reverse=True)
    if not ordered:
        raise ValueError("No stable vMAJOR.MINOR.PATCH release tags found")
    if not 1 <= count <= 20:
        raise ValueError("The rebuild count must be between 1 and 20")
    if requested and requested not in versions:
        raise ValueError(f"Not a stable release tag: {requested}")
    result = []
    for tag in [requested] if requested else ordered[:count]:
        version = versions[tag]
        aliases = [tag[1:]]
        # Only the newest patch/minor in a series may update its shared alias.
        for length in (2, 1):
            latest = next(t for t in ordered if versions[t][:length] == version[:length])
            if tag == latest:
                aliases.append(".".join(map(str, version[:length])))
        if tag == ordered[0]:
            aliases.append("latest")
        result.append({"ref": tag, "aliases": aliases})
    return result


def main():
    tags = subprocess.check_output(["git", "tag", "--list"], text=True).splitlines()
    requested = os.environ.get("RELEASE_TAG") or None
    count = int(os.environ.get("REBUILD_COUNT") or "1")
    matrix = select_tags(tags, requested, count)
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write("releases=" + json.dumps(matrix, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
