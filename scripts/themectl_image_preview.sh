#!/usr/bin/env bash
set -euo pipefail

image_path="${1:-}"
transfer_mode="${THEMECTL_PREVIEW_TRANSFER_MODE:-stream}"
preview_debug="${THEMECTL_PREVIEW_DEBUG:-0}"
preview_debug_log="${HOME}/.config/themectl/.cache/preview-debug.log"

if [[ -z "$image_path" ]]; then
  echo "Select an image to preview"
  exit 0
fi

if [[ ! -f "$image_path" ]]; then
  echo "Image not found: $image_path"
  exit 0
fi

start_ts="$(date +%s%3N 2>/dev/null || echo 0)"

append_debug() {
  [[ "$preview_debug" == "1" ]] || return 0
  mkdir -p "$(dirname "$preview_debug_log")" 2>/dev/null || true
  local now
  now="$(date '+%Y-%m-%dT%H:%M:%S' 2>/dev/null || echo now)"
  printf '%s %s\n' "$now" "$*" >> "$preview_debug_log" 2>/dev/null || true
}

preview_dimensions() {
  local cols="${FZF_PREVIEW_COLUMNS:-80}"
  local lines="${FZF_PREVIEW_LINES:-24}"
  echo "${cols}x${lines}"
}

is_kitty_context() {
  [[ -n "${KITTY_WINDOW_ID:-}" || "${TERM:-}" == "xterm-kitty" ]]
}

render_with_kitty_cmd() {
  local cmd="$1"
  local dim
  dim="$(preview_dimensions)"
  append_debug "renderer=kitty cmd='$cmd' mode=$transfer_mode dims=$dim image='$image_path'"

  # This matches the upstream kitty+fzf preview pattern in non-interactive subprocesses.
  $cmd \
    --stdin=no \
    --clear \
    --transfer-mode="${transfer_mode}" \
    --unicode-placeholder \
    --place="${dim}@0x0" \
    "$image_path" | sed '$d' | sed $'$s/$/\e[m/'
}

show_metadata() {
  local size_bytes=""
  local mime=""
  local dims=""

  if command -v stat >/dev/null 2>&1; then
    size_bytes="$(stat -c '%s' "$image_path" 2>/dev/null || true)"
  fi
  if command -v file >/dev/null 2>&1; then
    mime="$(file -Lb --mime-type "$image_path" 2>/dev/null || true)"
  fi
  if command -v identify >/dev/null 2>&1; then
    dims="$(identify -ping -format '%wx%h' "$image_path" 2>/dev/null || true)"
  fi

  echo "File: $(basename "$image_path")"
  echo "Path: $image_path"
  [[ -n "$mime" ]] && echo "Type: $mime"
  [[ -n "$dims" ]] && echo "Size: $dims"
  [[ -n "$size_bytes" ]] && echo "Bytes: $size_bytes"
  echo
  echo "No inline image previewer found."
  echo "Install 'chafa' for terminal previews or use kitty graphics protocol."
}

if is_kitty_context; then
  if command -v kitten >/dev/null 2>&1; then
    if render_with_kitty_cmd "kitten icat"; then
      append_debug "renderer=kitty/kitten status=ok"
      exit 0
    fi
    append_debug "renderer=kitty/kitten status=fail rc=$?"
  fi

  if command -v kitty >/dev/null 2>&1; then
    if render_with_kitty_cmd "kitty +kitten icat"; then
      append_debug "renderer=kitty/+kitten status=ok"
      exit 0
    fi
    append_debug "renderer=kitty/+kitten status=fail rc=$?"
  fi
fi

if command -v chafa >/dev/null 2>&1; then
  cols="${FZF_PREVIEW_COLUMNS:-80}"
  lines="${FZF_PREVIEW_LINES:-24}"
  if chafa --size "${cols}x${lines}" "$image_path" 2>/dev/null; then
    append_debug "renderer=chafa status=ok"
    exit 0
  fi
  append_debug "renderer=chafa status=fail"
fi

if command -v viu >/dev/null 2>&1; then
  if viu -w "${FZF_PREVIEW_COLUMNS:-80}" "$image_path" 2>/dev/null; then
    append_debug "renderer=viu status=ok"
    exit 0
  fi
  append_debug "renderer=viu status=fail"
fi

show_metadata
append_debug "renderer=metadata status=ok"

if [[ "$start_ts" != "0" ]]; then
  end_ts="$(date +%s%3N 2>/dev/null || echo "$start_ts")"
  append_debug "elapsed_ms=$((end_ts - start_ts))"
fi
