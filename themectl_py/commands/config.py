from __future__ import annotations

import sys

from ..config import load_config, set_config_key, unset_config_key

VALID_CONFIG_KEYS = {
    "wallpapers_dir",
    "set_wallpaper_on_image",
    "enabled_targets",
}

BOOLEAN_CONFIG_KEYS = {"set_wallpaper_on_image"}


def _parse_csv_targets(value: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in value.split(","):
        name = token.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def handle_config_action(paths, args) -> int:
    if args.key not in VALID_CONFIG_KEYS:
        print(f"ERROR: Unknown config key: {args.key}", file=sys.stderr)
        return 1

    if args.action == "get":
        config = load_config(paths)
        value = getattr(config, args.key)
        if args.key == "enabled_targets":
            print(",".join(value or []))
            return 0
        print(value)
        return 0

    if args.action == "set":
        if args.value is None:
            print("ERROR: config set requires a value", file=sys.stderr)
            return 1

        value: object = args.value
        if args.key in BOOLEAN_CONFIG_KEYS:
            if args.value not in {"true", "false"}:
                print(f"ERROR: {args.key} must be true or false", file=sys.stderr)
                return 1
            value = args.value == "true"
        elif args.key == "enabled_targets":
            value = _parse_csv_targets(args.value)

        set_config_key(paths, args.key, value)
        print(f"Set {args.key}={args.value}")
        return 0

    if args.action == "unset":
        unset_config_key(paths, args.key)
        print(f"Unset {args.key}")
        return 0

    print(f"ERROR: unsupported config action: {args.action}", file=sys.stderr)
    return 1
