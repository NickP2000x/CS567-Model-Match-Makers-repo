#!/usr/bin/env bash
set -euo pipefail

# Local development launcher: use the same native/project-local Node selection.
# shellcheck source=scripts/runtime.sh
source "$(dirname "${BASH_SOURCE[0]}")/runtime.sh"
source "$MM_ROOT/scripts/process-identity.sh"

USE_TMUX=false
# --study runs the participant setup: DEV_CONTROLS=false, no reload, and the production
# frontend build (allocated sequences, no development controls). The tmux relaunch passes it on.
STUDY="${MM_STUDY:-false}"
for arg in "$@"; do
  case "$arg" in
    --tmux) USE_TMUX=true ;;
    --study) STUDY=true ;;
    *)
      printf 'Usage: bash scripts/run.sh [--study] [--tmux]\nOptional: MM_BACKEND_PORT=8001 MM_FRONTEND_PORT=5174 bash scripts/run.sh\n' >&2
      exit 1 ;;
  esac
done

PYTHON="$MM_ROOT/backend/.venv/bin/python"
BACKEND_PORT="${MM_BACKEND_PORT:-8000}"
if [ "$STUDY" = true ]; then
  FRONTEND_PORT="${MM_FRONTEND_PORT:-4173}"
  DEV_CONTROLS_VALUE=false
  RELOAD_FLAG=''
  VITE_COMMAND=preview
else
  FRONTEND_PORT="${MM_FRONTEND_PORT:-5173}"
  DEV_CONTROLS_VALUE=true
  RELOAD_FLAG=--reload
  VITE_COMMAND=serve
fi
START_TIMEOUT="${MM_START_TIMEOUT_SECONDS:-180}"
RUN_STATE="$MM_TOOLS/dev-run.state"

process_start() { mm_process_identity "$1" 2>/dev/null || true; }
if [ -s "$RUN_STATE" ]; then
  old_pid=''
  old_start=''
  { IFS= read -r old_pid || true; IFS= read -r old_start || true; } < "$RUN_STATE"
  case "$old_pid" in
    ''|*[!0-9]*) ;;
    *)
      if [ "$old_pid" -gt 1 ] && [ -n "$old_start" ] && [ "$(process_start "$old_pid")" = "$old_start" ]; then
        printf 'This checkout already has a launcher running. Use bash scripts/stop.sh first.\n' >&2
        exit 1
      fi ;;
  esac
fi

if [ ! -x "$PYTHON" ]; then
  printf 'Backend environment is missing. Follow docs/backend/development-setup.md to create backend/.venv and install dependencies.\n' >&2
  exit 1
fi
mm_detect
mm_select_runtime check
if [ ! -f "$MM_FRONTEND/node_modules/vite/bin/vite.js" ]; then
  printf 'Frontend dependencies are missing. Run bash scripts/setup.sh first.\n' >&2
  exit 1
fi

# Validate dependencies and ports before starting either service. Do not import
# the app here: the backend alone owns loading its configuration.
"$PYTHON" - "$BACKEND_PORT" "$FRONTEND_PORT" "$START_TIMEOUT" <<'PY'
import socket
import sys

try:
    import fastapi
    import uvicorn
except ImportError:
    raise SystemExit("Backend dependencies are missing. Install backend/requirements-dev.txt in backend/.venv.")

try:
    ports = [int(value) for value in sys.argv[1:3]]
    timeout = int(sys.argv[3])
    if any(not 1 <= port <= 65535 for port in ports) or ports[0] == ports[1] or timeout <= 0:
        raise ValueError
except ValueError:
    raise SystemExit("Use different integer ports from 1 to 65535 and a positive integer startup timeout.")

for name, port in zip(("Backend", "Frontend"), ports):
    with socket.socket() as probe:
        # Match Uvicorn/Vite: a closed connection in TIME_WAIT is not a listener.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"{name} port {port} is unavailable. Stop the existing server or set MM_BACKEND_PORT/MM_FRONTEND_PORT.")
