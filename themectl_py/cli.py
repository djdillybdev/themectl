from __future__ import annotations

import argparse
import sys

from . import __version__
from .apply_native import apply_theme_native
from .commands import (
    handle_config_action,
    handle_generate_action,
    handle_target_action,
    handle_theme_action,
    handle_validate_action,
    has_harmony_flag,
    has_palette_model_flag,
    is_tty_interactive,
    pick_theme_interactive,
    print_help,
    run_generator,
    validate_all_manifests,
)
from .paths import discover_paths


def _run_generator(paths, args: list[str]) -> tuple[int, str, str]:
    return run_generator(paths, args)


def _has_palette_model_flag(args: list[str]) -> bool:
    return has_palette_model_flag(args)


def _has_harmony_flag(args: list[str]) -> bool:
    return has_harmony_flag(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    subcommands = parser.add_subparsers(dest="command")

    subcommands.add_parser("help")
    subcommands.add_parser("version")
    subcommands.add_parser("validate")

    theme = subcommands.add_parser("theme")
    theme_subcommands = theme.add_subparsers(dest="action")
    theme_subcommands.add_parser("list")
    theme_subcommands.add_parser("current")
    pick = theme_subcommands.add_parser("pick")
    pick.add_argument("--fallback-select", action="store_true")
    apply = theme_subcommands.add_parser("apply")
    apply.add_argument("theme_id", nargs="?")
    apply.add_argument("rest", nargs=argparse.REMAINDER)
    for action in ("toggle", "cycle"):
        command = theme_subcommands.add_parser(action)
        command.add_argument("rest", nargs=argparse.REMAINDER)

    config = subcommands.add_parser("config")
    config.add_argument("action", choices=["get", "set", "unset"])
    config.add_argument("key")
    config.add_argument("value", nargs="?")

    generate = subcommands.add_parser("generate")
    generate.add_argument("rest", nargs=argparse.REMAINDER)

    target = subcommands.add_parser("target")
    target_subcommands = target.add_subparsers(dest="action")
    scaffold = target_subcommands.add_parser("scaffold")
    scaffold.add_argument("name")
    test_target = target_subcommands.add_parser("test")
    test_target.add_argument("name")
    return parser


def _dispatch(paths, args: argparse.Namespace) -> int:
    if args.command == "help":
        print_help()
        return 0
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "validate":
        return handle_validate_action(paths)
    if args.command == "theme":
        manifests_valid, manifest_error = validate_all_manifests(paths)
        if not manifests_valid:
            print(f"ERROR: {manifest_error}", file=sys.stderr)
            return 1
        return handle_theme_action(paths, args)
    if args.command == "config":
        return handle_config_action(paths, args)
    if args.command == "generate":
        return handle_generate_action(paths, args, is_tty_interactive=is_tty_interactive())
    if args.command == "target":
        return handle_target_action(paths, args)

    print(f"ERROR: Unknown command: {args.command}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) == 1 and argv[0] in {"-h", "--help"}:
        print_help()
        return 0

    paths = discover_paths()

    if argv and argv[0] == "generate":
        return handle_generate_action(paths, argparse.Namespace(rest=argv[1:]), is_tty_interactive=is_tty_interactive())

    parser = _build_parser()
    if not argv:
        if is_tty_interactive():
            selected_theme_id = pick_theme_interactive(paths)
            if not selected_theme_id:
                return 1
            return apply_theme_native(paths, selected_theme_id, [], operation="pick")
        print_help()
        return 0

    parsed_args = parser.parse_args(argv)
    try:
        return _dispatch(paths, parsed_args)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
