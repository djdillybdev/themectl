from __future__ import annotations

import sys
from pathlib import Path

from ..apply_native import apply_theme_native
from ..jsonio import read_json
from ..picker import fallback_select, run_fzf
from ..state import load_state


def list_theme_ids(palettes_dir: Path) -> list[str]:
    theme_ids: list[str] = []
    for palette_path in sorted(palettes_dir.glob("*.json")):
        payload = read_json(palette_path, {})
        theme_id = payload.get("id")
        if isinstance(theme_id, str):
            theme_ids.append(theme_id)
    return theme_ids


def _theme_meta(palette_path: Path) -> tuple[str, str, str, str]:
    payload = read_json(palette_path, {})
    theme_id = payload.get("id") if isinstance(payload.get("id"), str) else palette_path.stem
    variant = payload.get("variant") if isinstance(payload.get("variant"), str) else "unknown"
    family = payload.get("family") if isinstance(payload.get("family"), str) else "unknown"
    origin = payload.get("origin") if isinstance(payload.get("origin"), str) else ""
    if origin:
        return str(theme_id), str(variant), str(family), origin

    source_type = payload.get("source", {}).get("type") if isinstance(payload.get("source"), dict) else ""
    inferred_origin = "generated" if family == "generated" or source_type == "image" else "builtin"
    return str(theme_id), str(variant), str(family), inferred_origin


def pick_theme_interactive(paths, fallback: bool = False) -> str | None:
    palette_paths = sorted(paths.palettes_dir.glob("*.json"))
    if not palette_paths:
        print(f"ERROR: no palette files found in {paths.palettes_dir}", file=sys.stderr)
        return None

    grouped_rows: list[tuple[str, str, str, str, str, str, str]] = []
    for palette_path in palette_paths:
        theme_id, variant, family, origin = _theme_meta(palette_path)
        group_rank, group_label = ("2", "Generated") if origin == "generated" else ("1", "Built-in / Catppuccin")
        grouped_rows.append((group_rank, group_label, theme_id, variant, family, origin, str(palette_path)))
    grouped_rows.sort(key=lambda row: (row[0], row[2]))

    fzf_rows: list[str] = []
    theme_ids: list[str] = []
    previous_group_label = ""
    for _, group_label, theme_id, variant, family, origin, palette_path in grouped_rows:
        if group_label != previous_group_label:
            fzf_rows.append(f"H\t=== {group_label} ===\t\t\t\t\t")
            previous_group_label = group_label
        fzf_rows.append(f"T\t{group_label}\t{theme_id}\t{variant}\t{family}\t{origin}\t{palette_path}")
        theme_ids.append(theme_id)

    if not fallback:
        preview_cmd = f"{paths.root / 'scripts' / 'themectl_theme_preview.sh'} {{7}}"
        while True:
            selected_row = run_fzf(
                fzf_rows,
                prompt="theme",
                preview_cmd=preview_cmd,
                delimiter="\t",
                with_nth="2,3,4,5,6",
                height="55%",
                preview_window="right:60%",
            )
            if not selected_row:
                return None
            selected_parts = selected_row.split("\t")
            if selected_parts and selected_parts[0] == "T" and len(selected_parts) >= 3:
                return selected_parts[2]

    return fallback_select(theme_ids, "Select theme")


def _resolve_theme_id_for_toggle(paths) -> str | None:
    theme_ids = list_theme_ids(paths.palettes_dir)
    if not theme_ids:
        print("ERROR: no palettes found", file=sys.stderr)
        return None

    state = load_state(paths)
    current_theme_id = state.current_theme
    if current_theme_id in theme_ids:
        current_index = theme_ids.index(current_theme_id)
        return theme_ids[(current_index + 1) % len(theme_ids)]
    return theme_ids[0]


def handle_theme_action(paths, args) -> int:
    if args.action == "list":
        for theme_id in list_theme_ids(paths.palettes_dir):
            print(theme_id)
        return 0

    if args.action == "current":
        state = load_state(paths)
        if state.current_theme:
            print(state.current_theme)
        return 0

    if args.action == "apply":
        apply_tokens: list[str] = []
        if args.theme_id:
            apply_tokens.append(args.theme_id)
        apply_tokens.extend(args.rest)
        if not apply_tokens or apply_tokens[0].startswith("-"):
            print("ERROR: apply requires explicit <theme_id>", file=sys.stderr)
            return 1
        return apply_theme_native(paths, apply_tokens[0], apply_tokens[1:], operation="apply")

    if args.action == "pick":
        from .common import is_tty_interactive

        if not is_tty_interactive():
            print("ERROR: interactive theme selection requires a TTY", file=sys.stderr)
            return 1
        selected_theme_id = pick_theme_interactive(paths, fallback=bool(getattr(args, "fallback_select", False)))
        if not selected_theme_id:
            return 1
        return apply_theme_native(paths, selected_theme_id, [], operation="pick")

    if args.action in ("toggle", "cycle"):
        selected_theme_id = _resolve_theme_id_for_toggle(paths)
        if not selected_theme_id:
            return 1
        return apply_theme_native(paths, selected_theme_id, list(args.rest), operation=args.action)

    print(f"ERROR: unknown theme action: {args.action}", file=sys.stderr)
    return 1
