# ADR 0001: Documentation Governance

Date: 2026-01-28
Status: Accepted

## Context

This repo accumulated many planning/status markdown files during rapid iteration with AI assistance. It became hard to know:
- which documents are current,
- which are historical snapshots,
- and which should be used as “source of truth”.

## Decision

We adopt a **docs governance model**:

1. **Canonical docs** live in `docs/` and must be kept current when behavior changes.
2. **Status snapshots** live in `docs/status/`.
3. **Decisions** are recorded as ADRs in `docs/adr/`.
4. **Historical / superseded docs** live in `docs/archive/`.
5. Repo root stays clean: only entrypoint docs and operational basics.

Additionally:

6. **Changelog** is recorded in `docs/status/CHANGELOG.md` for chronological, human+AI readable tracking.
7. **Work tracking** is primarily done in GitHub Issues; `docs/TODO.md` may be used as an optional offline mirror.

## Canonical Docs

- `docs/PROJECT_SPEC.md` (the “DNA” build-from-scratch spec)
- `docs/INDEX.md` (docs entrypoint)
- `docs/TODO.md` (optional offline mirror)
- `docs/status/STATUS.md` (rolling status)
- `docs/status/CHANGELOG.md` (chronological change log)

## Rules

- If you’re about to create a new markdown file, first ask: “Should this be an ADR? a status update? or an edit to canonical docs?”
- Prefer **editing an existing canonical doc** over creating a new file.
- If a document becomes outdated, move it to `docs/archive/` and add a short note at the top (“Archived on YYYY-MM-DD”).
- For noteworthy changes, add an entry to `docs/status/CHANGELOG.md`.

## Required Workflow (Humans + AI)

This repo treats documentation as part of the product. Use this workflow and do not invent parallel processes.

1. **Pick work** from a GitHub Issue (preferred) or `docs/TODO.md` (offline mirror).
	- If you discover new work (bug, debt, feature), create a GitHub Issue (and optionally mirror it to `docs/TODO.md`).
2. **Implement** the change in code.
	- Preserve architecture: UI calls services; services call repositories.
3. **Update tests**.
	- If behavior changes, update/add tests so they assert the new intended semantics.
4. **Update documentation**.
	- If the change affects behavior/architecture/data model/workflows, update `docs/PROJECT_SPEC.md`.
	- If it’s a durable decision/tradeoff, add an ADR in `docs/adr/`.
5. **Record the change** in `docs/status/CHANGELOG.md` (noteworthy changes).
6. **Close the loop** via PR review + merge.
	- Close the GitHub Issue after merge.
	- If a TODO mirror item exists, update/remove it after owner approval/merge.

## Consequences

- The team always knows which docs to follow.
- Historic context is preserved without polluting the active working set.
- AI agents have clear boundaries and a stable spec surface.
