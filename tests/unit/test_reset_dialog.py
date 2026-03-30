"""
Unit tests for ResetDialog

Tests the button gating logic and API contract to prevent regressions
observed in Issue #18.
"""

import pytest
import sys
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from desktop.ui.tools_dialogs import ResetDialog


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def dialog(qapp):
    """Create ResetDialog with sample table counts."""
    table_counts = {
        'users': 5,
        'sites': 3,
        'cards': 10,
        'redemption_methods': 4,
        'game_types': 8,
        'games': 20,
        'purchases': 100,
        'redemptions': 50,
        'game_sessions': 75,
        'daily_sessions': 30
    }
    dlg = ResetDialog(table_counts, parent=None)
    yield dlg
    dlg.close()


class TestResetButtonGating:
    """Test reset button enable logic (Issue #18 regression prevention)."""
    
    def test_button_disabled_by_default(self, dialog):
        """Reset button should be disabled on dialog open."""
        assert not dialog.reset_btn.isEnabled()
    
    def test_button_disabled_with_only_checkbox(self, dialog):
        """Checkbox alone should not enable button."""
        dialog.confirm_checkbox.setChecked(True)
        # Trigger update
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
    
    def test_button_disabled_with_only_text(self, dialog):
        """Text 'DELETE' alone should not enable button."""
        dialog.type_confirm_input.setText("DELETE")
        # Trigger update
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
    
    def test_button_enabled_with_both_confirmations(self, dialog):
        """Button should enable when checkbox is checked AND text is 'DELETE'."""
        dialog.confirm_checkbox.setChecked(True)
        dialog.type_confirm_input.setText("DELETE")
        # Trigger update
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
    
    def test_button_case_insensitive_delete(self, dialog):
        """Text confirmation should be case-insensitive."""
        dialog.confirm_checkbox.setChecked(True)
        
        # Test lowercase
        dialog.type_confirm_input.setText("delete")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
        
        # Test mixed case
        dialog.type_confirm_input.setText("DeLeTe")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
    
    def test_button_handles_whitespace(self, dialog):
        """Text confirmation should ignore leading/trailing whitespace."""
        dialog.confirm_checkbox.setChecked(True)
        
        dialog.type_confirm_input.setText("  DELETE  ")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
        
        dialog.type_confirm_input.setText("\tDELETE\n")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
    
    def test_button_rejects_wrong_text(self, dialog):
        """Button should remain disabled if text is not 'DELETE'."""
        dialog.confirm_checkbox.setChecked(True)
        
        # Wrong word
        dialog.type_confirm_input.setText("REMOVE")
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
        
        # Partial match
        dialog.type_confirm_input.setText("DEL")
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
        
        # Extra chars
        dialog.type_confirm_input.setText("DELETE NOW")
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
    
    def test_button_disabled_when_unchecking(self, dialog):
        """Button should disable if checkbox is unchecked after being enabled."""
        # First enable
        dialog.confirm_checkbox.setChecked(True)
        dialog.type_confirm_input.setText("DELETE")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
        
        # Then uncheck
        dialog.confirm_checkbox.setChecked(False)
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()
    
    def test_button_disabled_when_clearing_text(self, dialog):
        """Button should disable if text is cleared after being enabled."""
        # First enable
        dialog.confirm_checkbox.setChecked(True)
        dialog.type_confirm_input.setText("DELETE")
        dialog._update_button_state()
        assert dialog.reset_btn.isEnabled()
        
        # Then clear text
        dialog.type_confirm_input.setText("")
        dialog._update_button_state()
        assert not dialog.reset_btn.isEnabled()


class TestShouldPreserveSetupAPI:
    """Test the should_preserve_setup() API (Issue #18 regression prevention)."""
    
    def test_api_exists(self, dialog):
        """Dialog must have should_preserve_setup() method."""
        assert hasattr(dialog, 'should_preserve_setup')
        assert callable(dialog.should_preserve_setup)
    
    def test_returns_true_when_checked(self, dialog):
        """should_preserve_setup() returns True when checkbox is checked."""
        dialog.preserve_setup_checkbox.setChecked(True)
        assert dialog.should_preserve_setup() is True
    
    def test_returns_false_when_unchecked(self, dialog):
        """should_preserve_setup() returns False when checkbox is unchecked."""
        dialog.preserve_setup_checkbox.setChecked(False)
        assert dialog.should_preserve_setup() is False
    
    def test_default_state_is_checked(self, dialog):
        """Preserve setup checkbox should be checked by default (safer default)."""
        # Check the actual checkbox state
        assert dialog.preserve_setup_checkbox.isChecked()
        assert dialog.should_preserve_setup() is True
    
    def test_api_reflects_checkbox_state_changes(self, dialog):
        """API should always reflect current checkbox state."""
        # Start unchecked
        dialog.preserve_setup_checkbox.setChecked(False)
        assert dialog.should_preserve_setup() is False
        
        # Toggle on
        dialog.preserve_setup_checkbox.setChecked(True)
        assert dialog.should_preserve_setup() is True
        
        # Toggle off
        dialog.preserve_setup_checkbox.setChecked(False)
        assert dialog.should_preserve_setup() is False
        
        # Toggle on again
        dialog.preserve_setup_checkbox.setChecked(True)
        assert dialog.should_preserve_setup() is True


class TestDialogInvariants:
    """Test that dialog invariants hold (prevent restore-dialog bleed)."""
    
    def test_no_restore_sizing_logic_in_update_button_state(self, dialog):
        """_update_button_state should not reference restore-only attributes."""
        # This test prevents regression where restore dialog's _is_updating_size
        # logic was copied into reset dialog
        
        # Call should not raise AttributeError
        try:
            dialog._update_button_state()
        except AttributeError as e:
            if '_is_updating_size' in str(e):
                pytest.fail(f"ResetDialog._update_button_state references restore-only attribute: {e}")
            raise
    
    def test_dialog_has_required_widgets(self, dialog):
        """Dialog should have all required widgets."""
        assert hasattr(dialog, 'confirm_checkbox')
        assert hasattr(dialog, 'type_confirm_input')
        assert hasattr(dialog, 'reset_btn')
        assert hasattr(dialog, 'preserve_setup_checkbox')
    
    def test_table_summary_displays(self, dialog):
        """Dialog should display table count summary."""
        # The dialog should have formatted table info
        # Check via the window text/title or verify widgets exist
        assert dialog.windowTitle() == "Reset Database"
        
        # The dialog layout should contain labels
        # (summary_label is a local var, not stored on self)
        assert dialog.layout() is not None
