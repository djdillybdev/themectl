import datetime as dt
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
from typing import Any

COLOR_KEYS = [
    "rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach", "yellow", "green", "teal", "sky", "sapphire",
    "blue", "lavender", "text", "subtext1", "subtext0", "overlay2", "overlay1", "overlay0", "surface2",
    "surface1", "surface0", "base", "mantle", "crust",
]

ACCENT_KEYS = [
    "rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach", "yellow", "green", "teal", "sky", "sapphire", "blue", "lavender",
]

DARK_NEUTRAL_TARGETS = {
    "text": 0.88,
    "subtext1": 0.78,
    "subtext0": 0.70,
    "overlay2": 0.60,
    "overlay1": 0.52,
    "overlay0": 0.45,
    "surface2": 0.36,
    "surface1": 0.31,
    "surface0": 0.27,
    "base": 0.20,
    "mantle": 0.17,
    "crust": 0.14,
}

LIGHT_NEUTRAL_TARGETS = {
    "text": 0.34,
    "subtext1": 0.42,
    "subtext0": 0.50,
    "overlay2": 0.58,
    "overlay1": 0.66,
    "overlay0": 0.74,
    "surface2": 0.82,
    "surface1": 0.86,
    "surface0": 0.90,
    "base": 0.95,
    "mantle": 0.92,
    "crust": 0.89,
}

NEUTRAL_RATIOS_DARK = {
    "subtext1": 0.82,
    "subtext0": 0.68,
    "overlay2": 0.52,
    "overlay1": 0.40,
    "overlay0": 0.28,
    "surface2": 0.18,
    "surface1": 0.12,
    "surface0": 0.07,
}

NEUTRAL_RATIOS_LIGHT = {
    "subtext1": 0.18,
    "subtext0": 0.30,
    "overlay2": 0.42,
    "overlay1": 0.54,
    "overlay0": 0.66,
    "surface2": 0.78,
    "surface1": 0.86,
    "surface0": 0.92,
}

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb01_np(np: Any, color: str) -> Any:
    r, g, b = hex_to_rgb(color)
    return np.array([r / 255.0, g / 255.0, b / 255.0], dtype=np.float64)


def darken(color: str, amount: float) -> str:
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex((int(r * (1 - amount)), int(g * (1 - amount)), int(b * (1 - amount))))


def lighten(color: str, amount: float) -> str:
    r, g, b = hex_to_rgb(color)
    return rgb_to_hex((int(r + (255 - r) * amount), int(g + (255 - g) * amount), int(b + (255 - b) * amount)))


def blend(c1: str, c2: str, ratio_c2: float = 0.5) -> str:
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    r = int((1 - ratio_c2) * r1 + ratio_c2 * r2)
    g = int((1 - ratio_c2) * g1 + ratio_c2 * g2)
    b = int((1 - ratio_c2) * b1 + ratio_c2 * b2)
    return rgb_to_hex((r, g, b))


def rel_luminance(color: str) -> float:
    r, g, b = hex_to_rgb(color)

    def _lin(v: int) -> float:
        x = v / 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(c1: str, c2: str) -> float:
    l1 = rel_luminance(c1)
    l2 = rel_luminance(c2)
    lo = min(l1, l2)
    hi = max(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def magick_command() -> list[str]:
    if shutil.which("magick"):
        return ["magick"]
    if shutil.which("convert"):
        return ["convert"]
    fail("ImageMagick wasn't found. Install 'magick' or 'convert'.")


def imagemagick_extract(img: str, color_count: int) -> list[str]:
    cmd = [*magick_command(), f"{img}[0]", "-resize", "25%", "-colors", str(color_count), "-unique-colors", "txt:-"]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() if exc.stderr else str(exc)
        fail(f"ImageMagick command failed: {msg}")
    lines = out.splitlines()
    colors: list[str] = []
    for line in lines[1:]:
        m = HEX_RE.search(line)
        if m:
            colors.append(m.group(0).lower())
    return colors


def gen_wal_colors(img: str) -> list[str]:
    for i in range(20):
        cols = imagemagick_extract(img, 16 + i)
        if len(cols) > 16:
            return cols
    fail("ImageMagick couldn't generate a suitable palette.")


def adjust_wal(colors: list[str], light: bool) -> list[str]:
    raw = colors[:1] + colors[8:16] + colors[8:-1]
    while len(raw) < 16:
        raw.append(colors[len(raw) % len(colors)])

    raw = raw[:16]

    if light:
        raw[0] = lighten(colors[-1], 0.85)
        raw[7] = colors[0]
        raw[8] = darken(colors[-1], 0.4)
        raw[15] = colors[0]
    else:
        if raw[0][1] != "0":
            raw[0] = darken(raw[0], 0.40)
        raw[7] = blend(raw[7], "#EEEEEE")
        raw[8] = darken(raw[7], 0.30)
        raw[15] = blend(raw[15], "#EEEEEE")

    return raw


def normalize_id(input_id: str) -> str:
    cleaned = input_id.strip() if input_id else ""
    if cleaned:
        if not re.fullmatch(r"[A-Za-z0-9._-]+", cleaned):
            fail("--id must match [A-Za-z0-9._-]+")
        return cleaned
    return "generated"


def slug_from_image(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0].strip().lower()
    slug = re.sub(r"[^a-z0-9._-]+", "-", name).strip("-._")
    return slug or "generated"


def _srgb_to_linear_np(np: Any, x: Any) -> Any:
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb_np(np: Any, x: Any) -> Any:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * (x ** (1.0 / 2.4)) - 0.055)


