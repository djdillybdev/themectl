from __future__ import annotations

import sys

from .common import validate_installation


def handle_validate_action(paths) -> int:
    is_valid, message = validate_installation(paths)
    if not is_valid:
        print(f"ERROR: {message}", file=sys.stderr)
        return 1
    print("Validation passed: palettes, roles, and target manifests are valid.")
    return 0
