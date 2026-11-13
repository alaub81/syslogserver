# Local checks

## Lint checks

Run the same checks as the CI lint job:

```bash
./tests/linter-check.sh
```

The command works from any directory and requires Git, Bash and Python 3.10+
(CI uses Python 3.14). It creates `.lint-venv/` for pinned Python packages and
`.lint-tools/` for pinned native linters. Matching installations are reused;
initial setup and version updates require internet access. On macOS, install
Hadolint at the version specified in `lint-tools.json` on PATH first, for example
with Homebrew; upstream provides no macOS release binary. Native downloads are
verified against the SHA-256 checksums in that manifest.

Renovate tracks each platform's release tag and SHA-256 together using GitHub
release attachments. The installer derives download names from the version
and rejects mixed versions across a tool's platforms. When adding an asset,
keep its `version` and `sha256` fields adjacent and retain the manifest's JSON
formatting so the recursive Renovate matcher can read each tool's block.
Hadolint updates on macOS also require the matching version on PATH.

Checks cover tracked and non-ignored untracked files that still exist:

- Text hygiene: UTF-8, LF, final newline, trailing whitespace and merge markers.
- JSON syntax and duplicate keys (VS Code's commented settings are excluded).
- ShellCheck for shell scripts and Hadolint for all Dockerfiles.
- Strict Yamllint using `.yamllint.yaml` and Actionlint for CI/release workflows.
- Ruff correctness checks for Python using `ruff.toml`.

Every check runs even when an earlier check fails; the final summary reports
PASS/FAIL and the command exits nonzero on any failure. It never fixes source
files or starts containers. Local `.env`, `.local/`, enabled private configuration
copies and tool environments are excluded through Git's ignore rules. Binary
files containing NUL bytes are skipped by the text check.

The VS Code task `lint:all` runs this same command.

Linting does not run image builds, Trivy scans, runtime configuration validation
or end-to-end tests. Those remain separate CI checks.

## Automated regression tests

Run from the repository root:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

The cleanup tests use a simulated MariaDB client and require no running stack.
They cover bounded deletion batches, a fixed retention cutoff, empty results,
SQL failures and invalid settings.

Native installer tests check platform version consistency, release URL and
filename construction, archive extraction and rejection of incorrect checksums
or executable versions without downloading or executing release binaries.

## End-to-end stack test

With Docker running, execute:

```bash
./tests/e2e-check.sh
```

The test builds this checkout using `docker-compose.dev.yml` in a unique Compose
project with fresh database storage and random loopback-only host ports. It
uses the shipped standard syslog route, excluding local enabled vendor/debug
configuration files. It verifies UDP and TCP ingestion into MariaDB, both
messages appearing in LogAnalyzer and retention deleting an expired row while
preserving the fresh messages. Failed runs print the test stack's logs.
The test removes its own containers, network and database volume on exit.

CI runs lint, regressions, image scans and this E2E test for PRs and main pushes.
Trivy scans the three freshly built application images and the MariaDB image
selected by Compose. Fixable HIGH/CRITICAL vulnerabilities fail the scan check;
MEDIUM findings remain in the SARIF report, retained as a workflow artifact for
seven days even when the gate fails. Code-scanning uploads run only on main pushes.
Main pushes additionally build amd64 and arm64 images without publishing them.
Image scans use amd64 on GitHub's runner; E2E uses the host's native architecture.

Configure `CI required` as a required status check in the repository's main
branch protection or ruleset to enforce these results before merging. This
aggregate check fails if lint, scans or E2E fail or are skipped; multi-arch builds
are additionally required on main pushes. Automerge remains disabled.

Manual capture/replay tools and private log fixtures from local diagnosis are
kept under `.local/`; they are not distributed with the stack.
