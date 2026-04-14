## Summary

Phase 3c — Game Sessions Tab web port. The frontend files were developed in prior sessions; this PR commits and ships them.

## Changes

**Frontend (3 modified files):**
- `GameSessionModal.jsx` — Rewritten with 4 distinct modes:
  - **Create** (Start Session): User/Site/Date required, auto-fills expected starting balances via `/expected-balances` API, balance check display
  - **Edit** (Edit Active / Edit Closed): All fields editable, balance check, P/L preview for closed sessions
  - **Close** (Close Session): Pre-fills end date/time, ending SC/Redeemable inputs, session stats grid (read-only), wager amount, P/L preview, End & Start New button
  - **View**: Read-only detail with Edit/Close/Delete action buttons, deletion impact check
- `GameSessionsTab.jsx` — Added Active Only quick filter checkbox and Active Sessions counter metric chip
- `useEntityTable.js` — Extended `submitModal` to treat "close" mode as PATCH (not POST), and return `true`/`false` for End & Start New chaining

**Backend (already on develop):**
- Model, ORM, repo, service, 7 API endpoints — all previously shipped

## Features

- Expected balance auto-fill on create (300ms debounced)
- Always-on balance check: match / higher / lower vs expected
- P/L preview for closed sessions (delta total, discoverable SC, delta redeem, net P/L)
- End & Start New flow (close current → open pre-filled create with ending balances)
- Deletion impact check (warns if linked purchases/redemptions exist)
- 13-column table with status chips, P/L coloring, dash for Active fields

## Test Plan

- [x] `pytest`: 1342 passed, 0 failures
- [ ] Manual: Start Session, Close Session, Edit Active, Edit Closed, View, Delete, End & Start New

## Pitfalls / Follow-ups

- Travel mode badges (timezone indicator) deferred to Phase 6
- Adjusted badge on Site column deferred to adjustments infrastructure
- Auto-calc Redeemable (playthrough requirement) not yet implemented — may add later
- Timestamp collision banners ("Time adjusted to X") not yet surfaced in web UI
