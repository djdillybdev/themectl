from __future__ import annotations

import re
from pathlib import Path

from ..jsonio import read_json


def validate_palette_minimal(path: Path) -> tuple[bool, str]:
    try:
        data = read_json(path, None, strict=True, label="palette")
    except RuntimeError as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, f"Invalid JSON palette: {path}"
    required = ("id", "family", "variant")
    for key in required:
        if key not in data:
            return False, f"Missing palette key '{key}': {path}"
    return True, "ok"


def validate_roles_minimal(path: Path) -> tuple[bool, str]:
    try:
        data = read_json(path, None, strict=True, label="roles")
    except RuntimeError as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, f"Invalid JSON roles file: {path}"
    if "defaults" not in data:
        return False, f"Missing roles.defaults: {path}"
    return True, "ok"


def validate_target_manifest_minimal(path: Path) -> tuple[bool, str]:
    try:
        data = read_json(path, None, strict=True, label="target manifest")
    except RuntimeError as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, f"Invalid JSON target manifest: {path}"
    if "target" not in data:
        return False, f"Missing target field: {path}"
    if "templates" not in data:
        return False, f"Missing templates field: {path}"
    return True, "ok"


def _valid_dest(dest: str) -> bool:
    if not dest.strip():
        return False
    if dest.startswith("/") or dest.startswith("$HOME/") or dest.startswith("~/"):
        return True
    return bool(re.match(r"^\$[A-Z_][A-Z0-9_]*(/.*)?$", dest))


def _resolve_template_source(path: Path, root: Path, src_rel: str) -> Path | None:
    src = Path(src_rel)
    if src.is_absolute():
        return src if src.exists() else None
    local = path.parent / src_rel
    if local.exists():
        return local
    root_src = root / src_rel
    if root_src.exists():
        return root_src
    return None


