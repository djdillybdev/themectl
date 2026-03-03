# Troubleshooting

## Apply Issues

- Verify palette exists:

```bash
./themectl theme list
```

- Isolate render from reload:

```bash
./themectl theme apply <theme_id> --dry-run --no-reload
```

- Narrow reload scope:

```bash
./themectl theme apply <theme_id> --reload-targets i3 --reload-mode sync
```

## Generate Issues

- In non-interactive mode, `generate` requires `--image`.
- For interactive image selection without `--image`, configure:

```bash
./themectl config set wallpapers_dir <path>
```

- Ensure configured `wallpapers_dir` exists and contains image files.
- If selector preview is blank, install `chafa` or use kitty with `kitty +kitten icat` support.
- Verify optional deps for perceptual backend: `Pillow`, `numpy`, `scikit-learn`.
- If perceptual deps are unavailable, try `--backend wal`.

## VS Code Target

- The `vscode` target expects this marker block in settings:
  - `// THEMECTL START`
  - `// THEMECTL END`
- Supported default paths:
  - `~/.config/Code/User/settings.json`
  - `~/.config/Code - OSS/User/settings.json`
- Override with:
  - `THEMECTL_VSCODE_SETTINGS_PATH=/abs/path/to/settings.json`

## Preview Diagnostics

- Set `THEMECTL_PREVIEW_TRANSFER_MODE=stream|memory|detect` before running `themectl`.
- Set `THEMECTL_PREVIEW_DEBUG=1` and inspect `~/.config/themectl/.cache/preview-debug.log`.
