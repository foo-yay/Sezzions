import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EndSessionDialog, GameSessionsTab, StartSessionDialog


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def facade(temp_db_path):
    app = AppFacade(temp_db_path)
    yield app
    app.db.close()


def _find_visible_dialog(dialog_type):
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, dialog_type) and widget.isVisible():
            return widget
    return None


def _seed_low_balance_session(
    facade: AppFacade,
    *,
    sc_rate: float = 1.0,
    purchase_amount: Decimal = Decimal("20.00"),
    remaining_basis: Decimal = Decimal("20.00"),
    session_date: date = date(2026, 3, 25),
):
    user = facade.create_user("Prompt User")
    site = facade.create_site("Prompt Site", "https://example.com", sc_rate=sc_rate)
    game_type = facade.create_game_type("Slots")
    game = facade.create_game("Prompt Game", game_type.id, rtp=96.0)

    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, status)
        VALUES
            (?, ?, ?, '09:00:00', ?, ?, ?, 'active')
        """,
        (
            user.id,
            site.id,
            (session_date).isoformat(),
            str(purchase_amount),
            str(purchase_amount),
            str(remaining_basis),
        ),
    )
    facade.db.commit()

    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time,
             starting_balance, ending_balance, starting_redeemable, ending_redeemable,
             purchases_during, redemptions_during, notes, status)
        VALUES
            (?, ?, ?, ?, '10:00:00', ?, 0.00, 0.00, 0.00, 0.00, 0.00, '', 'Active')
        """,
        (
            user.id,
            site.id,
            game.id,
            session_date.isoformat(),
            str(purchase_amount),
        ),
    )
    facade.db.commit()
    session = facade.get_game_session(1)
    return user, site, session


def _drive_end_session_dialog(qtbot, *, end_total: str, end_redeem: str, start_new: bool = False):
    def drive():
        dlg = _find_visible_dialog(EndSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, drive)
            return
        dlg.end_total_edit.setText(end_total)
        dlg.end_redeem_edit.setText(end_redeem)
        target = dlg.end_and_start_btn if start_new else dlg.save_btn
        qtbot.mouseClick(target, Qt.LeftButton)

    QTimer.singleShot(0, drive)


def test_low_balance_prompt_context_uses_sc_rate_threshold(facade):
    user, site, _session = _seed_low_balance_session(
        facade,
        sc_rate=0.01,
        purchase_amount=Decimal("150.00"),
        remaining_basis=Decimal("150.00"),
    )

    prompt = facade.get_low_balance_close_prompt_data(
        site_id=site.id,
        user_id=user.id,
        ending_total_sc=Decimal("99.99"),
    )
    assert prompt is not None
    assert prompt["current_value"] < Decimal("1.00")

    no_prompt = facade.get_low_balance_close_prompt_data(
        site_id=site.id,
        user_id=user.id,
        ending_total_sc=Decimal("100.00"),
    )
    assert no_prompt is None


