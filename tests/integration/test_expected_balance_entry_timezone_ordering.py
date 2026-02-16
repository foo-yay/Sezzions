"""Ensure expected balances respect UTC ordering across entry time zones."""
from datetime import date
from decimal import Decimal

from app_facade import AppFacade
from models.purchase import Purchase


def test_expected_balances_ignore_future_purchase_in_other_tz():
    facade = AppFacade(":memory:")
    user = facade.create_user("Test User")
    site = facade.create_site("Test Site")

    purchase = Purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 2, 15),
        purchase_time="21:28:52",
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("100.00"),
        purchase_entry_time_zone="America/Phoenix",
    )
    facade.purchase_repo.create(purchase)

    expected_total, expected_redeemable = facade.compute_expected_balances(
        user_id=user.id,
        site_id=site.id,
        session_date=date(2026, 2, 15),
        session_time="22:00:00",
        entry_time_zone="America/New_York",
    )

    assert expected_total == Decimal("0.00")
    assert expected_redeemable == Decimal("0.00")

    facade.db.close()
