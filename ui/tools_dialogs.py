"""
Progress dialogs for Tools operations
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QTextEdit, QDialogButtonBox,
    QGroupBox, QCheckBox, QLineEdit, QComboBox, QStackedWidget, QWidget, QScrollArea, QSizePolicy, QLayout
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QFontMetrics


class _AdaptiveStackedWidget(QStackedWidget):
    """A QStackedWidget that sizes itself to the current page.

    Qt's default QStackedWidget sizeHint tends to reflect the largest page, which
    causes dialogs to stay tall after visiting a larger page.
    """

    def sizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # type: ignore[override]
        current = self.currentWidget()
        return current.minimumSizeHint() if current is not None else super().minimumSizeHint()


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
        self.setMinimumWidth(640)
        self.setSizeGripEnabled(False)
        self.backup_path: str | None = None
        self._setup_ui()
        # Defer initial sizing until after the dialog is laid out.
        QTimer.singleShot(0, self.adjustSize)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "backup_path_display"):
            self._set_backup_file_display(self.backup_path)
        
    def _setup_ui(self):
        """Setup the UI components"""
        from services.tools.enums import RestoreMode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Warning message
        warning_label = QLabel(
            "⚠️ Restoring a database will modify your current data.\n"
            "It is strongly recommended to create a backup first."
        )
        warning_label.setWordWrap(True)
        warning_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        warning_label.setStyleSheet(
            "background-color: #fff3cd; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 10px; color: #856404; font-weight: bold;"
        )
        layout.addWidget(warning_label)

        # Backup file selection (global section styling)
        backup_container = QWidget()
        backup_container_layout = QVBoxLayout(backup_container)
        backup_container_layout.setContentsMargins(0, 0, 0, 0)
        backup_container_layout.setSpacing(6)

        backup_header = QLabel("💾 Backup File")
        backup_header.setObjectName("SectionHeader")
        backup_container_layout.addWidget(backup_header)

        backup_section = QWidget()
        backup_section.setObjectName("SectionBackground")
        backup_section_layout = QVBoxLayout(backup_section)
        backup_section_layout.setContentsMargins(12, 12, 12, 12)
        backup_section_layout.setSpacing(8)

        file_select_layout = QHBoxLayout()
        file_select_layout.setContentsMargins(0, 0, 0, 0)
        file_select_layout.setSpacing(8)

        self.backup_path_display = QLabel("Not set")
        self.backup_path_display.setObjectName("InfoField")
        self.backup_path_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backup_path_display.setToolTip("Select a backup file")
        self.backup_path_display.setMinimumWidth(360)
        file_select_layout.addWidget(self.backup_path_display, 1)

        select_btn = QPushButton("📂 Browse")
        select_btn.clicked.connect(self._on_select_file)
        file_select_layout.addWidget(select_btn)

        backup_section_layout.addLayout(file_select_layout)
        backup_container_layout.addWidget(backup_section)
        layout.addWidget(backup_container)

        # Restore mode selection (compact + global section styling)
        mode_container = QWidget()
        mode_container_layout = QVBoxLayout(mode_container)
        mode_container_layout.setContentsMargins(0, 0, 0, 0)
        mode_container_layout.setSpacing(6)

        mode_header = QLabel("♻️ Restore Mode")
        mode_header.setObjectName("SectionHeader")
        mode_container_layout.addWidget(mode_header)

        mode_section = QWidget()
        mode_section.setObjectName("SectionBackground")
        mode_layout = QVBoxLayout(mode_section)
        mode_layout.setContentsMargins(12, 12, 12, 12)
        mode_layout.setSpacing(10)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Select restore mode…", None)
        self.mode_combo.addItem(
            "Merge (Import without deleting existing data)",
            RestoreMode.MERGE_ALL,
        )
        self.mode_combo.addItem(
            "Merge Selected (Import from specific tables)",
            RestoreMode.MERGE_SELECTED,
        )
        self.mode_combo.addItem(
            "Replace (Delete and replace all existing data)",
            RestoreMode.REPLACE,
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        mode_layout.addWidget(self.mode_combo)

        self.mode_stack = _AdaptiveStackedWidget()

        # Page 0: placeholder
        placeholder_page = QWidget()
        placeholder_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        placeholder_layout = QVBoxLayout(placeholder_page)
        placeholder_hint = QLabel("Select a restore mode to see details.")
        placeholder_hint.setObjectName("HelperText")
        placeholder_layout.addWidget(placeholder_hint)
        placeholder_layout.addStretch()
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_stack.addWidget(placeholder_page)

        # Page 1: MERGE_ALL
        merge_page = QWidget()
        merge_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        merge_layout = QVBoxLayout(merge_page)
        merge_desc = QLabel(
            "• Imports data from backup and merges with existing records\n"
            "• Validates data and detects duplicates (same as CSV import)\n"
            "• Safe — does not delete existing data"
        )
        merge_desc.setObjectName("HelperText")
        merge_desc.setWordWrap(True)
        merge_layout.addWidget(merge_desc)
        merge_layout.addStretch()
        merge_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_stack.addWidget(merge_page)

        # Page 2: MERGE_SELECTED
        merge_selected_page = QWidget()
        merge_selected_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        merge_selected_layout = QVBoxLayout(merge_selected_page)
        merge_selected_desc = QLabel(
            "• Select specific tables to merge from backup\n"
            "• Fine-grained control over what data to restore\n"
            "• Validates foreign key constraints"
        )
        merge_selected_desc.setObjectName("HelperText")
        merge_selected_desc.setWordWrap(True)
        merge_selected_layout.addWidget(merge_selected_desc)

        self.table_checkboxes = {}

        table_selection_group = QGroupBox("Select Tables to Merge")
        table_selection_group_layout = QVBoxLayout()

        columns_layout = QHBoxLayout()

        # Setup tables (left column)
        setup_group = QGroupBox("Setup")
        setup_group_layout = QVBoxLayout()
        setup_tables = ['users', 'sites', 'cards', 'game_types', 'games', 'redemption_methods']
        for table in setup_tables:
            cb = QCheckBox(table.replace('_', ' ').title())
            cb.setProperty('table_name', table)
            cb.toggled.connect(self._update_restore_button_state)
            setup_group_layout.addWidget(cb)
            self.table_checkboxes[table] = cb
        setup_group_layout.addStretch()
        setup_group.setLayout(setup_group_layout)
        columns_layout.addWidget(setup_group, 1)

        # Transaction tables (right column)
        transaction_group = QGroupBox("Transactions")
        transaction_group_layout = QVBoxLayout()
        transaction_tables = ['purchases', 'redemptions', 'game_sessions', 'daily_sessions', 'expenses', 'realized_transactions']
        for table in transaction_tables:
            cb = QCheckBox(table.replace('_', ' ').title())
            cb.setProperty('table_name', table)
            cb.toggled.connect(self._update_restore_button_state)
            transaction_group_layout.addWidget(cb)
            self.table_checkboxes[table] = cb
        transaction_group_layout.addStretch()
        transaction_group.setLayout(transaction_group_layout)
        columns_layout.addWidget(transaction_group, 1)

        columns_container = QWidget()
        columns_container.setLayout(columns_layout)
        columns_container.setStyleSheet("background: transparent;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(columns_container)
        scroll.setMinimumHeight(160)
        scroll.setMaximumHeight(220)
        table_selection_group_layout.addWidget(scroll)

        select_buttons_layout = QHBoxLayout()
        select_buttons_layout.addStretch()
        select_all_btn = QPushButton("✅ Select All")
        select_all_btn.clicked.connect(self._select_all_tables)
        deselect_all_btn = QPushButton("🚫 Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all_tables)
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(deselect_all_btn)
        table_selection_group_layout.addLayout(select_buttons_layout)

        table_selection_group.setLayout(table_selection_group_layout)
        merge_selected_layout.addWidget(table_selection_group)
        merge_selected_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_stack.addWidget(merge_selected_page)

        # Page 3: REPLACE
        replace_page = QWidget()
        replace_page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        replace_layout = QVBoxLayout(replace_page)
        replace_desc = QLabel(
            "• Replaces entire database with backup\n"
            "• ⚠️ DESTRUCTIVE — all current data will be lost\n"
            "• Automatic safety backup created before replacement"
        )
        replace_desc.setStyleSheet("color: #dc3545; font-size: 10pt; font-weight: bold;")
        replace_desc.setWordWrap(True)
        replace_layout.addWidget(replace_desc)
        replace_layout.addStretch()
        replace_layout.setContentsMargins(0, 0, 0, 0)
        self.mode_stack.addWidget(replace_page)

        mode_layout.addWidget(self.mode_stack)
        mode_container_layout.addWidget(mode_section)
        layout.addWidget(mode_container)
        
        # Button box
        button_box = QDialogButtonBox()
        self.restore_btn = button_box.addButton("♻️ Restore", QDialogButtonBox.AcceptRole)
        self.restore_btn.setObjectName("PrimaryButton")
        self.restore_btn.setEnabled(False)
        cancel_btn = button_box.addButton("✖️ Cancel", QDialogButtonBox.RejectRole)
        
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
            self._set_backup_file_display(file_path)
            self._update_restore_button_state()
            QTimer.singleShot(0, self.adjustSize)

    def _set_backup_file_display(self, file_path: str | None):
        """Set backup file display with elided (middle) path and tooltip."""
        file_path = file_path or ""
        if not file_path:
            self.backup_path_display.setText("Not set")
            self.backup_path_display.setToolTip("Select a backup file")
            return

        self.backup_path_display.setToolTip(file_path)
        metrics = QFontMetrics(self.backup_path_display.font())
        width = max(160, self.backup_path_display.width() - 16)
        elided = metrics.elidedText(file_path, Qt.ElideMiddle, width)
        self.backup_path_display.setText(elided)

    def _on_mode_combo_changed(self, _index: int):
        """Handle restore mode selection change."""
        from services.tools.enums import RestoreMode

        mode = self.get_restore_mode()
        if mode == RestoreMode.MERGE_ALL:
            self.mode_stack.setCurrentIndex(1)
        elif mode == RestoreMode.MERGE_SELECTED:
            self.mode_stack.setCurrentIndex(2)
        elif mode == RestoreMode.REPLACE:
            self.mode_stack.setCurrentIndex(3)
        else:
            self.mode_stack.setCurrentIndex(0)

        self._update_restore_button_state()
        # Force Qt to recalculate the dialog size to fit the new page
        QTimer.singleShot(0, self._resize_to_content)
    
    def _resize_to_content(self):
        """Resize dialog to fit current content."""
        # Clear any height locks
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        
        # Calculate the exact height needed:
        # - layout margins (top + bottom)
        # - warning label height
        # - spacing between widgets
        # - backup section height  
        # - mode section height (with current page)
        # - button box height
        
        layout_margins = self.layout().contentsMargins()
        total_height = layout_margins.top() + layout_margins.bottom()
        
        # Add each widget's height plus spacing
        for i in range(self.layout().count()):
            item = self.layout().itemAt(i)
            if item and item.widget():
                widget = item.widget()
                total_height += widget.sizeHint().height()
                if i < self.layout().count() - 1:
                    total_height += self.layout().spacing()
        
        # Set the calculated height
        self.resize(self.width(), total_height)

    def _update_restore_button_state(self):
        """Enable Restore only when inputs are valid."""
        from services.tools.enums import RestoreMode

        if not self.backup_path:
            self.restore_btn.setEnabled(False)
            return

        mode = self.get_restore_mode()
        if mode is None:
            self.restore_btn.setEnabled(False)
            return

        if mode == RestoreMode.MERGE_SELECTED and not self.get_selected_tables():
            self.restore_btn.setEnabled(False)
            return

        self.restore_btn.setEnabled(True)
            
    def _on_restore_clicked(self):
        """Handle restore button click"""
        if not self.backup_path:
            return

        mode = self.get_restore_mode()
        if mode is None:
            return

        from services.tools.enums import RestoreMode
        
        # Validate MERGE_SELECTED mode has at least one table selected
        if mode == RestoreMode.MERGE_SELECTED:
            selected_tables = self.get_selected_tables()
            if not selected_tables:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "No Tables Selected",
                    "Please select at least one table to merge.",
                    QMessageBox.Ok
                )
                return
            
        # Additional confirmation for replace mode
        if mode == RestoreMode.REPLACE:
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
    
    def _select_all_tables(self):
        """Select all table checkboxes"""
        for cb in self.table_checkboxes.values():
            cb.setChecked(True)
        self._update_restore_button_state()
    
    def _deselect_all_tables(self):
        """Deselect all table checkboxes"""
        for cb in self.table_checkboxes.values():
            cb.setChecked(False)
        self._update_restore_button_state()
    
    def get_selected_tables(self):
        """Get list of selected table names (for MERGE_SELECTED mode)"""
        return [name for name, cb in self.table_checkboxes.items() if cb.isChecked()]
        
    def get_restore_mode(self):
        """Get selected restore mode"""
        return self.mode_combo.currentData()


class ResetDialog(QDialog):
    """Dialog for configuring database reset operation."""
    
    def __init__(self, table_counts: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reset Database")
        self.setModal(True)
        self.resize(600, 500)
        self.table_counts = table_counts
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Critical warning message
        warning_label = QLabel(
            "⚠️ CRITICAL WARNING: Database Reset is Irreversible\n\n"
            "This will permanently DELETE data from your database.\n"
            "Create a backup before proceeding."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            "background-color: #f8d7da; border: 2px solid #dc3545; "
            "border-radius: 4px; padding: 15px; color: #721c24; "
            "font-weight: bold; font-size: 11pt;"
        )
        layout.addWidget(warning_label)
        
        # Current data summary
        summary_group = QGroupBox("Current Database State")
        summary_layout = QVBoxLayout()
        
        summary_text = QLabel(self._format_table_summary())
        summary_text.setWordWrap(True)
        summary_text.setStyleSheet("font-family: 'Courier New', Courier, monospace; font-size: 10pt;")
        summary_layout.addWidget(summary_text)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Reset options
        options_group = QGroupBox("Reset Options")
        options_layout = QVBoxLayout()
        
        # Preserve setup data checkbox
        self.preserve_setup_checkbox = QCheckBox(
            "Preserve setup data (users, sites, cards, game types, etc.)"
        )
        self.preserve_setup_checkbox.setChecked(True)  # Default to safer option
        self.preserve_setup_checkbox.toggled.connect(self._on_preserve_changed)
        options_layout.addWidget(self.preserve_setup_checkbox)
        
        preserve_help = QLabel(
            "  ✓ Recommended for most cases\n"
            "  • Deletes only transactional data (purchases, redemptions, sessions)\n"
            "  • Keeps your users, sites, cards, and other setup configured"
        )
        preserve_help.setStyleSheet("color: #666; font-size: 9pt; margin-left: 20px;")
        options_layout.addWidget(preserve_help)
        
        options_layout.addSpacing(10)
        
        # Full reset warning
        self.full_reset_warning = QLabel(
            "⚠️ FULL RESET: Will delete ALL data including users, sites, cards, etc.\n"
            "You will need to reconfigure everything from scratch."
        )
        self.full_reset_warning.setWordWrap(True)
        self.full_reset_warning.setStyleSheet(
            "background-color: #fff3cd; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 10px; color: #856404; font-weight: bold;"
        )
        self.full_reset_warning.setVisible(False)
        options_layout.addWidget(self.full_reset_warning)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Safety confirmation
        confirm_group = QGroupBox("Confirmation Required")
        confirm_layout = QVBoxLayout()
        
        self.confirm_checkbox = QCheckBox(
            "I understand this will permanently delete data and cannot be undone"
        )
        self.confirm_checkbox.setStyleSheet("font-weight: bold; color: #dc3545;")
        self.confirm_checkbox.toggled.connect(self._update_button_state)
        confirm_layout.addWidget(self.confirm_checkbox)
        
        self.type_confirm_label = QLabel("Type DELETE to confirm:")
        self.type_confirm_input = QLineEdit()
        self.type_confirm_input.setPlaceholderText("Type DELETE here")
        self.type_confirm_input.textChanged.connect(self._update_button_state)
        confirm_layout.addWidget(self.type_confirm_label)
        confirm_layout.addWidget(self.type_confirm_input)
        
        confirm_group.setLayout(confirm_layout)
        layout.addWidget(confirm_group)
        
        layout.addStretch()
        
        # Button box
        button_box = QDialogButtonBox()
        self.reset_btn = button_box.addButton("Reset Database", QDialogButtonBox.AcceptRole)
        self.reset_btn.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; font-weight: bold; "
            "padding: 8px 16px; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.reset_btn.setEnabled(False)
        cancel_btn = button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        
    def _format_table_summary(self):
        """Format table counts for display"""
        if not self.table_counts:
            return "No data in database."
            
        lines = []
        total_records = 0
        
        # Setup tables
        setup_count = sum(
            count for table, count in self.table_counts.items()
            if table in ['users', 'sites', 'cards', 'redemption_methods', 'game_types', 'games']
        )
        if setup_count > 0:
            lines.append(f"Setup Data: {setup_count:,} records")
        
        # Transaction tables
        transaction_count = sum(
            count for table, count in self.table_counts.items()
            if table in ['purchases', 'redemptions', 'game_sessions', 'daily_sessions', 'expenses']
        )
        if transaction_count > 0:
            lines.append(f"Transaction Data: {transaction_count:,} records")
        
        total_records = sum(self.table_counts.values())
        lines.append(f"\nTotal Records: {total_records:,}")
        
        return "\n".join(lines)
        
    def _on_preserve_changed(self, checked):
        """Handle preserve setup data checkbox change"""
        self.full_reset_warning.setVisible(not checked)
        
    def _update_button_state(self):
        """Enable reset button only when all confirmations are complete"""
        if self._is_updating_size:
            return
        self._is_updating_size = True
        try:
            # Lock width during auto-resize so wrapped labels (warning, helper text)
            # don't change line breaks between mode switches.
            target_width = max(self.minimumWidth(), self.width() or 0)
            if target_width <= 0:
                target_width = self.minimumWidth()
            self.setMinimumWidth(target_width)
            self.setMaximumWidth(target_width)

            # Relax any previous fixed height before recomputing; otherwise the dialog can
            # get "stuck" at the previous page's height (e.g., switching away from MERGE_SELECTED).
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)

            # Force the details area to match the current page (Qt otherwise tends to
            # reserve the max height across all pages).
            current = self.mode_stack.currentWidget()
            if current is not None:
                current.adjustSize()
                self.mode_stack.setFixedHeight(max(0, current.sizeHint().height()))
            else:
                self.mode_stack.setFixedHeight(0)

            self.mode_stack.updateGeometry()
            self.layout().activate()
            self.adjustSize()

            # Snap to the content-driven height after the stack updates.
            self.resize(target_width, self.sizeHint().height())
            self.setFixedHeight(self.sizeHint().height())
        finally:
            self._is_updating_size = False
