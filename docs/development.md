# Development and dependency updates

The Dockerfiles, development Compose file, runtime resources, CI configuration
and automated regression tests remain in the repository. Run the cleanup
regressions without a live database:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the same lint checks as CI (or the VS Code task `lint:all`):

```bash
./tests/linter-check.sh
```

The command prepares isolated, pinned tools and checks text hygiene, local
Markdown links, environment examples, JSON, ShellCheck, Hadolint, strict YAML,
GitHub Actions and Python correctness. It includes new, non-ignored files and never fixes source
files. See [tests/README.md](../tests/README.md) for setup and scope.

Local packet captures, copied live logs, replay outputs, one-off diagnostic
scripts and downloaded vendor archives belong under **`.local/`**. This directory
is excluded from Git and normal Docker build contexts and is not required to
run or build the stack. Local active configuration files and `.env` remain in
their documented locations and are also Git-ignored.

## Dependency updates

Renovate manages version-update PRs for GitHub Actions, Dockerfiles, Compose
images, Python and native lint tools, LogAnalyzer and Supercronic. Supercronic's
download URLs in the syslogng and dbcleanup Dockerfiles are updated together.
New update branches are scheduled for Mondays before 06:00 Europe/Berlin.
Non-major updates are grouped separately for Actions and Python lint
dependencies; Docker images and major upgrades are reviewed per dependency.
Automerge is disabled. The Dependency Dashboard tracks pending updates.

The three application Dockerfiles refresh package lists and upgrade installed
Debian packages before installing their dependencies. Their official base images
already enable the matching Debian security repository. CI and release builds
re-run the `os-packages` stage with `no-cache-filters`; local fresh builds can use
`docker compose -f docker-compose.dev.yml --env-file .env build --pull --no-cache`.
This picks up available package fixes even before a base image is republished.
Rebuilding an older release tag still uses that tag's Dockerfiles.

Both standalone Compose files select `mariadb:13`. Pulling this tag can install
newer minor and patch releases within MariaDB 13; Renovate proposes later major versions
as PRs. Before deploying a new release series, review the
[MariaDB upgrade guide](https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/upgrading)
and back up the database.

The explicit `ignorePaths` in `renovate.json` keeps `tests/requirements-lint.txt`
included despite the recommended preset's default exclusion of test directories.
Native linter updates in `lint-tools.json` include release tags and SHA-256
checksums for every listed platform in the same PR. Download filenames are
derived from the release version; the installer rejects mixed platform versions.

Dependabot version-update PRs are disabled with `open-pull-requests-limit: 0`.
Keep Dependabot alerts and, if desired, security-update PRs enabled in GitHub's
repository security settings. Renovate's vulnerability-alert PRs are disabled
to leave alert-driven security updates to Dependabot.

The Renovate GitHub App must be enabled for this repository, and these
configuration changes must be on the default branch before they take effect.

All PRs and main pushes run lint/regression and Compose checks. Runtime changes
also run fresh image builds, Trivy scans and an isolated [end-to-end stack test](../tests/README.md#end-to-end-stack-test).
Fixable HIGH/CRITICAL findings fail CI. Set `CI required` as a required status
check in GitHub's main branch rules to enforce the checks before merging.

## Build and CI layout

Application build contexts live under `resources/{syslogng,loganalyzer,dbcleanup}`.
Runtime configuration and database initialization live under `data/`.
`docker-compose.dev.yml` is a complete standalone copy of production, adding
only build contexts and local image names. VS Code can launch that file directly
without an overlay or extra environment parameters. `tests/check_compose.py`
compares the resolved runtime settings of both files in CI to prevent drift.

CI renders the development Compose file for Buildx Bake. Each image is built
once per architecture and reused by E2E and scanning. PRs test amd64; runtime
changes on main additionally test arm64 on a native runner. Per-image and
per-architecture build caches are isolated. Documentation and lint-only changes still
run lint/regressions/Compose validation and the required aggregate check.
See the [test guide](../tests/README.md) for coverage and caching details.

## Releases and scheduled refreshes

Tag pushes, manual rebuilds and the weekly Tuesday 01:00 UTC refresh use one
release path. The schedule rebuilds the latest stable tag; manual runs rebuild
the latest `num_tags` stable releases (1–20). Historical tags still use their
own Dockerfiles, including legacy root-level Dockerfiles when necessary.

Each application image is built and scanned for amd64 and arm64, then publishing
reuses those layers on the same builder. The gate consistently rejects fixable
HIGH/CRITICAL findings. Reports are converted from each scan's JSON rather than
rescanning. QEMU is confined to release arm64 builds. Publishing is serialized.

Full version aliases are always updated for the selected tag. Major, minor and
`latest` aliases are updated only by the newest stable version in the relevant
series, so rebuilding an older release cannot move them backwards. Stable
releases must use `vMAJOR.MINOR.PATCH`; prereleases are not published by this
workflow. Main pushes validate images but do not publish them.

The MariaDB/gosu scan review and approved exceptions are documented
in [image scan review](security-scans.md).

## Repository settings checked on 2026-11-13

| Setting | Observed state |
| --- | --- |
| Renovate version-update PRs | Working; recent Python, Ruff and Supercronic PRs were created. |
| Dependency graph and Dependabot alerts | Enabled. |
| Dependabot security-update PRs | Disabled; no custom rule opens them. |
| Private vulnerability reporting | Disabled. |
| Main branch protection/rulesets | No protection configured; `CI required` is not enforced. |

Repository files cannot enable these GitHub settings. To complete enforcement,
configure `CI required` for main and enable Dependabot security updates if it
should own alert-driven fix PRs. Renovate's vulnerability PRs remain disabled
to avoid two bots proposing the same security fix. Private reporting can be
enabled independently. These account-side settings were inspected without
changing them. Automatic dependency submission is disabled; no extra submission
workflow is needed for the currently recognized manifests.
