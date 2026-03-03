from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any, *, strict: bool = False, warn: bool = False, label: str | None = None) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        if strict:
            source = label if label else str(path)
            raise RuntimeError(f"Invalid JSON in {source}: {path}")
        if warn:
            source = label if label else str(path)
            print(f"WARN: Invalid JSON in {source}: {path}", file=sys.stderr)
        return default


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