PY

if [ "$USE_TMUX" = true ]; then
  if ! command -v tmux >/dev/null 2>&1; then
    printf 'tmux is not installed. Install it with sudo apt install tmux (Ubuntu/WSL) or brew install tmux (macOS), then retry; or omit --tmux.\n' >&2
    exit 1
  fi
  session="model-matchmakers-$$"
  # A private tmux server inherits this invocation's environment and does not
  # interfere with other tmux sessions. No credentials enter the command string.
  printf -v launch 'env MM_TMUX_SOCKET=%q MM_TMUX_SESSION=%q MM_STUDY=%q bash %q' "$session" "$session" "$STUDY" "$MM_ROOT/scripts/run.sh"
  tmux -L "$session" new-session -d -s "$session" -c "$MM_ROOT" "$launch"
  printf 'Started tmux session %s. Backend is on the left; frontend opens on the right after readiness.\n' "$session"
  if [ "$STUDY" = true ]; then printf 'Study mode: the frontend is built in the left pane first.\n'; fi
  printf 'Detach with Ctrl+B, then D. Stop both with bash scripts/stop.sh.\n'
  if [ -t 0 ] && [ -t 1 ] && [ -z "${TMUX:-}" ]; then
    exec tmux -L "$session" attach-session -t "$session"
  fi
  printf 'Attach from a terminal: tmux -L %s attach-session -t %s\n' "$session" "$session"
  exit 0
fi

