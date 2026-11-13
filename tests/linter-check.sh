#!/usr/bin/env bash
# Prepare isolated tools and check source files without changing them.
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"

if [[ $# -ne 0 ]]; then
  echo "Usage: ./tests/linter-check.sh" >&2
  exit 2
fi

if [[ ! -x "$PROJECT_DIR/.lint-venv/bin/python" ]]; then
  echo "Creating isolated lint environment..."
  PYTHON_RUNNER=""
  for candidate in python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
      PYTHON_RUNNER="$candidate"
      break
    fi
  done
  if [[ -z "$PYTHON_RUNNER" ]]; then
    echo "Python 3.10+ is required." >&2
    exit 1
  fi
  "$PYTHON_RUNNER" -m venv "$PROJECT_DIR/.lint-venv"
fi

export PATH="$PROJECT_DIR/.lint-venv/bin:$PROJECT_DIR/.lint-tools/bin:$PATH"
LINT_PYTHON="$PROJECT_DIR/.lint-venv/bin/python"
if ! "$LINT_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "The existing .lint-venv requires Python 3.10+; recreate it with a supported Python version." >&2
  exit 1
fi
if ! "$LINT_PYTHON" -c 'import sys; sys.path.insert(0, "tests"); from lint import check_linter_versions; sys.exit(not check_linter_versions())'; then
  "$LINT_PYTHON" -m pip install --disable-pip-version-check --requirement tests/requirements-lint.txt
fi
"$LINT_PYTHON" tests/install_lint_tools.py
exec "$LINT_PYTHON" tests/lint.py
