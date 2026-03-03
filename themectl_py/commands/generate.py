from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..apply_native import apply_theme_native
from ..config import load_config
from ..generate import run as run_native_generator
from ..jsonio import write_json_atomic
from ..picker import fallback_select, run_fzf

REMOVED_FLAGS = {"--regen", "--force-generate", "--fallback-select", "--wallpapers-dir"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}


def run_generator(paths, args: list[str]) -> tuple[int, str, str]:
    disable_uv = os.environ.get("THEMECTL_DISABLE_UV", "").strip().lower() in {"1", "true", "yes"}
    uv_path = shutil.which("uv")
    if not disable_uv and uv_path:
        command = [uv_path, "run", "--project", str(paths.root), "python3", str(paths.root / "scripts" / "themectl_generate.py"), *args]
        try:
            uv_cache_dir = paths.cache_dir / "uv"
            uv_cache_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.setdefault("UV_CACHE_DIR", str(uv_cache_dir))
            result = subprocess.run(command, cwd=str(paths.root), env=env, check=False, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        except OSError as exc:
            print(f"WARN: failed to execute uv; falling back to native generator ({exc})", file=sys.stderr)
    return run_native_generator(args)


def has_palette_model_flag(args: list[str]) -> bool:
    for index, arg_token in enumerate(args):
        if arg_token == "--palette-model" and index + 1 < len(args):
            return True
        if arg_token.startswith("--palette-model="):
            return True
    return False


def has_harmony_flag(args: list[str]) -> bool:
    for index, arg_token in enumerate(args):
        if arg_token == "--harmony" and index + 1 < len(args):
            return True
        if arg_token.startswith("--harmony="):
            return True
    return False


def _generated_theme_id(payload: dict) -> str | None:
    theme_id = payload.get("id")
    return theme_id if isinstance(theme_id, str) and theme_id else None


def _supports_color_preview() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    if os.environ.get("FZF_PREVIEW_COLUMNS") or os.environ.get("FZF_PREVIEW_LINES"):
        return True
    colorterm = os.environ.get("COLORTERM", "")
    return bool(colorterm or "256color" in term or "truecolor" in term)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
    if not isinstance(hex_color, str) or not hex_color.startswith("#") or len(hex_color) != 7:
        return None
    try:
        return int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    except ValueError:
        return None


def print_generated_palette(payload: dict, palette_path: Path) -> None:
    print(f"Palette file: {palette_path}")
    colors = payload.get("colors")
    if not isinstance(colors, dict) or not colors:
        return

    supports_color_output = _supports_color_preview()
    print("Palette colors:")
    for color_name, color_value in colors.items():
        if not isinstance(color_name, str) or not isinstance(color_value, str):
            continue
        rgb = _hex_to_rgb(color_value)
        if supports_color_output and rgb is not None:
            red, green, blue = rgb
            swatch = f"\x1b[48;2;{red};{green};{blue}m      \x1b[0m"
            print(f"  {swatch} {color_name:<14} {color_value}")
        else:
            print(f"  {color_name:<14} {color_value}")


def _extract_image_from_flags(args: list[str]) -> str | None:
    for index, arg_token in enumerate(args):
        if arg_token == "--image" and index + 1 < len(args):
            return args[index + 1]
        if arg_token.startswith("--image="):
            return arg_token.split("=", 1)[1]
    return None


def _is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def _discover_images_from_config_dir(config_wallpapers_dir: str | None) -> tuple[list[Path], str | None]:
    if not isinstance(config_wallpapers_dir, str) or not config_wallpapers_dir.strip():
        return [], "wallpapers_dir is not configured; set it with: themectl config set wallpapers_dir <path>"

    root = Path(config_wallpapers_dir).expanduser()
    if not root.is_dir():
        return [], f"wallpapers_dir does not exist or is not a directory: {root}"

    image_paths = sorted(path for path in root.rglob("*") if _is_image_file(path))
    if not image_paths:
        return [], f"no images found in wallpapers_dir: {root}"
    return image_paths, None


def _pick_image_interactive(paths, image_paths: list[Path]) -> Path | None:
    if not image_paths:
        return None

    preview_script = paths.root / "scripts" / "themectl_image_preview.sh"
    preview_cmd = f"{preview_script} {{2}}"
    rows = [f"{path.name}\t{path}" for path in image_paths]
    selected = run_fzf(
        rows,
        prompt="image",
        preview_cmd=preview_cmd,
        delimiter="\t",
        with_nth="1",
        height="55%",
        preview_window="right:65%",
    )
    if selected:
        selected_parts = selected.split("\t", 1)
        selected_path = selected_parts[1] if len(selected_parts) > 1 else selected_parts[0]
        return Path(selected_path)

    fallback_choice = fallback_select([str(path) for path in image_paths], "Select image")
    if not fallback_choice:
        return None
    return Path(fallback_choice)


def _resolve_image_arg(paths, passthrough_args: list[str], *, is_tty_interactive: bool, config) -> tuple[list[str], str | None]:
    image_path = _extract_image_from_flags(passthrough_args)
    if image_path:
        return passthrough_args, None

    if not is_tty_interactive:
        return [], "generate requires --image <path> in non-interactive mode; run in a TTY to use the selector"

    image_paths, discover_error = _discover_images_from_config_dir(config.wallpapers_dir)
    if discover_error:
        return [], discover_error

    selected_image = _pick_image_interactive(paths, image_paths)
    if not selected_image:
        return [], "no image selected"

    return ["--image", str(selected_image), *passthrough_args], None


def _should_set_wallpaper(no_wallpaper_flag: bool, configured_enabled: bool) -> bool:
    return configured_enabled and not no_wallpaper_flag


def _set_wallpaper_for_image(image_path: str, *, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[dry-run] set wallpaper -> {image_path}")
        return
    if shutil.which("feh") is None:
        print("WARN: feh not found; skipping wallpaper set", file=sys.stderr)
        return
    return_code = subprocess.run(["feh", "--bg-fill", image_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    if return_code != 0:
        print(f"WARN: Failed to set wallpaper with feh for: {image_path}", file=sys.stderr)


def _extract_generate_flags(args: list[str]) -> tuple[list[str], bool, bool, str, str | None]:
    apply_after = True
    no_wallpaper = False
    wallpaper_mode = "after"
    passthrough: list[str] = []

    index = 0
    while index < len(args):
        arg_token = args[index]
        if arg_token == "--no-apply":
            apply_after = False
            index += 1
            continue
        if arg_token == "--apply":
            apply_after = True
            index += 1
            continue
        if arg_token == "--no-wallpaper":
            no_wallpaper = True
            index += 1
            continue
        if arg_token == "--set-wallpaper" and index + 1 < len(args):
            wallpaper_mode = args[index + 1]
            index += 2
            continue
        if arg_token.startswith("--set-wallpaper="):
            wallpaper_mode = arg_token.split("=", 1)[1]
            index += 1
            continue
        if arg_token == "--set-wallpaper":
            return [], False, False, "after", "missing value for --set-wallpaper"
        if arg_token in REMOVED_FLAGS or any(arg_token.startswith(f"{flag}=") for flag in REMOVED_FLAGS):
            return [], False, False, "after", f"flag removed: {arg_token}"
        passthrough.append(arg_token)
        index += 1

    if wallpaper_mode not in {"before", "after", "off"}:
        return [], False, False, "after", f"invalid --set-wallpaper value: {wallpaper_mode} (expected before|after|off)"
    if wallpaper_mode == "off":
        no_wallpaper = True
    return passthrough, apply_after, no_wallpaper, wallpaper_mode, None


def handle_generate_action(paths, args, *, is_tty_interactive: bool) -> int:
    rest = list(args.rest)
    if any(arg_token in {"-h", "--help"} for arg_token in rest):
        return_code, stdout_text, stderr_text = run_generator(paths, ["-h"])
        if stdout_text:
            print(stdout_text, end="" if stdout_text.endswith("\n") else "\n")
        if stderr_text:
            print(stderr_text, file=sys.stderr, end="" if stderr_text.endswith("\n") else "\n")
        return int(return_code)

    passthrough_args, apply_after, no_wallpaper, wallpaper_mode, parse_error = _extract_generate_flags(rest)
    if parse_error:
        print(f"ERROR: {parse_error}", file=sys.stderr)
        return 1

    config = load_config(paths)
    resolved_args, image_error = _resolve_image_arg(paths, passthrough_args, is_tty_interactive=is_tty_interactive, config=config)
    if image_error:
        print(f"ERROR: {image_error}", file=sys.stderr)
        return 1

    image_path = _extract_image_from_flags(resolved_args)
    if not image_path:
        print("ERROR: could not resolve image path", file=sys.stderr)
        return 1

    if wallpaper_mode == "before" and _should_set_wallpaper(no_wallpaper, config.set_wallpaper_on_image):
        _set_wallpaper_for_image(image_path, dry_run=False)

    return_code, stdout_text, stderr_text = run_generator(paths, resolved_args)
    if stderr_text:
        print(stderr_text, file=sys.stderr, end="" if stderr_text.endswith("\n") else "\n")
    if return_code != 0:
        return int(return_code)

    output_text = stdout_text.strip()
    if not output_text:
        print("ERROR: generator produced no output", file=sys.stderr)
        return 1

    try:
        payload = json.loads(output_text)
    except json.JSONDecodeError:
        print(output_text)
        print("ERROR: generator output was not JSON", file=sys.stderr)
        return 1

    theme_id = _generated_theme_id(payload)
    if not theme_id:
        print("ERROR: generated palette missing id", file=sys.stderr)
        return 1

    palette_path = paths.palettes_dir / f"{theme_id}.json"
    write_json_atomic(palette_path, payload)
    if wallpaper_mode == "after" and _should_set_wallpaper(no_wallpaper, config.set_wallpaper_on_image):
        _set_wallpaper_for_image(image_path, dry_run=False)
    print(f"Generated palette: {theme_id} ({payload.get('variant', 'unknown')})")
    print_generated_palette(payload, palette_path)

    if apply_after:
        return apply_theme_native(paths, theme_id, [], operation="generate_apply")
    return 0