def rgb_to_oklab_np(np: Any, rgb: Any) -> Any:
    linear = _srgb_to_linear_np(np, rgb)
    r = linear[:, 0]
    g = linear[:, 1]
    b = linear[:, 2]

    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)

    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return np.stack([L, A, B], axis=1)


def oklab_to_rgb_np(np: Any, lab: Any) -> Any:
    L = lab[:, 0]
    A = lab[:, 1]
    B = lab[:, 2]

    l_ = L + 0.3963377774 * A + 0.2158037573 * B
    m_ = L - 0.1055613458 * A - 0.0638541728 * B
    s_ = L - 0.0894841775 * A - 1.2914855480 * B

    l = l_ ** 3
    m = m_ ** 3
    s = s_ ** 3

    r_linear = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g_linear = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    b_linear = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s

    srgb = _linear_to_srgb_np(np, np.stack([r_linear, g_linear, b_linear], axis=1))
    return np.clip(srgb, 0.0, 1.0)


def oklch_to_hex(np: Any, l: float, c: float, h: float) -> str:
    h_rad = math.radians(h)
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)
    lab = np.array([[clamp(l, 0.0, 1.0), a, b]], dtype=np.float64)
    rgb = oklab_to_rgb_np(np, lab)[0]
    return rgb_to_hex((int(round(rgb[0] * 255)), int(round(rgb[1] * 255)), int(round(rgb[2] * 255))))


def hex_to_oklch(np: Any, color: str) -> tuple[float, float, float]:
    rgb = hex_to_rgb01_np(np, color).reshape(1, 3)
    lab = rgb_to_oklab_np(np, rgb)[0]
    l = float(clamp(lab[0], 0.0, 1.0))
    a = float(lab[1])
    b = float(lab[2])
    c = float((a * a + b * b) ** 0.5)
    h = float((math.degrees(math.atan2(b, a)) + 360.0) % 360.0)
    return l, c, h


def oklab_distance_hex(np: Any, c1: str, c2: str) -> float:
    rgb = np.stack([hex_to_rgb01_np(np, c1), hex_to_rgb01_np(np, c2)], axis=0)
    lab = rgb_to_oklab_np(np, rgb)
    return float(np.linalg.norm(lab[0] - lab[1]))


def contrast_ratio_from_linear_lums(np: Any, fg_l: float, bg_l: Any) -> Any:
    hi = np.maximum(fg_l, bg_l)
    lo = np.minimum(fg_l, bg_l)
    return (hi + 0.05) / (lo + 0.05)


def min_alpha_contrast(np: Any, text: str, base: str, sampled_rgb: Any, alpha: float, percentile: float = 90.0) -> float:
    wall_linear = _srgb_to_linear_np(np, sampled_rgb)
    wall_luma = (0.2126 * wall_linear[:, 0]) + (0.7152 * wall_linear[:, 1]) + (0.0722 * wall_linear[:, 2])
    cut = float(np.percentile(wall_luma, percentile))
    bright = wall_linear[wall_luma >= cut]
    if bright.shape[0] == 0:
        bright = wall_linear

    base_linear = _srgb_to_linear_np(np, hex_to_rgb01_np(np, base))
    text_linear = _srgb_to_linear_np(np, hex_to_rgb01_np(np, text))
    text_l = float((0.2126 * text_linear[0]) + (0.7152 * text_linear[1]) + (0.0722 * text_linear[2]))

    composited = (alpha * base_linear.reshape(1, 3)) + ((1.0 - alpha) * bright)
    bg_luma = (0.2126 * composited[:, 0]) + (0.7152 * composited[:, 1]) + (0.0722 * composited[:, 2])
    ratios = contrast_ratio_from_linear_lums(np, text_l, bg_luma)
    return float(np.min(ratios))


def max_achievable_alpha_contrast(np: Any, sampled_rgb: Any, alpha: float, percentile: float = 90.0) -> float:
    wall_linear = _srgb_to_linear_np(np, sampled_rgb)
    wall_luma = (0.2126 * wall_linear[:, 0]) + (0.7152 * wall_linear[:, 1]) + (0.0722 * wall_linear[:, 2])
    cut = float(np.percentile(wall_luma, percentile))
    bright = wall_luma[wall_luma >= cut]
    if bright.size == 0:
        bright = wall_luma
    max_wall = float(np.max(bright))
    worst_bg = (1.0 - alpha) * max_wall
    return (1.0 + 0.05) / (worst_bg + 0.05)


