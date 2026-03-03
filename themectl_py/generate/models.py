from typing import Any

from .contracts import BASE16_KEYS, BASE24_EXTRA_KEYS, ANSI_KEYS


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def generate_base16_colors(legacy: Any, np: Any, candidates: list[dict[str, float]], variant: str, contrast: str, pastel: float, accent_count: int = 14) -> dict[str, str]:
    neutrals = [c for c in candidates if c["c"] < 0.045]
    neutral_seed = (max(neutrals, key=lambda x: x["pop"]) if neutrals else candidates[0])
    seed_h = neutral_seed["h"]
    seed_c = neutral_seed["c"] if neutrals else 0.01
    neutral_c = clamp(seed_c, 0.008, 0.03)

    if variant == "dark":
        neutral_targets = {
            "base00": 0.14,
            "base01": 0.19,
            "base02": 0.24,
            "base03": 0.34,
            "base04": 0.56,
            "base05": 0.72,
            "base06": 0.82,
            "base07": 0.90,
        }
    else:
        neutral_targets = {
            "base00": 0.94,
            "base01": 0.88,
            "base02": 0.80,
            "base03": 0.68,
            "base04": 0.46,
            "base05": 0.30,
            "base06": 0.20,
            "base07": 0.12,
        }

    neutrals_out = {k: legacy.oklch_to_hex(np, neutral_targets[k], neutral_c, seed_h) for k in neutral_targets}
    accent_palette, _, _ = legacy.generate_accents(np, candidates, variant, contrast, pastel, accent_count=accent_count)

    colors = {
        **neutrals_out,
        "base08": accent_palette["red"],
        "base09": accent_palette["peach"],
        "base0A": accent_palette["yellow"],
        "base0B": accent_palette["green"],
        "base0C": accent_palette["teal"],
        "base0D": accent_palette["blue"],
        "base0E": accent_palette["mauve"],
        "base0F": accent_palette["maroon"],
    }

    for key in BASE16_KEYS:
        if key not in colors or not legacy.HEX_RE.fullmatch(colors[key]):
            legacy.fail(f"invalid base16 mapped color for key '{key}'")

    return colors


def _neutral_targets_for_variant(variant: str) -> dict[str, float]:
    if variant == "dark":
        return {
            "base00": 0.14,
            "base01": 0.19,
            "base02": 0.24,
            "base03": 0.34,
            "base04": 0.56,
            "base05": 0.72,
            "base06": 0.82,
            "base07": 0.90,
        }
    return {
        "base00": 0.94,
        "base01": 0.88,
        "base02": 0.80,
        "base03": 0.68,
        "base04": 0.46,
        "base05": 0.30,
        "base06": 0.20,
        "base07": 0.12,
    }


def _pick_tint_seed(candidates: list[dict[str, float]]) -> tuple[float, float]:
    chromatic = [candidate for candidate in candidates if float(candidate.get("c", 0.0)) >= 0.05]
    if chromatic:
        seed = max(chromatic, key=lambda candidate: float(candidate.get("pop", 0.0)) * float(candidate.get("c", 0.0))
        )
        return float(seed.get("h", 250.0)) % 360.0, float(seed.get("c", 0.08))
    if candidates:
        return float(candidates[0].get("h", 250.0)) % 360.0, float(candidates[0].get("c", 0.05))
    return 250.0, 0.06


def apply_terminal_bg_mode_to_base16(
    legacy: Any,
    np: Any,
    candidates: list[dict[str, float]],
    base16_colors: dict[str, str],
    mode: str,
    variant: str,
    contrast: str,
    pastel: float,
    accent_count: int = 14,
) -> tuple[dict[str, str], str]:
    effective_variant = mode if mode in ("dark", "light") else variant
    if mode in ("dark", "light"):
        return (
            generate_base16_colors(legacy, np, candidates, effective_variant, contrast, pastel, accent_count=accent_count),
            effective_variant,
        )

    if mode != "color":
        return dict(base16_colors), effective_variant

    tint_h, tint_c = _pick_tint_seed(candidates)
    neutral_c = clamp((0.03 + (tint_c * 0.40)) * (1.0 - (pastel * 0.22)), 0.03, 0.08)
    targets = _neutral_targets_for_variant(effective_variant)
    out = dict(base16_colors)
    for key, lightness in targets.items():
        out[key] = legacy.oklch_to_hex(np, lightness, neutral_c, tint_h)

    return out, effective_variant


def _adjust(hex_color: str, amount: float, lighten: bool) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if lighten:
        r = int(r + (255 - r) * amount)
        g = int(g + (255 - g) * amount)
        b = int(b + (255 - b) * amount)
    else:
        r = int(r * (1 - amount))
        g = int(g * (1 - amount))
        b = int(b * (1 - amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_base24_colors(base16_colors: dict[str, str], variant: str) -> dict[str, str]:
    c = dict(base16_colors)
    if variant == "dark":
        c["base10"] = c["base03"]
        c["base11"] = _adjust(c["base08"], 0.08, True)
        c["base12"] = _adjust(c["base0B"], 0.08, True)
        c["base13"] = _adjust(c["base0A"], 0.08, True)
        c["base14"] = _adjust(c["base0D"], 0.08, True)
        c["base15"] = _adjust(c["base0E"], 0.08, True)
        c["base16"] = _adjust(c["base0C"], 0.08, True)
        c["base17"] = c["base07"]
    else:
        c["base10"] = c["base03"]
        c["base11"] = _adjust(c["base08"], 0.10, False)
        c["base12"] = _adjust(c["base0B"], 0.10, False)
        c["base13"] = _adjust(c["base0A"], 0.10, False)
        c["base14"] = _adjust(c["base0D"], 0.10, False)
        c["base15"] = _adjust(c["base0E"], 0.10, False)
        c["base16"] = _adjust(c["base0C"], 0.10, False)
        c["base17"] = c["base07"]

    for key in BASE24_EXTRA_KEYS:
        if key not in c:
            raise RuntimeError(f"missing base24 color {key}")
    return c


def ansi_from_base16(colors: dict[str, str]) -> dict[str, str]:
    out = {
        "color0": colors["base00"],
        "color1": colors["base08"],
        "color2": colors["base0B"],
        "color3": colors["base0A"],
        "color4": colors["base0D"],
        "color5": colors["base0E"],
        "color6": colors["base0C"],
        "color7": colors["base05"],
        "color8": colors.get("base10", colors["base03"]),
        "color9": colors.get("base11", colors["base08"]),
        "color10": colors.get("base12", colors["base0B"]),
        "color11": colors.get("base13", colors["base0A"]),
        "color12": colors.get("base14", colors["base0D"]),
        "color13": colors.get("base15", colors["base0E"]),
        "color14": colors.get("base16", colors["base0C"]),
        "color15": colors.get("base17", colors["base07"]),
    }
    for key in ANSI_KEYS:
        if key not in out:
            raise RuntimeError(f"missing ansi color {key}")
    return out
