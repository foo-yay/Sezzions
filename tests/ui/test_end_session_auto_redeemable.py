from datetime import date
from decimal import Decimal
import os

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EndSessionDialog, EditClosedSessionDialog


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
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("40.00"),
        ending_redeemable=Decimal("40.00"),
    )


def _build_closed_session(facade: AppFacade):
    session = _build_open_session(facade)
    return facade.update_game_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="11:00:00",
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("40.00"),
    )


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

    dialog.end_total_edit.setText("50.00")
    qapp.processEvents()

    assert dialog.end_redeem_edit.text() == "30.00"

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

    dialog.end_total_edit.setText("50.00")
    qapp.processEvents()
    assert dialog.end_redeem_edit.text() == "30.00"

    dialog.auto_redeem_check.setChecked(False)
    qapp.processEvents()
    assert dialog.end_redeem_edit.isEnabled()

    dialog.end_redeem_edit.setText("12.34")
    qapp.processEvents()
    assert dialog.end_redeem_edit.text() == "12.34"

    dialog.close()
