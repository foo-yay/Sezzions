# Sezzions

Casino sweepstakes tracker with a PySide6 desktop UI and an accounting-focused backend (purchases, redemptions, FIFO basis, and session/tax reporting).

This repository is consolidated: **Sezzions is the primary app**. Legacy code is quarantined in `.LEGACY/`.

## Quick Start (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Run the app:

```bash
python3 sezzions.py
```

## Download (Latest Executables)

Direct binary downloads (public updates repo):

- macOS (Apple Silicon): https://github.com/foo-yay/sezzions-updates/releases/latest/download/sezzions-macos-arm64.zip
- Windows (x64): https://github.com/foo-yay/sezzions-updates/releases/latest/download/sezzions-windows-x64.zip

Manifest used by in-app updater:

- https://github.com/foo-yay/sezzions-updates/releases/latest/download/latest.json

## Database Location

By default, the app uses `./sezzions.db` (repo root).

Override with an environment variable:

```bash
SEZZIONS_DB_PATH=/path/to/your.db python3 sezzions.py
```

## Tests

```bash
pytest
```

Coverage (optional):

```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## Repo Layout (High Level)

- `sezzions.py`: primary application entrypoint
- `app_facade.py`: app-level wiring between UI and services
- `models/`, `repositories/`, `services/`: core backend layers
- `ui/`: PySide6 UI
- `tools/`: offline/maintenance tools
- `.LEGACY/`: frozen legacy snapshot (not maintained)

## Documentation

- [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) (canonical “what/how”)
- [docs/status/CHANGELOG.md](docs/status/CHANGELOG.md) (chronological “why/when”)
- Historical/superseded docs live in `docs/archive/`.

## Contribution Workflow (Humans + AI)

This repo uses a strict workflow to prevent documentation sprawl and keep changes reproducible.

If you are the “project owner” assigning work:
- Prefer **GitHub Issues** for tracking work (bugs, features, chores).

If you are implementing work (human or AI):
1. Start from a GitHub Issue.
2. Implement in code following layering rules (UI → services → repositories).
3. Update/add tests to match intended semantics.
4. Update **[docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md)** when behavior/architecture/workflows change.
5. Add a noteworthy entry to **[docs/status/CHANGELOG.md](docs/status/CHANGELOG.md)**.
6. Open a Pull Request and request owner review.
7. After approval/merge, close the Issue.

### Branching & PR Policy


- `develop` is the integration/staging branch for day-to-day work.
- `main` is the production/release branch.
- For any non-trivial change, work on a feature branch created from `develop`:
	- Naming: `issue-<id>-<short-slug>` (preferred), or `bug/<slug>`, `feature/<slug>`, `chore/<slug>`.
	- Make small, coherent commits as you go.
	- Open a PR early (draft is fine) into `develop` so CI runs and review can start.
- Promote `develop` to `main` only for approved releases or hotfixes.
- Release publishing workflows must be run from `main`.
- Avoid rewriting published history (no force-push) unless explicitly coordinating a cleanup.

