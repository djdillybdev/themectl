# Plugin and Target Authoring

`themectl` applies templates from target manifests and can run optional shell reload hooks.

## Locations

- Built-in targets: `targets.d/`
- User targets: `~/.config/themectl/targets.d/`

## Manifest

Create `targets.d/<name>.json` with:
- `version` (`1` or `2`; `2` recommended)
- `target`
- `templates`
- optional `write_to_file`
- optional `required_roles`
- optional `reload`
- optional `capabilities`
- optional `validate`

Manifest constraints:
- filename stem must match `target`
- `templates` must be a non-empty object mapping source template path to destination path
- destination paths must be absolute, `~`-prefixed, `$HOME`-prefixed, or `$VARNAME`-prefixed
- `required_roles` entries must be known role keys
- `write_to_file` currently requires exactly one template entry
- `write_to_file.mode` must be `overwrite`, `markers`, or `from_marker`
- marker modes require marker fields (`start_marker`, and `end_marker` for `markers`)
- `reload.mode_hint` must be `none`, `async`, or `sync`
- `capabilities.reload_mode_supported` must contain `async` and/or `sync`
- `capabilities.session_scope` must be `user` or `global`
- `capabilities.health_check` must be a string when present

## `write_to_file` Rules

Example:

```json
"write_to_file": [
  { "path": "$HOME/.config/app/current-theme.conf", "mode": "overwrite" },
  {
    "path": "$HOME/.config/app/config.ini",
    "mode": "markers",
    "start_marker": "# THEMECTL START",
    "end_marker": "# THEMECTL END"
  },
  {
    "path": "$HOME/.config/app/config.ini",
    "mode": "from_marker",
    "start_marker": "# THEMECTL START"
  }
]
```

Mode behavior:
- `overwrite`: full file replace
- `markers`: replace each `start_marker...end_marker` block while preserving markers
- `from_marker`: replace from `start_marker` to EOF while preserving marker

## Optional Shell Reload Hook

If present, `targets.d/<name>.sh` may define:
- `target_reload_<name>`

Apply/render is Python-first; shell hooks are reload integration points.

## Reload Environment Contract

Reload hooks receive:
- `THEMECTL_OPERATION`, `THEMECTL_TARGET`, `THEMECTL_THEME_ID`
- `THEMECTL_THEME_FAMILY`, `THEMECTL_THEME_VARIANT`, `THEMECTL_PALETTE_PATH`
- `THEMECTL_RELOAD_META_FILE`

Per-color exports are also available as:
- `THEMECTL_COLOR_<TOKEN>_HEX`
- `THEMECTL_COLOR_<TOKEN>_RGB_R|G|B`
- `THEMECTL_COLOR_<TOKEN>_DEC_R|G|B`

## Authoring Workflow

- `themectl target scaffold <name>`: create starter manifest/template/reload hook in `~/.config/themectl/targets.d`.
- `themectl target test <name>`: validate manifest and run a dry-run apply for the target.
