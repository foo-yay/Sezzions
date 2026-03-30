import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app_facade import AppFacade
from desktop.ui.tabs.game_sessions_tab import EndSessionDialog, GameSessionsTab, StartSessionDialog


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _stub_message_boxes(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)


def _find_visible_dialog(dialog_type):
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, dialog_type) and widget.isVisible():
            return widget
    return None


def test_end_and_start_new_game_prefills_and_creates_new_session(qtbot, temp_db_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _stub_message_boxes(monkeypatch)

    facade = AppFacade(temp_db_path)

    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)
    gtype = facade.create_game_type("Slots")
    old_game = facade.create_game("Old Game", gtype.id, rtp=96.0)
    new_game = facade.create_game("New Game", gtype.id, rtp=96.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=old_game.id,
        session_date=date(2026, 2, 5),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("20.00"),
        ending_redeemable=Decimal("0.00"),
        purchases_during=Decimal("0.00"),
        redemptions_during=Decimal("0.00"),
        session_time="12:00:00",
        notes="",
        calculate_pl=False,
    )

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    def drive_end_dialog():
        dlg = _find_visible_dialog(EndSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive_end_dialog)
            return
        dlg.end_total_edit.setText("150.00")
        dlg.end_redeem_edit.setText("50.00")
        qtbot.mouseClick(dlg.end_and_start_btn, Qt.LeftButton)

    def drive_start_dialog():
        dlg = _find_visible_dialog(StartSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive_start_dialog)
            return

        assert dlg.user_combo.currentText() == "Test User"
        assert dlg.site_combo.currentText() == "Test Site"
        assert Decimal(dlg.start_total_edit.text()) == Decimal("150.00")
        assert Decimal(dlg.start_redeem_edit.text()) == Decimal("50.00")

        dlg.game_type_combo.setCurrentText("Slots")
        dlg.game_name_combo.setCurrentText(new_game.name)
        qtbot.mouseClick(dlg.save_btn, Qt.LeftButton)

    QTimer.singleShot(0, drive_end_dialog)
    QTimer.singleShot(0, drive_start_dialog)

    tab._end_session_by_id(session.id)

    sessions = facade.get_all_game_sessions(user_id=user.id, site_id=site.id)
    assert len(sessions) == 2

    closed = [s for s in sessions if (s.status or "Active") == "Closed"]
    active = [s for s in sessions if (s.status or "Active") != "Closed"]
    assert len(closed) == 1
    assert len(active) == 1

    closed_session = closed[0]
    new_session = active[0]

    assert closed_session.ending_balance == Decimal("150.00")
    assert closed_session.ending_redeemable == Decimal("50.00")

    assert new_session.starting_balance == Decimal("150.00")
    assert new_session.starting_redeemable == Decimal("50.00")
    assert new_session.game_id == new_game.id

    facade.db.close()


def test_end_and_start_new_game_cancel_start_creates_no_new_session(qtbot, temp_db_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _stub_message_boxes(monkeypatch)

    facade = AppFacade(temp_db_path)

    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)
    gtype = facade.create_game_type("Slots")
    game = facade.create_game("Old Game", gtype.id, rtp=96.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game.id,
        session_date=date(2026, 2, 5),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("20.00"),
        ending_redeemable=Decimal("0.00"),
        purchases_during=Decimal("0.00"),
        redemptions_during=Decimal("0.00"),
        session_time="12:00:00",
        notes="",
        calculate_pl=False,
    )

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    def drive_end_dialog():
        dlg = _find_visible_dialog(EndSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive_end_dialog)
            return
        dlg.end_total_edit.setText("150.00")
        dlg.end_redeem_edit.setText("50.00")
        qtbot.mouseClick(dlg.end_and_start_btn, Qt.LeftButton)

    def drive_start_dialog_cancel():
        dlg = _find_visible_dialog(StartSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive_start_dialog_cancel)
            return
        qtbot.mouseClick(dlg.cancel_btn, Qt.LeftButton)

    QTimer.singleShot(0, drive_end_dialog)
    QTimer.singleShot(0, drive_start_dialog_cancel)

    tab._end_session_by_id(session.id)

    sessions = facade.get_all_game_sessions(user_id=user.id, site_id=site.id)
    assert len(sessions) == 1
    assert (sessions[0].status or "Active") == "Closed"
    assert sessions[0].ending_balance == Decimal("150.00")

    facade.db.close()


def test_end_and_start_new_game_failure_injection_does_not_start_next(qtbot, temp_db_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _stub_message_boxes(monkeypatch)

    facade = AppFacade(temp_db_path)

    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)
    gtype = facade.create_game_type("Slots")
    game = facade.create_game("Old Game", gtype.id, rtp=96.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game.id,
        session_date=date(2026, 2, 5),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("20.00"),
        ending_redeemable=Decimal("0.00"),
        purchases_during=Decimal("0.00"),
        redemptions_during=Decimal("0.00"),
        session_time="12:00:00",
        notes="",
        calculate_pl=False,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(facade, "update_game_session", boom)

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    def drive_end_dialog_then_cancel():
        dlg = _find_visible_dialog(EndSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive_end_dialog_then_cancel)
            return
        dlg.end_total_edit.setText("150.00")
        dlg.end_redeem_edit.setText("50.00")
        qtbot.mouseClick(dlg.end_and_start_btn, Qt.LeftButton)
        QTimer.singleShot(0, lambda: qtbot.mouseClick(dlg.cancel_btn, Qt.LeftButton))

    QTimer.singleShot(0, drive_end_dialog_then_cancel)

    tab._end_session_by_id(session.id)

    sessions = facade.get_all_game_sessions(user_id=user.id, site_id=site.id)
    assert len(sessions) == 1
    assert (sessions[0].status or "Active") == "Active"

    facade.db.close()
