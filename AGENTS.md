# Sezzions — Agent / AI Working Agreement

This file defines how humans and AI agents should work in this repository.

## Product Rule

- **Sezzions is the product.** The primary entrypoint is `python3 sezzions.py`.
- `.LEGACY/` is reference-only and should not drive day-to-day decisions.

## Code Rules

- UI (`ui/`) calls services (`services/`), not repositories (`repositories/`) directly.
- Business rules live in services.
- Keep behavior changes intentional: prefer tests that assert business outputs.

## Documentation Rules

- Treat `docs/PROJECT_SPEC.md` as the build-from-scratch master spec.
- Update canonical docs rather than creating new scattered markdown.
- If you create a new file, it must be either:
  - an ADR in `docs/adr/`,
  - a status update in `docs/status/`,
  - or an archived snapshot in `docs/archive/`.

- For noteworthy changes, add an entry to `docs/status/CHANGELOG.md`.
- Optional: maintain an offline mirror queue in `docs/TODO.md` (GitHub Issues are the primary tracker).

## Required Workflow (Do Not Deviate)

1. Pick work from a GitHub Issue (preferred) or `docs/TODO.md` (offline mirror).
2. Implement in code following layering rules.
3. Update/add tests for intended semantics.
4. Update `docs/PROJECT_SPEC.md` if behavior/architecture/workflows changed.
5. Add a changelog entry in `docs/status/CHANGELOG.md` for noteworthy changes.
6. Commit changes to a feature branch, push, and open a PR (Draft by default unless the owner requests otherwise).
7. Move completed work to "Ready for Review" and wait for owner approval.
8. After approval/merge, close the Issue (and only then update/remove any related TODO mirror item) and ensure changelog/spec are updated.

## Issues (Templates)

- When creating or drafting Issues, use the repository Issue templates:
  - Feature: `.github/ISSUE_TEMPLATE/feature_request.yml`
  - Bug: `.github/ISSUE_TEMPLATE/bug_report.yml`
- If an agent cannot create the Issue directly, it should still draft the Issue text to match the template sections (problem, proposal, scope, acceptance criteria, test plan, etc.) so the owner can paste it with minimal editing.

## Approval Gate (Owner Review)

- Do not mark/remove TODO items as done without explicit project owner approval.
- Use `docs/TODO.md` → "Ready for Review" as the handoff point.
- "Ready for Review" means: PR is open (or changeset is otherwise shareable), core checks/tests are run where applicable, and it's waiting on owner review/approval.
- During interactive troubleshooting (font tweaks, minor UI fixes, error chasing), you do not need a new TODO for each micro-adjustment; treat it as part of the same parent TODO until approved.

## Ad-hoc Requests (Allowed, But Must Be Recorded)

Sometimes the project owner will give a direct verbal instruction (not sourced from `docs/TODO.md`). This is allowed, but it must still follow the documentation contract:

- **If the work is non-trivial or takes >15 minutes:** create a TODO item first, then proceed.
- **If the work is small/urgent:** proceed directly, but you must still:
  1. Add a changelog entry in `docs/status/CHANGELOG.md`.
  2. Update `docs/PROJECT_SPEC.md` if behavior/architecture/workflows changed.
  3. Do not create new random markdown files.

## Rollback / Undo Protocol

If asked to undo/revert work:
- Prefer creating a TODO item: "Rollback X".
- Do **not** delete prior changelog entries; add a new entry describing the rollback and what was reverted.
- Ensure the working set is consistent (tests pass; TODO reflects the current truth).

See [docs/adr/0001-docs-governance.md](docs/adr/0001-docs-governance.md).

## Testing Rules

- Tests should reflect Sezzions’ current semantics.
- Do not change core accounting logic just to satisfy an old test expectation.
- For accounting changes: add a small, explicit “golden scenario” test first.

## Legacy Rule

- Avoid editing `.LEGACY/` unless explicitly requested.
