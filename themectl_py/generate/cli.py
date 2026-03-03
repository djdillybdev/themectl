import argparse

from .contracts import (
    COLORBLIND_SAFE_MODES,
    CONTRASTS,
    EXTRACTOR_BACKENDS,
    HARMONY_ANCHORS,
    HARMONY_MODES,
    NOISE_FILTERS,
    PALETTE_MODELS,
    ROLE_DISTINCTIONS,
    TERMINAL_BG_MODES,
    VARIANTS,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Generate a themectl palette from image.\n"
            "Style flags shape accent hues, contrast, and saturation of the output palette."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  themectl generate --image ~/Pictures/wall.png\n"
            "  themectl generate --image ~/Pictures/wall.png --harmony triadic --contrast high\n"
            "  themectl generate --image ~/Pictures/wall.png --seed-hue 220 --harmony complementary\n"
            "  themectl generate --image ~/Pictures/wall.png --pastel 0.7 --saturation 0.9\n"
        ),
    )
    p.add_argument("--image", required=True, help="Input image path used for extraction.")
    p.add_argument("--id", default="", help="Theme id override (normalized slug from image name if omitted).")
    p.add_argument(
        "--variant",
        choices=VARIANTS,
        default="auto",
        help="Palette variant: dark/light, or auto from image luminance.",
    )
    p.add_argument(
        "--backend",
        choices=EXTRACTOR_BACKENDS,
        default="perceptual",
        help=(
            "Extractor backend:\n"
            "  wal = ImageMagick-compatible extraction\n"
            "  perceptual = clustering + color science mapping"
        ),
    )
    p.add_argument(
        "--palette-model",
        choices=PALETTE_MODELS + ["auto"],
        default="catppuccin26",
        help=(
            "Output palette format:\n"
            "  catppuccin26 = semantic desktop roles\n"
            "  base16/base24 = indexed baseXX format\n"
            "  ansi16 = terminal color0..15\n"
            "  auto = choose from image metrics"
        ),
    )
    p.add_argument(
        "--harmony",
        choices=HARMONY_MODES + ["auto"],
        default="analogous",
        help=(
            "Accent hue family strategy:\n"
            "  complementary/analogous/monochromatic/split/triadic/tetrad/square\n"
            "  auto = choose from image hue distribution"
        ),
    )
    p.add_argument(
        "--harmony-anchor",
        choices=HARMONY_ANCHORS,
        default="auto",
        help=(
            "How anchor hue is selected (when seed-hue=auto):\n"
            "  dominant = highest-population chromatic cluster\n"
            "  accent = highest salience chromatic cluster\n"
            "  auto = weighted salience/population heuristic"
        ),
    )
    p.add_argument(
        "--harmony-spread",
        default="30.0",
        help="Harmony spread in degrees (0..90). Higher values widen accent hue separation where applicable.",
    )
    p.add_argument(
        "--contrast",
        choices=CONTRASTS + ["auto"],
        default="balanced",
        help="Readability profile for foreground/background and accent contrast: low, balanced, high, or auto.",
    )
    p.add_argument(
        "--pastel",
        default="0.35",
        help="Pastel amount (0..1): 0 keeps accents vivid; 1 makes accents softer/pastel-like.",
    )
    p.add_argument(
        "--terminal-opacity",
        default="0.8",
        help="Terminal background opacity target (0.0001..1.0) used in dark-mode readability checks.",
    )
    p.add_argument(
        "--terminal-bg",
        choices=TERMINAL_BG_MODES,
        default="auto",
        help=(
            "Terminal background strategy:\n"
            "  auto = infer dark/light from image luminance\n"
            "  dark = force dark terminal background semantics\n"
            "  color = use a muted accent-tinted terminal background\n"
            "  light = force light terminal background semantics"
        ),
    )
    p.add_argument(
        "--saturation",
        default="1.0",
        help="Accent chroma multiplier (0..2). >1 increases vividness, <1 mutes accents.",
    )
    p.add_argument(
        "--lightness-bias",
        default="0.0",
        help="Global lightness shift (-0.25..0.25). Positive is lighter, negative is darker.",
    )
    p.add_argument(
        "--neutral-warmth",
        default="0.0",
        help="Warm/cool bias for near-neutrals (-1..1). Positive warms, negative cools.",
    )
    p.add_argument(
        "--accent-count",
        default="14",
        help="Desired number of accent roles to preserve/synthesize (6..14).",
    )
    p.add_argument(
        "--seed-hue",
        default="auto",
        help=(
            "Anchor hue seed in degrees (0..359.999), or auto.\n"
            "Sets the hue center that harmony targets orbit around."
        ),
    )
    p.add_argument(
        "--colorblind-safe",
        choices=COLORBLIND_SAFE_MODES + ["auto"],
        default="off",
        help="Apply colorblind distinction constraints: off/deuteranopia/protanopia/tritanopia, or auto.",
    )
    p.add_argument(
        "--role-distinction",
        choices=ROLE_DISTINCTIONS + ["auto"],
        default="balanced",
        help="Strength of semantic-role separation (low/balanced/high), or auto from image complexity.",
    )
    p.add_argument(
        "--noise-filter",
        choices=NOISE_FILTERS + ["auto"],
        default="medium",
        help="Cluster filtering level: low keeps more minor colors; high removes more extraction noise.",
    )
    return p.parse_args(argv)
