from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .config import load_config
from .jsonio import read_json, write_json_atomic
from .palette import load_palette_by_id, normalize_colors
from .paths import AppPaths
from .patch_write import PatchWriteError, patch_between_markers, patch_from_marker
from .render import render_template_text, write_atomic
from .roles import build_resolved_roles, resolve_role_hex
from .state import set_current_theme

ENV_TOKEN_RE = re.compile(r"[^A-Z0-9]+")


def _expand_dest(path: str) -> Path:
    expanded = os.path.expandvars(path.replace("$HOME", str(Path.home())))
    return Path(expanded).expanduser()


def _target_manifests(paths: AppPaths) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for base in (paths.targets_dir, paths.user_targets_dir):
        if not base.exists():
            continue
        for f in sorted(base.glob("*.json")):
            payload = read_json(f, {}, strict=True, label="target manifest")
            t = payload.get("target")
            if isinstance(t, str):
                payload["__manifest_dir"] = str(f.parent)
                out[t] = payload
    return out


def _parse_apply_flags(rest: list[str]) -> tuple[list[str] | None, bool, bool, str, str | None, set[str] | None, str, str | None]:
    targets: list[str] | None = None
    dry_run = False
    no_reload = False
    profile = "fast"
    reload_mode_override: str | None = None
    reload_targets: set[str] | None = None
    transaction_mode = "best-effort"
    parse_error: str | None = None
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok == "--targets" and i + 1 < len(rest):
            targets = _parse_target_list(rest[i + 1])
            i += 2
            continue
        if tok == "--dry-run":
            dry_run = True
            i += 1
            continue
        if tok == "--no-reload":
            no_reload = True
            i += 1
            continue
        if tok == "--profile" and i + 1 < len(rest):
            profile = rest[i + 1]
            i += 2
            continue
        if tok == "--reload-mode" and i + 1 < len(rest):
            reload_mode_override = rest[i + 1]
            i += 2
            continue
        if tok == "--reload-targets" and i + 1 < len(rest):
            reload_targets = set(_parse_target_list(rest[i + 1]))
            i += 2
            continue
        if tok == "--transaction" and i + 1 < len(rest):
            transaction_mode = rest[i + 1]
            i += 2
            continue
        if tok in {"--targets", "--profile", "--reload-mode", "--reload-targets", "--transaction"}:
            parse_error = f"missing value for {tok}"
            break
        parse_error = f"unknown apply flag: {tok}"
        break
        i += 1
    if parse_error is None and profile not in {"fast", "full", "full-parallel"}:
        parse_error = f"invalid --profile value: {profile}"
    if parse_error is None and reload_mode_override not in {None, "async", "sync"}:
        parse_error = f"invalid --reload-mode value: {reload_mode_override}"
    if parse_error is None and transaction_mode not in {"off", "best-effort", "required"}:
        parse_error = f"invalid --transaction value: {transaction_mode}"
    return targets, dry_run, no_reload, profile, reload_mode_override, reload_targets, transaction_mode, parse_error


