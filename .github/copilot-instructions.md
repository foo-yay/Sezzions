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
   - Prefer GitHub Issues for new work items

## Required Workflow (Humans + AI)

1. Start from a GitHub Issue.
2. Implement changes with minimal, surgical edits.
3. Update/add tests to match intended semantics.
4. Update `docs/PROJECT_SPEC.md` when behavior/architecture/workflows change.
5. Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes.
6. Commit changes to a feature branch, push, and open a PR (Draft by default unless the owner requests otherwise).
7. Move the item to "Ready for Review" and wait for owner approval.
8. After approval/merge, close the Issue.

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

