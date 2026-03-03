from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import read_json


def list_theme_ids(palettes_dir: Path) -> list[str]:
    theme_ids: list[str] = []
    for palette_path in sorted(palettes_dir.glob("*.json")):
        payload = read_json(palette_path, {}, warn=True, label="palette")
        theme_id = payload.get("id")
        if isinstance(theme_id, str):
            theme_ids.append(theme_id)
    return theme_ids


def load_palette_by_id(palettes_dir: Path, theme_id: str) -> tuple[Path, dict[str, Any]] | None:
    for palette_path in sorted(palettes_dir.glob("*.json")):
        payload = read_json(palette_path, {}, warn=True, label="palette")
        if payload.get("id") == theme_id:
            return palette_path, payload
    return None


def _detect_color_model(colors: dict[str, str], palette: dict[str, Any]) -> str:
    declared_model = palette.get("color_model")
    if isinstance(declared_model, str) and declared_model:
        if declared_model not in {"catppuccin26", "base16", "base24", "ansi16"}:
            raise RuntimeError(f"Unsupported color model: {declared_model}")
        return declared_model

    keys = set(colors.keys())
    if {"base00", "base0F"} <= keys:
        return "base24" if "base17" in keys else "base16"
    if {"color0", "color15"} <= keys:
        return "ansi16"
    if {"base", "text", "mauve", "green"} <= keys:
        return "catppuccin26"
    raise RuntimeError("Unable to infer supported color model from palette keys")


def _extract_hex_colors(palette: dict[str, Any]) -> dict[str, str]:
    colors: dict[str, str] = {}
    colors_raw = palette.get("colors")
    if isinstance(colors_raw, dict):
        for key, value in colors_raw.items():
            if isinstance(key, str) and isinstance(value, str) and value.startswith("#"):
                colors[key] = value.lower()

    for key, value in palette.items():
        if isinstance(key, str) and isinstance(value, str) and value.startswith("#"):
            colors.setdefault(key, value.lower())
    return colors


def _apply_base16_base24_fallbacks(colors: dict[str, str]) -> None:
    colors.setdefault("base", colors.get("base00", "#1e1e2e"))
    colors.setdefault("mantle", colors.get("base01", colors["base"]))
    colors.setdefault("crust", colors.get("base02", colors["mantle"]))
    colors.setdefault("text", colors.get("base05", "#cdd6f4"))
    colors.setdefault("subtext1", colors.get("base04", colors["text"]))
    colors.setdefault("subtext0", colors.get("base03", colors["subtext1"]))
    colors.setdefault("overlay2", colors.get("base02", colors["subtext0"]))
    colors.setdefault("overlay1", colors.get("base03", colors["overlay2"]))
    colors.setdefault("overlay0", colors.get("base01", colors["overlay1"]))
    colors.setdefault("surface2", colors.get("base02", colors["overlay2"]))
    colors.setdefault("surface1", colors.get("base01", colors["surface2"]))
    colors.setdefault("surface0", colors.get("base00", colors["surface1"]))

    colors.setdefault("red", colors.get("base08", "#f38ba8"))
    colors.setdefault("peach", colors.get("base09", colors["red"]))
    colors.setdefault("yellow", colors.get("base0A", "#f9e2af"))
    colors.setdefault("green", colors.get("base0B", "#a6e3a1"))
    colors.setdefault("teal", colors.get("base0C", "#94e2d5"))
    colors.setdefault("blue", colors.get("base0D", "#89b4fa"))
    colors.setdefault("mauve", colors.get("base0E", "#cba6f7"))
    colors.setdefault("pink", colors.get("base0F", colors["mauve"]))
    colors.setdefault("lavender", colors.get("base0D", colors["blue"]))
    colors.setdefault("rosewater", colors["text"])
    colors.setdefault("flamingo", colors["red"])
    colors.setdefault("maroon", colors["red"])
    colors.setdefault("sky", colors["blue"])
    colors.setdefault("sapphire", colors["blue"])


def _apply_ansi_like_fallbacks(colors: dict[str, str]) -> None:
    colors.setdefault("base", colors.get("background", colors.get("color0", "#1e1e2e")))
    colors.setdefault("text", colors.get("foreground", colors.get("color7", "#cdd6f4")))
    colors.setdefault("mantle", colors.get("color8", colors["base"]))
    colors.setdefault("crust", colors.get("color0", colors["base"]))
    colors.setdefault("surface0", colors.get("color8", colors["base"]))
    colors.setdefault("surface1", colors.get("color8", colors["surface0"]))
    colors.setdefault("surface2", colors.get("color7", colors["surface1"]))
    colors.setdefault("overlay0", colors["surface0"])
    colors.setdefault("overlay1", colors["surface1"])
    colors.setdefault("overlay2", colors["surface2"])
    colors.setdefault("subtext0", colors["overlay1"])
    colors.setdefault("subtext1", colors["overlay2"])

    colors.setdefault("red", colors.get("color1", "#f38ba8"))
    colors.setdefault("green", colors.get("color2", "#a6e3a1"))
    colors.setdefault("yellow", colors.get("color3", "#f9e2af"))
    colors.setdefault("blue", colors.get("color4", "#89b4fa"))
    colors.setdefault("mauve", colors.get("color5", "#cba6f7"))
    colors.setdefault("teal", colors.get("color6", "#94e2d5"))
    colors.setdefault("pink", colors["mauve"])
    colors.setdefault("lavender", colors["blue"])
    colors.setdefault("peach", colors["yellow"])
    colors.setdefault("rosewater", colors["text"])
    colors.setdefault("flamingo", colors["red"])
    colors.setdefault("maroon", colors["red"])
    colors.setdefault("sky", colors["blue"])
    colors.setdefault("sapphire", colors["blue"])


