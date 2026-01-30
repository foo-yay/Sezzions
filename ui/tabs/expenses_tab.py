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
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from ui.input_parsers import parse_date_input, parse_time_input


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

        self.columns = ["Date", "Category", "Vendor", "User", "Amount", "Notes"]
        self.table = QtWidgets.QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_expense)
        
        # Enable custom context menu for spreadsheet UX
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Add spreadsheet stats bar
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)

        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.refresh_data)
        
        # Set up keyboard shortcuts for spreadsheet UX
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)

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
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(expense.category or ""))
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
        has_selection = self.table.selectionModel().hasSelection()
        self.view_btn.setVisible(len(selected) == 1)
        self.edit_btn.setVisible(len(selected) == 1)
        self.delete_btn.setVisible(bool(selected))
        
        # Update spreadsheet stats bar
        if has_selection:
            grid = SpreadsheetUXController.extract_selection_grid(self.table)
            stats = SpreadsheetUXController.compute_stats(grid)
            self.stats_bar.update_stats(stats)
        else:
            self.stats_bar.clear_stats()

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
    """Modern expense dialog with streamlined layout"""
    
    def __init__(self, users, expense: Expense = None, parent=None):
        super().__init__(parent)
        self.users = users
        self.expense = expense
        self.setWindowTitle("Edit Expense" if expense else "Add Expense")
        self.setMinimumWidth(700)
        self.setMinimumHeight(420)
        self.resize(700, 420)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Initialize widgets
        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)

        self.amount_edit = QtWidgets.QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")

        self.vendor_edit = QtWidgets.QLineEdit()
        self.vendor_edit.setPlaceholderText("Vendor name...")

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.lineEdit().setPlaceholderText("Choose...")
        self.category_combo.addItems(EXPENSE_CATEGORIES)
        self.category_combo.setCurrentIndex(-1)  # Start with no selection

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.lineEdit().setPlaceholderText("Choose...")
        self.user_combo.addItem("")
        for user in users:
            self.user_combo.addItem(user.name, user.id)

        self.description_edit = QtWidgets.QPlainTextEdit()
        self.description_edit.setPlaceholderText("Optional...")
        self.description_edit.setFixedHeight(80)
        self.description_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Build form
        form = QtWidgets.QVBoxLayout()
        form.setSpacing(12)

        # Date/Time section
        datetime_section = QtWidgets.QWidget()
        datetime_section.setObjectName("SectionBackground")
        datetime_layout = QtWidgets.QHBoxLayout(datetime_section)
        datetime_layout.setContentsMargins(12, 10, 12, 10)
        datetime_layout.setSpacing(12)
        
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(date_label)
        
        date_container = QtWidgets.QWidget()
        date_layout = QtWidgets.QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(4)
        self.date_edit.setFixedWidth(110)
        date_layout.addWidget(self.date_edit)
        date_layout.addWidget(self.calendar_btn)
        datetime_layout.addWidget(date_container)
        
        datetime_layout.addWidget(self.today_btn)
        datetime_layout.addSpacing(30)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(time_label)
        
        self.time_edit.setFixedWidth(90)
        datetime_layout.addWidget(self.time_edit)
        datetime_layout.addWidget(self.now_btn)
        datetime_layout.addStretch(1)
        
        form.addWidget(datetime_section)

        # Expense Details section with 2-column grid
        main_header = self._create_section_header("💵  Expense Details")
        form.addWidget(main_header)
        
        main_section = QtWidgets.QWidget()
        main_section.setObjectName("SectionBackground")
        main_grid = QtWidgets.QGridLayout(main_section)
        main_grid.setContentsMargins(12, 12, 12, 12)
        main_grid.setHorizontalSpacing(30)
        main_grid.setVerticalSpacing(10)
        
        # Left Column
        row = 0
        
        # Amount
        amount_label = QtWidgets.QLabel("Amount ($):")
        amount_label.setObjectName("FieldLabel")
        amount_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(amount_label, row, 0)
        self.amount_edit.setFixedWidth(140)
        main_grid.addWidget(self.amount_edit, row, 1)
        
        # Category (right column)
        category_label = QtWidgets.QLabel("Category:")
        category_label.setObjectName("FieldLabel")
        category_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(category_label, row, 2)
        self.category_combo.setMinimumWidth(180)
        main_grid.addWidget(self.category_combo, row, 3)
        
        row += 1
        
        # Vendor
        vendor_label = QtWidgets.QLabel("Vendor:")
        vendor_label.setObjectName("FieldLabel")
        vendor_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(vendor_label, row, 0)
        self.vendor_edit.setMinimumWidth(180)
        main_grid.addWidget(self.vendor_edit, row, 1)
        
        # User (right column)
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(user_label, row, 2)
        self.user_combo.setMinimumWidth(180)
        main_grid.addWidget(self.user_combo, row, 3)
        
        main_grid.setColumnStretch(1, 1)
        main_grid.setColumnStretch(3, 1)
        
        form.addWidget(main_section)

        # Collapsible Notes
        self.notes_collapsed = True
        self.notes_toggle = QtWidgets.QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        form.addWidget(self.notes_toggle)
        
        self.notes_section = QtWidgets.QWidget()
        self.notes_section.setObjectName("SectionBackground")
        self.notes_section.setVisible(False)
        notes_layout = QtWidgets.QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.addWidget(self.description_edit)
        form.addWidget(self.notes_section)

        layout.addLayout(form)
        
        # Add stretch to push buttons to bottom when dialog is resized
        layout.addStretch(1)

        # Action buttons (don't adjust per user request)
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
        self.date_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)

        # Set tab order: Date -> Time -> Amount -> Vendor -> Category -> User -> Notes -> Save
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.amount_edit)
        self.setTabOrder(self.amount_edit, self.vendor_edit)
        self.setTabOrder(self.vendor_edit, self.category_combo)
        self.setTabOrder(self.category_combo, self.user_combo)
        self.setTabOrder(self.user_combo, self.description_edit)
        self.setTabOrder(self.description_edit, self.save_btn)

        # Load data if editing
        if expense:
            self._load_expense()
        else:
            self._set_today()
            self._set_now()

        self._validate_inline()

    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header label"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label

    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(420)
            self.setMaximumHeight(420)
            self.resize(self.width(), 420)
        else:
            self.notes_toggle.setText("📝 Hide Notes")
            self.setMinimumHeight(500)
            self.setMaximumHeight(16777215)  # Qt max
            self.resize(self.width(), 500)

    def _pick_date(self):
        """Show calendar picker for date selection"""
        from PySide6.QtWidgets import QCalendarWidget
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        
        # Parse current date if any
        current_text = self.date_edit.text().strip()
        if current_text:
            parsed = parse_date_input(current_text)
            if parsed:
                calendar.setSelectedDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
        else:
            calendar.setSelectedDate(QtCore.QDate.currentDate())
        
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            selected = calendar.selectedDate()
            self.date_edit.setText(selected.toString("MM/dd/yy"))

    def _load_expense(self):
        """Load expense data into form"""
        if not self.expense:
            return
        
        # Date
        if self.expense.expense_date:
            try:
                d = datetime.strptime(str(self.expense.expense_date), "%Y-%m-%d")
                self.date_edit.setText(d.strftime("%m/%d/%y"))
            except:
                pass
        
        # Time
        if self.expense.expense_time:
            self.time_edit.setText(self.expense.expense_time[:5] if len(self.expense.expense_time) >= 5 else self.expense.expense_time)
        
        # Amount
        if self.expense.amount:
            self.amount_edit.setText(str(self.expense.amount))
        
        # Vendor
        if self.expense.vendor:
            self.vendor_edit.setText(self.expense.vendor)
        
        # Category
        if self.expense.category:
            idx = self.category_combo.findText(self.expense.category)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setEditText(self.expense.category)
        
        # User
        if self.expense.user_id:
            idx = self.user_combo.findData(self.expense.user_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        
        # Notes
        if self.expense.description:
            self.description_edit.setPlainText(self.expense.description)
            # Expand notes if there's content - use toggle to ensure proper sizing
            self._toggle_notes()

    def collect_data(self):
        vendor = self.vendor_edit.text().strip()
        if not vendor:
            return None, "Vendor is required"
        
        # Parse date
        date_text = self.date_edit.text().strip()
        parsed_date = parse_date_input(date_text)
        if not parsed_date:
            return None, "Invalid date format"
        
        # Parse time
        time_text = self.time_edit.text().strip()
        expense_time = parse_time_input(time_text) if time_text else None
        
        ok, amount = validate_currency(self.amount_edit.text(), allow_zero=False)
        if not ok:
            return None, amount
        
        # Get user_id by matching text (not currentData which can be stale)
        user_text = self.user_combo.currentText().strip()
        user_id = None
        if user_text:
            # Find the matching user in the combo
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i) == user_text:
                    user_id = self.user_combo.itemData(i)
                    break
        
        category_text = self.category_combo.currentText().strip()
        category = category_text if category_text else None
        
        return {
            "expense_date": parsed_date,
            "expense_time": expense_time,
            "amount": Decimal(str(amount)),
            "vendor": vendor,
            "description": self.description_edit.toPlainText().strip() or None,
            "category": category,
            "user_id": user_id,
        }, None

    def _set_today(self):
        self.date_edit.setText(datetime.now().strftime("%m/%d/%y"))

    def _clear_form(self):
        self._set_today()
        self._set_now()
        self.amount_edit.clear()
        self.vendor_edit.clear()
        self.user_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(-1)
        self.category_combo.setEditText("")
        self.description_edit.clear()
        self.notes_collapsed = True
        self.notes_section.setVisible(False)
        self.notes_toggle.setText("📝 Add Notes...")
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

    def _validate_inline(self) -> bool:
        """Validate all fields and return True if all valid"""
        valid = True
        
        # Validate date
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
            valid = False
        else:
            parsed = parse_date_input(date_text)
            if not parsed:
                self._set_invalid(self.date_edit, "Invalid date format (use MM/DD/YY).")
                valid = False
            else:
                self._set_valid(self.date_edit)
        
        # Validate amount
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
            valid = False
        else:
            valid_amt, _result = validate_currency(amount_text, allow_zero=False)
            if not valid_amt:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
                valid = False
            else:
                self._set_valid(self.amount_edit)

        # Validate vendor
        vendor_text = self.vendor_edit.text().strip()
        if not vendor_text:
            self._set_invalid(self.vendor_edit, "Vendor is required.")
            valid = False
        else:
            self._set_valid(self.vendor_edit)
        
        # Validate user (optional, but must be valid if entered)
        user_text = self.user_combo.currentText().strip()
        if user_text:  # Only validate if text is entered
            # Check if it's a valid user
            valid_user = False
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i) == user_text:
                    valid_user = True
                    break
            if not valid_user:
                self._set_invalid(self.user_combo, "User not found. Choose from list or leave blank.")
                valid = False
            else:
                self._set_valid(self.user_combo)
        else:
            self._set_valid(self.user_combo)
        
        # Enable/disable save button based on validation
        self.save_btn.setEnabled(valid)
        return valid


