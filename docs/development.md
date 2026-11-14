# Development and dependency updates

The Dockerfiles, development Compose file, runtime resources, CI configuration
and automated regression tests remain in the repository. Run the cleanup
regressions without a live database:

```bash
./tests/test-check.sh
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
New update branches are scheduled for Mondays before 06:00 Europe/Berlin,
with a three-day minimum release age and at most three concurrent PRs.
Non-major updates are grouped separately for Actions and Python lint
dependencies; Docker images and major upgrades are reviewed per dependency.
Supercronic minor/patch updates merge automatically after CI passes; all other
updates remain manually reviewed. The Dependency Dashboard tracks pending updates.

The three application Dockerfiles refresh package lists and upgrade installed
Debian packages before installing their dependencies. Their official base images
already enable the matching Debian security repository. CI and release builds
re-run the `os-packages` stage with `no-cache-filters`; local fresh builds can use
`docker compose -f compose.dev.yml --env-file .env build --pull --no-cache`.
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
Fixable HIGH/CRITICAL findings fail CI. Branch protection and mandatory GitHub
status checks are deliberately deferred; the aggregate status remains available.

## Build and CI layout

Application build contexts live under `resources/{syslogng,loganalyzer,dbcleanup}`.
Runtime configuration and database initialization live under `data/`.
`compose.dev.yml` is a complete standalone copy of production, adding
only build contexts and local image names. VS Code can launch that file directly
without an overlay or extra environment parameters. `tests/check_compose.py`
compares the resolved runtime settings of both files in CI to prevent drift.

CI uses the tested `tools/change_plan.py` dependency graph. Pure documentation
changes run static checks without application builds or behavior tests. Unknown
diffs, workflows, tooling, Compose and test inputs take the conservative full path.
A changed application is recorded individually, but the shared database/schema
requires current versions of all three images for E2E. These images are built
once per architecture and reused by E2E and scanning. Both amd64 and arm64 use
native CI runners, including pull requests; matrices do not cancel other evidence
on the first failure. Per-image/per-architecture caches remain isolated.

## Releases and scheduled refreshes

Every selected release commit must have a completed, successful push CI run on
the default branch. A missing, failed, running or unverifiable run blocks planning
before any image build. The latest attempt counts; no runner polls waiting for CI.
Push the commit, wait for CI, then push a stable tag. The same exact-commit check
applies to manual and scheduled refreshes; historical tags without qualifying CI
are deliberately blocked rather than silently bypassing validation.

For a tag release, the planner compares image inputs with the preceding stable
tag. Unchanged images are loaded from an immutable registry digest; a missing
source image falls back to a build. Shared/unknown inputs force builds. Tuesday
01:00 UTC refreshes and manual `num_tags` runs (1–20) rebuild selected images,
including their OS package stages, even if the base digest has not changed.
Historical source layouts remain supported when their commit has qualifying CI.

Each architecture is loaded once, smoke-tested and scanned by its immutable local
image ID. Full JSON/SARIF reports and a scan receipt are retained for seven days,
including gate failures. Only a complete matching receipt permits publication.
The publisher pushes those exact image configs, verifies registry config digests,
checks the two-platform candidate index, then promotes its digest to release
aliases. There is no build after scanning. Candidate tags use the workflow run ID;
stable aliases are never assigned before both architecture gates pass for that image.
Each image job publishes independently; a failure can leave a partial release of
other successful images. The final notes job waits for all image jobs to succeed
before announcing a release.

Loaded Docker images do not carry separate BuildKit attestation manifests.
Full vulnerability inventories and publication receipts are kept as artifacts;
registry SBOM/provenance attachment is a separately reviewed extension, not a
claim made by this workflow. Monthly/on-demand security runs scan current published
images on both platforms and the complete committed history for secrets. CI scans
only the changed commit range with Gitleaks and falls back to full history if the
base is unknown. Logs are redacted; test credentials are disposable fixtures.

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

Repository files cannot enable these GitHub settings. To complete security-update coverage,
enable Dependabot security updates if it should own alert-driven fix PRs.
Branch protection remains deferred for all repositories until explicitly approved. Renovate's vulnerability PRs remain disabled
to avoid two bots proposing the same security fix. Private reporting can be
enabled independently. These account-side settings were inspected without
changing them. Automatic dependency submission is disabled; no extra submission
workflow is needed for the currently recognized manifests.

Known lint-only manifests, tool installers and bot configuration run static/offline
checks without application builds. Workflow, runtime-test and unknown input changes
remain conservative full-stack changes.

Manual dependency updates rebase on conflicts. The Supercronic automerge allowlist
rebases when behind the base branch so it obtains fresh CI without requiring branch
protection. GitHub settings remain deferred as described in the profile.

## Automatic release notes

A stable tag push creates a public GitHub release only after exact-commit CI,
all image smoke tests/security gates and publication of all three images succeed.
Reused images are included. The notes job downloads receipts from the current run
and verifies their tag, commit, image plan, platforms and published index digests.
It does not build images again. Use **Re-run failed jobs** after fixing a transient
notes/API error to keep successful image jobs.

English notes include non-merge commits (including direct commits), commit links,
the preceding reachable lower stable version, a comparison/source link and the
three versioned image references with their actual publication digests. Review
breaking changes and migration instructions before tagging; commit subjects are
an automatic changelog, not an inferred migration guide. Commit text is escaped.
Only the newest stable version is marked latest. Existing releases, including
drafts and edited notes, are preserved. API failures stop the job. Scheduled and
manual same-tag image refreshes do not create releases or change their notes;
those notes record the initial publication, while refresh receipts record new digests.
Only the notes job receives repository content write permission.

For a local preview, download the three `trivy-vX.Y.Z-*` artifacts from the same
successful release run into separate subdirectories. Save that run's release
matrix JSON (`{"include": [...]}`) in `/tmp/release-matrix.json`, fetch its tag and run:

```bash
python3 tools/create_release_notes.py --tag vX.Y.Z \
  --receipts /tmp/publications --matrix "$(cat /tmp/release-matrix.json)" \
  --output /tmp/release-notes.md
```

Preview mode writes a local file only. `--publish` additionally requires the GitHub
CLI and an authenticated token; it verifies the existing remote tag and uses a
notes file. No release tag is created by this tool.
