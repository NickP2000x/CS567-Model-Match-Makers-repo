#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  printf 'Backend environment is missing. Run bash scripts/setup-all.sh first (Python 3.12 required).\n' >&2
  exit 1
fi
cd "$ROOT/backend"
if ! "$PYTHON" -c 'import pydantic_settings' >/dev/null 2>&1; then
  printf 'Backend dependencies are missing or unusable. Run bash scripts/setup-all.sh; add --routellm for real routing.\n' >&2
  exit 1
fi

# The Python CLI requires --dry-run or --real; never choose a mode here.
exec "$PYTHON" -m app.calibrate "$@"
