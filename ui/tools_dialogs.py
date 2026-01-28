"""
Progress dialogs for Tools operations
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QTextEdit, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal


class ProgressDialog(QDialog):
    """Modal progress dialog for long-running operations
    
    Shows progress bar, status message, and optional cancel button.
    """
    
    cancel_requested = Signal()
    
    def __init__(self, title: str, allow_cancel: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(150)
        self._allow_cancel = allow_cancel
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Status message label
        self.status_label = QLabel("Initializing...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Details label (shows current/total)
        self.details_label = QLabel("")
        self.details_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.details_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if self._allow_cancel:
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.clicked.connect(self._on_cancel_clicked)
            button_layout.addWidget(self.cancel_btn)
        else:
            self.cancel_btn = None
            
        layout.addLayout(button_layout)
        
    def update_progress(self, current: int, total: int, message: str):
        """Update progress display
        
        Args:
            current: Current item/step number (1-indexed)
            total: Total items/steps
            message: Status message to display
        """
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.details_label.setText(f"Processing {current} of {total}")
        else:
            self.progress_bar.setMaximum(0)  # Indeterminate mode
            self.details_label.setText("")
            
        self.status_label.setText(message)
        
    def set_complete(self, message: str = "Complete!"):
        """Mark operation as complete"""
        self.progress_bar.setValue(100)
        self.status_label.setText(message)
        self.details_label.setText("")
        
        if self.cancel_btn:
            self.cancel_btn.setText("Close")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.accept)
            
    def set_error(self, error_message: str):
        """Show error state"""
        self.status_label.setText("Error occurred")
        self.status_label.setStyleSheet("color: red;")
        self.details_label.setText("")
        
        if self.cancel_btn:
            self.cancel_btn.setText("Close")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.reject)
            
    def _on_cancel_clicked(self):
        """Handle cancel button click"""
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.cancel_requested.emit()


class RecalculationProgressDialog(ProgressDialog):
    """Progress dialog specifically for recalculation operations"""
    
    def __init__(self, operation_name: str = "Recalculate Everything", parent=None):
        super().__init__(f"{operation_name} - Progress", allow_cancel=True, parent=parent)


class ImportProgressDialog(ProgressDialog):
    """Progress dialog specifically for CSV import operations"""
    
    def __init__(self, entity_type: str, parent=None):
        super().__init__(f"Importing {entity_type} - Progress", allow_cancel=False, parent=parent)


class ResultDialog(QDialog):
    """Dialog to show operation results with details"""
    
    def __init__(self, title: str, message: str, details: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self._setup_ui(message, details)
        
    def _setup_ui(self, message: str, details: str):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Summary message
        summary_label = QLabel(message)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(summary_label)
        
        # Details text (if provided)
        if details:
            details_text = QTextEdit()
            details_text.setReadOnly(True)
            details_text.setPlainText(details)
            details_text.setMinimumHeight(250)
            layout.addWidget(details_text)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)


class RecalculationResultDialog(ResultDialog):
    """Dialog to show recalculation results"""
    
    def __init__(self, result, parent=None):
        """Initialize with RebuildResult object"""
        message = self._format_message(result)
        details = self._format_details(result)
        super().__init__("Recalculation Complete", message, details, parent)
        
    def _format_message(self, result) -> str:
        """Format summary message from result"""
        return (
            f"Successfully recalculated {result.pairs_processed} user/site pairs.\n"
            f"Processed {result.redemptions_processed} redemptions."
        )
        
    def _format_details(self, result) -> str:
        """Format detailed results"""
        lines = [
            f"Pairs processed: {result.pairs_processed}",
            f"Redemptions processed: {result.redemptions_processed}",
            f"Allocations created: {result.allocations_written}",
            f"Purchases updated: {result.purchases_updated}",
        ]
        
        if hasattr(result, 'game_sessions_processed') and result.game_sessions_processed > 0:
            lines.append(f"Game sessions processed: {result.game_sessions_processed}")
            
        if hasattr(result, 'errors') and result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors:
                lines.append(f"  - {error}")
                
        return "\n".join(lines)


class ImportResultDialog(ResultDialog):
    """Dialog to show CSV import results"""
    
    def __init__(self, result, entity_type: str, parent=None):
        """Initialize with ImportResult object"""
        message = self._format_message(result, entity_type)
        details = self._format_details(result)
        super().__init__(f"{entity_type} Import Complete", message, details, parent)
        
    def _format_message(self, result, entity_type: str) -> str:
        """Format summary message from result"""
        if result.success:
            total = result.records_added + result.records_updated
            return f"Successfully imported {total} {entity_type.lower()} records."
        else:
            return f"Import failed. Please review the errors below."
        
    def _format_details(self, result) -> str:
        """Format detailed results"""
        lines = [
            f"Records added: {result.records_added}",
            f"Records updated: {result.records_updated}",
            f"Records skipped: {result.records_skipped}",
        ]
        
        if result.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in result.warnings:
                lines.append(f"  - {warning}")
                
        if result.errors:
            lines.append("")
            lines.append("Errors:")
            for error in result.errors:
                lines.append(f"  - {error}")
                
        return "\n".join(lines)


class PostImportPromptDialog(QDialog):
    """Dialog prompting user to recalculate after CSV import."""
    
    def __init__(self, parent=None, import_result=None):
        super().__init__(parent)
        self.setWindowTitle("Import Complete")
        self.setModal(True)
        self.resize(450, 200)
        
        layout = QVBoxLayout()
        
        # Success message
        entity_name = import_result.entity_type.replace('_', ' ').title() if import_result and import_result.entity_type else "Records"
        message = (
            f"Successfully imported {import_result.records_added if import_result else 0} {entity_name}.\n\n"
            f"Would you like to recalculate FIFO allocations for affected user/site pairs?"
        )
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        
        # Details about affected pairs
        if import_result and (import_result.affected_user_ids or import_result.affected_site_ids):
            affected_users = len(import_result.affected_user_ids)
            affected_sites = len(import_result.affected_site_ids)
            details = f"Affected: {affected_users} users, {affected_sites} sites"
            details_label = QLabel(details)
            details_label.setStyleSheet("color: gray; font-size: 10pt;")
            layout.addWidget(details_label)
        
        # Recommendation
        recommendation = QLabel(
            "⚠️ Recommended: Recalculating ensures accurate cost basis and P/L calculations."
        )
        recommendation.setWordWrap(True)
        recommendation.setStyleSheet("color: #cc6600; font-weight: bold;")
        layout.addWidget(recommendation)
        
        # Button box
        button_box = QDialogButtonBox()
        
        recalc_button = button_box.addButton("Recalculate Now", QDialogButtonBox.AcceptRole)
        recalc_button.setDefault(True)
        
        later_button = button_box.addButton("Later", QDialogButtonBox.RejectRole)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
        self.setLayout(layout)


class RestoreDialog(QDialog):
    """Dialog for configuring database restore operation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Database")
        self.setModal(True)
        self.resize(600, 400)
        self.backup_path = None
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Warning message
        warning_label = QLabel(
            "⚠️ Restoring a database will modify your current data.\n"
            "It is strongly recommended to create a backup first."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            "background-color: #fff3cd; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 10px; color: #856404; font-weight: bold;"
        )
        layout.addWidget(warning_label)
        
        # Backup file selection
        file_group = QGroupBox("Backup File")
        file_layout = QVBoxLayout()
        
        file_select_layout = QHBoxLayout()
        self.file_path_label = QLabel("(No file selected)")
        self.file_path_label.setStyleSheet("color: #666; font-style: italic;")
        file_select_layout.addWidget(self.file_path_label, 1)
        
        select_btn = QPushButton("Choose Backup File...")
        select_btn.clicked.connect(self._on_select_file)
        file_select_layout.addWidget(select_btn)
        
        file_layout.addLayout(file_select_layout)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Restore mode selection
        mode_group = QGroupBox("Restore Mode")
        mode_layout = QVBoxLayout()
        
        # Merge mode (default)
        self.merge_radio = QPushButton()
        self.merge_radio.setCheckable(True)
        self.merge_radio.setChecked(True)
        self.merge_radio.setText("Merge (Import without deleting existing data)")
        self.merge_radio.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:checked {
                border-color: #0078d4;
                background-color: #e7f3ff;
            }
        """)
        self.merge_radio.clicked.connect(lambda: self._on_mode_changed(self.merge_radio))
        
        merge_desc = QLabel(
            "  • Imports data from backup and merges with existing records\n"
            "  • Validates data and detects duplicates (same as CSV import)\n"
            "  • Safe - does not delete existing data"
        )
        merge_desc.setStyleSheet("color: #666; font-size: 10pt; margin-left: 20px;")
        
        mode_layout.addWidget(self.merge_radio)
        mode_layout.addWidget(merge_desc)
        mode_layout.addSpacing(10)
        
        # Replace mode (destructive)
        self.replace_radio = QPushButton()
        self.replace_radio.setCheckable(True)
        self.replace_radio.setText("Replace (Delete all existing data)")
        self.replace_radio.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px;
                border: 2px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:checked {
                border-color: #dc3545;
                background-color: #f8d7da;
            }
        """)
        self.replace_radio.clicked.connect(lambda: self._on_mode_changed(self.replace_radio))
        
        replace_desc = QLabel(
            "  • Replaces entire database with backup\n"
            "  • ⚠️ DESTRUCTIVE - all current data will be lost\n"
            "  • Automatic safety backup created before replacement"
        )
        replace_desc.setStyleSheet("color: #dc3545; font-size: 10pt; margin-left: 20px; font-weight: bold;")
        
        mode_layout.addWidget(self.replace_radio)
        mode_layout.addWidget(replace_desc)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Confirmation checkbox (for replace mode)
        self.confirm_checkbox = QLabel()
        self.confirm_checkbox.setVisible(False)
        self.confirm_checkbox.setWordWrap(True)
        self.confirm_checkbox.setStyleSheet("color: #dc3545; font-weight: bold; margin: 10px;")
        layout.addWidget(self.confirm_checkbox)
        
        layout.addStretch()
        
        # Button box
        button_box = QDialogButtonBox()
        self.restore_btn = button_box.addButton("Restore", QDialogButtonBox.AcceptRole)
        self.restore_btn.setEnabled(False)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        
        button_box.accepted.connect(self._on_restore_clicked)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
    def _on_select_file(self):
        """Handle backup file selection"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File",
            "",
            "Database Files (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        
        if file_path:
            self.backup_path = file_path
            # Show abbreviated path
            display_path = file_path
            if len(display_path) > 60:
                display_path = "..." + display_path[-57:]
            self.file_path_label.setText(display_path)
            self.file_path_label.setStyleSheet("color: #000;")
            self.restore_btn.setEnabled(True)
            
    def _on_mode_changed(self, clicked_button):
        """Handle restore mode change"""
        # Toggle buttons (only one can be checked)
        if clicked_button == self.merge_radio:
            self.merge_radio.setChecked(True)
            self.replace_radio.setChecked(False)
            self.confirm_checkbox.setVisible(False)
        else:
            self.merge_radio.setChecked(False)
            self.replace_radio.setChecked(True)
            self.confirm_checkbox.setVisible(True)
            self.confirm_checkbox.setText(
                "⚠️ WARNING: This will permanently delete all existing data. "
                "A safety backup will be created automatically."
            )
            
    def _on_restore_clicked(self):
        """Handle restore button click"""
        if not self.backup_path:
            return
            
        # Additional confirmation for replace mode
        if self.replace_radio.isChecked():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.warning(
                self,
                "Confirm Database Replacement",
                "Are you absolutely sure you want to REPLACE the entire database?\n\n"
                "This will permanently delete all existing data:\n"
                "• All purchases, redemptions, and game sessions\n"
                "• All users, sites, cards, and other setup data\n"
                "• All calculations and reports\n\n"
                "A safety backup will be created first, but this action cannot be undone.\n\n"
                "Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
                
        self.accept()
        
    def get_restore_mode(self):
        """Get selected restore mode"""
        from services.tools.enums import RestoreMode
        if self.merge_radio.isChecked():
            return RestoreMode.MERGE_ALL
        else:
            return RestoreMode.REPLACE
