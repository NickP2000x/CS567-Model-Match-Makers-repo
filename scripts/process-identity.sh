#!/usr/bin/env bash
# Shared PID-reuse check. Do not use Linux ps lstart: it is derived from the
# wall-clock boot time and can shift after WSL clock synchronization.
mm_process_identity() {
  local pid="$1" stat rest boot stamp
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  if [ "$(uname -s)" = Linux ]; then
    IFS= read -r stat < "/proc/$pid/stat" || return 1
    rest="${stat##*) }"
    local -a fields
    IFS=' ' read -r -a fields <<< "$rest"
    [ "${#fields[@]}" -ge 20 ] || return 1
    IFS= read -r boot < /proc/sys/kernel/random/boot_id || return 1
    # Field 22 is the start tick; the remaining fields start at field 3 (state).
    printf 'linux:%s:%s\n' "$boot" "${fields[19]}"
  else
    stamp="$(LC_ALL=C TZ=UTC ps -p "$pid" -o lstart= 2>/dev/null)" || return 1
    [ -n "$stamp" ] || return 1
    printf 'ps-utc:%s\n' "$stamp"
  fi
}
