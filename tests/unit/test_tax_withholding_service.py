from decimal import Decimal

import pytest

from repositories.daily_session_repository import DailySessionRepository
from services.tax_withholding_service import TaxWithholdingService


class FakeSettings:
    def __init__(self, data):
        self._data = dict(data)

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def service(test_db):
    settings = FakeSettings(
        {
            "tax_withholding_enabled": True,
            "tax_withholding_default_rate_pct": 20,
            "time_zone": "UTC",
        }
    )
    return TaxWithholdingService(test_db, settings=settings)


@pytest.fixture
def daily_session_repo(test_db):
    return DailySessionRepository(test_db)


def _insert_closed_game_session(
    test_db,
    sample_user,
    sample_site,
    session_date: str,
    session_time: str,
    end_date: str,
    end_time: str,
    net_taxable_pl: str,
):
    """Insert a closed game session for tax withholding tests."""
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, session_date, session_time,
            end_date, end_time, net_taxable_pl, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            session_date,
            session_time,
            end_date,
            end_time,
            net_taxable_pl,
            "Closed",
        ),
    )


def test_compute_amount_positive_pl():
    assert TaxWithholdingService.compute_amount(Decimal("100.00"), Decimal("20")) == Decimal("20.00")


def test_compute_amount_non_positive_pl_is_zero():
    assert TaxWithholdingService.compute_amount(Decimal("0.00"), Decimal("20")) == Decimal("0.00")
    assert TaxWithholdingService.compute_amount(Decimal("-10.00"), Decimal("20")) == Decimal("0.00")


def test_bulk_recalc_sets_rate_and_amount_for_non_custom_sessions(service, test_db, sample_user, sample_site):
    """Test bulk recalc calculates tax at the DATE level (net across all users)."""
    # Insert closed session for the date
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-01",
        "10:00:00",
        "2026-01-01",
        "11:00:00",
        "100.00",
    )

    # Recalculate all dates
    updated = service.bulk_recalculate(start_date=None, end_date=None, overwrite_custom=False)
    assert updated == 1

    # Tax is now stored in daily_date_tax table, not daily_sessions
    row = test_db.fetch_one(
        """
        SELECT net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM daily_date_tax WHERE session_date = ?
        """,
        ("2026-01-01",),
    )
    assert row["net_daily_pnl"] == 100.0
    assert row["tax_withholding_rate_pct"] == 20.0
    assert row["tax_withholding_is_custom"] == 0
    assert row["tax_withholding_amount"] == 20.0


def test_bulk_recalc_skips_custom_when_not_overwriting(service, test_db, sample_user, sample_site):
    """Test bulk recalc skips dates that have custom tax rates."""
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-01",
        "10:00:00",
        "2026-01-01",
        "11:00:00",
        "100.00",
    )
    # Insert custom tax for this date
    test_db.execute(
        "INSERT INTO daily_date_tax (session_date, net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount) VALUES (?, ?, ?, ?, ?)",
        ("2026-01-01", 100.0, 30.0, 1, 30.0)
    )

    updated = service.bulk_recalculate(overwrite_custom=False)
    assert updated == 0  # Custom date should not be updated

    row = test_db.fetch_one(
        """
        SELECT tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM daily_date_tax WHERE session_date = ?
        """,
        ("2026-01-01",),
    )
    # Should still have custom values
    assert row["tax_withholding_rate_pct"] == 30.0
    assert row["tax_withholding_is_custom"] == 1
    assert row["tax_withholding_amount"] == 30.0


