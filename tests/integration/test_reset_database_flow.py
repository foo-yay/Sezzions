"""
Integration smoke tests for Tools -> Reset Database flow

Prevents regressions in the reset workflow (Issue #18).
Tests that the dialog can be constructed, options can be read, and the flow
completes without exceptions in a headless environment.
"""

import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from app_facade import AppFacade
from ui.tabs.tools_tab import ToolsTab
from ui.tools_dialogs import ResetDialog


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def app_facade(tmp_path):
    """Create a test AppFacade with temporary database."""
    db_path = str(tmp_path / "test_reset.db")
    facade = AppFacade(db_path)
    yield facade
    facade.db.close()


@pytest.fixture
def tools_tab(qapp, app_facade):
    """Create ToolsTab with test facade."""
    tab = ToolsTab(app_facade)
    yield tab
    # No explicit cleanup needed


class TestResetFlowSmoke:
    """Headless smoke tests for reset database workflow."""
    
    def test_reset_dialog_construction(self, qapp):
        """ResetDialog can be constructed without exceptions."""
        table_counts = {
            'users': 5,
            'sites': 3,
            'purchases': 100
        }
        
        try:
            dialog = ResetDialog(table_counts, parent=None)
            dialog.close()
        except Exception as e:
            pytest.fail(f"ResetDialog construction failed: {e}")
    
    def test_reset_dialog_has_required_api(self, qapp):
        """ResetDialog has all required methods for reset flow."""
        table_counts = {'purchases': 10}
        dialog = ResetDialog(table_counts, parent=None)
        
        # API contract: Tools tab expects these methods
        assert hasattr(dialog, 'should_preserve_setup'), \
            "ResetDialog missing should_preserve_setup() (Issue #18)"
        assert callable(dialog.should_preserve_setup), \
            "should_preserve_setup must be callable"
        
        # Should not raise AttributeError
        try:
            preserve = dialog.should_preserve_setup()
            assert isinstance(preserve, bool)
        except AttributeError as e:
            pytest.fail(f"ResetDialog API broken: {e}")
        finally:
            dialog.close()
    
    def test_reset_dialog_button_state_no_exceptions(self, qapp):
        """ResetDialog._update_button_state() does not raise exceptions."""
        table_counts = {'purchases': 10}
        dialog = ResetDialog(table_counts, parent=None)
        
        try:
            # Should not raise AttributeError about _is_updating_size or similar
            dialog._update_button_state()
        except AttributeError as e:
            pytest.fail(f"ResetDialog._update_button_state() raised AttributeError: {e}")
        finally:
            dialog.close()
    
    def test_tools_tab_can_construct_reset_dialog(self, tools_tab):
        """Tools tab can construct ResetDialog with table counts."""
        from services.tools.reset_service import ResetService
        
        # Get table counts like the real flow does
        reset_service = ResetService(tools_tab.facade.db)
        table_counts = reset_service.get_table_counts()
        
        # Verify we can construct the dialog (doesn't require exec())
        try:
            from ui.tools_dialogs import ResetDialog
            dialog = ResetDialog(table_counts, tools_tab)
            
            # Verify API exists
            assert hasattr(dialog, 'should_preserve_setup')
            preserve = dialog.should_preserve_setup()
            assert isinstance(preserve, bool)
            
            dialog.close()
        except AttributeError as e:
            pytest.fail(f"Reset dialog API broken: {e}")
    
    def test_tools_tab_reset_service_accessible(self, tools_tab):
        """Tools tab can access ResetService without exceptions."""
        from services.tools.reset_service import ResetService
        
        try:
            reset_service = ResetService(tools_tab.facade.db)
            table_counts = reset_service.get_table_counts()
            assert isinstance(table_counts, dict)
        except Exception as e:
            pytest.fail(f"ResetService instantiation failed: {e}")
    
    def test_reset_dialog_confirmation_text_updates_button(self, qapp):
        """Typing DELETE in confirmation field enables button (when checkbox checked)."""
        table_counts = {'purchases': 10}
        dialog = ResetDialog(table_counts, parent=None)
        
        try:
            # Enable checkbox
            dialog.confirm_checkbox.setChecked(True)
            
            # Type DELETE
            dialog.type_confirm_input.setText("DELETE")
            
            # Trigger update (happens automatically via signal, but we call manually)
            dialog._update_button_state()
            
            # Button should be enabled now
            assert dialog.reset_btn.isEnabled(), \
                "Reset button should enable when checkbox + DELETE text are satisfied"
        finally:
            dialog.close()


class TestResetDialogInvariants:
    """Test invariants that prevent copy/paste regressions from other dialogs."""
    
    def test_no_restore_attributes_in_reset_dialog(self, qapp):
        """ResetDialog should not reference RestoreDialog-specific attributes."""
        table_counts = {'purchases': 10}
        dialog = ResetDialog(table_counts, parent=None)
        
        try:
            # Should NOT have restore-only attributes
            restore_only_attrs = [
                '_is_updating_size',  # RestoreDialog sizing state
                'restore_mode_group',  # RestoreDialog mode selector
                'backup_file_path',   # RestoreDialog file picker
            ]
            
            for attr in restore_only_attrs:
                assert not hasattr(dialog, attr), \
                    f"ResetDialog should not have RestoreDialog attribute: {attr}"
        finally:
            dialog.close()
    
    def test_reset_dialog_has_reset_specific_widgets(self, qapp):
        """ResetDialog should have its own specific widgets."""
        table_counts = {'purchases': 10}
        dialog = ResetDialog(table_counts, parent=None)
        
        try:
            # Reset-specific widgets
            assert hasattr(dialog, 'preserve_setup_checkbox')
            assert hasattr(dialog, 'full_reset_warning')
            assert hasattr(dialog, 'confirm_checkbox')
            assert hasattr(dialog, 'type_confirm_input')
            assert hasattr(dialog, 'reset_btn')
        finally:
            dialog.close()
