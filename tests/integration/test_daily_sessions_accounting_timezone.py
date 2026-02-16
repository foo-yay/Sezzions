"""Integration tests for Accounting TZ history in Daily Sessions (Issue #117)."""
from datetime import date

from services.daily_sessions_service import DailySessionsService


def _seed_history(db):
    db.execute(
        """
        INSERT INTO accounting_time_zone_history (effective_utc_timestamp, accounting_time_zone)
        VALUES (?, ?)
        """,
        ("1970-01-01 00:00:00", "America/New_York"),
    )
    db.execute(
        """
        INSERT INTO accounting_time_zone_history (effective_utc_timestamp, accounting_time_zone)
        VALUES (?, ?)
        """,
        ("2026-02-15 07:00:00", "America/Phoenix"),
    )


def test_daily_sessions_use_accounting_tz_history(test_db, sample_user, sample_site):
    _seed_history(test_db)

    # Session ending before the Accounting TZ change (NY applies).
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, session_date, session_time, end_date, end_time,
            starting_balance, ending_balance, starting_redeemable, ending_redeemable,
            purchases_during, redemptions_during, wager_amount, status, net_taxable_pl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-02-15",
            "04:30:00",
            "2026-02-15",
            "04:30:00",
            "10.00",
            "15.00",
            "10.00",
            "15.00",
            "0.00",
            "0.00",
            "0.00",
            "Closed",
            "5.00",
        ),
    )

    # Session ending after the Accounting TZ change (Phoenix applies).
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, session_date, session_time, end_date, end_time,
            starting_balance, ending_balance, starting_redeemable, ending_redeemable,
            purchases_during, redemptions_during, wager_amount, status, net_taxable_pl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-02-15",
            "07:30:00",
            "2026-02-15",
            "07:30:00",
            "10.00",
            "18.00",
            "10.00",
            "18.00",
            "0.00",
            "0.00",
            "0.00",
            "Closed",
            "8.00",
        ),
    )

    service = DailySessionsService(test_db)
    rows = service.fetch_sessions()
    dates = {row["session_date"] for row in rows}

    assert date(2026, 2, 15) in dates
    assert date(2026, 2, 14) in dates

    filtered = service.fetch_sessions(active_date_filter=(date(2026, 2, 14), date(2026, 2, 14)))
    assert len(filtered) == 1
    assert filtered[0]["session_date"] == date(2026, 2, 14)
