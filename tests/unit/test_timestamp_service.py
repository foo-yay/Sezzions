"""
Tests for timezone-aware timestamp uniqueness.
"""
from datetime import date

import pytest

from repositories.database import DatabaseManager
from services.timestamp_service import TimestampService


@pytest.fixture
def db():
    db = DatabaseManager(":memory:")
    yield db
    db.close()


@pytest.fixture
def timestamp_service(db):
    return TimestampService(db)


def _seed_user_site(db, user_id=1, site_id=1):
    db.execute(
        "INSERT INTO users (id, name, is_active) VALUES (?, ?, 1)",
        (user_id, f"User {user_id}"),
    )
    db.execute(
        "INSERT INTO sites (id, name, is_active) VALUES (?, ?, 1)",
        (site_id, f"Site {site_id}"),
    )


def _seed_purchase(db, user_id, site_id, purchase_date, purchase_time):
    db.execute(
        """
        INSERT INTO purchases (
            user_id, site_id, amount, sc_received, starting_sc_balance, cashback_earned,
            cashback_is_manual, purchase_date, purchase_time, card_id, remaining_amount, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            site_id,
            "10.00",
            "10.00",
            "10.00",
            "0.00",
            0,
            purchase_date,
            purchase_time,
            None,
            "10.00",
            None,
        ),
    )


def test_timestamp_service_adjusts_for_existing_utc_conflict(timestamp_service, db, monkeypatch):
    """Ensure local input is compared against UTC storage and adjusted if needed."""
    from services import timestamp_service as ts_module

    monkeypatch.setattr(ts_module, "get_configured_timezone_name", lambda: "America/New_York")

    _seed_user_site(db, user_id=1, site_id=1)

    # Existing purchase stored in UTC at 20:00:00, which is 15:00:00 local (EST).
    _seed_purchase(db, user_id=1, site_id=1, purchase_date="2026-02-10", purchase_time="20:00:00")

    adjusted_date_str, adjusted_time_str, was_adjusted = timestamp_service.ensure_unique_timestamp(
        user_id=1,
        site_id=1,
        date_val=date(2026, 2, 10),
        time_str="15:00:00",
        event_type="purchase",
    )

    assert was_adjusted is True
    assert adjusted_date_str == "2026-02-10"
    assert adjusted_time_str == "15:00:01"
