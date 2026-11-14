#!/usr/bin/env bash
# Run the shared offline suite and Compose parity checks without touching live data.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
if (( $# != 0 )); then
  echo "Usage: ./tests/test-check.sh" >&2
  exit 2
fi
export PATH="$PROJECT_DIR/.lint-venv/bin:$PROJECT_DIR/.lint-tools/bin:$PATH"
export PYTHONPATH="$PROJECT_DIR/tools:$PROJECT_DIR/tests${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
python3 tests/install_lint_tools.py trivy
for tool in python3 docker jq trivy; do
  command -v "$tool" >/dev/null || { echo "Missing test dependency: $tool" >&2; exit 1; }
done
docker compose version >/dev/null
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/check_compose.py
