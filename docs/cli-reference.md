# CLI Reference

## General

- `themectl help`
- `themectl version`
- `themectl validate`

## Theme

- `themectl theme list`
- `themectl theme current`
- `themectl theme apply <theme_id> [--targets csv] [--dry-run] [--no-reload] [--profile fast|full|full-parallel] [--reload-mode async|sync] [--reload-targets csv] [--transaction off|best-effort|required]`
- `themectl theme pick [--fallback-select]`
- `themectl theme toggle [apply flags]`
- `themectl theme cycle [apply flags]`

Transaction mode:
- `off`: writes directly; failures can leave partial changes.
- `best-effort` (default): plans first, commits writes, and reports failures.
- `required`: preflight failures abort writes; commit failures trigger rollback.

Target precedence for apply:
- `--targets` value (highest priority)
- `config.enabled_targets`
- all discovered targets

## Generate

- `themectl generate [--image <path>] [style flags] [--apply|--no-apply] [--no-wallpaper] [--set-wallpaper before|after|off]`

Behavior:
- If `--image` is omitted in an interactive TTY, `generate` opens image selection from configured `wallpapers_dir`.
- If `--image` is omitted in non-interactive mode, `generate` exits with an error.
- Wallpaper set timing is controlled by `--set-wallpaper`; default is `after`.

## Target

- `themectl target scaffold <name>`
- `themectl target test <name>`

## Config

- `themectl config get wallpapers_dir`
- `themectl config set wallpapers_dir <path>`
- `themectl config unset wallpapers_dir`
- `themectl config get set_wallpaper_on_image`
- `themectl config set set_wallpaper_on_image true|false`
- `themectl config unset set_wallpaper_on_image`
- `themectl config get enabled_targets`
- `themectl config set enabled_targets kitty,nvim,vscode`
- `themectl config unset enabled_targets`
