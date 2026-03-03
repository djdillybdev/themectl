# themectl

Linux theme switching and image-based palette generation.
I was inspired to make this by pywal, and have heavily borrowed from it, as I really liked it but was not completely satisfied by the colors it generated. Generating colors from images did not always result in very readable and usable palettes. So I made themectl, which allows for quickly switching themes across your apps (I have initially set it up for i3, kitty, polybar, dunst, and rofi) and also for generating a theme from a given image. I have tried to focus on readability of text in the terminal and on a terminal with a more transparent bg (my kitty conf has opacity set to 0.8)

I did use codex to help with throwing this together. I think it came out pretty well, but it is on my todo list to refactor this later. I may simplify it to focus what exactly works, as for example the harmony option did not come out the way I wanted it to.

## Quickstart

clone and cd to directory

```bash
./themectl theme apply mocha
./themectl generate --image ~/Pictures/Wallpapers/example.jpg --apply
```

## Commands

- `./themectl help`
- `./themectl version`
- `./themectl validate`
- `./themectl theme list`
- `./themectl theme current`
- `./themectl theme apply <theme_id> [--targets csv] [--dry-run] [--no-reload] [--profile fast|full|full-parallel] [--reload-mode async|sync] [--reload-targets csv] [--transaction off|best-effort|required]`
- `./themectl theme toggle [apply flags]`
- `./themectl theme cycle [apply flags]`
- `./themectl theme pick [--fallback-select]`
- `./themectl generate [--image <path>] [style flags] [--apply|--no-apply] [--no-wallpaper] [--set-wallpaper before|after|off]`
- `./themectl target scaffold <name>`
- `./themectl target test <name>`
- `./themectl config get|set|unset wallpapers_dir`
- `./themectl config get|set|unset set_wallpaper_on_image`
- `./themectl config get|set|unset enabled_targets`

## Generate Style Flags

- `--id`
- `--variant auto|dark|light`
- `--backend wal|perceptual`
- `--palette-model catppuccin26|base16|base24|ansi16|auto`
- `--harmony complementary|analogous|monochromatic|split|triadic|tetrad|square|auto`
- `--harmony-anchor auto|dominant|accent`
- `--harmony-spread 0..90`
- `--contrast low|balanced|high|auto`
- `--pastel 0..1`
- `--terminal-opacity 0.0001..1.0`
- `--terminal-bg auto|dark|color|light`
- `--saturation 0..2`
- `--lightness-bias -0.25..0.25`
- `--neutral-warmth -1..1`
- `--accent-count 6..14`
- `--seed-hue 0..359.999`
- `--colorblind-safe off|deuteranopia|protanopia|tritanopia|auto`
- `--role-distinction low|balanced|high|auto`
- `--noise-filter low|medium|high|auto`

## Docs

- [Documentation Index](docs/README.md)
- [Quickstart](docs/quickstart.md)
- [CLI Reference](docs/cli-reference.md)
- [Config Reference](docs/config-reference.md)
- [Plugin Authoring](docs/plugin-authoring.md)
- [Contracts](docs/contracts.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Performance](docs/performance.md)

## Runtime Layout

- `themectl`: top-level launcher.
- `themectl_py/`: Python runtime and command implementations.
- `scripts/`: preview helpers.
- `targets.d/`: built-in target manifests and shell reload hooks.
- `templates/`: managed templates.
- `palettes/`: built-in and generated palettes.
