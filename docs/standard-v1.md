# Repository Standard v1 profile

This repository uses the multi-image/Compose profile. The three production build
contexts are `resources/syslogng`, `resources/loganalyzer` and `resources/dbcleanup`,
each with its own Dockerfile and restrictive `.dockerignore`. Runtime examples stay
under `data/`; secrets, local enabled configurations and runtime logs remain ignored.
The supported image platforms are Linux amd64 and arm64.

## Validation and release policy

Local and CI entry points are `tests/linter-check.sh`, `tests/test-check.sh`,
`tests/e2e-check.sh` and `tools/secret-check.sh`. Tool versions and checksums are
recorded in `lint-tools.json` and `tests/requirements-lint.txt`. Code comments,
docstrings and versioned documentation use English; localized test data is intentional.

Changed image inputs are planned individually. The E2E dependency closure includes
all three applications because they share a database schema; current source builds
are required rather than substituting possibly older published images. This is a
project-specific dependency decision, not an exception to testing changed inputs.
Pure documentation changes skip application builds and offline behavior tests.

The release planner requires successful exact-commit default-branch push CI. It
builds changed images and reuses immutable digests for unchanged images. Every
published architecture is smoke-tested and freshly scanned. The HIGH/CRITICAL
fixable gate and approved, expiring exceptions are separate from full reports.
Publication checks config IDs and manifest digests, with no build after the scan.
Scheduled/manual rebuilds refresh OS packages independently of base digest changes.
A historical source layout is supported; a historical tag without qualifying CI
is blocked until an explicitly reviewed validation path is agreed.

## GitHub settings and deliberate deferrals

Branch protection, PR requirements, mandatory GitHub status checks and force-push/
delete restrictions are deferred across all repositories by owner decision on
2026-11-14. They are not enabled by this implementation or required for v1 acceptance.
The `CI required` aggregate and exact-commit release gate remain active workflow logic.

Renovate owns regular version updates. Dependabot owns alert-driven security PRs;
its version PR limit is zero and Renovate vulnerability PRs are disabled. Verify
Dependabot alerts/security updates and Renovate App access in repository settings;
configuration files alone cannot enable account-side features. No GitHub settings
are changed by this local implementation.

Funding is `.github/FUNDING.yml` with `buy_me_a_coffee: alaub81`. Check its visible
GitHub Sponsor entry after the change reaches the default branch.

## Runtime privileges and attestations

The collector/cleanup need their packaged process and file ownership behavior,
and the Apache image uses its standard privileged entry point before dropping
worker privileges. Non-root/read-only conversions require separate service-specific
validation; they are not asserted here. Scratch files and logs are bounded as
explained in the operations guide. Review this choice with the maintainer on
2027-02-01 alongside the existing scoped scan exceptions.

Loaded Docker images do not retain standalone BuildKit attestation manifests.
Registry SBOM/provenance attachment is a separately reviewed extension. Full scan
inventories and digest/config publication receipts are retained for seven days.
Repository owner `alaub81` owns these documented decisions; review by 2027-02-01.

Known lint-only manifests, tool installers and bot configuration run static/offline
checks without application builds. Workflow, runtime-test and unknown input changes
remain conservative full-stack changes.


## README content contract

The root README preserves the published-image quick start, local Compose build
commands and the purpose/variable mapping of generated database passwords.
Shelly parsing is a key feature even though activation is optional: its setup,
host modes, extra logs, DNS, configuration reload and storage choices remain
directly usable from the README. Detailed guides supplement those entry points.
Before restructuring the README, compare its important features and commands
with the previous version; shortening is not a reason to remove user workflows.

## Automatic release notes

Stable tag pushes announce a release after successful publication of all three
images. English notes include direct commits, reachable stable-tag comparisons,
versioned documentation and actual multi-platform image digests from publication
receipts. Existing release text/drafts are preserved, older versions are not
marked latest, and scheduled/manual refreshes do not overwrite initial notes.
The notes job alone has content write permission; API errors fail the workflow.
Local generation and retry behavior are documented in the development guide.
