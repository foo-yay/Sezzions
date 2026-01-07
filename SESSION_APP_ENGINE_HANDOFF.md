
# SESSION APP – ENGINE & ACCOUNTING HANDOFF (CRITICAL)

## CURRENT STATUS (KNOWN-GOOD BASELINE)
This handoff corresponds to the CURRENT FILES PROVIDED IN THIS SESSION.
- App launches successfully
- Stake test cases are working
- UI is stable
- Gameplay P/L columns are removed from Game Sessions
- Core session-based taxable accounting mostly works

KNOWN REMAINING GAP:
- Multi-session / partial playthrough accounting (e.g. Modo, Pulsz Bingo)

---

## CORE DESIGN GOALS

1. Taxable events are SESSION-based, not redemption-based
2. Redemptions move cash only; sessions determine tax
3. Engine must fully recompute after any CRUD change

---

## KEY CONCEPTS

Total SC:
- Locked + redeemable

Redeemable SC:
- Only taxable balance

Expected Start Redeemable:
- Prior session ending redeemable
- Minus redemptions between sessions
- Boundary-inclusive (>= checkpoint)

Starting Redeemable:
- User-entered snapshot

Ending Redeemable:
- User-entered snapshot

---

## DISCOVERABLE REDEEMABLE (CRITICAL)

If starting_redeemable > expected_start_redeemable:

discoverable = starting_redeemable - expected_start_redeemable

This is taxable EVEN IF NO PLAY OCCURS.

(Stake bonus sessions depend on this.)

---

## PURCHASE BASIS MODEL

Pending Basis Pool:
- Cash spent not yet realized
- Purchases add to pool
- Carries across sessions

Basis is ONLY consumed when redeemable increases.

---

## SESSION DELTA

delta_play = ending_redeemable - starting_redeemable

---

## FINAL TARGET NET TAXABLE FORMULA

net_taxable_pl =
    discoverable
  + delta_play
  - basis_consumed

Where:

basis_consumed =
    min(pending_basis_pool, max(delta_play, 0))

This must:
- Preserve Stake bonus-only sessions
- Handle carry-in redeemable
- Fix partial playthrough
- Avoid phantom losses

---

## CURRENTLY WORKING

- Stake bonus recognition
- Redemption boundary logic
- Full playthrough sessions
- UI alignment and stability

---

## NOT YET FIXED (NEXT WORK)

Partial / multi-session playthrough:
- Modo
- Pulsz Bingo

Cause:
- Basis being consumed without redeemable increase

Fix direction:
- Persistent pending_basis_pool
- Consume basis only via delta_play

---

## DEPRECATED / DO NOT REVIVE

- gameplay_pnl
- total_gameplay_pnl
- cost-per-SC logic
- spin-based basis allocation
- basis_bonus (tax-irrelevant)

---

## FILE RESPONSIBILITIES

business_logic.py:
- All accounting logic

session2.py:
- Orchestration / recompute trigger

gui_tabs.py:
- UI only

---

## INSTRUCTIONS FOR NEXT CHATGPT SESSION

Do NOT:
- Reintroduce gameplay P/L
- Change formulas blindly

Do:
- Implement pending_basis_pool cleanly
- Validate Stake + Modo + Pulsz cases
- Keep one canonical recompute engine

This document is authoritative.