class ExpenseViewDialog(QtWidgets.QDialog):
    """Modern view-only expense dialog with sectioned layout"""
    def __init__(self, expense: Expense, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.expense = expense
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Expense")
        self.setMinimumWidth(700)
        self.setMinimumHeight(350)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # ========== EXPENSE DETAILS SECTION ==========
        details_section, details_layout = self._create_section("💳 Expense Details")
        
        # Two-column grid layout
        columns_widget = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 4, 0, 0)
        columns_layout.setSpacing(12)
        
        # Left column
        left_grid = QtWidgets.QGridLayout()
        left_grid.setHorizontalSpacing(12)
        left_grid.setVerticalSpacing(6)
        
        # Date & Time
        date_label = QtWidgets.QLabel("Date:")
        date_label.setStyleSheet("color: palette(mid);")
        left_grid.addWidget(date_label, 0, 0)
        date_time_str = self._format_date(expense.expense_date)
        if expense.expense_time:
            time_display = expense.expense_time[:5] if len(expense.expense_time) >= 5 else expense.expense_time
            date_time_str += f" {time_display}"
        left_grid.addWidget(self._make_selectable_label(date_time_str), 0, 1)
        
        # Vendor
        vendor_label = QtWidgets.QLabel("Vendor:")
        vendor_label.setStyleSheet("color: palette(mid);")
        left_grid.addWidget(vendor_label, 1, 0)
        left_grid.addWidget(self._make_selectable_label(expense.vendor or "—"), 1, 1)
        
        # Amount
        amount_label = QtWidgets.QLabel("Amount:")
        amount_label.setStyleSheet("color: palette(mid);")
        left_grid.addWidget(amount_label, 2, 0)
        left_grid.addWidget(self._make_selectable_label(f"${expense.amount:,.2f}"), 2, 1)
        
        left_grid.setColumnStretch(1, 1)
        
        # Right column
        right_grid = QtWidgets.QGridLayout()
        right_grid.setHorizontalSpacing(12)
        right_grid.setVerticalSpacing(6)
        
        # User
        user_label = QtWidgets.QLabel("User:")
        user_label.setStyleSheet("color: palette(mid);")
        right_grid.addWidget(user_label, 0, 0)
        right_grid.addWidget(self._make_selectable_label(expense.user_name or "—"), 0, 1)
        
        # Category
        category_label = QtWidgets.QLabel("Category:")
        category_label.setStyleSheet("color: palette(mid);")
        right_grid.addWidget(category_label, 1, 0)
        right_grid.addWidget(self._make_selectable_label(expense.category or "—"), 1, 1)
        
        right_grid.setColumnStretch(1, 1)
        
        columns_layout.addLayout(left_grid, 1)
        columns_layout.addLayout(right_grid, 1)
        
        details_layout.addWidget(columns_widget)
        layout.addWidget(details_section)

        # ========== NOTES SECTION ==========
        notes_section, notes_layout = self._create_section("📝 Notes")
        notes_value = expense.description or ""
        
        if notes_value:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(notes_value)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setStyleSheet("color: palette(mid); font-style: italic;")
            notes_layout.addWidget(notes_empty)
        
        layout.addWidget(notes_section)
        layout.addStretch(1)

        # ========== BUTTONS ==========
        button_layout = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(self._on_delete)
            button_layout.addWidget(delete_btn)
        button_layout.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("✏️ Edit")
            edit_btn.clicked.connect(self._handle_edit)
            button_layout.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _create_section(self, title_text):
        """Create a section container with header"""
        section_widget = QtWidgets.QWidget()
        section_widget.setObjectName("SectionBackground")
        section_layout = QtWidgets.QVBoxLayout(section_widget)
        section_layout.setContentsMargins(10, 8, 10, 8)
        section_layout.setSpacing(6)
        
        # Section header
        section_header = QtWidgets.QLabel(title_text)
        section_header.setObjectName("SectionHeader")
        section_layout.addWidget(section_header)
        
        return section_widget, section_layout

    def _make_selectable_label(self, text):
        """Create a selectable QLabel"""
        label = QtWidgets.QLabel(text)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        label.setCursor(QtCore.Qt.IBeamCursor)
        return label

    def _format_date(self, value):
        """Format date to MM/DD/YY"""
        if not value:
            return "—"
        if isinstance(value, date):
            return value.strftime("%m/%d/%y")
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return str(value)

    def _handle_edit(self):
        """Close dialog before triggering edit callback"""
        self.accept()
        if self._on_edit:
            self._on_edit()
    
    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        SpreadsheetUXController.copy_to_clipboard(self.table)
    
    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        SpreadsheetUXController.copy_to_clipboard(self.table, include_headers=True)
    
    def _show_context_menu(self, position):
        """Show context menu for table"""
        if not self.table.selectionModel().hasSelection():
            return
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))
    
    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        SpreadsheetUXController.copy_to_clipboard(self.table)
    
    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        SpreadsheetUXController.copy_to_clipboard(self.table, include_headers=True)
    
    def _show_context_menu(self, position):
        """Show context menu for table"""
        if not self.table.selectionModel().hasSelection():
            return
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))
