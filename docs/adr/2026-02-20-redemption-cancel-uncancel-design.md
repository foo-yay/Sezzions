# ADR: Redemption Cancellation / Uncancellation — Full Design

**Date:** 2026-02-20  
**Status:** Proposed (awaiting owner approval before implementation)  
**Author:** GitHub Copilot (design session)

---

## 0. Context & Goals

A redeemed sweepstakes-coin balance can be returned by the site (chargeback, error, etc.).
When that happens we need to:

1. Return the coins to the redeemable balance **at the cancellation moment** (not retroactively).
2. Leave all downstream transactions (sessions, purchases, other redemptions) entered *after* the original redemption **completely undisturbed** — their user-entered fields and stored derived fields were correct at time of entry.
3. Not create a taxable event on cancel/uncancel (the "return" is just coins coming back, not a gain).
4. Track the cancellation in the audit log and undo/redo stack.
5. Allow the cancellation to be undone.
6. Handle the edge case where a session is currently active on the same user/site pair.

---

## 1. Core Accounting Insight (Why Previous Attempts Failed)

### 1.1 How `compute_expected_balances` currently works

```
expected_balance(T) =
  anchor_balance                           # latest checkpoint or session-end before T
  + Σ purchases in (anchor, T)            # purchases overwrite total; see Issue #130
  − Σ pending redemptions in (anchor, T)  # redemptions subtract as deltas
```

### 1.2 The cancellation problem

A CANCELED redemption R1 at time `T_R1` has two real-world effects:
- At `T_R1`: coins left the account             → **−R1.amount**
- At `T_cancel`: coins came back                → **+R1.amount**

These are two separate balance events at two different timestamps. The correct solution is to model **both events** inside `compute_expected_balances` rather than creating external checkpoint records.

### 1.3 Why "cancellation checkpoint" failed

Creating a `BALANCE_CHECKPOINT_CORRECTION` at `T_cancel` works for the first cancellation, but as soon as a second cancellation occurs — building on state that already included the first cancel return in its checkpoint value — the checkpoint values compound. Uncanceling then requires invalidating and recalculating all later checkpoints (a cascade). This entanglement is what made the previous implementation fragile.

### 1.4 The clean solution: two-event delta model

A CANCELED redemption contributes **two delta events** to the balance walk:

| Event | Time | Delta |
|---|---|---|
| Original redemption | `redemption_date/time` | `−amount` |
| Cancellation return | `canceled_at` | `+amount` |

A PENDING redemption contributes only the first event.

