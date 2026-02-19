from datetime import date

from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.tabs.expenses_tab import ExpensesTab
from ui.tabs.game_sessions_tab import GameSessionsTab
from ui.tabs.purchases_tab import PurchasesTab
from ui.tabs.redemptions_tab import RedemptionsTab, RedemptionViewDialog


def _mk_facade(tmp_path):
    db_path = tmp_path / "test_issue_143_ui.db"
    facade = AppFacade(str(db_path))
    user = facade.create_user("UI User")
    site = facade.create_site("UI Site")
    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=100,
        redemption_date=date.today(),
        apply_fifo=False,
    )
    return facade, redemption


def test_crud_toolbar_button_labels_are_compact(qtbot, tmp_path):
    _ = QApplication.instance() or QApplication([])
    facade, _redemption = _mk_facade(tmp_path)
    try:
        purchases = PurchasesTab(facade)
        redemptions = RedemptionsTab(facade)
        sessions = GameSessionsTab(facade)
        expenses = ExpensesTab(facade)

        qtbot.addWidget(purchases)
        qtbot.addWidget(redemptions)
        qtbot.addWidget(sessions)
        qtbot.addWidget(expenses)

        assert purchases.view_btn.text() == "👁️ View"
        assert purchases.edit_btn.text() == "✏️ Edit"
        assert purchases.delete_btn.text() == "🗑️ Delete"

        assert redemptions.view_btn.text() == "👁️ View"
        assert redemptions.edit_btn.text() == "✏️ Edit"
        assert redemptions.delete_btn.text() == "🗑️ Delete"
        assert redemptions.cancel_btn.text() == "🚫 Cancel"

        assert sessions.view_button.text() == "👁️ View"
        assert sessions.edit_button.text() == "✏️ Edit"
        assert sessions.delete_button.text() == "🗑️ Delete"

        assert expenses.view_btn.text() == "👁️ View"
        assert expenses.edit_btn.text() == "✏️ Edit"
        assert expenses.delete_btn.text() == "🗑️ Delete"

        add_texts = [btn.text() for btn in purchases.findChildren(type(purchases.view_btn))]
        assert "➕ Add Purchase" in add_texts
    finally:
        facade.db.close()


def test_redemption_view_dialog_shows_cancel_button(qtbot, tmp_path):
    _ = QApplication.instance() or QApplication([])
    facade, redemption = _mk_facade(tmp_path)
    try:
        triggered = {"cancel": 0}

        def _on_cancel():
            triggered["cancel"] += 1

        dialog = RedemptionViewDialog(
            redemption=facade.get_redemption(redemption.id),
            facade=facade,
            on_cancel=_on_cancel,
        )
        qtbot.addWidget(dialog)

        from PySide6.QtWidgets import QPushButton
        button_texts = [btn.text() for btn in dialog.findChildren(QPushButton)]
        assert "🚫 Cancel" in button_texts
        assert "🗑️ Delete" in button_texts

        from PySide6.QtWidgets import QLabel
        label_texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert "🚫 Cancellation Reason" not in label_texts
    finally:
        facade.db.close()


def test_redemption_view_dialog_shows_cancellation_reason_when_canceled(qtbot, tmp_path):
    _ = QApplication.instance() or QApplication([])
    facade, redemption = _mk_facade(tmp_path)
    try:
        facade.cancel_redemption(redemption.id, reason="Operator canceled duplicate")
        dialog = RedemptionViewDialog(
            redemption=facade.get_redemption(redemption.id),
            facade=facade,
        )
        qtbot.addWidget(dialog)

        from PySide6.QtWidgets import QLabel, QTextEdit
        label_texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert "🚫 Cancellation Reason" in label_texts

        text_values = [widget.toPlainText() for widget in dialog.findChildren(QTextEdit)]
        assert any("Operator canceled duplicate" in value for value in text_values)
    finally:
        facade.db.close()
