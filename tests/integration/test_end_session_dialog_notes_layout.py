"""Regression test: EndSessionDialog auto-expands when notes exist.

Bug: When ending a session that already has notes, the dialog opened too
short and the "Session Details" fields got scrunched.

We assert that when notes are pre-populated, the dialog minimum height is
bumped above the baseline.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EndSessionDialog


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_end_session_dialog_starts_collapsed_then_expands_for_notes(qtbot, temp_db_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    facade = AppFacade(temp_db_path)

    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)
    gtype = facade.create_game_type("Slots")
    game = facade.create_game("Starburst", gtype.id, rtp=96.0)

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
        notes="Some existing notes\nline 2",
        calculate_pl=False,
    )

    dialog = EndSessionDialog(facade, session)
    qtbot.addWidget(dialog)

    # Starts compact even if notes exist.
    assert dialog.notes_section.isVisible() is False
    assert dialog.notes_collapsed is True
    assert "Some existing notes" in dialog.notes_edit.toPlainText()

    dialog.show()
    qtbot.wait(50)
    collapsed_height = dialog.height()

    qtbot.mouseClick(dialog.notes_toggle, Qt.LeftButton)
    qtbot.wait(50)
    assert dialog.notes_section.isVisible() is True
    assert dialog.height() > collapsed_height
    assert dialog.height() >= dialog.minimumHeight()

    qtbot.mouseClick(dialog.notes_toggle, Qt.LeftButton)
    qtbot.wait(50)
    assert dialog.notes_section.isVisible() is False
    assert dialog.height() <= collapsed_height

    dialog.close()
    facade.db.close()
