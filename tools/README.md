# Sezzions Tools

Utilities for maintenance, validation, and testing that run outside the main application.

Note: These scripts live in `tools/`. The in-app Tools functionality is implemented under `services/tools/` and is invoked by the UI.

## Supported Utilities

### Release Update Automation (Issue #174)
```bash
python3 tools/release_update.py --version 1.0.1
```

Builds and publishes updater assets with a single command:
- builds macOS arm64 app artifact via PyInstaller,
- zips the app bundle,
- generates `latest.json` with SHA-256,
- uploads both files to `foo-yay/sezzions-updates` release `v<version>`.

Useful options:
```bash
# Preview commands without executing
python3 tools/release_update.py --version 1.0.1 --dry-run

# Reuse existing asset zip instead of building
python3 tools/release_update.py --version 1.0.1 --asset-path /path/to/sezzions-macos-arm64.zip

# Also create source release tag in Sezzions repo if missing
python3 tools/release_update.py --version 1.0.1 --publish-source-release
```

### Schema Validation
```bash
python3 tools/validate_schema.py [path/to/db]
```
Validates the database schema against the specification in `docs/PROJECT_SPEC.md`. If no path is provided, uses `./sezzions.db` or the `SEZZIONS_DB_PATH` environment variable.

### CRUD Scenario Matrix
```bash
python3 tools/run_crud_scenario_matrix.py
```
Runs comprehensive CRUD operation tests across all entity types to validate repository layer behavior.

### One-off Backfills

#### Purchase starting redeemable balance backfill
```bash
python3 tools/backfill_purchase_redeemable.py --db /path/to/sezzions.db
```
One-time maintenance script used to backfill `starting_redeemable_balance` onto historical purchases.

## Archive

The `tools/archive/` folder contains historical scripts used during development phases. These are **not maintained** and are preserved only for reference.

## Adding New Tools

When adding a new utility:
1. Add it to this directory with clear docstring/usage
2. Update this README with usage instructions
3. Add a changelog entry in `docs/status/CHANGELOG.md`
