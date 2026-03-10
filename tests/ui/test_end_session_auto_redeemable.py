from datetime import date
from decimal import Decimal
import os

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EndSessionDialog, EditClosedSessionDialog, StartSessionDialog


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def facade():
    f = AppFacade(":memory:")
    yield f
    f.db.close()


def _build_open_session(facade: AppFacade):
    user = facade.create_user("Auto User")
    site = facade.create_site("Auto Site", playthrough_requirement=3.0)
    game_type = facade.create_game_type("Slots")
    game = facade.create_game("Auto Game", game_type.id, rtp=96.0)

    return facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game.id,
        session_date=date(2026, 3, 1),
        session_time="10:00:00",
        starting_balance=Decimal("2005.00"),
        ending_balance=Decimal("2605.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
    )


def _build_closed_session(facade: AppFacade):
    session = _build_open_session(facade)
    return facade.update_game_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="11:00:00",
        ending_balance=Decimal("2605.00"),
        ending_redeemable=Decimal("0.00"),
    )


def _build_history_for_starting_redeemable(facade: AppFacade):
    user1 = facade.create_user("Auto Fill User 1")
    user2 = facade.create_user("Auto Fill User 2")
    site1 = facade.create_site("Auto Fill Site 1", playthrough_requirement=3.0)
    site2 = facade.create_site("Auto Fill Site 2", playthrough_requirement=3.0)
    game_type = facade.create_game_type("Auto Fill Slots")
    game = facade.create_game("Auto Fill Game", game_type.id, rtp=96.0)

    session1 = facade.create_game_session(
        user_id=user1.id,
        site_id=site1.id,
        game_id=game.id,
        session_date=date(2026, 3, 1),
        session_time="09:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("150.00"),
        starting_redeemable=Decimal("5.00"),
        ending_redeemable=Decimal("40.00"),
    )
    facade.update_game_session(
        session1.id,
        status="Closed",
        end_date=session1.session_date,
        end_time="10:00:00",
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("40.00"),
    )

    return {
        "user1": user1,
        "user2": user2,
        "site1": site1,
        "site2": site2,
        "game": game,
    }


def test_end_session_auto_calc_toggle_locks_and_updates_redeemable(qapp, facade):
    session = _build_open_session(facade)

    dialog = EndSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    assert hasattr(dialog, "auto_redeem_check")
    assert not dialog.auto_redeem_check.isChecked()
    dialog.auto_redeem_check.setChecked(True)
    qapp.processEvents()
    assert dialog.auto_redeem_check.isChecked()
    assert not dialog.end_redeem_edit.isEnabled()

    dialog.wager_edit.setText("600.00")
    dialog.end_total_edit.setText("2605.00")
    qapp.processEvents()

    assert dialog.end_redeem_edit.text() == "200.00"

    dialog.auto_redeem_check.setChecked(False)
    qapp.processEvents()
    assert dialog.end_redeem_edit.isEnabled()

    dialog.end_redeem_edit.setText("12.34")
    qapp.processEvents()
    assert dialog.end_redeem_edit.text() == "12.34"

    dialog.close()


def test_edit_closed_session_auto_calc_toggle_locks_and_updates_redeemable(qapp, facade):
    session = _build_closed_session(facade)

    dialog = EditClosedSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    assert hasattr(dialog, "auto_redeem_check")
    assert not dialog.auto_redeem_check.isChecked()
    assert dialog.end_redeem_edit.isEnabled()

    dialog.auto_redeem_check.setChecked(True)
    qapp.processEvents()
    assert dialog.auto_redeem_check.isChecked()
    assert not dialog.end_redeem_edit.isEnabled()

    dialog.wager_edit.setText("600.00")
    dialog.end_total_edit.setText("2605.00")
    qapp.processEvents()
    assert dialog.end_redeem_edit.text() == "200.00"

    dialog.auto_redeem_check.setChecked(False)
    qapp.processEvents()
    assert dialog.end_redeem_edit.isEnabled()

    dialog.end_redeem_edit.setText("12.34")
    qapp.processEvents()
    assert dialog.end_redeem_edit.text() == "12.34"

    dialog.close()


