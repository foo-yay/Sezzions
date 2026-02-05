"""Regression test: EndSessionDialog displays Game Type.

Bug: Game type chip was blank/"—" because EndSessionDialog queried
non-existent repo attributes on AppFacade (game_type_repo/list_all).

This verifies the dialog uses AppFacade APIs and shows correct names.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6 import QtCore

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EndSessionDialog


@pytest.fixture
def temp_db_path():
    """Temporary database for headless UI tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_end_session_dialog_shows_game_type_and_game(qtbot, temp_db_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    facade = AppFacade(temp_db_path)

    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)
    game_type = facade.create_game_type("Slots")
    game = facade.create_game("Starburst", game_type.id, rtp=96.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=game.id,
        session_date=date(2026, 1, 15),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("100.00"),
        ending_redeemable=Decimal("0.00"),
        session_time="12:00:00",
        notes="",
        calculate_pl=False,
    )

    dialog = EndSessionDialog(facade, session)
    qtbot.addWidget(dialog)
    dialog.show()

    QtCore.QCoreApplication.processEvents()

    assert dialog.game_type_display.text() == game_type.name
    assert dialog.game_display.text() == game.name

    dialog.close()
    facade.db.close()
