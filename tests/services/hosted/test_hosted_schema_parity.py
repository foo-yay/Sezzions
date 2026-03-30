"""Tests for hosted schema parity with desktop (Issue #236).

Verifies that all hosted ORM tables have the expected timestamp columns,
the purchases table has starting_redeemable_balance, and the three
previously-missing tables (audit_log, settings, accounting_time_zone_history)
exist with correct columns.
"""

from sqlalchemy import create_engine, inspect, text

from services.hosted.persistence import (
    HostedBase,
    _column_default_sql,
    _ensure_hosted_schema_compatibility,
    _migrate_missing_columns,
)


def _fresh_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine


# --- Timestamp columns on all domain tables --------------------------------


_TABLES_WITH_CREATED_AND_UPDATED = [
    "hosted_accounts",
    "hosted_workspaces",
    "hosted_users",
    "hosted_sites",
    "hosted_cards",
    "hosted_redemption_method_types",
    "hosted_redemption_methods",
    "hosted_game_types",
    "hosted_games",
    "hosted_purchases",
    "hosted_unrealized_positions",
    "hosted_redemptions",
    "hosted_game_sessions",
    "hosted_expenses",
    "hosted_daily_sessions",
    "hosted_daily_date_tax",
    "hosted_account_adjustments",
    "hosted_realized_daily_notes",
]


def test_all_domain_tables_have_created_at_and_updated_at():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        for table_name in _TABLES_WITH_CREATED_AND_UPDATED:
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            assert "created_at" in cols, f"{table_name} missing created_at"
            assert "updated_at" in cols, f"{table_name} missing updated_at"
    finally:
        engine.dispose()


_TABLES_WITH_CREATED_AT_ONLY = [
    "hosted_game_session_event_links",
    "hosted_redemption_allocations",
    "hosted_realized_transactions",
    "hosted_accounting_time_zone_history",
]


def test_link_tables_have_created_at():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        for table_name in _TABLES_WITH_CREATED_AT_ONLY:
            cols = {c["name"] for c in inspector.get_columns(table_name)}
            assert "created_at" in cols, f"{table_name} missing created_at"
    finally:
        engine.dispose()


# --- Missing purchase column -----------------------------------------------


def test_purchases_has_starting_redeemable_balance():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("hosted_purchases")}
        assert "starting_redeemable_balance" in cols
    finally:
        engine.dispose()


# --- New tables ------------------------------------------------------------


def test_audit_log_table_has_expected_columns():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("hosted_audit_log")}
        assert cols >= {
            "id",
            "workspace_id",
            "action",
            "table_name",
            "record_id",
            "details",
            "user_name",
            "old_data",
            "new_data",
            "group_id",
            "summary_data",
            "timestamp",
        }
    finally:
        engine.dispose()


def test_settings_table_has_expected_columns():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("hosted_settings")}
        assert cols >= {"workspace_id", "key", "value"}
    finally:
        engine.dispose()


def test_accounting_time_zone_history_table_has_expected_columns():
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("hosted_accounting_time_zone_history")}
        assert cols >= {
            "id",
            "workspace_id",
            "effective_utc_timestamp",
            "accounting_time_zone",
            "reason",
            "created_at",
        }
    finally:
        engine.dispose()


# --- Auto-migration: missing columns added to existing tables ---------------


