#!/usr/bin/env bash
# Shared by setup and the launcher; compatible with macOS Bash 3.2.

MM_ROOT="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MM_FRONTEND="$MM_ROOT/frontend"
MM_VERSION="$(< "$MM_FRONTEND/.nvmrc")"
MM_TOOLS="$MM_ROOT/.tools"

mm_detect() {
  case "$(uname -s)" in
    Darwin) MM_OS=darwin; MM_PLATFORM=macOS; MM_DOC=macos ;;
    Linux)
      MM_OS=linux; MM_PLATFORM='native Linux'; MM_DOC=native-linux
      case "$(uname -r)" in
        *[Mm]icrosoft*|*[Ww][Ss][Ll]*) MM_PLATFORM='WSL (Ubuntu recommended)'; MM_DOC=wsl2-ubuntu ;;
      esac
      ;;
    *) printf 'Unsupported platform. Use WSL2 Ubuntu, Linux, or macOS.\n' >&2; return 1 ;;
  esac
  case "$(uname -m)" in
    x86_64|amd64) MM_ARCH=x64 ;;
    arm64|aarch64) MM_ARCH=arm64 ;;
    *) printf 'Unsupported CPU architecture. Supported: x64 and arm64.\n' >&2; return 1 ;;
  esac
  MM_DIST="node-v$MM_VERSION-$MM_OS-$MM_ARCH"
  printf 'Environment: %s (%s)\nRequired Node: %s\n' "$MM_PLATFORM" "$MM_ARCH" "$MM_VERSION"
}

mm_guidance() {
  printf 'See %s/docs/frontend/development-setup.md#%s\n' "$MM_ROOT" "$MM_DOC" >&2
}

mm_use_node() {
  local candidate="$1"
  local cli="$(dirname "$candidate")/../lib/node_modules/npm/bin/npm-cli.js"
  [ -x "$candidate" ] && [ -f "$cli" ] || return 1
  [ "$("$candidate" --version 2>/dev/null)" = "v$MM_VERSION" ] || return 1
  [ "$("$candidate" -p 'process.platform' 2>/dev/null)" = "$MM_OS" ] || return 1
  MM_NODE="$candidate"
  MM_NPM_CLI="$cli"
  export PATH="$(dirname "$candidate"):$PATH"
}

mm_npm() {
  # Invoke the selected Node's bundled npm, never Windows npm inherited in WSL.
  "$MM_NODE" "$MM_NPM_CLI" "$@"
}

mm_verify_checksum() {
  local file="$1" expected="$2" actual
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$file")" || return 1
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$file")" || return 1
  else
    printf 'Missing checksum tool: install sha256sum or shasum manually.\n' >&2
    return 1
  fi
  actual="${actual%% *}"
  if [ "$actual" != "$expected" ]; then
    printf 'Node archive checksum mismatch; nothing will be extracted. Run setup again to retry.\n' >&2
    return 1
  fi
}

mm_bootstrap() {
  local tool cache archive base expected='' digest name
  for tool in curl tar mktemp; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      printf 'Missing download prerequisite: %s. Install it manually.\n' "$tool" >&2
      mm_guidance
      return 1
    fi
  done
  if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
    printf 'Missing checksum tool: install sha256sum or shasum manually.\n' >&2
    mm_guidance
    return 1
  fi
  if [ -e "$MM_TOOLS/$MM_DIST" ]; then
    printf 'Existing local runtime is incomplete/incompatible: %s\nMove it aside manually before rerunning setup.\n' "$MM_TOOLS/$MM_DIST" >&2
    return 1
  fi
  mkdir -p "$MM_TOOLS/downloads"
  cache="$(mktemp -d "$MM_TOOLS/downloads/bootstrap.XXXXXX")"
  archive="$MM_DIST.tar.gz"
  base="https://nodejs.org/dist/v$MM_VERSION"
  printf 'Preparing project-local Node %s. No system packages or shell profiles will change.\n' "$MM_VERSION"
  if ! curl --fail --location --silent --show-error --retry 2 --connect-timeout 15 "$base/SHASUMS256.txt" --output "$cache/SHASUMS256.txt"; then
    printf 'Could not download Node checksums. Check network access and rerun setup.\n' >&2
    return 1
  fi
  while read -r digest name; do
    if [ "$name" = "$archive" ]; then expected="$digest"; break; fi
  done < "$cache/SHASUMS256.txt"
  if [ "${#expected}" -ne 64 ]; then
    printf 'No valid checksum found for %s.\n' "$archive" >&2
    return 1
  fi
  case "$expected" in
    *[!0-9a-f]*) printf 'Invalid checksum format.\n' >&2; return 1 ;;
  esac
  if ! curl --fail --location --silent --show-error --retry 2 --connect-timeout 15 "$base/$archive" --output "$cache/$archive"; then
    printf 'Could not download Node. Check network access and rerun setup.\n' >&2
    return 1
  fi
  mm_verify_checksum "$cache/$archive" "$expected" || return 1
  tar -xzf "$cache/$archive" -C "$MM_TOOLS" || return 1
  if ! mm_use_node "$MM_TOOLS/$MM_DIST/bin/node"; then
    printf 'Downloaded Node cannot run on this system. Check OS compatibility in the setup docs.\n' >&2
    return 1
  fi
  printf 'Verified and installed local runtime: %s\n' "$MM_TOOLS/$MM_DIST"
}

mm_select_runtime() {
  if mm_use_node "$MM_TOOLS/$MM_DIST/bin/node"; then
    printf 'Using existing project-local Node.\n'
  elif command -v node >/dev/null 2>&1 && mm_use_node "$(command -v node)"; then
    printf 'Using compatible native Node and its bundled npm.\n'
  elif [ "$1" = bootstrap ]; then
    mm_bootstrap || return 1
  else
    printf 'No compatible native Node/npm pair is ready. Run bash scripts/setup.sh to prepare it.\n' >&2
    mm_guidance
    return 1
  fi
  printf 'Node %s\nnpm %s\n' "$("$MM_NODE" --version)" "$(mm_npm --version)"
}
