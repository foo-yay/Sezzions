# CRITICAL: Game Session P/L Calculation is WRONG

## Problem
The current GameSession implementation uses a **simplified, incorrect** P/L formula:

```python
# CURRENT (WRONG):
profit_loss = (redemptions + ending) - (starting + purchases)
```

## Correct Formula (From Legacy App)
```python
net_taxable_pl = ((discoverable_sc + delta_play_sc) * sc_rate) - basis_consumed
```

**Where:**
- `discoverable_sc` = max(0, starting_redeemable - expected_start_redeemable)
- `delta_play_sc` = ending_redeemable - starting_redeemable
- `basis_consumed` = based on locked SC processing (complex calculation)
- `expected_start_redeemable` = previous session's ending_redeemable

## Missing Fields in GameSession Model

The model needs these additional fields:
```python
starting_redeemable_sc: Decimal   # Redeemable balance at start
ending_redeemable_sc: Decimal     # Redeemable balance at end
expected_start_total_sc: Decimal  # Expected start (from prev session)
expected_start_redeemable_sc: Decimal
discoverable_sc: Decimal          # Found money
delta_total: Decimal              # Change in total balance
delta_redeem: Decimal             # Change in redeemable balance
session_basis: Decimal            # Basis added during session
basis_consumed: Decimal           # Basis consumed in session
net_taxable_pl: Decimal           # The REAL taxable P/L
```

## Why This Matters

The simple formula **completely ignores**:
1. **Redeemable vs Total SC** - Some SC is "locked" (bonus) and not taxable until unlocked
2. **Discoverable SC** - Free money that appears (promos, errors) is fully taxable
3. **Basis Consumption** - Only consume basis when redeemable balance increases
4. **Sequential Calculation** - Each session depends on previous session's ending state

## Impact

**Every P/L value shown in the Game Sessions tab is WRONG.**

Tax calculations will be completely incorrect.

## Required Fix

1. Add missing fields to GameSession model
2. Update database schema (migration)
3. Implement correct P/L algorithm in GameSessionService
4. Update UI to show redeemable balances
5. Ensure sequential processing (sessions must be calculated in chronological order)

## Reference Implementation

See `business_logic.py` lines 1100-1159 for the correct algorithm.
See `sezzions/docs/ACCOUNTING_LOGIC.md` for detailed documentation.

## DO NOT PROCEED

**Do not use the Game Sessions tab for any real data until this is fixed.**

The P/L values it displays are meaningless and will lead to incorrect tax reporting.
