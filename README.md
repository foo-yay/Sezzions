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
- `web/`: Vite + React web frontend scaffold
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

## Staged Static Web Deploy

The repository now includes a staged static-site deployment scaffold for future web rollout:

- pushes to `develop` target the `development` GitHub environment
- pushes to `main` target the `production` GitHub environment
- deploys use `.github/workflows/deploy-static-web.yml`
- publish uses SSH + `rsync` via `tools/deploy_cpanel_static.sh`

This workflow now supports the real web frontend scaffold under `web/`. It still skips cleanly when the required environment configuration has not been added yet.

### GitHub Environment Variables

Configure these variables separately in the `development` and `production` GitHub environments:

- `DEPLOY_ENABLED`: set to `true` only after secrets and target paths are fully configured
- `CPANEL_HOST`: SSH host for the cPanel server
- `CPANEL_PORT`: SSH port, usually `22`
- `CPANEL_USERNAME`: cPanel SSH username
- `CPANEL_TARGET_PATH`: remote directory to publish into, such as `public_html/dev` or `public_html/app`
- `CPANEL_PUBLIC_URL`: public URL for the deployed site
- `DEPLOY_SOURCE_DIR`: built static site directory, for example `web/dist`
- `DEPLOY_BUILD_COMMAND`: optional build command, for example `cd web && npm ci --cache .npm-cache && npm run build`

### GitHub Environment Secrets

Configure these secrets separately in the `development` and `production` GitHub environments:

- `CPANEL_SSH_PRIVATE_KEY`: private key used by GitHub Actions to connect over SSH
- `CPANEL_SSH_KNOWN_HOSTS`: output from `ssh-keyscan` for the cPanel host/port

### What You Need To Do In cPanel

1. Create the subdomains you want to use, such as `dev.yourdomain.com` and `app.yourdomain.com`.
2. Note each subdomain's document root path. These become your `CPANEL_TARGET_PATH` values.
3. Enable SSH access for the hosting account if your plan requires support to turn it on.
4. Add and authorize an SSH key for deployment in cPanel.
5. Make sure the deploy target directories are dedicated to this app, because the workflow uses `rsync --delete`.
6. If you are using shared hosting, treat this workflow as static-site deployment only. A hosted Python API may need a separate platform unless your cPanel plan includes reliable Python app/process support.

### How To Generate Known Hosts

Run this locally after you know the SSH hostname and port:

```bash
ssh-keyscan -p 22 your-cpanel-host.example.com
```

Paste the full output into the `CPANEL_SSH_KNOWN_HOSTS` secret for the matching environment.

