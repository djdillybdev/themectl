# Role Override Patterns

Centralize per-theme and per-variant style policy in `roles.json` rules.

## Principles

- Keep templates semantic (`{{role:...}}`).
- Keep theme exceptions in `roles.json`, not templates.
- Keep overrides narrow and explicit in `rules[].match`.

## Focus Border Pattern

`roles.json` defaults/role sets provide baseline focus keys:

- `ui.focus.focused_border = accent0`
- `ui.focus.unfocused_border = surface0`
- `ui.focus.inactive_border = surface1`

Variant-specific overrides can then target family/variant combinations where needed.

## Recommended Rule Authoring

- Match on `family` + `variant` first.
- Add `theme_id` only for true theme-specific exceptions.
- Avoid raw hex overrides unless you intentionally bypass palette semantics.
