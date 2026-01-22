"""
Unrealized tab - View open positions (sites with remaining basis)
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date
from app_facade import AppFacade
from models.unrealized_position import UnrealizedPosition
from ui.date_filter_widget import DateFilterWidget


class UnrealizedTab(QtWidgets.QWidget):
    """Tab for viewing unrealized positions (open positions with remaining basis)"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.positions = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Unrealized Positions - Sites With Remaining Basis")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search positions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_positions)
        header_layout.addWidget(self.search_edit)
        
        layout.addLayout(header_layout)
        
        # Info label
        info = QtWidgets.QLabel("💰 Shows current open positions with remaining purchase basis. Unrealized P/L is NOT taxable until position is closed.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filter
        self.date_filter = DateFilterWidget()
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        self.close_btn = QtWidgets.QPushButton("🔒 Close Balance")
        self.close_btn.setToolTip("Create $0 redemption to mark position dormant")
        self.close_btn.clicked.connect(self._close_balance)
        self.close_btn.setEnabled(False)
        toolbar.addWidget(self.close_btn)
        
        self.notes_btn = QtWidgets.QPushButton("📝 Add Notes")
        self.notes_btn.clicked.connect(self._add_notes)
        self.notes_btn.setEnabled(False)
        toolbar.addWidget(self.notes_btn)
        
        toolbar.addStretch()
        
        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Site", "User", "Start Date", "Purchase Basis", 
            "Current SC", "Current Value", "Unrealized P/L", 
            "Last Activity", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._add_notes)
        
        layout.addWidget(self.table)
        
        # Totals
        totals_layout = QtWidgets.QHBoxLayout()
        totals_layout.addStretch()
        self.totals_label = QtWidgets.QLabel()
        self.totals_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        totals_layout.addWidget(self.totals_label)
        layout.addLayout(totals_layout)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload unrealized positions from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.positions = self.facade.get_unrealized_positions(start_date=start_date, end_date=end_date)
        self._populate_table(self.positions)
        self._update_totals()
    
    def _populate_table(self, positions):
        """Populate table with position data"""
        self.table.setRowCount(len(positions))
        
        for row, pos in enumerate(positions):
            # Store position data
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(pos.site_name))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(pos.user_name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(pos.start_date)))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${pos.purchase_basis:,.2f}"))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{pos.current_sc:,.2f}"))
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"${pos.current_value:,.2f}"))
            
            # Color P/L
            pl_item = QtWidgets.QTableWidgetItem(f"${pos.unrealized_pl:,.2f}")
            if pos.unrealized_pl > 0:
                pl_item.setForeground(QtGui.QBrush(QtGui.QColor(0, 150, 0)))  # Green
            elif pos.unrealized_pl < 0:
                pl_item.setForeground(QtGui.QBrush(QtGui.QColor(200, 0, 0)))  # Red
            self.table.setItem(row, 6, pl_item)
            
            self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(str(pos.last_activity) if pos.last_activity else ""))
            self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(pos.notes))
            
            # Right-align numbers
            for col in [3, 4, 5, 6]:
                self.table.item(row, col).setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    
    def _update_totals(self):
        """Update totals footer"""
        if not self.positions:
            self.totals_label.setText("")
            return
        
        total_basis = sum(p.purchase_basis for p in self.positions)
        total_value = sum(p.current_value for p in self.positions)
        total_pl = sum(p.unrealized_pl for p in self.positions)
        
        color = "green" if total_pl >= 0 else "red"
        self.totals_label.setText(
            f"Totals: Basis: ${total_basis:,.2f} | Value: ${total_value:,.2f} | "
            f"<span style='color: {color}'>Unrealized P/L: ${total_pl:,.2f}</span>"
        )
    
    def _filter_positions(self, text):
        """Filter positions by search text"""
        if not text:
            self._populate_table(self.positions)
            return
        
        text = text.lower()
        filtered = [
            p for p in self.positions
            if text in p.site_name.lower() or text in p.user_name.lower()
        ]
        self._populate_table(filtered)
    
    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        has_selection = len(self.table.selectedItems()) > 0
        self.close_btn.setEnabled(has_selection)
        self.notes_btn.setEnabled(has_selection)
    
    def _close_balance(self):
        """Close position (create $0 redemption to mark dormant)"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        # TODO: Implement close balance logic
        # - Create $0 redemption with is_free_sc=True
        # - Mark purchases as 'dormant' status
        QtWidgets.QMessageBox.information(
            self, "Close Balance", 
            "Close balance feature coming soon.\n\n"
            "This will create a $0 redemption to mark the position as closed/dormant."
        )
    
    def _add_notes(self):
        """Add/edit notes for position"""
        row = self.table.currentRow()
        if row < 0:
            return
        
        current_notes = self.table.item(row, 8).text() if self.table.item(row, 8) else ""
        
        notes, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Position Notes",
            f"Notes for {self.table.item(row, 0).text()} / {self.table.item(row, 1).text()}:",
            current_notes
        )
        
        if ok:
            # TODO: Save notes to database
            self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(notes))
            QtWidgets.QMessageBox.information(
                self, "Notes", "Note: Position notes are not yet persisted to database."
            )
    
    def _export_csv(self):
        """Export positions to CSV"""
        if not self.positions:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Unrealized Positions", 
            f"unrealized_positions_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Site", "User", "Start Date", "Purchase Basis", 
                        "Current SC", "Current Value", "Unrealized P/L",
                        "Last Activity", "Notes"
                    ])
                    for pos in self.positions:
                        writer.writerow([
                            pos.site_name, pos.user_name, pos.start_date,
                            pos.purchase_basis, pos.current_sc, pos.current_value,
                            pos.unrealized_pl, pos.last_activity or "", pos.notes
                        ])
                
                QtWidgets.QMessageBox.information(
                    self, "Export Complete", 
                    f"Exported {len(self.positions)} positions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )
