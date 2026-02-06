# Sezzions Documentation Index

This repo is consolidated: **Sezzions is the product under active development**.
Legacy is quarantined in `.LEGACY/`.

## Start Here

- Product + build-from-scratch spec: [docs/PROJECT_SPEC.md](PROJECT_SPEC.md)
- How to run/install/test: [GETTING_STARTED.md](../GETTING_STARTED.md)
- Repo overview: [README.md](../README.md)
- Operator guide (HTML, navigable): [docs/Readme/index.html](Readme/index.html)

## Canonical (Keep Updated)

These are the docs we treat as “source of truth” and keep current when behavior changes:

- Product + build-from-scratch spec: [docs/PROJECT_SPEC.md](PROJECT_SPEC.md)
- Work tracking: GitHub Issues (primary) + optional offline mirror: [docs/TODO.md](TODO.md)
- Current product status (rolling): [docs/status/STATUS.md](status/STATUS.md)
- Changelog (chronological): [docs/status/CHANGELOG.md](status/CHANGELOG.md)
- Decisions (ADRs): [docs/adr/0001-docs-governance.md](adr/0001-docs-governance.md)

## Status / Progress

- Current product status (rolling): [docs/status/STATUS.md](status/STATUS.md)
- Changelog (chronological): [docs/status/CHANGELOG.md](status/CHANGELOG.md)
- Work tracking: GitHub Issues (primary) + optional offline mirror: [docs/TODO.md](TODO.md)
- Tools status (historical snapshots):
  - [docs/status/TOOLS_DATABASE_PHASE_3_STATUS.md](status/TOOLS_DATABASE_PHASE_3_STATUS.md)
  - [docs/status/TOOLS_RECALCULATION_PHASE_4_STATUS.md](status/TOOLS_RECALCULATION_PHASE_4_STATUS.md)

## Decisions (ADRs)

- Docs/workflow governance: [docs/adr/0001-docs-governance.md](adr/0001-docs-governance.md)

## Incidents / Known Issues

- Game-session P/L concern writeup: [docs/incidents/CRITICAL_P&L_ISSUE.md](incidents/CRITICAL_P&L_ISSUE.md)

When to use Incidents:
- Use GitHub Issues for actionable work items (preferred).
- Use `docs/TODO.md` only as an optional offline mirror.
- Use `docs/incidents/` for investigation writeups (repro steps, impact, hypotheses, what was tried).
- If an incident exists, the related Issue (and optionally the TODO mirror item) should link to it so humans/AI know to read it.

## Archive

Old plans, phase checklists, and “done” writeups live in `docs/archive/`.
If you’re unsure whether a doc is current, check [docs/status/STATUS.md](status/STATUS.md) and [docs/adr/0001-docs-governance.md](adr/0001-docs-governance.md).
