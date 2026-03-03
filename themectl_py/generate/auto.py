import math
from typing import Any


AUTO_RESOLVER_VERSION = "auto-v1"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _as_int(v: Any, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _is_auto(v: Any) -> bool:
    return isinstance(v, str) and v == "auto"


def _hue_entropy(candidates: list[dict[str, float]], bins: int = 12) -> float:
    hist = [0.0] * bins
    total = 0.0
    for c in candidates:
        w = float(c.get("pop", 0.0))
        h = float(c.get("h", 0.0)) % 360.0
        idx = int((h / 360.0) * bins) % bins
        hist[idx] += w
        total += w
    if total <= 0:
        return 0.0
    entropy = 0.0
    for h in hist:
        if h <= 0:
            continue
        p = h / total
        entropy -= p * math.log2(p)
    return entropy


def _hue_circular_variance(candidates: list[dict[str, float]]) -> float:
    sx = 0.0
    sy = 0.0
    wsum = 0.0
    for c in candidates:
        w = float(c.get("pop", 0.0))
        h = math.radians(float(c.get("h", 0.0)))
        sx += math.cos(h) * w
        sy += math.sin(h) * w
        wsum += w
    if wsum <= 0:
        return 0.0
    r = (sx * sx + sy * sy) ** 0.5 / wsum
    return _clamp(1.0 - r, 0.0, 1.0)


def compute_image_metrics(np: Any, sampled_rgb: Any, mean_luma: float, candidates: list[dict[str, float]]) -> dict[str, float]:
    if sampled_rgb is None or getattr(sampled_rgb, "shape", [0])[0] == 0:
        return {
            "mean_luma": round(float(mean_luma), 4),
            "luma_std": 0.0,
            "mean_chroma": 0.0,
            "hue_entropy": 0.0,
            "hue_circular_variance": 0.0,
            "edge_density": 0.0,
            "neutral_ratio": 1.0,
        }

    linear = np.where(sampled_rgb <= 0.04045, sampled_rgb / 12.92, ((sampled_rgb + 0.055) / 1.055) ** 2.4)
    luma = 0.2126 * linear[:, 0] + 0.7152 * linear[:, 1] + 0.0722 * linear[:, 2]
    luma_std = float(np.std(luma))
    mean_chroma = float(np.mean([float(c.get("c", 0.0)) for c in candidates])) if candidates else 0.0
    neutral_ratio = 1.0
    if candidates:
        neutral_ratio = float(sum(1.0 for c in candidates if float(c.get("c", 0.0)) < 0.045) / len(candidates))

    # A low-cost texture proxy: luma gradient over a coarse thumbnail-ish reshape when possible.
    edge_density = 0.0
    if sampled_rgb.shape[0] >= 1024:
        n = int(sampled_rgb.shape[0] ** 0.5)
        if n >= 16:
            l2 = luma[: n * n].reshape((n, n))
            gx = np.abs(np.diff(l2, axis=1))
            gy = np.abs(np.diff(l2, axis=0))
            edge_density = float(np.mean(gx) + np.mean(gy))

    return {
        "mean_luma": round(float(mean_luma), 4),
        "luma_std": round(luma_std, 4),
        "mean_chroma": round(mean_chroma, 4),
        "hue_entropy": round(_hue_entropy(candidates), 4),
        "hue_circular_variance": round(_hue_circular_variance(candidates), 4),
        "edge_density": round(edge_density, 4),
        "neutral_ratio": round(neutral_ratio, 4),
    }


def default_metrics_for_wal(variant: str) -> dict[str, float]:
    return {
        "mean_luma": 0.62 if variant == "light" else 0.34,
        "luma_std": 0.12,
        "mean_chroma": 0.09,
        "hue_entropy": 1.8,
        "hue_circular_variance": 0.45,
        "edge_density": 0.05,
        "neutral_ratio": 0.25,
    }


def resolve_params(requested: dict[str, Any], metrics: dict[str, float], backend: str) -> dict[str, Any]:
    out = dict(requested)
    ml = float(metrics.get("mean_luma", 0.45))
    ls = float(metrics.get("luma_std", 0.12))
    mc = float(metrics.get("mean_chroma", 0.08))
    he = float(metrics.get("hue_entropy", 1.6))
    hv = float(metrics.get("hue_circular_variance", 0.5))
    ed = float(metrics.get("edge_density", 0.05))
    nr = float(metrics.get("neutral_ratio", 0.3))

    if _is_auto(out.get("variant")):
        out["variant"] = "light" if ml >= 0.5 else "dark"

    if _is_auto(out.get("terminal_bg")):
        out["terminal_bg"] = "light" if ml >= 0.5 else "dark"

    if _is_auto(out.get("palette_model")):
        if backend == "wal":
            out["palette_model"] = "ansi16"
        elif mc < 0.05:
            out["palette_model"] = "base16"
        elif he > 2.2 and mc > 0.08:
            out["palette_model"] = "catppuccin26"
        else:
            out["palette_model"] = "base24"

    if _is_auto(out.get("harmony")):
        if hv < 0.25 and he < 1.2:
            out["harmony"] = "monochromatic"
        elif he > 2.5:
            out["harmony"] = "triadic"
        elif 0.35 <= hv <= 0.65:
            out["harmony"] = "complementary"
        else:
            out["harmony"] = "analogous"

    if _is_auto(out.get("harmony_spread")):
        spread = 18.0 + (hv * 24.0)
        out["harmony_spread"] = round(_clamp(spread, 18.0, 42.0), 2)
    else:
        out["harmony_spread"] = _clamp(_as_float(out.get("harmony_spread"), 30.0), 0.0, 90.0)

    if _is_auto(out.get("contrast")):
        if ls < 0.11 or ed > 0.08:
            out["contrast"] = "high"
        elif ls > 0.2 and nr < 0.2:
            out["contrast"] = "low"
        else:
            out["contrast"] = "balanced"

    if _is_auto(out.get("pastel")):
        out["pastel"] = round(_clamp(0.62 - (mc * 3.0), 0.15, 0.7), 3)
    else:
        out["pastel"] = _clamp(_as_float(out.get("pastel"), 0.35), 0.0, 1.0)

    if _is_auto(out.get("terminal_opacity")):
        out["terminal_opacity"] = round(_clamp(0.82 + (ed * 1.5), 0.82, 1.0), 3)
    else:
        out["terminal_opacity"] = _clamp(_as_float(out.get("terminal_opacity"), 0.8), 0.01, 1.0)

    if _is_auto(out.get("saturation")):
        out["saturation"] = round(_clamp(1.18 - (mc * 2.0), 0.85, 1.25), 3)
    else:
        out["saturation"] = _clamp(_as_float(out.get("saturation"), 1.0), 0.0, 2.0)

    if _is_auto(out.get("lightness_bias")):
        out["lightness_bias"] = round(_clamp((0.5 - ml) * 0.18, -0.12, 0.12), 3)
    else:
        out["lightness_bias"] = _clamp(_as_float(out.get("lightness_bias"), 0.0), -0.25, 0.25)

    if _is_auto(out.get("neutral_warmth")):
        out["neutral_warmth"] = round(_clamp((0.5 - nr) * 0.45, -0.35, 0.35), 3)
    else:
        out["neutral_warmth"] = _clamp(_as_float(out.get("neutral_warmth"), 0.0), -1.0, 1.0)

    if _is_auto(out.get("accent_count")):
        out["accent_count"] = int(round(_clamp(6.0 + (he * 2.6), 6.0, 14.0)))
    else:
        out["accent_count"] = int(_clamp(float(_as_int(out.get("accent_count"), 14)), 6.0, 14.0))

    if _is_auto(out.get("gamut_fit")):
        out["gamut_fit"] = "oklch-chroma" if mc > 0.10 else "lch-chroma"

    if _is_auto(out.get("colorblind_safe")):
        out["colorblind_safe"] = "deuteranopia" if he < 1.0 and nr > 0.5 else "off"

    if _is_auto(out.get("role_distinction")):
        if he < 1.3:
            out["role_distinction"] = "high"
        elif he < 2.1:
            out["role_distinction"] = "balanced"
        else:
            out["role_distinction"] = "low"

    if _is_auto(out.get("noise_filter")):
        if ed > 0.09 and he > 2.2:
            out["noise_filter"] = "high"
        elif ed < 0.04:
            out["noise_filter"] = "low"
        else:
            out["noise_filter"] = "medium"

    if _is_auto(out.get("seed_hue")):
        out["seed_hue"] = "auto"
    else:
        out["seed_hue"] = round(_clamp(_as_float(out.get("seed_hue"), 0.0), 0.0, 359.999), 3)

    return out
