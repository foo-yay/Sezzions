"""
Realized tab - View completed redemptions (cash flow tracking)
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, timedelta
from app_facade import AppFacade
from models.realized_transaction import RealizedTransaction


class RealizedTab(QtWidgets.QWidget):
    """Tab for viewing realized transactions (completed redemption cash flow)"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.transactions = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Realized Transactions - Completed Redemptions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search transactions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_transactions)
        header_layout.addWidget(self.search_edit)
        
        layout.addLayout(header_layout)
        
        # Info label
        info = QtWidgets.QLabel("💵 Shows cash flow from redemptions (Cost Basis vs Payout). This is NOT taxable P/L - see Game Sessions for tax calculations.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filters
        filter_group = QtWidgets.QGroupBox("🎯 Filters")
        filter_layout = QtWidgets.QVBoxLayout()
        
        # Date filter row
        date_row = QtWidgets.QHBoxLayout()
        
        date_row.addWidget(QtWidgets.QLabel("From:"))
        self.start_date = QtWidgets.QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QtCore.QDate.currentDate().addDays(-30))
        self.start_date.dateChanged.connect(self.refresh_data)
        date_row.addWidget(self.start_date)
        
        date_row.addWidget(QtWidgets.QLabel("To:"))
        self.end_date = QtWidgets.QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QtCore.QDate.currentDate())
        self.end_date.dateChanged.connect(self.refresh_data)
        date_row.addWidget(self.end_date)
        
        # Quick buttons
        today_btn = QtWidgets.QPushButton("Today")
        today_btn.clicked.connect(self._filter_today)
        date_row.addWidget(today_btn)
        
        last30_btn = QtWidgets.QPushButton("Last 30 Days")
        last30_btn.clicked.connect(self._filter_last_30)
        date_row.addWidget(last30_btn)
        
        this_month_btn = QtWidgets.QPushButton("This Month")
        this_month_btn.clicked.connect(self._filter_this_month)
        date_row.addWidget(this_month_btn)
        
        this_year_btn = QtWidgets.QPushButton("This Year")
        this_year_btn.clicked.connect(self._filter_this_year)
        date_row.addWidget(this_year_btn)
        
        date_row.addStretch()
        filter_layout.addLayout(date_row)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)
        
        toolbar.addStretch()
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date", "Site", "User", "Cost Basis", 
            "Payout", "Net Cash Flow", "Method", "Notes"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        
        # Set column widths
        self.table.setColumnWidth(0, 100)  # Date
        self.table.setColumnWidth(1, 120)  # Site
        self.table.setColumnWidth(2, 100)  # User
        self.table.setColumnWidth(3, 120)  # Cost Basis
        self.table.setColumnWidth(4, 120)  # Payout
        self.table.setColumnWidth(5, 120)  # Net Cash Flow
        self.table.setColumnWidth(6, 120)  # Method
        
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
        """Reload realized transactions from database"""
        start = self.start_date.date().toPython()
        end = self.end_date.date().toPython()
        
        self.transactions = self.facade.get_realized_transactions(
            start_date=start,
            end_date=end
        )
        self._populate_table(self.transactions)
        self._update_totals()
    
    def _populate_table(self, transactions):
        """Populate table with transaction data"""
        self.table.setRowCount(len(transactions))
        
        for row, trans in enumerate(transactions):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(trans.redemption_date)))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(trans.site_name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(trans.user_name))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${trans.cost_basis:,.2f}"))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"${trans.payout:,.2f}"))
            
            # Color Net Cash Flow
            cf_item = QtWidgets.QTableWidgetItem(f"${trans.net_pl:,.2f}")
            if trans.net_pl > 0:
                cf_item.setForeground(QtGui.QBrush(QtGui.QColor(0, 150, 0)))  # Green
            elif trans.net_pl < 0:
                cf_item.setForeground(QtGui.QBrush(QtGui.QColor(200, 0, 0)))  # Red
            self.table.setItem(row, 5, cf_item)
            
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(trans.method_name or ""))
            self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(trans.notes))
            
            # Right-align numbers
            for col in [3, 4, 5]:
                self.table.item(row, col).setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    
    def _update_totals(self):
        """Update totals footer"""
        if not self.transactions:
            self.totals_label.setText("")
            return
        
        total_basis = sum(t.cost_basis for t in self.transactions)
        total_payout = sum(t.payout for t in self.transactions)
        total_cf = sum(t.net_pl for t in self.transactions)
        
        color = "green" if total_cf >= 0 else "red"
        self.totals_label.setText(
            f"Totals: Cost Basis: ${total_basis:,.2f} | Payout: ${total_payout:,.2f} | "
            f"<span style='color: {color}'>Net Cash Flow: ${total_cf:,.2f}</span>"
        )
    
    def _filter_transactions(self, text):
        """Filter transactions by search text"""
        if not text:
            self._populate_table(self.transactions)
            return
        
        text = text.lower()
        filtered = [
            t for t in self.transactions
            if text in t.site_name.lower() or text in t.user_name.lower() 
            or (t.method_name and text in t.method_name.lower())
        ]
        self._populate_table(filtered)
    
    def _filter_today(self):
        """Filter to today only"""
        today = QtCore.QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)
    
    def _filter_last_30(self):
        """Filter to last 30 days"""
        today = QtCore.QDate.currentDate()
        self.start_date.setDate(today.addDays(-30))
        self.end_date.setDate(today)
    
    def _filter_this_month(self):
        """Filter to current month"""
        today = QtCore.QDate.currentDate()
        first_of_month = QtCore.QDate(today.year(), today.month(), 1)
        self.start_date.setDate(first_of_month)
        self.end_date.setDate(today)
    
    def _filter_this_year(self):
        """Filter to current year"""
        today = QtCore.QDate.currentDate()
        first_of_year = QtCore.QDate(today.year(), 1, 1)
        self.start_date.setDate(first_of_year)
        self.end_date.setDate(today)
    
    def _export_csv(self):
        """Export transactions to CSV"""
        if not self.transactions:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Realized Transactions", 
            f"realized_transactions_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "Date", "Site", "User", "Cost Basis", "Payout",
                        "Net Cash Flow", "Method", "Notes"
                    ])
                    for trans in self.transactions:
                        writer.writerow([
                            trans.redemption_date, trans.site_name, trans.user_name,
                            trans.cost_basis, trans.payout, trans.net_pl,
                            trans.method_name or "", trans.notes
                        ])
                
                QtWidgets.QMessageBox.information(
                    self, "Export Complete", 
                    f"Exported {len(self.transactions)} transactions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )
