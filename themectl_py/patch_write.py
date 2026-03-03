from __future__ import annotations

import re


class PatchWriteError(RuntimeError):
    pass


def _normalize_insertion(insertion: str) -> str:
    return insertion.rstrip("\n")


def patch_between_markers(source: str, insertion: str, start_marker: str, end_marker: str) -> str:
    if not start_marker or not end_marker:
        raise PatchWriteError("markers mode requires non-empty start_marker and end_marker")

    replacement = f"{start_marker}\n{_normalize_insertion(insertion)}\n{end_marker}"
    pattern = re.compile(f"{re.escape(start_marker)}.*?{re.escape(end_marker)}", flags=re.DOTALL)
    patched, count = pattern.subn(replacement, source)
    if count == 0:
        raise PatchWriteError(f"markers not found: start={start_marker!r} end={end_marker!r}")
    return patched


def patch_from_marker(source: str, insertion: str, start_marker: str) -> str:
    if not start_marker:
        raise PatchWriteError("from_marker mode requires non-empty start_marker")

    marker_index = source.find(start_marker)
    if marker_index < 0:
        raise PatchWriteError(f"start marker not found: {start_marker!r}")
    head = source[: marker_index + len(start_marker)]
    return f"{head}\n{_normalize_insertion(insertion)}\n"
