#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
YES=0

usage() {
  cat <<'USAGE'
Usage: install.sh [--dry-run] [--yes]

Options:
  --dry-run   print actions without writing files
  --yes       non-interactive defaults (safe mode)
  -h, --help  show help
USAGE
}

say() { echo "[install] $*"; }
warn() { echo "[install][warn] $*" >&2; }
err() { echo "[install][error] $*" >&2; }

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    say "[dry-run] $*"
    return 0
  fi
  "$@"
}

confirm() {
  local prompt="$1"
  if [[ "$YES" -eq 1 ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N]: " answer || true
  [[ "${answer,,}" == "y" || "${answer,,}" == "yes" ]]
}

check_dep() {
  local cmd="$1" level="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    say "found: $cmd"
  else
    if [[ "$level" == "required" ]]; then
      err "missing required command: $cmd"
      exit 1
    fi
    warn "missing optional command: $cmd"
  fi
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      --yes) YES=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) err "unknown argument: $1"; usage; exit 1 ;;
    esac
  done

  say "checking dependencies"
  check_dep bash required
  check_dep jq required
  check_dep python3 optional
  check_dep fzf optional
  check_dep feh optional

  local src_dir
  src_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local bin_dir="$HOME/.local/bin"
  local app_dir="$HOME/.local/share/themectl"
  local target="$bin_dir/themectl"
  local app_entry="$app_dir/themectl"
  local rollback_file="$HOME/.config/themectl/.cache/install-rollback.txt"

  say "source: $src_dir"
  say "target: $target"

  if ! confirm "Install themectl to $target?"; then
    say "aborted by user"
    exit 0
  fi

  run mkdir -p "$bin_dir"
  run mkdir -p "$app_dir"
  run mkdir -p "$app_dir/scripts" "$app_dir/themectl_py" "$app_dir/templates" "$app_dir/targets.d" "$app_dir/palettes"
  run mkdir -p "$(dirname "$rollback_file")"
  run cp "$src_dir/themectl" "$app_entry"
  run cp -r "$src_dir/scripts/." "$app_dir/scripts"
  run cp -r "$src_dir/themectl_py/." "$app_dir/themectl_py"
  run cp -r "$src_dir/templates/." "$app_dir/templates"
  run cp -r "$src_dir/targets.d/." "$app_dir/targets.d"
  run cp -r "$src_dir/palettes/." "$app_dir/palettes"
  run cp "$src_dir/roles.json" "$app_dir/roles.json"
  run cp "$src_dir/config.json" "$app_dir/config.json"
  run cp "$src_dir/state.json" "$app_dir/state.json"
  run chmod +x "$app_entry"
  run ln -sfn "$app_entry" "$target"

  if [[ "$DRY_RUN" -eq 0 ]]; then
    {
      echo "# rollback actions"
      echo "rm -f \"$target\""
      echo "rm -rf \"$app_dir\""
    } >"$rollback_file"
    say "rollback script written: $rollback_file"
  fi

  say "installation complete"
  cat <<EOF
Next steps:
  1. $target theme list
  2. $target theme apply mocha
  3. $target generate --help
EOF
}

main "$@"
