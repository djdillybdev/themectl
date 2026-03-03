#!/usr/bin/env bash

register_target "polybar" "target_apply_polybar" "target_reload_polybar" "target_validate_polybar"

target_apply_polybar() {
  local palette="$1"
  themectl_render_template "$THEMECTL_ROOT/templates/polybar/current-theme.ini.tmpl" "$palette" "$HOME/.config/polybar/current-theme.ini"
}

polybar_count_running() {
  pgrep -x polybar 2>/dev/null | wc -l | tr -d ' '
}

polybar_wait_for_running() {
  local wait_seconds="${1:-5}"
  local elapsed=0
  while [[ "$elapsed" -lt "$wait_seconds" ]]; do
    if [[ "$(polybar_count_running)" -gt 0 ]]; then
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  return 1
}

polybar_run_launch_script() {
  local launch_script="$HOME/.config/polybar/launch.sh"
  if [[ ! -x "$launch_script" ]]; then
    themectl_warn "polybar launch script missing or not executable: $launch_script"
    return 1
  fi
  "$launch_script" >/dev/null 2>&1 || {
    themectl_warn "polybar reload via launch.sh failed"
    return 1
  }
  return 0
}

polybar_write_reload_meta() {
  local pre_running_count="$1" post_running_count="$2" reload_method="$3" recovery_used="$4"
  local meta_file="${THEMECTL_RELOAD_META_FILE:-}"
  [[ -n "$meta_file" ]] || return 0
  jq -cn \
    --argjson pre_running_count "$pre_running_count" \
    --argjson post_running_count "$post_running_count" \
    --arg reload_method "$reload_method" \
    --argjson recovery_used "$recovery_used" \
    '{
      pre_running_count: $pre_running_count,
      post_running_count: $post_running_count,
      reload_method: $reload_method,
      recovery_used: $recovery_used
    }' >"$meta_file"
}

target_reload_polybar() {
  local pre_count post_count reload_method recovery_used
  pre_count="$(polybar_count_running)"
  post_count="$pre_count"
  reload_method="none"
  recovery_used=false

  if [[ "$pre_count" -gt 0 ]] && command -v polybar-msg >/dev/null 2>&1; then
    if polybar-msg cmd restart >/dev/null 2>&1; then
      reload_method="ipc_restart"
      if ! polybar_wait_for_running 5; then
        recovery_used=true
        if polybar_run_launch_script && polybar_wait_for_running 5; then
          reload_method="launch_fallback"
        fi
      fi
    else
      themectl_warn "polybar IPC restart failed; trying launch fallback"
      recovery_used=true
      if polybar_run_launch_script && polybar_wait_for_running 5; then
        reload_method="launch_fallback"
      fi
    fi
  else
    if [[ "$pre_count" -gt 0 ]]; then
      themectl_warn "polybar-msg not found; using launch fallback"
    fi
    if polybar_run_launch_script && polybar_wait_for_running 5; then
      reload_method="launch_fallback"
    fi
  fi

  post_count="$(polybar_count_running)"
  polybar_write_reload_meta "$pre_count" "$post_count" "$reload_method" "$recovery_used"
  if [[ "$post_count" -eq 0 ]]; then
    themectl_warn "polybar reload left no running bars"
    return 1
  fi

  return 0
}

target_validate_polybar() {
  rg -q 'include-file = ~/.config/polybar/current-theme.ini' "$HOME/.config/polybar/config.ini" || {
    themectl_err "polybar/config.ini must include current-theme.ini"
    return 1
  }
}
