"""
Expenses tab - Manage expenses
"""
from datetime import date, datetime
from decimal import Decimal
from PySide6 import QtWidgets, QtCore
from app_facade import AppFacade
from models.expense import Expense
from ui.date_filter_widget import DateFilterWidget
from ui.table_header_filters import TableHeaderFilter


EXPENSE_CATEGORIES = [
    "Advertising",
    "Car and Truck Expenses",
    "Commissions and Fees",
    "Contract Labor",
    "Depreciation",
    "Insurance (Business)",
    "Interest (Mortgage/Other)",
    "Legal and Professional Services",
    "Office Expense",
    "Rent or Lease (Vehicles/Equipment)",
    "Rent or Lease (Other Business Property)",
    "Repairs and Maintenance",
    "Supplies",
    "Taxes and Licenses",
    "Travel",
    "Meals (Deductible)",
    "Utilities",
    "Wages (Not Contract Labor)",
    "Other Expenses",
]


def validate_currency(value_str: str, allow_zero: bool = True):
    value_str = str(value_str).strip()
    if not value_str:
        return False, "Amount cannot be empty"
    try:
        value = float(value_str)
        if value < 0 or (not allow_zero and value == 0):
            return False, "Amount must be greater than zero"
        decimal_str = str(value)
        if "." in decimal_str:
            decimal_places = len(decimal_str.split(".")[1])
            if decimal_places > 2 and not decimal_str.split(".")[1].rstrip("0")[:2] == decimal_str.split(".")[1].rstrip("0"):
                if len(decimal_str.split(".")[1].rstrip("0")) > 2:
                    return False, "Amount cannot have more than 2 decimal places"
        normalized = round(value, 2)
        return True, normalized
    except ValueError:
        return False, "Please enter a valid number"


