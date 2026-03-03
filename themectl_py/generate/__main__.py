#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from typing import Any

from . import engine
from .auto import AUTO_RESOLVER_VERSION, compute_image_metrics, default_metrics_for_wal, resolve_params
from .cli import parse_args
from .harmony import apply_harmony
from .mapping import map_model_theme
from .models import ansi_from_base16, apply_terminal_bg_mode_to_base16, generate_base16_colors, generate_base24_colors


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def _is_auto(value: Any) -> bool:
    return isinstance(value, str) and value == "auto"


def _to_float(name: str, value: Any, low: float, high: float, *, allow_auto: bool = True) -> float | str:
    if allow_auto and _is_auto(value):
        return "auto"
    try:
        out = float(value)
    except (TypeError, ValueError):
        _fail(f"{name} must be {'auto or ' if allow_auto else ''}a number in [{low}, {high}]")
    if out < low or out > high:
        _fail(f"{name} must be {'auto or ' if allow_auto else ''}a number in [{low}, {high}]")
    return out


def _to_int(name: str, value: Any, low: int, high: int, *, allow_auto: bool = True) -> int | str:
    if allow_auto and _is_auto(value):
        return "auto"
    try:
        out = int(float(value))
    except (TypeError, ValueError):
        _fail(f"{name} must be {'auto or ' if allow_auto else ''}an integer in [{low}, {high}]")
    if out < low or out > high:
        _fail(f"{name} must be {'auto or ' if allow_auto else ''}an integer in [{low}, {high}]")
    return out


def _normalize_numeric_ranges(requested: dict[str, Any]) -> None:
    requested["harmony_spread"] = _to_float("--harmony-spread", requested["harmony_spread"], 0.0, 90.0)
    requested["pastel"] = _to_float("--pastel", requested["pastel"], 0.0, 1.0)
    requested["terminal_opacity"] = _to_float("--terminal-opacity", requested["terminal_opacity"], 0.0001, 1.0)
    requested["saturation"] = _to_float("--saturation", requested["saturation"], 0.0, 2.0)
    requested["lightness_bias"] = _to_float("--lightness-bias", requested["lightness_bias"], -0.25, 0.25)
    requested["neutral_warmth"] = _to_float("--neutral-warmth", requested["neutral_warmth"], -1.0, 1.0)
    requested["accent_count"] = _to_int("--accent-count", requested["accent_count"], 6, 14)
    if requested["seed_hue"] != "auto":
        requested["seed_hue"] = _to_float("--seed-hue", requested["seed_hue"], 0.0, 359.999, allow_auto=False)


def _requested_params(args: Any) -> dict[str, Any]:
    return {
        "variant": args.variant,
        "palette_model": args.palette_model,
        "harmony": args.harmony,
        "harmony_anchor": args.harmony_anchor,
        "harmony_spread": args.harmony_spread,
        "contrast": args.contrast,
        "pastel": args.pastel,
        "terminal_opacity": args.terminal_opacity,
        "terminal_bg": args.terminal_bg,
        "saturation": args.saturation,
        "lightness_bias": args.lightness_bias,
        "neutral_warmth": args.neutral_warmth,
        "accent_count": args.accent_count,
        "seed_hue": args.seed_hue,
        "gamut_fit": "auto",
        "colorblind_safe": args.colorblind_safe,
        "role_distinction": args.role_distinction,
        "noise_filter": args.noise_filter,
    }


def _variant_for_wal(extracted_colors: list[str], requested_variant: str) -> str:
    if requested_variant == "auto":
        return "light" if engine.rel_luminance(extracted_colors[0]) >= 0.55 else "dark"
    return requested_variant


def _variant_for_perceptual(mean_luma: float, requested_variant: str) -> str:
    if requested_variant == "auto":
        return "light" if mean_luma >= 0.5 else "dark"
    return requested_variant


def _seed_hue_or_none(seed_hue: Any) -> float | None:
    if seed_hue == "auto":
        return None
    try:
        return float(seed_hue)
    except (TypeError, ValueError):
        return None


