#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=scripts/runtime.sh
source "$(dirname "${BASH_SOURCE[0]}")/runtime.sh"
COMMAND="${1:-dev}"
case "$COMMAND" in
  dev|build|preview|type-check|test) ;;
  *) printf 'Usage: bash scripts/frontend.sh [dev|build|preview|type-check|test] [arguments]\n' >&2; exit 1 ;;
esac
if [ "$#" -gt 0 ]; then shift; fi

mm_detect
mm_select_runtime check
cd "$MM_FRONTEND"
if [ ! -d node_modules ]; then
  printf 'Frontend dependencies are missing. Run bash scripts/setup.sh first.\n' >&2
  exit 1
fi
exec "$MM_NODE" "$MM_NPM_CLI" run "$COMMAND" -- "$@"