backend_pid=''
frontend_pid=''
# Separate process groups let cleanup include Uvicorn's reload worker and any
# frontend children without touching servers that were started elsewhere.
set -m
cleanup() {
  trap '' INT TERM HUP
  printf '\nStopping project servers…\n'
  if [ -n "$frontend_pid" ]; then kill -TERM -- "-$frontend_pid" 2>/dev/null || true; fi
  # Let Uvicorn's supervisor stop/reap its workers and resource tracker first.
  if [ -n "$backend_pid" ]; then kill -TERM "$backend_pid" 2>/dev/null || true; fi
  for attempt in 1 2 3 4 5; do
    local running=false
    for pid in "$frontend_pid" "$backend_pid"; do
      if [ -n "$pid" ] && kill -0 -- "-$pid" 2>/dev/null; then running=true; fi
    done
    if [ "$running" = false ]; then break; fi
    sleep 1
  done
  # Escalate only groups created by this launcher, if graceful shutdown stalled.
  for pid in "$frontend_pid" "$backend_pid"; do
    if [ -n "$pid" ]; then kill -TERM -- "-$pid" 2>/dev/null || true; fi
  done
  for attempt in 1 2 3; do
    local running=false
    for pid in "$frontend_pid" "$backend_pid"; do
      if [ -n "$pid" ] && kill -0 -- "-$pid" 2>/dev/null; then running=true; fi
    done
    if [ "$running" = false ]; then break; fi
    sleep 1
  done
  for pid in "$frontend_pid" "$backend_pid"; do
    if [ -n "$pid" ]; then
      kill -KILL -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  recorded_pid=''
  if [ -f "$RUN_STATE" ]; then IFS= read -r recorded_pid < "$RUN_STATE" || true; fi
  if [ "$recorded_pid" = "$$" ]; then : > "$RUN_STATE"; fi
  printf 'Project servers stopped.\n'
  if [ -n "${MM_TMUX_SESSION:-}" ]; then
    tmux -L "$MM_TMUX_SOCKET" kill-session -t "$MM_TMUX_SESSION" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
mkdir -p "$MM_TOOLS"
printf '%s\n%s\n' "$$" "$(process_start "$$")" > "$RUN_STATE"

if [ "$STUDY" = true ]; then
  # The API address is baked into the build, so rebuild for this backend port every launch.
  printf 'Building the participant frontend for http://127.0.0.1:%s…\n' "$BACKEND_PORT"
  (
    cd "$MM_FRONTEND"
    env VITE_API_BASE_URL="http://127.0.0.1:$BACKEND_PORT" "$MM_NODE" "$MM_FRONTEND/node_modules/vite/bin/vite.js" build
  )
fi

printf 'Starting backend using its configured model/router settings. Waiting up to %s seconds…\n' "$START_TIMEOUT"
(
  cd "$MM_ROOT/backend"
  # RELOAD_FLAG is unquoted on purpose: it is either empty or the single word --reload.
  exec env DEV_CONTROLS="$DEV_CONTROLS_VALUE" CORS_ORIGINS="http://127.0.0.1:$FRONTEND_PORT,http://localhost:$FRONTEND_PORT" \
    "$PYTHON" -m uvicorn app.main:app $RELOAD_FLAG --host 127.0.0.1 --port "$BACKEND_PORT"
) &
backend_pid=$!

ready=false
deadline=$((SECONDS + 10#$START_TIMEOUT))
while [ "$SECONDS" -lt "$deadline" ]; do
  if ! mm_process_running "$backend_pid"; then
    printf 'Backend stopped during startup. Check its error output above.\n' >&2
    exit 1
  fi
  # Short probes keep TERM/Ctrl+C responsive even during slow model/router loading.
  if "$PYTHON" - "$BACKEND_PORT" <<'PY'
import json
import sys
import urllib.error
import urllib.request

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{int(sys.argv[1])}/api/health", timeout=1) as response:
        raise SystemExit(0 if json.load(response).get("status") == "ok" else 1)
except (OSError, ValueError, urllib.error.URLError):
    raise SystemExit(1)
PY
  then
    ready=true
    break
  fi
  sleep 0.2
done
if [ "$ready" = false ]; then
  printf 'Backend did not become ready. Check its output; slow router downloads may need a larger MM_START_TIMEOUT_SECONDS.\n' >&2
  exit 1
fi

if [ -n "${MM_TMUX_SESSION:-}" ]; then
  printf -v frontend_command 'exec env VITE_API_BASE_URL=%q %q %q %q --host 127.0.0.1 --port %q --strictPort' \
    "http://127.0.0.1:$BACKEND_PORT" "$MM_NODE" "$MM_FRONTEND/node_modules/vite/bin/vite.js" "$VITE_COMMAND" "$FRONTEND_PORT"
  frontend_pid="$(tmux -L "$MM_TMUX_SOCKET" split-window -h -t "$MM_TMUX_SESSION:0.0" -c "$MM_FRONTEND" -P -F '#{pane_pid}' "$frontend_command")"
  tmux -L "$MM_TMUX_SOCKET" select-layout -t "$MM_TMUX_SESSION:0" even-horizontal >/dev/null
else
  (
    cd "$MM_FRONTEND"
    exec env VITE_API_BASE_URL="http://127.0.0.1:$BACKEND_PORT" \
      "$MM_NODE" "$MM_FRONTEND/node_modules/vite/bin/vite.js" "$VITE_COMMAND" --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
  ) &
  frontend_pid=$!
fi

if [ "$STUDY" = true ]; then
  mode_note='Study mode: participant sessions with allocated sequences, no development controls.'
else
  mode_note='Development sessions enabled (always sequence 1; not for participants, use --study).'
fi
printf '\nOpen http://localhost:%s\nAPI docs: http://127.0.0.1:%s/api/docs\n%s Both servers log here; press Ctrl+C to stop both.\nOr run bash scripts/stop.sh from another terminal.\n' "$FRONTEND_PORT" "$BACKEND_PORT" "$mode_note"
while mm_process_running "$backend_pid" && mm_process_running "$frontend_pid"; do
  sleep 1
done
printf 'A server exited; stopping the other server. Check the output above.\n' >&2
exit 1