def validate_target_manifest_contract(path: Path, root: Path, allowed_roles: set[str]) -> tuple[bool, str]:
    ok, msg = validate_target_manifest_minimal(path)
    if not ok:
        return ok, msg
    data = read_json(path, {}, strict=True, label="target manifest")
    if not isinstance(data, dict):
        return False, f"Invalid JSON target manifest: {path}"

    allowed_keys = {"version", "target", "templates", "required_roles", "reload", "validate", "capabilities", "write_to_file"}
    unknown = sorted(k for k in data.keys() if k not in allowed_keys)
    if unknown:
        return False, f"Unknown keys in target manifest {path}: {', '.join(unknown)}"

    version = data.get("version")
    if not isinstance(version, int) or version not in {1, 2}:
        return False, f"Unsupported or missing manifest version in {path}: expected 1 or 2"

    target = data.get("target")
    if not isinstance(target, str) or not target:
        return False, f"Invalid target field in {path}: expected non-empty string"
    if path.stem != target:
        return False, f"Manifest filename must match target name: {path.name} vs {target}"

    templates = data.get("templates")
    if not isinstance(templates, dict) or not templates:
        return False, f"Manifest templates must be a non-empty object: {path}"
    for src_rel, dest in templates.items():
        if not isinstance(src_rel, str) or not isinstance(dest, str):
            return False, f"Manifest templates must map string->string: {path}"
        src = _resolve_template_source(path, root, src_rel)
        if src is None:
            return False, f"Template source does not exist for {target}: {src_rel}"
        if not _valid_dest(dest):
            return False, f"Invalid template destination for {target}: {dest}"

    write_rules = data.get("write_to_file", [])
    if write_rules is not None and not isinstance(write_rules, list):
        return False, f"write_to_file must be a list in {path}"
    if isinstance(write_rules, list) and write_rules and len(templates) != 1:
        return False, f"write_to_file currently requires exactly one template in {path}"
    for idx, rule in enumerate(write_rules):
        if not isinstance(rule, dict):
            return False, f"write_to_file[{idx}] must be an object in {path}"
        rule_allowed_keys = {"path", "mode", "start_marker", "end_marker"}
        rule_unknown = sorted(k for k in rule.keys() if k not in rule_allowed_keys)
        if rule_unknown:
            return False, f"Unknown write_to_file keys in {path}: {', '.join(rule_unknown)}"
        rule_path = rule.get("path")
        if not isinstance(rule_path, str) or not _valid_dest(rule_path):
            return False, f"Invalid write_to_file[{idx}].path in {path}: {rule_path}"
        mode = rule.get("mode", "overwrite")
        if mode not in {"overwrite", "markers", "from_marker"}:
            return False, f"write_to_file[{idx}].mode must be overwrite|markers|from_marker in {path}"
        start_marker = rule.get("start_marker", "")
        end_marker = rule.get("end_marker", "")
        if mode == "overwrite":
            if "start_marker" in rule or "end_marker" in rule:
                return False, f"write_to_file[{idx}] overwrite mode does not accept marker keys in {path}"
        elif mode == "markers":
            if not isinstance(start_marker, str) or not start_marker.strip():
                return False, f"write_to_file[{idx}].start_marker is required in {path}"
            if not isinstance(end_marker, str) or not end_marker.strip():
                return False, f"write_to_file[{idx}].end_marker is required in {path}"
        elif mode == "from_marker":
            if not isinstance(start_marker, str) or not start_marker.strip():
                return False, f"write_to_file[{idx}].start_marker is required in {path}"
            if "end_marker" in rule:
                return False, f"write_to_file[{idx}] from_marker mode does not accept end_marker in {path}"

    required_roles = data.get("required_roles", [])
    if not isinstance(required_roles, list):
        return False, f"required_roles must be a list in {path}"
    for role in required_roles:
        if not isinstance(role, str):
            return False, f"required_roles must contain strings in {path}"
        if role not in allowed_roles:
            return False, f"Unknown required role '{role}' in {path}"

    reload_data = data.get("reload", {})
    if reload_data is not None and not isinstance(reload_data, dict):
        return False, f"reload must be an object in {path}"
    if isinstance(reload_data, dict):
        reload_allowed_keys = {"enabled", "command", "mode_hint"}
        reload_unknown = sorted(k for k in reload_data.keys() if k not in reload_allowed_keys)
        if reload_unknown:
            return False, f"Unknown reload keys in {path}: {', '.join(reload_unknown)}"
        enabled = reload_data.get("enabled", False)
        if not isinstance(enabled, bool):
            return False, f"reload.enabled must be a boolean in {path}"
        command = reload_data.get("command", "")
        if not isinstance(command, str):
            return False, f"reload.command must be a string in {path}"
        mode_hint = reload_data.get("mode_hint", "none")
        if mode_hint not in {"none", "async", "sync"}:
            return False, f"reload.mode_hint must be one of none|async|sync in {path}"

    validate_checks = data.get("validate", [])
    if validate_checks is not None and not isinstance(validate_checks, list):
        return False, f"validate must be a list in {path}"
    if isinstance(validate_checks, list) and not all(isinstance(item, str) for item in validate_checks):
        return False, f"validate entries must be strings in {path}"

    capabilities = data.get("capabilities", {})
    if capabilities is not None and not isinstance(capabilities, dict):
        return False, f"capabilities must be an object in {path}"
    if isinstance(capabilities, dict):
        cap_allowed_keys = {"reload_mode_supported", "session_scope", "health_check"}
        cap_unknown = sorted(k for k in capabilities.keys() if k not in cap_allowed_keys)
        if cap_unknown:
            return False, f"Unknown capabilities keys in {path}: {', '.join(cap_unknown)}"

        reload_modes = capabilities.get("reload_mode_supported", ["async", "sync"])
        if not isinstance(reload_modes, list) or not all(isinstance(item, str) for item in reload_modes):
            return False, f"capabilities.reload_mode_supported must be a list[str] in {path}"
        valid_reload_modes = {"async", "sync"}
        for mode in reload_modes:
            if mode not in valid_reload_modes:
                return False, f"Invalid reload mode in capabilities.reload_mode_supported in {path}: {mode}"

        session_scope = capabilities.get("session_scope", "user")
        if session_scope not in {"user", "global"}:
            return False, f"capabilities.session_scope must be user|global in {path}"

        health_check = capabilities.get("health_check", "")
        if not isinstance(health_check, str):
            return False, f"capabilities.health_check must be a string in {path}"
    return True, "ok"
