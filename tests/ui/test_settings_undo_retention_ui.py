"""
UI smoke tests for configurable undo retention settings (Issue #95)

Tests Settings dialog Data section without displaying UI.
"""
import pytest
from PySide6.QtWidgets import QApplication
from unittest.mock import Mock
from app_facade import AppFacade
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication once for all tests in this module"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="module")
def app_facade():
    """Create in-memory app facade (module-scoped to amortize MainWindow setup cost)"""
    facade = AppFacade(":memory:")
    yield facade
    # Process events before closing to prevent "closed database" popup errors
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    facade.db.close()


@pytest.fixture(scope="module")
def main_window(qapp, app_facade):
    """Create main window without showing it (module-scoped to amortize 10s setup cost)"""
    window = MainWindow(app_facade)
    yield window
    window.close()
    # Process events after window close to clean up pending operations
    qapp.processEvents()


@pytest.fixture(autouse=True)
def reset_undo_state(main_window):
    """Reset undo/redo state between tests to prevent interference"""
    # Each test establishes its own initial state, but clear the undo stack to be safe
    yield
    # After each test, clear undo stack
    try:
        main_window.facade.undo_redo_service._undo_stack.clear()
        main_window.facade.undo_redo_service._redo_stack.clear()
    except Exception:
        pass  # Already closed or doesn't matter


def test_settings_dialog_has_data_section(main_window):
    """Test that Settings dialog includes Data section in navigation"""
    dialog = SettingsDialog(main_window.settings, main_window)
    
    # Check navigation list has Data section
    assert dialog.nav_list.count() == 5
    items = [dialog.nav_list.item(i).text() for i in range(dialog.nav_list.count())]
    assert "Data" in items
    
    dialog.close()


def test_settings_dialog_data_section_has_max_undo_control(main_window):
    """Test that Data section contains max undo operations spinbox"""
    dialog = SettingsDialog(main_window.settings, main_window)
    
    # Switch to Data section (index 4)
    dialog.nav_list.setCurrentRow(4)
    
    # Verify max_undo_spin exists
    assert hasattr(dialog, 'max_undo_spin')
    assert dialog.max_undo_spin is not None
    
    # Verify range
    assert dialog.max_undo_spin.minimum() == 0
    assert dialog.max_undo_spin.maximum() == 5000
    
    # Verify special text for 0
    assert dialog.max_undo_spin.specialValueText() == "Disabled"
    
    dialog.close()


def test_settings_dialog_data_section_shows_database_location_controls(main_window):
    """Test that Data section includes database path display and relocation action."""
    dialog = SettingsDialog(main_window.settings, main_window)
    dialog.nav_list.setCurrentRow(4)

    assert hasattr(dialog, "db_path_value")
    assert hasattr(dialog, "change_db_location_button")
    assert str(main_window.facade.db_path) in dialog.db_path_value.toPlainText()
    assert dialog.change_db_location_button.text() == "Change Database Location..."

    dialog.close()


def test_settings_dialog_loads_current_max_undo_value(main_window):
    """Test that Data section loads current max undo operations from service"""
    # Set a known value
    main_window.facade.undo_redo_service.set_max_undo_operations(150)
    
    dialog = SettingsDialog(main_window.settings, main_window)
    
    # Verify loaded value
    assert dialog.max_undo_spin.value() == 150
    assert dialog._initial_max_undo == 150
    
    dialog.close()


def test_settings_dialog_applies_new_max_undo_value(main_window):
    """Test that changing max undo operations applies to service"""
    # Start with 100
    main_window.facade.undo_redo_service.set_max_undo_operations(100)
    
    dialog = SettingsDialog(main_window.settings, main_window)
    
    # Change to 50 (this would normally show warning, but we're testing headless)
    dialog.max_undo_spin.setValue(200)
    
    # Mock the message box to auto-accept
    from unittest.mock import patch
    with patch('PySide6.QtWidgets.QMessageBox.question', return_value=0x00004000):  # Yes
        dialog._on_save()
    
    # Verify applied to service
    assert main_window.facade.undo_redo_service.get_max_undo_operations() == 200
    
    dialog.close()


def test_settings_dialog_warns_when_lowering_limit(main_window, qapp):
    """Test that lowering limit shows warning dialog"""
    # Start with 100
    main_window.facade.undo_redo_service.set_max_undo_operations(100)
    
    # Create some operations
    for i in range(5):
        group_id = main_window.facade.audit_service.generate_group_id()
        main_window.facade.audit_service.log_create('purchases', i+1, {'amount': f'{i*100}.00'}, group_id=group_id)
        main_window.facade.undo_redo_service.push_operation(group_id, f'Op {i+1}', '2026-02-09T10:00:00')
    
    dialog = SettingsDialog(main_window.settings, main_window)
    
    # Lower limit to 2
    dialog.max_undo_spin.setValue(2)
    
    # Mock message box and verify it's called
    from unittest.mock import patch, MagicMock
    mock_question = MagicMock(return_value=0x00010000)  # No
    
    with patch('PySide6.QtWidgets.QMessageBox.question', mock_question):
        dialog._on_save()
    
    # Verify warning was shown
    assert mock_question.called
    call_args = mock_question.call_args
    assert "permanently remove" in call_args[0][2].lower()
    assert "3 operation(s)" in call_args[0][2]
    
    # Verify save was cancelled (value unchanged)
    assert main_window.facade.undo_redo_service.get_max_undo_operations() == 100
    
    dialog.close()


def test_settings_dialog_accepts_zero_for_disabled_undo(main_window):
    """Test that setting max undo to 0 disables undo/redo"""
    dialog = SettingsDialog(main_window.settings, main_window)
    
    dialog.max_undo_spin.setValue(0)
    
    # Mock message box to accept
    from unittest.mock import patch
    with patch('PySide6.QtWidgets.QMessageBox.question', return_value=0x00004000):  # Yes
        dialog._on_save()
    
    # Verify applied
    assert main_window.facade.undo_redo_service.get_max_undo_operations() == 0
    assert not main_window.facade.undo_redo_service.can_undo()
    
    dialog.close()
