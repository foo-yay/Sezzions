# Sezzions — Agent / AI Working Agreement

This file defines how humans and AI agents should work in this repository.

## Product Rule

- **Sezzions is the product.**
- The **web app** (React SPA at `web/` + FastAPI at `api/`) is the active development surface.
- The **desktop app** is deprecated and lives in `desktop/` (entrypoint: `python3 desktop/sezzions.py`). It remains usable and serves as reference for web development.
- Shared backend code lives at root: `models/`, `repositories/`, `services/`, `app_facade.py`.
- `.LEGACY/` is reference-only and should not drive day-to-day decisions.

## Code Rules

- Desktop UI (`desktop/ui/`) calls services (`services/`), not repositories (`repositories/`) directly.
- Web UI (`web/src/`) talks to `api/` endpoints, which call `services/hosted/`.
- Business rules live in services.
- Keep behavior changes intentional: prefer tests that assert business outputs.
- **DRY / Reusability (Doctrinal)**: When two or more entities share the same structural pattern (CRUD repos, API routes, React table tabs, etc.), extract the shared logic into a reusable source — do not copy-paste and adapt per entity. Before writing new code, search the codebase for existing implementations. Shared components must have generic names (not entity-prefixed). See `docs/PROJECT_SPEC.md` §2 "Design Principles" for the full rules.
- **Stop-and-extract enforcement**: If a change requires the same edit in 2+ files, that means the shared code hasn't been extracted yet. Extract it first (or file an Issue for the extraction). Do not apply the same patch to N files. See `docs/PROJECT_SPEC.md` §2 principle 6.

## Documentation Rules

- Treat `docs/PROJECT_SPEC.md` as the build-from-scratch master spec.
- Update canonical docs rather than creating new scattered markdown.
- If you create a new file, it must be either:
  - an ADR in `docs/adr/`,
  - a status update in `docs/status/`,
  - or an archived snapshot in `docs/archive/`.

- For noteworthy changes, add an entry to `docs/status/CHANGELOG.md`.
- Work tracking is done in GitHub Issues.

## Required Workflow (Do Not Deviate)

1. Pick work from a GitHub Issue.
2. For normal work, branch from `develop` using a feature branch (`issue-<id>-<slug>`, `feature/<slug>`, `bug/<slug>`, `chore/<slug>`).
3. Implement in code following layering rules.
4. Update/add tests for intended semantics.
5. Update `docs/PROJECT_SPEC.md` if behavior/architecture/workflows changed.
6. Add a changelog entry in `docs/status/CHANGELOG.md` for noteworthy changes.
7. Push the feature branch and open a PR into `develop` (Draft by default unless the owner requests otherwise).
8. Treat `main` as production-only; merge `develop` into `main` only for approved releases or explicit hotfixes.
9. Move completed work to "Ready for Review" and wait for owner approval.
10. After approval/merge, close the Issue and ensure changelog/spec are updated.

## Branch Policy

- `develop` is the integration/staging branch.
- `main` is the production/release branch.
- Agents should default to `develop` for implementation PRs unless the owner explicitly asks for a production hotfix or release action.
- Release publishing workflows must be run from `main`.

## Issues (Templates)

- When creating or drafting Issues, use the repository Issue templates:
  - Feature: `.github/ISSUE_TEMPLATE/feature_request.yml`
  - Bug: `.github/ISSUE_TEMPLATE/bug_report.yml`
- If an agent cannot create the Issue directly, it should still draft the Issue text to match the template sections (problem, proposal, scope, acceptance criteria, test plan, etc.) so the owner can paste it with minimal editing.

### Issue Creation (Agent-Safe Process)

When an agent is asked to create a GitHub Issue via CLI, avoid passing long multi-line bodies directly on the command line (shell quoting and command substitution can corrupt the body).

Preferred workflow:

1. Draft the issue body into a repo file (temporary or archival), e.g. `docs/archive/<date>-issue-body.md`.
2. Create the issue using a body file:
  - `gh issue create --title "..." --body-file docs/archive/<file>.md --label <existing-label>`
