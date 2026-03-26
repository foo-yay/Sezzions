from datetime import date, datetime
from decimal import Decimal

import pytest

import app_facade as app_facade_module
import services.redemption_service as redemption_service_module
from app_facade import AppFacade
from models.purchase import Purchase


@pytest.fixture
def facade():
    app = AppFacade(":memory:")
    try:
        yield app
    finally:
        app.db.close()


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.combine(date.today(), datetime.strptime("09:30:00", "%H:%M:%S").time())


def _seed_reference_data(facade: AppFacade) -> None:
    facade.db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    facade.db.execute("INSERT INTO sites (id, name, sc_rate) VALUES (1, 'Fortune Coins', 0.01)")
    facade.db.commit()


def test_issue_195_close_marker_consumes_same_day_purchase_basis_with_local_time(facade, monkeypatch):
    _seed_reference_data(facade)

    facade.purchase_repo.create(
        Purchase(
            user_id=1,
            site_id=1,
            amount=Decimal("49.99"),
            purchase_date=date.today(),
            purchase_time="09:00:00",
            purchase_entry_time_zone="America/New_York",
            starting_sc_balance=Decimal("5608.00"),
            starting_redeemable_balance=Decimal("8.00"),
            remaining_amount=Decimal("49.99"),
            status="active",
            notes="Issue 195 same-day purchase",
        )
    )

    monkeypatch.setattr(app_facade_module, "datetime", _FixedDateTime)
    monkeypatch.setattr(redemption_service_module, "get_entry_timezone_name", lambda: "America/New_York")

    result = facade.close_unrealized_position(
        site_id=1,
        user_id=1,
        current_sc=Decimal("8.00"),
        current_value=Decimal("0.08"),
        total_basis=Decimal("49.99"),
    )

    assert result["net_loss"] == Decimal("49.99")

    purchase = facade.db.fetch_one(
        "SELECT remaining_amount FROM purchases WHERE id = 1"
    )
    assert Decimal(str(purchase["remaining_amount"])) == Decimal("0.00")

    redemption = facade.db.fetch_one(
        "SELECT more_remaining, notes FROM redemptions ORDER BY id DESC LIMIT 1"
    )
    assert redemption["more_remaining"] == 0
    assert redemption["notes"].startswith("Balance Closed - Net Loss: $49.99")

    realized = facade.db.fetch_one(
        "SELECT cost_basis, payout, net_pl FROM realized_transactions ORDER BY id DESC LIMIT 1"
    )
    assert Decimal(str(realized["cost_basis"])) == Decimal("49.99")
    assert Decimal(str(realized["payout"])) == Decimal("0.00")
    assert Decimal(str(realized["net_pl"])) == Decimal("-49.99")

    allocations = facade.db.fetch_all(
        "SELECT purchase_id, allocated_amount FROM redemption_allocations ORDER BY id"
    )
    assert allocations == [{"purchase_id": 1, "allocated_amount": '49.99'}]
