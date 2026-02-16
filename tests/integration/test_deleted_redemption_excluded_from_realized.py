"""Deleted redemptions should not rebuild into realized transactions."""
from datetime import date
from decimal import Decimal

from app_facade import AppFacade


def test_deleted_redemption_excluded_from_realized_rebuild():
    facade = AppFacade(":memory:")
    user = facade.create_user("Test User")
    site = facade.create_site("Test Site")

    purchase = facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 2, 15),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("100.00"),
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 2, 15),
    )

    # Soft-delete redemption without clearing realized rows to simulate stale data.
    facade.redemption_repo.delete(redemption.id)

    facade.recalculation_service.rebuild_for_pair(user.id, site.id)

    realized = facade.realized_transaction_repo.get_all()
    assert realized == []

    facade.db.close()