def _parse_target_list(csv_text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in csv_text.split(","):
        name = token.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _resolve_effective_targets(
    manifests: dict[str, dict[str, Any]],
    cli_targets: list[str] | None,
    config_targets: list[str] | None,
) -> list[str]:
    if cli_targets is not None:
        return cli_targets
    if config_targets is not None:
        return config_targets
    return sorted(manifests.keys())


def _effective_reload_mode(no_reload: bool, profile: str, override: str | None) -> str:
    if no_reload:
        return "none"
    if override in {"async", "sync"}:
        return override
    if profile == "fast":
        return "async"
    return "sync"


def _resolve_template_source(paths: AppPaths, manifest: dict[str, Any], src_rel: str) -> Path:
    src = Path(src_rel)
    if src.is_absolute():
        return src
    manifest_dir_raw = manifest.get("__manifest_dir")
    if isinstance(manifest_dir_raw, str) and manifest_dir_raw:
        local_src = Path(manifest_dir_raw) / src_rel
        if local_src.exists():
            return local_src
    return paths.root / src_rel


def _apply_fingerprint(paths: AppPaths, palette_path: Path, manifests: dict[str, dict[str, Any]], targets: list[str]) -> str:
    h = hashlib.sha256()
    h.update(palette_path.read_bytes())
    if paths.roles_file.exists():
        h.update(paths.roles_file.read_bytes())
    for t in sorted(targets):
        m = manifests.get(t, {})
        if isinstance(m, dict):
            manifest_data = {k: v for k, v in m.items() if not k.startswith("__")}
        else:
            manifest_data = {}
        h.update(json.dumps(manifest_data, sort_keys=True).encode())
        templates = m.get("templates", {})
        if isinstance(templates, dict):
            for src_rel in sorted(templates.keys()):
                src = _resolve_template_source(paths, m, src_rel)
                if src.exists():
                    h.update(src.read_bytes())
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _reload_script_path(paths: AppPaths, target: str) -> Path | None:
    user = paths.user_targets_dir / f"{target}.sh"
    if user.exists():
        return user
    built_in = paths.targets_dir / f"{target}.sh"
    if built_in.exists():
        return built_in
    return None


def _build_shell_reload_command(script_path: Path, target: str) -> str:
    fn = f"target_reload_{target}"
    return (
        "set -euo pipefail; "
        "register_target(){ :; }; "
        "themectl_warn(){ :; }; themectl_err(){ :; }; themectl_info(){ :; }; "
        f"source {json.dumps(str(script_path))}; "
        f"{fn}"
    )


def _read_reload_meta(meta_file: Path) -> dict[str, Any]:
    if not meta_file.exists():
        return {}
    payload = read_json(meta_file, {})
    return payload if isinstance(payload, dict) else {}


def _normalize_env_token(key: str) -> str:
    normalized = ENV_TOKEN_RE.sub("_", key.upper()).strip("_")
    return re.sub(r"_+", "_", normalized)


def _hex_to_rgb_dec(hex_color: str) -> tuple[tuple[int, int, int], tuple[str, str, str]] | None:
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) != 7:
        return None
    try:
        red = int(hex_color[1:3], 16)
        green = int(hex_color[3:5], 16)
        blue = int(hex_color[5:7], 16)
    except ValueError:
        return None
    return (red, green, blue), (f"{red / 255.0:.6f}", f"{green / 255.0:.6f}", f"{blue / 255.0:.6f}")


def _build_theme_env(
    *,
    operation: str,
    target: str,
    theme_id: str,
    palette_path: Path,
    palette: dict[str, Any],
    colors: dict[str, str],
) -> dict[str, str]:
    out: dict[str, str] = {
        "THEMECTL_OPERATION": operation,
        "THEMECTL_TARGET": target,
        "THEMECTL_THEME_ID": theme_id,
        "THEMECTL_THEME_FAMILY": str(palette.get("family", "")),
        "THEMECTL_THEME_VARIANT": str(palette.get("variant", "")),
        "THEMECTL_PALETTE_PATH": str(palette_path),
    }
    for key, value in colors.items():
        env_token = _normalize_env_token(key)
        if not env_token:
            continue
        out[f"THEMECTL_COLOR_{env_token}_HEX"] = value
        parsed = _hex_to_rgb_dec(value)
        if not parsed:
            continue
        (red, green, blue), (red_dec, green_dec, blue_dec) = parsed
        out[f"THEMECTL_COLOR_{env_token}_RGB_R"] = str(red)
        out[f"THEMECTL_COLOR_{env_token}_RGB_G"] = str(green)
        out[f"THEMECTL_COLOR_{env_token}_RGB_B"] = str(blue)
        out[f"THEMECTL_COLOR_{env_token}_DEC_R"] = red_dec
        out[f"THEMECTL_COLOR_{env_token}_DEC_G"] = green_dec
        out[f"THEMECTL_COLOR_{env_token}_DEC_B"] = blue_dec
    return out


def _run_reload_sync(
    paths: AppPaths,
    target: str,
    manifest: dict[str, Any],
    theme_id: str,
    *,
    theme_env: dict[str, str],
) -> tuple[bool, dict[str, Any]]:
    script_path = _reload_script_path(paths, target)
    meta_file = Path(tempfile.mkstemp(prefix=f"themectl-reload-{target}-", suffix=".json")[1])
    env = os.environ.copy()
    env.update(theme_env)
    env["THEMECTL_RELOAD_META_FILE"] = str(meta_file)
    try:
        if script_path:
            cmd = _build_shell_reload_command(script_path, target)
            rc = subprocess.run(["bash", "-lc", cmd], check=False, env=env).returncode
        else:
            reload_data = manifest.get("reload", {})
            cmd = str(reload_data.get("command", "")).strip()
            if not cmd:
                return True, {}
            rc = subprocess.run(cmd, shell=True, check=False, env=env).returncode
        meta = _read_reload_meta(meta_file)
        return rc == 0, meta
    finally:
        meta_file.unlink(missing_ok=True)


