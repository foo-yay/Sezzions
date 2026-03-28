# Sezzions Tools

Utilities for maintenance, validation, and testing that run outside the main application.

Note: These scripts live in `tools/`. The in-app Tools functionality is implemented under `services/tools/` and is invoked by the UI.

## Supported Utilities

### Static cPanel Deploy Helper (Issue #199)
```bash
bash tools/deploy_cpanel_static.sh
```

Helper used by `.github/workflows/deploy-static-web.yml` to publish a built static site to a cPanel host over SSH with `rsync`.

Expected environment variables:
- `DEPLOY_SOURCE_DIR`
- `DEPLOY_BUILD_COMMAND` (optional)
- `CPANEL_HOST`
- `CPANEL_PORT`
- `CPANEL_USERNAME`
- `CPANEL_TARGET_PATH`
- `CPANEL_PUBLIC_URL` (optional)
- `CPANEL_SSH_PRIVATE_KEY`
- `CPANEL_SSH_KNOWN_HOSTS`

Behavior notes:
- skips cleanly when no cPanel deployment config exists yet
- fails fast if only part of the config is present
- mirrors the source directory with `rsync --delete`, so the target path must be dedicated to this app

### Release Update Automation (Issue #174)
```bash
python3 tools/release_update.py --version 1.0.1
```

Builds and publishes updater assets with a single command:
- builds macOS arm64 app artifact via PyInstaller,
- zips the app bundle,
- generates `latest.json` with SHA-256,
- uploads assets + manifest to `foo-yay/sezzions-updates` release `v<version>`.

Binary-only distribution note:
- GitHub auto-generates source archives for every release and they cannot be removed.
- For end users, share direct binary asset URLs (or app in-product updater) rather than the generic release page.

Useful options:
```bash
# Preview commands without executing
python3 tools/release_update.py --version 1.0.1 --dry-run

# Reuse existing asset zip instead of building
python3 tools/release_update.py --version 1.0.1 --asset-path /path/to/sezzions-macos-arm64.zip

# Publish both macOS + Windows assets in one release (Windows asset prebuilt)
python3 tools/release_update.py --version 1.0.1 \
	--asset-path /path/to/sezzions-macos-arm64.zip \
	--extra-asset windows-x64=/path/to/sezzions-windows-x64.zip

# Auto-increment patch from highest of local __version__ and latest published release
# (e.g. local 1.0.0 + latest release 1.0.1 -> publishes 1.0.2)
python3 tools/release_update.py --next-patch \
	--asset-path /path/to/sezzions-macos-arm64.zip \
	--extra-asset windows-x64=/path/to/sezzions-windows-x64.zip

# Verify local __version__ is not behind latest published updates release
python3 tools/release_update.py --check-version-sync

# Also create source release tag in Sezzions repo if missing
python3 tools/release_update.py --version 1.0.1 --publish-source-release

# After release publish, sync local checkout to latest main
python3 tools/release_update.py --version 1.0.1 --sync-local-main

# Sync a different branch instead of main
python3 tools/release_update.py --version 1.0.1 --sync-local-main --sync-branch release
```

Windows build note:
- PyInstaller does not reliably cross-compile Windows executables from macOS.
- Build `sezzions-windows-x64.zip` on Windows (local machine or CI runner), then pass it with `--extra-asset windows-x64=...`.

### GitHub Actions Cross-Platform Release (macOS + Windows)

Workflow file: `.github/workflows/release-binaries.yml`

What it does:
- builds macOS arm64 zip on `macos-14`,
- builds Windows x64 zip on `windows-latest`,
- publishes both assets in one release update flow,
- supports explicit version input or automatic patch bump.

Prerequisite:
- Configure repository secret `SEZZIONS_UPDATES_TOKEN` with a PAT that can create/update releases in `foo-yay/sezzions-updates`.

Canonical release guardrail:
- Development/source tags remain in `foo-yay/Sezzions`.
- Updater manifest + binary assets are published only to `foo-yay/sezzions-updates`.
- `tools/release_update.py` enforces repo separation and fails if `--updates-repo` equals source repo.

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
