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

Manual capture/replay tools and private log fixtures from local diagnosis are
kept under `.local/`; they are not distributed with the stack.