3. If labels fail:
  - List available labels first: `gh label list`
  - Use an existing label (e.g. `bug`) or omit labels.
4. If the body is corrupted after creation:
  - Regenerate the body file and run: `gh issue edit <number> --body-file docs/archive/<file>.md`

Notes:
- Prefer ASCII-only in issue bodies when using terminal heredocs (avoid “smart quotes” and long lines if your terminal wraps aggressively).
- If the terminal session gets into a bad state (garbled output / stuck heredoc), use a fresh terminal session or write the body file via a tool/script and only use `gh ... --body-file`.

## Approval Gate (Owner Review)

- Do not close Issues or mark work as done without explicit project owner approval.
- "Ready for Review" means: PR is open (or changeset is otherwise shareable), core checks/tests are run where applicable, and it's waiting on owner review/approval.
- During interactive troubleshooting (font tweaks, minor UI fixes, error chasing), you do not need a new Issue for each micro-adjustment; treat it as part of the same parent Issue until approved.

## Ad-hoc Requests (Allowed, But Must Be Recorded)

Sometimes the project owner will give a direct verbal instruction (not sourced from a GitHub Issue). This is allowed, but it must still follow the documentation contract:

- **If the work is non-trivial or takes >15 minutes:** create a GitHub Issue first, then proceed.
- **If the work is small/urgent:** proceed directly, but you must still:
  1. Add a changelog entry in `docs/status/CHANGELOG.md`.
  2. Update `docs/PROJECT_SPEC.md` if behavior/architecture/workflows changed.
  3. Do not create new random markdown files.

## Rollback / Undo Protocol

If asked to undo/revert work:
- Prefer creating a GitHub Issue: "Rollback X".
- Do **not** delete prior changelog entries; add a new entry describing the rollback and what was reverted.
- Ensure the working set is consistent (tests pass; spec + changelog reflect the current truth).

## Testing Rules

- Tests should reflect Sezzions’ current semantics.
- Do not change core accounting logic just to satisfy an old test expectation.
- For accounting changes: add a small, explicit “golden scenario” test first.

## Agent Execution Standard (Test-First + Usability + Pitfalls)

This section exists to reduce post-PR troubleshooting (runtime issues, UI regressions, and cascading bugs).
When assigned an Issue, agents must follow these standards.

### 1) Red → Green → Review (Mandatory)

1. Convert the Issue acceptance criteria into automated tests.
2. Run the tests and confirm at least one fails for the intended reason (feature not implemented yet).
3. Implement minimal, surgical changes until tests pass.
4. Re-run the full suite and confirm **100% pass**.
5. Only then open/update the PR.

### 2) Torture-Test Matrix (Required for each Issue)

Before writing production code, document (in the PR description or issue notes) a short matrix and implement tests for it:

- Happy path(s)
- At least 2 edge cases
- At least 1 failure-injection case proving rollback/invariants
- Explicit invariants (what must not change)

Example (data tools / restore-like issues):
- “Only selected tables change”
- “Atomic rollback on any failure”
- “Audit log entries created for affected tables”

### 3) Headless Usability Smoke Tests (If UI is touched)

If an Issue touches UI flows, dialogs, menus, or threading/lifetime behavior:

- Add/update a headless smoke test that boots a `QApplication`, instantiates `MainWindow(AppFacade(...))`, processes events briefly, and exits cleanly.
- Prefer `QT_QPA_PLATFORM=offscreen` (or equivalent) so tests can run in CI/headless.

Goal: catch startup and wiring regressions early (missing menu actions, signal/slot mismatches, dialog lifetime issues).

### 4) Pitfalls / Follow-ups (No scope creep)

After implementation is complete and tests are green:

- Perform a brief “pitfalls scan”: what could break later, what is confusing, what risks remain.
- Do **not** fix items outside the Issue scope.
- Record follow-ups as new GitHub Issues.

## Legacy Rule

- Avoid editing `.LEGACY/` unless explicitly requested.
