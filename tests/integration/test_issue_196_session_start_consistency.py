from datetime import date
from decimal import Decimal

import pytest

from app_facade import AppFacade


@pytest.fixture
def facade():
    app = AppFacade(":memory:")
    try:
        yield app
    finally:
        app.db.close()


def _seed_user_site(facade: AppFacade) -> tuple[int, int]:
    user = facade.create_user("Issue196 User")
    site = facade.create_site("Issue196 Site", sc_rate=1.0)
    return user.id, site.id


def test_issue_196_valid_mid_session_purchase_can_still_close(facade):
    user_id, site_id = _seed_user_site(facade)

    facade.create_purchase(
        user_id=user_id,
        site_id=site_id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 3, 26),
        purchase_time="09:50:00",
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("100.00"),
    )
    session = facade.create_game_session(
        user_id=user_id,
        site_id=site_id,
        game_id=None,
        session_date=date(2026, 3, 26),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
    )
    facade.create_purchase(
        user_id=user_id,
        site_id=site_id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 3, 26),
        purchase_time="11:00:00",
        sc_received=Decimal("50.00"),
        starting_sc_balance=Decimal("150.00"),
    )

    closed = facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("180.00"),
        ending_redeemable=Decimal("80.00"),
        end_date=date(2026, 3, 26),
        end_time="12:00:00",
        status="Closed",
    )

    assert closed.status == "Closed"
    assert Decimal(str(closed.expected_start_total)) == Decimal("100.00")
    assert Decimal(str(closed.basis_consumed)) == Decimal("50.000")


def test_issue_196_close_blocks_if_start_already_includes_later_during_purchase(facade):
    user_id, site_id = _seed_user_site(facade)

    facade.create_purchase(
        user_id=user_id,
        site_id=site_id,
        amount=Decimal("2000.00"),
        purchase_date=date(2026, 3, 26),
        purchase_time="13:51:51",
        sc_received=Decimal("2005.00"),
        starting_sc_balance=Decimal("2009.98"),
    )
    session = facade.create_game_session(
        user_id=user_id,
        site_id=site_id,
        game_id=None,
        session_date=date(2026, 3, 26),
        session_time="13:52:00",
        starting_balance=Decimal("3012.48"),
        ending_balance=Decimal("3012.48"),
        starting_redeemable=Decimal("4.98"),
        ending_redeemable=Decimal("4.98"),
    )
    facade.create_purchase(
        user_id=user_id,
        site_id=site_id,
        amount=Decimal("1000.00"),
        purchase_date=date(2026, 3, 26),
        purchase_time="13:52:05",
        sc_received=Decimal("1002.50"),
        starting_sc_balance=Decimal("3012.48"),
    )

    with pytest.raises(ValueError, match="starting balances no longer match the balance check"):
        facade.update_game_session(
            session_id=session.id,
            ending_balance=Decimal("3072.48"),
            ending_redeemable=Decimal("24.98"),
            end_date=date(2026, 3, 26),
            end_time="14:22:25",
            status="Closed",
        )

    still_active = facade.get_game_session(session.id)
    assert still_active.status == "Active"