def _run_reload_async(
    paths: AppPaths,
    target: str,
    manifest: dict[str, Any],
    theme_id: str,
    log_file: Path,
    *,
    theme_env: dict[str, str],
) -> bool:
    script_path = _reload_script_path(paths, target)
    meta_file = Path(tempfile.mkstemp(prefix=f"themectl-reload-async-{target}-", suffix=".json")[1])
    reload_data = manifest.get("reload", {})
    fallback_cmd = str(reload_data.get("command", "")).strip()
    payload = {
        "theme_id": theme_id,
        "target": target,
        "script_path": str(script_path) if script_path else "",
        "fallback_cmd": fallback_cmd,
        "meta_file": str(meta_file),
        "log_file": str(log_file),
        "theme_env": theme_env,
    }
    worker = r"""
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

payload = json.loads(sys.argv[1])
log_file = Path(payload["log_file"])
meta_file = Path(payload["meta_file"])
env = os.environ.copy()
theme_env = payload.get("theme_env", {})
if isinstance(theme_env, dict):
    env.update({str(k): str(v) for k, v in theme_env.items()})
env["THEMECTL_RELOAD_META_FILE"] = str(meta_file)
rc = 0
if payload.get("script_path"):
    target = payload["target"]
    fn = f"target_reload_{target}"
    cmd = (
        "set -euo pipefail; "
        "register_target(){ :; }; "
        "themectl_warn(){ :; }; themectl_err(){ :; }; themectl_info(){ :; }; "
        f"source {json.dumps(payload['script_path'])}; "
        f"{fn}"
    )
    rc = subprocess.run(["bash", "-lc", cmd], check=False, env=env).returncode
elif payload.get("fallback_cmd"):
    rc = subprocess.run(payload["fallback_cmd"], shell=True, check=False, env=env).returncode

meta = {}
if meta_file.exists():
    try:
        parsed = json.loads(meta_file.read_text())
        if isinstance(parsed, dict):
            meta = parsed
    except Exception:
        meta = {}
    meta_file.unlink(missing_ok=True)

event = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "theme_id": payload["theme_id"],
    "target": payload["target"],
    "mode": "async",
    "dispatch_ok": True,
    "exit_code": rc,
}
event.update(meta)
if payload.get("target") == "polybar" and rc != 0:
    event.setdefault("reload_method", "none")
    event.setdefault("recovery_used", True)
    event.setdefault("pre_running_count", 1)
    event.setdefault("post_running_count", 0)
log_file.parent.mkdir(parents=True, exist_ok=True)
with log_file.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(event, sort_keys=True) + "\n")
"""
    proc = subprocess.Popen(
        [sys.executable, "-c", worker, json.dumps(payload)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    dispatch_event = {
        "ts": _now_iso(),
        "theme_id": theme_id,
        "target": target,
        "mode": "async",
        "dispatch_ok": True,
        "pid": proc.pid,
    }
    _append_jsonl(log_file, dispatch_event)
    return True


def _manifest_supported_reload_modes(manifest: dict[str, Any]) -> set[str]:
    capabilities = manifest.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return {"async", "sync"}
    reload_modes = capabilities.get("reload_mode_supported", ["async", "sync"])
    if isinstance(reload_modes, list):
        out = {mode for mode in reload_modes if isinstance(mode, str)}
        return out or {"async", "sync"}
    return {"async", "sync"}


def _manifest_health_check(manifest: dict[str, Any]) -> str:
    capabilities = manifest.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return ""
    health_check = capabilities.get("health_check", "")
    return health_check if isinstance(health_check, str) else ""


def _run_target_health_check(target: str, manifest: dict[str, Any], *, dry_run: bool) -> bool:
    health_check = _manifest_health_check(manifest).strip()
    if not health_check:
        return True
    if dry_run:
        print(f"[dry-run] health-check {target}: {health_check}")
        return True
    rc = subprocess.run(health_check, shell=True, check=False).returncode
    if rc != 0:
        print(f"WARN: Health check failed for target: {target}")
        return False
    return True


def _write_to_file_rules(manifest: dict[str, Any]) -> list[dict[str, str]]:
    raw = manifest.get("write_to_file", [])
    if not isinstance(raw, list):
        return []
    rules: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        mode = item.get("mode", "overwrite")
        start_marker = item.get("start_marker", "")
        end_marker = item.get("end_marker", "")
        if not isinstance(path, str) or not isinstance(mode, str):
            continue
        if not isinstance(start_marker, str) or not isinstance(end_marker, str):
            continue
        rules.append(
            {
                "path": path,
                "mode": mode,
                "start_marker": start_marker,
                "end_marker": end_marker,
            }
        )
    return rules


def _rendered_for_write_rule(dst: Path, rendered: str, rule: dict[str, str]) -> str:
    mode = rule.get("mode", "overwrite")
    start_marker = rule.get("start_marker", "")
    end_marker = rule.get("end_marker", "")
    if mode == "overwrite":
        return rendered

    if not dst.exists():
        raise PatchWriteError(f"target file not found for mode '{mode}': {dst}")
    current = dst.read_text()
    if mode == "markers":
        return patch_between_markers(current, rendered, start_marker, end_marker)
    if mode == "from_marker":
        return patch_from_marker(current, rendered, start_marker)
    raise PatchWriteError(f"unsupported write_to_file mode: {mode}")


def _content_would_change(dst: Path, content: str) -> bool:
    if not dst.exists():
        return True
    try:
        if not stat.S_ISREG(dst.stat().st_mode):
            return True
        return dst.read_text() != content
    except Exception:
        return True


def _rollback_written_paths(backups: dict[Path, str | None], written_paths: list[Path]) -> bool:
    rolled_back = True
    for path in reversed(written_paths):
        try:
            original = backups.get(path)
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original)
        except Exception:
            rolled_back = False
    return rolled_back


@dataclass
class _WriteOp:
    path: Path
    content: str
    dry_run_message: str
    would_change: bool


@dataclass
class _TargetPlan:
    target: str
    manifest: dict[str, Any]
    write_ops: list[_WriteOp]
    theme_env: dict[str, str]


def _build_target_plan(
    *,
    paths: AppPaths,
    target: str,
    manifest: dict[str, Any],
    palette: dict[str, Any],
    colors: dict[str, str],
    role_resolver,
    theme_id: str,
    palette_path: Path,
    operation: str,
) -> _TargetPlan:
    templates = manifest.get("templates", {})
    required_roles = manifest.get("required_roles", [])
    if isinstance(required_roles, list):
        for role_key in required_roles:
            if isinstance(role_key, str) and not role_resolver(role_key):
                raise RuntimeError(f"Missing required role: {role_key}")

    write_rules = _write_to_file_rules(manifest)
    if write_rules and len(templates) != 1:
        raise RuntimeError("write_to_file currently supports exactly one template per target")

    rendered_templates: list[tuple[str, Path, str]] = []
    if target == "starship":
        base = paths.root / "templates" / "starship" / "base.toml"
        pal_tmpl = paths.root / "templates" / "starship" / "palette.toml.tmpl"
        if not base.exists():
            raise RuntimeError(f"Missing starship base template: {base}")
        text = render_template_text(
            pal_tmpl.read_text(),
            colors=colors,
            role_resolver=role_resolver,
            theme_id=str(palette.get("id", "unknown")),
            variant=str(palette.get("variant", "dark")),
        )
        rendered = base.read_text().rstrip() + "\n\n" + text
        dst = _expand_dest(str(next(iter(templates.values()))))
        rendered_templates.append(("starship", dst, rendered))
    else:
        for src_rel, dst_raw in templates.items():
            src = _resolve_template_source(paths, manifest, src_rel)
            dst = _expand_dest(str(dst_raw))
            rendered = render_template_text(
                src.read_text(),
                colors=colors,
                role_resolver=role_resolver,
                theme_id=str(palette.get("id", "unknown")),
                variant=str(palette.get("variant", "dark")),
            )
            rendered_templates.append((src.name, dst, rendered))

    write_ops: list[_WriteOp] = []
    if write_rules:
        rendered = rendered_templates[0][2]
        for rule in write_rules:
            mode = rule.get("mode", "overwrite")
            rule_dst = _expand_dest(rule["path"])
            content = _rendered_for_write_rule(rule_dst, rendered, rule)
            write_ops.append(
                _WriteOp(
                    path=rule_dst,
                    content=content,
                    dry_run_message=f"[dry-run] write_to_file {mode} -> {rule_dst}",
                    would_change=_content_would_change(rule_dst, content),
                )
            )
    else:
        for src_name, dst, rendered in rendered_templates:
            write_ops.append(
                _WriteOp(
                    path=dst,
                    content=rendered,
                    dry_run_message=f"[dry-run] render {src_name} -> {dst}",
                    would_change=_content_would_change(dst, rendered),
                )
            )

    theme_env = _build_theme_env(
        operation=operation,
        target=target,
        theme_id=theme_id,
        palette_path=palette_path,
        palette=palette,
        colors=colors,
    )
    return _TargetPlan(target=target, manifest=manifest, write_ops=write_ops, theme_env=theme_env)


def apply_theme_native(paths: AppPaths, theme_id: str, rest: list[str], *, operation: str = "apply") -> int:
    parsed = load_palette_by_id(paths.palettes_dir, theme_id)
    if not parsed:
        print(f"ERROR: Unknown theme: {theme_id}")
        return 1
    palette_path, palette = parsed
    targets_filter, dry_run, no_reload, profile, reload_mode_override, reload_targets, transaction_mode, parse_error = _parse_apply_flags(rest)
    if parse_error:
        print(f"ERROR: {parse_error}", file=sys.stderr)
        return 1
    manifests = _target_manifests(paths)
    config = load_config(paths)
    targets = _resolve_effective_targets(manifests, targets_filter, config.enabled_targets)
    colors = normalize_colors(palette)
    roles = read_json(paths.roles_file, {}, strict=True, label="roles")
    resolved_roles = build_resolved_roles(roles, palette)
    reload_mode = _effective_reload_mode(no_reload, profile, reload_mode_override)
    async_log_file = paths.cache_dir / "apply-reload.log.jsonl"

    def role_resolver(role_key: str) -> str | None:
        return resolve_role_hex(role_key, resolved_roles, colors)

    fp = _apply_fingerprint(paths, palette_path, manifests, targets)
    state_raw = read_json(paths.state_file, {}, strict=True, label="state")
    prev_fp = ""
    prev_theme = ""
    if isinstance(state_raw, dict):
        prev_theme = str(state_raw.get("current_theme", ""))
        la = state_raw.get("last_apply", {})
        if isinstance(la, dict):
            prev_fp = str(la.get("fingerprint", ""))
    if not dry_run and prev_theme == theme_id and prev_fp and prev_fp == fp:
        print(
            f"Apply summary: changed=0 unchanged={len(targets)} reload_dispatched=0 failed=0 "
            f"transaction_mode={transaction_mode} commit_failed=0 rolled_back=0"
        )
        print(f"Theme applied: {theme_id}")
        return 0

    changed = 0
    unchanged = 0
    fails = 0
    reload_dispatched = 0
    commit_failed = False
    rolled_back = False

    plans: list[_TargetPlan] = []
    preflight_failed = False
    for t in targets:
        manifest = manifests.get(t)
        if not manifest:
            print(f"WARN: Unknown target: {t}")
            fails += 1
            if transaction_mode == "required":
                preflight_failed = True
                break
            continue
        print(f"Applying {theme_id} -> {t}")
        try:
            plan = _build_target_plan(
                paths=paths,
                target=t,
                manifest=manifest,
                palette=palette,
                colors=colors,
                role_resolver=role_resolver,
                theme_id=theme_id,
                palette_path=palette_path,
                operation=operation,
            )
            if t == "i3" and dry_run:
                focused = role_resolver("i3.focused_border") or ""
                focused_inactive = role_resolver("i3.focused_inactive_border") or ""
                unfocused = role_resolver("i3.unfocused_border") or ""
                print(f"[dry-run] i3 role colors focused={focused} focused_inactive={focused_inactive} unfocused={unfocused}")
            plans.append(plan)
        except Exception as exc:
            print(f"WARN: Apply failed for target: {t} ({exc})")
            fails += 1
            if transaction_mode == "required":
                preflight_failed = True
                break

    if dry_run:
        for plan in plans:
            for op in plan.write_ops:
                print(op.dry_run_message)
            unchanged += 1
    elif preflight_failed and transaction_mode == "required":
        commit_failed = True
    else:
        committed: list[_TargetPlan] = []
        backups: dict[Path, str | None] = {}
        written_paths: list[Path] = []
        for plan in plans:
            target_changed = False
            target_failed = False
            for op in plan.write_ops:
                try:
                    if op.would_change:
                        if transaction_mode == "required" and op.path not in backups:
                            if op.path.exists() and stat.S_ISREG(op.path.stat().st_mode):
                                backups[op.path] = op.path.read_text()
                            else:
                                backups[op.path] = None
                        if write_atomic(op.path, op.content):
                            target_changed = True
                            written_paths.append(op.path)
                except Exception as exc:
                    fails += 1
                    commit_failed = True
                    target_failed = True
                    print(f"WARN: Apply failed for target: {plan.target} ({exc})")
                    if transaction_mode == "required":
                        rolled_back = _rollback_written_paths(backups, written_paths)
                    break

            if target_failed:
                if transaction_mode == "off":
                    continue
                if transaction_mode in {"best-effort", "required"}:
                    break
                continue

            committed.append(plan)
            if target_changed:
                changed += 1
            else:
                unchanged += 1

        if not commit_failed or transaction_mode == "off":
            pending_parallel: list[tuple[str, dict[str, Any], dict[str, str]]] = []
            for plan in committed:
                t = plan.target
                manifest = plan.manifest
                if reload_mode == "none":
                    continue
                if reload_targets is not None and t not in reload_targets:
                    continue
                if not _run_target_health_check(t, manifest, dry_run=dry_run):
                    fails += 1
                    continue
                reload_data = manifest.get("reload", {})
                if not bool(reload_data.get("enabled", False)):
                    continue
                supported_reload_modes = _manifest_supported_reload_modes(manifest)
                if reload_mode not in supported_reload_modes:
                    print(f"WARN: Reload mode '{reload_mode}' not supported for target: {t}")
                    continue
                if reload_mode == "async":
                    _run_reload_async(paths, t, manifest, theme_id, async_log_file, theme_env=plan.theme_env)
                    reload_dispatched += 1
                    continue
                if profile == "full-parallel":
                    pending_parallel.append((t, manifest, plan.theme_env))
                else:
                    ok, _meta = _run_reload_sync(paths, t, manifest, theme_id, theme_env=plan.theme_env)
                    if ok:
                        reload_dispatched += 1
                    else:
                        fails += 1
                        print(f"WARN: Reload failed for target: {t}")

            if pending_parallel:
                with ThreadPoolExecutor(max_workers=len(pending_parallel)) as ex:
                    futs = {
                        ex.submit(_run_reload_sync, paths, t, m, theme_id, theme_env=theme_env): t
                        for t, m, theme_env in pending_parallel
                    }
                    for fut in as_completed(futs):
                        t = futs[fut]
                        try:
                            ok, _meta = fut.result()
                        except Exception:
                            ok = False
                        if ok:
                            reload_dispatched += 1
                        else:
                            fails += 1
                            print(f"WARN: Reload failed for target: {t}")

    print(
        f"Apply summary: changed={changed} unchanged={unchanged} reload_dispatched={reload_dispatched} failed={fails} "
        f"transaction_mode={transaction_mode} commit_failed={1 if commit_failed else 0} rolled_back={1 if rolled_back else 0}"
    )
    if reload_mode == "async" and reload_dispatched > 0:
        print(f"Async reload log: {async_log_file}")
    if fails == 0 and not commit_failed:
        if not dry_run:
            set_current_theme(paths, theme_id)
            raw = read_json(paths.state_file, {}, strict=True, label="state")
            if isinstance(raw, dict):
                raw.setdefault("last_apply", {})
                if isinstance(raw["last_apply"], dict):
                    raw["last_apply"]["fingerprint"] = fp
                write_json_atomic(paths.state_file, raw)
        print(f"Theme applied: {theme_id}")
        return 0
    if commit_failed and transaction_mode == "required" and rolled_back:
        print(f"WARN: Transaction rollback applied for theme: {theme_id}")
    print(f"WARN: Theme applied with {fails} failure(s): {theme_id}")
    return 2