def test_bulk_recalc_overwrites_custom_when_requested(service, test_db, sample_user, sample_site):
    """Test bulk recalc overwrites custom tax rates when requested."""
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-01",
        "10:00:00",
        "2026-01-01",
        "11:00:00",
        "100.00",
    )
    # Insert custom tax for this date
    test_db.execute(
        "INSERT INTO daily_date_tax (session_date, net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount) VALUES (?, ?, ?, ?, ?)",
        ("2026-01-01", 100.0, 30.0, 1, 30.0)
    )

    updated = service.bulk_recalculate(start_date=None, end_date=None, overwrite_custom=True)
    assert updated == 1

    row = test_db.fetch_one(
        """
        SELECT tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM daily_date_tax WHERE session_date = ?
        """,
        ("2026-01-01",),
    )
    assert row["tax_withholding_rate_pct"] == 20.0
    assert row["tax_withholding_is_custom"] == 0
    assert row["tax_withholding_amount"] == 20.0


def test_apply_to_date_preserves_existing_custom_rate(service, test_db, sample_user, sample_site):
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-01",
        "10:00:00",
        "2026-01-01",
        "11:00:00",
        "100.00",
    )

    # Seed a custom rate for the date.
    test_db.execute(
        "INSERT INTO daily_date_tax (session_date, net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount) VALUES (?, ?, ?, ?, ?)",
        ("2026-01-01", 100.0, 30.0, 1, 30.0),
    )

    # Re-apply without specifying a custom rate: should preserve the custom rate.
    service.apply_to_date("2026-01-01")

    row = test_db.fetch_one(
        """
        SELECT net_daily_pnl, tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM daily_date_tax WHERE session_date = ?
        """,
        ("2026-01-01",),
    )
    assert row["net_daily_pnl"] == 100.0
    assert row["tax_withholding_rate_pct"] == 30.0
    assert row["tax_withholding_is_custom"] == 1
    assert row["tax_withholding_amount"] == 30.0


def test_bulk_recalc_is_atomic_on_failure(service, test_db, sample_user, sample_site, monkeypatch):
    """Test that bulk recalc is atomic - failure rolls back all changes."""
    # Two daily sessions eligible for update.
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-01",
        "10:00:00",
        "2026-01-01",
        "11:00:00",
        "100.00",
    )
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-01-02",
        "10:00:00",
        "2026-01-02",
        "11:00:00",
        "50.00",
    )


def test_apply_to_date_uses_local_end_date(service, test_db, sample_user, sample_site, monkeypatch):
    """Tax rollups should follow local end date, not UTC date boundary."""
    from tools import timezone_utils

    monkeypatch.setattr(timezone_utils, "get_configured_timezone_name", lambda *_: "America/New_York")

    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-02-14",
        "17:00:00",
        "2026-02-15",
        "02:00:00",
        "100.00",
    )
    _insert_closed_game_session(
        test_db,
        sample_user,
        sample_site,
        "2026-02-14",
        "18:00:00",
        "2026-02-14",
        "20:00:00",
        "-20.00",
    )

    service.apply_to_date("2026-02-14")

    row = test_db.fetch_one(
        """
        SELECT net_daily_pnl, tax_withholding_amount
        FROM daily_date_tax WHERE session_date = ?
        """,
        ("2026-02-14",),
    )
    assert row["net_daily_pnl"] == 80.0
    assert row["tax_withholding_amount"] == 16.0

    # Inject failure after the UPDATE executemany call begins.
    real_executemany = test_db.executemany_no_commit

    def boom(query, params_seq):
        # Fail before any statement is actually executed.
        raise RuntimeError("boom")

    monkeypatch.setattr(test_db, "executemany_no_commit", boom)

    with pytest.raises(RuntimeError, match="boom"):
        service.bulk_recalculate(start_date=None, end_date=None, overwrite_custom=False)

    # Nothing should be updated in daily_date_tax - check both dates
    for date in ("2026-01-01", "2026-01-02"):
        row = test_db.fetch_one(
            """
            SELECT * FROM daily_date_tax WHERE session_date = ?
            """,
            (date,),
        )
        assert row is None  # No tax data should exist after rollback

    # Restore to avoid side effects
    monkeypatch.setattr(test_db, "executemany_no_commit", real_executemany)
