### Problem / motivation

A submitted redemption can be returned by a site (chargeback, error, etc.), meaning the swept coins come back to the account and should remain redeemable. The app currently has no cancel/uncancel flow. Deleting the redemption is not acceptable because all downstream transactions (sessions, purchases, subsequent redemptions) were entered under the assumption the redemption had processed, so their user-entered and derived fields would become invalid.

Two previous partial implementations were attempted and abandoned because they created external `BALANCE_CHECKPOINT_CORRECTION` records that compounded under chained cancel/uncancel cycles, requiring increasingly fragile parameter cascades across 4+ layers. This issue implements a clean design from scratch.

Full design: `docs/adr/2026-02-20-redemption-cancel-uncancel-design.md`

### Proposed solution

**What:**
- Add `status` (`PENDING` | `PENDING_CANCEL` | `CANCELED`), `canceled_at`, and `cancel_reason` columns to the `redemptions` table.
- Model a CANCELED redemption as two delta events inside `compute_expected_balances`: the original `-amount` debit at `redemption_date`, and a `+amount` credit at `canceled_at`. No checkpoint records are created.
- Add `cancel_redemption` and `uncancel_redemption` to `RedemptionService`, with full FIFO reversal/re-application and audit/undo-redo logging.
- Defer cancellation when an active session exists (PENDING_CANCEL state); auto-complete on session end.

**Why:**
- No cascading recalculation of downstream records needed.
- No checkpoint records means no compounding or invalidation on repeated cycles.
- `compute_expected_balances` remains stateless and derived — no special flags required.

**Notes:**
- Canceled redemptions remain visible in the ledger, grayed out, labeled "CANCELED". Metadata fields (notes, cancel_reason) remain editable; accounting fields take effect only on uncancel. Saving an edited `amount` runs a prospective balance check (warns if the new amount would fail uncancel).
- Canceling and uncanceling are both undoable via the existing undo/redo stack.
- Unrealized tab updates automatically because it is driven by `compute_expected_balances`.

### Scope

**In-scope:**
- Schema migration (3 new columns on `redemptions`).
- Two-event delta model in `compute_expected_balances`.
- `cancel_redemption` / `uncancel_redemption` service methods with FIFO reversal + realized_transaction soft-delete.
- `PENDING_CANCEL` active-session interlock and auto-completion hook in `end_session`.
- Audit log and undo/redo integration for cancel and uncancel.
- UI: Cancel/Uncancel buttons on Redemptions tab (context-sensitive visibility).
- UI: Rename "View/Edit/Delete Session/Redemption/Purchase" buttons to "View/Edit/Delete" on all three tabs.
- UI: CANCELED row display (grayed, "CANCELED" in Receipt Dt column, non-editable).
- Notification for deferred (PENDING_CANCEL) cancellations.
- Integration + unit tests covering the full scenario matrix (see ADR Section 12).

**Out-of-scope:**
- Bulk cancel (single-record cancel only in v1).
- Retroactive modification of downstream sessions/purchases/redemptions.
- Any new `BALANCE_CHECKPOINT_CORRECTION` records created by the cancel flow.
- Canceling completed redemptions (those with a receipt date are finalized and cannot be canceled).
- Max depth limit on cancel/uncancel cycles (no limit; all cycles tracked in audit log).

### UX / fields / checkboxes

**Redemptions Tab:**
- Cancel button: visible only when exactly one row selected AND `status == 'PENDING'` AND `receipt_date IS NULL`.
- Uncancel button: visible only when exactly one row selected AND `status IN ('CANCELED', 'PENDING_CANCEL')`.
- "View/Edit/Delete Redemption" button row → rename to "View/Edit/Delete".
- CANCELED rows: grayed text; "CANCELED" shown in Receipt Dt column; accounting fields read-only in edit view; notes/cancel_reason editable. When saving a changed `amount`, the service runs a prospective capacity check (`available_redeemable at original timestamp >= new_amount`). If it fails, a **warning** is shown but the save is still permitted (user may free up balance before uncanceling). Persistent UI note: "Changes take effect when this redemption is uncanceled."
- PENDING_CANCEL rows: slightly grayed; "PENDING CANCELLATION" in Receipt Dt column.

