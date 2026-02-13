## Summary

- Fix Unrealized "View Position" Related tab scoping for profit-only positions (Remaining Basis = $0): anchor to latest non-adjustment checkpoint (purchase/session) instead of earliest-ever purchase.
- Keep Related scoped to position basis window when Remaining Basis > $0.
- Improve Related sessions filtering to use `end_date` when present so sessions spanning midnight still appear when anchored to a checkpoint date.

## Why

Profit-only Unrealized positions can exist after FIFO consumes all basis. In these cases, the position start date falls back to earliest purchase date, which causes Related to show a lifetime history rather than the activity that explains the current balance.

## Changes

- repositories/unrealized_position_repository.py
  - Add `get_related_anchor_date(...)` and allow `_get_latest_checkpoint(..., include_balance_checkpoints=...)`.
- app_facade.py
  - Add `get_unrealized_related_anchor_date(...)` used by UI.
  - Filter related sessions by `COALESCE(end_date, session_date)` when a start_date is provided.
- ui/tabs/unrealized_tab.py
  - Use related anchor date when loading purchases/sessions for the dialog.
- tests
  - Add regression test covering profit-only anchor behavior and midnight-spanning sessions.

## Test Plan

- `pytest -q`

## Pitfalls / Follow-ups

- Related currently shows only purchases and sessions; profit-only positions anchored to a checkpoint may legitimately show very few purchases. Consider adding a Related section for balance checkpoint adjustments if you want that explicitly visible.
