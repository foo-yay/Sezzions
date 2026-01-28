"""
Tools Tab - Recalculation, CSV Import/Export, Database Tools, Audit
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QMessageBox, QFileDialog,
    QComboBox, QCompleter, QListView, QDialog
)
from PySide6.QtCore import QThreadPool, Qt
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
    
    def __init__(self, app_facade, parent=None):
        super().__init__(parent)
        self.facade = app_facade
        self.thread_pool = QThreadPool.globalInstance()
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Recalculation Section
        recalc_group = self._create_recalculation_group()
        layout.addWidget(recalc_group)
        
        # CSV Import/Export Section (placeholder for now)
        csv_group = self._create_csv_group()
        layout.addWidget(csv_group)
        
        # Database Tools Section (placeholder for now)
        db_group = self._create_database_group()
        layout.addWidget(db_group)
        
        layout.addStretch()
        
    def _create_recalculation_group(self) -> QGroupBox:
        """Create the recalculation section"""
        group = QGroupBox("Data Recalculation")
        layout = QVBoxLayout(group)
        
        # Description
        desc_label = QLabel(
            "Recalculate derived accounting data (FIFO allocations, cost basis, P/L). "
            "This should be run after importing data or correcting errors."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # Recalculate Everything button
        recalc_all_layout = QHBoxLayout()
        recalc_all_btn = QPushButton("Recalculate Everything")
        recalc_all_btn.setMinimumHeight(40)
        recalc_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        recalc_all_btn.clicked.connect(self._on_recalculate_all)
        recalc_all_layout.addWidget(recalc_all_btn)
        layout.addLayout(recalc_all_layout)
        
        # Scoped recalculation section
        scoped_layout = QHBoxLayout()
        scoped_label = QLabel("Recalculate specific user/site:")
        scoped_layout.addWidget(scoped_label)
        
        # User selector with autocomplete
        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.setMinimumWidth(150)
        self.user_combo.lineEdit().setPlaceholderText("All Users")
        self._load_users()
        scoped_layout.addWidget(self.user_combo)
        
        # Site selector with autocomplete
        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.setMinimumWidth(150)
        self.site_combo.lineEdit().setPlaceholderText("All Sites")
        self._load_sites()
        scoped_layout.addWidget(self.site_combo)
        
        # Scoped recalculate button
        recalc_scoped_btn = QPushButton("Recalculate Pair")
        recalc_scoped_btn.clicked.connect(self._on_recalculate_scoped)
        scoped_layout.addWidget(recalc_scoped_btn)
        
        scoped_layout.addStretch()
        layout.addLayout(scoped_layout)
        
        # Statistics display
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 10px;")
        layout.addWidget(self.stats_label)
        self._update_stats()
        
        return group
        
    def _create_csv_group(self) -> QGroupBox:
        """Create the CSV import/export section."""
        group = QGroupBox("CSV Import/Export")
        layout = QVBoxLayout(group)
        
        desc_label = QLabel(
            "Import and export data as CSV files. "
            "Import validates data and shows preview before committing."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton("Import CSV...")
        import_btn.setMinimumHeight(35)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        import_btn.clicked.connect(self._on_import_csv)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export CSV...")
        export_btn.setMinimumHeight(35)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        export_btn.clicked.connect(self._on_export_csv)
        btn_layout.addWidget(export_btn)
        
        download_template_btn = QPushButton("Download Template...")
        download_template_btn.setMinimumHeight(35)
        download_template_btn.clicked.connect(self._on_download_template)
        btn_layout.addWidget(download_template_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return group
        
    def _create_database_group(self) -> QGroupBox:
        """Create the database tools section"""
        group = QGroupBox("Database Tools")
        layout = QVBoxLayout(group)
        
        desc_label = QLabel(
            "Backup, restore, and reset database. "
            "Always create a backup before restore or reset operations."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # Manual backup section
        backup_layout = QHBoxLayout()
        backup_layout.setSpacing(10)
        
        # Backup directory label and path display
        backup_dir_label = QLabel("Backup directory:")
        backup_layout.addWidget(backup_dir_label)
        
        self.backup_dir_display = QLabel("(Not set)")
        self.backup_dir_display.setStyleSheet("color: #666; font-style: italic;")
        backup_layout.addWidget(self.backup_dir_display, 1)
        
        # Select directory button
        select_dir_btn = QPushButton("Choose...")
        select_dir_btn.setMaximumWidth(100)
        select_dir_btn.clicked.connect(self._on_select_backup_directory)
        backup_layout.addWidget(select_dir_btn)
        
        # Backup Now button
        self.backup_now_btn = QPushButton("Backup Now")
        self.backup_now_btn.setMinimumHeight(35)
        self.backup_now_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.backup_now_btn.setEnabled(False)
        self.backup_now_btn.clicked.connect(self._on_backup_now)
        backup_layout.addWidget(self.backup_now_btn)
        
        layout.addLayout(backup_layout)
        
        # Backup status label
        self.backup_status_label = QLabel("")
        self.backup_status_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 5px;")
        layout.addWidget(self.backup_status_label)
        
        # Restore/Reset buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        restore_btn = QPushButton("Restore from Backup...")
        restore_btn.setMinimumHeight(35)
        restore_btn.clicked.connect(self._on_restore_database)
        btn_layout.addWidget(restore_btn)
        
        reset_btn = QPushButton("Reset Database...")
        reset_btn.setMinimumHeight(35)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        reset_btn.clicked.connect(self._on_reset_database)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        return group
        
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
            # Display abbreviated path if too long
            display_path = directory
            if len(display_path) > 50:
                display_path = "..." + display_path[-47:]
            self.backup_dir_display.setText(display_path)
            self.backup_dir_display.setStyleSheet("color: #000;")
            self.backup_now_btn.setEnabled(True)
            self.backup_status_label.setText("")
    
    def _on_backup_now(self):
        """Handle manual backup"""
        if not hasattr(self, 'backup_dir') or not self.backup_dir:
            QMessageBox.warning(
                self,
                "No Directory Selected",
                "Please select a backup directory first."
            )
            return
        
        try:
            from services.tools import BackupService
            from datetime import datetime
            
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"sezzions_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Create backup service
            backup_service = BackupService(self.facade.db)
            result = backup_service.backup_database(backup_path)
            
            if result.success:
                size_mb = result.size_bytes / (1024 * 1024)
                self.backup_status_label.setText(
                    f"✓ Backup created: {backup_filename} ({size_mb:.2f} MB)"
                )
                self.backup_status_label.setStyleSheet("color: #28a745; font-size: 11px; margin-top: 5px;")
                
                QMessageBox.information(
                    self,
                    "Backup Complete",
                    f"Database backed up successfully:\n\n{backup_path}\n\nSize: {size_mb:.2f} MB"
                )
            else:
                self.backup_status_label.setText(f"✗ Backup failed")
                self.backup_status_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 5px;")
                
                QMessageBox.critical(
                    self,
                    "Backup Failed",
                    f"Failed to create backup:\n\n{result.error}"
                )
        
        except Exception as e:
            self.backup_status_label.setText(f"✗ Backup error")
            self.backup_status_label.setStyleSheet("color: #dc3545; font-size: 11px; margin-top: 5px;")
            
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred:\n\n{str(e)}"
            )
    
    def _on_restore_database(self):
        """Handle database restore"""
        from PySide6.QtWidgets import QMessageBox
        from ui.tools_dialogs import RestoreDialog
        from services.tools.restore_service import RestoreService
        from services.tools.backup_service import BackupService
        import os
        from datetime import datetime
        
        # Show restore dialog
        dialog = RestoreDialog(self)
        if dialog.exec() != dialog.Accepted:
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
            if hasattr(self, 'backup_directory') and self.backup_directory:
                backup_dir = self.backup_directory
            else:
                backup_dir = os.path.dirname(backup_path)
                
            result = backup_service.backup_database(backup_dir)
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
        
        # Perform restore
        restore_service = RestoreService(self.facade.db)
        result = restore_service.restore_database(backup_path, restore_mode)
        
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
        else:
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"Database restore failed:\n{result.error}"
            )
    
    def _on_reset_database(self):
        """Handle database reset"""
        from PySide6.QtWidgets import QMessageBox
        from ui.tools_dialogs import ResetDialog
        from services.tools.reset_service import ResetService
        from services.tools.backup_service import BackupService
        import os
        
        # Get current table counts
        reset_service = ResetService(self.facade.db)
        table_counts = reset_service.get_table_counts()
        
        # Show reset dialog
        dialog = ResetDialog(table_counts, self)
        if dialog.exec() != dialog.Accepted:
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
        if hasattr(self, 'backup_directory') and self.backup_directory:
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
                result = backup_service.backup_database(self.backup_directory)
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
        
        # Perform reset
        result = reset_service.reset_database(
            keep_setup_data=preserve_setup,
            keep_audit_log=True
        )
        
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
        else:
            QMessageBox.critical(
                self,
                "Reset Failed",
                f"Database reset failed:\n{result.error}"
            )
    
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
