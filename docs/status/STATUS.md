# Status (Rolling)

Last updated: 2026-01-28

## Product Goal

Make **Sezzions** the standalone, production-ready desktop app for casino sweepstakes tracking with correct accounting outputs:
- FIFO basis tracking across purchases/redemptions
- Cashflow P/L outputs (realized/unrealized)
- Taxable P/L outputs (game sessions)
- Tools (CSV import/export, backup/restore/reset, recalculation)

## Current State (High Signal)

- Primary entrypoint: `python3 sezzions.py`
- Tests: `pytest` (suite currently passing)
- Legacy: quarantined in `.LEGACY/` (not required for day-to-day development)

## Current Priorities

1. Accounting correctness confidence: add a small set of “golden scenario” tests for basis + cashflow P/L + taxable P/L.
2. UI parity and UX tightening: focus on Sezzions UI flows as the primary product.
3. Release hygiene: stable run instructions, backups, and a clear upgrade path.

## Work Rules (Team / AI)

- Sezzions behavior is the reference for tests (update tests when they drift).
- Do not change accounting semantics without an explicit “golden scenario” that defines expected outputs.
- Keep docs minimal: update canonical docs or add an ADR; archive the rest.
