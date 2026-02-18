from datetime import date
from decimal import Decimal

import pytest
from PySide6 import QtCore
from PySide6.QtTest import QTest
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


def test_expense_dialog_vendor_and_notes_inline_prediction_with_tab_accept(qapp):
    dialog = ExpenseDialog(
        users=[],
        vendor_suggestions=["Amazon", "Walmart"],
        notes_suggestions=["Parking", "Mileage"],
        parent=None,
    )

    dialog.show()
    qapp.processEvents()

    dialog.vendor_edit.setFocus()
    QTest.keyClicks(dialog.vendor_edit, "Ama")
    qapp.processEvents()

    assert dialog.vendor_edit.text() == "Amazon"
    assert dialog.vendor_edit.selectedText() == "zon"

    QTest.keyClick(dialog.vendor_edit, QtCore.Qt.Key_Tab)
    qapp.processEvents()

    assert dialog.vendor_edit.text() == "Amazon"
    assert dialog.vendor_edit.selectedText() == ""

    dialog.vendor_edit.setFocus()
    dialog.vendor_edit.setText("")
    QTest.keyClicks(dialog.vendor_edit, "wal")
    qapp.processEvents()
    QTest.keyClick(dialog.vendor_edit, QtCore.Qt.Key_Tab)
    qapp.processEvents()
    assert dialog.vendor_edit.text() == "Walmart"

    dialog.vendor_edit.setFocus()
    QTest.keyClick(dialog.vendor_edit, QtCore.Qt.Key_Backspace)
    qapp.processEvents()
    assert dialog.vendor_edit.text() == "Walmar"

    QTest.keyClick(dialog.vendor_edit, QtCore.Qt.Key_Delete)
    qapp.processEvents()
    assert dialog.vendor_edit.text() == "Walmar"

    dialog._toggle_notes()
    dialog.description_edit.setFocus()
    QTest.keyClicks(dialog.description_edit, "Par")
    qapp.processEvents()

    assert dialog.description_edit.toPlainText() == "Parking"
    assert dialog.description_edit.textCursor().selectedText() == "king"

    QTest.keyClick(dialog.description_edit, QtCore.Qt.Key_Tab)
    qapp.processEvents()

    assert dialog.description_edit.toPlainText() == "Parking"
    assert not dialog.description_edit.textCursor().hasSelection()

    dialog.description_edit.setFocus()
    dialog.description_edit.setPlainText("")
    QTest.keyClicks(dialog.description_edit, "Mil")
    qapp.processEvents()
    QTest.keyClick(dialog.description_edit, QtCore.Qt.Key_Tab)
    qapp.processEvents()
    assert dialog.description_edit.toPlainText() == "Mileage"

    QTest.keyClick(dialog.description_edit, QtCore.Qt.Key_Backspace)
    qapp.processEvents()
    assert dialog.description_edit.toPlainText() == "Mileag"

    QTest.keyClick(dialog.description_edit, QtCore.Qt.Key_Delete)
    qapp.processEvents()
    assert dialog.description_edit.toPlainText() == "Mileag"

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
