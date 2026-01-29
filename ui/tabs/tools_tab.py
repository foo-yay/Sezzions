"""
Tools Tab - Recalculation, CSV Import/Export, Database Tools, Audit
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QComboBox, QCompleter, QListView, QDialog, QLineEdit,
    QCheckBox, QSpinBox, QSizePolicy
)
from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtGui import QFontMetrics
from typing import Optional
import os
from datetime import datetime
import zipfile
import tempfile

from ui.tools_workers import RecalculationWorker
from ui.tools_dialogs import (
    RecalculationProgressDialog,
    RecalculationResultDialog,
    PostImportPromptDialog
)
from ui.csv_dialogs import (
    ImportPreviewDialog,
    ImportResultDialog,
    ExportOptionsDialog
)
from services.tools.dtos import ImportResult


class ToolsTab(QWidget):
    """Tools tab for recalculation, imports, exports, and database operations"""
    
    # Signal emitted after database-modifying operations (backup/restore/reset)
    data_changed = Signal()
    
    def __init__(self, app_facade, parent=None):
        super().__init__(parent)
        self.facade = app_facade
        self.backup_dir = ''  # Initialize backup directory attribute
        self.thread_pool = QThreadPool.globalInstance()
        self._active_progress_dialog = None  # Store active progress dialog to prevent GC
        self._setup_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "backup_dir_input") and hasattr(self, "backup_dir"):
            # Re-elide on resize so the display remains compact.
            self._set_backup_location_display(self.backup_dir)
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header (match other Setup sub-tabs)
        header_layout = QHBoxLayout()
        title = QLabel("Tools")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # These Setup sub-tabs (Users/Sites/Cards/etc.) include a search box + buttons on the right.
        # Tools doesn't need search, but we still match the header row height/vertical alignment.
        dummy_search = QLineEdit()
        dummy_search.setFixedWidth(0)
        dummy_search.setMaximumWidth(0)
        header_layout.addWidget(dummy_search)

        dummy_clear = QPushButton("Clear")
        dummy_clear.setFixedWidth(0)
        dummy_clear.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear)

        dummy_clear_filters = QPushButton("Clear All Filters")
        dummy_clear_filters.setFixedWidth(0)
        dummy_clear_filters.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear_filters)

        layout.addLayout(header_layout)
        
        # Recalculation Section
        recalc_group = self._create_recalculation_group()
        layout.addWidget(recalc_group)
        
        # CSV Import/Export Section
        csv_group = self._create_csv_group()
        layout.addWidget(csv_group)
        
        # Database Tools Section
        db_group = self._create_database_group()
        layout.addWidget(db_group)
        
        layout.addStretch()
        
    def _create_recalculation_group(self) -> QWidget:
        """Create the recalculation section"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section header
        header = QLabel("🧮 Data Recalculation")
        header.setObjectName("SectionHeader")
        container_layout.addWidget(header)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Description
        desc_label = QLabel(
            "Recalculate derived accounting data (FIFO allocations, cost basis, P/L). "
            "This should be run after importing data or correcting errors."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)

        layout.addSpacing(6)

        # Row 1: scoped recalculation
        scoped_layout = QHBoxLayout()
        scoped_layout.setSpacing(8)
        scoped_label = QLabel("Recalculate for:")
        scoped_label.setObjectName("FieldLabel")
        scoped_layout.addWidget(scoped_label)
        
        # User selector with autocomplete
        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setMinimumWidth(200)
        self.user_combo.lineEdit().setPlaceholderText("All Users")
        self._load_users()
        scoped_layout.addWidget(self.user_combo)
        
        # Site selector with autocomplete
        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.setMinimumWidth(200)
        self.site_combo.lineEdit().setPlaceholderText("All Sites")
        self._load_sites()
        scoped_layout.addWidget(self.site_combo)
        
        # Scoped recalculate button
        recalc_scoped_btn = QPushButton("🎯 Recalculate Pair")
        recalc_scoped_btn.clicked.connect(self._on_recalculate_scoped)
        scoped_layout.addWidget(recalc_scoped_btn)
        
        scoped_layout.addStretch()
        layout.addLayout(scoped_layout)
        
        layout.addSpacing(6)

        # Row 2: full recalculation (size-to-content)
        primary_row = QHBoxLayout()
        primary_row.setSpacing(8)
        recalc_all_btn = QPushButton("🔄 Recalculate Everything")
        recalc_all_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        recalc_all_btn.clicked.connect(self._on_recalculate_all)
        primary_row.addWidget(recalc_all_btn)
        primary_row.addStretch(1)
        layout.addLayout(primary_row)
        
        # Statistics display
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("HelperText")
        layout.addWidget(self.stats_label)
        self._update_stats()
        
        container_layout.addWidget(section)
        return container
        
    def _create_csv_group(self) -> QWidget:
        """Create the CSV import/export section."""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section header
        header = QLabel("📄 CSV Import/Export")
        header.setObjectName("SectionHeader")
        container_layout.addWidget(header)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "Import and export data as CSV files. "
            "Import validates data and shows preview before committing."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)

        layout.addSpacing(6)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        import_btn = QPushButton("📥 Import CSV")
        import_btn.clicked.connect(self._on_import_csv)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._on_export_csv)
        btn_layout.addWidget(export_btn)
        
        download_template_btn = QPushButton("📄 Download Template")
        download_template_btn.clicked.connect(self._on_download_template)
        btn_layout.addWidget(download_template_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        container_layout.addWidget(section)
        return container
        
    def _create_database_group(self) -> QWidget:
        """Create unified database tools section with streamlined backup controls"""
        from PySide6.QtCore import QTimer
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)
        
        # Section header
        header = QLabel("🗄️ Database Tools")
        header.setObjectName("SectionHeader")
        container_layout.addWidget(header)
        
        # Section background
        section = QWidget()
        section.setObjectName("SectionBackground")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        desc_label = QLabel(
            "Backup, restore, and reset database. "
            "Always create a backup before restore or reset operations."
        )
        desc_label.setWordWrap(True)
        desc_label.setObjectName("HelperText")
        layout.addWidget(desc_label)
        
        layout.addSpacing(6)

        # Two simple rows (no grid/columns)
        # Row 1: Backup Location:, backup field, Browse
        backup_row_layout = QHBoxLayout()
        backup_row_layout.setContentsMargins(0, 0, 0, 0)
        backup_row_layout.setSpacing(8)

        backup_label = QLabel("Backup Location:")
        backup_label.setObjectName("FieldLabel")
        backup_row_layout.addWidget(backup_label)

        self.backup_dir_input = QLabel("Not set")
        self.backup_dir_input.setObjectName("InfoField")
        self.backup_dir_input.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.backup_dir_input.setToolTip("Select a backup directory")
        self.backup_dir_input.setFixedWidth(325)
        backup_row_layout.addWidget(self.backup_dir_input)

        browse_btn = QPushButton("📁 Browse")
        browse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        browse_btn.clicked.connect(self._on_select_backup_directory)
        backup_row_layout.addWidget(browse_btn)

        backup_row_widget = QWidget()
        backup_row_widget.setLayout(backup_row_layout)
        backup_row_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(backup_row_widget, 0, Qt.AlignLeft)

        # Row 2: Backup Now, Restore, Reset, auto-backup controls (all left-justified; compact sizing)
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        
        # Backup Now button
        self.backup_now_btn = QPushButton("💾 Backup Now")
        self.backup_now_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.backup_now_btn.setEnabled(False)
        self.backup_now_btn.clicked.connect(self._on_backup_now)
        actions_layout.addWidget(self.backup_now_btn)
        
        # Restore button
        restore_btn = QPushButton("♻️ Restore")
        restore_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        restore_btn.clicked.connect(self._on_restore_database)
        actions_layout.addWidget(restore_btn)
        
        # Reset button
        reset_btn = QPushButton("🗑️ Reset")
        reset_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        reset_btn.setObjectName("DangerButton")
        reset_btn.clicked.connect(self._on_reset_database)
        actions_layout.addWidget(reset_btn)

        
        # Automatic backup checkbox
        self.auto_backup_enabled_checkbox = QCheckBox("Auto backup every")
        self.auto_backup_enabled_checkbox.toggled.connect(self._on_auto_backup_toggle)
        actions_layout.addWidget(self.auto_backup_enabled_checkbox)
        
        # Frequency spinbox using global stylesheet
        self.auto_backup_frequency_spinbox = QSpinBox()
        self.auto_backup_frequency_spinbox.setRange(1, 30)  # 1 to 30 days
        self.auto_backup_frequency_spinbox.setValue(1)
        self.auto_backup_frequency_spinbox.setSuffix(" day(s)")
        self.auto_backup_frequency_spinbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.auto_backup_frequency_spinbox.setEnabled(False)
        self.auto_backup_frequency_spinbox.valueChanged.connect(self._on_auto_backup_frequency_changed)
        actions_layout.addWidget(self.auto_backup_frequency_spinbox)

        actions_widget = QWidget()
        actions_widget.setLayout(actions_layout)
        actions_widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        layout.addWidget(actions_widget, 0, Qt.AlignLeft)

        # Last backup status (subtle)
        self.last_backup_label = QLabel("Last backup: —")
        self.last_backup_label.setObjectName("HelperText")
        layout.addWidget(self.last_backup_label)
        
        # Timer for checking backup schedule (check every 5 minutes)
        self.backup_check_timer = QTimer(self)
        self.backup_check_timer.timeout.connect(self._check_automatic_backup)
        self.backup_check_timer.setInterval(5 * 60 * 1000)  # 5 minutes
        
        # Load saved settings
        self._load_automatic_backup_settings()
        
        container_layout.addWidget(section)
        return container

    def _set_backup_location_display(self, directory: str):
        """Set backup location display with elided (middle) path and tooltip."""
        directory = directory or ""
        if not directory:
            self.backup_dir_input.setText("Not set")
            self.backup_dir_input.setToolTip("Select a backup directory")
            return

        self.backup_dir_input.setToolTip(directory)
        metrics = QFontMetrics(self.backup_dir_input.font())
        width = max(120, self.backup_dir_input.width() - 16)
        elided = metrics.elidedText(directory, Qt.ElideMiddle, width)
        self.backup_dir_input.setText(elided)
        
    def _load_users(self):
        """Load users into combo box"""
        self.user_combo.clear()
        
        try:
            users = self.facade.user_service.list_active_users()
            for user in users:
                self.user_combo.addItem(user.name, user.id)
            self._setup_completer(self.user_combo)
            
            # Set to empty (show placeholder) by default
            self.user_combo.setCurrentIndex(-1)
        except Exception as e:
            print(f"Error loading users: {e}")
            
    def _load_sites(self):
        """Load sites into combo box"""
        self.site_combo.clear()
        
        try:
            sites = self.facade.site_service.list_active_sites()
            for site in sites:
                self.site_combo.addItem(site.name, site.id)
            self._setup_completer(self.site_combo)
            
            # Set to empty (show placeholder) by default
            self.site_combo.setCurrentIndex(-1)
        except Exception as e:
            print(f"Error loading sites: {e}")
    
    def _setup_completer(self, combo: QComboBox):
        """Setup autocomplete for a combo box"""
        if not combo.isEditable():
            return
            
        completer = QCompleter(combo.model())
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        
        # Style the popup
        popup = QListView()
        popup.setStyleSheet(
            "QListView { background: palette(base); color: palette(text); }"
            "QListView::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
        )
        completer.setPopup(popup)
        
        combo.setCompleter(completer)
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.setCompleter(completer)
            
    def _update_stats(self):
        """Update statistics display"""
        try:
            from services import RecalculationService
            recalc_service = RecalculationService(self.facade.db)
            stats = recalc_service.get_stats()
            
            self.stats_label.setText(
                f"Database: {stats['pairs']} pairs, "
                f"{stats['purchases']} purchases, "
                f"{stats['redemptions']} redemptions, "
                f"{stats['sessions']} sessions, "
                f"{stats['allocations']} allocations"
            )
        except Exception as e:
            self.stats_label.setText(f"Could not load statistics: {e}")
            
    def _on_recalculate_all(self):
        """Handle recalculate everything button click"""
        # Confirmation dialog with correct terminology
        reply = QMessageBox.question(
            self,
            "Recalculate Everything",
            "This will rebuild ALL calculations from scratch:\n\n"
            "1. FIFO cost basis for all redemptions\n"
            "2. Session taxable P/L (gameplay-based)\n"
            "3. Daily totals\n\n"
            "This may take a moment for large databases.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog("Recalculate Everything", self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(self.facade.db.db_path, operation="all")
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(lambda result: self._on_recalculation_finished(result, progress_dialog))
        worker.signals.error.connect(lambda error: self._on_recalculation_error(error, progress_dialog))
        worker.signals.cancelled.connect(lambda: self._on_recalculation_cancelled(progress_dialog))
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
        
    def _on_recalculate_scoped(self):
        """Handle scoped recalculation button click"""
        # Get current text from editable combo boxes
        user_text = self.user_combo.currentText().strip()
        site_text = self.site_combo.currentText().strip()
        
        # If empty, default to "all"
        if not user_text and not site_text:
            # Both empty - recalculate all
            self._on_recalculate_all()
            return
        
        # Try to find matching IDs from text
        user_id = None
        site_id = None
        user_name = "All Users"
        site_name = "All Sites"
        
        # Find user by name
        if user_text:
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i).lower() == user_text.lower():
                    user_id = self.user_combo.itemData(i)
                    user_name = self.user_combo.itemText(i)
                    break
        
        # Find site by name
        if site_text:
            for i in range(self.site_combo.count()):
                if self.site_combo.itemText(i).lower() == site_text.lower():
                    site_id = self.site_combo.itemData(i)
                    site_name = self.site_combo.itemText(i)
                    break
        
        # If both are specified but one is invalid
        if user_text and user_id is None:
            QMessageBox.warning(
                self,
                "Invalid User",
                f"User '{user_text}' not found. Please select from the dropdown."
            )
            return
        
        if site_text and site_id is None:
            QMessageBox.warning(
                self,
                "Invalid Site",
                f"Site '{site_text}' not found. Please select from the dropdown."
            )
            return
        
        # Determine operation type
        if user_id and site_id:
            operation = "pair"
            title = f"Recalculate {user_name} @ {site_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  User: {user_name}\n  Site: {site_name}\n\nContinue?"
        elif user_id:
            operation = "user"
            title = f"Recalculate {user_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  User: {user_name} (all sites)\n\nContinue?"
        elif site_id:
            operation = "site"
            title = f"Recalculate {site_name}"
            message = f"Recalculate FIFO cost basis and P/L for:\n  Site: {site_name} (all users)\n\nContinue?"
        else:
            # Neither specified
            self._on_recalculate_all()
            return
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self,
            "Recalculate",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog(title, self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(
            self.facade.db.db_path,
            operation=operation,
            user_id=user_id,
            site_id=site_id
        )
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(lambda result: self._on_recalculation_finished(result, progress_dialog))
        worker.signals.error.connect(lambda error: self._on_recalculation_error(error, progress_dialog))
        worker.signals.cancelled.connect(lambda: self._on_recalculation_cancelled(progress_dialog))
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
        
    def _on_recalculation_finished(self, result, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation completion"""
        progress_dialog.set_complete("Recalculation complete!")
        progress_dialog.accept()
        
        # Update stats
        self._update_stats()
        
        # Show results dialog
        result_dialog = RecalculationResultDialog(result, self)
        result_dialog.exec()
        
        # Notify listeners (refresh UI tables)
        self.facade.db._notify_change()
        
    def _on_recalculation_error(self, error: str, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation error"""
        progress_dialog.set_error(error)
        progress_dialog.reject()
        
        QMessageBox.critical(
            self,
            "Recalculation Error",
            f"An error occurred during recalculation:\n\n{error}"
        )
        
    def _on_recalculation_cancelled(self, progress_dialog: RecalculationProgressDialog):
        """Handle recalculation cancellation"""
        progress_dialog.accept()
        
        QMessageBox.information(
            self,
            "Recalculation Cancelled",
            "Recalculation was cancelled. The database may be in an incomplete state.\n\n"
            "Consider running recalculation again to ensure data consistency."
        )
        
    def refresh(self):
        """Refresh the tab (reload dropdowns, update stats)"""
        self._load_users()
        self._load_sites()
        self._update_stats()
    
    # ========================================================================
    # CSV Import/Export Handlers
    # ========================================================================
    
    def _on_import_csv(self):
        """Handle CSV import button click."""
        # Show entity type selector dialog
        dialog = ExportOptionsDialog(self, mode="import")
        
        if dialog.exec() != QDialog.Accepted or not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # File picker
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {entity_type.replace('_', ' ').title()} CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Preview import
            preview = self.facade.csv_import_service.preview_import(
                csv_path=file_path,
                entity_type=entity_type,
                strict_mode=True
            )
            
            # Show preview dialog
            preview_dialog = ImportPreviewDialog(preview, entity_type, self)
            
            if preview_dialog.exec() != QDialog.Accepted:
                return
            
            # User confirmed - perform import with conflict resolution options
            result = self.facade.csv_import_service.execute_import(
                csv_path=file_path,
                entity_type=entity_type,
                skip_conflicts=preview_dialog.skip_conflicts,
                overwrite_conflicts=preview_dialog.overwrite_conflicts
            )
            
            # Show result
            result_dialog = ImportResultDialog(result, self)
            result_dialog.exec()
            
            # If successful and affects accounting data, prompt for recalculation
            if result.success and result.total_processed > 0:
                accounting_entities = ['purchases', 'redemptions', 'game_sessions']
                if entity_type in accounting_entities:
                    self.prompt_recalculate_after_import(result)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import CSV:\n\n{str(e)}"
            )
    
    def _on_export_csv(self):
        """Handle CSV export button click."""
        # Show entity type selector
        dialog = ExportOptionsDialog(self)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Check if export all was selected
        if dialog.export_all:
            self._export_all_csv()
            return
        
        if not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{entity_type}_{timestamp}.csv"
        
        # File picker for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {entity_type.replace('_', ' ').title()} CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Perform export
            result = self.facade.csv_export_service.export_csv(
                entity_type=entity_type,
                output_path=file_path
            )
            
            if result.success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Exported {result.records_exported} records to:\n{file_path}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    f"Failed to export data:\n\n{result.error or 'Unknown error'}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export CSV:\n\n{str(e)}"
            )
    
    def _export_all_csv(self):
        """Export all entity types to a ZIP file."""
        # File picker for ZIP save location
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"sezzions_export_all_{timestamp}.zip"
        
        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Data to ZIP",
            default_filename,
            "ZIP Files (*.zip);;All Files (*)"
        )
        
        if not zip_path:
            return
        
        try:
            # Only entity types that have schemas defined
            entity_types = [
                "purchases", "redemptions", "game_sessions",
                "users", "sites", "cards", "redemption_methods",
                "redemption_method_types", "game_types", "games"
            ]
            
            # Create temporary directory for CSV files
            with tempfile.TemporaryDirectory() as temp_dir:
                exported_count = 0
                failed = []
                
                # Export each entity to temp directory
                for entity_type in entity_types:
                    try:
                        csv_filename = f"{entity_type}.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        result = self.facade.csv_export_service.export_csv(
                            entity_type=entity_type,
                            output_path=csv_path
                        )
                        
                        if result.success:
                            exported_count += 1
                        else:
                            failed.append(f"{entity_type}: {result.error}")
                    
                    except Exception as e:
                        failed.append(f"{entity_type}: {str(e)}")
                
                # Create ZIP file
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for entity_type in entity_types:
                        csv_filename = f"{entity_type}.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        if os.path.exists(csv_path):
                            zipf.write(csv_path, csv_filename)
                
                # Show result
                if failed:
                    QMessageBox.warning(
                        self,
                        "Export Complete with Errors",
                        f"Exported {exported_count} entity types to ZIP.\n\n"
                        f"Failed:\n" + "\n".join(failed)
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Export Successful",
                        f"Exported all {exported_count} entity types to:\n{zip_path}"
                    )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to create ZIP file:\n\n{str(e)}"
            )
    
    def _on_download_template(self):
        """Handle download template button click."""
        # Show entity type selector
        dialog = ExportOptionsDialog(self, mode="template")
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # Check if download all was selected
        if dialog.export_all:
            self._download_all_templates()
            return
        
        if not dialog.selected_entity:
            return
        
        entity_type = dialog.selected_entity
        
        # Generate template filename
        default_filename = f"{entity_type}_template.csv"
        
        # File picker for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {entity_type.replace('_', ' ').title()} Template",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # Generate template
            result = self.facade.csv_export_service.generate_template(
                entity_type=entity_type,
                output_path=file_path
            )
            
            if result.success:
                QMessageBox.information(
                    self,
                    "Template Created",
                    f"Template saved to:\n{file_path}\n\n"
                    "Fill in your data and use 'Import CSV' to upload it."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Template Generation Failed",
                    f"Failed to create template:\n\n{result.error or 'Unknown error'}"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Template Error",
                f"Failed to generate template:\n\n{str(e)}"
            )
    
    def _download_all_templates(self):
        """Download all templates to a ZIP file."""
        # File picker for ZIP save location
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"sezzions_templates_{timestamp}.zip"
        
        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            "Download All Templates to ZIP",
            default_filename,
            "ZIP Files (*.zip);;All Files (*)"
        )
        
        if not zip_path:
            return
        
        try:
            # Only entity types that have schemas defined
            entity_types = [
                "purchases", "redemptions", "game_sessions",
                "users", "sites", "cards", "redemption_methods",
                "redemption_method_types", "game_types", "games"
            ]
            
            # Create temporary directory for template files
            with tempfile.TemporaryDirectory() as temp_dir:
                generated_count = 0
                failed = []
                
                # Generate each template to temp directory
                for entity_type in entity_types:
                    try:
                        csv_filename = f"{entity_type}_template.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        result = self.facade.csv_export_service.generate_template(
                            entity_type=entity_type,
                            output_path=csv_path
                        )
                        
                        if result.success:
                            generated_count += 1
                        else:
                            failed.append(f"{entity_type}: {result.error}")
                    
                    except Exception as e:
                        failed.append(f"{entity_type}: {str(e)}")
                
                # Create ZIP file
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for entity_type in entity_types:
                        csv_filename = f"{entity_type}_template.csv"
                        csv_path = os.path.join(temp_dir, csv_filename)
                        
                        if os.path.exists(csv_path):
                            zipf.write(csv_path, csv_filename)
                
                # Show result
                if failed:
                    QMessageBox.warning(
                        self,
                        "Templates Complete with Errors",
                        f"Generated {generated_count} templates to ZIP.\n\n"
                        f"Failed:\n" + "\n".join(failed)
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Templates Downloaded",
                        f"All {generated_count} templates saved to:\n{zip_path}\n\n"
                        "Fill in your data and use 'Import CSV' to upload them."
                    )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Template Error",
                f"Failed to create template ZIP:\n\n{str(e)}"
            )
    
    # ========================================================================
    # Database Tools Handlers
    # ========================================================================
    
    def _on_select_backup_directory(self):
        """Handle backup directory selection"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Directory",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.backup_dir = directory
            self._set_backup_location_display(directory)
            self.backup_now_btn.setEnabled(True)
            
            # Save to settings (shared with automatic backup)
            self._save_automatic_backup_settings()
            
            # If automatic backup is enabled, restart timer
            if self.auto_backup_enabled_checkbox.isChecked():
                self.backup_check_timer.start()
    
    def _on_backup_now(self):
        """Handle manual backup"""
        # Disable button immediately to prevent double-clicks
        self.backup_now_btn.setEnabled(False)
        
        if not hasattr(self, 'backup_dir') or not self.backup_dir:
            self.backup_now_btn.setEnabled(True)
            QMessageBox.warning(
                self,
                "No Directory Selected",
                "Please select a backup directory first."
            )
            return
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            self.backup_now_btn.setEnabled(True)
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        try:
            from datetime import datetime
            from ui.settings import Settings
            from PySide6.QtWidgets import QProgressDialog
            
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"sezzions_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Acquire exclusive lock
            if not self.facade.acquire_tools_lock():
                self.backup_now_btn.setEnabled(True)
                QMessageBox.warning(
                    self,
                    "Lock Failed",
                    "Could not acquire exclusive lock for backup operation."
                )
                return
            
            # Create worker
            worker = self.facade.create_backup_worker(backup_path)
            
            # Create progress dialog and store as instance variable
            self._active_progress_dialog = QProgressDialog("Creating database backup...", None, 0, 0, self)
            self._active_progress_dialog.setWindowTitle("Backup")
            self._active_progress_dialog.setWindowModality(Qt.WindowModal)
            self._active_progress_dialog.setMinimumDuration(0)
            self._active_progress_dialog.setCancelButton(None)  # Disable cancel to prevent premature closure
            
            # Make dialog non-interactive to prevent event loop issues when clicked
            self._active_progress_dialog.setWindowFlags(
                Qt.Window | 
                Qt.WindowTitleHint | 
                Qt.CustomizeWindowHint |
                Qt.WindowStaysOnTopHint
            )
            self._active_progress_dialog.setEnabled(False)  # Completely disable interaction
            self._active_progress_dialog.show()
            
            # Connect signals
            def on_finished(result):
                print(f"[UI] on_finished called with success={result.success}")
                
                # Close progress dialog first
                if self._active_progress_dialog:
                    self._active_progress_dialog.close()
                    self._active_progress_dialog = None
                
                # Release lock and re-enable button immediately
                self.facade.release_tools_lock()
                self.backup_now_btn.setEnabled(True)
                print("[UI] Lock released, button re-enabled")
                
                # Defer message box to next event loop iteration
                # This ensures the progress dialog is fully closed first
                from PySide6.QtCore import QTimer
                
                def show_result():
                    print("[UI] Showing result message")
                    if result.success:
                        size_mb = result.size_bytes / (1024 * 1024)
                        
                        # Save backup time to settings
                        now = datetime.now()
                        settings = Settings()
                        config = settings.get_automatic_backup_config()
                        config['last_backup_time'] = now.isoformat()
                        settings.set_automatic_backup_config(config)
                        
                        # Update last backup display
                        self._update_last_backup_display()
                        
                        QMessageBox.information(
                            self,
                            "Backup Complete",
                            f"Database backed up successfully:\n\n{backup_path}\n\nSize: {size_mb:.2f} MB"
                        )
                        print("[UI] Success message closed")
                    else:
                        print(f"[UI] Showing error message: {result.error}")
                        QMessageBox.critical(
                            self,
                            "Backup Failed",
                            f"Failed to create backup:\n\n{result.error}"
                        )
                
                QTimer.singleShot(100, show_result)
            
            def on_error(error_msg):
                print(f"[UI] on_error called: {error_msg}")
                
                # Close progress dialog first
                if self._active_progress_dialog:
                    self._active_progress_dialog.close()
                    self._active_progress_dialog = None
                
                # Release lock and re-enable button immediately
                self.facade.release_tools_lock()
                self.backup_now_btn.setEnabled(True)
                
                # Defer message box to next event loop iteration
                from PySide6.QtCore import QTimer
                
                def show_error():
                    QMessageBox.critical(
                        self,
                        "Backup Error",
                        f"An error occurred:\n\n{error_msg}"
                    )
                
                QTimer.singleShot(100, show_error)
            
            worker.signals.finished.connect(on_finished)
            worker.signals.error.connect(on_error)
            
            # Start worker
            self.thread_pool.start(worker)
        
        except Exception as e:
            if self._active_progress_dialog:
                self._active_progress_dialog.close()
                self._active_progress_dialog = None
            self.facade.release_tools_lock()
            self.backup_now_btn.setEnabled(True)
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred:\n\n{str(e)}"
            )
    
    def _on_restore_database(self):
        """Handle database restore"""
        from PySide6.QtWidgets import QMessageBox, QProgressDialog
        from ui.tools_dialogs import RestoreDialog
        from services.tools.backup_service import BackupService
        import os
        from datetime import datetime
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        # Show restore dialog
        dialog = RestoreDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        backup_path = dialog.backup_path
        restore_mode = dialog.get_restore_mode()
        
        # Validate backup file exists
        if not os.path.exists(backup_path):
            QMessageBox.critical(
                self,
                "Error",
                f"Backup file not found: {backup_path}"
            )
            return
            
        # For replace mode, create safety backup first
        if restore_mode.name == "REPLACE":
            backup_service = BackupService(self.facade.db)
            
            # Get backup directory from last backup
            if hasattr(self, 'backup_dir') and self.backup_dir:
                backup_dir = self.backup_dir
            else:
                backup_dir = os.path.dirname(backup_path)
            
            # Generate timestamped filename for safety backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup_path = os.path.join(backup_dir, f"pre_restore_backup_{timestamp}.db")
                
            result = backup_service.backup_database(safety_backup_path)
            if not result.success:
                QMessageBox.critical(
                    self,
                    "Backup Failed",
                    f"Could not create safety backup before restore:\n{result.error}\n\n"
                    "Restore operation cancelled for safety."
                )
                return
                
            safety_backup_file = os.path.basename(result.backup_path)
            QMessageBox.information(
                self,
                "Safety Backup Created",
                f"Safety backup created: {safety_backup_file}\n\n"
                "Proceeding with database replacement..."
            )
        
        # Acquire exclusive lock
        if not self.facade.acquire_tools_lock():
            QMessageBox.warning(
                self,
                "Lock Failed",
                "Could not acquire exclusive lock for restore operation."
            )
            return
        
        # Create worker
        worker = self.facade.create_restore_worker(backup_path, restore_mode)
        
        # Create progress dialog and store as instance variable
        self._active_progress_dialog = QProgressDialog("Restoring database...", None, 0, 0, self)
        self._active_progress_dialog.setWindowTitle("Restore")
        self._active_progress_dialog.setWindowModality(Qt.WindowModal)
        self._active_progress_dialog.setMinimumDuration(0)
        self._active_progress_dialog.setCancelButton(None)  # Disable cancel to prevent premature closure
        self._active_progress_dialog.show()
        
        # Connect signals
        def on_finished(result):
            if self._active_progress_dialog:
                self._active_progress_dialog.close()
                self._active_progress_dialog = None
            self.facade.release_tools_lock()
            
            if result.success:
                tables_info = f"\n• ".join(result.tables_affected) if result.tables_affected else "All tables"
                QMessageBox.information(
                    self,
                    "Restore Complete",
                    f"✓ Database restored successfully!\n\n"
                    f"Mode: {restore_mode.name.replace('_', ' ').title()}\n"
                    f"Records restored: {result.records_restored:,}\n"
                    f"Tables affected:\n• {tables_info}\n\n"
                    "Please restart the application to see all changes."
                )
                # Emit data changed signal (for future cross-tab refresh)
                if hasattr(self, 'data_changed'):
                    self.data_changed.emit()
            else:
                QMessageBox.critical(
                    self,
                    "Restore Failed",
                    f"Database restore failed:\n{result.error}"
                )
        
        def on_error(error_msg):
            if self._active_progress_dialog:
                self._active_progress_dialog.close()
                self._active_progress_dialog = None
            self.facade.release_tools_lock()
            QMessageBox.critical(
                self,
                "Restore Error",
                f"An error occurred:\n\n{error_msg}"
            )
        
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        
        # Start worker
        self.thread_pool.start(worker)
    
    def _on_reset_database(self):
        """Handle database reset"""
        from PySide6.QtWidgets import QMessageBox
        from ui.tools_dialogs import ResetDialog, RecalculationProgressDialog
        from services.tools.reset_service import ResetService
        from services.tools.backup_service import BackupService
        import os
        from datetime import datetime
        
        # Check if another tools operation is running
        if self.facade.is_tools_operation_active():
            QMessageBox.warning(
                self,
                "Operation in Progress",
                "Another database tools operation is currently running.\n\n"
                "Please wait for it to complete before starting a new operation."
            )
            return
        
        # Get current table counts
        reset_service = ResetService(self.facade.db)
        table_counts = reset_service.get_table_counts()
        
        # Show reset dialog
        dialog = ResetDialog(table_counts, self)
        if dialog.exec() != QDialog.Accepted:
            return
            
        preserve_setup = dialog.should_preserve_setup()
        
        # Final confirmation
        reset_type = "transactional data only" if preserve_setup else "ALL DATA"
        reply = QMessageBox.warning(
            self,
            "Final Confirmation",
            f"This will permanently delete {reset_type}.\n\n"
            "Are you absolutely sure you want to proceed?\n\n"
            "This action CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        # Offer to create backup first
        if hasattr(self, 'backup_dir') and self.backup_dir:
            backup_reply = QMessageBox.question(
                self,
                "Create Backup First?",
                "Would you like to create a safety backup before resetting?\n\n"
                "This is STRONGLY recommended.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if backup_reply == QMessageBox.Yes:
                backup_service = BackupService(self.facade.db)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safety_backup_path = os.path.join(self.backup_dir, f"pre_reset_backup_{timestamp}.db")
                result = backup_service.backup_database(safety_backup_path)
                if result.success:
                    backup_file = os.path.basename(result.backup_path)
                    QMessageBox.information(
                        self,
                        "Backup Created",
                        f"Safety backup created: {backup_file}\n\n"
                        "Proceeding with reset..."
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Backup Failed",
                        f"Could not create backup:\n{result.error}\n\n"
                        "Reset cancelled for safety."
                    )
                    return
        
        # Acquire exclusive lock
        if not self.facade.acquire_tools_lock():
            QMessageBox.warning(
                self,
                "Lock Failed",
                "Could not acquire exclusive lock for reset operation."
            )
            return
        
        # Create worker
        worker = self.facade.create_reset_worker(keep_setup_data=preserve_setup, keep_audit_log=True)
        
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog("Reset", self)
        progress_dialog.setLabelText("Resetting database...")
        progress_dialog.setRange(0, 0)  # Indeterminate progress
        progress_dialog.show()
        
        # Connect signals
        def on_finished(result):
            progress_dialog.close()
            self.facade.release_tools_lock()
            
            if result.success:
                tables_info = "\n• ".join(result.tables_cleared) if result.tables_cleared else "None"
                QMessageBox.information(
                    self,
                    "Reset Complete",
                    f"✓ Database reset successfully!\n\n"
                    f"Records deleted: {result.records_deleted:,}\n"
                    f"Tables cleared:\n• {tables_info}\n\n"
                    "Please restart the application to see all changes."
                )
                # Emit data changed signal (for future cross-tab refresh)
                if hasattr(self, 'data_changed'):
                    self.data_changed.emit()
            else:
                QMessageBox.critical(
                    self,
                    "Reset Failed",
                    f"Database reset failed:\n{result.error}"
                )
        
        def on_error(error_msg):
            progress_dialog.close()
            self.facade.release_tools_lock()
            QMessageBox.critical(
                self,
                "Reset Error",
                f"An error occurred:\n\n{error_msg}"
            )
        
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(on_error)
        
        # Start worker
        self.thread_pool.start(worker)
    
    # ========================================================================
    # Post-Import Recalculation
    # ========================================================================
    
    def prompt_recalculate_after_import(self, import_result):
        """Show post-import recalculation prompt and trigger if user confirms.
        
        Args:
            import_result: ImportResult with affected_user_ids and affected_site_ids
        """
        # Show prompt dialog
        prompt_dialog = PostImportPromptDialog(self, import_result)
        
        if prompt_dialog.exec() == QDialog.Accepted:
            # User chose to recalculate
            self._trigger_post_import_recalculation(
                import_result.entity_type,
                import_result.affected_user_ids,
                import_result.affected_site_ids
            )
    
    def _trigger_post_import_recalculation(
        self,
        entity_type: str,
        user_ids: list,
        site_ids: list
    ):
        """Trigger recalculation for affected pairs after import.
        
        Args:
            entity_type: Type of entity imported (purchases, redemptions, etc.)
            user_ids: List of affected user IDs
            site_ids: List of affected site IDs
        """
        # Create progress dialog
        progress_dialog = RecalculationProgressDialog("Post-Import Recalculation", parent=self)
        
        # Create worker with database path (creates its own connection for thread safety)
        worker = RecalculationWorker(
            self.facade.db.db_path,
            operation="after_import",
            entity_type=entity_type,
            user_ids=user_ids,
            site_ids=site_ids
        )
        
        # Connect signals
        worker.signals.progress.connect(progress_dialog.update_progress)
        worker.signals.finished.connect(
            lambda result: self._on_recalculation_finished(result, progress_dialog)
        )
        worker.signals.error.connect(
            lambda error: self._on_recalculation_error(error, progress_dialog)
        )
        worker.signals.cancelled.connect(
            lambda: self._on_recalculation_cancelled(progress_dialog)
        )
        progress_dialog.cancel_requested.connect(worker.cancel)
        
        # Start worker
        self.thread_pool.start(worker)
        
        # Show progress dialog
        progress_dialog.exec()
    
    # ========================================================================
    # Automatic Backup Management
    # ========================================================================
    
    def _load_automatic_backup_settings(self):
        """Load automatic backup settings from JSON"""
        from ui.settings import Settings
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        # Block signals during load to prevent premature saves
        self.auto_backup_enabled_checkbox.blockSignals(True)
        self.auto_backup_frequency_spinbox.blockSignals(True)
        
        # Apply settings to UI
        enabled = config.get('enabled', False)
        self.auto_backup_enabled_checkbox.setChecked(enabled)
        
        directory = config.get('directory', '')
        if directory:
            self._set_backup_location_display(directory)
            self.backup_dir = directory
            self.backup_now_btn.setEnabled(True)
        
        # Convert hours to days for spinbox display
        frequency_hours = config.get('frequency_hours', 24)
        frequency_days = max(1, frequency_hours // 24)  # At least 1 day
        self.auto_backup_frequency_spinbox.setValue(frequency_days)
        
        # Set spinbox enabled state based on checkbox (while signals still blocked)
        self.auto_backup_frequency_spinbox.setEnabled(enabled)
        
        # Enable/disable spinbox based on checkbox
        self.auto_backup_frequency_spinbox.setEnabled(config.get('enabled', False))
        
        # Update last backup label
        self._update_last_backup_display()
        
        # Start timer if enabled
        if config.get('enabled', False) and directory:
            self.backup_check_timer.start()
    
    def _save_automatic_backup_settings(self):
        """Save automatic backup settings to JSON"""
        from ui.settings import Settings
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        # Update config
        config['enabled'] = self.auto_backup_enabled_checkbox.isChecked()
        config['directory'] = self.backup_dir if self.backup_dir else ''
        # Convert days to hours for storage
        config['frequency_hours'] = self.auto_backup_frequency_spinbox.value() * 24
        
        settings.set_automatic_backup_config(config)
    
    def _on_auto_backup_toggle(self, checked):
        """Handle automatic backup enable/disable"""
        # Enable/disable spinbox
        self.auto_backup_frequency_spinbox.setEnabled(checked)
        
        # Start/stop timer
        if checked and self.backup_dir:
            self.backup_check_timer.start()
        else:
            self.backup_check_timer.stop()
        
        self._save_automatic_backup_settings()
    
    def _on_auto_backup_frequency_changed(self, value):
        """Handle frequency change"""
        self._save_automatic_backup_settings()
    
    def _update_last_backup_display(self):
        """Update the last backup label with most recent backup time"""
        from ui.settings import Settings
        from datetime import datetime
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        last_backup_str = config.get('last_backup_time')
        
        if last_backup_str:
            try:
                last_time = datetime.fromisoformat(last_backup_str)
                time_str = last_time.strftime('%Y-%m-%d %H:%M')
                self.last_backup_label.setText(f"Last backup: {time_str}")
            except:
                self.last_backup_label.setText("Last backup: —")
        else:
            self.last_backup_label.setText("Last backup: —")
    
    def _check_automatic_backup(self):
        """Check if it's time to run an automatic backup"""
        from ui.settings import Settings
        from datetime import datetime, timedelta
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        
        if not config.get('enabled', False):
            return
        
        directory = config.get('directory', '')
        if not directory:
            return
        
        frequency_hours = config.get('frequency_hours', 24)
        last_backup_str = config.get('last_backup_time')
        
        should_backup = False
        if not last_backup_str:
            # Never backed up - do it now
            should_backup = True
        else:
            try:
                last_backup = datetime.fromisoformat(last_backup_str)
                next_backup = last_backup + timedelta(hours=frequency_hours)
                should_backup = datetime.now() >= next_backup
            except:
                # Invalid timestamp - backup now
                should_backup = True
        
        if should_backup:
            self._perform_automatic_backup()
    
    def _perform_automatic_backup(self):
        """Perform an automatic backup"""
        from services.tools.backup_service import BackupService
        from ui.settings import Settings
        from datetime import datetime
        import os
        
        settings = Settings()
        config = settings.get_automatic_backup_config()
        directory = config.get('directory', '')
        
        if not directory:
            return
        
        # Perform backup
        backup_service = BackupService(self.facade.db)
        result = backup_service.backup_with_timestamp(directory, prefix="auto_backup")
        
        if result.success:
            # Update last backup time
            config['last_backup_time'] = datetime.now().isoformat()
            settings.set_automatic_backup_config(config)
            self._update_last_backup_display()
            
            # Log success (non-blocking)
            filename = os.path.basename(result.backup_path)
            size_mb = result.size_bytes / (1024 * 1024)
            print(f"[Auto-Backup] Created: {filename} ({size_mb:.2f} MB)")
        else:
            # Log error but don't block UI
            print(f"[Auto-Backup] Failed: {result.error}")
    