def image_seed(image_path: str) -> int:
    hasher = hashlib.sha256()
    with open(image_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return int.from_bytes(hasher.digest()[:8], "big", signed=False) % (2**32 - 1)


def require_catppuccin_deps() -> tuple[Any, Any, Any]:
    missing: list[str] = []
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None
        missing.append("numpy")
    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None
        missing.append("Pillow")
    try:
        from sklearn.cluster import MiniBatchKMeans  # type: ignore
    except Exception:
        MiniBatchKMeans = None
        missing.append("scikit-learn")

    if missing:
        fail("perceptual backend requires Python modules: " + ", ".join(missing))

    return np, Image, MiniBatchKMeans


def load_sampled_pixels(image_path: str, np: Any, Image: Any, seed: int, max_side: int = 384, max_samples: int = 24000) -> tuple[Any, float]:
    try:
        with Image.open(image_path) as img:
            resample = getattr(Image, "Resampling", Image).LANCZOS
            img = img.convert("RGB")
            img.thumbnail((max_side, max_side), resample)
            arr = np.asarray(img, dtype=np.float64) / 255.0
    except Exception as exc:
        fail(f"Unable to read image for perceptual backend: {exc}")

    flat = arr.reshape(-1, 3)
    if flat.shape[0] == 0:
        fail("Image produced zero pixels after preprocessing")

    if flat.shape[0] > max_samples:
        rng = np.random.default_rng(seed)
        idx = rng.choice(flat.shape[0], size=max_samples, replace=False)
        flat = flat[idx]

    linear = _srgb_to_linear_np(np, flat)
    mean_luma = float(np.mean(0.2126 * linear[:, 0] + 0.7152 * linear[:, 1] + 0.0722 * linear[:, 2]))
    return flat, mean_luma


def cluster_candidates(np: Any, MiniBatchKMeans: Any, sampled_rgb: Any, seed: int, n_clusters: int = 24) -> list[dict[str, float]]:
    oklab = rgb_to_oklab_np(np, sampled_rgb)
    unique_count = int(np.unique(np.round(oklab, 5), axis=0).shape[0])
    k = max(2, min(n_clusters, unique_count, oklab.shape[0]))

    model = MiniBatchKMeans(
        n_clusters=k,
        random_state=seed,
        n_init=5,
        max_iter=120,
        batch_size=min(4096, oklab.shape[0]),
    )

    labels = model.fit_predict(oklab)
    centers = model.cluster_centers_
    counts = np.bincount(labels, minlength=k)
    total = float(oklab.shape[0])

    candidates: list[dict[str, float]] = []
    for i in range(k):
        pop = float(counts[i] / total)
        l = float(clamp(centers[i][0], 0.0, 1.0))
        a = float(centers[i][1])
        b = float(centers[i][2])
        c = float((a * a + b * b) ** 0.5)
        h = float((math.degrees(math.atan2(b, a)) + 360.0) % 360.0)
        candidates.append({"l": l, "a": a, "b": b, "c": c, "h": h, "pop": pop})

    candidates.sort(key=lambda x: x["pop"], reverse=True)
    return candidates


def build_neutral_targets(variant: str, shift: float) -> dict[str, float]:
    base = dict(DARK_NEUTRAL_TARGETS if variant == "dark" else LIGHT_NEUTRAL_TARGETS)
    if shift <= 0:
        return base
    if variant == "dark":
        base["text"] = clamp(base["text"] + shift, 0.0, 1.0)
        for k in ["subtext1", "subtext0", "overlay2", "overlay1", "overlay0", "surface2", "surface1", "surface0", "base", "mantle", "crust"]:
            base[k] = clamp(base[k] - (shift * 0.55), 0.0, 1.0)
    else:
        base["text"] = clamp(base["text"] - shift, 0.0, 1.0)
        for k in ["subtext1", "subtext0", "overlay2", "overlay1", "overlay0", "surface2", "surface1", "surface0", "base", "mantle", "crust"]:
            base[k] = clamp(base[k] + (shift * 0.55), 0.0, 1.0)
    return base


def build_neutral_palette(np: Any, variant: str, seed_h: float, seed_c: float, shift: float = 0.0) -> dict[str, str]:
    targets = build_neutral_targets(variant, shift)
    neutral_c = clamp(seed_c, 0.008, 0.03)
    return {k: oklch_to_hex(np, targets[k], neutral_c, seed_h) for k in targets}


def accent_targets(variant: str, contrast: str) -> tuple[float, float]:
    if variant == "dark":
        l_map = {"low": 0.80, "balanced": 0.74, "high": 0.66}
    else:
        l_map = {"low": 0.46, "balanced": 0.52, "high": 0.58}

    c_cap = {"low": 0.10, "balanced": 0.13, "high": 0.17}
    return l_map[contrast], c_cap[contrast]


def pastelize_accent(l: float, c: float, target_l: float, cap_c: float, pastel: float) -> tuple[float, float]:
    l2 = lerp(l, target_l, pastel)
    c2 = min(c, cap_c)
    c2 = lerp(c2, c2 * 0.85, pastel)
    c2 = max(0.03, c2)
    return clamp(l2, 0.0, 1.0), clamp(c2, 0.0, 0.37)


def select_accent_candidates(candidates: list[dict[str, float]]) -> list[dict[str, float]]:
    for thresh in (0.045, 0.035, 0.03):
        accent = [c for c in candidates if c["c"] >= thresh]
        if len(accent) >= 4:
            return accent
    return [c for c in candidates if c["c"] > 0.0]


def accent_distance(a: dict[str, float], b: dict[str, float]) -> float:
    hue_part = hue_distance(a["h"], b["h"]) / 180.0
    l_part = abs(a["l"] - b["l"])
    c_part = abs(a["c"] - b["c"])
    return (0.70 * hue_part) + (0.20 * l_part) + (0.10 * c_part)


def prepare_accent_records(candidates: list[dict[str, float]], variant: str, contrast: str, pastel: float) -> list[dict[str, float]]:
    target_l, cap_c = accent_targets(variant, contrast)
    accent_input = select_accent_candidates(candidates)
    records: list[dict[str, float]] = []

    for c in accent_input:
        l2, c2 = pastelize_accent(c["l"], c["c"], target_l, cap_c, pastel)
        records.append({"l": l2, "c": c2, "h": c["h"], "pop": c["pop"], "synthetic": 0.0, "salience": (0.55 * c2) + (0.45 * c["pop"])})

    records.sort(key=lambda x: (x["salience"], x["pop"]), reverse=True)
    return records


def build_diverse_accent_pool(base_records: list[dict[str, float]], target_size: int = 14) -> tuple[list[dict[str, float]], int]:
    if not base_records:
        return [], 0

    pool: list[dict[str, float]] = []
    for min_dist in (0.16, 0.11, 0.07, 0.0):
        for rec in base_records:
            if rec in pool:
                continue
            if not pool:
                pool.append(rec)
                continue
            if min(accent_distance(rec, p) for p in pool) >= min_dist:
                pool.append(rec)
            if len(pool) >= target_size:
                return pool[:target_size], 0

    synth_count = 0
    seed = pool[0]
    hue_offsets = [18.0, -18.0, 36.0, -36.0, 54.0, -54.0, 72.0, -72.0, 108.0, -108.0]
    l_offsets = [0.05, -0.05, 0.09, -0.09]
    c_scale = [0.95, 0.82, 0.70]

    for ho in hue_offsets:
        for lo in l_offsets:
            for cs in c_scale:
                if len(pool) >= target_size:
                    break
                cand = {"h": (seed["h"] + ho) % 360.0, "l": clamp(seed["l"] + lo, 0.0, 1.0), "c": clamp(seed["c"] * cs, 0.03, 0.24), "pop": 0.0, "synthetic": 1.0, "salience": seed["salience"] * cs}
                if min(accent_distance(cand, p) for p in pool) >= 0.07:
                    pool.append(cand)
                    synth_count += 1
            if len(pool) >= target_size:
                break
        if len(pool) >= target_size:
            break

    while len(pool) < target_size:
        idx = len(pool) % max(1, len(base_records))
        base = base_records[idx]
        bump = 9.0 * (1 + (len(pool) // max(1, len(base_records))))
        cand = {"h": (base["h"] + bump) % 360.0, "l": clamp(base["l"] + (0.02 if len(pool) % 2 == 0 else -0.02), 0.0, 1.0), "c": clamp(base["c"] * (0.92 if len(pool) % 3 == 0 else 0.85), 0.03, 0.24), "pop": 0.0, "synthetic": 1.0, "salience": base["salience"] * 0.9}
        pool.append(cand)
        synth_count += 1

    return pool[:target_size], synth_count


def semantic_score(role: str, rec: dict[str, float], variant: str) -> float:
    h = rec["h"]
    l = rec["l"]
    c = rec["c"]
    s = rec["salience"]
    warm = max(0.0, math.cos(math.radians(h - 25.0)))
    cool = max(0.0, math.cos(math.radians(h - 210.0)))
    redish = 1.0 if (h >= 330.0 or h <= 35.0) else 0.0
    yellowish = 1.0 if (35.0 <= h <= 95.0) else 0.0
    greenish = 1.0 if (90.0 <= h <= 170.0) else 0.0
    blueish = 1.0 if (180.0 <= h <= 280.0) else 0.0
    magentaish = 1.0 if (285.0 <= h <= 345.0) else 0.0

    if role == "mauve":
        return (1.0 * s) + (0.5 * c) + (0.2 * cool)
    if role == "red":
        return (1.0 * redish) + (0.7 * warm) + (0.4 * s)
    if role == "yellow":
        return (1.0 * yellowish) + (0.5 * warm) + (0.5 * l)
    if role == "green":
        return (1.0 * greenish) + (0.5 * cool) + (0.3 * s)
    if role == "blue":
        return (1.0 * blueish) + (0.7 * cool) + (0.3 * s)
    if role == "teal":
        tealish = 1.0 if (150.0 <= h <= 220.0) else 0.0
        return (1.0 * tealish) + (0.5 * cool) + (0.2 * l)
    if role == "peach":
        orangeish = 1.0 if (15.0 <= h <= 55.0) else 0.0
        return (1.0 * orangeish) + (0.6 * warm) + (0.2 * l)
    if role == "pink":
        return (1.0 * magentaish) + (0.5 * warm) + (0.2 * l)
    if role == "lavender":
        return (0.8 * blueish) + (0.5 * l) + (0.3 * cool)
    if role == "sapphire":
        return (0.9 * blueish) + (0.4 * cool) + (0.2 * s)
    if role == "sky":
        return (0.7 * blueish) + (0.7 * l) + (0.2 * cool)
    if role == "maroon":
        return (0.8 * warm) + (0.7 * (1.0 - l)) + (0.2 * redish)
    if role == "flamingo":
        return (0.8 * warm) + (0.6 * l) + (0.2 * magentaish)
    if role == "rosewater":
        return (0.6 * warm) + (0.7 * l) + (0.2 * (1.0 - c))

    return s


def assign_semantic_accents(pool: list[dict[str, float]], variant: str) -> dict[str, dict[str, float]]:
    remaining = list(pool)
    assigned: dict[str, dict[str, float]] = {}
    role_order = ["mauve", "red", "yellow", "green", "blue", "teal", "peach", "pink", "lavender", "sapphire", "sky", "maroon", "flamingo", "rosewater"]

    for role in role_order:
        if not remaining:
            break
        best = max(remaining, key=lambda r: semantic_score(role, r, variant))
        assigned[role] = best
        remaining.remove(best)

    if remaining:
        for role in ACCENT_KEYS:
            if role not in assigned:
                assigned[role] = remaining.pop(0)
                if not remaining:
                    break

    # Guarantee all semantic roles exist even when the pool is intentionally small.
    if len(assigned) < len(ACCENT_KEYS):
        seed = pool[0] if pool else {"h": 250.0, "l": 0.70 if variant == "dark" else 0.50, "c": 0.08, "pop": 0.0, "synthetic": 1.0, "salience": 0.3}
        missing = [r for r in ACCENT_KEYS if r not in assigned]
        for idx, role in enumerate(missing):
            offset = 360.0 * (idx + 1) / (len(missing) + 1)
            assigned[role] = {
                "h": (seed["h"] + offset) % 360.0,
                "l": clamp(seed["l"] + (0.04 if idx % 2 == 0 else -0.04), 0.0, 1.0),
                "c": clamp(seed["c"] * (0.90 if idx % 3 == 0 else 0.80), 0.03, 0.24),
                "pop": 0.0,
                "synthetic": 1.0,
                "salience": max(0.1, seed.get("salience", 0.3) * 0.85),
            }

    return assigned


def generate_accents(np: Any, candidates: list[dict[str, float]], variant: str, contrast: str, pastel: float, accent_count: int = len(ACCENT_KEYS)) -> tuple[dict[str, str], int, int]:
    base_records = prepare_accent_records(candidates, variant, contrast, pastel)
    if not base_records:
        base_records = [{"h": 250.0, "l": 0.72 if variant == "dark" else 0.52, "c": 0.08, "pop": 0.0, "synthetic": 1.0, "salience": 0.3}]

    target_size = max(6, min(int(accent_count), len(ACCENT_KEYS)))
    pool, synth_count = build_diverse_accent_pool(base_records, target_size=target_size)
    assigned = assign_semantic_accents(pool, variant)
    out = {k: oklch_to_hex(np, assigned[k]["l"], assigned[k]["c"], assigned[k]["h"]) for k in ACCENT_KEYS}
    return out, len(pool), synth_count


def rebuild_dark_neutrals_from_text_base(np: Any, colors: dict[str, str], neutral_c_max: float = 0.03) -> dict[str, str]:
    text_l, text_c, text_h = hex_to_oklch(np, colors["text"])
    base_l, base_c, base_h = hex_to_oklch(np, colors["base"])
    neutral_h = (0.7 * base_h) + (0.3 * text_h)
    neutral_c = clamp((0.65 * base_c) + (0.35 * text_c), 0.008, neutral_c_max)

    out = dict(colors)
    for key, ratio in NEUTRAL_RATIOS_DARK.items():
        l = lerp(base_l, text_l, ratio)
        out[key] = oklch_to_hex(np, l, neutral_c, neutral_h)

    out["mantle"] = oklch_to_hex(np, clamp(base_l * 0.85, 0.0, 1.0), neutral_c, neutral_h)
    out["crust"] = oklch_to_hex(np, clamp(base_l * 0.70, 0.0, 1.0), neutral_c, neutral_h)
    return out


def rebuild_light_neutrals_from_text_base(np: Any, colors: dict[str, str], neutral_c_max: float = 0.03) -> dict[str, str]:
    text_l, text_c, text_h = hex_to_oklch(np, colors["text"])
    base_l, base_c, base_h = hex_to_oklch(np, colors["base"])
    neutral_h = (0.7 * base_h) + (0.3 * text_h)
    neutral_c = clamp((0.65 * base_c) + (0.35 * text_c), 0.008, neutral_c_max)

    out = dict(colors)
    for key, ratio in NEUTRAL_RATIOS_LIGHT.items():
        l = lerp(text_l, base_l, ratio)
        out[key] = oklch_to_hex(np, l, neutral_c, neutral_h)

    out["mantle"] = oklch_to_hex(np, clamp(base_l * 0.97, 0.0, 1.0), neutral_c, neutral_h)
    out["crust"] = oklch_to_hex(np, clamp(base_l * 0.94, 0.0, 1.0), neutral_c, neutral_h)
    return out


def enforce_dark_terminal_readability(
    np: Any,
    colors: dict[str, str],
    sampled_rgb: Any,
    terminal_opacity: float,
    contrast: str,
    neutral_c_max: float = 0.03,
) -> dict[str, str]:
    opaque_target = {"low": 6.0, "balanced": 7.0, "high": 8.0}[contrast]
    alpha_target_desired = {"low": 4.0, "balanced": 4.5, "high": 5.0}[contrast]
    alpha_target = min(alpha_target_desired, max_achievable_alpha_contrast(np, sampled_rgb, terminal_opacity, percentile=90.0) - 0.05)
    out = dict(colors)

    for _ in range(8):
        opaque_ratio = contrast_ratio(out["text"], out["base"])
        alpha_ratio = min_alpha_contrast(np, out["text"], out["base"], sampled_rgb, terminal_opacity, percentile=90.0)
        if opaque_ratio >= opaque_target and alpha_ratio >= alpha_target:
            return out

        text_l, text_c, text_h = hex_to_oklch(np, out["text"])
        base_l, base_c, base_h = hex_to_oklch(np, out["base"])
        text_l = clamp(text_l + 0.04, 0.0, 1.0)
        base_l = clamp(base_l - 0.03, 0.0, 0.32)
        if text_l - base_l < 0.25:
            text_l = clamp(base_l + 0.25, 0.0, 1.0)

        out["text"] = oklch_to_hex(np, text_l, clamp(text_c, 0.008, neutral_c_max), text_h)
        out["base"] = oklch_to_hex(np, base_l, clamp(base_c, 0.008, neutral_c_max), base_h)
        out = rebuild_dark_neutrals_from_text_base(np, out, neutral_c_max=neutral_c_max)

    out["text"] = "#ffffff"
    out["base"] = "#000000"
    out = rebuild_dark_neutrals_from_text_base(np, out, neutral_c_max=neutral_c_max)
    return out


def enforce_light_terminal_readability(np: Any, colors: dict[str, str], contrast: str, neutral_c_max: float = 0.03) -> dict[str, str]:
    contrast_target = {"low": 4.5, "balanced": 5.0, "high": 6.0}[contrast]
    out = dict(colors)
    for _ in range(8):
        if contrast_ratio(out["text"], out["base"]) >= contrast_target and contrast_ratio(out["subtext1"], out["base"]) >= 3.8:
            return out

        text_l, text_c, text_h = hex_to_oklch(np, out["text"])
        base_l, base_c, base_h = hex_to_oklch(np, out["base"])
        text_l = clamp(text_l - 0.035, 0.0, 0.48)
        base_l = clamp(base_l + 0.02, 0.55, 1.0)
        if base_l - text_l < 0.24:
            text_l = clamp(base_l - 0.24, 0.0, 1.0)

        out["text"] = oklch_to_hex(np, text_l, clamp(text_c, 0.008, neutral_c_max), text_h)
        out["base"] = oklch_to_hex(np, base_l, clamp(base_c, 0.008, neutral_c_max), base_h)
        out = rebuild_light_neutrals_from_text_base(np, out, neutral_c_max=neutral_c_max)

    return out


def _pick_tint_seed(np: Any, candidates: list[dict[str, float]], colors: dict[str, str]) -> tuple[float, float]:
    chromatic = [candidate for candidate in candidates if float(candidate.get("c", 0.0)) >= 0.05]
    if chromatic:
        seed = max(chromatic, key=lambda candidate: float(candidate.get("pop", 0.0)) * float(candidate.get("c", 0.0)))
        return float(seed.get("h", 250.0)) % 360.0, float(seed.get("c", 0.08))

    if "mauve" in colors:
        _, chroma, hue = hex_to_oklch(np, colors["mauve"])
        return hue, chroma

    _, chroma, hue = hex_to_oklch(np, colors.get("base", "#1e1e2e"))
    return hue, chroma


def apply_terminal_bg_mode_to_catppuccin(
    np: Any,
    colors: dict[str, str],
    mode: str,
    variant: str,
    candidates: list[dict[str, float]],
    contrast: str,
    sampled_rgb: Any,
    terminal_opacity: float,
) -> dict[str, str]:
    effective_variant = mode if mode in ("dark", "light") else variant
    out = dict(colors)
    neutral_c_max = 0.07 if mode == "color" else 0.03

    if mode in ("dark", "light"):
        base_h, _ = _pick_tint_seed(np, candidates, out)
        neutral_seed_c = 0.01
        neutral_palette = build_neutral_palette(np, effective_variant, base_h, neutral_seed_c, shift=0.0)
        for key in neutral_palette:
            out[key] = neutral_palette[key]
    elif mode == "color":
        tint_h, tint_c = _pick_tint_seed(np, candidates, out)
        neutral_c = clamp(0.03 + (tint_c * 0.40), 0.03, neutral_c_max)
        targets = build_neutral_targets(effective_variant, 0.0)
        for key, lightness in targets.items():
            out[key] = oklch_to_hex(np, lightness, neutral_c, tint_h)

    if rel_luminance(out["base"]) < rel_luminance(out["text"]):
        out = enforce_dark_terminal_readability(np, out, sampled_rgb, terminal_opacity, contrast, neutral_c_max=neutral_c_max)
    else:
        out = enforce_light_terminal_readability(np, out, contrast, neutral_c_max=neutral_c_max)
    out = enforce_focus_distinction(np, out)
    return out


def apply_terminal_bg_mode_to_wal_term(term: list[str], mode: str, variant: str) -> list[str]:
    out = list(term[:16])
    while len(out) < 16:
        out.append(out[len(out) % max(1, len(out))] if out else "#000000")

    effective_mode = mode if mode in ("dark", "light") else variant
    if mode == "color":
        seed = out[4]
        if effective_mode == "dark":
            out[0] = blend(darken(seed, 0.78), darken(out[0], 0.35), 0.40)
        else:
            out[0] = blend(lighten(seed, 0.82), lighten(out[15], 0.88), 0.45)

    if effective_mode == "dark":
        if mode != "color":
            out[0] = darken(out[0], 0.45)
        out[7] = blend(out[7], "#f0f0f0", 0.55)
        out[8] = darken(out[7], 0.30)
        out[15] = blend(out[15], "#ffffff", 0.50)
        return out

    if mode != "color":
        out[0] = lighten(out[15], 0.88)
    out[7] = darken(out[7], 0.58)
    out[8] = darken(out[7], 0.20)
    out[15] = darken(out[15], 0.62)
    return out


def enforce_focus_distinction(np: Any, colors: dict[str, str]) -> dict[str, str]:
    out = dict(colors)
    dark_theme = rel_luminance(out["base"]) < rel_luminance(out["text"])
    if dark_theme:
        min_dist = 0.22
        min_mauve_base = 5.6
        min_green_base = 7.0
    else:
        min_dist = 0.14
        min_mauve_base = 3.0
        min_green_base = 3.0

    def good(mauve_hex: str, green_hex: str) -> bool:
        return (
            oklab_distance_hex(np, mauve_hex, green_hex) >= min_dist
            and contrast_ratio(mauve_hex, out["base"]) >= min_mauve_base
            and contrast_ratio(green_hex, out["base"]) >= min_green_base
        )

    if good(out["mauve"], out["green"]):
        return out

    m_l, m_c, m_h = hex_to_oklch(np, out["mauve"])
    g_l, g_c, g_h = hex_to_oklch(np, out["green"])

    for delta in range(4, 24, 4):
        for sign in (1, -1):
            cand_h = (g_h + (sign * delta)) % 360.0
            cand = oklch_to_hex(np, g_l, g_c, cand_h)
            if good(out["mauve"], cand):
                out["green"] = cand
                return out

    for delta in range(3, 21, 3):
        for sign in (1, -1):
            cand_h = (m_h + (sign * delta)) % 360.0
            cand = oklch_to_hex(np, m_l, m_c, cand_h)
            if good(cand, out["green"]):
                out["mauve"] = cand
                return out

    for step in (0.03, 0.05, 0.08):
        cand_m = oklch_to_hex(np, clamp(m_l + step, 0.0, 1.0), m_c, m_h)
        cand_g = oklch_to_hex(np, clamp(g_l - step, 0.0, 1.0), g_c, g_h)
        if good(cand_m, cand_g):
            out["mauve"] = cand_m
            out["green"] = cand_g
            return out

    return out


def _choose_focus_roles(colors: dict[str, str]) -> tuple[str, str, str]:
    base_hex = colors.get("base", "#101010")
    focused_candidates = ["mauve", "lavender", "blue", "pink", "teal", "peach", "yellow", "green"]
    unfocused_candidates = ["surface0", "surface1", "overlay0", "subtext0", "overlay1"]
    inactive_candidates = ["surface1", "overlay0", "subtext0", "surface0", "overlay1"]

    focused = "mauve"
    unfocused = "surface0"
    best_pair_score = 0.0
    best_pair: tuple[str, str] | None = None

    # Fast-path: in most palettes this already yields clear state separation.
    if all(k in colors for k in ("mauve", "surface0", "surface1")):
        if contrast_ratio(colors["mauve"], base_hex) >= 2.2 and contrast_ratio(colors["surface0"], base_hex) >= 1.2 and contrast_ratio(colors["mauve"], colors["surface0"]) >= 1.35:
            return "mauve", "surface0", "surface1"

    for f in focused_candidates:
        if f not in colors:
            continue
        if contrast_ratio(colors[f], base_hex) < 2.2:
            continue
        for u in unfocused_candidates:
            if u not in colors:
                continue
            u_base = contrast_ratio(colors[u], base_hex)
            if u_base < 1.2:
                continue
            fu = contrast_ratio(colors[f], colors[u])
            if fu >= 1.35 and u_base >= 1.35:
                focused, unfocused = f, u
                best_pair = (f, u)
                break
            if fu > best_pair_score:
                best_pair_score = fu
                best_pair = (f, u)
        if best_pair is not None and best_pair == (focused, unfocused):
            break

    if best_pair is not None and (focused, unfocused) != best_pair:
        focused, unfocused = best_pair

    inactive = unfocused
    for cand in inactive_candidates:
        if cand not in colors:
            continue
        if contrast_ratio(colors[cand], base_hex) >= 1.2:
            inactive = cand
            break

    return focused, unfocused, inactive


def recommended_roles_for_palette(colors: dict[str, str]) -> dict[str, str]:
    focused_role, unfocused_role, inactive_role = _choose_focus_roles(colors)
    return {
        "ui.bg.primary": "base",
        "ui.bg.elevated": "mantle",
        "ui.fg.primary": "text",
        "ui.fg.muted": "subtext0",
        "ui.accent.primary": "mauve",
        "ui.accent.secondary": "lavender",
        "ui.state.success": "green",
        "ui.state.warning": "yellow",
        "ui.state.danger": "red",
        "ui.focus.focused_border": focused_role,
        "ui.focus.unfocused_border": unfocused_role,
        "ui.focus.inactive_border": inactive_role,
    }


def generate_catppuccin_colors(
    np: Any,
    candidates: list[dict[str, float]],
    sampled_rgb: Any,
    variant: str,
    contrast: str,
    pastel: float,
    terminal_opacity: float,
    accent_count: int = len(ACCENT_KEYS),
) -> tuple[dict[str, str], int, int, float]:
    neutrals = [c for c in candidates if c["c"] < 0.045]
    neutral_seed = (max(neutrals, key=lambda x: x["pop"]) if neutrals else candidates[0])
    seed_h = neutral_seed["h"]
    seed_c = neutral_seed["c"] if neutrals else 0.01

    min_text_base = {"low": 6.0, "balanced": 7.0, "high": 8.0}[contrast]
    neutral_palette = None

    alpha_target_desired = {"low": 4.0, "balanced": 4.5, "high": 5.0}[contrast]
    alpha_target = min(alpha_target_desired, max_achievable_alpha_contrast(np, sampled_rgb, terminal_opacity, percentile=90.0) - 0.05)

    for i in range(10):
        shift = 0.02 * i
        p = build_neutral_palette(np, variant, seed_h, seed_c, shift)
        text_base_ok = contrast_ratio(p["text"], p["base"]) >= min_text_base and contrast_ratio(p["subtext1"], p["base"]) >= 4.5
        alpha_ok = True
        if variant == "dark":
            alpha_ok = min_alpha_contrast(np, p["text"], p["base"], sampled_rgb, terminal_opacity, percentile=90.0) >= alpha_target
        if text_base_ok and alpha_ok:
            neutral_palette = p
            break
        neutral_palette = p

    if neutral_palette is None:
        fail("failed to produce neutral palette")

    accent_palette, accent_pool_size, synthetic_accent_count = generate_accents(np, candidates, variant, contrast, pastel, accent_count=accent_count)

    colors: dict[str, str] = {**accent_palette, **neutral_palette}
    if variant == "dark":
        colors = enforce_dark_terminal_readability(np, colors, sampled_rgb, terminal_opacity, contrast)
    colors = enforce_focus_distinction(np, colors)

    for key in COLOR_KEYS:
        if key not in colors or not HEX_RE.fullmatch(colors[key]):
            fail(f"invalid mapped color for key '{key}'")

    return colors, accent_pool_size, synthetic_accent_count, alpha_target


def map_wal_to_theme(term: list[str], variant: str, image_path: str, backend: str, variant_mode: str, theme_id_override: str) -> dict[str, Any]:
    red = term[1]
    green = term[2]
    yellow = term[3]
    blue = term[4]
    mauve = term[5]
    teal = term[6]
    rosewater = term[7]

    flamingo = term[9]
    lavender = term[10]
    peach = term[11]
    sapphire = term[12]
    pink = term[13]
    sky = term[14]
    maroon = blend(red, peach, 0.5)

    text = term[15]
    base = term[0]

    if variant == "dark":
        mantle = darken(base, 0.12)
        crust = darken(base, 0.24)
        surface0 = lighten(base, 0.10)
        surface1 = lighten(base, 0.18)
        surface2 = lighten(base, 0.26)
        overlay0 = lighten(base, 0.34)
        overlay1 = lighten(base, 0.44)
        overlay2 = lighten(base, 0.54)
        subtext0 = blend(overlay2, text, 0.35)
        subtext1 = blend(overlay2, text, 0.60)
    else:
        mantle = darken(base, 0.04)
        crust = darken(base, 0.08)
        surface0 = darken(base, 0.04)
        surface1 = darken(base, 0.08)
        surface2 = darken(base, 0.12)
        overlay0 = darken(base, 0.20)
        overlay1 = darken(base, 0.30)
        overlay2 = darken(base, 0.40)
        subtext0 = blend(text, overlay2, 0.35)
        subtext1 = blend(text, overlay2, 0.60)

    theme_id = normalize_id(theme_id_override) if theme_id_override else slug_from_image(image_path)

    colors = {
        "rosewater": rosewater,
        "flamingo": flamingo,
        "pink": pink,
        "mauve": mauve,
        "red": red,
        "maroon": maroon,
        "peach": peach,
        "yellow": yellow,
        "green": green,
        "teal": teal,
        "sky": sky,
        "sapphire": sapphire,
        "blue": blue,
        "lavender": lavender,
        "text": text,
        "subtext1": subtext1,
        "subtext0": subtext0,
        "overlay2": overlay2,
        "overlay1": overlay1,
        "overlay0": overlay0,
        "surface2": surface2,
        "surface1": surface1,
        "surface0": surface0,
        "base": base,
        "mantle": mantle,
        "crust": crust,
    }

    return {
        "id": theme_id,
        "origin": "generated",
        "family": "generated",
        "variant": variant,
        "toggle_group": "generated-main",
        "colors": colors,
        "source": {
            "type": "image",
            "image_path": os.path.abspath(image_path),
            "backend": backend,
            "generated_at": dt.datetime.now().astimezone().isoformat(),
            "variant_mode": variant_mode,
        },
    }


def map_catppuccin_to_theme(colors: dict[str, str], variant: str, image_path: str, variant_mode: str, theme_id_override: str, contrast: str, pastel: float, cluster_count: int, sample_size: int, accent_pool_size: int, synthetic_accent_count: int, terminal_opacity: float, alpha_target_effective: float, mauve_green_oklab_distance: float, mauve_base_contrast: float, green_base_contrast: float) -> dict[str, Any]:
    theme_id = normalize_id(theme_id_override) if theme_id_override else slug_from_image(image_path)
    return {
        "id": theme_id,
        "origin": "generated",
        "family": "generated",
        "variant": variant,
        "toggle_group": "generated-main",
        "colors": colors,
        "recommended_roles": recommended_roles_for_palette(colors),
        "source": {
            "type": "image",
            "image_path": os.path.abspath(image_path),
            "backend": "catppuccin",
            "generated_at": dt.datetime.now().astimezone().isoformat(),
            "variant_mode": variant_mode,
            "params": {
                "contrast": contrast,
                "pastel": pastel,
                "extractor": "minibatch_kmeans_oklab",
                "cluster_count": cluster_count,
                "sample_size": sample_size,
                "mapping_mode": "adaptive_semantic",
                "diversity_mode": "balanced",
                "accent_pool_size": accent_pool_size,
                "synthetic_accent_count": synthetic_accent_count,
                "terminal_opacity": terminal_opacity,
                "alpha_readability_mode": "wallpaper_aware_p90",
                "alpha_contrast_target": "balanced",
                "alpha_contrast_target_effective": round(alpha_target_effective, 3),
                "focus_distinction_mode": "hard_oklab_guard",
                "distinction_profile": "catppuccin_dark_calibrated",
                "mauve_green_oklab_distance": round(mauve_green_oklab_distance, 4),
                "mauve_base_contrast": round(mauve_base_contrast, 3),
                "green_base_contrast": round(green_base_contrast, 3),
                "role_assignment_mode": "semantic_role_first",
                "quality_tier": "dark_optimized" if variant == "dark" else "baseline",
            },
        },
    }
