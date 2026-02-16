"""Expected redeemable should not be increased by purchases."""
from datetime import date
from decimal import Decimal

from app_facade import AppFacade


def test_expected_redeemable_ignores_purchases():
    facade = AppFacade(":memory:")
    user = facade.create_user("Test User")
    site = facade.create_site("Test Site")

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date(2026, 2, 8),
        session_time="22:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("69.10"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("69.10"),
        calculate_pl=False,
    )

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("69.10"),
        ending_redeemable=Decimal("69.10"),
        end_date=date(2026, 2, 8),
        end_time="23:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("299.99"),
        sc_received=Decimal("306.00"),
        starting_sc_balance=Decimal("388.60"),
        purchase_date=date(2026, 2, 15),
        purchase_time="12:00:00",
    )

    expected_total, expected_redeemable = facade.compute_expected_balances(
        user_id=user.id,
        site_id=site.id,
        session_date=date(2026, 2, 15),
        # compute_expected_balances applies purchases strictly before the cutoff
        session_time="12:00:01",
    )

    assert expected_total == Decimal("388.60")
    assert expected_redeemable == Decimal("69.10")

    facade.db.close()