def _tune_candidates(candidates: list[dict[str, float]], resolved: dict[str, Any]) -> list[dict[str, float]]:
    saturation = float(resolved["saturation"])
    lightness_bias = float(resolved["lightness_bias"])
    neutral_warmth = float(resolved["neutral_warmth"])
    noise_level = str(resolved["noise_filter"])
    min_population = {"low": 0.0, "medium": 0.003, "high": 0.008}.get(noise_level, 0.003)

    tuned: list[dict[str, float]] = []
    for candidate in candidates:
        updated = dict(candidate)
        updated["c"] = max(0.0, min(0.37, float(updated.get("c", 0.0)) * saturation))
        updated["l"] = max(0.0, min(1.0, float(updated.get("l", 0.0)) + lightness_bias))
        if float(updated.get("c", 0.0)) < 0.05 and neutral_warmth != 0.0:
            updated["h"] = (float(updated.get("h", 0.0)) + (neutral_warmth * 25.0)) % 360.0
        if float(updated.get("pop", 0.0)) >= min_population:
            tuned.append(updated)

    if len(tuned) >= 6:
        return tuned
    return sorted((dict(candidate) for candidate in candidates), key=lambda entry: float(entry.get("pop", 0.0)), reverse=True)[:6]


def _apply_role_distinction_guard(
    numpy_module: Any,
    colors: dict[str, str],
    resolved: dict[str, Any],
    palette_model: str,
) -> dict[str, str]:
    distinction_level = str(resolved.get("role_distinction", "balanced"))
    colorblind_mode = str(resolved.get("colorblind_safe", "off"))
    if distinction_level == "low" and colorblind_mode == "off":
        return colors

    role_pairs: list[tuple[str, str]] = []
    if palette_model == "catppuccin26":
        role_pairs = [("mauve", "green"), ("blue", "teal")]
    elif palette_model in ("base16", "base24"):
        role_pairs = [("base0E", "base0B"), ("base0D", "base0C")]
    elif palette_model == "ansi16":
        role_pairs = [("color5", "color2"), ("color4", "color6")]

    minimum_distance = {"low": 0.12, "balanced": 0.16, "high": 0.2}.get(distinction_level, 0.16)
    if colorblind_mode != "off":
        minimum_distance = max(minimum_distance, 0.2)

    out = dict(colors)
    for anchor_key, adjust_key in role_pairs:
        if anchor_key not in out or adjust_key not in out:
            continue
        anchor_color = out[anchor_key]
        candidate_color = out[adjust_key]
        if engine.oklab_distance_hex(numpy_module, anchor_color, candidate_color) >= minimum_distance:
            continue
        lightness, chroma, hue = engine.hex_to_oklch(numpy_module, candidate_color)
        adjusted_color = candidate_color
        for hue_shift in (12.0, -12.0, 20.0, -20.0, 30.0, -30.0):
            shifted_color = engine.oklch_to_hex(numpy_module, lightness, chroma, (hue + hue_shift) % 360.0)
            if engine.oklab_distance_hex(numpy_module, anchor_color, shifted_color) >= minimum_distance:
                adjusted_color = shifted_color
                break
        out[adjust_key] = adjusted_color
    return out


def _attach_metadata(
    theme: dict[str, Any],
    requested: dict[str, Any],
    resolved: dict[str, Any],
    metrics: dict[str, Any],
    extractor_backend: str,
) -> None:
    source = theme.setdefault("source", {})
    source["backend"] = extractor_backend
    params = source.setdefault("params", {})
    params.update(requested)
    params["extractor_backend"] = extractor_backend
    params["resolved"] = resolved
    params["auto_resolver_version"] = AUTO_RESOLVER_VERSION
    params["image_metrics"] = metrics


def _print_theme(theme: dict[str, Any]) -> None:
    print(json.dumps(theme, indent=2))


def _build_mapped_theme(
    *,
    colors: dict[str, str],
    color_model: str,
    variant: str,
    image_path: str,
    requested: dict[str, Any],
    resolved: dict[str, Any],
    theme_id_override: str,
    extractor_backend: str,
    extra_params: dict[str, Any],
) -> dict[str, Any]:
    return map_model_theme(
        legacy=engine,
        colors=colors,
        color_model=color_model,
        variant=variant,
        image_path=image_path,
        variant_mode=str(requested["variant"]),
        theme_id_override=theme_id_override,
        backend=extractor_backend,
        harmony=requested["harmony"],
        harmony_anchor=requested["harmony_anchor"],
        harmony_spread=requested["harmony_spread"],
        contrast=requested["contrast"],
        pastel=requested["pastel"],
        terminal_opacity=requested["terminal_opacity"],
        saturation=requested["saturation"],
        lightness_bias=requested["lightness_bias"],
        neutral_warmth=requested["neutral_warmth"],
        accent_count=requested["accent_count"],
        seed_hue=requested["seed_hue"],
        gamut_fit=requested["gamut_fit"],
        colorblind_safe=requested["colorblind_safe"],
        terminal_bg=requested["terminal_bg"],
        role_distinction=requested["role_distinction"],
        noise_filter=requested["noise_filter"],
        extra_params=extra_params,
    )