class ExpensesTab(QtWidgets.QWidget):
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.expenses = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Expenses")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search expenses...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_expenses)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)

        layout.addLayout(header_layout)

        info = QtWidgets.QLabel("Log deductible business expenses here.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)

        self.date_filter = DateFilterWidget()
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)

        toolbar = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("➕ Add Expense")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_expense)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_expense)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_expense)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_expense)
        self.delete_btn.setVisible(False)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch(1)

        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        self.columns = ["Date", "Category", "Vendor", "User", "Amount", "Description"]
        self.table = QtWidgets.QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_expense)
        layout.addWidget(self.table)

        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.refresh_data)

        self.refresh_data()

    def refresh_data(self):
        start_date, end_date = self.date_filter.get_date_range()
        self.expenses = self.facade.get_expenses(start_date=start_date, end_date=end_date)
        self._populate_table()

    def _populate_table(self):
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = []
            for e in self.expenses:
                parts = [
                    str(e.expense_date),
                    e.category or "",
                    e.vendor or "",
                    e.user_name or "",
                    str(e.amount),
                    e.description or "",
                ]
                haystack = " ".join(parts).lower()
                if search_text in haystack:
                    filtered.append(e)
        else:
            filtered = self.expenses

        filtered.sort(key=lambda e: e.expense_date, reverse=True)
        self.table.setRowCount(len(filtered))

        for row, expense in enumerate(filtered):
            date_item = QtWidgets.QTableWidgetItem(str(expense.expense_date))
            date_item.setData(QtCore.Qt.UserRole, expense.id)
            self.table.setItem(row, 0, date_item)
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(expense.category or "Other Expenses"))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(expense.vendor or ""))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(expense.user_name or ""))
            amount_item = QtWidgets.QTableWidgetItem(f"${expense.amount:,.2f}")
            amount_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 4, amount_item)
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(expense.description or ""))

        self.table_filter.apply_filters()

    def _filter_expenses(self):
        self._populate_table()

    def _clear_search(self):
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        self._populate_table()

    def _clear_all_filters(self):
        self.search_edit.clear()
        self.date_filter.set_all_time()
        self.table.clearSelection()
        self._on_selection_changed()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()
        self.refresh_data()

    def _on_selection_changed(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        self.view_btn.setVisible(len(selected) == 1)
        self.edit_btn.setVisible(len(selected) == 1)
        self.delete_btn.setVisible(has_selection)

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def _add_expense(self):
        users = self.facade.get_all_users(active_only=True)
        dialog = ExpenseDialog(users, parent=self)
        if dialog.exec():
            data, error = dialog.collect_data()
            if error:
                QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                self.facade.create_expense(**data)
                self.refresh_data()
                QtWidgets.QMessageBox.information(self, "Success", "Expense added")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to add expense:\n{e}")

    def _edit_expense(self):
        ids = self._selected_ids()
        if not ids:
            return
        expense = self.facade.get_expense(ids[0])
        if not expense:
            return
        users = self.facade.get_all_users(active_only=True)
        dialog = ExpenseDialog(users, expense=expense, parent=self)
        if dialog.exec():
            data, error = dialog.collect_data()
            if error:
                QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                self.facade.update_expense(expense.id, **data)
                self.refresh_data()
                QtWidgets.QMessageBox.information(self, "Success", "Expense updated")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to update expense:\n{e}")

    def _view_expense(self, *_args):
        ids = self._selected_ids()
        if not ids:
            return
        expense = self.facade.get_expense(ids[0])
        if not expense:
            return
        dialog = ExpenseViewDialog(
            expense,
            parent=self,
            on_edit=self._edit_expense,
            on_delete=lambda: self._delete_expense_by_id(expense.id),
        )
        dialog.exec()

    def _delete_expense(self):
        ids = self._selected_ids()
        if not ids:
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(ids)} expense{'s' if len(ids) != 1 else ''}?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        for expense_id in ids:
            self.facade.delete_expense(expense_id)
        self.refresh_data()
        QtWidgets.QMessageBox.information(self, "Success", "Expense(s) deleted")

    def _delete_expense_by_id(self, expense_id: int):
        self.facade.delete_expense(expense_id)
        self.refresh_data()

    def _export_csv(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Expenses",
            f"expenses_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)",
        )
        if not filename:
            return
        try:
            import csv
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.columns)
                for row in range(self.table.rowCount()):
                    if self.table.isRowHidden(row):
                        continue
                    row_values = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_values.append(item.text() if item else "")
                    writer.writerow(row_values)
            QtWidgets.QMessageBox.information(self, "Export Complete", f"Exported expenses to:\n{filename}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export Error", f"Failed to export:\n{e}")


