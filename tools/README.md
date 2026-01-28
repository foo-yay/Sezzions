# Sezzions Tools

Utilities for maintenance, validation, and testing that run outside the main application.

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

## Archive

The `tools/archive/` folder contains historical scripts used during development phases. These are **not maintained** and are preserved only for reference.

## Adding New Tools

When adding a new utility:
1. Add it to this directory with clear docstring/usage
2. Update this README with usage instructions
3. Add a changelog entry in `docs/status/CHANGELOG.md`