def test_end_session_auto_calc_zero_when_loss_exceeds_unlocked_redeemable(qapp, facade):
    session = _build_open_session(facade)

    dialog = EndSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.auto_redeem_check.setChecked(True)
    dialog.wager_edit.setText("600.00")
    dialog.end_total_edit.setText("1405.00")
    qapp.processEvents()

    assert dialog.end_redeem_edit.text() == "0.00"

    dialog.close()


def test_edit_closed_session_auto_calc_zero_when_loss_exceeds_unlocked_redeemable(qapp, facade):
    session = _build_closed_session(facade)

    dialog = EditClosedSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.auto_redeem_check.setChecked(True)
    dialog.wager_edit.setText("600.00")
    dialog.end_total_edit.setText("1405.00")
    qapp.processEvents()

    assert dialog.end_redeem_edit.text() == "0.00"

    dialog.close()


def test_end_session_auto_mode_requires_wager(qapp, facade):
    session = _build_open_session(facade)

    dialog = EndSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.auto_redeem_check.setChecked(True)
    dialog.end_total_edit.setText("2605.00")
    dialog.wager_edit.clear()
    qapp.processEvents()

    _data, error = dialog.collect_data()
    assert error == "Please enter Wager Amount when Auto-Calculate End Redeemable SC is enabled."

    dialog.close()