class ExpenseDialog(QtWidgets.QDialog):
    def __init__(self, users, expense: Expense = None, parent=None):
        super().__init__(parent)
        self.users = users
        self.expense = expense
        self.setWindowTitle("Edit Expense" if expense else "Add Expense")
        self.resize(620, 420)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        self.date_edit = QtWidgets.QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QtCore.QDate.currentDate())
        if expense:
            self.date_edit.setDate(QtCore.QDate.fromString(str(expense.expense_date), "yyyy-MM-dd"))
        self.today_btn = QtWidgets.QPushButton("Today")
        self.today_btn.setObjectName("MiniButton")
        self.today_btn.clicked.connect(self._set_today)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.setObjectName("MiniButton")
        self.now_btn.clicked.connect(self._set_now)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(QtWidgets.QLabel("Time:"))
        date_row.addWidget(self.time_edit, 1)
        date_row.addWidget(self.now_btn)

        self.amount_edit = QtWidgets.QLineEdit()
        if expense:
            self.amount_edit.setText(str(expense.amount))

        self.vendor_edit = QtWidgets.QLineEdit()
        if expense:
            self.vendor_edit.setText(expense.vendor or "")

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItem("")
        for user in users:
            self.user_combo.addItem(user.name, user.id)
        if expense and expense.user_id:
            idx = self.user_combo.findData(expense.user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(EXPENSE_CATEGORIES)
        if expense:
            idx = self.category_combo.findText(expense.category or "Other Expenses")
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setEditText(expense.category or "Other Expenses")
        else:
            self.category_combo.setCurrentIndex(-1)
            self.category_combo.setEditText("")

        self.description_edit = QtWidgets.QPlainTextEdit()
        self.description_edit.setObjectName("NotesField")
        self.description_edit.setPlaceholderText("Description...")
        if expense and expense.description:
            self.description_edit.setPlainText(expense.description)
        self.description_edit.setMinimumHeight(self.description_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Date:"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("Amount"), 1, 0)
        form.addWidget(self.amount_edit, 1, 1)
        form.addWidget(QtWidgets.QLabel("Vendor"), 2, 0)
        form.addWidget(self.vendor_edit, 2, 1)
        form.addWidget(QtWidgets.QLabel("User (optional)"), 3, 0)
        form.addWidget(self.user_combo, 3, 1)
        form.addWidget(QtWidgets.QLabel("Category"), 4, 0)
        form.addWidget(self.category_combo, 4, 1)
        desc_label = QtWidgets.QLabel("Description")
        desc_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(desc_label, 5, 0)
        form.addWidget(self.description_edit, 5, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        self.clear_btn = QtWidgets.QPushButton("🧹 Clear")
        self.save_btn = QtWidgets.QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self.reject)
        self.clear_btn.clicked.connect(self._clear_form)
        self.save_btn.clicked.connect(self.accept)

        self.amount_edit.textChanged.connect(self._validate_inline)
        self.vendor_edit.textChanged.connect(self._validate_inline)

        self._validate_inline()

    def collect_data(self):
        vendor = self.vendor_edit.text().strip()
        if not vendor:
            return None, "Vendor is required"
        ok, amount = validate_currency(self.amount_edit.text(), allow_zero=False)
        if not ok:
            return None, amount
        user_id = self.user_combo.currentData() if self.user_combo.currentData() else None
        category = self.category_combo.currentText().strip() or "Other Expenses"
        return {
            "expense_date": self.date_edit.date().toPython(),
            "amount": Decimal(str(amount)),
            "vendor": vendor,
            "description": self.description_edit.toPlainText().strip() or None,
            "category": category,
            "user_id": user_id,
        }, None

    def _set_today(self):
        self.date_edit.setDate(QtCore.QDate.currentDate())

    def _clear_form(self):
        self.date_edit.setDate(QtCore.QDate.currentDate())
        self.time_edit.clear()
        self.amount_edit.clear()
        self.vendor_edit.clear()
        self.user_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(-1)
        self.category_combo.setEditText("")
        self.description_edit.clear()
        self._validate_inline()

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _set_invalid(self, widget, message):
        widget.setProperty("invalid", True)
        widget.setToolTip(message)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_valid(self, widget):
        widget.setProperty("invalid", False)
        widget.setToolTip("")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _validate_inline(self):
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
        else:
            valid, _result = validate_currency(amount_text, allow_zero=False)
            if not valid:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.amount_edit)

        vendor_text = self.vendor_edit.text().strip()
        if not vendor_text:
            self._set_invalid(self.vendor_edit, "Vendor is required.")
        else:
            self._set_valid(self.vendor_edit)


class ExpenseViewDialog(QtWidgets.QDialog):
    def __init__(self, expense: Expense, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.expense = expense
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Expense")
        self.resize(520, 320)

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)

        def add_row(label, value, row):
            layout.addWidget(QtWidgets.QLabel(label), row, 0)
            val = QtWidgets.QLabel(value)
            val.setWordWrap(True)
            layout.addWidget(val, row, 1, 1, 3)

        add_row("Date:", str(expense.expense_date), 0)
        add_row("Category:", expense.category or "Other Expenses", 1)
        add_row("Vendor:", expense.vendor or "", 2)
        add_row("User:", expense.user_name or "", 3)
        add_row("Amount:", f"${expense.amount:,.2f}", 4)
        add_row("Description:", expense.description or "", 5)

        button_layout = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(self._on_delete)
            button_layout.addWidget(delete_btn)
        button_layout.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("✏️ Edit")
            edit_btn.clicked.connect(self._on_edit)
            button_layout.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout, 6, 0, 1, 4)
