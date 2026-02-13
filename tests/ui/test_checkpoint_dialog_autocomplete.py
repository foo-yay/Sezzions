"""Regression test for Checkpoint dialog autocomplete/autofill behavior."""

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.adjustment_dialogs import CheckpointDialog, BasisAdjustmentDialog


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


def test_checkpoint_dialog_resolves_user_site_from_text(qapp, facade):
    user = facade.create_user("Test User")
    site = facade.create_site("Test Site", "https://example.com", sc_rate=1.0)

    dialog = CheckpointDialog(facade, parent=None)

    dialog.user_combo.setEditText("test user")
    dialog.site_combo.setEditText("TEST SITE")
    dialog.date_edit.setText("01/02/26")
    dialog.time_edit.setText("10:00")
    dialog.total_sc_input.setText("2700")
    dialog.reason_input.setText("Correction")

    assert dialog._validate_inline() is True

    dialog._on_create()
    assert dialog.adjustment is not None
    assert dialog.adjustment.user_id == user.id
    assert dialog.adjustment.site_id == site.id

    dialog.close()


def test_basis_adjustment_dialog_resolves_user_site_from_text(qapp, facade):
    user = facade.create_user("Basis User")
    site = facade.create_site("Basis Site", "https://example.com", sc_rate=1.0)

    dialog = BasisAdjustmentDialog(facade, parent=None)

    dialog.user_combo.setEditText("basis user")
    dialog.site_combo.setEditText("BASIS SITE")
    dialog.date_edit.setText("01/02/26")
    dialog.time_edit.setText("10:00")
    dialog.delta_input.setText("-20.00")
    dialog.reason_input.setText("Correction")

    assert dialog._validate_inline() is True

    dialog._on_create()
    assert dialog.adjustment is not None
    assert dialog.adjustment.user_id == user.id
    assert dialog.adjustment.site_id == site.id

    dialog.close()
