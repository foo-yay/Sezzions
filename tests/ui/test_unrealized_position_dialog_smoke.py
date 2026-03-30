"""UI regression tests for the Unrealized "View Position" dialog.

Ensures the dialog can be instantiated headlessly without attribute errors.
"""

from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication

from models.unrealized_position import UnrealizedPosition
from desktop.ui.tabs.unrealized_tab import UnrealizedPositionDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_unrealized_position_dialog_constructs_without_crash(qapp):
    pos = UnrealizedPosition(
        site_id=1,
        user_id=1,
        site_name="Test Site",
        user_name="Test User",
        start_date=date(2026, 1, 1),
        purchase_basis=Decimal("100.00"),
        total_sc=Decimal("2505.00"),
        redeemable_sc=Decimal("2505.00"),
        current_value=Decimal("2505.00"),
        unrealized_pl=Decimal("2405.00"),
        last_activity=date(2026, 2, 1),
        notes="",
    )

    dialog = UnrealizedPositionDialog(position=pos, purchases=[], sessions=[])
    qapp.processEvents()

    assert dialog is not None

    dialog.close()
    qapp.processEvents()