def _generate_wal_theme(args: Any, image_path: str, requested: dict[str, Any]) -> dict[str, Any]:
    extracted = engine.gen_wal_colors(image_path)
    variant_guess = _variant_for_wal(extracted, str(requested["variant"]))
    metrics = default_metrics_for_wal(variant_guess)
    resolved = resolve_params(requested, metrics, backend="wal")
    variant = str(resolved["variant"])
    terminal_colors = engine.adjust_wal(extracted, light=(variant == "light"))
    terminal_colors = engine.apply_terminal_bg_mode_to_wal_term(terminal_colors, str(resolved["terminal_bg"]), variant)

    palette_model = str(resolved["palette_model"])
    if palette_model not in ("ansi16", "catppuccin26"):
        palette_model = "ansi16"
        resolved["palette_model"] = palette_model

    if palette_model == "ansi16":
        colors = {f"color{i}": terminal_colors[i] for i in range(16)}
        theme = _build_mapped_theme(
            colors=colors,
            color_model="ansi16",
            variant=variant,
            image_path=image_path,
            requested=requested,
            resolved=resolved,
            theme_id_override=args.id,
            extractor_backend="wal",
            extra_params={"mapping_mode": "wal_terminal_direct"},
        )
        _attach_metadata(theme, requested, resolved, metrics, "wal")
        return theme

    theme = engine.map_wal_to_theme(terminal_colors, variant, image_path, "wal", str(requested["variant"]), args.id)
    _attach_metadata(theme, requested, resolved, metrics, "wal")
    return theme


