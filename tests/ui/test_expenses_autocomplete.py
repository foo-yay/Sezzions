from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.tabs.expenses_tab import ExpenseDialog, ExpensesTab


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


def test_expense_dialog_wires_vendor_and_notes_completers(qapp):
    dialog = ExpenseDialog(
        users=[],
        vendor_suggestions=["Amazon", "Walmart"],
        notes_suggestions=["Parking", "Mileage"],
        parent=None,
    )

    assert dialog.vendor_edit.completer() is not None
    assert dialog.description_edit.completer() is not None

    dialog.close()


def test_expenses_tab_builds_distinct_vendor_and_notes_suggestions(facade, qapp):
    user = facade.create_user("Autocomplete User")

    facade.create_expense(
        expense_date=date(2026, 2, 1),
        amount=Decimal("10.00"),
        vendor="Amazon",
        description="Parking",
        user_id=user.id,
        expense_time="10:00:00",
    )
    facade.create_expense(
        expense_date=date(2026, 2, 2),
        amount=Decimal("12.00"),
        vendor="  amazon  ",
        description="Parking",
        user_id=user.id,
        expense_time="11:00:00",
    )
    facade.create_expense(
        expense_date=date(2026, 2, 3),
        amount=Decimal("15.00"),
        vendor="Target",
        description="Mileage",
        user_id=user.id,
        expense_time="12:00:00",
    )

    tab = ExpensesTab(facade)
    vendors, notes = tab._build_expense_autocomplete_lists()

    assert vendors == ["Amazon", "Target"]
    assert notes == ["Mileage", "Parking"]

    tab.close()
