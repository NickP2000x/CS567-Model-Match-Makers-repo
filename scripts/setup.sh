#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=scripts/runtime.sh
source "$(dirname "${BASH_SOURCE[0]}")/runtime.sh"
CHECK_ONLY=false

case "${1:-}" in
  '') ;;
  --check) CHECK_ONLY=true ;;
  *) printf 'Usage: bash scripts/setup.sh [--check]\n' >&2; exit 1 ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'Usage: bash scripts/setup.sh [--check]\n' >&2
  exit 1
fi

mm_detect
if ! command -v git >/dev/null 2>&1; then
  printf 'Missing prerequisite: git. Install it manually.\n' >&2
  mm_guidance
  exit 1
fi
git --version

if [ "$CHECK_ONLY" = true ]; then
  mm_select_runtime check
  printf 'Prerequisite checks passed. No dependencies were installed.\n'
  exit 0
fi

mm_select_runtime bootstrap
cd "$MM_FRONTEND"
mm_npm ci
mm_npm run build
printf '\nSetup complete. Run bash scripts/frontend.sh dev from %s.\n' "$MM_ROOT"
printf 'Open the displayed localhost URL in your browser (Windows browser for WSL).\n'
