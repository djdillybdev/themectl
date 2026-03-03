# Config Reference

Config file path:
- `~/.config/themectl/config.json`

## Keys

### `wallpapers_dir`

- Type: string or null
- Purpose: image source directory for interactive `themectl generate` when `--image` is omitted.

### `set_wallpaper_on_image`

- Type: boolean
- Default: `true`
- Purpose: whether generation should set wallpaper automatically (unless disabled by CLI flags).

### `enabled_targets`

- Type: `array[string]` or `null`
- Purpose: default target list for `theme apply` when `--targets` is not provided.
- Behavior:
  - `null` or missing key: all discovered targets are eligible.
  - non-empty list: only listed targets are eligible by default.
  - empty list: apply operates with no selected targets.
