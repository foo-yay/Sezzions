# Sezzions Tools

Utilities for maintenance, validation, and testing that run outside the main application.

Note: These scripts live in `tools/`. The in-app Tools functionality is implemented under `services/tools/` and is invoked by the UI.

## Supported Utilities

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
