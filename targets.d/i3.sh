#!/usr/bin/env bash

register_target "i3" "target_apply_i3" "target_reload_i3" "target_validate_i3"

target_apply_i3() {
  local palette="$1"
  local template="$THEMECTL_ROOT/templates/i3/current-theme.conf.tmpl"
  local out="$HOME/.config/i3/current-theme.conf"
  local focused_hex unfocused_hex focused_inactive_hex

  focused_hex="$(resolve_role_hex_for_palette "$palette" "i3.focused_border")"
  unfocused_hex="$(resolve_role_hex_for_palette "$palette" "i3.unfocused_border")"
  focused_inactive_hex="$(resolve_role_hex_for_palette "$palette" "i3.focused_inactive_border")"

  themectl_render_template "$template" "$palette" "$out"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    themectl_info "[dry-run] i3 role colors focused=$focused_hex focused_inactive=$focused_inactive_hex unfocused=$unfocused_hex"
  fi
}

target_reload_i3() {
  if ! command -v i3-msg >/dev/null 2>&1; then
    themectl_warn "i3-msg not found; skipped i3 reload"
    return 0
  fi
  i3-msg reload >/dev/null 2>&1 || {
    themectl_warn "i3 reload failed (possibly not running i3)"
    return 0
  }
}

target_validate_i3() {
  rg -q '^include current-theme.conf$' "$HOME/.config/i3/config" || {
    themectl_err "i3/config must include current-theme.conf"
    return 1
  }
}
