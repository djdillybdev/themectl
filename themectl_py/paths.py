from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    palettes_dir: Path
    targets_dir: Path
    user_targets_dir: Path
    state_file: Path
    roles_file: Path
    config_file: Path
    cache_dir: Path


def _maybe_migrate_legacy_file(root: Path, xdg_dir: Path, name: str) -> Path:
    xdg_path = xdg_dir / name
    legacy_path = root / name
    if xdg_path.exists() or not legacy_path.exists():
        return xdg_path
    xdg_dir.mkdir(parents=True, exist_ok=True)
    xdg_path.write_text(legacy_path.read_text())
    print(f"INFO: migrated {legacy_path} -> {xdg_path}")
    return xdg_path


def discover_paths() -> AppPaths:
    root = Path(__file__).resolve().parents[1]
    config_dir = Path.home() / ".config" / "themectl"
    cache_dir = config_dir / ".cache"
    state_file = _maybe_migrate_legacy_file(root, config_dir, "state.json")
    config_file = _maybe_migrate_legacy_file(root, config_dir, "config.json")
    return AppPaths(
        root=root,
        palettes_dir=root / "palettes",
        targets_dir=root / "targets.d",
        user_targets_dir=config_dir / "targets.d",
        state_file=state_file,
        roles_file=root / "roles.json",
        config_file=config_file,
        cache_dir=cache_dir,
    )
