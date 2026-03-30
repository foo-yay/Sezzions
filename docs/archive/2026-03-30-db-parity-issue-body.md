### Problem / Motivation

The hosted Postgres schema (persistence.py) is missing several columns and tables that exist in the desktop SQLite schema (database.py). This creates drift between the two platforms and will cause issues as more features are built on the hosted side.

### Proposal

Bring the hosted schema to full parity with the desktop schema by adding missing columns, tables, and constraints.

### Scope

#### 1. Add created_at / updated_at to all hosted domain tables (16 tables)

The following tables are missing timestamp columns:
- hosted_users, hosted_sites, hosted_cards, hosted_redemption_method_types
- hosted_redemption_methods, hosted_game_types, hosted_games, hosted_purchases
- hosted_unrealized_positions, hosted_redemptions, hosted_game_sessions, hosted_expenses
- hosted_realized_transactions, hosted_account_adjustments, hosted_daily_sessions, hosted_daily_date_tax

#### 2. Add missing column to hosted_purchases

- `starting_redeemable_balance` (String, default "0.00") -- exists in desktop via migration

#### 3. Add missing tables

- `hosted_audit_log` -- compliance trail for undo/redo and change history
- `hosted_settings` -- key-value store for accounting TZ, report prefs, etc.
- `hosted_accounting_time_zone_history` -- effective-dated TZ change history

#### 4. Add CHECK constraints (optional, lower priority)

- `hosted_game_session_event_links.event_type` CHECK IN ('purchase', 'redemption')
- `hosted_game_session_event_links.relation` CHECK IN ('BEFORE', 'DURING', 'AFTER', 'MANUAL')
- `hosted_account_adjustments.type` CHECK IN ('BASIS_USD_CORRECTION', 'BALANCE_CHECKPOINT_CORRECTION')

#### 5. Wire up auto-migration for existing live Postgres

Extend `_ensure_hosted_schema_compatibility()` to ALTER existing tables and add missing columns on startup (idempotent).

### Out of Scope

- API endpoints for new tables (separate issue)
- Undo/redo service implementation (separate issue)
- Desktop-to-hosted data sync/import improvements

### Acceptance Criteria

- [ ] All 16 domain tables have created_at (server_default=now()) and updated_at columns
- [ ] hosted_purchases has starting_redeemable_balance column
- [ ] hosted_audit_log, hosted_settings, hosted_accounting_time_zone_history tables exist
- [ ] Auto-migration adds missing columns to existing live Postgres tables on deploy
- [ ] All desktop tests pass (1159+)
- [ ] Schema parity test validates hosted schema matches desktop FK and column expectations

### Test Plan

- Unit test: verify new ORM models can be instantiated and persisted (in-memory SQLite via SQLAlchemy)
- Schema parity test: compare desktop CREATE TABLE columns against hosted ORM model columns
- Integration: deploy to Render staging, verify auto-migration runs without errors
