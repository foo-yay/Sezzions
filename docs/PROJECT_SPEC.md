# Sezzions — Master Product & Implementation Spec

Version: 2026-01-28

This document is intended to be the **single consolidated project file** describing Sezzions end-to-end. It should be usable by a developer team (or an AI) to recreate Sezzions with high functional parity.

## 1) Product Overview

### Purpose
Sezzions is a desktop application for tracking casino sweepstakes activity with accounting-grade outputs:
- Purchases (adds basis / SC)
- Redemptions (consumes basis via FIFO, yields cashflow P/L)
- Game sessions (taxable P/L derived from gameplay / balance movements)
- Recalculation tools to keep derived data consistent
- Import/export and database safety tooling

### Primary Users
- Individual player (single operator)
- Potential future: multi-user support, multiple casinos (“sites”)

### Key Non-Goals (for now)
- Web/multi-tenant deployment
- Real-time sync
- Automated bank/casino integrations

## 2) Architecture (Current Paradigm)

### Layering
- `models/`: domain entities
- `repositories/`: database access (SQLite via `DatabaseManager`)
- `services/`: business logic and orchestration
- `ui/`: PySide6 UI; must call services, not repositories directly

Key rule: UI must not talk to the database directly.

### Primary Entrypoint
- Run the app via `python3 sezzions.py` (repo root)
- The app uses `./sezzions.db` by default, or `SEZZIONS_DB_PATH` override.

## 3) Data Model (High-Level)

SQLite database. Core tables and purpose:

- `schema_version`: schema tracking
- `users`, `sites`, `cards`: core entities
- `purchases`: basis lots; `remaining_amount` tracks unconsumed basis
- `redemptions`: cashouts; `more_remaining` differentiates closeout vs partial behavior
- `redemption_allocations`: redemption → purchase mapping (FIFO allocations)
- `realized_transactions`: derived cashflow P/L rows (rebuildable)
- `game_sessions`: derived taxable-session rows (rebuildable)
- `redemption_methods`, `games`, `game_types`: catalogs
- `audit_log`, `settings`: compliance/config

Derived invariants:
- For each purchase: `0 <= remaining_amount <= amount` (unless explicitly allowing edge-case bookkeeping)
- For each redemption: `cost_basis = sum(allocations)` and `net_pl = payout - cost_basis` (except special $0 “close balance” loss entries)

## 4) Core Accounting Semantics

### 4.1 FIFO Basis (Purchases → Redemptions)

- Purchases add basis.
- Redemptions consume basis in chronological order.
- Derived tables (`redemption_allocations`, `realized_transactions`) must be rebuildable from the authoritative purchases/redemptions.

#### Closeout vs Partial Redemption
- `more_remaining = 0` (default behavior): treat redemption as a **closeout**; consume *all remaining basis* up to timestamp.
- `more_remaining = 1`: treat redemption as **partial**; consume only the redemption amount.

This distinction is intentionally “business semantic” and must be preserved.

### 4.2 Cashflow P/L

- Cashflow P/L is primarily produced from redemptions (payout vs basis).
- Unrealized positions represent remaining basis/SC not yet realized.

### 4.3 Taxable P/L (Gameplay Sessions)

Game sessions compute taxable P/L based on redeemable vs locked balances and basis consumption rules.
This is one of the highest-risk correctness areas.

Tax-session logic is high-risk correctness territory. Any changes should be anchored by explicit scenario tests and validated via recalculation.

## 5) UI/UX (Product Behavior)

### Navigation
Main UI is a PySide6 window with primary tabs:
- Purchases
- Redemptions
- Game Sessions
- Setup (Users/Sites/Cards/etc)
- Tools

UI rules:
- UI calls services; no direct SQL in UI.
- Prefer View-first dialog flows; edits are deliberate.
- Bulk actions and destructive actions require confirmation.

## 6) Tools (Operational)

Tools are part of “production readiness”:
- CSV import/export (schema-driven)
- Backup/restore/reset
- Recalculation (full and scoped)

Helpful maintenance scripts:
- Validate schema vs spec: `python3 tools/validate_schema.py`

Status snapshots:
- [docs/status/TOOLS_DATABASE_PHASE_3_STATUS.md](status/TOOLS_DATABASE_PHASE_3_STATUS.md)
- [docs/status/TOOLS_RECALCULATION_PHASE_4_STATUS.md](status/TOOLS_RECALCULATION_PHASE_4_STATUS.md)

## 7) Testing Strategy

Tests live under `tests/` and use `pytest`.

- Run: `pytest`
- Coverage: `pytest --cov=. --cov-report=html`

Rules:
- Tests should reflect current product semantics.
- If accounting behavior is changed, it must be anchored by an explicit “golden scenario” test.

Recommended additions:
- A small set of scenario-based tests that assert final outputs (basis roll-forward, cashflow P/L, taxable P/L) for hand-computable datasets.

## 8) Development Workflow (Team + AI)

### Canonical docs
See [docs/INDEX.md](INDEX.md) and ADR [docs/adr/0001-docs-governance.md](adr/0001-docs-governance.md).

### Change control
- For non-trivial accounting changes: add/modify a golden scenario test first.
- For architectural decisions: record an ADR.
- For progress tracking: update `docs/status/STATUS.md`.

### Required Workflow (Do Not Deviate)

1. Pick work from a GitHub Issue (preferred) or from `docs/TODO.md` (offline mirror).
2. Implement changes with minimal, surgical edits.
3. Update/add tests to match intended semantics.
4. Update this spec (`docs/PROJECT_SPEC.md`) when behavior/architecture/workflows change.
5. Add a changelog entry to `docs/status/CHANGELOG.md` for noteworthy changes.
6. Open a Pull Request and request owner review.
7. After approval/merge, close the Issue (and only then update any related TODO mirror item).

### Branching & PR Policy

- Default branch (typically `main`) is the stable integration branch.
- For any non-trivial work item, use a feature branch per Issue:
  - Naming: `issue-<id>-<short-slug>` (preferred), or `bug/<slug>`, `feature/<slug>`, `chore/<slug>`.
  - Commit early and often (small, coherent commits).
  - Open a PR early (draft is fine) to get CI feedback.
- Merge via PR after CI is green and owner review is complete.
- Avoid rewriting published history (no force-push) unless explicitly coordinating a cleanup.

## 9) Legacy Relationship

Legacy code is quarantined in `.LEGACY/`.
- It is reference-only.
- Sezzions is the product under active development.

## 10) Open Questions (To Resolve Explicitly)

- Define a single authoritative reconciliation between:
  - FIFO basis/cashflow P&L (redemptions/realized/unrealized)
  - Taxable P&L (gameplay sessions)
- Lock down a minimal set of golden scenarios that “prove” correctness.
