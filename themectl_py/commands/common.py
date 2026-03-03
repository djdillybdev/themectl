from __future__ import annotations

import re
import sys
from pathlib import Path

from ..contracts.validation import (
    validate_palette_minimal,
    validate_roles_minimal,
    validate_target_manifest_contract,
)
from ..jsonio import read_json

HEX_RE = re.compile(r"#[0-9A-Fa-f]+")

USAGE_TEXT = """Usage:
  themectl help
  themectl version
  themectl validate
  themectl theme list|current
  themectl theme apply <theme_id> [pass-through flags]
  themectl theme pick [--fallback-select]
  themectl theme toggle|cycle [pass-through flags]
  themectl generate [pass-through flags]
  themectl target scaffold <name>
  themectl target test <name>
  themectl config get|set|unset <key> [value]
"""


def print_help() -> None:
    print(USAGE_TEXT)


def is_tty_interactive() -> bool:
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def manifest_files(paths) -> list[Path]:
    files: list[Path] = []
    if paths.targets_dir.exists():
        files.extend(sorted(paths.targets_dir.glob("*.json")))
    if paths.user_targets_dir.exists():
        files.extend(sorted(paths.user_targets_dir.glob("*.json")))
    return files


def validate_all_manifests(paths) -> tuple[bool, str]:
    try:
        roles_raw = read_json(paths.roles_file, {}, strict=True, label="roles")
    except RuntimeError as exc:
        return False, str(exc)
    if not isinstance(roles_raw, dict):
        return False, f"Invalid JSON roles file: {paths.roles_file}"
    allowed_roles = set()
    defaults = roles_raw.get("defaults", {})
    if isinstance(defaults, dict):
        allowed_roles.update(k for k in defaults.keys() if isinstance(k, str))
    role_sets = roles_raw.get("role_sets", {})
    if isinstance(role_sets, dict):
        for role_set in role_sets.values():
            if isinstance(role_set, dict):
                allowed_roles.update(k for k in role_set.keys() if isinstance(k, str))

    for manifest_path in manifest_files(paths):
        is_valid, error_message = validate_target_manifest_contract(manifest_path, paths.root, allowed_roles)
        if not is_valid:
            return False, f"Invalid target manifest schema: {error_message}"
    return True, "ok"


def validate_installation(paths) -> tuple[bool, str]:
    roles_ok, roles_msg = validate_roles_minimal(paths.roles_file)
    if not roles_ok:
        return False, roles_msg
    for palette_path in sorted(paths.palettes_dir.glob("*.json")):
        palette_ok, palette_msg = validate_palette_minimal(palette_path)
        if not palette_ok:
            return False, palette_msg
    manifests_ok, manifests_msg = validate_all_manifests(paths)
    if not manifests_ok:
        return manifests_ok, manifests_msg
    for template_path in sorted((paths.root / "templates").rglob("*.tmpl")):
        text = template_path.read_text()
        for literal in HEX_RE.findall(text):
            if len(literal) not in {7, 9}:
                return False, f"Invalid hex literal in template {template_path}: {literal}"
        if text.count("{{") != text.count("}}"):
            return False, f"Unbalanced template delimiters in {template_path}"
    return True, "ok"
