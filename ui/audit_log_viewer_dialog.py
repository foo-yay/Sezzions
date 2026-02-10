"""
Audit Log Viewer Dialog - Browse and filter audit trail (Issue #92)
"""
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, date, timedelta
import tempfile
import os


class AuditLogViewerDialog(QtWidgets.QDialog):
    """Dialog for viewing and filtering audit log entries"""
    
    def __init__(self, audit_service, parent=None):
        super().__init__(parent)
        self.audit_service = audit_service
        self.current_entries = []
        
        self.setWindowTitle("Audit Log Viewer")
        self.resize(1000, 700)
        
        self._setup_ui()
        self._load_entries()
    
    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title_label = QtWidgets.QLabel("Audit Log")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Filters section
        filter_group = QtWidgets.QGroupBox("Filters")
        filter_layout = QtWidgets.QGridLayout(filter_group)
        filter_layout.setSpacing(8)
        
        row = 0
        
        # Date range presets
        filter_layout.addWidget(QtWidgets.QLabel("Date Range:"), row, 0)
        self.date_preset_combo = QtWidgets.QComboBox()
        self.date_preset_combo.addItem("All Time", None)
        self.date_preset_combo.addItem("Today", "today")
        self.date_preset_combo.addItem("Last 7 Days", "last_7")
        self.date_preset_combo.addItem("Last 30 Days", "last_30")
        self.date_preset_combo.addItem("This Month", "this_month")
        self.date_preset_combo.addItem("This Year", "this_year")
        self.date_preset_combo.addItem("Custom...", "custom")
        self.date_preset_combo.currentIndexChanged.connect(self._on_date_preset_changed)
        filter_layout.addWidget(self.date_preset_combo, row, 1)
        
        # Custom date range (initially hidden)
        self.start_date_edit = QtWidgets.QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QtCore.QDate.currentDate().addMonths(-1))
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(QtWidgets.QLabel("From:"), row, 2)
        filter_layout.addWidget(self.start_date_edit, row, 3)
        
        self.end_date_edit = QtWidgets.QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QtCore.QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(QtWidgets.QLabel("To:"), row, 4)
        filter_layout.addWidget(self.end_date_edit, row, 5)
        
        # Hide custom date inputs initially
        self.start_date_edit.setVisible(False)
        self.end_date_edit.setVisible(False)
        filter_layout.itemAtPosition(row, 2).widget().setVisible(False)
        filter_layout.itemAtPosition(row, 4).widget().setVisible(False)
        
        row += 1
        
        # Table filter
        filter_layout.addWidget(QtWidgets.QLabel("Table:"), row, 0)
        self.table_combo = QtWidgets.QComboBox()
        self.table_combo.setMinimumWidth(150)
        self.table_combo.addItem("All Tables", None)
        for table in ["purchases", "redemptions", "game_sessions", "account_adjustments", "__system__"]:
            self.table_combo.addItem(table, table)
        self.table_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.table_combo, row, 1)
        
        # Action filter
        filter_layout.addWidget(QtWidgets.QLabel("Action:"), row, 2)
        self.action_combo = QtWidgets.QComboBox()
        self.action_combo.setMinimumWidth(120)
        self.action_combo.addItem("All Actions", None)
        for action in ["CREATE", "UPDATE", "DELETE", "RESTORE", "UNDO", "REDO", "BACKUP", "RESTORE_DB", "RESET"]:
            self.action_combo.addItem(action, action)
        self.action_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.action_combo, row, 3)
        
        # Limit
        filter_layout.addWidget(QtWidgets.QLabel("Limit:"), row, 4)
        self.limit_spin = QtWidgets.QSpinBox()
        self.limit_spin.setMinimum(10)
        self.limit_spin.setMaximum(10000)
        self.limit_spin.setValue(100)
        self.limit_spin.setSingleStep(50)
        self.limit_spin.valueChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.limit_spin, row, 5)
        
        row += 1
        
        # Action buttons row
        button_row = QtWidgets.QHBoxLayout()
        
        # Refresh button
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._load_entries)
        button_row.addWidget(refresh_btn)
        
        # Export CSV button
        self.export_btn = QtWidgets.QPushButton("📊 Export to CSV")
        self.export_btn.clicked.connect(self._export_to_csv)
        button_row.addWidget(self.export_btn)
        
        button_row.addStretch()
        
        filter_layout.addLayout(button_row, row, 0, 1, 6)
        
        layout.addWidget(filter_group)
        
        # Split view: table on top, details on bottom
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        
        # Table view
        self.table_widget = QtWidgets.QTableWidget()
        self.table_widget.setColumnCount(7)
        self.table_widget.setHorizontalHeaderLabels([
            "ID", "Timestamp", "Action", "Table", "Record ID", "User", "Group ID"
        ])
        self.table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setSortingEnabled(True)  # Enable column sorting
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.table_widget.setColumnWidth(0, 60)   # ID
        self.table_widget.setColumnWidth(1, 180)  # Timestamp
        self.table_widget.setColumnWidth(2, 100)  # Action
        self.table_widget.setColumnWidth(3, 150)  # Table
        self.table_widget.setColumnWidth(4, 80)   # Record ID
        self.table_widget.setColumnWidth(5, 100)  # User
        self.table_widget.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.Stretch)  # Group ID
        self.table_widget.itemSelectionChanged.connect(self._on_selection_changed)
        
        splitter.addWidget(self.table_widget)
        
        # Details panel
        details_group = QtWidgets.QGroupBox("Entry Details")
        details_layout = QtWidgets.QVBoxLayout(details_group)
        
        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setFont(QtGui.QFont("Courier", 10))
        details_layout.addWidget(self.details_text)
        
        splitter.addWidget(details_group)
        
        # Set initial splitter sizes (60% table, 40% details)
        splitter.setSizes([420, 280])
        
        layout.addWidget(splitter, 1)
        
        # Button row
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_entries(self):
        """Load audit log entries from database"""
        try:
            table_name = self.table_combo.currentData()
            action = self.action_combo.currentData()
            limit = self.limit_spin.value()
            
            self.current_entries = self.audit_service.get_audit_log(
                table_name=table_name,
                action=action,
                limit=limit
            )
            
            self._populate_table()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Loading Audit Log",
                f"Failed to load audit log entries:\n\n{str(e)}"
            )
    
    def _apply_filters(self):
        """Apply filters and reload entries"""
        self._load_entries()
    
    def _on_date_preset_changed(self):
        """Handle date preset selection"""
        preset = self.date_preset_combo.currentData()
        
        # Show/hide custom date inputs
        is_custom = preset == "custom"
        self.start_date_edit.setVisible(is_custom)
        self.end_date_edit.setVisible(is_custom)
        # Also show/hide labels
        filter_layout = self.date_preset_combo.parent().layout()
        for i in range(filter_layout.count()):
            item = filter_layout.itemAtPosition(0, i)
            if item and item.widget() and item.widget().text() in ["From:", "To:"]:
                item.widget().setVisible(is_custom)
        
        if not is_custom:
            self._apply_filters()
    
    def _get_date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get date range based on current preset selection"""
        preset = self.date_preset_combo.currentData()
        
        if preset is None:  # All Time
            return None, None
        elif preset == "custom":
            return (
                self.start_date_edit.date().toPython(),
                self.end_date_edit.date().toPython()
            )
        elif preset == "today":
            today = date.today()
            return today, today
        elif preset == "last_7":
            today = date.today()
            return today - timedelta(days=7), today
        elif preset == "last_30":
            today = date.today()
            return today - timedelta(days=30), today
        elif preset == "this_month":
            today = date.today()
            return date(today.year, today.month, 1), today
        elif preset == "this_year":
            today = date.today()
            return date(today.year, 1, 1), today
        
        return None, None
    
    def _export_to_csv(self):
        """Export current audit log to CSV"""
        try:
            # Get date range for filtering
            start_date, end_date = self._get_date_range()
            
            # Prompt for file location
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Audit Log to CSV",
                f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Ensure .csv extension
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'
            
            # Export using audit service
            row_count = self.audit_service.export_audit_log_csv(
                file_path,
                start_date=start_date,
                end_date=end_date
            )
            
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {row_count} audit log entries to:\n{file_path}"
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export audit log:\n\n{str(e)}"
            )
    
    def _populate_table(self):
        """Populate table with current entries"""
        self.table_widget.setRowCount(0)
        
        for entry in self.current_entries:
            row = self.table_widget.rowCount()
            self.table_widget.insertRow(row)
            
            # ID
            id_item = QtWidgets.QTableWidgetItem(str(entry.get('id', '')))
            id_item.setData(QtCore.Qt.UserRole, entry)  # Store full entry
            self.table_widget.setItem(row, 0, id_item)
            
            # Timestamp
            timestamp = entry.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            self.table_widget.setItem(row, 1, QtWidgets.QTableWidgetItem(timestamp))
            
            # Action
            action = entry.get('action', '')
            action_item = QtWidgets.QTableWidgetItem(action)
            # Color-code actions
            if action in ["CREATE", "RESTORE"]:
                action_item.setForeground(QtGui.QColor("#2ecc71"))  # Green
            elif action in ["DELETE", "RESET"]:
                action_item.setForeground(QtGui.QColor("#e74c3c"))  # Red
            elif action in ["UPDATE", "UNDO", "REDO"]:
                action_item.setForeground(QtGui.QColor("#f39c12"))  # Orange
            self.table_widget.setItem(row, 2, action_item)
            
            # Table
            self.table_widget.setItem(row, 3, QtWidgets.QTableWidgetItem(entry.get('table_name', '')))
            
            # Record ID
            record_id = entry.get('record_id')
            self.table_widget.setItem(row, 4, QtWidgets.QTableWidgetItem(str(record_id) if record_id else '—'))
            
            # User
            self.table_widget.setItem(row, 5, QtWidgets.QTableWidgetItem(entry.get('user_name', '')))
            
            # Group ID (truncated for display)
            group_id = entry.get('group_id', '')
            if group_id:
                group_id = group_id[:8] + '…'
            self.table_widget.setItem(row, 6, QtWidgets.QTableWidgetItem(group_id))
        
        # Update status
        self.setWindowTitle(f"Audit Log Viewer ({len(self.current_entries)} entries)")
    
    def _on_selection_changed(self):
        """Handle row selection to show details"""
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            self.details_text.clear()
            return
        
        row = selected_rows[0].row()
        id_item = self.table_widget.item(row, 0)
        entry = id_item.data(QtCore.Qt.UserRole)
        
        if not entry:
            self.details_text.clear()
            return
        
        # Format entry details
        details = []
        details.append(f"=== Audit Entry #{entry.get('id')} ===\n")
        details.append(f"Timestamp: {entry.get('timestamp', 'N/A')}")
        details.append(f"Action:    {entry.get('action', 'N/A')}")
        details.append(f"Table:     {entry.get('table_name', 'N/A')}")
        details.append(f"Record ID: {entry.get('record_id', 'N/A')}")
        details.append(f"User:      {entry.get('user_name', 'N/A')}")
        details.append(f"Group ID:  {entry.get('group_id', 'N/A')}")
        
        if entry.get('details'):
            details.append(f"\nDetails:\n{entry['details']}")
        
        if entry.get('old_data'):
            details.append("\n--- Old Data (before change) ---")
            try:
                old_data = entry['old_data'] if isinstance(entry['old_data'], dict) else json.loads(entry['old_data'])
                details.append(json.dumps(old_data, indent=2))
            except:
                details.append(str(entry['old_data']))
        
        if entry.get('new_data'):
            details.append("\n--- New Data (after change) ---")
            try:
                new_data = entry['new_data'] if isinstance(entry['new_data'], dict) else json.loads(entry['new_data'])
                details.append(json.dumps(new_data, indent=2))
            except:
                details.append(str(entry['new_data']))
        
        self.details_text.setPlainText("\n".join(details))
