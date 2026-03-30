"""
Headless UI smoke test for Settings dialog (Issue #31).

Boots a QApplication, instantiates MainWindow, verifies:
- Gear icon exists and is accessible
- Settings dialog can open and close without errors
"""
import os
import tempfile
import pytest
from PySide6 import QtWidgets, QtCore
from app_facade import AppFacade
from desktop.ui.main_window import MainWindow


@pytest.fixture
def temp_db_path():
    """Temporary database for headless UI tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_settings_gear_and_dialog_open_close(qtbot, temp_db_path):
    """
    Headless smoke test: gear icon exists, Settings dialog can open/close.
    """
    # Setup
    facade = AppFacade(temp_db_path)
    window = MainWindow(facade)
    qtbot.addWidget(window)
    
    # Process pending events
    QtCore.QCoreApplication.processEvents()
    
    # 1. Core tabs should be available
    assert hasattr(window, "redemptions_tab"), "MainWindow should have redemptions_tab"

    # 2. Gear icon should exist and be accessible
    assert hasattr(window, "_settings_gear"), "MainWindow should have _settings_gear attribute"
    gear = window._settings_gear
    assert gear is not None, "Settings gear button should exist"
    assert gear.isVisible() or gear.parent() is not None, "Settings gear should be visible or parented"
    
    # 3. Trigger gear action (simulate click)
    # The gear should open a Settings dialog
    # We'll use QTimer to close it immediately after opening
    dialog_opened = []
    
    def check_for_dialog():
        """Check if Settings dialog opened and close it."""
        # Find any QDialog that looks like Settings
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(widget, QtWidgets.QDialog) and widget.isVisible():
                if "Settings" in widget.windowTitle() or widget.objectName() == "SettingsDialog":
                    dialog_opened.append(widget)
                    widget.close()
                    return
    
    # Schedule dialog check after click
    QtCore.QTimer.singleShot(100, check_for_dialog)
    
    # Simulate gear click
    gear.click()
    
    # Process events to allow dialog to open and be checked
    qtbot.wait(200)
    
    # 4. Verify dialog opened
    assert len(dialog_opened) > 0, "Settings dialog should have opened after gear click"
    
    # Cleanup
    window.close()
    facade.db.close()
