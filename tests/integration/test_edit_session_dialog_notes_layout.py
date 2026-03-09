"""Regression tests: Session edit dialogs start with notes collapsed.

We want consistent behavior across End Session / Edit Session / Edit Closed Session:
- Notes start collapsed (even if notes exist) so the dialog opens compact.
- Clicking the notes toggle expands and increases dialog height.
- Clicking again collapses and shrinks back.
"""

import os
import tempfile
from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt

from app_facade import AppFacade
from ui.tabs.game_sessions_tab import EditClosedSessionDialog, EditSessionDialog


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _seed_session_with_notes(facade: AppFacade):
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
    return session


def _seed_closed_session_without_game_metadata(facade: AppFacade):
    user = facade.create_user("No Game User")
    site = facade.create_site("No Game Site", "https://example.com/no-game", sc_rate=1.0)

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        game_type_id=None,
        session_date=date(2026, 1, 20),
        starting_balance=Decimal("50.00"),
        ending_balance=Decimal("25.00"),
        starting_redeemable=Decimal("50.00"),
        ending_redeemable=Decimal("25.00"),
        session_time="13:00:00",
        notes="",
        calculate_pl=False,
    )
    return session


def test_edit_session_dialog_starts_collapsed_then_expands(qtbot, temp_db_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    facade = AppFacade(temp_db_path)
    session = _seed_session_with_notes(facade)

    dialog = EditSessionDialog(facade, session)
    qtbot.addWidget(dialog)

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

    qtbot.mouseClick(dialog.notes_toggle, Qt.LeftButton)
    qtbot.wait(50)
    assert dialog.notes_section.isVisible() is False
    assert dialog.height() <= collapsed_height

    dialog.close()
    facade.db.close()


def test_edit_closed_session_dialog_starts_collapsed_then_expands(qtbot, temp_db_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    facade = AppFacade(temp_db_path)
    session = _seed_session_with_notes(facade)

    dialog = EditClosedSessionDialog(facade, session)
    qtbot.addWidget(dialog)

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

    qtbot.mouseClick(dialog.notes_toggle, Qt.LeftButton)
    qtbot.wait(50)
    assert dialog.notes_section.isVisible() is False
    assert dialog.height() <= collapsed_height

    dialog.close()
    facade.db.close()


def test_edit_closed_session_dialog_no_game_type_does_not_default_first_option(qtbot, temp_db_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    facade = AppFacade(temp_db_path)
    facade.create_game_type("Blackjack")
    facade.create_game_type("Slots")
    session = _seed_closed_session_without_game_metadata(facade)

    dialog = EditClosedSessionDialog(facade, session)
    qtbot.addWidget(dialog)

    assert dialog.game_type_combo.currentText().strip() == ""
    assert dialog.game_name_combo.currentText().strip() == ""

    dialog.close()
    facade.db.close()
