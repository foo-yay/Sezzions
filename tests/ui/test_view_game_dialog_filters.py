from datetime import date
from decimal import Decimal
import os

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.main_window import MainWindow
from ui.tabs.games_tab import GameViewDialog


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


def test_view_game_dialog_has_user_and_date_filters(qapp, facade):
    user = facade.create_user("Filter User")
    site = facade.create_site("Filter Site")
    game_type = facade.create_game_type("Slots")
    game = facade.create_game("Filter Game", game_type.id, rtp=95.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game.id,
        session_date=date(2026, 2, 1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00"),
    )
    facade.update_game_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="11:00:00",
        wager_amount=Decimal("50.00"),
    )

    dialog = GameViewDialog(game=game, parent=None, facade=facade)
    dialog.show()
    qapp.processEvents()

    assert hasattr(dialog, "user_filter_combo")
    assert dialog.user_filter_combo.isEditable()
    assert dialog.user_filter_combo.lineEdit().placeholderText() == "All Users"

    assert hasattr(dialog, "date_quick_combo")
    assert dialog.date_quick_combo.currentText() == "All Time"
    assert hasattr(dialog, "start_date_edit")
    assert hasattr(dialog, "end_date_edit")

    assert hasattr(dialog, "total_wager_value")
    assert dialog.total_wager_value.text().startswith("$")

    dialog.close()


def test_headless_main_window_smoke_for_view_game_filters(qapp):
    facade = AppFacade(":memory:")
    window = MainWindow(facade)
    qapp.processEvents()
    window.close()
    facade.db.close()
