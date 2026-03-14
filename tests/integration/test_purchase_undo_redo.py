from datetime import date
from decimal import Decimal

import pytest

from app_facade import AppFacade


@pytest.fixture
def facade(tmp_path):
    app = AppFacade(str(tmp_path / "purchase_undo_redo.db"))
    yield app
    app.db.close()


def test_undo_redo_deleted_purchase_restores_and_redeletes_purchase(facade):
    """Undo/redo for purchase delete should round-trip a fully reconstructed purchase."""
    user = facade.create_user("Undo User")
    site = facade.create_site("Undo Site", sc_rate=1.0)

    purchase = facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("25.00"),
        purchase_date=date(2026, 3, 1),
        purchase_time="10:00:00",
        sc_received=Decimal("25.00"),
    )

    facade.delete_purchase(purchase.id)
    assert facade.get_purchase(purchase.id) is None

    undone = facade.undo_redo_service.undo()
    assert undone == f"Delete purchase #{purchase.id}"

    restored = facade.get_purchase(purchase.id)
    assert restored is not None
    assert restored.amount == Decimal("25.00")
    assert restored.starting_redeemable_balance == Decimal("0.00")
    assert restored.remaining_amount == Decimal("25.00")

    redone = facade.undo_redo_service.redo()
    assert redone == f"Delete purchase #{purchase.id}"
    assert facade.get_purchase(purchase.id) is None
