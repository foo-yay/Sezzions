## Summary
Implements Issue #174 by adding one-command release automation for Sezzions update publishing.

## What changed
- Added `tools/release_update.py`:
  - semantic version validation (`X.Y.Z`, optional `v` prefix),
  - macOS arm64 build via PyInstaller,
  - app bundle zip packaging,
  - SHA-256 generation,
  - `latest.json` generation,
  - create/upload release assets to `foo-yay/sezzions-updates`,
  - optional source release creation,
  - dry-run mode and existing-asset mode.
- Added tests: `tests/unit/test_release_update_tool.py`.
- Updated docs:
  - `tools/README.md` usage examples,
  - `docs/PROJECT_SPEC.md` release automation contract,
  - `docs/status/CHANGELOG.md` entry `2026-03-12-08`.
- Updated `.gitignore` for build/release artifacts (`build/`, `dist/`, `release/`, `*.spec`).

## Validation
- `pytest -q tests/unit/test_release_update_tool.py tests/unit/test_update_service.py tests/unit/test_app_update_facade.py tests/ui/test_update_ui.py`
- `python3 tools/release_update.py --version 1.0.1 --dry-run`

## Manual usage (future releases)
- `python3 tools/release_update.py --version 1.0.1`
- Optional source release tag creation:
  - `python3 tools/release_update.py --version 1.0.1 --publish-source-release`

Closes #174
