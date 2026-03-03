# Repository Guidelines

- Use `uv` for this project.
- Prefer self-explanatory code over excessive comments.

## Project Structure

- `themectl`: top-level launcher.
- `themectl_py/`: Python runtime (`cli`, apply, generate, target/config/validate commands).
- `scripts/`: preview helper scripts.
- `targets.d/`: built-in target manifests and optional shell reload hooks.
- `templates/`: rendered templates by app.
- `palettes/`: built-in and generated palettes.
- `tests/`: `unittest` suite.
- `docs/`: user and contributor documentation.

## Build, Test, and Development Commands

- `./themectl help`: list CLI commands/options.
- `./themectl validate`: validate palettes, roles, and target manifests.
- `bash -n themectl scripts/*.sh targets.d/*.sh`: shell syntax checks.
- `uv run --project . python3 -m themectl_py.generate --help`: run generator module in project env.

## Coding Style and Naming

- Shell: Bash with `set -euo pipefail`; small focused functions.
- Python: deterministic behavior and schema-safe updates.
- Prefer existing file style; 2-space indentation in shell bodies where practical.
- Naming:
  - functions: `snake_case`
  - target hooks: `target_apply_<name>`, `target_reload_<name>`, `target_validate_<name>`
  - tests: `test_<behavior>`

## Testing Guidelines

- Framework: Python `unittest`.
- Add or update tests for every behavior change.
- Keep async reload logging behavior covered (dispatch + completion JSONL events).
- Generator tests may skip when optional deps (`Pillow`, `numpy`, `sklearn`) are missing.

## Commit and PR Guidelines

- Use clear imperative commit subjects (example: `picker: group preview swatches`).
- PRs should include:
  - what changed and why
  - affected commands/paths
  - test results (`unittest` output)
  - screenshots or terminal captures for picker/preview UX changes

## Security and Configuration Notes

- Do not commit personal paths or secrets from `state.json`, `config.json`, or generated metadata.
