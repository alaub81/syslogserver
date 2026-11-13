# Repository checks

## Lint checks

Run the same checks as the CI lint job:

```bash
./tests/linter-check.sh
```

Requires Git, Bash and Python 3.10+. CI selects Python in
`.github/workflows/ci.yml`. The command creates `.lint-venv/` for pinned Python
packages and `.lint-tools/` for pinned native linters. Matching installations
are reused; first setup and version updates require internet access. On macOS,
install the Hadolint version in `lint-tools.json` on PATH first (for example
with Homebrew); upstream provides no macOS release binary.

Checks include tracked and non-ignored untracked files that still exist:

- UTF-8, LF, final newlines, trailing whitespace and merge markers.
- JSON syntax and duplicate keys (VS Code's commented settings are excluded).
- Local Markdown links and documented environment variables.
- ShellCheck for shell scripts and Hadolint for Dockerfiles.
- Strict Yamllint and Actionlint for workflows.
- Ruff correctness checks for Python, targeting the minimum Python 3.10.

All checks run even after an earlier failure; the final summary reports
PASS/FAIL, with a nonzero exit status on failure. No source files are fixed.
The VS Code task `lint:all` runs this command. `.env`, `.local/`, active private
configuration copies and tool environments are excluded through Git ignore rules.

Native downloads are checked against SHA-256 hashes. Renovate tracks each
platform's release tag and checksum together. Keep `version` and `sha256`
adjacent in the manifest and preserve its formatting for the recursive matcher.
The installer rejects mixed platform versions. Hadolint updates on macOS also
require the matching version on PATH.

CI validates both standalone Compose files and compares their resolved runtime
settings with `python3 tests/check_compose.py`. Only local image names and build
settings may differ. PHP, syslog-ng and
cron syntax are checked with the real container tools during E2E.

## Automated regression tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

These tests require no running stack or network:

- Cleanup: bounded batches, fixed cutoff, empty results, SQL failures and invalid settings.
- Native installer: version consistency, release URLs, extraction, checksums and executable versions.
- Release tags: numeric SemVer ordering, invalid tags/counts and safe major/minor/latest aliases.
- Scan policy: six boundary checks using the real Trivy converter, run in the
  stack job after Trivy installation (skipped when Trivy is unavailable locally).

## End-to-end stack test

With Docker running:

```bash
./tests/e2e-check.sh
```

The test builds this checkout with fresh base images and no build-cache reuse.
It uses a unique Compose project, an empty database volume and random
**loopback-only host ports**. Test configuration copies the shipped templates;
your local `.env`, enabled Shelly/debug files and running database are excluded.
The database image is pulled explicitly before startup.

The test sends through the published host ports and verifies:

1. Default standard syslog with Shelly disabled: RFC3164 UDP and two byte-counted
   RFC5424 TCP frames on one connection.
2. Shelly enabled in both `sender` and `device` host modes: NUL-delimited records,
   empty delimiters, trailing NUL, all five levels, script channels 101/102,
   unknown channels, older headers and incomplete fragments.
3. Exact SQL messages and metadata, PIDs, priorities, reception time, Unicode,
   embedded newlines and trailing spaces, without duplicate rows.
4. Standard syslog still working alongside Shelly, normalized/raw diagnostics
   and both message types displayed through published HTTP in LogAnalyzer.
5. Multiple real cleanup batches removing five expired rows while preserving
   all 30 fresh test rows.

Failures print the test stack's logs. Exit and signal handlers remove only its
containers, network and database volume. No live device traffic is needed.

CI builds once per architecture and uses those same images for E2E and scanning:

```bash
./tests/e2e-check.sh --skip-build
```

This option requires `syslogng-mysql:latest`, `loganalyzer:dev` and
`dbcleanup:latest` to have been built from the checkout under test; it never
pulls published application images as a substitute.

## CI and vulnerability scans

All PRs and main pushes run lint, regressions and Compose validation. Runtime
changes additionally run the full stack checks on amd64; main pushes also run
the same builds, E2E and scans on a native arm64 runner. Native runners avoid
QEMU overhead in CI. Documentation and lint-only changes skip image work; `CI required`
still verifies the applicable results. A failed change-detection command fails
CI. New commits cancel superseded CI runs.

Each application image is built once per tested architecture. Per-image caches
avoid collisions. Only the `os-packages` stage is forcibly refreshed for package
fixes. Trivy scans each of these images and the actual MariaDB image once,
then converts JSON into SARIF and a HIGH/CRITICAL gate. Raw JSON and SARIF are
retained for seven days even when the gate fails. Code-scanning uploads run
only on main, with separate image/architecture categories. The CVE database is
cached daily; native lint tools and pip downloads are cached independently.

For a local scan of exported images, `tests/scan-images.sh` also accepts
`NAME=archive:/absolute/path/image.tar`. This lets a containerized scanner work
without access to the Docker daemon socket.

See [image scan review](../docs/security-scans.md) for the current MariaDB/gosu
findings and their analysis. Set `CI required` as a required status check in
GitHub's main branch protection/ruleset to enforce the results before merging.
Automerge remains disabled.

Private capture/replay fixtures belong under `.local/` and are not distributed.
