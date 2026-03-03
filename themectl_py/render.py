from __future__ import annotations

import re
from pathlib import Path


ROLE_RE = re.compile(r"\{\{role:([^}]+)\}\}")
TOKEN_RE = re.compile(r"\{\{([a-zA-Z0-9_.-]+)\}\}")


def render_template_text(
    template_text: str,
    colors: dict[str, str],
    role_resolver,
    theme_id: str,
    variant: str,
) -> str:
    def role_sub(match: re.Match[str]) -> str:
        role_key = match.group(1).strip()
        hexv = role_resolver(role_key)
        if not hexv:
            raise ValueError(f"Unresolved role placeholder: {role_key}")
        return hexv

    rendered = ROLE_RE.sub(role_sub, template_text)
    mapping = dict(colors)
    mapping["theme_id"] = theme_id
    mapping["variant"] = variant

    def tok_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping:
            return mapping[key]
        return match.group(0)

    rendered = TOKEN_RE.sub(tok_sub, rendered)
    leftovers = ROLE_RE.findall(rendered)
    if leftovers:
        raise ValueError(f"Unresolved role placeholders remain: {', '.join(sorted(set(leftovers)))}")
    return rendered


def write_atomic(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    if path.exists() and path.read_text() == content:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(path)
    return True

