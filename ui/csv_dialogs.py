"""
CSV Import/Export Dialogs - Preview, confirmation, and options for CSV operations
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QMessageBox, QGroupBox, QCheckBox, QFileDialog, QComboBox,
    QRadioButton, QButtonGroup, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import Optional

from services.tools.dtos import ImportPreview, ImportResult, ExportResult


class ImportPreviewDialog(QDialog):
    """Dialog showing preview of CSV import before confirmation."""
    
    def __init__(self, preview: ImportPreview, entity_type: str, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.entity_type = entity_type
        self.user_confirmed = False
        self.skip_conflicts = False
        self.overwrite_conflicts = False
        
        self.setWindowTitle(f"Import Preview - {entity_type.title()}")
        self.resize(900, 600)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel(f"<b>Preview: {self.entity_type.title()} Import</b>")
        header.setStyleSheet("font-size: 14pt; padding: 10px;")
        layout.addWidget(header)
        
        # Summary stats
        summary = self._create_summary_widget()
        layout.addWidget(summary)
        
        # Tabs for different categories
        tabs = QTabWidget()
        
        if self.preview.to_add:
            tabs.addTab(self._create_records_tab(self.preview.to_add, "green"), 
                       f"To Add ({len(self.preview.to_add)})")
        
        if self.preview.to_update:
            tabs.addTab(self._create_records_tab(self.preview.to_update, "blue"),
                       f"To Update ({len(self.preview.to_update)})")
        
        if self.preview.conflicts:
            tabs.addTab(self._create_records_tab(self.preview.conflicts, "orange"),
                       f"Conflicts ({len(self.preview.conflicts)})")
        
        if self.preview.exact_duplicates:
            tabs.addTab(self._create_records_tab(self.preview.exact_duplicates, "gray"),
                       f"Exact Duplicates ({len(self.preview.exact_duplicates)})")
        
        if self.preview.invalid_rows:
            tabs.addTab(self._create_errors_tab(self.preview.invalid_rows),
                       f"Errors ({len(self.preview.invalid_rows)})")
        
        if self.preview.csv_duplicates:
            tabs.addTab(self._create_records_tab(self.preview.csv_duplicates, "red"),
                       f"CSV Duplicates ({len(self.preview.csv_duplicates)})")
        
        layout.addWidget(tabs)
        
        # Conflict resolution options (only show if conflicts exist)
        if self.preview.conflicts:
            conflict_group = QGroupBox("Conflict Resolution")
            conflict_layout = QVBoxLayout(conflict_group)
            
            self.skip_conflicts_cb = QCheckBox("Skip conflicting records (import only new records)")
            self.skip_conflicts_cb.setChecked(True)  # Default to skip
            conflict_layout.addWidget(self.skip_conflicts_cb)
            
            self.overwrite_conflicts_cb = QCheckBox("Overwrite existing records with CSV data")
            conflict_layout.addWidget(self.overwrite_conflicts_cb)
            
            # Make them mutually exclusive
            self.skip_conflicts_cb.toggled.connect(
                lambda checked: self.overwrite_conflicts_cb.setChecked(False) if checked else None
            )
            self.overwrite_conflicts_cb.toggled.connect(
                lambda checked: self.skip_conflicts_cb.setChecked(False) if checked else None
            )
            
            layout.addWidget(conflict_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        proceed_btn = QPushButton("Proceed with Import")
        proceed_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        # Disable proceed if there are blocking errors
        if self.preview.has_errors:
            proceed_btn.setEnabled(False)
            proceed_btn.setToolTip("Cannot proceed - fix errors in CSV file first")
        
        proceed_btn.clicked.connect(self._on_proceed)
        button_layout.addWidget(proceed_btn)
        
        layout.addLayout(button_layout)
        
    def _create_summary_widget(self) -> QGroupBox:
        """Create summary statistics widget."""
        group = QGroupBox("Summary")
        layout = QVBoxLayout(group)
        
        summary_text = []
        
        if self.preview.to_add:
            summary_text.append(f"✓ <span style='color: green'><b>{len(self.preview.to_add)}</b> records will be added</span>")
        
        if self.preview.to_update:
            summary_text.append(f"✓ <span style='color: blue'><b>{len(self.preview.to_update)}</b> records will be updated</span>")
        
        if self.preview.exact_duplicates:
            summary_text.append(f"⊘ <span style='color: gray'><b>{len(self.preview.exact_duplicates)}</b> exact duplicates (will be skipped)</span>")
        
        if self.preview.conflicts:
            summary_text.append(f"⚠ <span style='color: orange'><b>{len(self.preview.conflicts)}</b> conflicts (will be skipped)</span>")
        
        if self.preview.invalid_rows:
            error_count = sum(1 for e in self.preview.invalid_rows if e.severity.value == "error")
            warning_count = sum(1 for e in self.preview.invalid_rows if e.severity.value == "warning")
            if error_count:
                summary_text.append(f"✗ <span style='color: red'><b>{error_count}</b> errors (BLOCKS IMPORT)</span>")
            if warning_count:
                summary_text.append(f"⚠ <span style='color: orange'><b>{warning_count}</b> warnings</span>")
        
        if self.preview.csv_duplicates:
            summary_text.append(f"✗ <span style='color: red'><b>{len(self.preview.csv_duplicates)}</b> duplicates within CSV (fix file)</span>")
        
        if not summary_text:
            summary_text.append("No changes to import")
        
        label = QLabel("<br>".join(summary_text))
        label.setTextFormat(Qt.RichText)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        return group
    
    def _create_records_tab(self, records, color_name: str) -> QWidget:
        """Create a tab showing records with their data."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        if not records:
            layout.addWidget(QLabel("No records"))
            return widget
        
        # Create table
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        
        # Get columns from first record
        first_record = records[0]
        columns = list(first_record.keys())
        
        table.setColumnCount(len(columns))
        table.setRowCount(len(records))
        table.setHorizontalHeaderLabels(columns)
        
        # Populate table
        for row_idx, record in enumerate(records):
            for col_idx, col_name in enumerate(columns):
                value = record.get(col_name, "")
                item = QTableWidgetItem(str(value) if value is not None else "")
                
                # Color code the row
                if color_name == "green":
                    item.setBackground(QColor(230, 255, 230))
                elif color_name == "blue":
                    item.setBackground(QColor(230, 240, 255))
                elif color_name == "orange":
                    item.setBackground(QColor(255, 245, 230))
                elif color_name == "red":
                    item.setBackground(QColor(255, 230, 230))
                elif color_name == "gray":
                    item.setBackground(QColor(240, 240, 240))
                
                table.setItem(row_idx, col_idx, item)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        return widget
    
    def _create_errors_tab(self, errors) -> QWidget:
        """Create a tab showing validation errors."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        if not errors:
            layout.addWidget(QLabel("No errors"))
            return widget
        
        # Create table for errors
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Row", "Field", "Value", "Error Message"])
        table.setRowCount(len(errors))
        
        for row_idx, error in enumerate(errors):
            # Row number
            item = QTableWidgetItem(str(error.row_number))
            if error.severity.value == "error":
                item.setBackground(QColor(255, 230, 230))
            else:
                item.setBackground(QColor(255, 245, 230))
            table.setItem(row_idx, 0, item)
            
            # Field
            item = QTableWidgetItem(error.field)
            if error.severity.value == "error":
                item.setBackground(QColor(255, 230, 230))
            else:
                item.setBackground(QColor(255, 245, 230))
            table.setItem(row_idx, 1, item)
            
            # Value
            value_str = str(error.value) if error.value is not None else ""
            item = QTableWidgetItem(value_str)
            if error.severity.value == "error":
                item.setBackground(QColor(255, 230, 230))
            else:
                item.setBackground(QColor(255, 245, 230))
            table.setItem(row_idx, 2, item)
            
            # Error message
            item = QTableWidgetItem(error.message)
            if error.severity.value == "error":
                item.setBackground(QColor(255, 230, 230))
            else:
                item.setBackground(QColor(255, 245, 230))
            table.setItem(row_idx, 3, item)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        return widget
    
    def _on_proceed(self):
        """Handle proceed button click."""
        # Capture conflict resolution choices if conflicts exist
        if self.preview.conflicts:
            self.skip_conflicts = self.skip_conflicts_cb.isChecked()
            self.overwrite_conflicts = self.overwrite_conflicts_cb.isChecked()
        
        # Show confirmation if there are warnings
        if self.preview.has_warnings and not self.preview.has_errors:
            reply = QMessageBox.question(
                self,
                "Warnings Detected",
                "There are warnings in the import. Are you sure you want to proceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        self.user_confirmed = True
        self.accept()


class ImportResultDialog(QDialog):
    """Dialog showing the results of a CSV import."""
    
    def __init__(self, result: ImportResult, parent=None):
        super().__init__(parent)
        self.result = result
        
        self.setWindowTitle("Import Complete")
        self.resize(600, 400)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header
        if self.result.success:
            header = QLabel("<b>✓ Import Successful</b>")
            header.setStyleSheet("color: green; font-size: 14pt; padding: 10px;")
        else:
            header = QLabel("<b>✗ Import Failed</b>")
            header.setStyleSheet("color: red; font-size: 14pt; padding: 10px;")
        layout.addWidget(header)
        
        # Summary
        summary_text = [
            f"Entity Type: {self.result.entity_type}",
            f"Records Added: {self.result.records_added}",
            f"Records Updated: {self.result.records_updated}",
            f"Records Skipped: {self.result.records_skipped}",
            f"Total Processed: {self.result.total_processed}"
        ]
        
        summary = QLabel("\n".join(summary_text))
        summary.setStyleSheet("padding: 10px; background-color: #f5f5f5; border-radius: 4px;")
        layout.addWidget(summary)
        
        # Errors
        if self.result.errors:
            errors_group = QGroupBox("Errors")
            errors_layout = QVBoxLayout(errors_group)
            errors_text = QTextEdit()
            errors_text.setPlainText("\n".join(self.result.errors))
            errors_text.setReadOnly(True)
            errors_text.setMaximumHeight(150)
            errors_layout.addWidget(errors_text)
            layout.addWidget(errors_group)
        
        # Warnings
        if self.result.warnings:
            warnings_group = QGroupBox("Warnings")
            warnings_layout = QVBoxLayout(warnings_group)
            warnings_text = QTextEdit()
            warnings_text.setPlainText("\n".join(self.result.warnings))
            warnings_text.setReadOnly(True)
            warnings_text.setMaximumHeight(150)
            warnings_layout.addWidget(warnings_text)
            layout.addWidget(warnings_group)
        
        layout.addStretch()
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class ExportOptionsDialog(QDialog):
    """Dialog for selecting export options."""
    
    entity_selected = Signal(str)  # Emits entity type when selected
    
    def __init__(self, parent=None, mode="export"):
        super().__init__(parent)
        self.selected_entity = None
        self.export_all = False
        self.mode = mode  # "export", "import", or "template"
        
        # Set default title based on mode
        if mode == "import":
            self.setWindowTitle("Import CSV")
        elif mode == "template":
            self.setWindowTitle("Download Template")
        else:
            self.setWindowTitle("Export CSV")
        
        self.resize(400, 350)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header - text varies by mode
        if self.mode == "import":
            header_text = "<b>Select Data to Import</b>"
        elif self.mode == "template":
            header_text = "<b>Select Template to Download</b>"
        else:
            header_text = "<b>Select Data to Export</b>"
        
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 12pt; padding: 10px;")
        layout.addWidget(header)
        
        # Radio buttons for single vs all (only for export and template modes)
        if self.mode in ["export", "template"]:
            selection_group = QGroupBox("Selection")
            selection_layout = QVBoxLayout(selection_group)
            
            self.button_group = QButtonGroup(self)
            
            self.single_radio = QRadioButton("Single entity type")
            self.single_radio.setChecked(True)
            self.single_radio.toggled.connect(self._on_selection_changed)
            self.button_group.addButton(self.single_radio)
            selection_layout.addWidget(self.single_radio)
            
            if self.mode == "export":
                all_text = "All entity types (creates ZIP file)"
            else:
                all_text = "All templates (creates ZIP file)"
            
            self.all_radio = QRadioButton(all_text)
            self.all_radio.toggled.connect(self._on_selection_changed)
            self.button_group.addButton(self.all_radio)
            selection_layout.addWidget(self.all_radio)
            
            layout.addWidget(selection_group)
        
        # Entity type selector
        entity_group = QGroupBox("Entity Type")
        entity_layout = QVBoxLayout(entity_group)
        
        self.entity_combo = QComboBox()
        # Only show entities that have schemas defined
        self.entity_combo.addItems([
            "Purchases",
            "Redemptions",
            "Game Sessions",
            "Users",
            "Sites",
            "Cards",
            "Redemption Methods",
            "Redemption Method Types",
            "Game Types",
            "Games"
        ])
        entity_layout.addWidget(self.entity_combo)
        layout.addWidget(entity_group)
        
        # Store entity group for enabling/disabling
        self.entity_group = entity_group
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Action button - text varies by mode
        if self.mode == "import":
            action_text = "Import"
        elif self.mode == "template":
            action_text = "Download"
        else:
            action_text = "Export"
        
        export_btn = QPushButton(action_text)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        export_btn.clicked.connect(self._on_export)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)
    
    def _on_selection_changed(self):
        """Handle radio button selection change."""
        if self.mode in ["export", "template"]:
            # Enable/disable entity combo based on selection
            is_single = self.single_radio.isChecked()
            self.entity_group.setEnabled(is_single)
    
    def _on_export(self):
        """Handle export button click."""
        # Check if "export all" is selected
        if self.mode in ["export", "template"] and hasattr(self, 'all_radio') and self.all_radio.isChecked():
            self.export_all = True
            self.selected_entity = None  # No specific entity
            self.accept()
            return
        
        # Map display names to entity types
        entity_map = {
            "Purchases": "purchases",
            "Redemptions": "redemptions",
            "Game Sessions": "game_sessions",
            "Users": "users",
            "Sites": "sites",
            "Cards": "cards",
            "Redemption Methods": "redemption_methods",
            "Redemption Method Types": "redemption_method_types",
            "Game Types": "game_types",
            "Games": "games"
        }
        
        display_name = self.entity_combo.currentText()
        self.selected_entity = entity_map.get(display_name)
        
        if self.selected_entity:
            self.accept()
