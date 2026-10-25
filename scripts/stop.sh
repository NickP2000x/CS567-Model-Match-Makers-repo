#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/scripts/process-identity.sh"
STATE="$ROOT/.tools/dev-run.state"
if [ "$#" -ne 0 ]; then printf 'Usage: bash scripts/stop.sh\n' >&2; exit 1; fi
if [ ! -s "$STATE" ]; then
  printf 'No launcher is recorded for this checkout. Separately started servers are not stopped.\n'
  exit 0
fi

pid=''
started=''
{ IFS= read -r pid || true; IFS= read -r started || true; } < "$STATE"
case "$pid" in
  ''|*[!0-9]*) printf 'Invalid launcher record. No processes were stopped.\n' >&2; exit 1 ;;
esac
if [ "$pid" -le 1 ] || [ -z "$started" ]; then
  printf 'Invalid launcher record. No processes were stopped.\n' >&2
  exit 1
fi
process_start() { mm_process_identity "$1" 2>/dev/null || true; }
current="$(process_start "$pid")"
if [ -z "$current" ]; then
  printf 'The recorded launcher has already exited. Separately started servers are not stopped.\n'
  exit 0
fi
case "$started" in
  linux:*|ps-utc:*) ;;
  *) printf 'This launcher has an older wall-clock identity record. Stop it with Ctrl+C in its original terminal/tmux pane, then restart once. No processes were signaled.\n' >&2; exit 1 ;;
esac
if [ "$current" != "$started" ]; then
  printf 'The recorded PID no longer matches the launcher. No processes were stopped.\n' >&2
  exit 1
fi

printf 'Stopping this checkout’s frontend and backend…\n'
kill -TERM "$pid" 2>/dev/null || true
deadline=$((SECONDS + 15))
while [ "$SECONDS" -lt "$deadline" ]; do
  if [ "$(process_start "$pid")" != "$started" ]; then
    printf 'Project launcher stopped.\n'
    exit 0
  fi
  sleep 0.2
done
printf 'The launcher is still shutting down. Check its terminal output. No unrelated processes were stopped.\n' >&2
exit 1
