from __future__ import annotations

from dataclasses import dataclass

from .jsonio import read_json, write_json_atomic
from .paths import AppPaths


@dataclass
class AppState:
    current_theme: str | None


def load_state(paths: AppPaths) -> AppState:
    raw = read_json(paths.state_file, {}, strict=True, label="state")
    current = raw.get("current_theme")
    if isinstance(current, str) and current:
        return AppState(current_theme=current)
    return AppState(current_theme=None)


def set_current_theme(paths: AppPaths, theme_id: str) -> None:
    raw = read_json(paths.state_file, {}, strict=True, label="state")
    raw["current_theme"] = theme_id
    write_json_atomic(paths.state_file, raw)