**Game Sessions Tab:**
- "View/Edit/Delete Session" → "View/Edit/Delete".

**Purchases Tab:**
- "View/Edit/Delete Purchase" → "View/Edit/Delete".

**Cancel dialog — standard (no active session):**
- "Are you sure you want to cancel this redemption? This will reverse its FIFO allocation and return the coins to your redeemable balance."
- Optional `cancel_reason` free-text field.

**Cancel dialog — deferred (active session exists for this user/site pair):**
- Modal: "An active session is in progress for [Site]. This cancellation will be queued and will complete automatically when the session ends. Proceed?"
- On confirm: row → PENDING_CANCEL; notification created.

**Uncancel dialog:**
- No additional fields; confirmation prompt only.
- Show clear error if validation blocks (insufficient balance, FIFO conflict).

### Implementation notes / strategy

**Approach:**
The core accounting insight: instead of creating a balance checkpoint at cancellation time (which compounds on chained cancels), a CANCELED redemption contributes two delta events to the balance walk:
- `-amount` at `redemption_date/time` (original debit — always present)
- `+amount` at `canceled_at` (return credit — only when `status == 'CANCELED'`)

This makes the balance calculation stateless and correct for all cancel/uncancel combinations without any additional parameters.

**Data model / migrations:**
```sql
ALTER TABLE redemptions ADD COLUMN status TEXT NOT NULL DEFAULT 'PENDING';
ALTER TABLE redemptions ADD COLUMN canceled_at TEXT NULL;
ALTER TABLE redemptions ADD COLUMN cancel_reason TEXT NULL;
```
All existing rows get `status = 'PENDING'`, `canceled_at = NULL`. No data loss.

**Cancel eligibility:** `status == 'PENDING'` AND `receipt_date IS NULL`. Completed redemptions (receipt date set) cannot be canceled — the Cancel button is hidden. On uncancel, `receipt_date` returns to NULL.

**FIFO conflict on uncancel — two distinct scenarios:**

The conflict depends on *which* purchase lots got consumed, not simply whether other redemptions exist. FIFO is strictly chronological by purchase date:

- **R2 existed before R1 was canceled** (already downstream in the ledger while R1 was active): R2 consumed lots available *after* R1's share — R2 never touched R1's lots. Restoring R1's lots and re-running FIFO succeeds. Existing downstream redemptions do **not** block uncanceling R1. ✅

- **R2 submitted *after* R1 was canceled**: R2 had access to R1's restored lots and may have consumed them. FIFO re-run for R1 finds insufficient basis. ❌ Blocked.

Error message names the blocking redemption: *"Cannot uncancel: Redemption #N ($X, date) has consumed purchase basis needed by this redemption. Cancel it first, then retry."*

