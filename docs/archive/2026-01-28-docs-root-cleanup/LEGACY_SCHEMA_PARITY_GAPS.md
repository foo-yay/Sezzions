# Legacy Schema Parity Gaps (Root vs Sezzions)

This document lists schema mismatches between the legacy SQLite schema in the root **database.py** and the new Sezzions schema in **sezzions/repositories/database.py**. It is informational only and does **not** propose or apply changes.

## Summary
- The legacy schema contains several tables that do not exist in Sezzions.
- Several shared tables have different column names, missing fields, or different data types.
- Sezzions adds metadata columns (created_at/updated_at) that do not exist in legacy.

## Tables present in legacy but missing in Sezzions
- **site_sessions**
- **realized_daily_notes**
- **other_income**
- **sc_conversion_rates**
- **expenses**
- **game_rtp_aggregates**
- **game_session_event_links**

## Tables renamed in Sezzions

### daily_tax_sessions → daily_sessions

Legacy table name:
- daily_tax_sessions

Sezzions table name:
- daily_sessions

Notes:
- Schema fields are identical; only the table name changed to match standard naming.

## Shared tables with column differences

### users
Legacy columns:
- id, name, notes, active

Sezzions columns:
- id, name, email, is_active, notes, created_at, updated_at

Gaps:
- Sezzions uses is_active instead of active.
- Legacy does not include email, created_at, updated_at.

### sites
Legacy columns:
- id, name, sc_rate, notes, active

Sezzions columns:
- id, name, url, sc_rate, is_active, notes, created_at, updated_at

Gaps:
- Sezzions uses is_active instead of active.
- Legacy does not include url, created_at, updated_at.

### cards
Legacy columns:
- id, name, last_four, cashback_rate, user_id, notes, active

Sezzions columns:
- id, name, user_id, last_four, cashback_rate, is_active, notes, created_at, updated_at

Gaps:
- Sezzions uses is_active instead of active.
- Legacy does not include created_at, updated_at.

### purchases
Legacy columns:
- id, purchase_date, purchase_time, site_id, amount, sc_received, starting_sc_balance, card_id, user_id,
  remaining_amount, notes, processed, status

Sezzions columns:
- id, user_id, site_id, amount, sc_received, starting_sc_balance, cashback_earned, purchase_date,
  purchase_time, card_id, remaining_amount, notes, created_at, updated_at

Gaps:
- Legacy has processed and status; Sezzions does not.
- Sezzions has cashback_earned; legacy does not.
- Data types differ (legacy uses REAL/DATE, Sezzions uses TEXT for many monetary/time fields).
- Legacy requires card_id; Sezzions allows card_id NULL.

### redemptions
Legacy columns:
- id, site_session_id, site_id, redemption_date, redemption_time, amount, receipt_date, redemption_method_id,
  processed, is_free_sc, more_remaining, user_id, notes

Sezzions columns:
- id, user_id, site_id, amount, fees, redemption_date, redemption_time, redemption_method_id,
  is_free_sc, receipt_date, processed, more_remaining, notes, created_at, updated_at

Gaps:
- Legacy has site_session_id; Sezzions does not.
- Sezzions has fees; legacy does not.
- Data types differ (legacy uses REAL/DATE, Sezzions uses TEXT for many monetary/time fields).

### redemption_allocations
Legacy columns:
- id, redemption_id, purchase_id, allocated_amount

Sezzions columns:
- id, redemption_id, purchase_id, allocated_amount, created_at

Gaps:
- Sezzions adds created_at.
- Data type differs (legacy REAL vs Sezzions TEXT for allocated_amount).

### realized_transactions
Legacy columns:
- id, redemption_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id, notes

Sezzions columns:
- id, redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl, notes, created_at

Gaps:
- Sezzions adds created_at.
- Data type differs (legacy REAL/DATE vs Sezzions TEXT for monetary/date fields).

### game_sessions
Legacy columns (key differences only):
- session_date, start_time, end_date, end_time
- site_id, user_id, game_type, game_name, wager_amount, rtp
- starting_sc_balance, ending_sc_balance, starting_redeemable_sc, ending_redeemable_sc
- freebies_detected, processed
- session_basis, basis_consumed, expected_start_total_sc, expected_start_redeemable_sc,
  inferred_start_total_delta, inferred_start_redeemable_delta, delta_total, delta_redeem,
  net_taxable_pl, total_taxable, sc_change, dollar_value, basis_bonus, gameplay_pnl

Sezzions columns (key differences only):
- session_date, session_time, end_date, end_time
- site_id, user_id, game_id
- starting_balance, ending_balance, starting_redeemable, ending_redeemable
- purchases_during, redemptions_during
- expected_start_total, expected_start_redeemable, discoverable_sc
- delta_total, delta_redeem, session_basis, basis_consumed, net_taxable_pl, status, notes

Gaps:
- Legacy uses start_time; Sezzions uses session_time.
- Legacy uses game_type/game_name; Sezzions uses game_id.
- Legacy includes wager_amount, rtp, processed; Sezzions does not.
- Legacy includes freebies_detected; Sezzions uses discoverable_sc (naming mismatch).
- Legacy includes inferred_start_total_delta and inferred_start_redeemable_delta; Sezzions does not.
- Legacy includes total_taxable, sc_change, dollar_value, basis_bonus, gameplay_pnl; Sezzions does not.
- Sezzions includes purchases_during and redemptions_during; legacy does not.
- Data types differ (legacy REAL/DATE vs Sezzions TEXT for monetary/date fields).

### audit_log
Legacy columns:
- id, timestamp, action, table_name, record_id, details, user_name

Sezzions columns:
- id, action, table_name, record_id, details, user_name, timestamp

Gaps:
- Same fields, different order only.

## Notes
- This list is based on the current root database.py and sezzions/repositories/database.py as of this commit.
- No schema changes are applied here; this is a reference for parity tracking only.
