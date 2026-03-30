"""Headless smoke tests for the Adjustments/Checkpoints rollout.

Ensures the view dialogs still instantiate cleanly after adding the optional
"Adjustments" tab + deep-links.
"""

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from models.purchase import Purchase
from models.redemption import Redemption
from models.game_session import GameSession

from desktop.ui.tabs.purchases_tab_modern import ModernPurchaseViewDialog
from desktop.ui.tabs.redemptions_tab import RedemptionViewDialog
from desktop.ui.tabs.game_sessions_tab import ViewSessionDialog
from desktop.ui.tabs.realized_tab import RealizedPositionDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def facade():
    f = AppFacade(":memory:")
    yield f
    f.db.close()


def test_purchase_view_dialog_instantiates(qapp, facade):
    purchase = Purchase(
        id=1,
        user_id=1,
        site_id=1,
        amount=Decimal("10.00"),
        purchase_date=date(2026, 1, 1),
        purchase_time="12:00:00",
    )
    dialog = ModernPurchaseViewDialog(
        facade=facade,
        purchase=purchase,
        parent=None,
        user_name="User",
        site_name="Site",
        card_name="Card",
    )
    qapp.processEvents()
    dialog.close()


def test_redemption_view_dialog_instantiates(qapp, facade):
    redemption = Redemption(
        id=1,
        user_id=1,
        site_id=1,
        amount=Decimal("0.00"),
        redemption_date=date(2026, 1, 2),
        redemption_time="13:00:00",
        fees=Decimal("0.00"),
    )
    dialog = RedemptionViewDialog(redemption=redemption, facade=facade, parent=None)
    qapp.processEvents()
    dialog.close()


def test_session_view_dialog_instantiates(qapp, facade):
    session = GameSession(
        id=1,
        user_id=1,
        site_id=1,
        session_date=date(2026, 1, 3),
        session_time="14:00:00",
        status="Closed",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        purchases_during=Decimal("0.00"),
        redemptions_during=Decimal("0.00"),
        wager_amount=Decimal("0.00"),
    )
    dialog = ViewSessionDialog(facade=facade, session=session, parent=None)
    qapp.processEvents()
    dialog.close()


def test_realized_position_dialog_instantiates(qapp, facade):
    position = {
        "tax_session_id": 1,
        "session_date": "2026-01-04",
        "cost_basis": "0.00",
        "net_pl": "0.00",
        "redemption_id": 1,
        "redemption_amount": "0.00",
        "redemption_date": "2026-01-04",
        "redemption_time": "15:00:00",
        "fees": "0.00",
        "more_remaining": 0,
        "receipt_date": None,
        "processed": 0,
        "redemption_notes": "",
        "site_name": "Site",
        "user_name": "User",
        "method_name": "",
        "method_type": "",
    }
    dialog = RealizedPositionDialog(
        position=position,
        allocations=[],
        linked_sessions=[],
        parent=None,
        facade=facade,
    )
    qapp.processEvents()
    dialog.close()
