from __future__ import annotations

from typing import Any


def _is_hex(v: str) -> bool:
    if not isinstance(v, str) or len(v) != 7 or not v.startswith("#"):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in v[1:])


def build_resolved_roles(roles_data: dict[str, Any], palette: dict[str, Any]) -> dict[str, str]:
    role_sets = roles_data.get("role_sets", {})
    defaults = roles_data.get("defaults", {})
    rules = roles_data.get("rules", [])
    out: dict[str, str] = {}

    if isinstance(role_sets, dict):
        for rs in role_sets.values():
            if isinstance(rs, dict):
                for k, v in rs.items():
                    if isinstance(k, str) and isinstance(v, str):
                        out[k] = v
    if isinstance(defaults, dict):
        for k, v in defaults.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v

    pid = str(palette.get("id", ""))
    family = str(palette.get("family", ""))
    variant = str(palette.get("variant", ""))
    tgroup = str(palette.get("toggle_group", "default"))

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        match = rule.get("match", {})
        set_map = rule.get("set", {})
        if not isinstance(match, dict) or not isinstance(set_map, dict):
            continue
        if "theme_id" in match and str(match["theme_id"]) != pid:
            continue
        if "family" in match and str(match["family"]) != family:
            continue
        if "variant" in match and str(match["variant"]) != variant:
            continue
        if "toggle_group" in match and str(match["toggle_group"]) != tgroup:
            continue
        for k, v in set_map.items():
            if isinstance(k, str) and isinstance(v, str):
                out[k] = v
    return out


def resolve_role_hex(role_key: str, resolved_roles: dict[str, str], colors: dict[str, str], depth: int = 0) -> str | None:
    if depth > 16:
        return None
    value = resolved_roles.get(role_key)
    if not value:
        aliases = {
            "i3.focused_border": "ui.focus.focused_border",
            "i3.unfocused_border": "ui.focus.unfocused_border",
            "i3.focused_inactive_border": "ui.focus.inactive_border",
        }
        alias = aliases.get(role_key)
        if alias:
            value = resolved_roles.get(alias)
    if not value:
        return None
    if _is_hex(value):
        return value.lower()
    if value in colors:
        return colors[value].lower()
    if value in resolved_roles:
        return resolve_role_hex(value, resolved_roles, colors, depth + 1)
    return None

