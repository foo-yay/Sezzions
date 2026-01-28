# Copilot Instructions — Sezzions

## Primary Goal

You are assisting with **Sezzions**, the standalone desktop app in this repository.

- Primary entrypoint: `python3 sezzions.py`
- Product code lives at repo root (`models/`, `repositories/`, `services/`, `ui/`, `tools/`).
- Legacy code is quarantined in `.LEGACY/` and is reference-only.

## Rules

1. Prefer minimal, surgical changes.
2. UI must not talk to the database directly.
3. Preserve current app behavior unless explicitly instructed to change it.
4. For accounting changes, add or update scenario-based tests to define expected outputs.
5. Keep docs tidy:
   - Update canonical docs in `docs/`
   - Decisions go in `docs/adr/`
   - Status updates go in `docs/status/`
   - Archive old docs in `docs/archive/`
6. Avoid documentation sprawl:
   - Prefer updating `docs/PROJECT_SPEC.md` over creating new docs
   - Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes
   - Prefer GitHub Issues for new work items; optionally mirror to `docs/TODO.md` for offline work

## Required Workflow (Humans + AI)

1. Start from a GitHub Issue (preferred) or `docs/TODO.md` (offline mirror).
2. Implement changes with minimal, surgical edits.
3. Update/add tests to match intended semantics.
4. Update `docs/PROJECT_SPEC.md` when behavior/architecture/workflows change.
5. Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes.
6. Move the item to "Ready for Review" and wait for owner approval.
7. After approval/merge, close the Issue (and only then update/remove any related TODO mirror item).

## Issues (Templates)

- Prefer GitHub Issues for new work items.
- When creating or drafting Issues, use the repository templates:
   - Feature: `.github/ISSUE_TEMPLATE/feature_request.yml`
   - Bug: `.github/ISSUE_TEMPLATE/bug_report.yml`
- If you cannot create the Issue directly, draft the Issue content to match the template sections so the owner can paste it with minimal editing.

## Approval Gate

- Do not mark/remove TODO items as done without explicit project owner approval.
- Use the `docs/TODO.md` "Ready for Review" section as the handoff point.

## Ad-hoc Requests + Rollbacks

- Direct verbal requests are allowed, but must still be recorded.
- For non-trivial work: add a TODO item in `docs/TODO.md` first.
- Prefer: create a GitHub Issue first, then optionally mirror to `docs/TODO.md`.
- For small/urgent work: proceed, but still update `docs/status/CHANGELOG.md` and update `docs/PROJECT_SPEC.md` if semantics/workflows changed.
- For rollbacks: do not delete old changelog entries; add a new changelog entry describing the rollback.

## Start Here

- Docs index: `docs/INDEX.md`
- Master spec: `docs/PROJECT_SPEC.md`
- Changelog: `docs/status/CHANGELOG.md`
- TODO: `docs/TODO.md`