Recovery: cancel R2 → uncancel R1 (succeeds) → re-enter R2 (FIFO re-runs at R2's timestamp against remaining basis). No cascade recalculation of other records.

**Risk areas:**
- FIFO conflict check must run before any DB write — validate, then commit atomically.
- Multiple PENDING_CANCEL redemptions queued at session end must process in ascending chronological order.
- Undo of a cancel blocked by a newer redemption: reject undo gracefully; do **not** pop the stack entry.

**Phased implementation (see ADR Section 13):**
1. Schema + model (no behavior change) → all existing tests pass.
2. `compute_expected_balances` two-event delta (golden scenario tests, red → green).
3. Cancel/uncancel service methods + active-session hook.
4. AppFacade wiring + undo/redo.
5. UI changes.
6. Notifications (PENDING_CANCEL).
7. Docs + changelog.

**Files expected to change:**
`repositories/database.py`, `models/redemption.py`, `repositories/redemption_repository.py`, `repositories/realized_transaction_repository.py`, `services/redemption_service.py`, `services/game_session_service.py`, `app_facade.py`, `ui/tabs/redemptions_tab.py`, `ui/tabs/game_sessions_tab.py`, `ui/tabs/purchases_tab.py`, plus new test files.

### Acceptance criteria

- Only PENDING redemptions with no `receipt_date` can be canceled. Cancel button hidden for rows with a receipt date or non-PENDING status.
- Given a PENDING, no-receipt-date redemption R with no active session, when Cancel is confirmed, then R.status == 'CANCELED', FIFO reversed, realized_transaction soft-deleted, cost_basis/taxable_profit cleared, and `compute_expected_balances` at any time >= `canceled_at` reflects +R.amount in redeemable balance.
- Given a CANCELED redemption R with sufficient purchase basis at its original timestamp, when Uncancel is confirmed, then R.status == 'PENDING', `receipt_date` returns to NULL, FIFO re-applied, realized_transaction restored, and redeemable balance decreases by R.amount from R's original timestamp forward.
- Given a CANCELED R where a redemption submitted *after* R's cancel has consumed R's purchase basis, when Uncancel is attempted, a clear error names the blocking redemption and no DB state changes occur.
- Given insufficient redeemable balance at R's original timestamp, when Uncancel is attempted, a clear error shows the shortfall and no DB state changes occur.
- Redemptions that existed downstream of R in the ledger *before* R was canceled do not block uncanceling R.
- Given an active session on the same user/site when Cancel is clicked, a modal confirmation appears; on confirm R.status == 'PENDING_CANCEL', a notification is created, and cancellation auto-completes when the session ends.
- Editing a CANCELED redemption's amount while the prospective balance check fails shows a warning but still saves. UI note confirms changes take effect on uncancel.
- Given the full 12-step scenario in the ADR (Section 8.4), all intermediate balance checks produce the expected values.
- Cancel and uncancel both appear in the audit log and undo/redo stack; both are reversible. Undo of a blocked cancel fails gracefully without losing the stack entry.
- CANCELED rows are visible in the Redemptions tab: grayed, "CANCELED" in Receipt Dt column, Cancel button hidden, Uncancel button visible.
- "View/Edit/Delete" button labels updated on Purchases, Redemptions, and Game Sessions tabs.
- All existing tests pass after schema migration.
- `compute_expected_balances` correct for all combinations of PENDING, CANCELED, and PENDING_CANCEL redemptions.
- No `BALANCE_CHECKPOINT_CORRECTION` records created by the cancel/uncancel flow.

### Test plan

**Automated tests:**
- `tests/integration/test_redemption_cancel_uncancel.py` — full scenario matrix: happy paths, edge cases, failure injection (FIFO conflict — both blocked and unblocked scenarios, insufficient balance, active session interlock, mid-transaction rollback).
- Key scenario: cancel R1 → submit R2 (consumes R1's basis) → uncancel R1 blocked with clear message → cancel R2 → uncancel R1 succeeds → re-enter R2 with correct FIFO.
- Key scenario: cancel R1 when R2 already existed downstream → uncancel R1 succeeds (R2 not affected).
- Test that canceling a redemption with a `receipt_date` raises `ValueError`.
- Test that uncanceled redemption's `receipt_date` returns to NULL.
- Test prospective balance warning fires on edit-amount when balance is insufficient.
- `tests/integration/test_compute_expected_balances_cancel.py` — unit-level two-event delta accounting tests.
- Headless smoke: boot MainWindow with CANCELED redemption in DB; assert Cancel/Uncancel button visibility responds correctly to selection and receipt_date presence.
- Full `pytest` suite passes after each phase.

**Manual verification (owner):**
- Cancel a real PENDING redemption; verify Unrealized tab updates immediately.
- Trigger deferred cancel during active session; verify modal, PENDING CANCELLATION label, notification, auto-completion on session end.
- Undo a cancel; verify redemption reverts to PENDING with NULL receipt_date and FIFO restored.
- Confirm a row with a receipt date shows no Cancel button.
- Edit a CANCELED redemption's amount to exceed available balance; verify warning appears but save succeeds.
