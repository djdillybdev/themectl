#!/usr/bin/env bash

register_target "kitty" "target_apply_kitty" "target_reload_kitty" "target_validate_kitty"

target_apply_kitty() {
  local palette="$1"
  themectl_render_template "$THEMECTL_ROOT/templates/kitty/current-theme.conf.tmpl" "$palette" "$HOME/.config/kitty/current-theme.conf"
  themectl_render_template "$THEMECTL_ROOT/templates/kitty/current-colors.conf.tmpl" "$palette" "$HOME/.config/kitty/current-colors.conf"
}

target_reload_kitty() {
  if ! command -v kitty >/dev/null 2>&1; then
    themectl_warn "kitty not found; skipped kitty reload"
    return 0
  fi

  local user_name kitty_conf current_colors
  local socket socket_from_conf
  local socket_path
  local -a sockets=()
  local -a reachable_sockets=()
  local live_socket_ok=0
  local set_colors_ok load_config_ok
  local set_colors_err
  user_name="${USER:-$(id -un 2>/dev/null || echo user)}"
  kitty_conf="$HOME/.config/kitty/kitty.conf"
  current_colors="$HOME/.config/kitty/current-colors.conf"

  if [[ -n "${THEMECTL_KITTY_SOCKET:-}" ]]; then
    sockets+=("$THEMECTL_KITTY_SOCKET")
  fi

  if [[ -n "${KITTY_LISTEN_ON:-}" ]]; then
    sockets+=("$KITTY_LISTEN_ON")
  fi

  socket_from_conf="$(rg -n '^[[:space:]]*listen_on[[:space:]]+[^[:space:]#]+' "$kitty_conf" \
    | sed -E 's/^[0-9]+:[[:space:]]*listen_on[[:space:]]+([^[:space:]#]+).*$/\1/' \
    | head -n 1 || true)"

  if [[ -n "$socket_from_conf" ]]; then
    sockets+=("$socket_from_conf")
    socket="${socket_from_conf//\$\{USER\}/$user_name}"
    socket="${socket//\$USER/$user_name}"
    sockets+=("$socket")
  fi

  sockets+=("unix:/tmp/kitty-remote-$user_name")

  # Discover concrete socket files for patterns like /tmp/kitty-remote-$USER*.
  local discovered_paths=""
  local candidate
  for candidate in "${sockets[@]}"; do
    [[ "$candidate" == unix:* ]] || continue
    socket_path="${candidate#unix:}"
    [[ -n "$socket_path" ]] || continue
    while IFS= read -r socket; do
      [[ -n "$socket" ]] || continue
      discovered_paths+="${discovered_paths:+$'\n'}$socket"
    done < <(compgen -G "${socket_path}*" || true)
  done
  while IFS= read -r socket_path; do
    [[ -n "$socket_path" ]] || continue
    sockets+=("unix:$socket_path")
  done <<<"$discovered_paths"

  local seen="" s reachable=""
  for s in "${sockets[@]}"; do
    [[ -n "$s" ]] || continue
    case ",$seen," in
      *,"$s",*) continue ;;
      *) seen="${seen:+$seen,}$s" ;;
    esac

    if kitty @ --to "$s" ls >/dev/null 2>&1; then
      reachable_sockets+=("$s")
      reachable="${reachable:+$reachable,}$s"
    fi
  done

  if [[ "${#reachable_sockets[@]}" -eq 0 ]]; then
    local pids_no_socket
    pids_no_socket="$(pgrep -x kitty 2>/dev/null || true)"
    if [[ -z "$pids_no_socket" ]]; then
      themectl_warn "kitty live color reload skipped: no kitty processes found"
      return 0
    fi
    themectl_err "kitty live color reload failed: no reachable kitty sockets discovered"
    themectl_err "Checked socket candidates: [${seen:-none}]"
    return 1
  fi

  for s in "${reachable_sockets[@]}"; do

    set_colors_ok=0
    load_config_ok=0
    set_colors_err=""

    if set_colors_err="$(kitty @ --to "$s" set-colors --all --configured "$current_colors" 2>&1)"; then
      set_colors_ok=1
    fi

    if kitty @ --to "$s" load-config "$kitty_conf" >/dev/null 2>&1; then
      load_config_ok=1
    fi

    if [[ "$set_colors_ok" -eq 1 ]]; then
      live_socket_ok=1
    fi

    if [[ "$set_colors_ok" -eq 1 || "$load_config_ok" -eq 1 ]]; then
      continue
    fi

    themectl_warn "kitty reload failed on socket '$s' (set-colors and load-config)"
  done

  if [[ "$live_socket_ok" -eq 1 ]]; then
    return 0
  fi

  local pids
  pids="$(pgrep -x kitty 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    themectl_warn "kitty live color reload skipped: no kitty processes found"
    return 0
  fi

  themectl_err "kitty live color reload failed for reachable socket(s) [${reachable:-none}]"
  if [[ -n "$set_colors_err" ]]; then
    themectl_err "kitty set-colors error: $set_colors_err"
  fi
  return 1
}

target_validate_kitty() {
  local kitty_conf include_line last_background_line
  kitty_conf="$HOME/.config/kitty/kitty.conf"

  rg -q '^[[:space:]]*include[[:space:]]+current-theme\.conf[[:space:]]*$' "$kitty_conf" || {
    themectl_err "kitty/kitty.conf must include current-theme.conf"
    return 1
  }

  rg -q '^[[:space:]]*allow_remote_control[[:space:]]+(yes|socket|socket-only)[[:space:]]*$' "$kitty_conf" || {
    themectl_err "kitty/kitty.conf must set allow_remote_control to yes, socket, or socket-only"
    return 1
  }

  include_line="$(rg -n '^[[:space:]]*include[[:space:]]+current-theme\.conf[[:space:]]*$' "$kitty_conf" | head -n 1 | cut -d: -f1)"
  last_background_line="$(rg -n '^[[:space:]]*background[[:space:]]+[^[:space:]#]+([[:space:]]*#.*)?$' "$kitty_conf" | tail -n 1 | cut -d: -f1 || true)"
  if [[ -n "$last_background_line" && "$last_background_line" -gt "$include_line" ]]; then
    themectl_err "kitty/kitty.conf should place include current-theme.conf after static background entries"
    return 1
  fi

  rg -q '^[[:space:]]*listen_on[[:space:]]+[^[:space:]#]+([[:space:]]*#.*)?$' "$kitty_conf" || {
    themectl_err "kitty/kitty.conf must set listen_on (recommended: unix:/tmp/kitty-remote-\$USER)"
    return 1
  }
}
