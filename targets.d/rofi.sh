#!/usr/bin/env bash

register_target "rofi" "target_apply_rofi" "target_reload_rofi" "target_validate_rofi"

target_apply_rofi() {
  local palette="$1"
  themectl_render_template "$THEMECTL_ROOT/templates/rofi/current-palette.rasi.tmpl" "$palette" "$HOME/.config/rofi/current-palette.rasi"
}

target_reload_rofi() {
  return 0
}

target_validate_rofi() {
  rg -q '^@import "current-palette.rasi"$' "$HOME/.config/rofi/rofi-minimal.rasi" || {
    themectl_err "rofi/rofi-minimal.rasi must import current-palette.rasi"
    return 1
  }
  rg -q '^@theme "rofi-minimal.rasi"$' "$HOME/.config/rofi/config.rasi" || {
    themectl_err "rofi/config.rasi must point to rofi-minimal.rasi"
    return 1
  }
}