def _apply_common_semantic_fallbacks(colors: dict[str, str]) -> None:
    colors.setdefault("bg", colors.get("base", "#1e1e2e"))
    colors.setdefault("fg", colors.get("text", "#cdd6f4"))
    colors.setdefault("surface0", colors.get("base", colors["bg"]))
    colors.setdefault("surface1", colors.get("overlay0", colors["surface0"]))
    colors.setdefault("surface2", colors.get("overlay1", colors["surface1"]))
    colors.setdefault("overlay0", colors.get("surface0", colors["bg"]))
    colors.setdefault("overlay1", colors.get("surface1", colors["overlay0"]))
    colors.setdefault("overlay2", colors.get("surface2", colors["overlay1"]))

    colors.setdefault("accent0", colors.get("mauve", colors.get("blue", "#89b4fa")))
    colors.setdefault("accent1", colors.get("lavender", colors["accent0"]))
    colors.setdefault("accent2", colors.get("teal", colors["accent0"]))

    colors.setdefault("error", colors.get("red", "#f38ba8"))
    colors.setdefault("warn", colors.get("yellow", "#f9e2af"))
    colors.setdefault("ok", colors.get("green", "#a6e3a1"))
    colors.setdefault("info", colors.get("blue", "#89b4fa"))

    colors.setdefault("muted", colors.get("subtext0", colors["fg"]))
    colors.setdefault("suggestion", colors.get("overlay2", colors["muted"]))
    colors.setdefault("overlay", colors.get("overlay0", colors["muted"]))
    colors.setdefault("border", colors.get("surface1", colors["overlay"]))
    colors.setdefault("cursor", colors.get("rosewater", colors["fg"]))
    colors.setdefault("selection_bg", colors.get("surface2", colors["bg"]))
    colors.setdefault("selection_fg", colors.get("text", colors["fg"]))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(hex_a)
    br, bg, bb = _hex_to_rgb(hex_b)
    r = int(round((1.0 - t) * ar + t * br))
    g = int(round((1.0 - t) * ag + t * bg))
    b = int(round((1.0 - t) * ab + t * bb))
    return _rgb_to_hex((r, g, b))


def _rel_luminance(hex_color: str) -> float:
    r, g, b = _hex_to_rgb(hex_color)

    def _lin(v: int) -> float:
        x = v / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    l1 = _rel_luminance(hex_a)
    l2 = _rel_luminance(hex_b)
    lo = min(l1, l2)
    hi = max(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _ensure_suggestion_contrast(colors: dict[str, str]) -> None:
    bg = colors.get("bg", colors.get("base", "#1e1e2e"))
    fg = colors.get("fg", colors.get("text", "#cdd6f4"))
    suggestion = colors.get("suggestion", colors.get("overlay2", colors.get("muted", fg)))
    dark_theme = _rel_luminance(bg) < _rel_luminance(fg)

    min_contrast = 2.6 if dark_theme else 2.2
    max_contrast = 4.8 if dark_theme else 4.5
    contrast = _contrast_ratio(suggestion, bg)

    if contrast < min_contrast:
        for step in range(1, 17):
            candidate = _mix(suggestion, fg, step / 16.0)
            if _contrast_ratio(candidate, bg) >= min_contrast:
                suggestion = candidate
                break

    contrast = _contrast_ratio(suggestion, bg)
    if contrast > max_contrast:
        for step in range(1, 17):
            candidate = _mix(suggestion, bg, step / 16.0)
            candidate_contrast = _contrast_ratio(candidate, bg)
            if candidate_contrast <= max_contrast and candidate_contrast >= min_contrast:
                suggestion = candidate
                break

    colors["suggestion"] = suggestion


def _apply_ansi_aliases(colors: dict[str, str]) -> None:
    for index in range(16):
        color_key = f"color{index}"
        alias_key = f"ansi{index}"
        if color_key in colors:
            colors.setdefault(alias_key, colors[color_key])

    colors.setdefault("ansi0", colors.get("surface1", colors["bg"]))
    colors.setdefault("ansi1", colors.get("red", colors["error"]))
    colors.setdefault("ansi2", colors.get("green", colors["ok"]))
    colors.setdefault("ansi3", colors.get("yellow", colors["warn"]))
    colors.setdefault("ansi4", colors.get("blue", colors["info"]))
    colors.setdefault("ansi5", colors.get("mauve", colors["accent0"]))
    colors.setdefault("ansi6", colors.get("teal", colors["accent2"]))
    colors.setdefault("ansi7", colors.get("text", colors["fg"]))
    colors.setdefault("ansi8", colors.get("suggestion", colors.get("surface2", colors["ansi0"])))
    colors.setdefault("ansi9", colors["ansi1"])
    colors.setdefault("ansi10", colors["ansi2"])
    colors.setdefault("ansi11", colors["ansi3"])
    colors.setdefault("ansi12", colors["ansi4"])
    colors.setdefault("ansi13", colors["ansi5"])
    colors.setdefault("ansi14", colors["ansi6"])
    colors.setdefault("ansi15", colors.get("subtext0", colors["ansi7"]))


def normalize_colors(palette: dict[str, Any]) -> dict[str, str]:
    colors = _extract_hex_colors(palette)
    color_model = _detect_color_model(colors, palette)

    if color_model in ("base16", "base24"):
        _apply_base16_base24_fallbacks(colors)
    elif color_model == "ansi16":
        _apply_ansi_like_fallbacks(colors)

    _apply_common_semantic_fallbacks(colors)
    _ensure_suggestion_contrast(colors)
    _apply_ansi_aliases(colors)
    return colors
