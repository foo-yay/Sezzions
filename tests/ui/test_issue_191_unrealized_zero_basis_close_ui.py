from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from models.unrealized_position import UnrealizedPosition
from desktop.ui.tabs.unrealized_tab import UnrealizedTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app



def test_zero_basis_close_uses_close_flow_instead_of_basis_guard(qapp, monkeypatch):
    facade = Mock()
    facade.get_unrealized_positions.return_value = []
    facade.close_unrealized_position.return_value = {
        "net_loss": Decimal("0.00"),
        "current_sc": Decimal("0.14"),
        "current_value": Decimal("0.14"),
    }

    tab = UnrealizedTab(facade)
    position = UnrealizedPosition(
        site_id=1,
        user_id=1,
        site_name="Play Fame",
        user_name="fooyay",
        start_date=date(2026, 3, 1),
        purchase_basis=Decimal("0.00"),
        total_sc=Decimal("0.14"),
        redeemable_sc=Decimal("0.14"),
        current_value=Decimal("0.14"),
        unrealized_pl=Decimal("0.14"),
        last_activity=date(2026, 3, 23),
        notes="",
    )
    tab.positions = [position]
    monkeypatch.setattr(tab, "_selected_position", lambda: position)

    prompts = []
    infos = []

    def fake_question(_parent, _title, message):
        prompts.append(message)
        return QMessageBox.Yes

    def fake_information(_parent, title, message):
        infos.append((title, message))
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "question", fake_question)
    monkeypatch.setattr(QMessageBox, "information", fake_information)

    tab._close_balance()
    qapp.processEvents()

    assert prompts
    assert "No active basis to close" not in prompts[0]
    assert "Net loss: $0.00" in prompts[0]
    facade.close_unrealized_position.assert_called_once_with(
        1,
        1,
        current_sc=Decimal("0.14"),
        current_value=Decimal("0.14"),
        total_basis=Decimal("0.00"),
    )
    assert infos
    assert infos[-1][0] == "Success"
    assert "No cash flow loss recorded" in infos[-1][1]

    tab.close()
    qapp.processEvents()
