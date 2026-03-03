# Performance Notes

## Apply Path

Use dry-run and narrow targets to isolate rendering overhead:

```bash
./themectl theme apply mocha --targets i3 --dry-run --no-reload
./themectl theme apply mocha --dry-run --no-reload
```

## Generate Path

Use explicit backend/model flags for repeatable generation runs:

```bash
./themectl generate --image /path/to/image --backend perceptual --palette-model catppuccin26 --no-apply
```
