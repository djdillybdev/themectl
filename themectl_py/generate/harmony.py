import math
from typing import Any


DEFAULT_SPREAD = {
    "complementary": 0.0,
    "analogous": 30.0,
    "monochromatic": 0.0,
    "split": 30.0,
    "triadic": 0.0,
    "tetrad": 0.0,
    "square": 0.0,
}


def _targets(mode: str, spread: float) -> list[float]:
    if mode == "complementary":
        return [0.0, 180.0]
    if mode == "analogous":
        return [0.0, -spread, spread]
    if mode == "monochromatic":
        return [0.0]
    if mode == "split":
        return [0.0, 180.0 - spread, 180.0 + spread]
    if mode == "triadic":
        return [0.0, 120.0, 240.0]
    if mode == "tetrad":
        return [0.0, 60.0, 180.0, 240.0]
    if mode == "square":
        return [0.0, 90.0, 180.0, 270.0]
    return [0.0, -30.0, 30.0]


def _hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _anchor(candidates: list[dict[str, float]], anchor_mode: str) -> float:
    chromatic = [c for c in candidates if c.get("c", 0.0) >= 0.03]
    base = chromatic or candidates
    if not base:
        return 0.0
    if anchor_mode == "dominant":
        return max(base, key=lambda x: x.get("pop", 0.0)).get("h", 0.0)
    if anchor_mode == "accent":
        return max(base, key=lambda x: x.get("c", 0.0) * 0.6 + x.get("pop", 0.0) * 0.4).get("h", 0.0)
    # auto
    return max(base, key=lambda x: x.get("c", 0.0) * 0.45 + x.get("pop", 0.0) * 0.55).get("h", 0.0)


def apply_harmony(candidates: list[dict[str, float]], mode: str, anchor_mode: str, spread: float, seed_hue: float | None = None) -> list[dict[str, float]]:
    if not candidates or mode == "analogous":
        return candidates

    anchor = seed_hue if seed_hue is not None else _anchor(candidates, anchor_mode)
    targets = [((anchor + offset) % 360.0) for offset in _targets(mode, spread)]

    out: list[dict[str, float]] = []
    for c in candidates:
        rec = dict(c)
        if mode == "monochromatic":
            rec["c"] = max(0.02, min(0.24, rec.get("c", 0.06) * 0.85))
            out.append(rec)
            continue

        h = rec.get("h", 0.0)
        nearest = min(targets, key=lambda t: _hue_distance(h, t))
        # Nudge toward target to preserve image identity while introducing harmonic structure.
        dist = _hue_distance(h, nearest)
        t = 0.62 if dist > 10 else 0.35
        # shortest arc interpolation
        delta = ((nearest - h + 540.0) % 360.0) - 180.0
        rec["h"] = (h + delta * t) % 360.0
        out.append(rec)

    return out