def _generate_perceptual_theme(args: Any, image_path: str, requested: dict[str, Any]) -> dict[str, Any]:
    numpy_module, image_module, kmeans_cls = engine.require_catppuccin_deps()
    seed = engine.image_seed(image_path)
    sampled_rgb, mean_luma = engine.load_sampled_pixels(image_path, numpy_module, image_module, seed)
    raw_candidates = engine.cluster_candidates(numpy_module, kmeans_cls, sampled_rgb, seed, n_clusters=24)

    metrics = compute_image_metrics(numpy_module, sampled_rgb, mean_luma, raw_candidates)
    resolved = resolve_params(requested, metrics, backend="perceptual")

    variant = _variant_for_perceptual(mean_luma, str(resolved["variant"]))
    resolved["variant"] = variant
    tuned_candidates = _tune_candidates(raw_candidates, resolved)
    tuned_candidates = apply_harmony(
        tuned_candidates,
        str(resolved["harmony"]),
        str(resolved["harmony_anchor"]),
        float(resolved["harmony_spread"]),
        seed_hue=_seed_hue_or_none(resolved["seed_hue"]),
    )

    palette_model = str(resolved["palette_model"])
    if palette_model == "catppuccin26":
        colors, accent_pool_size, synthetic_accent_count, alpha_target = engine.generate_catppuccin_colors(
            numpy_module,
            tuned_candidates,
            sampled_rgb,
            variant,
            str(resolved["contrast"]),
            float(resolved["pastel"]),
            float(resolved["terminal_opacity"]),
            accent_count=int(resolved["accent_count"]),
        )
        colors = engine.apply_terminal_bg_mode_to_catppuccin(
            numpy_module,
            colors,
            str(resolved["terminal_bg"]),
            variant,
            tuned_candidates,
            str(resolved["contrast"]),
            sampled_rgb,
            float(resolved["terminal_opacity"]),
        )
        colors = _apply_role_distinction_guard(numpy_module, colors, resolved, "catppuccin26")
        theme = engine.map_catppuccin_to_theme(
            colors,
            variant,
            image_path,
            str(requested["variant"]),
            args.id,
            str(resolved["contrast"]),
            float(resolved["pastel"]),
            cluster_count=min(24, len(tuned_candidates)),
            sample_size=int(sampled_rgb.shape[0]),
            accent_pool_size=accent_pool_size,
            synthetic_accent_count=synthetic_accent_count,
            terminal_opacity=float(resolved["terminal_opacity"]),
            alpha_target_effective=alpha_target,
            mauve_green_oklab_distance=engine.oklab_distance_hex(numpy_module, colors["mauve"], colors["green"]),
            mauve_base_contrast=engine.contrast_ratio(colors["mauve"], colors["base"]),
            green_base_contrast=engine.contrast_ratio(colors["green"], colors["base"]),
        )
        _attach_metadata(theme, requested, resolved, metrics, "perceptual")
        return theme

    base16 = generate_base16_colors(
        engine,
        numpy_module,
        tuned_candidates,
        variant,
        str(resolved["contrast"]),
        float(resolved["pastel"]),
        accent_count=int(resolved["accent_count"]),
    )
    base16, effective_variant = apply_terminal_bg_mode_to_base16(
        engine,
        numpy_module,
        tuned_candidates,
        base16,
        str(resolved["terminal_bg"]),
        variant,
        str(resolved["contrast"]),
        float(resolved["pastel"]),
        accent_count=int(resolved["accent_count"]),
    )
    base16 = _apply_role_distinction_guard(numpy_module, base16, resolved, "base16")

    if palette_model == "base16":
        theme = _build_mapped_theme(
            colors=base16,
            color_model="base16",
            variant=variant,
            image_path=image_path,
            requested=requested,
            resolved=resolved,
            theme_id_override=args.id,
            extractor_backend="perceptual",
            extra_params={
                "extractor": "minibatch_kmeans_oklab",
                "cluster_count": min(24, len(tuned_candidates)),
                "sample_size": int(sampled_rgb.shape[0]),
                "mapping_mode": "base16_semantic",
                "quality_tier": "image_derived",
            },
        )
        _attach_metadata(theme, requested, resolved, metrics, "perceptual")
        return theme

    if palette_model == "base24":
        base24 = generate_base24_colors(base16, effective_variant)
        base24 = _apply_role_distinction_guard(numpy_module, base24, resolved, "base24")
        theme = _build_mapped_theme(
            colors=base24,
            color_model="base24",
            variant=variant,
            image_path=image_path,
            requested=requested,
            resolved=resolved,
            theme_id_override=args.id,
            extractor_backend="perceptual",
            extra_params={
                "extractor": "minibatch_kmeans_oklab",
                "cluster_count": min(24, len(tuned_candidates)),
                "sample_size": int(sampled_rgb.shape[0]),
                "mapping_mode": "base24_semantic",
                "quality_tier": "image_derived",
            },
        )
        _attach_metadata(theme, requested, resolved, metrics, "perceptual")
        return theme

    if palette_model == "ansi16":
        base24 = generate_base24_colors(base16, effective_variant)
        ansi16 = ansi_from_base16(base24)
        ansi16 = _apply_role_distinction_guard(numpy_module, ansi16, resolved, "ansi16")
        theme = _build_mapped_theme(
            colors=ansi16,
            color_model="ansi16",
            variant=variant,
            image_path=image_path,
            requested=requested,
            resolved=resolved,
            theme_id_override=args.id,
            extractor_backend="perceptual",
            extra_params={
                "extractor": "minibatch_kmeans_oklab",
                "cluster_count": min(24, len(tuned_candidates)),
                "sample_size": int(sampled_rgb.shape[0]),
                "mapping_mode": "ansi16_terminal",
                "quality_tier": "image_derived",
            },
        )
        _attach_metadata(theme, requested, resolved, metrics, "perceptual")
        return theme

    _fail(f"Unsupported --palette-model: {palette_model}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    image_path = os.path.abspath(args.image)
    if not os.path.isfile(image_path):
        _fail(f"Image file not found: {image_path}")

    requested = _requested_params(args)
    _normalize_numeric_ranges(requested)

    if args.backend == "wal":
        theme = _generate_wal_theme(args, image_path, requested)
        _print_theme(theme)
        return

    theme = _generate_perceptual_theme(args, image_path, requested)
    _print_theme(theme)


def run(argv: list[str]) -> tuple[int, str, str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    return_code = 0
    with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
        try:
            main(argv)
        except SystemExit as exc:
            if isinstance(exc.code, int):
                return_code = exc.code
            elif exc.code is None:
                return_code = 0
            else:
                return_code = 1
        except Exception as exc:
            return_code = 1
            print(f"ERROR: {exc}", file=sys.stderr)
    return return_code, stdout_buffer.getvalue(), stderr_buffer.getvalue()


if __name__ == "__main__":
    main()
