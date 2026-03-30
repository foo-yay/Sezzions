"""Regression test for Issue #47.

Editing a purchase should compute expected balance *before* that purchase,
not include the purchase being edited.

This is exercised via the PurchaseDialog live balance-check label.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6 import QtCore

from app_facade import AppFacade
from desktop.ui.tabs.purchases_tab import PurchaseDialog


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_purchase_edit_balance_check_excludes_edited_purchase(qtbot, temp_db_path):
    facade = AppFacade(temp_db_path)

    user = facade.create_user("TestUser")
    site = facade.create_site("Zula", sc_rate=1.0)
    card = facade.create_card(user_id=user.id, name="Test Card", last_four="1234", cashback_rate=0.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("12.99"),
        purchase_date=date(2026, 1, 22),
        purchase_time="12:06:00",
        sc_received=Decimal("15"),
        starting_sc_balance=Decimal("36.75"),
        card_id=card.id,
    )

    purchase2 = facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("7.99"),
        purchase_date=date(2026, 2, 2),
        purchase_time="17:50:00",
        sc_received=Decimal("10"),
        starting_sc_balance=Decimal("55.75"),
        card_id=card.id,
    )

    dialog = PurchaseDialog(facade, purchase=purchase2)
    qtbot.addWidget(dialog)

    QtCore.QCoreApplication.processEvents()
    qtbot.wait(50)

    text = dialog.balance_check_label.text()
    # New logic uses actual balance chain: P2 expected = P1's actual post-purchase (36.75)
    # P2 actual pre = 45.75, so difference = 45.75 - 36.75 = 9.00 SC
    # Expected post = 36.75 + 10 = 46.75 SC
    assert "9.00 SC HIGHER than expected" in text
    assert "(46.75 SC)" in text
    assert dialog.balance_check_label.property("status") == "warning"

    dialog.close()
    facade.db.close()