def test_edit_closed_session_auto_mode_requires_wager(qapp, facade):
    session = _build_closed_session(facade)

    dialog = EditClosedSessionDialog(facade=facade, session=session, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.auto_redeem_check.setChecked(True)
    dialog.end_total_edit.setText("2605.00")
    dialog.wager_edit.clear()
    qapp.processEvents()

    _data, error = dialog.collect_data()
    assert error == "Please enter Wager Amount when Auto-Calculate End Redeemable SC is enabled."

    dialog.close()


def test_auto_calc_checkbox_text_and_label_cleanup_in_auto_dialogs(qapp, facade):
    open_session = _build_open_session(facade)
    closed_session = facade.update_game_session(
        open_session.id,
        status="Closed",
        end_date=open_session.session_date,
        end_time="11:00:00",
        ending_balance=Decimal("2605.00"),
        ending_redeemable=Decimal("0.00"),
    )

    end_dialog = EndSessionDialog(facade=facade, session=open_session, parent=None)
    end_dialog.show()
    qapp.processEvents()

    assert end_dialog.auto_redeem_check.text() == ""
    assert any(
        label.text() == "Auto-Calc Redeemable SC"
        for label in end_dialog.findChildren(QLabel)
    )
    assert all(
        label.text() != "Auto End Redeemable:"
        for label in end_dialog.findChildren(QLabel)
    )
    end_dialog.close()

    closed_dialog = EditClosedSessionDialog(facade=facade, session=closed_session, parent=None)
    closed_dialog.show()
    qapp.processEvents()

    assert closed_dialog.auto_redeem_check.text() == ""
    assert any(
        label.text() == "Auto-Calc Redeemable SC"
        for label in closed_dialog.findChildren(QLabel)
    )
    assert all(
        label.text() != "Auto End Redeemable:"
        for label in closed_dialog.findChildren(QLabel)
    )
    closed_dialog.close()


def test_start_session_balance_check_displays_two_expected_lines(qapp, facade):
    seeded = _build_history_for_starting_redeemable(facade)
    dialog = StartSessionDialog(facade=facade, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.user_combo.setCurrentText(seeded["user1"].name)
    dialog.site_combo.setCurrentText(seeded["site1"].name)
    dialog.start_total_edit.setText("150.00")
    qapp.processEvents()

    text = dialog.balance_check_display.text()
    assert "Starting SC" in text
    assert "Starting Redeemable" in text
    dialog.close()


def test_starting_redeemable_auto_fill_manual_override_and_repopulate(qapp, facade):
    seeded = _build_history_for_starting_redeemable(facade)
    dialog = StartSessionDialog(facade=facade, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.user_combo.setCurrentText(seeded["user1"].name)
    dialog.site_combo.setCurrentText(seeded["site1"].name)
    qapp.processEvents()

    expected_total_1, expected_redeem_1 = facade.compute_expected_balances(
        user_id=seeded["user1"].id,
        site_id=seeded["site1"].id,
        session_date=date.today(),
        session_time="23:59:59",
    )
    assert dialog.start_total_edit.text() == f"{float(expected_total_1):.2f}"
    assert dialog.start_redeem_edit.text() == f"{float(expected_redeem_1):.2f}"
    assert "color: #8c8c8c" in dialog.start_total_edit.styleSheet()
    assert "color: #8c8c8c" in dialog.start_redeem_edit.styleSheet()

    dialog.start_total_edit.setText("999.00")
    dialog._on_start_total_edited("999.00")
    dialog.start_redeem_edit.setText("0.00")
    dialog._on_start_redeem_edited("0.00")
    qapp.processEvents()
    dialog.user_combo.setCurrentText(seeded["user2"].name)
    dialog.site_combo.setCurrentText(seeded["site2"].name)
    qapp.processEvents()
    assert dialog.start_total_edit.text() == "999.00"
    assert dialog.start_redeem_edit.text() == "0.00"
    assert dialog.start_total_edit.styleSheet() == ""
    assert dialog.start_redeem_edit.styleSheet() == ""

    dialog.start_total_edit.clear()
    dialog._on_start_total_edited("")
    dialog.start_redeem_edit.clear()
    dialog._on_start_redeem_edited("")
    qapp.processEvents()
    dialog.user_combo.setCurrentText(seeded["user1"].name)
    dialog.site_combo.setCurrentText(seeded["site1"].name)
    qapp.processEvents()
    assert dialog.start_total_edit.text() == f"{float(expected_total_1):.2f}"
    assert dialog.start_redeem_edit.text() == f"{float(expected_redeem_1):.2f}"
    assert "color: #8c8c8c" in dialog.start_total_edit.styleSheet()
    assert "color: #8c8c8c" in dialog.start_redeem_edit.styleSheet()

    dialog.close()


def test_edit_closed_session_start_balances_auto_fill_apply_on_context_change(qapp, facade):
    seeded = _build_history_for_starting_redeemable(facade)
    session = facade.create_game_session(
        user_id=seeded["user1"].id,
        site_id=seeded["site1"].id,
        game_id=seeded["game"].id,
        session_date=date(2026, 3, 2),
        session_time="12:00:00",
        starting_balance=Decimal("150.00"),
        ending_balance=Decimal("145.00"),
        starting_redeemable=Decimal("40.00"),
        ending_redeemable=Decimal("35.00"),
    )
    closed = facade.update_game_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="13:00:00",
        ending_balance=Decimal("145.00"),
        ending_redeemable=Decimal("35.00"),
    )

    dialog = EditClosedSessionDialog(facade=facade, session=closed, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.start_total_edit.clear()
    dialog._on_start_total_edited("")
    dialog.start_redeem_edit.clear()
    dialog._on_start_redeem_edited("")
    qapp.processEvents()

    dialog.user_combo.setCurrentText(seeded["user2"].name)
    dialog.site_combo.setCurrentText(seeded["site2"].name)
    qapp.processEvents()

    expected_total_2, expected_redeem_2 = facade.compute_expected_balances(
        user_id=seeded["user2"].id,
        site_id=seeded["site2"].id,
        session_date=date.today(),
        session_time="23:59:59",
    )
    assert dialog.start_total_edit.text() == f"{float(expected_total_2):.2f}"
    assert dialog.start_redeem_edit.text() == f"{float(expected_redeem_2):.2f}"
    assert "color: #8c8c8c" in dialog.start_total_edit.styleSheet()
    assert "color: #8c8c8c" in dialog.start_redeem_edit.styleSheet()

    dialog.close()


def test_start_session_balance_check_flags_mismatch_with_indicator(qapp, facade):
    seeded = _build_history_for_starting_redeemable(facade)
    dialog = StartSessionDialog(facade=facade, parent=None)
    dialog.show()
    qapp.processEvents()

    dialog.user_combo.setCurrentText(seeded["user1"].name)
    dialog.site_combo.setCurrentText(seeded["site1"].name)
    dialog.start_total_edit.setText("149.50")
    dialog.start_redeem_edit.setText("40.00")
    qapp.processEvents()

    text = dialog.balance_check_display.text()
    assert "⚠️ Starting SC: Expected 150.00 (-0.50)" in text
    assert "✅ Starting Redeemable" in text
    assert "⚠️ Starting Redeemable" not in text
    assert dialog.balance_check_display.property("status") == "neutral"

    dialog.close()
