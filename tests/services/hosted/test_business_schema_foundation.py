from sqlalchemy import create_engine, inspect

from services.hosted.persistence import HostedBase


def _inspector():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, inspect(engine)


def test_hosted_business_schema_defines_all_core_workspace_tables() -> None:
    engine, inspector = _inspector()

    try:
        table_names = set(inspector.get_table_names())
    finally:
        engine.dispose()

    assert {
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
        "hosted_game_session_event_links",
        "hosted_game_rtp_aggregates",
        "hosted_redemption_allocations",
        "hosted_realized_transactions",
        "hosted_realized_daily_notes",
        "hosted_expenses",
        "hosted_daily_sessions",
        "hosted_daily_date_tax",
        "hosted_account_adjustments",
        "hosted_audit_log",
        "hosted_settings",
        "hosted_accounting_time_zone_history",
    }.issubset(table_names)


def test_all_hosted_business_tables_have_explicit_workspace_ownership() -> None:
    engine, inspector = _inspector()

    try:
        business_tables = [
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
            "hosted_game_session_event_links",
            "hosted_game_rtp_aggregates",
            "hosted_redemption_allocations",
            "hosted_realized_transactions",
            "hosted_realized_daily_notes",
            "hosted_expenses",
            "hosted_daily_sessions",
            "hosted_daily_date_tax",
            "hosted_account_adjustments",
        ]
        table_columns = {
            table_name: {column["name"] for column in inspector.get_columns(table_name)}
            for table_name in business_tables
        }
    finally:
        engine.dispose()

    for table_name, columns in table_columns.items():
        assert "workspace_id" in columns, table_name


def test_workspace_scoped_master_tables_allow_duplicate_names_across_workspaces() -> None:
    engine, inspector = _inspector()

    try:
        uniques = {
            table_name: inspector.get_unique_constraints(table_name)
            for table_name in [
                "hosted_users",
                "hosted_sites",
                "hosted_game_types",
                "hosted_redemption_method_types",
            ]
        }
    finally:
        engine.dispose()

    assert any(
        constraint["column_names"] == ["workspace_id", "name"]
        for constraint in uniques["hosted_users"]
    )
    assert any(
        constraint["column_names"] == ["workspace_id", "name"]
        for constraint in uniques["hosted_sites"]
    )
    assert any(
        constraint["column_names"] == ["workspace_id", "name"]
        for constraint in uniques["hosted_game_types"]
    )
    assert any(
        constraint["column_names"] == ["workspace_id", "name"]
        for constraint in uniques["hosted_redemption_method_types"]
    )


def test_core_transaction_tables_reference_workspace_scoped_parents() -> None:
    engine, inspector = _inspector()

    try:
        purchase_fks = inspector.get_foreign_keys("hosted_purchases")
        redemption_fks = inspector.get_foreign_keys("hosted_redemptions")
        game_session_fks = inspector.get_foreign_keys("hosted_game_sessions")
        allocation_fks = inspector.get_foreign_keys("hosted_redemption_allocations")
    finally:
        engine.dispose()

    assert {fk["referred_table"] for fk in purchase_fks} >= {
        "hosted_workspaces",
        "hosted_users",
        "hosted_sites",
        "hosted_cards",
    }
    assert {fk["referred_table"] for fk in redemption_fks} >= {
        "hosted_workspaces",
        "hosted_users",
        "hosted_sites",
        "hosted_redemption_methods",
    }
    assert {fk["referred_table"] for fk in game_session_fks} >= {
        "hosted_workspaces",
        "hosted_users",
        "hosted_sites",
        "hosted_games",
        "hosted_game_types",
    }
    assert {fk["referred_table"] for fk in allocation_fks} >= {
        "hosted_workspaces",
        "hosted_redemptions",
        "hosted_purchases",
    }