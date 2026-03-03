#!/usr/bin/env bash
set -euo pipefail

palette="${1:-}"

if [[ -z "$palette" || ! -f "$palette" ]]; then
  echo "Select a theme to preview"
  exit 0
fi

id="$(jq -r '.id // "unknown"' "$palette" 2>/dev/null || echo unknown)"
variant="$(jq -r '.variant // "unknown"' "$palette" 2>/dev/null || echo unknown)"
family="$(jq -r '.family // "unknown"' "$palette" 2>/dev/null || echo unknown)"
origin="$(jq -r '.origin // empty' "$palette" 2>/dev/null || true)"
if [[ -z "$origin" ]]; then
  source_type="$(jq -r '.source.type // empty' "$palette" 2>/dev/null || true)"
  if [[ "$family" == "generated" || "$source_type" == "image" ]]; then
    origin="generated"
  else
    origin="builtin"
  fi
fi

echo "Theme:   $id"
echo "Variant: $variant"
echo "Family:  $family"
echo "Origin:  $origin"

img="$(jq -r '.source.image_path // empty' "$palette" 2>/dev/null || true)"
backend="$(jq -r '.source.backend // empty' "$palette" 2>/dev/null || true)"
if [[ -n "$img" ]]; then
  echo "Image:   $img"
fi
if [[ -n "$backend" ]]; then
  echo "Backend: $backend"
fi

echo

color_preview_supported() {
  [[ -z "${NO_COLOR:-}" ]] || return 1
  [[ "${TERM:-}" != "dumb" ]] || return 1

  # fzf preview is usually a non-tty pipe; allow color there explicitly.
  if [[ -n "${FZF_PREVIEW_COLUMNS:-}" || -n "${FZF_PREVIEW_LINES:-}" ]]; then
    return 0
  fi

  if [[ -n "${COLORTERM:-}" || "${TERM:-}" == *256color* || "${TERM:-}" == *truecolor* ]]; then
    return 0
  fi

  return 1
}

show_key() {
  local key="$1"
  local block="${2:-6}"
  local hex
  hex="$(jq -r --arg k "$key" '.colors[$k] // empty' "$palette")"
  [[ -n "$hex" && "$hex" =~ ^#[0-9A-Fa-f]{6}$ ]] || return 0
  local r g b
  r=$((16#${hex:1:2}))
  g=$((16#${hex:3:2}))
  b=$((16#${hex:5:2}))
  printf '\033[48;2;%s;%s;%sm%*s\033[0m %-12s %s\n' "$r" "$g" "$b" "$block" "" "$key" "$hex"
}

if color_preview_supported; then
  for key in base mantle crust surface0 surface1 surface2 overlay0 overlay1 overlay2 text mauve green blue peach red yellow teal lavender; do
    show_key "$key" 8
  done
else
  echo "(color preview unavailable in this terminal)"
  jq -r '.colors | to_entries[] | "\(.key)=\(.value)"' "$palette" 2>/dev/null | head -n 14 || true
fi
