#!/usr/bin/env bash

register_target "starship" "target_apply_starship" "target_reload_starship" "target_validate_starship"

target_apply_starship() {
  local palette="$1"
  local base="$THEMECTL_ROOT/templates/starship/base.toml"
  local palette_tmpl="$THEMECTL_ROOT/templates/starship/palette.toml.tmpl"
  local out="$HOME/.config/starship.toml"
  local tmp_palette tmp

  [[ -f "$base" ]] || {
    themectl_err "Missing starship base template: $base"
    return 1
  }

  tmp_palette="$(mktemp)"
  tmp="$(mktemp)"

  themectl_render_template "$palette_tmpl" "$palette" "$tmp_palette"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    themectl_info "[dry-run] render starship -> $out"
    rm -f "$tmp_palette" "$tmp"
    return 0
  fi

  cat "$base" > "$tmp"
  printf '\n' >> "$tmp"
  cat "$tmp_palette" >> "$tmp"
  atomic_write "$tmp" "$out"
  rm -f "$tmp_palette"
}

target_reload_starship() {
  return 0
}

target_validate_starship() {
  [[ -f "$THEMECTL_ROOT/templates/starship/base.toml" ]] || {
    themectl_err "Missing theme/templates/starship/base.toml"
    return 1
  }
}
