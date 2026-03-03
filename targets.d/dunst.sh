#!/usr/bin/env bash

register_target "dunst" "target_apply_dunst" "target_reload_dunst" "target_validate_dunst"

target_apply_dunst() {
  local palette="$1"
  local dir="$HOME/.config/dunst"
  local base="$dir/dunstrc.base"
  local current="$dir/current-theme.conf"
  local merged="$dir/dunstrc"

  [[ -f "$base" ]] || {
    themectl_err "Missing dunst base file: $base"
    return 1
  }

  themectl_render_template "$THEMECTL_ROOT/templates/dunst/current-theme.conf.tmpl" "$palette" "$current"
  themectl_concat_files "$merged" "$base" "$current"
}

target_reload_dunst() {
  if ! command -v dunstctl >/dev/null 2>&1; then
    themectl_warn "dunstctl not found; skipped dunst reload"
    return 0
  fi
  dunstctl reload >/dev/null 2>&1 || {
    themectl_warn "dunst reload failed"
    return 0
  }
}

target_validate_dunst() {
  [[ -f "$HOME/.config/dunst/dunstrc.base" ]] || {
    themectl_err "Missing dunst/dunstrc.base"
    return 1
  }
}