With this model:
- No new checkpoint record is ever created by the cancel flow.
- `compute_expected_balances(T)` naturally includes the return credit when `T > canceled_at`.
- Editing a record whose timestamp is between `T_R1` and `T_cancel` still sees R1 as "deducted" (correct — it hadn't been returned yet at that moment).
- Uncanceling R1 simply clears `canceled_at` — no checkpoint to hunt down and delete.

---

## 2. Schema Changes

### 2.1 `redemptions` table

Three new columns on the existing table:

```sql
ALTER TABLE redemptions ADD COLUMN status TEXT NOT NULL DEFAULT 'PENDING';
-- Values: 'PENDING' | 'CANCELED'

ALTER TABLE redemptions ADD COLUMN canceled_at TEXT NULL;
-- UTC datetime string (same format as redemption_date), set on cancel

ALTER TABLE redemptions ADD COLUMN cancel_reason TEXT NULL;
-- Free-text reason entered by user at time of cancel
```

Migration key:
- All existing rows get `status = 'PENDING'`, `canceled_at = NULL`.
- No data loss; `receipt_date` column is unchanged (it shows PENDING/date in UI as before).

### 2.2 No new tables required

The design requires no new tables. All state lives in the `redemptions` row and the existing `account_adjustments` table (for undo metadata, not for balance logic).

---

## 3. Model Changes

### 3.1 `models/redemption.py`

Add fields:

```python
status: str = "PENDING"          # "PENDING" | "CANCELED"
canceled_at: Optional[str] = None   # UTC datetime ISO string
cancel_reason: Optional[str] = None
```

Add helpers:

```python
@property
def is_canceled(self) -> bool:
    return self.status == "CANCELED"

@property
def is_pending(self) -> bool:
    return self.status == "PENDING"
```

---

## 4. `compute_expected_balances` Changes

**Location:** `services/game_session_service.py`

The redemption delta loop currently does:

```python
for r in redemptions_sorted:
    ...
    amount = Decimal(str(r.amount))
    expected_total -= amount
    expected_redeemable -= amount
```

It must become:

```python
for r in redemptions_sorted:
    r_dt = to_utc_dt(r.redemption_date, r.redemption_time, ...)

    # --- original redemption event ---
    if anchor_dt is not None and r_dt <= anchor_dt:
        pass  # absorbed in anchor
    elif r_dt < cutoff:
        expected_total -= Decimal(str(r.amount))
        expected_redeemable -= Decimal(str(r.amount))

    # --- cancellation return event (only for CANCELED redemptions) ---
    if r.is_canceled and r.canceled_at:
        cancel_dt = datetime.strptime(r.canceled_at, "%Y-%m-%d %H:%M:%S")
        if (anchor_dt is None or cancel_dt > anchor_dt) and cancel_dt < cutoff:
            expected_total += Decimal(str(r.amount))
            expected_redeemable += Decimal(str(r.amount))
```

> **Note:** `canceled_at` is stored as a UTC string. The `to_utc_dt` path is used for the original redemption event (same as before). For `cancel_dt` we parse directly since it's already UTC.

**No other parameters needed.** No `include_balance_checkpoints`, no `include_redemption_checkpoints` flags.  
The existing checkpoint path (`Priority 1` in the method) is unchanged.

---

## 5. FIFO & Realized-Transaction Behavior on Cancel

### 5.1 On CANCEL

- **Reverse the FIFO allocation** (restore `remaining_amount` on affected purchases).
  - This is required because the SC are coming back and need to be available for future redemptions.
- **Soft-delete the `realized_transactions` row** for this redemption (set `deleted_at`).
  - The redemption didn't result in a realized gain/loss — the coins came back.
- **Clear `cost_basis` and `taxable_profit`** on the `Redemption` row (set to NULL).
- Delete from `redemption_allocations`.

### 5.2 On UNCANCEL

- **Re-apply FIFO allocation** using current purchase `remaining_amount` values.
  - This may fail if subsequent redemptions consumed the original purchase lots — see Section 8 (validation).
- **Restore `realized_transactions` row** (un-soft-delete or re-insert).
- **Re-populate `cost_basis` and `taxable_profit`** on the Redemption row.
- Re-insert `redemption_allocations`.

### 5.3 Tax correctness

Canceled SC are **not taxable**. The reversal of `realized_transactions` ensures no double-counting on Schedule D. When/if the SC are eventually redeemed again (via a new redemption), a fresh realized transaction is created at that time.

---

## 6. Cancel Flow (Step by Step)

```
PRECONDITION: redemption.status == 'PENDING'

1. [Active session guard]
   If get_active_session(user_id, site_id) is not None:
       → Create a PENDING_CANCEL notification for this redemption.
       → Return to caller with status "pending_after_session".
       → The cancellation completes automatically when the session is ended
         (hook into end_session flow).

   Otherwise proceed immediately.

2. [Capacity guard — not needed for cancel]
   Cancel does not need to validate available balance.
   (Cancel always increases balance, never causes an overdraft.)

3. [FIFO reversal — in a transaction]
   a. Load redemption_allocations for this redemption.
   b. For each (purchase_id, allocated_amount): restore purchase.remaining_amount += allocated_amount.
   c. Delete rows from redemption_allocations.
   d. Soft-delete realized_transactions row (set deleted_at = now).

4. [Mark redemption CANCELED]
   UPDATE redemptions
   SET status = 'CANCELED',
       canceled_at = CURRENT_TIMESTAMP,   -- UTC
       cancel_reason = ?,
       cost_basis = NULL,
       taxable_profit = NULL,
       updated_at = CURRENT_TIMESTAMP
   WHERE id = ?

5. [Audit + undo/redo]
   log_update('redemptions', redemption_id, old_data, new_data, group_id)
   undo_redo_service.push_operation(group_id, "Cancel redemption #N ($X.XX)", timestamp)

6. [UI refresh signal]
   Emit data_change_event so Unrealized tab, Redemptions tab, and Realized tab all refresh.
```

---

## 7. Uncancel Flow (Step by Step)

```
PRECONDITION: redemption.status == 'CANCELED'

1. [Capacity validation — see Section 8 for rules]
   Compute available_redeemable at the redemption's original timestamp.
   available = compute_available_at(user_id, site_id, redemption_date, redemption_time,
                                    exclude_redemption_id=redemption_id)
   If redemption.amount > available:
       → Raise ValueError("Insufficient redeemable balance to uncancel: ...")

2. [FIFO conflict check]
   Check whether the purchases that would be allocated to this redemption (via FIFO)
   have sufficient remaining_amount to cover redemption.amount.
   If not:
       → Raise ValueError("Cannot uncancel: downstream redemptions have consumed the
                           required purchase basis. Cancel those redemptions first.")

3. [Re-apply FIFO — in a transaction]
   a. Re-run fifo_service.calculate_cost_basis(...) for this redemption.
   b. Update redemption.cost_basis, redemption.taxable_profit.
   c. Re-insert into redemption_allocations.
   d. Apply allocations to purchases (deduct remaining_amount).
   e. Re-insert or un-soft-delete realized_transactions row.

4. [Mark redemption PENDING]
   UPDATE redemptions
   SET status = 'PENDING',
       canceled_at = NULL,
       cancel_reason = NULL,
       updated_at = CURRENT_TIMESTAMP
   WHERE id = ?

5. [Audit + undo/redo]
   log_update('redemptions', redemption_id, old_data, new_data, group_id)
   undo_redo_service.push_operation(group_id, "Uncancel redemption #N ($X.XX)", timestamp)

6. [UI refresh signal]
```

---

## 8. Validation Rules

### 8.1 Cancel eligibility

| Condition | Result |
|---|---|
| status == 'PENDING' | ✅ Cancellable |
| status == 'CANCELED' | ❌ Already canceled — show "Uncancel" option instead |
| Active session on same user/site | ⚠️ Mark as PENDING_CANCEL; complete after session ends |
| Redemption has `deleted_at` set (hard deleted) | ❌ Cannot cancel a deleted record |

### 8.2 Uncancel eligibility

| Condition | Result |
|---|---|
| status == 'CANCELED' | ✅ Potentially uncancellable (subject to below checks) |
| status == 'PENDING' | ❌ Not canceled — show "Cancel" option instead |
| `available_redeemable(T_original)` < redemption.amount | ❌ Blocking: "Insufficient redeemable balance. Found $X, need $Y." |
| Subsequent PENDING (active) redemptions exist on same pair AND they consumed the required basis | ❌ Blocking: "Cancel downstream redemptions first" (see FIFO conflict check) |
| Subsequent PENDING redemptions exist but do NOT conflict with FIFO basis | ✅ Allowed — uncancel proceeds |

### 8.3 What `available_redeemable` means for uncancel check

Use the same `compute_expected_balances` at the redemption's original timestamp, passing
`exclude_redemption_id=redemption_id` so the redemption in question doesn't count against itself.

```python
_, available = game_session_service.compute_expected_balances(
    user_id, site_id,
    redemption.redemption_date,
    redemption.redemption_time or "23:59:59",
    # Note: no exclude_purchase_id here; we pass a new exclude_redemption_id
    exclude_redemption_id=redemption.id,
)
```

This requires adding `exclude_redemption_id: Optional[int] = None` to `compute_expected_balances` — analogous to the existing `exclude_purchase_id`.

### 8.4 Worked scenario from spec

```
State:
  S1 ended → ending_redeemable = $200 + $2,272.41 earned = (site-specific numbers don't matter; use symbolic)

Starting balance: $200 redeemable (simplification for illustration)

Step 1: R1 submitted for $100 → PENDING
  Balance before R1 = $200 → after = $100

Step 2: S1 active session begins (balance = $200 SC total)
  [session is open]

Step 3: R1 cancel requested
  → Active session detected → R1 marked PENDING_CANCEL; user notified

Step 4: S1 ends with ending_balance $200 SC
  → PENDING_CANCEL redemptions processed automatically
  → R1 CANCELED; FIFO reversed; balance "virtually" = $200
    (compute_expected sees: R1_debit at T1 − R1_credit at cancel_time = net $0; balance = $200)

Step 5: R2 = $200 submitted
  compute_expected at T_R2:
    anchor = S_latest_end → $200
    events: R1_debit −$100, R1_credit +$100 = net $0
    expected_redeemable = $200 ✅
  R2 PENDING; balance after = $0

Step 6: Cancel R2
  R2 CANCELED; FIFO reversed; balance re-emerges
  compute_expected at T_now: R1_net=$0, R2_debit−$200+R2_credit+$200 = $0; balance = $200 ✅

Step 7: Uncancel R1
  available_redeemable at T_R1 (excluding R1):
    anchor = S1_end → $200; events between S1 and T_R1 = none; available = $200 ≥ $100 ✅
  FIFO conflict check: R2 is CANCELED → no conflict ✅
  R1 PENDING restored
  balance = compute_expected(now): R1_debit −$100 (no cancel credit anymore), R2_debit −$200, R2_credit +$200 = $100 ✅

Step 8: Attempt R3 = $300
  compute_expected at T_R3 = $100 → R3 would need $300 → BLOCKED ✅

Step 9: Uncancel R2
  available_redeemable at T_R2 (excluding R2):
    anchor → $200; R1_debit = −$100; available = $100 < $200 → BLOCKED ✅

Step 10: Edit R2 → change amount to $100
  Now R2.amount = $100
  (R2 still CANCELED; edit of a canceled redemption changes the stored amount only)

Step 11: Uncancel R2 (after edit to $100)
  available at T_R2 = $100, R2.amount = $100 → $100 ≥ $100 ✅
  FIFO conflict: none ✅
  R2 PENDING; balance = R1_debit −$100 + R2_debit −$100 = $0 (from $200 base) ✅

Step 12: Cancel R1
  R1 CANCELED; FIFO reversed
  balance = R1_net $0 (canceled) + R2_debit −$100 + (no R2 cancel) = $200 − $100 = $100 ✅
```

---

## 9. Active Session Interlock

When a user cancels a PENDING redemption and an active session exists for that user/site:

1. **Do not block** the cancellation request from being placed.
2. **Set a `PENDING_CANCEL` intermediate state** (additional status value or a notification flag):
   - Add `status = 'PENDING_CANCEL'` as a third status value. Alternative: use a separate `pending_cancel` boolean column. The status enum approach is cleaner.
   - Revised status set: `'PENDING'` | `'PENDING_CANCEL'` | `'CANCELED'`
3. **Create a Notification** (using existing `Notification` model) with message "Redemption #N cancellation is pending — will complete when the active session ends."
4. **Hook into `end_session` flow** in `GameSessionService.update_session`:
   - After successfully closing a session, query for any `PENDING_CANCEL` redemptions on the same user/site pair.
   - Process them in order (oldest first): run the cancel flow fully.
   - Dismiss/clear the related notification.

### Why not complete immediately?

An active session has user-entered starting balance fields that were entered assuming R1 was active. Completing the cancel mid-session would not change those stored fields (they're frozen at entry time), but it would change what `compute_expected_balances` returns for the session entry form if the user is still typing — which could confuse the user. Deferring until session end is cleaner UX.

---

## 10. Undo / Redo Integration

### 10.1 Cancel is undoable

The cancel operation (and its FIFO reversal) is logged as a single `group_id` in the audit log.

Undo a cancel = run the uncancel flow (subject to the same validation rules). If validation blocks the undo (e.g., subsequent redemptions consumed the basis), the undo is rejected with a message.

### 10.2 Uncancel is undoable

Undo an uncancel = re-run the cancel flow.

### 10.3 Stack ordering

Cancel + Uncancel operations push to the undo stack exactly like Create/Update/Delete. No special handling needed beyond the existing `UndoRedoService.push_operation` call.

---

## 11. UI Changes

### 11.1 CRUD button renaming

On **Purchases**, **Redemptions**, and **Game Sessions** tabs:

| Before | After |
|---|---|
| "View/Edit/Delete Session" | "View/Edit/Delete" |
| "View/Edit/Delete Redemption" | "View/Edit/Delete" |
| "View/Edit/Delete Purchase" | "View/Edit/Delete" |

"Add Session / Add Redemption / Add Purchase" labels remain unchanged.

### 11.2 Cancel / Uncancel button visibility

A "Cancel" button appears in the Redemptions tab toolbar/action area **only when**:
- Exactly one redemption is selected, AND
- That redemption's `status == 'PENDING'`

An "Uncancel" button appears **only when**:
- Exactly one redemption is selected, AND
- That redemption's `status == 'CANCELED'` (or `'PENDING_CANCEL'`)

### 11.3 Canceled row display

- Grayed-out text color in the table row.
- "CANCELED" shown in the "Receipt Dt" column (same as current `PENDING` display).
  - PENDING → shows "PENDING"
  - CANCELED → shows "CANCELED"
  - Has receipt date → shows the date
- Row is **not editable** when status is CANCELED (edit button disabled or opens read-only view).
- Row remains visible in the list for ledger continuity.

### 11.4 Pending cancel display

- "PENDING CANCEL" in the Receipt Dt column.
- Row slightly grayed; Cancel button shows "Awaiting Session End".

### 11.5 Unrealized tab

No code changes needed. `compute_expected_balances` drives the Unrealized display. With the two-event delta model, Unrealized automatically reflects the correct balance after cancellation without any explicit refresh logic beyond the existing `data_change_event` signal.

---

## 12. Edge Cases & Stress-Test Matrix

### 12.1 Happy paths

| # | Scenario | Expected |
|---|---|---|
| H1 | Simple cancel of lone pending redemption | FIFO reversed; balance restored; Unrealized updates |
| H2 | Uncancel after simple cancel | FIFO re-applied; balance reduces; Unrealized updates |
| H3 | Cancel with active session (pending_cancel) | Deferred; auto-completes on session end |
| H4 | Cancel R1, new R2, cancel R2, uncancel R1 | All validated correctly per Section 8.4 |

### 12.2 Edge cases

| # | Scenario | Expected |
|---|---|---|
| E1 | Cancel a redemption that has no FIFO allocation (amount=0 or applied_fifo=False) | No FIFO reversal step; rest of flow normal |
| E2 | Uncancel when available_redeemable is exactly equal to redemption.amount | Allowed (≥, not >) |
| E3 | Two redemptions at identical timestamp; cancel the later one | `compute_expected_balances` uses ID ordering; cancellation return event correctly excludes self |
| E4 | Cancel then immediately uncancel (same group_id undo scenario) | Undo reverts to PENDING unchanged |
| E5 | Uncancel with `amount=0` redemption | Allowed; no-op on balance |
| E6 | Session starts between R1 and R1's cancel, then cancel | PENDING_CANCEL created; clears on session end |
| E7 | Multiple PENDING_CANCEL redemptions when session ends | Processed in chronological order of `redemption_date` |
| E8 | Cancel a `is_free_sc=True` redemption | Same flow; free SC are just returned at zero cost-basis |
| E9 | Bulk cancel (multiple selected) | Not supported in v1; cancel is single-record only |
| E10 | User tries to delete a CANCELED redemption | Allowed (delete is independent of cancel status); both cancel and delete are UI options |
| E11 | Uncancel a redemption whose `more_remaining=False` (full redemption), when partial new purchases occurred since cancel | FIFO re-calculation proceeds against current purchase remaining_amounts; if insufficient, blocked with message |
| E12 | Editing a CANCELED redemption's `amount` field | Allowed (amount change is just a metadata update while canceled); the new amount is used if later uncanceled |
| E13 | Canceling a redemption on a site with zero SC rate | No change to logic; SC rate does not affect cancel/uncancel |

### 12.3 Failure injection / invariants

| # | Scenario | Invariant to assert |
|---|---|---|
| F1 | DB fails mid-cancel (after FIFO reversed, before redemption row updated) | Transaction rolled back; redemption stays PENDING; purchase remaining_amounts unchanged |
| F2 | Uncancel validation blocks (insufficient balance) | redemption.status stays CANCELED; no FIFO re-applied; ValueError raised |
| F3 | Uncancel during active session | Should be allowed (uncancel does not require session to be inactive); only cancel is deferred |
| F4 | Undo a cancel when a newer redemption has since consumed the basis | Undo raises ValueError; undo stack entry is preserved (not popped on failure) |
| F5 | `compute_expected_balances` called with a mix of PENDING, CANCELED, PENDING_CANCEL redemptions | Each contributes the correct combination of debit/credit events; no double-counting |

### 12.4 "What-if" scenarios not in the spec

| Scenario | Verdict |
|---|---|
| Can you cancel a `PENDING_CANCEL` redemption? | No-op; it's already being canceled. Show message "Cancellation already pending." |
| Can you uncancel a `PENDING_CANCEL` redemption? | Yes — removes PENDING_CANCEL, reverts to PENDING, dismisses notification. |
| Cancel R1, receive new purchase P2, uncancel R1 — does P2 take priority in FIFO? | FIFO is run at uncancel time using current `remaining_amount` order; P2 may or may not be consumed depending on timestamps. This is correct behavior — FIFO is time-based. |
| Cancel + edit + uncancel cycle repeated 10× | No drift — each uncancel re-runs FIFO fresh; `compute_expected_balances` is stateless/derived |
| Canceling a redemption on a site that has been deactivated | No restriction; site deactivation does not prevent accounting actions |
| Cancel a redemption and then immediately run a full recalculation (`recalculation_service`) | Recalculation sees CANCELED redemption contributing two delta events; output is the same as the incremental path |

---

## 13. Implementation Plan (Ordered)

### Phase 1 — Schema + Model (no behavior change)

1. Add migration: `status`, `canceled_at`, `cancel_reason` columns to `redemptions`.
2. Update `Redemption` model with new fields and `is_canceled` / `is_pending` properties.
3. Update `RedemptionRepository` CRUD (create, update, `_row_to_model`, `get_by_user_and_site`).
4. Update `realized_transaction_repository` to support soft-delete by `redemption_id`.
5. **Tests:** all existing tests pass (new columns are nullable with defaults).

### Phase 2 — `compute_expected_balances` (core accounting)

1. Add `exclude_redemption_id: Optional[int] = None` param to `compute_expected_balances` in `GameSessionService`.
2. Update redemption delta loop to emit two events for CANCELED redemptions.
3. Update `AppFacade.compute_expected_balances` wrapper.
4. **Tests (red → green):** golden scenario tests covering the full Section 8.4 walkthrough.

### Phase 3 — Cancel / Uncancel service methods

1. Add `cancel_redemption(redemption_id, reason, group_id=None)` to `RedemptionService`.
2. Add `uncancel_redemption(redemption_id, group_id=None)` to `RedemptionService`.
3. Add `get_pending_cancel_redemptions(user_id, site_id)` to `RedemptionRepository`.
4. Hook `end_session` in `GameSessionService` to process pending-cancel redemptions.
5. Add `PENDING_CANCEL` status handling.
6. **Tests:** torture-test matrix (Sections 12.2 and 12.3).

### Phase 4 — AppFacade wiring

1. Expose `cancel_redemption` and `uncancel_redemption` through `AppFacade`.
2. Wire undo/redo actions for cancel and uncancel.

### Phase 5 — UI

1. Rename "View/Edit/Delete Session/Redemption/Purchase" → "View/Edit/Delete" in all three tabs.
2. Add Cancel/Uncancel button to Redemptions tab with visibility rules.
3. Update row renderer: gray out CANCELED rows; update "Receipt Dt" display logic.
4. Disable edit action for CANCELED rows.
5. Connect Cancel/Uncancel buttons to `AppFacade` methods.
6. **Guard Bulk Mark Received against CANCELED rows** (Gap 3): `AppFacade.bulk_update_redemption_metadata()` must skip (or raise for) any redemption with `status != 'PENDING'`. CANCELED rows visually excluded from multi-select bulk actions in the UI.
7. **CSV import exclusion**: The CSV import schema for `redemptions` explicitly excludes `status`, `canceled_at`, and `cancel_reason`. All imported redemptions default to `PENDING`.
8. **Headless smoke tests:** boot MainWindow with CANCELED redemption in DB; verify buttons appear/hide correctly.

### Phase 6 — Notifications (PENDING_CANCEL + Notification rule fix)

1. Create `Notification` entry on deferred cancel.
2. Auto-dismiss on session end.
3. Show bell count if deferred cancels are waiting.
4. **Fix notification rule query** (Gap 1): Update `notification_rules_service.py` pending-receipt rule to add `AND status = 'PENDING'` — CANCELED rows must not generate pending-receipt notifications.
5. **Dismiss existing notification on cancel** (Gap 2): In `cancel_redemption()`, after setting `status = 'CANCELED'`, call `notification_service.dismiss_by_type(type='redemption_pending_receipt', subject_id=redemption_id)` to prevent a stale pending-receipt notification remaining after a successful cancel.

### Phase 7 — Docs & Changelog

1. Update `docs/PROJECT_SPEC.md` (redemption lifecycle section).
2. Update `docs/status/CHANGELOG.md`.
3. Archive this ADR (move from proposed to accepted or superseded).

---

## 14. What We Are NOT Doing

- No deletion of canceled redemptions from the ledger (they remain for continuity).
- No retroactive modification of downstream sessions/purchases/redemptions.
- No `BALANCE_CHECKPOINT_CORRECTION` record created during cancel/uncancel. (This is the key change from the abandoned prior attempt.)
- No cascading recalculation of all subsequent records. (The two-event model makes this unnecessary.)
- No bulk cancel in v1.

---

## 15. Design Decisions (Resolved 2026-02-20)

1. **Edit while canceled — ALLOWED with prospective balance check:** Editing a CANCELED redemption is permitted. `notes` and `cancel_reason` are always editable. Accounting fields (`amount`, `redemption_date`, `site_id`, `user_id`) can be changed while canceled but have no accounting effect until the record is uncanceled. When saving a change to `amount`, the service runs the same capacity check that uncancel would: `available_redeemable at original timestamp ≥ new_amount`. If this check fails, a **warning** is shown (not a hard block, since the user may intend to free up balance before uncanceling), but the save is allowed. UI always shows a persistent note: "Changes to this record take effect when it is uncanceled."

2. **PENDING_CANCEL UX — modal confirmation:** When canceling during an active session, show a modal: "An active session is in progress for [Site]. This cancellation will be queued and will complete automatically when the session ends. Proceed?" Row shows "PENDING CANCELLATION" in the Receipt Dt column.

3. **FIFO conflict on uncancel — only redemptions submitted *after* R1's cancel can block it:** The conflict depends on *which* purchase lots got consumed, not simply whether other redemptions exist. Since FIFO is strictly chronological by purchase date:

   - **R2 existed before R1 was canceled** (R2 was downstream of R1 in the ledger while R1 was still active): R2 ran its FIFO against lots that were available *after* R1 already consumed its share. R2 never touched R1's lots. When R1 is canceled, R1's lots are restored. Uncanceling R1 re-runs FIFO and finds its original lots available — R2 is not disturbed. ✅ No conflict.

   - **R2 was submitted *after* R1 was canceled**: R2 had access to R1's now-restored lots and may have consumed them. Uncanceling R1 re-runs FIFO and finds the basis gone. ❌ Blocked.

   The mechanical FIFO check handles both cases correctly without special-casing — it simply checks whether sufficient `remaining_amount` exists across the relevant purchase lots. The error message when blocked names R2 specifically and explains it was submitted after R1's cancel. Recovery: cancel R2 → uncancel R1 (succeeds) → re-enter R2 (FIFO re-runs at R2's timestamp against remaining basis). No automatic cascade recalculation of downstream records is performed.

4. **Max depth — no limit:** Cancel/uncancel cycles are unlimited. All cycles are tracked in the audit log.

5. **Cancel eligibility and receipt date — completed redemptions are not cancellable:** Cancel is strictly for in-process (PENDING) redemptions that were reversed before receipt. A redemption with a `receipt_date` set is considered completed and cannot be canceled. The Cancel button is hidden for such rows. On uncancel, `receipt_date` returns to NULL (the redemption goes back to PENDING with no receipt date).

---

## 16. Files Expected to Change

| File | Change |
|---|---|
| `repositories/database.py` | Schema migration for `status`, `canceled_at`, `cancel_reason` |
| `models/redemption.py` | New fields + properties |
| `repositories/redemption_repository.py` | `_row_to_model`, queries, new helper |
| `repositories/realized_transaction_repository.py` | Soft-delete by `redemption_id` |
| `services/redemption_service.py` | `cancel_redemption`, `uncancel_redemption` |
| `services/game_session_service.py` | `compute_expected_balances` (2-event delta), `end_session` hook |
| `app_facade.py` | Expose cancel/uncancel, updated `compute_expected_balances` |
| `ui/tabs/redemptions_tab.py` | Buttons, row renderer, edit guard |
| `ui/tabs/game_sessions_tab.py` | Button label rename |
| `ui/tabs/purchases_tab.py` | Button label rename |
| `tests/integration/test_redemption_cancel_uncancel.py` | New — full scenario matrix |
| `tests/integration/test_compute_expected_balances_cancel.py` | New — accounting unit tests |
| `docs/PROJECT_SPEC.md` | Redemption lifecycle update |
| `docs/status/CHANGELOG.md` | Entry |
