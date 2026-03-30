## Problem

The repository mixes desktop-only UI code (PyQt) at the root level alongside shared backend code (models, repositories, services) and the web app (web/, api/). As the desktop app is being deprecated in favor of the web version, this creates confusion about what is actively developed vs reference-only. Files like `sezzions.py`, `ui/`, `app_facade.py`, and `sezzions-macos-arm64.spec` sit at the root alongside shared code, making it unclear what belongs to which surface.

## Proposal

Reorganize the repository so desktop-only code lives in a `desktop/` subdirectory while shared backend code stays at the root:

```
/                           # root
  desktop/                  # desktop-only (deprecated, reference-only)
    ui/                     # PyQt UI code
    sezzions.py             # desktop entrypoint
    app_facade.py           # desktop facade
    sezzions-macos-arm64.spec
    resources/              # desktop icons/assets
  web/                      # React SPA (active development)
    src/
  api/                      # FastAPI endpoints (active development)
  models/                   # shared domain models
  repositories/             # shared data access
  services/                 # shared business logic
  docs/                     # canonical docs, ADRs, changelog
  tests/                    # all tests
```

Update `AGENTS.md`, `copilot-instructions.md`, and `PROJECT_SPEC.md` to reflect:
- `desktop/` is deprecated and reference-only
- Active development targets `web/` and `api/`
- Shared backend (models, repositories, services) serves both surfaces

## Scope

- Move desktop-only files/folders into `desktop/`
- Update all import paths in desktop code
- Update test paths if needed
- Update `pyproject.toml` / `pytest.ini` if paths change
- Update build spec file paths
- Update canonical docs (AGENTS.md, copilot-instructions.md, PROJECT_SPEC.md)
- Verify desktop app still launches from `python3 desktop/sezzions.py`
- Verify all tests pass

## Out of Scope

- No behavior changes to either app
- No new features
- No changes to shared backend code
- `.LEGACY/` stays where it is

## Acceptance Criteria

- [ ] Desktop-only code lives under `desktop/`
- [ ] `python3 desktop/sezzions.py` launches the desktop app
- [ ] Shared backend code (models/, repositories/, services/) remains at root
- [ ] All existing tests pass
- [ ] AGENTS.md and copilot-instructions.md updated to reflect new structure
- [ ] PROJECT_SPEC.md updated with new directory layout

## Test Plan

- Run full pytest suite and confirm no regressions
- Launch desktop app from new path
- Verify web app (npm run dev) still works