def test_confirmed_low_balance_prompt_reuses_basis_close_path(qtbot, facade, monkeypatch):
    _seed_low_balance_session(facade, remaining_basis=Decimal("20.00"))

    prompts = []
    infos = []
    warnings = []

    monkeypatch.setattr(QMessageBox, "question", lambda _p, _t, message: prompts.append(message) or QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda _p, title, message: infos.append((title, message)) or QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, title, message: warnings.append((title, message)) or QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected critical dialog")))

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    _drive_end_session_dialog(qtbot, end_total="0.40", end_redeem="0.40")
    tab._end_session_by_id(1)

    assert prompts, "Expected low-balance close prompt"
    assert "below the $1.00 equivalent close threshold" in prompts[0]
    assert "Remaining basis: $20.00" in prompts[0]
    assert not warnings

    session = facade.get_game_session(1)
    assert (session.status or "") == "Closed"

    redemption = facade.db.fetch_one(
        "SELECT amount, more_remaining, notes FROM redemptions ORDER BY id DESC LIMIT 1"
    )
    assert Decimal(str(redemption["amount"])) == Decimal("0.00")
    assert redemption["more_remaining"] == 0
    assert redemption["notes"].startswith("Balance Closed - Net Loss: $20.00")

    realized = facade.db.fetch_one(
        "SELECT cost_basis, payout, net_pl FROM realized_transactions ORDER BY id DESC LIMIT 1"
    )
    assert Decimal(str(realized["cost_basis"])) == Decimal("20.00")
    assert Decimal(str(realized["payout"])) == Decimal("0.00")
    assert Decimal(str(realized["net_pl"])) == Decimal("-20.00")
    assert infos and "Position also closed" in infos[-1][1]


def test_confirmed_low_balance_prompt_reuses_zero_basis_close_path(qtbot, facade, monkeypatch):
    _seed_low_balance_session(facade, remaining_basis=Decimal("0.00"))

    prompts = []
    infos = []

    monkeypatch.setattr(QMessageBox, "question", lambda _p, _t, message: prompts.append(message) or QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda _p, title, message: infos.append((title, message)) or QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected critical dialog")))

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    _drive_end_session_dialog(qtbot, end_total="0.14", end_redeem="0.14")
    tab._end_session_by_id(1)

    assert prompts
    assert "No FIFO basis change" in prompts[0]

    redemption = facade.db.fetch_one(
        "SELECT amount, more_remaining, notes FROM redemptions ORDER BY id DESC LIMIT 1"
    )
    assert Decimal(str(redemption["amount"])) == Decimal("0.00")
    assert redemption["more_remaining"] == 1
    assert redemption["notes"].startswith("Balance Closed - Net Loss: $0.00")

    realized_count = facade.db.fetch_one(
        "SELECT COUNT(*) AS count FROM realized_transactions"
    )["count"]
    assert realized_count == 0
    assert infos and "No cash flow loss recorded" in infos[-1][1]


def test_declining_low_balance_prompt_keeps_session_closed_without_position_close(qtbot, facade, monkeypatch):
    _seed_low_balance_session(facade, remaining_basis=Decimal("20.00"))

    prompts = []
    infos = []

    monkeypatch.setattr(QMessageBox, "question", lambda _p, _t, message: prompts.append(message) or QMessageBox.No)
    monkeypatch.setattr(QMessageBox, "information", lambda _p, title, message: infos.append((title, message)) or QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Unexpected critical dialog")))

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    _drive_end_session_dialog(qtbot, end_total="0.40", end_redeem="0.40")
    tab._end_session_by_id(1)

    assert prompts
    session = facade.get_game_session(1)
    assert (session.status or "") == "Closed"
    redemption_count = facade.db.fetch_one("SELECT COUNT(*) AS count FROM redemptions")["count"]
    assert redemption_count == 0
    assert infos and infos[-1][1] == "Session closed successfully!"


def test_end_and_start_new_skips_low_balance_prompt(qtbot, facade, monkeypatch):
    _seed_low_balance_session(facade, remaining_basis=Decimal("20.00"))

    prompts = []
    monkeypatch.setattr(QMessageBox, "question", lambda _p, _t, message: prompts.append(message) or QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)

    tab = GameSessionsTab(facade)
    qtbot.addWidget(tab)

    def cancel_start_dialog():
        dlg = _find_visible_dialog(StartSessionDialog)
        if dlg is None:
            QTimer.singleShot(10, cancel_start_dialog)
            return
        qtbot.mouseClick(dlg.cancel_btn, Qt.LeftButton)

    _drive_end_session_dialog(qtbot, end_total="0.40", end_redeem="0.40", start_new=True)
    QTimer.singleShot(0, cancel_start_dialog)
    tab._end_session_by_id(1)

    assert prompts == []
    session = facade.get_game_session(1)
    assert (session.status or "") == "Closed"