def test_migrate_missing_columns_adds_created_at_to_existing_table():
    """Simulate an existing DB that was created before timestamps were added."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    try:
        # Create schema WITHOUT created_at/updated_at by using raw DDL
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE hosted_accounts ("
                "  id VARCHAR(36) PRIMARY KEY,"
                "  owner_email VARCHAR(255) NOT NULL,"
                "  auth_provider VARCHAR(32) NOT NULL DEFAULT 'google',"
                "  role VARCHAR(32) NOT NULL DEFAULT 'owner',"
                "  status VARCHAR(32) NOT NULL DEFAULT 'active',"
                "  supabase_user_id VARCHAR(255) NOT NULL UNIQUE"
                ")"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_workspaces ("
                "  id VARCHAR(36) PRIMARY KEY,"
                "  account_id VARCHAR(36) NOT NULL REFERENCES hosted_accounts(id),"
                "  name VARCHAR(255) NOT NULL,"
                "  source_db_path VARCHAR(1024)"
                ")"
            ))

        inspector = inspect(engine)
        # Verify columns are missing before migration
        acct_cols = {c["name"] for c in inspector.get_columns("hosted_accounts")}
        assert "created_at" not in acct_cols
        assert "updated_at" not in acct_cols

        # Run migration
        _migrate_missing_columns(engine, inspector)

        # Re-inspect after migration
        inspector = inspect(engine)
        acct_cols_after = {c["name"] for c in inspector.get_columns("hosted_accounts")}
        assert "created_at" in acct_cols_after
        assert "updated_at" in acct_cols_after

        ws_cols_after = {c["name"] for c in inspector.get_columns("hosted_workspaces")}
        assert "created_at" in ws_cols_after
        assert "updated_at" in ws_cols_after
    finally:
        engine.dispose()


def test_migrate_missing_columns_adds_starting_redeemable_balance():
    """Simulate a purchases table without starting_redeemable_balance."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    try:
        with engine.begin() as conn:
            # Minimal schema: accounts → workspaces → users → sites → purchases (without the new column)
            conn.execute(text(
                "CREATE TABLE hosted_accounts (id VARCHAR(36) PRIMARY KEY, owner_email VARCHAR(255) NOT NULL,"
                " auth_provider VARCHAR(32) DEFAULT 'google', role VARCHAR(32) DEFAULT 'owner',"
                " status VARCHAR(32) DEFAULT 'active', supabase_user_id VARCHAR(255) UNIQUE)"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_workspaces (id VARCHAR(36) PRIMARY KEY,"
                " account_id VARCHAR(36) REFERENCES hosted_accounts(id), name VARCHAR(255),"
                " source_db_path VARCHAR(1024))"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_users (id VARCHAR(36) PRIMARY KEY,"
                " workspace_id VARCHAR(36) REFERENCES hosted_workspaces(id),"
                " name VARCHAR(255), email VARCHAR(255), notes VARCHAR(1024), is_active BOOLEAN DEFAULT 1)"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_sites (id VARCHAR(36) PRIMARY KEY,"
                " workspace_id VARCHAR(36) REFERENCES hosted_workspaces(id),"
                " name VARCHAR(255), url VARCHAR(1024), sc_rate FLOAT DEFAULT 1.0,"
                " playthrough_requirement FLOAT DEFAULT 1.0, is_active BOOLEAN DEFAULT 1, notes TEXT)"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_cards (id VARCHAR(36) PRIMARY KEY,"
                " workspace_id VARCHAR(36) REFERENCES hosted_workspaces(id),"
                " user_id VARCHAR(36) REFERENCES hosted_users(id),"
                " name VARCHAR(255), last_four VARCHAR(8), cashback_rate FLOAT DEFAULT 0.0,"
                " is_active BOOLEAN DEFAULT 1, notes TEXT)"
            ))
            conn.execute(text(
                "CREATE TABLE hosted_purchases (id VARCHAR(36) PRIMARY KEY,"
                " workspace_id VARCHAR(36) REFERENCES hosted_workspaces(id),"
                " user_id VARCHAR(36) REFERENCES hosted_users(id),"
                " site_id VARCHAR(36) REFERENCES hosted_sites(id),"
                " amount VARCHAR(32), sc_received VARCHAR(32) DEFAULT '0.00',"
                " starting_sc_balance VARCHAR(32) DEFAULT '0.00',"
                " cashback_earned VARCHAR(32) DEFAULT '0.00',"
                " cashback_is_manual BOOLEAN DEFAULT 0,"
                " purchase_date VARCHAR(32), purchase_time VARCHAR(32),"
                " purchase_entry_time_zone VARCHAR(128),"
                " card_id VARCHAR(36) REFERENCES hosted_cards(id),"
                " remaining_amount VARCHAR(32), status VARCHAR(64) DEFAULT 'active',"
                " notes TEXT, deleted_at VARCHAR(64))"
            ))

        inspector = inspect(engine)
        cols_before = {c["name"] for c in inspector.get_columns("hosted_purchases")}
        assert "starting_redeemable_balance" not in cols_before

        _migrate_missing_columns(engine, inspector)

        inspector = inspect(engine)
        cols_after = {c["name"] for c in inspector.get_columns("hosted_purchases")}
        assert "starting_redeemable_balance" in cols_after
    finally:
        engine.dispose()


def test_migrate_missing_columns_is_idempotent():
    """Running migration twice should not raise errors."""
    engine = _fresh_engine()
    try:
        inspector = inspect(engine)
        _migrate_missing_columns(engine, inspector)  # first run (no-op, all columns exist)
        _migrate_missing_columns(engine, inspector)  # second run (still no-op)
    finally:
        engine.dispose()


# --- _column_default_sql unit tests ----------------------------------------


def test_column_default_sql_string_default():
    engine = _fresh_engine()
    try:
        table = HostedBase.metadata.tables["hosted_purchases"]
        col = table.columns["starting_redeemable_balance"]
        assert _column_default_sql(col) == "'0.00'"
    finally:
        engine.dispose()


def test_column_default_sql_boolean_default():
    engine = _fresh_engine()
    try:
        table = HostedBase.metadata.tables["hosted_users"]
        col = table.columns["is_active"]
        assert _column_default_sql(col) == "TRUE"
    finally:
        engine.dispose()


def test_column_default_sql_float_default():
    engine = _fresh_engine()
    try:
        table = HostedBase.metadata.tables["hosted_sites"]
        col = table.columns["sc_rate"]
        assert _column_default_sql(col) == "1.0"
    finally:
        engine.dispose()
