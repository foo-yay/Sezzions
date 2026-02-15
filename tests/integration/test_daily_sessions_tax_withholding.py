"""Integration coverage for Daily Sessions tax withholding display data."""
from datetime import date

from repositories.database import DatabaseManager
from services.daily_sessions_service import DailySessionsService


def _seed_common_tables(db: DatabaseManager):
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Tax User')")
    db.execute("INSERT INTO sites (id, name, sc_rate) VALUES (1, 'Tax Site', 1.0)")
    db.execute("INSERT INTO game_types (id, name) VALUES (1, 'Slots')")
    db.execute("INSERT INTO games (id, name, game_type_id) VALUES (1, 'Buffalo Gold', 1)")


def test_daily_sessions_group_includes_tax_withholding(monkeypatch):
    from tools import timezone_utils

    monkeypatch.setattr(timezone_utils, "get_configured_timezone_name", lambda: "UTC")

    db = DatabaseManager(":memory:")
    try:
        _seed_common_tables(db)
        db.execute(
            """
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2026-02-10', '10:00:00', '2026-02-10', '11:00:00',
                    100.00, 150.00, 150.00, 'Closed')
            """
        )
        db.execute(
            """
            INSERT INTO daily_date_tax
            (session_date, net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount)
            VALUES ('2026-02-10', 50.00, 20.0, 0, 10.00)
            """
        )
        db.commit()

        service = DailySessionsService(db)
        monkeypatch.setattr(service, "fetch_notes_for_dates", lambda dates: {})
        sessions = service.fetch_sessions(active_date_filter=(date(2026, 2, 10), date(2026, 2, 10)))
        daily_tax_data = service.fetch_daily_tax_data(active_date_filter=(date(2026, 2, 10), date(2026, 2, 10)))
        grouped = service.group_sessions(sessions, daily_tax_data)

        assert grouped
        assert grouped[0]["date_tax_withholding"] == 10.00
    finally:
        db.close()
