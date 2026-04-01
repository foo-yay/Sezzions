# Copilot Instructions — Sezzions

## Primary Goal

You are assisting with **Sezzions**, a casino session tracker.

- The **web app** (React + FastAPI) is the active development surface (`web/`, `api/`).
- The **desktop app** is deprecated and lives in `desktop/` (entrypoint: `python3 desktop/sezzions.py`).
- Shared backend code lives at root: `models/`, `repositories/`, `services/`, `app_facade.py`, `tools/`.
- Desktop-only code (PyQt UI) lives in `desktop/ui/`.
- Legacy code is quarantined in `.LEGACY/` and is reference-only.

## Rules

1. Prefer minimal, surgical changes.
2. Desktop UI (`desktop/ui/`) must not talk to the database directly. Web UI talks to `api/` endpoints.
3. Preserve current app behavior unless explicitly instructed to change it.
4. For accounting changes, add or update scenario-based tests to define expected outputs.
5. **DRY / Reusability**: When implementing a pattern that already exists (or will exist for multiple entities), extract shared logic into a reusable source (utility, base class, generic component, shared hook) rather than copy-pasting per entity. Before writing new code, search the codebase for existing implementations of the same pattern. See `docs/PROJECT_SPEC.md` §2 "Design Principles" for the full doctrinal rules.
6. **Stop-and-extract enforcement**: If a change requires the same edit in 2+ files, extract the shared logic first (or file an Issue for the extraction). Do not apply the same patch to N files. See `docs/PROJECT_SPEC.md` §2 principle 6.
7. Keep docs tidy:
   - Update canonical docs in `docs/`
   - Decisions go in `docs/adr/`
   - Status updates go in `docs/status/`
   - Archive old docs in `docs/archive/`
7. Avoid documentation sprawl:
   - Prefer updating `docs/PROJECT_SPEC.md` over creating new docs
   - Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes
   - Prefer GitHub Issues for new work items

## Required Workflow (Humans + AI)

1. Start from a GitHub Issue.
2. For normal work, branch from `develop` using a feature branch (`issue-<id>-<slug>`, `feature/<slug>`, `bug/<slug>`, `chore/<slug>`).
3. Implement changes with minimal, surgical edits.
4. Update/add tests to match intended semantics.
5. Update `docs/PROJECT_SPEC.md` when behavior/architecture/workflows change.
6. Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes.
7. Push the feature branch and open a PR into `develop` (Draft by default unless the owner requests otherwise).
8. Merge `develop` into `main` only for approved release/hotfix promotion.
9. Move the item to "Ready for Review" and wait for owner approval.
10. After approval/merge, close the Issue.

Branch policy:
- `develop` is the integration/staging branch for ongoing work.
- `main` is the protected production/release branch.
- Unless the owner explicitly requests a production hotfix/release change, agents should target `develop`, not `main`.
- Production release publishing must be run from `main`.

## Agent Quality Bar (Test-First + Headless Smoke + Pitfalls)

When you are assigned a GitHub Issue (e.g., Issue #8), you must execute the work in a way that minimizes after-the-fact troubleshooting.

### 1) Mandatory Red → Green → Review

Before implementing production code changes:

1. **Translate acceptance criteria into automated tests first** (integration + unit where appropriate).
2. **Run the tests and confirm at least one fails for the intended reason** (feature not implemented yet).
3. Implement the smallest, cleanest change set to satisfy the tests.
4. Re-run tests and confirm **100% pass**.
5. Only then open/update the PR.

### 2) Torture-Test Matrix (Edge Cases + Failure Injection)

For each Issue, create a short test matrix *before* implementation:

- **Happy path(s)**: proves core feature behavior.
- **Edge cases** (at least 2): boundaries, empty DB, partial data, invalid selections.
- **Failure injection** (at least 1): force a mid-operation failure and assert rollback/invariants.
- **Invariants**: assert what must not change (e.g., “only selected tables changed”, “no partial writes”).

### 3) Headless Usability Smoke Tests (When UI is touched)

If the Issue touches UI behavior/flows:

- Add or update at least one **headless smoke test** that:
   - creates a `QApplication`,
   - instantiates the main window (`MainWindow(AppFacade(...))`),
   - processes events briefly,
   - and exits cleanly.
- Prefer running in headless mode via `QT_QPA_PLATFORM=offscreen` (or equivalent) in CI/local.

Goal: catch startup crashes, missing widgets/actions, signal/slot mismatches, and menu/dialog lifetime issues early.

### 4) Post-Implementation Pitfalls Scan (No scope creep)

After tests pass and before requesting review:

- Add a short **“Pitfalls / Follow-ups”** section in the PR description.
- Identify risks or likely next fixes discovered during implementation (performance, UX confusion, concurrency, data integrity).
- Do **not** implement follow-ups outside the Issue scope; instead propose them as:
   - a new GitHub Issue, and/or
   - a brief note in the PR description.

### 5) “No Surprise Regressions” Checklist

Before moving to “Ready for Review”:

- Run full `pytest`.
- Run headless UI smoke tests if UI was touched.
- Perform one minimal manual verification step (≤5 minutes) and note it in the PR.

## Issues (Templates)

- Prefer GitHub Issues for new work items.
- When creating or drafting Issues, use the repository templates:
   - Feature: `.github/ISSUE_TEMPLATE/feature_request.yml`
   - Bug: `.github/ISSUE_TEMPLATE/bug_report.yml`
- If you cannot create the Issue directly, draft the Issue content to match the template sections so the owner can paste it with minimal editing.

## Issue Creation (CLI Safety)

If asked to create a GitHub Issue via `gh`, do not inline a long multi-line body in the shell.

Preferred pattern:
- Write the body to a repo file (e.g. `docs/archive/<date>-issue-body.md`).
- Use `gh issue create --body-file <file>` (and `gh issue edit <n> --body-file <file>` if needed).
- Check available labels with `gh label list` before applying labels.

## Approval Gate

- "Ready for Review" means: PR is open (or changeset is otherwise shareable), relevant checks/tests have been run, and it's awaiting owner review.

## Ad-hoc Requests + Rollbacks

- Direct verbal requests are allowed, but must still be recorded.
- For non-trivial work: create a GitHub Issue first.
- For small/urgent work: proceed, but still update `docs/status/CHANGELOG.md` and update `docs/PROJECT_SPEC.md` if semantics/workflows changed.
- For rollbacks: do not delete old changelog entries; add a new changelog entry describing the rollback.

## Start Here

- Master spec: `docs/PROJECT_SPEC.md`
- Changelog: `docs/status/CHANGELOG.md`

