# Contracts

This document defines stable runtime and data contracts for current `themectl` behavior.

## Palette Contract

Path: `palettes/<theme_id>.json`

Required keys:
- `id`
- `family`
- `variant`

Common keys:
- `colors` (object of color roles; expected by most templates/targets)
- `color_model` (optional)
- `origin` (optional)
- `source` (optional)

Color values are expected as `#RRGGBB` when used by rendering/role resolution.

## Roles Contract

Path: `roles.json`

Minimum required key:
- `defaults`

Current repository schema also includes versioned role-set/rule fields used by resolution logic.

## Target Manifest Contract

Paths:
- built-in: `targets.d/<target>.json`
- user: `~/.config/themectl/targets.d/<target>.json`

Supported top-level keys:
- `version`
- `target`
- `templates`
- `required_roles`
- `reload`
- `validate`
- `capabilities`
- `write_to_file`

Validation and behavior guarantees:
- strict schema validation for known keys
- strict filename-to-target match
- strict template source/destination checks
- strict `required_roles` validation against known role keys

## Reload Log Contract

Path: `~/.config/themectl/.cache/apply-reload.log.jsonl`

Async dispatch and completion events include:
- `ts`
- `theme_id`
- `target`
- `mode`
- `dispatch_ok`

Depending on event type, entries may also include `pid`, `exit_code`, and target-specific metadata.

## Reload Environment Contract

Reload execution receives stable variables:
- `THEMECTL_OPERATION`
- `THEMECTL_TARGET`
- `THEMECTL_THEME_ID`
- `THEMECTL_THEME_FAMILY`
- `THEMECTL_THEME_VARIANT`
- `THEMECTL_PALETTE_PATH`
- `THEMECTL_RELOAD_META_FILE`

Per-color variables are exported for normalized palette tokens:
- `THEMECTL_COLOR_<TOKEN>_HEX`
- `THEMECTL_COLOR_<TOKEN>_RGB_R|G|B`
- `THEMECTL_COLOR_<TOKEN>_DEC_R|G|B`
