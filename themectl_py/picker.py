from __future__ import annotations

import shutil
import subprocess
from typing import Iterable


def has_fzf() -> bool:
    return shutil.which("fzf") is not None


def run_fzf(
    lines: Iterable[str],
    prompt: str,
    preview_cmd: str | None = None,
    *,
    delimiter: str | None = None,
    with_nth: str | None = None,
    height: str = "50%",
    preview_window: str = "right:60%",
) -> str | None:
    if not has_fzf():
        return None
    cmd = ["fzf", "--prompt", f"{prompt}> ", "--height", height, "--reverse"]
    if delimiter:
        cmd += ["--delimiter", delimiter]
    if with_nth:
        cmd += ["--with-nth", with_nth]
    if preview_cmd:
        cmd += ["--preview", preview_cmd, "--preview-window", preview_window]
    proc = subprocess.run(
        cmd,
        input="\n".join(lines) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def fallback_select(options: list[str], prompt: str) -> str | None:
    if not options:
        return None
    print(f"{prompt}:")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    try:
        raw = input("Choose number: ").strip()
        idx = int(raw)
    except (ValueError, EOFError):
        return None
    if idx < 1 or idx > len(options):
        return None
    return options[idx - 1]
