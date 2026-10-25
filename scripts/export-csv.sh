#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  printf 'Backend environment is missing. Run bash scripts/setup-all.sh first (Python 3.12 required).\n' >&2
  exit 1
fi

cd "$ROOT/backend"
# argparse uses the last --database value, so an explicit override takes precedence.
# Do not source .env: the exporter only reads the explicitly selected SQLite file.
exec "$PYTHON" -m app.export_csv --database "$ROOT/backend/data/model-matchmakers.sqlite3" "$@"
