from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .jsonio import read_json, write_json_atomic
from .paths import AppPaths


@dataclass
class AppConfig:
    wallpapers_dir: str | None = None
    set_wallpaper_on_image: bool = True
    enabled_targets: list[str] | None = None


def _normalize_enabled_targets(raw: Any) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def load_config(paths: AppPaths) -> AppConfig:
    raw = read_json(paths.config_file, {}, strict=True, label="config")
    return AppConfig(
        wallpapers_dir=raw.get("wallpapers_dir"),
        set_wallpaper_on_image=bool(raw.get("set_wallpaper_on_image", True)),
        enabled_targets=_normalize_enabled_targets(raw.get("enabled_targets")),
    )


def set_config_key(paths: AppPaths, key: str, value: Any) -> None:
    raw = read_json(paths.config_file, {}, strict=True, label="config")
    raw[key] = value
    write_json_atomic(paths.config_file, raw)


def unset_config_key(paths: AppPaths, key: str) -> None:
    raw = read_json(paths.config_file, {}, strict=True, label="config")
    raw[key] = None
    write_json_atomic(paths.config_file, raw)
