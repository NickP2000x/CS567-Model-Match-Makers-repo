#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK=false
ROUTELLM=false
for argument in "$@"; do
  case "$argument" in
    --check) CHECK=true ;;
    --routellm) ROUTELLM=true ;;
    --help)
      printf 'Usage: bash scripts/setup-all.sh [--routellm] [--check]\nPrepares frontend and backend. --routellm includes optional router dependencies.\n--check checks an existing setup without installing anything.\n'
      exit 0 ;;
    *) printf 'Unknown option: %s\nUse --help for setup options.\n' "$argument" >&2; exit 1 ;;
  esac
done

BACKEND_PYTHON="$ROOT/backend/.venv/bin/python"
if [ -e "$ROOT/backend/.venv" ] && [ ! -x "$BACKEND_PYTHON" ]; then
  printf 'Existing backend/.venv is incomplete. Follow docs/backend/development-setup.md to repair it manually; setup will not overwrite it.\n' >&2
  exit 1
fi
if [ -x "$BACKEND_PYTHON" ]; then
  PYTHON="$BACKEND_PYTHON"
elif [ "$CHECK" = true ]; then
  printf 'Backend environment is missing. Run bash scripts/setup-all.sh first.\n' >&2
  exit 1
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
else
  printf 'Python 3.12 is required. Install it using docs/backend/development-setup.md, then rerun setup. No system packages will be installed automatically.\n' >&2
  exit 1
fi
case "$("$PYTHON" --version 2>&1)" in
  "Python 3.12."*) ;;
  *) printf 'Backend requires Python 3.12. Repair the existing environment or install Python 3.12; setup will not overwrite it.\n' >&2; exit 1 ;;
esac

if [ "$CHECK" = true ]; then
  bash "$ROOT/scripts/setup.sh" --check
  if [ ! -f "$ROOT/frontend/node_modules/vite/bin/vite.js" ]; then
    printf 'Frontend dependencies are missing. Run bash scripts/setup-all.sh first.\n' >&2
    exit 1
  fi
else
  # Reuse the existing verified Node bootstrap, dependency install, and build.
  bash "$ROOT/scripts/setup.sh"
  if [ ! -x "$BACKEND_PYTHON" ]; then
    printf '\nCreating backend Python environment…\n'
    "$PYTHON" -I -m venv "$ROOT/backend/.venv"
  fi
  "$BACKEND_PYTHON" -I -m pip install -r "$ROOT/backend/requirements-dev.txt"
  if [ "$ROUTELLM" = true ]; then
    printf '\nInstalling optional RouteLLM dependencies (large download)…\n'
    "$BACKEND_PYTHON" -I -m pip install -r "$ROOT/backend/requirements-routellm.txt"
  fi
fi

# Isolated Python mode ignores inherited PYTHONPATH/user packages (for example ROS).
# Inspect installed packages without importing the app, loading .env, initializing
# SQLite, downloading router checkpoints, or contacting model providers.
"$BACKEND_PYTHON" -I - "$ROUTELLM" <<'PY'
import importlib.util
import sys

required = ["fastapi", "uvicorn", "pydantic_settings", "pytest"]
if sys.argv[1] == "true":
    required += ["routellm", "torch", "transformers"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("Missing backend packages: " + ", ".join(missing) + ". Rerun setup with --routellm if needed.")
PY
"$BACKEND_PYTHON" -I -m pip check

printf '\nFrontend and backend setup checks passed.\n'
if [ "$CHECK" = true ]; then printf 'No dependencies were installed.\n'; fi
printf 'Next: bash scripts/run.sh\n'
if [ "$ROUTELLM" = false ]; then
  printf 'For a RouteLLM router, also run: bash scripts/setup-all.sh --routellm\n'
fi
printf 'Existing configuration and data are preserved. Ollama installation/model downloads and cloud sign-in are separate steps on the machine running Ollama.\n'
