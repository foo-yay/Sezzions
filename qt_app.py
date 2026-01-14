#!/usr/bin/env python3
"""
qt_app.py - PySide6/Qt UI for Session
Run: python3 qt_app.py
"""
import sys
import os
import re
import csv
from datetime import date, datetime, timedelta
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis

from database import Database
from business_logic import FIFOCalculator, SessionManager
from reporting import ReportingService, ReportFilters


def format_currency(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "$0.00"


def format_date_time(date_str, time_str):
    if not date_str:
        return ""
    try:
        year, month, day = date_str.split("-")
        display_date = f"{month}/{day}/{year[2:]}"
    except Exception:
        display_date = date_str
    if time_str:
        return f"{display_date} {time_str[:5]}"
    return display_date


def parse_date_input(value):
    value = value.strip()
    if not value:
        return date.today()
    if "/" in value:
        parts = value.split("/")
        if len(parts) == 2:
            value = f"{parts[0]}/{parts[1]}/{date.today().year}"
    if "-" in value:
        parts = value.split("-")
        if len(parts) == 2:
            value = f"{date.today().year}-{parts[0]}-{parts[1]}"
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def parse_time_input(value):
    value = value.strip()
    if not value:
        return datetime.now().strftime("%H:%M:%S")
    formats = ["%H:%M:%S", "%H:%M", "%I:%M%p", "%I:%M %p"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt).time()
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Invalid time: {value}")


TIME_24H_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d(?:\:[0-5]\d)?$")


def is_valid_time_24h(value, allow_blank=True):
    value = value.strip()
    if not value:
        return allow_blank
    return bool(TIME_24H_RE.match(value))


def validate_currency(value_str, allow_zero=True):
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


def header_resize_section_index(header, pos, margin=4):
    index = header.logicalIndexAt(pos)
    if index < 0:
        return None
    left = header.sectionPosition(index)
    right = left + header.sectionSize(index)
    x = pos.x()
    if abs(x - right) <= margin:
        return index
    if abs(x - left) <= margin and index > 0:
        return index - 1
    return None


def header_menu_position(header, col_index, menu):
    try:
        pos_x = header.sectionViewportPosition(col_index)
    except AttributeError:
        pos_x = header.sectionPosition(col_index) - header.offset()
    anchor = header.viewport().mapToGlobal(QtCore.QPoint(pos_x, header.height()))
    screen = QtGui.QGuiApplication.screenAt(anchor) or QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return anchor
    available = screen.availableGeometry()
    menu_size = menu.sizeHint()
    max_x = available.right() - menu_size.width() + 1
    max_y = available.bottom() - menu_size.height() + 1
    pos_x = min(max(anchor.x(), available.left()), max_x) if max_x >= available.left() else available.left()
    pos_y = min(max(anchor.y(), available.top()), max_y) if max_y >= available.top() else available.top()
    return QtCore.QPoint(pos_x, pos_y)


class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, spacing=6, align=QtCore.Qt.AlignLeft):
        super().__init__(parent)
        self._items = []
        self._align = align
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        line_width = 0
        line_items = []
        available_width = rect.width()
        spacing = self.spacing()

        def flush_line():
            nonlocal x, y, line_height, line_width, line_items
            if not line_items:
                return
            extra = available_width - line_width
            if self._align == QtCore.Qt.AlignCenter and extra > 0:
                x = rect.x() + extra // 2
            elif self._align == QtCore.Qt.AlignRight and extra > 0:
                x = rect.x() + extra
            else:
                x = rect.x()
            for item in line_items:
                if not test_only:
                    item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
                x += item.sizeHint().width() + spacing
            y += line_height + spacing
            line_height = 0
            line_width = 0
            line_items = []

        for item in self._items:
            item_width = item.sizeHint().width()
            if line_items and line_width + spacing + item_width > available_width:
                flush_line()
            if line_items:
                line_width += spacing
            line_items.append(item)
            line_width += item_width
            line_height = max(line_height, item.sizeHint().height())

        if line_items:
            flush_line()

        return max(0, y - rect.y() - spacing)


class ColumnFilterDialog(QtWidgets.QDialog):
    def __init__(self, values, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter")
        self.resize(280, 420)
        self._values = list(values)
        self._selected = set(selected or [])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        search_layout = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search values...")
        self.search_edit.textChanged.connect(self._apply_search)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        btn_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select All")
        clear_all = QtWidgets.QPushButton("Clear All")
        select_all.clicked.connect(self._select_all)
        clear_all.clicked.connect(self._clear_all)
        btn_row.addWidget(select_all)
        btn_row.addWidget(clear_all)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self.list_widget, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        ok_btn = QtWidgets.QPushButton("OK")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        footer.addWidget(ok_btn)
        layout.addLayout(footer)

        self._populate()

    def _populate(self):
        self.list_widget.clear()
        for value in self._values:
            item = QtWidgets.QListWidgetItem(str(value))
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if value in self._selected or not self._selected else QtCore.Qt.Unchecked)
            self.list_widget.addItem(item)

    def _apply_search(self):
        term = self.search_edit.text().strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            visible = term in item.text().lower()
            item.setHidden(not visible)

    def _select_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(QtCore.Qt.Checked)

    def _clear_all(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(QtCore.Qt.Unchecked)

    def selected_values(self):
        selected = set()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                selected.add(item.text())
        if len(selected) == len(self._values):
            return set()
        return selected


class DateTimeFilterDialog(QtWidgets.QDialog):
    def __init__(self, values, selected, parent=None, show_time=True):
        super().__init__(parent)
        self.setWindowTitle("Filter")
        self.resize(320, 440)
        self._values = list(values)
        self._selected = set(selected or [])
        self._show_time = show_time
        self._updating = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Select All")
        clear_all = QtWidgets.QPushButton("Clear All")
        select_all.clicked.connect(self._select_all)
        clear_all.clicked.connect(self._clear_all)
        btn_row.addWidget(select_all)
        btn_row.addWidget(clear_all)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        footer = QtWidgets.QHBoxLayout()
        footer.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("OK")
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)
        footer.addWidget(cancel_btn)
        footer.addWidget(ok_btn)
        layout.addLayout(footer)

        self._populate()

    def _populate(self):
        self.tree.clear()
        grouped = {}
        for value in self._values:
            date_part = value
            time_part = ""
            if " " in value:
                date_part, time_part = value.split(" ", 1)
            try:
                parsed_date = parse_date_input(date_part)
                year = parsed_date.strftime("%Y")
                month_num = parsed_date.strftime("%m")
                month_name = parsed_date.strftime("%B")
                day = parsed_date.strftime("%d")
            except ValueError:
                year = "????"
                month_num = "??"
                month_name = "Unknown"
                day = "??"
            time_label = time_part.strip() or "00:00"
            if self._show_time:
                grouped.setdefault(year, {}).setdefault(month_num, {}).setdefault(day, {}).setdefault(
                    time_label, []
                ).append(value)
            else:
                grouped.setdefault(year, {}).setdefault(month_num, {}).setdefault(day, []).append(value)

        for year in sorted(grouped.keys()):
            year_item = QtWidgets.QTreeWidgetItem([year])
            year_item.setFlags(year_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.tree.addTopLevelItem(year_item)
            for month_num in sorted(grouped[year].keys()):
                month_name = "Unknown"
                if month_num.isdigit():
                    try:
                        month_name = datetime.strptime(month_num, "%m").strftime("%B")
                    except ValueError:
                        month_name = month_num
                month_item = QtWidgets.QTreeWidgetItem([month_name])
                month_item.setFlags(month_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                year_item.addChild(month_item)
                for day in sorted(grouped[year][month_num].keys()):
                    day_item = QtWidgets.QTreeWidgetItem([day])
                    day_item.setFlags(day_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                    month_item.addChild(day_item)
                    if self._show_time:
                        for time_label in sorted(grouped[year][month_num][day].keys()):
                            leaf_values = grouped[year][month_num][day][time_label]
                            leaf_item = QtWidgets.QTreeWidgetItem([time_label])
                            leaf_item.setFlags(leaf_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                            leaf_item.setData(0, QtCore.Qt.UserRole, leaf_values)
                            day_item.addChild(leaf_item)
                    else:
                        leaf_values = grouped[year][month_num][day]
                        day_item.setData(0, QtCore.Qt.UserRole, leaf_values)

        self._update_check_states()

    def _update_check_states(self):
        self._updating = True
        all_selected = not self._selected
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._set_item_checked_recursive(root.child(i), all_selected)
        if self._selected:
            for leaf in self._leaf_items():
                leaf_values = leaf.data(0, QtCore.Qt.UserRole) or []
                checked = any(value in self._selected for value in leaf_values)
                leaf.setCheckState(0, QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            self._sync_parent_states()
        self._updating = False

    def _leaf_items(self):
        items = []
        root = self.tree.invisibleRootItem()
        stack = [root.child(i) for i in range(root.childCount())]
        while stack:
            item = stack.pop()
            if item.childCount() == 0:
                items.append(item)
            else:
                for idx in range(item.childCount()):
                    stack.append(item.child(idx))
        return items

    def _set_item_checked_recursive(self, item, checked):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        item.setCheckState(0, state)
        for i in range(item.childCount()):
            self._set_item_checked_recursive(item.child(i), checked)

    def _sync_parent_states(self):
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._update_parent_state(root.child(i))

    def _update_parent_state(self, item):
        for i in range(item.childCount()):
            self._update_parent_state(item.child(i))
        if item.childCount() == 0:
            return
        states = {item.child(i).checkState(0) for i in range(item.childCount())}
        if len(states) == 1:
            item.setCheckState(0, states.pop())
        else:
            item.setCheckState(0, QtCore.Qt.PartiallyChecked)

    def _on_item_changed(self, item, _column):
        if self._updating:
            return
        self._updating = True
        if item.checkState(0) != QtCore.Qt.PartiallyChecked:
            self._set_item_checked_recursive(item, item.checkState(0) == QtCore.Qt.Checked)
        parent = item.parent()
        while parent:
            self._update_parent_state(parent)
            parent = parent.parent()
        self._updating = False

    def _select_all(self):
        self._updating = True
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._set_item_checked_recursive(root.child(i), True)
        self._updating = False

    def _clear_all(self):
        self._updating = True
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._set_item_checked_recursive(root.child(i), False)
        self._updating = False

    def selected_values(self):
        selected = set()
        for leaf in self._leaf_items():
            if leaf.checkState(0) == QtCore.Qt.Checked:
                for value in leaf.data(0, QtCore.Qt.UserRole) or []:
                    selected.add(value)
        if len(selected) == len(self._values):
            return set()
        return selected


class ComboCompleterFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
            key = event.key()
            if key in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                return self._handle_commit(obj, key, event.type())
        return False

    def _handle_commit(self, obj, key, event_type):
        focus_widget = QtWidgets.QApplication.focusWidget()
        combo = None
        if isinstance(focus_widget, QtWidgets.QLineEdit):
            combo = self._combo_for_line_edit(focus_widget)
        elif isinstance(focus_widget, QtWidgets.QComboBox):
            combo = focus_widget if focus_widget.isEditable() else None
        if combo is not None and combo.isEditable():
            line_edit = combo.lineEdit()
            text = line_edit.text() if line_edit is not None else combo.currentText()
            committed = self._commit_from_combo(combo, text)
            if committed:
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    return True
                if key == QtCore.Qt.Key_Tab:
                    return False
        return False

    def _combo_for_line_edit(self, widget):
        if not isinstance(widget, QtWidgets.QLineEdit):
            return None
        parent = widget.parent()
        while parent is not None:
            if isinstance(parent, QtWidgets.QComboBox) and parent.lineEdit() is widget:
                return parent
            parent = parent.parent()
        return None

    def _commit_from_combo(self, combo, text):
        text = (text or "").strip()
        if not text:
            return False
        model = combo.model()
        column = combo.modelColumn()
        text_lower = text.lower()
        for row in range(model.rowCount()):
            idx = model.index(row, column)
            data = model.data(idx)
            if data is None:
                continue
            data_text = str(data)
            if data_text.lower().startswith(text_lower):
                combo.setCurrentText(data_text)
                completer = combo.completer()
                if completer is not None and completer.popup() is not None:
                    completer.popup().hide()
                return True
        return False

    def _wire_line_edit(self, _line_edit):
        return


class PurchaseDialog(QtWidgets.QDialog):
    def __init__(self, db, user_names, site_names, card_names, purchase=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.purchase = purchase
        self.setWindowTitle("Edit Purchase" if purchase else "Add Purchase")
        self.resize(600, 520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnMinimumWidth(1, 300)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QtWidgets.QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(user_names)
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.addItems(site_names)
        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.setEditable(True)
        self.card_combo.lineEdit().setPlaceholderText("Select a user first")
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}

        self.amount_edit = QtWidgets.QLineEdit()
        self.sc_edit = QtWidgets.QLineEdit()
        self.start_sc_edit = QtWidgets.QLineEdit()

        # Cashback display (read-only label + editable field)
        self.cashback_rate_label = QtWidgets.QLabel("—")
        self.cashback_rate_label.setObjectName("HelperText")
        self.cashback_edit = QtWidgets.QLineEdit()
        self.cashback_edit.setPlaceholderText("Auto-calculated")

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Date"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("Time"), 1, 0)
        form.addLayout(time_row, 1, 1)
        form.addWidget(QtWidgets.QLabel("User"), 2, 0)
        form.addWidget(self.user_combo, 2, 1)
        form.addWidget(QtWidgets.QLabel("Site"), 3, 0)
        form.addWidget(self.site_combo, 3, 1)

        # Card row with cashback rate display
        card_label = QtWidgets.QLabel("Card")
        form.addWidget(card_label, 4, 0)
        card_container = QtWidgets.QVBoxLayout()
        card_container.setSpacing(4)
        card_container.addWidget(self.card_combo)
        card_container.addWidget(self.cashback_rate_label)
        form.addLayout(card_container, 4, 1)

        form.addWidget(QtWidgets.QLabel("Amount"), 5, 0)
        form.addWidget(self.amount_edit, 5, 1)
        form.addWidget(QtWidgets.QLabel("SC Received"), 6, 0)
        form.addWidget(self.sc_edit, 6, 1)
        form.addWidget(QtWidgets.QLabel("Starting SC"), 7, 0)
        form.addWidget(self.start_sc_edit, 7, 1)

        # Cashback earned row (editable override)
        cashback_label = QtWidgets.QLabel("Cashback Earned")
        form.addWidget(cashback_label, 8, 0)
        form.addWidget(self.cashback_edit, 8, 1)

        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(notes_label, 9, 0)
        form.addWidget(self.notes_edit, 9, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)

        self.user_combo.currentTextChanged.connect(self._on_user_change)
        self.card_combo.currentTextChanged.connect(self._on_card_change)
        self.amount_edit.textChanged.connect(self._on_amount_change)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.card_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.sc_edit.textChanged.connect(self._validate_inline)
        self.start_sc_edit.textChanged.connect(self._validate_inline)

        if purchase:
            self._load_purchase()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()

    def _update_completers(self):
        for combo in (self.user_combo, self.site_combo, self.card_combo):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _on_user_change(self, value):
        user_name = value.strip()
        
        # Check if user is valid
        user_valid = user_name and user_name.lower() in self._user_lookup
        
        if not user_valid:
            self.card_combo.blockSignals(True)
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            # Restore placeholder when user is cleared or invalid
            self.card_combo.lineEdit().setPlaceholderText("Select a user first")
            self.card_combo.blockSignals(False)
            # Clear cashback fields
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()
            self._card_name_map = {}
            self._validate_inline()
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            self.card_combo.blockSignals(True)
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            # Restore placeholder when user not found
            self.card_combo.lineEdit().setPlaceholderText("Select a user first")
            self.card_combo.blockSignals(False)
            # Clear cashback fields
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()
            self._card_name_map = {}
            self._validate_inline()
            return
        
        user_id = user_row["id"]
        c.execute("SELECT name, last_four FROM cards WHERE user_id = ? AND active = 1 ORDER BY name", (user_id,))
        card_rows = c.fetchall()
        conn.close()
        
        # Build name map and formatted display list
        self._card_name_map = {}
        cards = []
        for row in card_rows:
            card_name = row["name"]
            last_four = row["last_four"]
            if last_four:
                display_name = f"{card_name} – x{last_four}"
            else:
                display_name = card_name
            cards.append(display_name)
            self._card_name_map[display_name.lower()] = card_name
        
        preserve = getattr(self, "_preserve_card_selection", False)
        current = self.card_combo.currentText().strip()
        self.card_combo.blockSignals(True)
        self.card_combo.clear()
        self.card_combo.addItems(cards)
        # Remove placeholder since valid user is selected
        self.card_combo.lineEdit().setPlaceholderText("")
        
        if preserve and current:
            # Find display name that matches original card name
            found = False
            for display_name, mapped_name in self._card_name_map.items():
                if mapped_name == current:
                    # Find case-sensitive match in combo
                    for i in range(self.card_combo.count()):
                        if self.card_combo.itemText(i).lower() == display_name:
                            self.card_combo.setCurrentIndex(i)
                            found = True
                            break
                    break
            if not found:
                self.card_combo.setCurrentIndex(-1)
                self.card_combo.setEditText("")
        else:
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
        self.card_combo.blockSignals(False)
        # Manually trigger card change to update cashback
        self._on_card_change(self.card_combo.currentText())
        self._update_completers()
        self._validate_inline()

    def _on_card_change(self, value):
        """Update cashback rate display and recalculate cashback when card changes"""
        card_name = value.strip()
        if not card_name:
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()
            return

        # Map display name back to actual card name if needed
        if hasattr(self, '_card_name_map') and card_name.lower() in self._card_name_map:
            actual_card_name = self._card_name_map[card_name.lower()]
        else:
            actual_card_name = card_name

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (actual_card_name,))
        card_row = c.fetchone()
        conn.close()

        if card_row:
            cashback_rate = float(card_row["cashback_rate"] or 0.0)
            self.cashback_rate_label.setText(f"Cashback: {cashback_rate:.2f}%")
            self._recalculate_cashback(cashback_rate)
        else:
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()

    def _on_amount_change(self, value):
        """Recalculate cashback when amount changes"""
        card_name = self.card_combo.currentText().strip()
        if not card_name:
            return

        # Map display name back to actual card name if needed
        if hasattr(self, '_card_name_map') and card_name.lower() in self._card_name_map:
            actual_card_name = self._card_name_map[card_name.lower()]
        else:
            actual_card_name = card_name

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (actual_card_name,))
        card_row = c.fetchone()
        conn.close()

        if card_row:
            cashback_rate = float(card_row["cashback_rate"] or 0.0)
            self._recalculate_cashback(cashback_rate)

    def _recalculate_cashback(self, cashback_rate):
        """Calculate and update cashback earned field"""
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self.cashback_edit.clear()
            return

        try:
            amount = float(amount_text)
            cashback = round(amount * (cashback_rate / 100.0), 2)
            self.cashback_edit.setText(f"{cashback:.2f}")
        except ValueError:
            self.cashback_edit.clear()

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
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
        else:
            try:
                parsed = parse_date_input(date_text)
                if parsed > date.today():
                    self._set_invalid(self.date_edit, "Date cannot be in the future.")
                else:
                    self._set_valid(self.date_edit)
            except ValueError:
                self._set_invalid(self.date_edit, "Enter a valid date.")

        time_text = self.time_edit.text().strip()
        if not is_valid_time_24h(time_text, allow_blank=True):
            self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
        else:
            self._set_valid(self.site_combo)

        card_text = self.card_combo.currentText().strip()
        # If card has text, validate it
        if card_text:
            # Check if user is selected first (need _card_name_map)
            if not hasattr(self, '_card_name_map') or not self._card_name_map:
                self._set_invalid(self.card_combo, "Select a User first.")
            elif card_text.lower() not in self._card_name_map:
                self._set_invalid(self.card_combo, "Select a valid Card for the chosen User.")
            else:
                self._set_valid(self.card_combo)
        else:
            # Card is required
            self._set_invalid(self.card_combo, "Card is required.")

        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
        else:
            valid, _result = validate_currency(amount_text)
            if not valid:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.amount_edit)

        sc_text = self.sc_edit.text().strip()
        if not sc_text:
            self._set_invalid(self.sc_edit, "SC Received is required.")
        else:
            valid, _result = validate_currency(sc_text)
            if not valid:
                self._set_invalid(self.sc_edit, "Enter a valid SC amount (max 2 decimals).")
            else:
                self._set_valid(self.sc_edit)

        start_sc_text = self.start_sc_edit.text().strip()
        if not start_sc_text:
            self._set_invalid(self.start_sc_edit, "Starting SC is required.")
        else:
            valid, _result = validate_currency(start_sc_text)
            if not valid:
                self._set_invalid(self.start_sc_edit, "Enter a valid Starting SC (max 2 decimals).")
            else:
                self._set_valid(self.start_sc_edit)

    def _load_purchase(self):
        self.date_edit.setText(self._format_date_for_input(self.purchase["purchase_date"]))
        self.time_edit.setText(self._format_time_for_input(self.purchase["purchase_time"]))

        # Load user first (this will populate the card dropdown)
        self.user_combo.setCurrentText(self.purchase["user_name"])
        # Trigger user change to filter cards and populate _card_name_map
        self._on_user_change(self.purchase["user_name"])

        self.site_combo.setCurrentText(self.purchase["site_name"])
        
        # Find the formatted display name for the card
        card_name = self.purchase["card_name"]
        if hasattr(self, '_card_name_map'):
            # Find the display name that maps to this card name
            display_name = None
            for disp, actual in self._card_name_map.items():
                if actual == card_name:
                    # Find the actual case-sensitive display text in combo
                    for i in range(self.card_combo.count()):
                        if self.card_combo.itemText(i).lower() == disp:
                            display_name = self.card_combo.itemText(i)
                            break
                    break
            if display_name:
                self.card_combo.setCurrentText(display_name)
            else:
                self.card_combo.setCurrentText(card_name)
        else:
            self.card_combo.setCurrentText(card_name)
        
        self.amount_edit.setText(str(self.purchase["amount"]))
        self.sc_edit.setText(str(self.purchase["sc_received"]))
        self.start_sc_edit.setText(str(self.purchase["starting_sc_balance"]))
        # Format cashback to 2 decimal places
        self.cashback_edit.setText(f"{float(self.purchase['cashback_earned'] or 0.0):.2f}")
        self.notes_edit.setPlainText(self.purchase["notes"] or "")

    def _format_date_for_input(self, date_str):
        if not date_str:
            return ""
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return date_str

    def _format_time_for_input(self, time_str):
        if not time_str:
            return ""
        return time_str[:5]

    def _clear_form(self):
        self.date_edit.clear()
        self.time_edit.clear()
        for combo in (self.user_combo, self.site_combo, self.card_combo):
            combo.setCurrentIndex(-1)
            combo.setEditText("")
        # Restore card placeholder since user will be cleared
        self.card_combo.lineEdit().setPlaceholderText("Select a user first")
        self.amount_edit.clear()
        self.sc_edit.clear()
        self.start_sc_edit.clear()
        self.cashback_edit.clear()
        self.cashback_rate_label.setText("—")
        self.notes_edit.clear()
        self._set_today()
        self._validate_inline()

    def collect_data(self):
        user_name = self.user_combo.currentText().strip()
        site_name = self.site_combo.currentText().strip()
        card_name = self.card_combo.currentText().strip()

        if not all([user_name, site_name, card_name]):
            return None, "Please select User, Site, and Card."

        date_str = self.date_edit.text().strip()
        if not date_str:
            return None, "Please enter a purchase date."
        try:
            pdate = parse_date_input(date_str)
        except ValueError:
            return None, "Please enter a valid date."
        if pdate > date.today():
            return None, "Purchase date cannot be in the future."

        time_str = self.time_edit.text().strip()
        if time_str and not is_valid_time_24h(time_str, allow_blank=False):
            return None, "Please enter a valid time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            ptime = parse_time_input(time_str)
        except ValueError:
            return None, "Please enter a valid time (HH:MM or HH:MM:SS)."

        amount_str = self.amount_edit.text().strip()
        if not amount_str:
            return None, "Please enter a purchase amount."
        valid, result = validate_currency(amount_str)
        if not valid:
            return None, result
        amount = result

        sc_str = self.sc_edit.text().strip()
        if not sc_str:
            return None, "Please enter SC received."
        valid, result = validate_currency(sc_str)
        if not valid:
            return None, result
        sc_received = result

        start_sc_str = self.start_sc_edit.text().strip()
        if not start_sc_str:
            return None, "Please enter Starting SC."
        valid, result = validate_currency(start_sc_str)
        if not valid:
            return None, result
        start_sc = result

        notes = self.notes_edit.toPlainText().strip()

        # Get cashback earned (use entered value or calculate if empty)
        cashback_str = self.cashback_edit.text().strip()
        if cashback_str:
            try:
                cashback_earned = round(float(cashback_str), 2)
            except ValueError:
                cashback_earned = 0.0
        else:
            # Auto-calculate if not provided
            conn = self.db.get_connection()
            c = conn.cursor()
            # Map display name back to actual card name if needed
            if hasattr(self, '_card_name_map') and card_name.lower() in self._card_name_map:
                actual_card_name = self._card_name_map[card_name.lower()]
            else:
                actual_card_name = card_name
            c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (actual_card_name,))
            card_row = c.fetchone()
            conn.close()
            if card_row:
                cashback_rate = float(card_row["cashback_rate"] or 0.0)
                cashback_earned = round(amount * (cashback_rate / 100.0), 2)
            else:
                cashback_earned = 0.0

        return {
            "user_name": user_name,
            "site_name": site_name,
            "card_name": card_name,
            "purchase_date": pdate.strftime("%Y-%m-%d"),
            "purchase_time": ptime,
            "amount": amount,
            "sc_received": sc_received,
            "starting_sc_balance": start_sc,
            "cashback_earned": cashback_earned,
            "notes": notes,
        }, None


class PurchaseViewDialog(QtWidgets.QDialog):
    def __init__(self, purchase, parent=None, on_edit=None, on_delete=None, on_open_session=None, on_open_redemption=None):
        super().__init__(parent)
        self.purchase = purchase
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.on_open_session = on_open_session
        self.on_open_redemption = on_open_redemption
        self.setWindowTitle("View Purchase")
        self.resize(700, 650)

        # Fetch card's last_four if available
        from database import Database
        from business_logic import FIFOCalculator, SessionManager
        self.db = Database()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT last_four FROM cards WHERE id = ?", (purchase["card_id"],))
        card_row = c.fetchone()
        conn.close()
        
        card_display = purchase["card_name"] or "—"
        if card_row and card_row["last_four"]:
            card_display = f"{purchase['card_name']} – x{card_row['last_four']}"

        # Fetch linked sessions and redemption allocations
        fifo = FIFOCalculator(self.db)
        self.session_manager = SessionManager(self.db, fifo)
        self.linked_sessions = self.session_manager.get_links_for_purchase(purchase["id"])
        self.redemption_allocations = self._load_redemption_allocations()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Create tab widget
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_details_tab(card_display), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _format_date(self, value):
        """Helper to format date strings to MM/DD/YY"""
        if not value:
            return "—"
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return value

    def _create_details_tab(self, card_display):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnMinimumWidth(1, 300)

        def add_row(label_text, value, row, wrap=False):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label.setWordWrap(wrap)
            form.addWidget(label, row, 0)
            form.addWidget(value_label, row, 1)
            return row + 1

        def format_date(value):
            if not value:
                return "—"
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return value

        def format_time(value):
            return value[:5] if value else "—"

        row = 0
        row = add_row("Date", format_date(self.purchase["purchase_date"]), row)
        row = add_row("Time", format_time(self.purchase["purchase_time"]), row)
        row = add_row("User", self.purchase["user_name"] or "—", row)
        row = add_row("Site", self.purchase["site_name"] or "—", row)
        row = add_row("Card", card_display, row)
        row = add_row("Amount", format_currency(self.purchase["amount"]), row)
        row = add_row("SC Received", f"{float(self.purchase['sc_received'] or 0):.2f}", row)
        row = add_row("Starting SC", f"{float(self.purchase['starting_sc_balance'] or 0):.2f}", row)
        row = add_row("Cashback Earned", format_currency(self.purchase["cashback_earned"] or 0.0), row)
        row = add_row("Remaining", format_currency(self.purchase["remaining_amount"]), row)

        notes_label = QtWidgets.QLabel("Notes")
        notes_value = self.purchase["notes"] or ""
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, row, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
            form.addWidget(notes_edit, row, 1)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            form.addWidget(notes_field, row, 1, QtCore.Qt.AlignVCenter)

        layout.addLayout(form)
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Summary labels
        summary_layout = QtWidgets.QGridLayout()
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        
        original_amt = float(self.purchase["amount"] or 0.0)
        consumed_amt = original_amt - float(self.purchase["remaining_amount"] or 0.0)
        remaining_amt = float(self.purchase["remaining_amount"] or 0.0)
        
        summary_layout.addWidget(QtWidgets.QLabel("Original Amount:"), 0, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(original_amt)), 0, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Total Allocated:"), 1, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(consumed_amt)), 1, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Remaining Basis:"), 2, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(remaining_amt)), 2, 1)
        summary_layout.setColumnStretch(2, 1)
        
        layout.addLayout(summary_layout)
        layout.addSpacing(8)

        # Linked Game Sessions table
        sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.linked_sessions:
            note = QtWidgets.QLabel("No linked game sessions found.")
            note.setWordWrap(True)
            sessions_layout.addWidget(note)
        else:
            self.sessions_table = QtWidgets.QTableWidget(0, 6)
            self.sessions_table.setHorizontalHeaderLabels(
                ["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View"]
            )
            self.sessions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.sessions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.sessions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.sessions_table.setAlternatingRowColors(True)
            self.sessions_table.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            header = self.sessions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.sessions_table.verticalHeader().setVisible(False)
            self.sessions_table.setColumnWidth(0, 100)
            self.sessions_table.setColumnWidth(1, 80)
            self.sessions_table.setColumnWidth(2, 120)
            self.sessions_table.setColumnWidth(3, 100)
            self.sessions_table.setColumnWidth(4, 70)
            sessions_layout.addWidget(self.sessions_table)
            self._populate_sessions_table()

        layout.addWidget(sessions_group, 1)

        # Allocated Redemptions table
        redemptions_group = QtWidgets.QGroupBox("Allocated Redemptions")
        redemptions_layout = QtWidgets.QVBoxLayout(redemptions_group)
        redemptions_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.redemption_allocations:
            note = QtWidgets.QLabel("No redemptions have allocated from this purchase.")
            note.setWordWrap(True)
            redemptions_layout.addWidget(note)
        else:
            self.redemptions_table = QtWidgets.QTableWidget(0, 5)
            self.redemptions_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Redemption Amount", "Allocated From This", "View"]
            )
            self.redemptions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.redemptions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.redemptions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.redemptions_table.setAlternatingRowColors(True)
            self.redemptions_table.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            header = self.redemptions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.redemptions_table.verticalHeader().setVisible(False)
            self.redemptions_table.setColumnWidth(0, 100)
            self.redemptions_table.setColumnWidth(1, 80)
            self.redemptions_table.setColumnWidth(2, 160)
            self.redemptions_table.setColumnWidth(3, 160)
            redemptions_layout.addWidget(self.redemptions_table)
            self._populate_redemptions_table()

        layout.addWidget(redemptions_group, 1)
        return widget

    def _load_redemption_allocations(self):
        """Load all redemptions that have allocated basis from this purchase."""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute('''
            SELECT r.id, r.redemption_date, r.redemption_time, r.amount,
                   ra.allocated_amount
            FROM redemption_allocations ra
            JOIN redemptions r ON r.id = ra.redemption_id
            WHERE ra.purchase_id = ?
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time, '00:00:00') ASC
        ''', (self.purchase["id"],))
        results = c.fetchall()
        conn.close()
        return results

    def _populate_sessions_table(self):
        self.sessions_table.setRowCount(len(self.linked_sessions))
        for row_idx, session in enumerate(self.linked_sessions):
            session_date = self._format_date(session["session_date"]) if session["session_date"] else "—"
            start_time = session["start_time"][:5] if session["start_time"] else "—"
            end_display = f"{self._format_date(session['end_date'])} {session['end_time'][:5]}" if session["end_date"] and session["end_time"] else "—"
            game_type = session["game_type"] or "—"
            status = session["status"] or "—"
            relation = session["relation"] or "—"
            values = [session_date, start_time, end_display, game_type, status]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.sessions_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, sid=session["game_session_id"]: self._open_session(sid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.sessions_table.setCellWidget(row_idx, 5, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self):
        self.redemptions_table.setRowCount(len(self.redemption_allocations))
        for row_idx, redemption in enumerate(self.redemption_allocations):
            date_display = self._format_date(redemption["redemption_date"]) if redemption["redemption_date"] else "—"
            time_display = redemption["redemption_time"][:5] if redemption["redemption_time"] else "—"
            total_amount = format_currency(redemption["amount"])
            allocated_amount = format_currency(redemption["allocated_amount"])

            values = [date_display, time_display, total_amount, allocated_amount]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (2, 3):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.redemptions_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, rid=redemption["id"]: self._open_redemption(rid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.redemptions_table.setCellWidget(row_idx, 4, view_container)
            self.redemptions_table.setRowHeight(
                row_idx,
                max(self.redemptions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_session(self, session_id):
        if not self.on_open_session:
            QtWidgets.QMessageBox.information(
                self, "Sessions Unavailable", "Session view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_session(session_id))

    def _open_redemption(self, redemption_id):
        if not self.on_open_redemption:
            QtWidgets.QMessageBox.information(
                self, "Redemptions Unavailable", "Redemption view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_redemption(redemption_id))

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class RedemptionDialog(QtWidgets.QDialog):
    def __init__(self, db, user_names, site_names, method_names, redemption=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.redemption = redemption
        self.setWindowTitle("Edit Redemption" if redemption else "Add Redemption")
        self.resize(540, 500)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QtWidgets.QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(user_names)
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.addItems(site_names)
        self.method_type_combo = QtWidgets.QComboBox()
        self.method_type_combo.setEditable(True)
        self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")
        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
        self.method_combo.addItems(method_names)
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}

        self.amount_edit = QtWidgets.QLineEdit()
        self.fees_edit = QtWidgets.QLineEdit()
        self.fees_edit.setPlaceholderText("Optional fees")
        
        amount_row = QtWidgets.QHBoxLayout()
        amount_row.setSpacing(8)
        amount_row.addWidget(self.amount_edit, 2)
        amount_row.addWidget(QtWidgets.QLabel("Fees:"))
        amount_row.addWidget(self.fees_edit, 1)
        
        self.receipt_edit = QtWidgets.QLineEdit()
        self.receipt_edit.setPlaceholderText("MM/DD/YY")
        self.receipt_btn = QtWidgets.QPushButton("📅")
        self.receipt_btn.setFixedWidth(44)
        self.receipt_btn.clicked.connect(self._pick_receipt_date)
        receipt_row = QtWidgets.QHBoxLayout()
        receipt_row.setSpacing(8)
        receipt_row.addWidget(self.receipt_edit, 1)
        receipt_row.addWidget(self.receipt_btn)

        self.partial_radio = QtWidgets.QRadioButton("Partial (balance remains)")
        self.final_radio = QtWidgets.QRadioButton("Full (close basis)")
        self.redemption_group = QtWidgets.QButtonGroup(self)
        self.redemption_group.addButton(self.partial_radio)
        self.redemption_group.addButton(self.final_radio)

        self.type_info_btn = QtWidgets.QToolButton()
        self.type_info_btn.setObjectName("InfoButton")
        self.type_info_btn.setText("?")
        self.type_info_btn.setToolTip("What do Partial and Full mean?")
        self.type_info_btn.clicked.connect(self._show_redemption_type_info)

        type_row = QtWidgets.QHBoxLayout()
        type_row.setSpacing(12)
        type_row.addWidget(self.partial_radio)
        type_row.addWidget(self.final_radio)
        type_row.addWidget(self.type_info_btn)
        type_row.addStretch(1)

        self.processed_check = QtWidgets.QCheckBox("Processed")
        self.processed_info_btn = QtWidgets.QToolButton()
        self.processed_info_btn.setObjectName("InfoButton")
        self.processed_info_btn.setText("?")
        self.processed_info_btn.setToolTip("What does Processed mean?")
        self.processed_info_btn.clicked.connect(self._show_processed_info)

        checkbox_row = QtWidgets.QHBoxLayout()
        checkbox_row.setSpacing(12)
        checkbox_row.addWidget(self.processed_check)
        checkbox_row.addWidget(self.processed_info_btn)
        checkbox_row.addStretch(1)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Date"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("Time"), 1, 0)
        form.addLayout(time_row, 1, 1)
        form.addWidget(QtWidgets.QLabel("User"), 2, 0)
        form.addWidget(self.user_combo, 2, 1)
        form.addWidget(QtWidgets.QLabel("Site"), 3, 0)
        form.addWidget(self.site_combo, 3, 1)
        form.addWidget(QtWidgets.QLabel("Method Type"), 4, 0)
        form.addWidget(self.method_type_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Method"), 5, 0)
        form.addWidget(self.method_combo, 5, 1)
        
        form.addWidget(QtWidgets.QLabel("Amount"), 6, 0)
        form.addLayout(amount_row, 6, 1)
        form.addWidget(QtWidgets.QLabel("Receipt Date"), 7, 0)
        form.addLayout(receipt_row, 7, 1)
        form.addWidget(QtWidgets.QLabel("Redemption Type"), 8, 0)
        form.addLayout(type_row, 8, 1)
        form.addWidget(QtWidgets.QLabel("Flags"), 9, 0)
        form.addLayout(checkbox_row, 9, 1)
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(notes_label, 10, 0)
        form.addWidget(self.notes_edit, 10, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)
        
        # Set tab order after all widgets added to layout
        self.setTabOrder(self.site_combo, self.method_type_combo)
        self.setTabOrder(self.method_type_combo, self.method_combo)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)
        self.user_combo.currentTextChanged.connect(self._on_user_change)
        self.method_type_combo.currentTextChanged.connect(self._on_method_type_change)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.method_type_combo.currentTextChanged.connect(self._validate_inline)
        self.method_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.fees_edit.textChanged.connect(self._validate_inline)
        self.receipt_edit.textChanged.connect(self._validate_inline)
        self.partial_radio.toggled.connect(self._validate_inline)
        self.final_radio.toggled.connect(self._validate_inline)

        if redemption:
            self._load_redemption()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()

    def _update_completers(self):
        for combo in (self.user_combo, self.site_combo, self.method_combo):
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        self._open_calendar(self.date_edit)

    def _pick_receipt_date(self):
        self._open_calendar(self.receipt_edit)

    def _open_calendar(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _show_redemption_type_info(self):
        message = (
            "Partial keeps remaining balance open and only applies FIFO basis to this amount.\n"
            "Full closes out remaining basis up to this timestamp and can record a cashflow loss.\n\n"
            "Game Session taxable P/L is not affected either way."
        )
        QtWidgets.QMessageBox.information(self, "Redemption Type", message)

    def _show_processed_info(self):
        message = "Processed is a tracking flag for your workflow. It does not change calculations."
        QtWidgets.QMessageBox.information(self, "Processed Flag", message)

    def _on_user_change(self, value):
        user_name = value.strip()
        if not user_name:
            self.method_type_combo.clear()
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")
            self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
            return
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            self.method_type_combo.clear()
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")
            self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
            return
        user_id = user_row["id"]
        
        # Populate method types for this user
        c.execute(
            """
            SELECT DISTINCT method_type FROM redemption_methods
            WHERE active = 1 AND (user_id IS NULL OR user_id = ?) AND method_type IS NOT NULL AND method_type != ''
            ORDER BY method_type
            """,
            (user_id,),
        )
        method_types = [r["method_type"] for r in c.fetchall()]
        
        preserve_type = getattr(self, "_preserve_method_type_selection", False)
        current_type = self.method_type_combo.currentText().strip()
        self.method_type_combo.blockSignals(True)
        self.method_type_combo.clear()
        self.method_type_combo.addItems(method_types)
        # Remove placeholder since user is selected
        self.method_type_combo.lineEdit().setPlaceholderText("")
        if preserve_type and current_type in method_types:
            self.method_type_combo.setCurrentText(current_type)
        else:
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")
        self.method_type_combo.blockSignals(False)
        
        conn.close()
        
        # Trigger method type change to populate methods
        self._on_method_type_change(self.method_type_combo.currentText())
    
    def _on_method_type_change(self, value):
        method_type = value.strip()
        user_name = self.user_combo.currentText().strip()
        
        # Clear method dropdown if no user or no method_type
        if not user_name or not method_type:
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
            return
        
        user_id = user_row["id"]
        
        # Check if method_type is valid before populating methods
        valid_method_types = {
            self.method_type_combo.itemText(i).lower()
            for i in range(self.method_type_combo.count())
            if self.method_type_combo.itemText(i)
        }
        
        # If method_type is not valid, keep placeholder and don't populate
        if method_type.lower() not in valid_method_types:
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
            conn.close()
            return
        
        # Populate methods filtered by type and user (only if method_type is valid)
        c.execute(
            """
            SELECT name FROM redemption_methods
            WHERE active = 1 AND (user_id IS NULL OR user_id = ?) AND method_type = ?
            ORDER BY name
            """,
            (user_id, method_type),
        )
        methods = [r["name"] for r in c.fetchall()]
        conn.close()
        
        preserve = getattr(self, "_preserve_method_selection", False)
        current = self.method_combo.currentText().strip()
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        self.method_combo.addItems(methods)
        # Remove placeholder only when method type is valid
        self.method_combo.lineEdit().setPlaceholderText("")
        if preserve and current in methods:
            self.method_combo.setCurrentText(current)
        else:
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
        self.method_combo.blockSignals(False)
        self._update_completers()
        self._validate_inline()

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
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
            redemption_date = None
        else:
            try:
                redemption_date = parse_date_input(date_text)
                self._set_valid(self.date_edit)
            except ValueError:
                redemption_date = None
                self._set_invalid(self.date_edit, "Enter a valid date.")

        time_text = self.time_edit.text().strip()
        if not is_valid_time_24h(time_text, allow_blank=True):
            self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
        else:
            self._set_valid(self.site_combo)

        # Validate Method Type is required and valid
        method_type_text = self.method_type_combo.currentText().strip()
        valid_method_types = {
            self.method_type_combo.itemText(i).lower()
            for i in range(self.method_type_combo.count())
            if self.method_type_combo.itemText(i)
        }
        if not method_type_text:
            self._set_invalid(self.method_type_combo, "Method Type is required.")
        elif method_type_text.lower() not in valid_method_types:
            self._set_invalid(self.method_type_combo, "Select a valid Method Type from the list.")
        else:
            self._set_valid(self.method_type_combo)

        amount_text = self.amount_edit.text().strip()
        amount_value = None
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
        else:
            valid, result = validate_currency(amount_text)
            if not valid:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
            else:
                amount_value = result
                self._set_valid(self.amount_edit)

        # Validate fees
        fees_text = self.fees_edit.text().strip()
        fees_value = None
        if fees_text:
            valid, result = validate_currency(fees_text)
            if not valid:
                self._set_invalid(self.fees_edit, "Enter a valid fee amount (max 2 decimals).")
            else:
                fees_value = result
                if fees_value < 0:
                    self._set_invalid(self.fees_edit, "Fees cannot be negative.")
                elif amount_value is not None and fees_value > amount_value:
                    self._set_invalid(self.fees_edit, "Fees cannot exceed the redemption amount.")
                else:
                    self._set_valid(self.fees_edit)
        else:
            # Fees are optional
            self._set_valid(self.fees_edit)
            fees_value = 0

        receipt_text = self.receipt_edit.text().strip()
        if receipt_text:
            try:
                receipt_date = parse_date_input(receipt_text)
                if redemption_date and receipt_date < redemption_date:
                    self._set_invalid(self.receipt_edit, "Receipt date cannot be before redemption date.")
                else:
                    self._set_valid(self.receipt_edit)
            except ValueError:
                self._set_invalid(self.receipt_edit, "Enter a valid receipt date.")
        else:
            self._set_valid(self.receipt_edit)

        method_text = self.method_combo.currentText().strip()
        valid_methods = {
            self.method_combo.itemText(i).lower()
            for i in range(self.method_combo.count())
            if self.method_combo.itemText(i)
        }
        if amount_value is None or amount_value > 0:
            if not method_text or method_text.lower() not in valid_methods:
                self._set_invalid(self.method_combo, "Select a valid Method for the chosen User.")
            else:
                self._set_valid(self.method_combo)
        else:
            if method_text and method_text.lower() not in valid_methods:
                self._set_invalid(self.method_combo, "Select a valid Method for the chosen User.")
            else:
                self._set_valid(self.method_combo)

        if not self.partial_radio.isChecked() and not self.final_radio.isChecked():
            self._set_invalid(self.partial_radio, "Select Partial or Full.")
            self._set_invalid(self.final_radio, "Select Partial or Full.")
        else:
            self._set_valid(self.partial_radio)
            self._set_valid(self.final_radio)

    def _load_redemption(self):
        self.date_edit.setText(self._format_date_for_input(self.redemption["redemption_date"]))
        self.time_edit.setText(self._format_time_for_input(self.redemption["redemption_time"]))
        
        # Set preserve flags to prevent cascading clears during load
        self._preserve_method_type_selection = True
        self._preserve_method_selection = True
        
        # Block signals during initial setup to prevent premature triggers
        self.user_combo.blockSignals(True)
        self.method_type_combo.blockSignals(True)
        self.method_combo.blockSignals(True)
        
        # Load user first
        self.user_combo.setCurrentText(self.redemption["user_name"])
        
        # Unblock and manually trigger user change to populate method_types
        self.user_combo.blockSignals(False)
        self._on_user_change(self.redemption["user_name"])
        
        # Load method_type from the redemption's method (via JOIN)
        method_type_value = self.redemption["method_type"] if "method_type" in self.redemption.keys() else None
        if method_type_value:
            self.method_type_combo.setCurrentText(method_type_value)
            # Trigger method population for this type
            self._on_method_type_change(method_type_value)
        
        # Now load method if it exists
        if self.redemption["method_name"]:
            self.method_combo.setCurrentText(self.redemption["method_name"])
        
        # Unblock signals and clear preserve flags
        self.method_type_combo.blockSignals(False)
        self.method_combo.blockSignals(False)
        self._preserve_method_selection = False
        self._preserve_method_type_selection = False
        
        # Load other fields
        self.site_combo.setCurrentText(self.redemption["site_name"])
        self.amount_edit.setText(str(self.redemption["amount"]))
        fees_val = self.redemption["fees"] if "fees" in self.redemption.keys() else None
        if fees_val:
            self.fees_edit.setText(str(fees_val))
        if self.redemption["receipt_date"]:
            self.receipt_edit.setText(self._format_date_for_input(self.redemption["receipt_date"]))
        if self.redemption["more_remaining"]:
            self.partial_radio.setChecked(True)
        else:
            self.final_radio.setChecked(True)
        self.processed_check.setChecked(bool(self.redemption["processed"]))
        self.notes_edit.setPlainText(self.redemption["notes"] or "")

    def _format_date_for_input(self, date_str):
        if not date_str:
            return ""
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return date_str

    def _format_time_for_input(self, time_str):
        if not time_str:
            return ""
        return time_str[:5]

    def _clear_form(self):
        self.date_edit.clear()
        self.time_edit.clear()
        for combo in (self.user_combo, self.site_combo):
            combo.setCurrentIndex(-1)
            combo.setEditText("")
        self.method_type_combo.setCurrentIndex(0)
        self.method_combo.setCurrentIndex(-1)
        self.method_combo.setEditText("")
        self.amount_edit.clear()
        self.fees_edit.clear()
        self.receipt_edit.clear()
        self.partial_radio.setChecked(False)
        self.final_radio.setChecked(False)
        self.processed_check.setChecked(False)
        self.notes_edit.clear()
        self._set_today()
        self._validate_inline()

    def collect_data(self):
        user_name = self.user_combo.currentText().strip()
        site_name = self.site_combo.currentText().strip()
        if not user_name or not site_name:
            return None, "Please select User and Site."

        date_str = self.date_edit.text().strip()
        if not date_str:
            return None, "Please enter a redemption date."
        try:
            rdate = parse_date_input(date_str)
        except ValueError:
            return None, "Please enter a valid redemption date."

        time_str = self.time_edit.text().strip()
        if time_str and not is_valid_time_24h(time_str, allow_blank=False):
            return None, "Please enter a valid time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            rtime = parse_time_input(time_str)
        except ValueError:
            return None, "Please enter a valid time (HH:MM or HH:MM:SS)."

        if not self.partial_radio.isChecked() and not self.final_radio.isChecked():
            return None, "Please choose Partial or Full for the redemption type."

        receipt_str = self.receipt_edit.text().strip()
        receipt_date = None
        if receipt_str:
            try:
                receipt_date = parse_date_input(receipt_str)
                if receipt_date < rdate:
                    return None, "Receipt date cannot be before redemption date."
            except ValueError:
                return None, "Please enter a valid receipt date."

        amount_str = self.amount_edit.text().strip()
        if not amount_str:
            return None, "Please enter a redemption amount."
        valid, result = validate_currency(amount_str)
        if not valid:
            return None, result
        amount = result

        # Validate and collect fees (optional)
        fees_str = self.fees_edit.text().strip()
        fees = 0
        if fees_str:
            valid, result = validate_currency(fees_str)
            if not valid:
                return None, "Please enter a valid fee amount (max 2 decimals)."
            fees = result
            if fees < 0:
                return None, "Fees cannot be negative."
            if fees > amount:
                return None, "Fees cannot exceed the redemption amount."

        method_name = self.method_combo.currentText().strip()
        if amount > 0 and not method_name:
            return None, "Please select a redemption method."

        notes = self.notes_edit.toPlainText().strip()

        return {
            "user_name": user_name,
            "site_name": site_name,
            "method_name": method_name,
            "redemption_date": rdate.strftime("%Y-%m-%d"),
            "redemption_time": rtime,
            "amount": amount,
            "fees": fees,
            "receipt_date": receipt_date.strftime("%Y-%m-%d") if receipt_date else None,
            "more_remaining": self.partial_radio.isChecked(),
            "processed": self.processed_check.isChecked(),
            "notes": notes,
        }, None


class RedemptionViewDialog(QtWidgets.QDialog):
    def __init__(
        self, redemption, allocations=None, parent=None, on_edit=None, on_open=None, on_open_purchase=None, on_open_session=None, on_delete=None, on_view_realized=None
    ):
        super().__init__(parent)
        self.redemption = redemption
        self.allocations = allocations or []
        self._on_edit = on_edit
        self._on_open = on_open
        self.on_open_purchase = on_open_purchase
        self.on_open_session = on_open_session
        self._on_delete = on_delete
        self._on_view_realized = on_view_realized
        self.setWindowTitle("View Redemption")
        self.resize(700, 650)
        
        # Fetch linked sessions
        from database import Database
        from business_logic import FIFOCalculator, SessionManager
        self.db = Database()
        fifo = FIFOCalculator(self.db)
        self.session_manager = SessionManager(self.db, fifo)
        self.linked_sessions = self.session_manager.get_links_for_redemption(redemption["id"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Create tab widget
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_details_tab(), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_view_realized:
            view_realized_btn = QtWidgets.QPushButton("View Realized Position")
            btn_row.addWidget(view_realized_btn)
        if self._on_open:
            open_btn = QtWidgets.QPushButton("View in Redemptions")
            btn_row.addWidget(open_btn)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_view_realized:
            view_realized_btn.clicked.connect(self._handle_view_realized)
        if self._on_open:
            open_btn.clicked.connect(self._handle_open)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _format_date(self, value):
        """Helper to format date strings to MM/DD/YY"""
        if not value:
            return "—"
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return value

    def _create_details_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnMinimumWidth(1, 300)

        def add_row(label_text, value, row, wrap=False):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label.setWordWrap(wrap)
            form.addWidget(label, row, 0)
            form.addWidget(value_label, row, 1)
            return row + 1

        def format_time(value):
            return value[:5] if value else "—"

        amount = float(self.redemption["amount"] or 0.0)
        method_name = self.redemption["method_name"] or ""
        if amount == 0:
            method_name = "Loss"

        receipt_date = self.redemption["receipt_date"] or ""
        if amount == 0:
            receipt_display = "N/A"
        elif receipt_date:
            receipt_display = self._format_date(receipt_date)
        else:
            receipt_display = "PENDING"

        redemption_type = "Partial" if self.redemption["more_remaining"] else "Full"
        processed_display = "Yes" if self.redemption["processed"] else "No"

        row = 0
        row = add_row("Date", self._format_date(self.redemption["redemption_date"]), row)
        row = add_row("Time", format_time(self.redemption["redemption_time"]), row)
        row = add_row("User", self.redemption["user_name"] or "—", row)
        row = add_row("Site", self.redemption["site_name"] or "—", row)
        row = add_row("Amount", format_currency(amount), row)
        # Fees (optional)
        fees_val = self.redemption["fees"] if "fees" in self.redemption.keys() else None
        fees_display = format_currency(fees_val) if fees_val not in (None, "", 0, 0.0) else "—"
        row = add_row("Fees", fees_display, row)
        row = add_row("Receipt Date", receipt_display, row)
        row = add_row("Method", method_name or "—", row)
        row = add_row("Redemption Type", redemption_type, row)
        row = add_row("Processed", processed_display, row)

        notes_label = QtWidgets.QLabel("Notes")
        notes_value = self.redemption["notes"] or ""
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, row, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
            form.addWidget(notes_edit, row, 1)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            form.addWidget(notes_field, row, 1, QtCore.Qt.AlignVCenter)

        layout.addLayout(form)
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Calculate unbased/winnings portion
        total_allocated = sum(float(a["allocated_amount"] or 0) for a in self.allocations)
        redemption_amount = float(self.redemption["amount"] or 0)
        unbased_portion = redemption_amount - total_allocated
        is_free_sc = self.redemption["is_free_sc"] if "is_free_sc" in self.redemption.keys() else 0

        # Summary labels
        summary_layout = QtWidgets.QGridLayout()
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        
        if is_free_sc:
            summary_layout.addWidget(QtWidgets.QLabel("Cost Basis:"), 0, 0)
            cost_basis_label = QtWidgets.QLabel("$0.00 (Free SC)")
            cost_basis_label.setStyleSheet("font-weight: 600; color: #2e7d32;")
            summary_layout.addWidget(cost_basis_label, 0, 1)
        else:
            summary_layout.addWidget(QtWidgets.QLabel("Cost Basis:"), 0, 0)
            summary_layout.addWidget(QtWidgets.QLabel(format_currency(total_allocated)), 0, 1)
        
        if unbased_portion > 0.01:
            summary_layout.addWidget(QtWidgets.QLabel("Unbased Portion (Winnings):"), 1, 0)
            winnings_label = QtWidgets.QLabel(format_currency(unbased_portion))
            winnings_label.setStyleSheet("font-weight: 600; color: #2e7d32;")
            summary_layout.addWidget(winnings_label, 1, 1)
        
        summary_layout.addWidget(QtWidgets.QLabel("Total Redemption:"), 2, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(redemption_amount)), 2, 1)
        summary_layout.setColumnStretch(2, 1)
        
        layout.addLayout(summary_layout)
        layout.addSpacing(8)

        # Allocated Purchases table
        purchases_group = QtWidgets.QGroupBox("Allocated Purchases (FIFO)")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.allocations:
            note = QtWidgets.QLabel(
                "This redemption has no purchase basis. This may occur when cashing out freebies, bonuses, "
                "or winnings from partial redemptions. If you believe this is incorrect, use Tools → "
                "Recalculate Everything to rebuild FIFO allocations."
            )
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.allocations_table = QtWidgets.QTableWidget(0, 6)
            self.allocations_table.setHorizontalHeaderLabels(
                ["Purchase Date/Time", "Amount", "SC", "Allocated", "Remaining", "View"]
            )
            self.allocations_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.allocations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.allocations_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.allocations_table.setAlternatingRowColors(True)
            self.allocations_table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            header = self.allocations_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.allocations_table.verticalHeader().setVisible(False)
            self.allocations_table.setColumnWidth(0, 140)
            self.allocations_table.setColumnWidth(1, 90)
            self.allocations_table.setColumnWidth(2, 80)
            self.allocations_table.setColumnWidth(3, 90)
            self.allocations_table.setColumnWidth(4, 90)
            purchases_layout.addWidget(self.allocations_table)
            self._populate_allocations()

        layout.addWidget(purchases_group, 1)

        # Linked Game Sessions table
        sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.linked_sessions:
            note = QtWidgets.QLabel("No linked game sessions found.")
            note.setWordWrap(True)
            sessions_layout.addWidget(note)
        else:
            self.sessions_table = QtWidgets.QTableWidget(0, 6)
            self.sessions_table.setHorizontalHeaderLabels(
                ["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View"]
            )
            self.sessions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.sessions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.sessions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.sessions_table.setAlternatingRowColors(True)
            self.sessions_table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            header = self.sessions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.sessions_table.verticalHeader().setVisible(False)
            self.sessions_table.setColumnWidth(0, 100)
            self.sessions_table.setColumnWidth(1, 80)
            self.sessions_table.setColumnWidth(2, 120)
            self.sessions_table.setColumnWidth(3, 100)
            self.sessions_table.setColumnWidth(4, 70)
            self.sessions_table.setColumnWidth(5, 70)
            sessions_layout.addWidget(self.sessions_table)
            self._populate_sessions_table()

        layout.addWidget(sessions_group, 1)
        return widget

    def _populate_allocations(self):
        self.allocations_table.setRowCount(len(self.allocations))
        for row_idx, row in enumerate(self.allocations):
            purchase_time = row["purchase_time"] if row["purchase_time"] else "00:00:00"
            date_display = format_date_time(row["purchase_date"], purchase_time)
            amount = format_currency(row["amount"])
            sc_received = f"{float(row['sc_received'] or 0.0):.2f}"
            allocated = format_currency(row["allocated_amount"])
            remaining = format_currency(row["remaining_amount"])

            values = [date_display, amount, sc_received, allocated, remaining]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (1, 2, 3, 4):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.allocations_table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, pid=row["purchase_id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QHBoxLayout(view_container)
            view_layout.setContentsMargins(0, 2, 0, 2)
            view_layout.addStretch(1)
            view_layout.addWidget(view_btn)
            view_layout.addStretch(1)
            self.allocations_table.setCellWidget(row_idx, 5, view_container)

    def _populate_sessions_table(self):
        self.sessions_table.setRowCount(len(self.linked_sessions))
        for row_idx, session in enumerate(self.linked_sessions):
            session_date = self._format_date(session["session_date"]) if session["session_date"] else "—"
            start_time = session["start_time"][:5] if session["start_time"] else "—"
            end_display = f"{self._format_date(session['end_date'])} {session['end_time'][:5]}" if session["end_date"] and session["end_time"] else "—"
            game_type = session["game_type"] or "—"
            status = session["status"] or "—"
            relation = session["relation"] or "—"
            values = [session_date, start_time, end_display, game_type, status]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.sessions_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, sid=session["game_session_id"]: self._open_session(sid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QHBoxLayout(view_container)
            view_layout.setContentsMargins(0, 2, 0, 2)
            view_layout.addStretch(1)
            view_layout.addWidget(view_btn)
            view_layout.addStretch(1)
            self.sessions_table.setCellWidget(row_idx, 5, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_session(self, session_id):
        if not self.on_open_session:
            QtWidgets.QMessageBox.information(
                self, "Sessions Unavailable", "Session view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_session(session_id))

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_view_realized(self):
        if self._on_view_realized:
            self.accept()
            QtCore.QTimer.singleShot(0, lambda: self._on_view_realized(self.redemption["id"]))

    def _handle_open(self):
        if self._on_open:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_open)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class ExpenseDialog(QtWidgets.QDialog):
    def __init__(self, db, user_names, expense=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.expense = expense
        self.setWindowTitle("Edit Expense" if expense else "Add Expense")
        self.resize(520, 420)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)  # Increased for consistent visual spacing
        form.setColumnStretch(1, 1)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.amount_edit = QtWidgets.QLineEdit()
        self.vendor_edit = QtWidgets.QLineEdit()
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItem("")
        self.user_combo.addItems(user_names)
        self._user_lookup = {name.lower(): name for name in user_names}

        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(False)
        self.category_combo.addItems(EXPENSE_CATEGORIES)

        self.desc_edit = QtWidgets.QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Description...")
        self.desc_edit.setObjectName("NotesField")
        self.desc_edit.setMinimumHeight(self.desc_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Date"), 0, 0)
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
        form.addWidget(self.desc_edit, 5, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)

        self.date_edit.textChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.vendor_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.category_combo.currentTextChanged.connect(self._validate_inline)

        if expense:
            self._load_expense()
        else:
            self._clear_form()

        self._validate_inline()

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

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
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
        else:
            try:
                parse_date_input(date_text)
                self._set_valid(self.date_edit)
            except ValueError:
                self._set_invalid(self.date_edit, "Enter a valid date.")

        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
        else:
            valid, _result = validate_currency(amount_text)
            if not valid:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.amount_edit)

        vendor_text = self.vendor_edit.text().strip()
        if not vendor_text:
            self._set_invalid(self.vendor_edit, "Vendor is required.")
        else:
            self._set_valid(self.vendor_edit)

        user_text = self.user_combo.currentText().strip()
        if user_text and user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User or leave blank.")
        else:
            self._set_valid(self.user_combo)

        category_text = self.category_combo.currentText().strip()
        if not category_text:
            self._set_invalid(self.category_combo, "Category is required.")
        else:
            self._set_valid(self.category_combo)

    def _load_expense(self):
        self.date_edit.setText(self._format_date_for_input(self.expense["expense_date"]))
        self.amount_edit.setText(str(self.expense["amount"]))
        self.vendor_edit.setText(self.expense["vendor"] or "")
        user_name = self.expense["user_name"] or ""
        self.user_combo.setCurrentText(user_name)
        category = self.expense["category"] or "Other Expenses"
        if category not in EXPENSE_CATEGORIES:
            self.category_combo.addItem(category)
        self.category_combo.setCurrentText(category)
        self.desc_edit.setPlainText(self.expense["description"] or "")

    def _format_date_for_input(self, date_str):
        if not date_str:
            return ""
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return date_str

    def _clear_form(self):
        self.date_edit.clear()
        self.amount_edit.clear()
        self.vendor_edit.clear()
        self.user_combo.setCurrentIndex(0)
        self.category_combo.setCurrentText("Other Expenses")
        self.desc_edit.clear()
        self._set_today()
        self._validate_inline()

    def collect_data(self):
        self._validate_inline()
        if self.date_edit.property("invalid"):
            return None, "Please enter a valid date."
        if self.amount_edit.property("invalid"):
            return None, "Please enter a valid amount."
        if self.vendor_edit.property("invalid"):
            return None, "Please enter a vendor."
        if self.user_combo.property("invalid"):
            return None, "Please select a valid user or leave blank."
        if self.category_combo.property("invalid"):
            return None, "Please select a category."

        date_val = parse_date_input(self.date_edit.text().strip()).strftime("%Y-%m-%d")
        valid_amount, amount = validate_currency(self.amount_edit.text().strip())
        if not valid_amount:
            return None, "Please enter a valid amount."

        user_text = self.user_combo.currentText().strip()
        user_name = self._user_lookup.get(user_text.lower()) if user_text else ""

        return (
            {
                "expense_date": date_val,
                "amount": amount,
                "vendor": self.vendor_edit.text().strip(),
                "user_name": user_name,
                "category": self.category_combo.currentText().strip() or "Other Expenses",
                "description": self.desc_edit.toPlainText().strip(),
            },
            None,
        )


class ExpenseViewDialog(QtWidgets.QDialog):
    def __init__(self, expense, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.expense = expense
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Expense")
        self.resize(540, 480)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)  # Increased for consistent visual spacing
        form.setColumnStretch(1, 1)

        def add_row(label_text, value, row):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
            )
            form.addWidget(label, row, 0)
            form.addWidget(value_label, row, 1)
            return row + 1

        def format_date(value):
            if not value:
                return "—"
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return value

        row = 0
        row = add_row("Date", format_date(expense["expense_date"]), row)
        row = add_row("Vendor", expense["vendor"] or "—", row)
        row = add_row("User", expense["user_name"] or "—", row)
        row = add_row("Category", expense["category"] or "—", row)
        row = add_row("Amount", format_currency(expense["amount"]), row)

        desc_value = expense["description"] or ""
        desc_label = QtWidgets.QLabel("Description")
        desc_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if desc_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(desc_label, row, 0)
        if desc_value:
            desc_edit = QtWidgets.QPlainTextEdit()
            desc_edit.setObjectName("NotesField")
            desc_edit.setReadOnly(True)
            desc_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            desc_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            desc_edit.setPlainText(desc_value)
            desc_edit.setMinimumHeight(desc_edit.fontMetrics().lineSpacing() * 3 + 12)
            form.addWidget(desc_edit, row, 1)
        else:
            desc_field = QtWidgets.QLabel("—")
            desc_field.setObjectName("InfoField")
            desc_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            desc_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(desc_field.sizeHint().height(), 26)
            desc_field.setFixedHeight(fixed_height)
            form.addWidget(desc_field, row, 1, QtCore.Qt.AlignVCenter)

        spacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        form.addItem(spacer, row + 1, 0, 1, 2)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)
        QtCore.QTimer.singleShot(0, close_btn.setFocus)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class GameSessionStartDialog(QtWidgets.QDialog):
    def __init__(
        self,
        db,
        session_mgr,
        user_names,
        site_names,
        game_types,
        game_names_by_type,
        session=None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.session = session
        self.game_names_by_type = game_names_by_type or {}
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}
        self._game_type_lookup = {name.lower(): name for name in game_types}
        self.setWindowTitle("Edit Session" if session else "Start Session")
        self.resize(640, 560)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Session section
        session_group = QtWidgets.QGroupBox("Session")
        session_grid = QtWidgets.QGridLayout(session_group)
        session_grid.setHorizontalSpacing(10)
        session_grid.setVerticalSpacing(8)
        session_grid.setColumnStretch(1, 1)
        session_grid.setColumnStretch(3, 1)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)
        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QtWidgets.QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.addItems(site_names)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(user_names)

        session_grid.addWidget(QtWidgets.QLabel("Date"), 0, 0)
        session_grid.addLayout(date_row, 0, 1)
        session_grid.addWidget(QtWidgets.QLabel("Start Time"), 0, 2)
        session_grid.addLayout(time_row, 0, 3)
        session_grid.addWidget(QtWidgets.QLabel("Site"), 1, 0)
        session_grid.addWidget(self.site_combo, 1, 1)
        session_grid.addWidget(QtWidgets.QLabel("User"), 1, 2)
        session_grid.addWidget(self.user_combo, 1, 3)
        layout.addWidget(session_group)

        # Game section
        game_group = QtWidgets.QGroupBox("Game")
        game_grid = QtWidgets.QGridLayout(game_group)
        game_grid.setHorizontalSpacing(10)
        game_grid.setVerticalSpacing(8)
        game_grid.setColumnStretch(1, 1)
        game_grid.setColumnStretch(3, 1)

        self.game_type_combo = QtWidgets.QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QtWidgets.QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")

        self.rtp_tooltip = QtWidgets.QLabel("")
        self.rtp_tooltip.setObjectName("HelperText")
        self.rtp_tooltip.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.rtp_tooltip.setWordWrap(True)

        game_grid.addWidget(QtWidgets.QLabel("Game Type"), 0, 0)
        game_grid.addWidget(self.game_type_combo, 0, 1)
        game_grid.addWidget(QtWidgets.QLabel("Game Name"), 0, 2)
        game_grid.addWidget(self.game_name_combo, 0, 3)
        game_grid.addWidget(self.rtp_tooltip, 1, 0, 1, 4)
        layout.addWidget(game_group)

        # Balances section
        balance_group = QtWidgets.QGroupBox("Starting Balances")
        balance_grid = QtWidgets.QGridLayout(balance_group)
        balance_grid.setHorizontalSpacing(10)
        balance_grid.setVerticalSpacing(8)
        balance_grid.setColumnStretch(1, 1)
        balance_grid.setColumnStretch(3, 1)

        self.start_total_edit = QtWidgets.QLineEdit()
        self.start_redeem_edit = QtWidgets.QLineEdit()

        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.balance_label = QtWidgets.QLabel("Balance Check")
        self.balance_label.setToolTip(balance_tooltip)
        self.balance_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.freebie_label = QtWidgets.QLabel("")
        self.freebie_label.setWordWrap(True)
        self.freebie_label.setObjectName("InfoField")
        self.freebie_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.freebie_label.setProperty("status", "neutral")
        self.freebie_label.setToolTip(balance_tooltip)

        balance_grid.addWidget(QtWidgets.QLabel("Starting Total SC"), 0, 0)
        balance_grid.addWidget(self.start_total_edit, 0, 1)
        balance_grid.addWidget(QtWidgets.QLabel("Starting Redeemable"), 0, 2)
        balance_grid.addWidget(self.start_redeem_edit, 0, 3)
        balance_grid.addWidget(self.balance_label, 1, 0)
        balance_grid.addWidget(self.freebie_label, 1, 1, 1, 3)
        layout.addWidget(balance_group)

        # Notes section
        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)
        self.game_type_combo.currentTextChanged.connect(self._update_game_names)
        self.game_type_combo.currentTextChanged.connect(self._validate_inline)
        self.game_name_combo.currentTextChanged.connect(self._validate_inline)
        self.game_name_combo.currentTextChanged.connect(self._update_rtp_tooltip)
        self.site_combo.currentTextChanged.connect(self._update_freebie_label)
        self.user_combo.currentTextChanged.connect(self._update_freebie_label)
        self.start_total_edit.textChanged.connect(self._update_freebie_label)
        self.date_edit.textChanged.connect(self._update_freebie_label)
        self.time_edit.textChanged.connect(self._update_freebie_label)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.start_total_edit.textChanged.connect(self._validate_inline)
        self.start_redeem_edit.textChanged.connect(self._validate_inline)

        if session:
            self._load_session()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()

    def _all_game_names(self):
        names = set()
        for game_list in self.game_names_by_type.values():
            names.update(game_list)
        return sorted(names)

    def _update_game_names(self):
        game_type = self.game_type_combo.currentText().strip()
        
        # If no game type or invalid, clear and show placeholder
        if not game_type:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return
        
        # Check if game type is valid
        if game_type.lower() not in self._game_type_lookup:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return
        
        # Game type is valid, populate names and remove placeholder
        type_key = None
        for key in self.game_names_by_type:
            if key.lower() == game_type.lower():
                type_key = key
                break
        names = list(self.game_names_by_type.get(type_key, [])) if type_key else []
        current = self.game_name_combo.currentText().strip()
        if "" not in names:
            names.insert(0, "")
        self.game_name_combo.blockSignals(True)
        self.game_name_combo.clear()
        self.game_name_combo.addItems(names)
        self.game_name_combo.lineEdit().setPlaceholderText("")  # Remove placeholder
        if current and current in names:
            self.game_name_combo.setCurrentText(current)
        else:
            self.game_name_combo.setCurrentIndex(0)
            self.game_name_combo.setEditText("")
        self.game_name_combo.blockSignals(False)
        self._update_completers()
        self._validate_inline()

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
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
        else:
            try:
                parse_date_input(date_text)
                self._set_valid(self.date_edit)
            except ValueError:
                self._set_invalid(self.date_edit, "Enter a valid date.")

        time_text = self.time_edit.text().strip()
        if not is_valid_time_24h(time_text, allow_blank=True):
            self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
        else:
            self._set_valid(self.site_combo)

        game_type_text = self.game_type_combo.currentText().strip()
        if game_type_text and game_type_text.lower() not in self._game_type_lookup:
            self._set_invalid(self.game_type_combo, "Select a valid Game Type.")
        else:
            self._set_valid(self.game_type_combo)

        game_name_text = self.game_name_combo.currentText().strip()
        if game_name_text:
            if not game_type_text:
                self._set_invalid(self.game_type_combo, "Select a Game Type for this Game Name.")
                self._set_invalid(self.game_name_combo, "Select a valid Game Name for the chosen type.")
            else:
                type_key = None
                for key in self.game_names_by_type:
                    if key.lower() == game_type_text.lower():
                        type_key = key
                        break
                valid_names = self.game_names_by_type.get(type_key, []) if type_key else []
                valid_lookup = {name.lower(): name for name in valid_names if name}
                if game_name_text.lower() not in valid_lookup:
                    self._set_invalid(self.game_name_combo, "Select a valid Game Name for the chosen type.")
                else:
                    self._set_valid(self.game_name_combo)
        else:
            self._set_valid(self.game_name_combo)

        start_total_text = self.start_total_edit.text().strip()
        if not start_total_text:
            self._set_invalid(self.start_total_edit, "Starting Total SC is required.")
        else:
            valid, _result = validate_currency(start_total_text)
            if not valid:
                self._set_invalid(self.start_total_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.start_total_edit)

        start_redeem_text = self.start_redeem_edit.text().strip()
        if not start_redeem_text:
            self._set_invalid(self.start_redeem_edit, "Starting Redeemable is required.")
        else:
            valid, _result = validate_currency(start_redeem_text)
            if not valid:
                self._set_invalid(self.start_redeem_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.start_redeem_edit)

    def _update_completers(self):
        for combo in (
            self.user_combo,
            self.site_combo,
            self.game_type_combo,
            self.game_name_combo,
        ):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _format_date_for_input(self, date_str):
        if not date_str:
            return ""
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return date_str

    def _format_time_for_input(self, time_str):
        if not time_str:
            return ""
        return time_str[:5]

    def _lookup_ids(self, site_name, user_name):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        conn.close()
        return (site_row["id"] if site_row else None, user_row["id"] if user_row else None)

    def _update_freebie_label(self):
        site_name = self.site_combo.currentText().strip()
        user_name = self.user_combo.currentText().strip()
        start_total_text = self.start_total_edit.text().strip()
        if not site_name or not user_name or not start_total_text:
            self.freebie_label.setText("—")
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.style().unpolish(self.freebie_label)
            self.freebie_label.style().polish(self.freebie_label)
            return
        valid, result = validate_currency(start_total_text)
        if not valid:
            self.freebie_label.setText("—")
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.style().unpolish(self.freebie_label)
            self.freebie_label.style().polish(self.freebie_label)
            return
        site_id, user_id = self._lookup_ids(site_name, user_name)
        if not site_id or not user_id:
            self.freebie_label.setText("—")
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.style().unpolish(self.freebie_label)
            self.freebie_label.style().polish(self.freebie_label)
            return
        session_date = self.date_edit.text().strip() or None
        session_time = self.time_edit.text().strip() or None
        try:
            parsed_date = parse_date_input(session_date).strftime("%Y-%m-%d") if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.freebie_label.setText("—")
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.style().unpolish(self.freebie_label)
            self.freebie_label.style().polish(self.freebie_label)
            return
        info = self.session_mgr.detect_freebies(
            site_id, user_id, result, parsed_date, parsed_time
        )
        delta_total = float(info.get("delta_total_sc", 0.0))
        expected_total = float(info.get("expected_total_sc", 0.0))
        freebies_sc = float(info.get("freebies_sc", 0.0))
        freebies_dollar = float(info.get("freebies_dollar", 0.0))
        missing_sc = float(info.get("missing_sc", 0.0))
        if freebies_sc > 0:
            self.freebie_label.setProperty("status", "positive")
            self.freebie_label.setText(
                f"+ Detected {freebies_sc:.2f} SC in extra balance (${freebies_dollar:.2f})"
            )
        elif missing_sc > 0:
            self.freebie_label.setProperty("status", "negative")
            self.freebie_label.setText(
                f"- WARNING: Starting balance is {missing_sc:.2f} SC less than expected ({expected_total:.2f})"
            )
        else:
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.setText(f"Matches expected balance ({expected_total:.2f} SC)")
        self.freebie_label.style().unpolish(self.freebie_label)
        self.freebie_label.style().polish(self.freebie_label)

    def _update_rtp_tooltip(self):
        """Update the RTP tooltip with Expected and Actual RTP when a game is selected"""
        game_name = self.game_name_combo.currentText().strip()
        if not game_name:
            self.rtp_tooltip.setText("")
            return
        
        # Fetch game RTP info from database
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT rtp, actual_rtp FROM games WHERE name = ?
            """,
            (game_name,),
        )
        row = c.fetchone()
        conn.close()
        
        if row:
            exp_rtp = row['rtp']
            act_rtp = row['actual_rtp']
            
            exp_str = f"{exp_rtp:.2f}%" if exp_rtp is not None else "—"
            act_str = f"{act_rtp:.2f}%" if act_rtp is not None else "—"
            
            self.rtp_tooltip.setText(f"Exp RTP: {exp_str} / Act RTP: {act_str}")
        else:
            self.rtp_tooltip.setText("")

    def _load_session(self):
        self.date_edit.setText(self._format_date_for_input(self.session["session_date"]))
        self.time_edit.setText(self._format_time_for_input(self.session["start_time"]))
        self.user_combo.setCurrentText(self.session["user_name"])
        self.site_combo.setCurrentText(self.session["site_name"])
        self.game_type_combo.blockSignals(True)
        if self.session["game_type"]:
            self.game_type_combo.setCurrentText(self.session["game_type"])
        self.game_type_combo.blockSignals(False)
        self.game_name_combo.blockSignals(True)
        if self.session["game_name"]:
            self.game_name_combo.setCurrentText(self.session["game_name"])
        self.game_name_combo.blockSignals(False)
        self._update_game_names()
        self.start_total_edit.setText(str(self.session["starting_sc_balance"]))
        start_redeem = (
            self.session["starting_redeemable_sc"]
            if self.session["starting_redeemable_sc"] is not None
            else self.session["starting_sc_balance"]
        )
        self.start_redeem_edit.setText(str(start_redeem))
        self.notes_edit.setPlainText(self.session["notes"] or "")
        self._update_freebie_label()
        self._update_rtp_tooltip()

    def _clear_form(self):
        self.date_edit.clear()
        self.time_edit.clear()
        for combo in (self.user_combo, self.site_combo, self.game_type_combo, self.game_name_combo):
            combo.setCurrentIndex(-1)
            if combo.isEditable():
                combo.setEditText("")
            else:
                combo.setCurrentIndex(0)
        self.start_total_edit.clear()
        self.start_redeem_edit.clear()
        self.notes_edit.clear()
        self._set_today()
        self._set_now()
        self.freebie_label.setText("—")
        self.freebie_label.setProperty("status", "neutral")
        self.freebie_label.style().unpolish(self.freebie_label)
        self.freebie_label.style().polish(self.freebie_label)
        self.rtp_tooltip.setText("")
        self._validate_inline()

    def collect_data(self):
        user_name = self.user_combo.currentText().strip()
        site_name = self.site_combo.currentText().strip()
        game_type = self.game_type_combo.currentText().strip()
        game_name = self.game_name_combo.currentText().strip()
        if not user_name or not site_name:
            return None, "Please select Date, User, and Site."
        if game_name and not game_type:
            return None, "Please select a Game Type when entering a Game Name."

        date_str = self.date_edit.text().strip()
        if not date_str:
            return None, "Please enter a session date."
        try:
            sdate = parse_date_input(date_str)
        except ValueError:
            return None, "Please enter a valid session date."

        time_str = self.time_edit.text().strip()
        if time_str and not is_valid_time_24h(time_str, allow_blank=False):
            return None, "Please enter a valid start time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            stime = parse_time_input(time_str)
        except ValueError:
            return None, "Please enter a valid start time (HH:MM or HH:MM:SS)."

        start_total_str = self.start_total_edit.text().strip()
        if not start_total_str:
            return None, "Please enter Starting Total SC."
        valid, result = validate_currency(start_total_str)
        if not valid:
            return None, result
        start_total = result

        start_redeem_str = self.start_redeem_edit.text().strip()
        if not start_redeem_str:
            return None, "Please enter Starting Redeemable SC."
        valid, result = validate_currency(start_redeem_str)
        if not valid:
            return None, result
        start_redeem = result

        if start_redeem > start_total:
            return None, "Starting Redeemable SC cannot exceed Starting Total SC."

        wager_amount = None
        if self.session is not None and self.session["wager_amount"] is not None:
            wager_amount = float(self.session["wager_amount"] or 0.0)

        notes = self.notes_edit.toPlainText().strip()

        return {
            "session_date": sdate.strftime("%Y-%m-%d"),
            "start_time": stime,
            "user_name": user_name,
            "site_name": site_name,
            "game_type": game_type,
            "game_name": game_name,
            "wager_amount": wager_amount,
            "starting_total_sc": start_total,
            "starting_redeemable_sc": start_redeem,
            "notes": notes,
        }, None


class GameSessionEndDialog(QtWidgets.QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("End Game Session")
        self.resize(640, 560)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        start_total = float(session["starting_sc_balance"] or 0.0)
        start_redeem = session["starting_redeemable_sc"]
        if start_redeem is None:
            start_redeem = start_total
        start_redeem = float(start_redeem)

        info = QtWidgets.QLabel(
            f"Starting Total SC: {start_total:.2f} | Starting Redeemable: {start_redeem:.2f}"
        )
        layout.addWidget(info)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)
        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QtWidgets.QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.end_total_edit = QtWidgets.QLineEdit()
        self.end_redeem_edit = QtWidgets.QLineEdit()
        self.wager_edit = QtWidgets.QLineEdit()

        self.locked_label = QtWidgets.QLabel("—")
        self.locked_label.setObjectName("InfoField")
        self.locked_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.locked_label.setProperty("status", "neutral")
        self.pnl_label = QtWidgets.QLabel("—")
        self.pnl_label.setObjectName("InfoField")
        self.pnl_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.pnl_label.setProperty("status", "neutral")

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("End Date"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("End Time"), 1, 0)
        form.addLayout(time_row, 1, 1)
        form.addWidget(QtWidgets.QLabel("Ending Total SC"), 2, 0)
        form.addWidget(self.end_total_edit, 2, 1)
        form.addWidget(QtWidgets.QLabel("Ending Redeemable"), 3, 0)
        form.addWidget(self.end_redeem_edit, 3, 1)
        form.addWidget(QtWidgets.QLabel("Wager Amount"), 4, 0)
        form.addWidget(self.wager_edit, 4, 1)
        locked_title = QtWidgets.QLabel("Locked SC")
        locked_title.setToolTip("Total SC minus Redeemable SC")
        locked_title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        form.addWidget(locked_title, 5, 0)
        form.addWidget(self.locked_label, 5, 1)
        redeem_change_label = QtWidgets.QLabel("Redeemable Change")
        redeem_change_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        form.addWidget(redeem_change_label, 6, 0)
        form.addWidget(self.pnl_label, 6, 1)
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(notes_label, 7, 0)
        form.addWidget(self.notes_edit, 7, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("End Session")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self.reject)
        self.end_total_edit.textChanged.connect(lambda: self._update_locked(start_redeem))
        self.end_redeem_edit.textChanged.connect(lambda: self._update_locked(start_redeem))
        self.end_redeem_edit.textChanged.connect(lambda: self._update_pnl(start_redeem))
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.end_total_edit.textChanged.connect(self._validate_inline)
        self.end_redeem_edit.textChanged.connect(self._validate_inline)
        self.wager_edit.textChanged.connect(self._validate_inline)

        self._set_today()
        self._set_now()
        if session["wager_amount"] is not None:
            self.wager_edit.setText(str(session["wager_amount"]))
        self._validate_inline()

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _update_locked(self, start_redeem):
        try:
            end_total = float(self.end_total_edit.text().strip() or 0.0)
            end_redeem = float(self.end_redeem_edit.text().strip() or 0.0)
        except ValueError:
            self.locked_label.setText("—")
            self.locked_label.setProperty("status", "neutral")
            self.locked_label.style().unpolish(self.locked_label)
            self.locked_label.style().polish(self.locked_label)
            return
        locked = end_total - end_redeem
        if locked >= 0:
            self.locked_label.setText(f"{locked:.2f} SC")
            self.locked_label.setProperty("status", "neutral")
        else:
            self.locked_label.setText("— (redeemable > total)")
            self.locked_label.setProperty("status", "negative")
        self.locked_label.style().unpolish(self.locked_label)
        self.locked_label.style().polish(self.locked_label)

    def _update_pnl(self, start_redeem):
        try:
            end_redeem = float(self.end_redeem_edit.text().strip() or 0.0)
        except ValueError:
            self.pnl_label.setText("—")
            self.pnl_label.setProperty("status", "neutral")
            self.pnl_label.style().unpolish(self.pnl_label)
            self.pnl_label.style().polish(self.pnl_label)
            return
        change = end_redeem - float(start_redeem or 0.0)
        if change > 0:
            self.pnl_label.setText(f"+{change:.2f} SC")
            self.pnl_label.setProperty("status", "positive")
        elif change < 0:
            self.pnl_label.setText(f"{change:.2f} SC")
            self.pnl_label.setProperty("status", "negative")
        else:
            self.pnl_label.setText("0.00 SC")
            self.pnl_label.setProperty("status", "neutral")
        self.pnl_label.style().unpolish(self.pnl_label)
        self.pnl_label.style().polish(self.pnl_label)

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
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "End date is required.")
        else:
            try:
                parse_date_input(date_text)
                self._set_valid(self.date_edit)
            except ValueError:
                self._set_invalid(self.date_edit, "Enter a valid end date.")

        time_text = self.time_edit.text().strip()
        if not is_valid_time_24h(time_text, allow_blank=True):
            self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.time_edit)

        end_total_text = self.end_total_edit.text().strip()
        if not end_total_text:
            self._set_invalid(self.end_total_edit, "Ending Total SC is required.")
        else:
            valid, _result = validate_currency(end_total_text)
            if not valid:
                self._set_invalid(self.end_total_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.end_total_edit)

        end_redeem_text = self.end_redeem_edit.text().strip()
        if not end_redeem_text:
            self._set_invalid(self.end_redeem_edit, "Ending Redeemable is required.")
        else:
            valid, _result = validate_currency(end_redeem_text)
            if not valid:
                self._set_invalid(self.end_redeem_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.end_redeem_edit)

        wager_text = self.wager_edit.text().strip()
        if wager_text:
            valid, _result = validate_currency(wager_text)
            if not valid:
                self._set_invalid(self.wager_edit, "Enter a valid wager (max 2 decimals).")
            else:
                self._set_valid(self.wager_edit)
        else:
            self._set_valid(self.wager_edit)

    def collect_data(self):
        date_str = self.date_edit.text().strip()
        if not date_str:
            return None, "Please enter an end date."
        try:
            end_date = parse_date_input(date_str)
        except ValueError:
            return None, "Please enter a valid end date."

        time_str = self.time_edit.text().strip()
        if time_str and not is_valid_time_24h(time_str, allow_blank=False):
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            end_time = parse_time_input(time_str)
        except ValueError:
            return None, "Please enter a valid end time."

        end_total_str = self.end_total_edit.text().strip()
        if not end_total_str:
            return None, "Please enter Ending Total SC."
        valid, result = validate_currency(end_total_str)
        if not valid:
            return None, result
        end_total = result

        end_redeem_str = self.end_redeem_edit.text().strip()
        if not end_redeem_str:
            return None, "Please enter Ending Redeemable SC."
        valid, result = validate_currency(end_redeem_str)
        if not valid:
            return None, result
        end_redeem = result

        if end_redeem > end_total:
            return None, "Ending Redeemable SC cannot exceed Ending Total SC."

        wager_amount = None
        wager_str = self.wager_edit.text().strip()
        if wager_str:
            valid, result = validate_currency(wager_str)
            if not valid:
                return None, result
            wager_amount = result

        notes = self.notes_edit.toPlainText().strip()

        return {
            "end_date": end_date.strftime("%Y-%m-%d"),
            "end_time": end_time,
            "ending_total_sc": end_total,
            "ending_redeemable_sc": end_redeem,
            "wager_amount": wager_amount,
            "notes": notes,
        }, None


class GameSessionEditDialog(QtWidgets.QDialog):
    def __init__(
        self,
        db,
        session_mgr,
        user_names,
        site_names,
        game_types,
        game_names_by_type,
        session,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.session = session
        self.game_names_by_type = game_names_by_type or {}
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}
        self._game_type_lookup = {name.lower(): name for name in game_types}
        self.setWindowTitle("Edit Closed Session")
        self.resize(640, 640)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Session section
        session_group = QtWidgets.QGroupBox("Session")
        session_grid = QtWidgets.QGridLayout(session_group)
        session_grid.setHorizontalSpacing(10)
        session_grid.setVerticalSpacing(8)
        session_grid.setColumnStretch(1, 1)
        session_grid.setColumnStretch(3, 1)

        self.start_date_edit = QtWidgets.QLineEdit()
        self.start_date_edit.setPlaceholderText("MM/DD/YY")
        self.start_date_btn = QtWidgets.QPushButton("📅")
        self.start_date_btn.setFixedWidth(44)
        self.start_date_btn.clicked.connect(lambda: self._pick_date(self.start_date_edit))
        start_date_row = QtWidgets.QHBoxLayout()
        start_date_row.setSpacing(8)
        start_date_row.addWidget(self.start_date_edit, 1)
        start_date_row.addWidget(self.start_date_btn)

        self.start_time_edit = QtWidgets.QLineEdit()
        self.start_time_edit.setPlaceholderText("HH:MM")
        self.start_now_btn = QtWidgets.QPushButton("Now")
        self.start_now_btn.clicked.connect(lambda: self._set_now(self.start_time_edit))
        start_time_row = QtWidgets.QHBoxLayout()
        start_time_row.setSpacing(8)
        start_time_row.addWidget(self.start_time_edit, 1)
        start_time_row.addWidget(self.start_now_btn)

        self.end_date_edit = QtWidgets.QLineEdit()
        self.end_date_edit.setPlaceholderText("MM/DD/YY")
        self.end_date_btn = QtWidgets.QPushButton("📅")
        self.end_date_btn.setFixedWidth(44)
        self.end_date_btn.clicked.connect(lambda: self._pick_date(self.end_date_edit))
        end_date_row = QtWidgets.QHBoxLayout()
        end_date_row.setSpacing(8)
        end_date_row.addWidget(self.end_date_edit, 1)
        end_date_row.addWidget(self.end_date_btn)

        self.end_time_edit = QtWidgets.QLineEdit()
        self.end_time_edit.setPlaceholderText("HH:MM")
        self.end_now_btn = QtWidgets.QPushButton("Now")
        self.end_now_btn.clicked.connect(lambda: self._set_now(self.end_time_edit))
        end_time_row = QtWidgets.QHBoxLayout()
        end_time_row.setSpacing(8)
        end_time_row.addWidget(self.end_time_edit, 1)
        end_time_row.addWidget(self.end_now_btn)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(user_names)

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.addItems(site_names)

        session_grid.addWidget(QtWidgets.QLabel("Start Date"), 0, 0)
        session_grid.addLayout(start_date_row, 0, 1)
        session_grid.addWidget(QtWidgets.QLabel("End Date"), 0, 2)
        session_grid.addLayout(end_date_row, 0, 3)
        session_grid.addWidget(QtWidgets.QLabel("Start Time"), 1, 0)
        session_grid.addLayout(start_time_row, 1, 1)
        session_grid.addWidget(QtWidgets.QLabel("End Time"), 1, 2)
        session_grid.addLayout(end_time_row, 1, 3)
        session_grid.addWidget(QtWidgets.QLabel("Site"), 2, 0)
        session_grid.addWidget(self.site_combo, 2, 1)
        session_grid.addWidget(QtWidgets.QLabel("User"), 2, 2)
        session_grid.addWidget(self.user_combo, 2, 3)
        layout.addWidget(session_group)

        # Game section
        game_group = QtWidgets.QGroupBox("Game")
        game_grid = QtWidgets.QGridLayout(game_group)
        game_grid.setHorizontalSpacing(10)
        game_grid.setVerticalSpacing(8)
        game_grid.setColumnStretch(1, 1)
        game_grid.setColumnStretch(3, 1)

        self.game_type_combo = QtWidgets.QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QtWidgets.QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")

        self.rtp_tooltip = QtWidgets.QLabel("")
        self.rtp_tooltip.setObjectName("HelperText")
        self.rtp_tooltip.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.rtp_tooltip.setWordWrap(True)

        game_grid.addWidget(QtWidgets.QLabel("Game Type"), 0, 0)
        game_grid.addWidget(self.game_type_combo, 0, 1)
        game_grid.addWidget(QtWidgets.QLabel("Game Name"), 0, 2)
        game_grid.addWidget(self.game_name_combo, 0, 3)
        game_grid.addWidget(self.rtp_tooltip, 1, 0, 1, 4)
        layout.addWidget(game_group)

        # Balances section
        balance_group = QtWidgets.QGroupBox("Balances")
        balance_grid = QtWidgets.QGridLayout(balance_group)
        balance_grid.setHorizontalSpacing(10)
        balance_grid.setVerticalSpacing(8)
        balance_grid.setColumnStretch(1, 1)
        balance_grid.setColumnStretch(3, 1)

        self.start_total_edit = QtWidgets.QLineEdit()
        self.start_redeem_edit = QtWidgets.QLineEdit()
        self.end_total_edit = QtWidgets.QLineEdit()
        self.end_redeem_edit = QtWidgets.QLineEdit()
        self.wager_edit = QtWidgets.QLineEdit()

        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.balance_label = QtWidgets.QLabel("Balance Check")
        self.balance_label.setToolTip(balance_tooltip)
        self.balance_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.balance_value = QtWidgets.QLabel("—")
        self.balance_value.setWordWrap(True)
        self.balance_value.setObjectName("InfoField")
        self.balance_value.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.balance_value.setProperty("status", "neutral")
        self.balance_value.setToolTip(balance_tooltip)

        balance_grid.addWidget(QtWidgets.QLabel("Starting Total SC"), 0, 0)
        balance_grid.addWidget(self.start_total_edit, 0, 1)
        balance_grid.addWidget(QtWidgets.QLabel("Ending Total SC"), 0, 2)
        balance_grid.addWidget(self.end_total_edit, 0, 3)
        balance_grid.addWidget(QtWidgets.QLabel("Starting Redeemable"), 1, 0)
        balance_grid.addWidget(self.start_redeem_edit, 1, 1)
        balance_grid.addWidget(QtWidgets.QLabel("Ending Redeemable"), 1, 2)
        balance_grid.addWidget(self.end_redeem_edit, 1, 3)
        balance_grid.addWidget(QtWidgets.QLabel("Wager Amount"), 2, 0)
        balance_grid.addWidget(self.wager_edit, 2, 1)
        balance_grid.addWidget(self.balance_label, 3, 0)
        balance_grid.addWidget(self.balance_value, 3, 1, 1, 3)
        layout.addWidget(balance_group)

        # Notes section
        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_group)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save Changes")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self.reject)
        self.game_type_combo.currentTextChanged.connect(self._update_game_names)
        self.game_name_combo.currentTextChanged.connect(self._update_rtp_tooltip)
        self.site_combo.currentTextChanged.connect(self._update_balance_label)
        self.user_combo.currentTextChanged.connect(self._update_balance_label)
        self.start_total_edit.textChanged.connect(self._update_balance_label)
        self.start_date_edit.textChanged.connect(self._update_balance_label)
        self.start_time_edit.textChanged.connect(self._update_balance_label)
        self.game_type_combo.currentTextChanged.connect(self._validate_inline)
        self.game_name_combo.currentTextChanged.connect(self._validate_inline)
        self.start_date_edit.textChanged.connect(self._validate_inline)
        self.start_time_edit.textChanged.connect(self._validate_inline)
        self.end_date_edit.textChanged.connect(self._validate_inline)
        self.end_time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.start_total_edit.textChanged.connect(self._validate_inline)
        self.start_redeem_edit.textChanged.connect(self._validate_inline)
        self.end_total_edit.textChanged.connect(self._validate_inline)
        self.end_redeem_edit.textChanged.connect(self._validate_inline)
        self.wager_edit.textChanged.connect(self._validate_inline)

        self._load_session()
        self._update_completers()
        self._validate_inline()

    def _all_game_names(self):
        names = set()
        for game_list in self.game_names_by_type.values():
            names.update(game_list)
        return sorted(names)

    def _update_game_names(self):
        game_type = self.game_type_combo.currentText().strip()
        
        # If no game type or invalid, clear and show placeholder
        if not game_type:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return
        
        # Check if game type is valid
        if game_type.lower() not in self._game_type_lookup:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return
        
        # Game type is valid, populate names and remove placeholder
        type_key = None
        for key in self.game_names_by_type:
            if key.lower() == game_type.lower():
                type_key = key
                break
        names = list(self.game_names_by_type.get(type_key, [])) if type_key else []
        current = self.game_name_combo.currentText().strip()
        if "" not in names:
            names.insert(0, "")
        self.game_name_combo.blockSignals(True)
        self.game_name_combo.clear()
        self.game_name_combo.addItems(names)
        self.game_name_combo.lineEdit().setPlaceholderText("")  # Remove placeholder
        if current and current in names:
            self.game_name_combo.setCurrentText(current)
        else:
            self.game_name_combo.setCurrentIndex(0)
            self.game_name_combo.setEditText("")
        self.game_name_combo.blockSignals(False)
        self._update_completers()
        self._validate_inline()

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
        start_date_text = self.start_date_edit.text().strip()
        if not start_date_text:
            self._set_invalid(self.start_date_edit, "Start date is required.")
        else:
            try:
                parse_date_input(start_date_text)
                self._set_valid(self.start_date_edit)
            except ValueError:
                self._set_invalid(self.start_date_edit, "Enter a valid start date.")

        end_date_text = self.end_date_edit.text().strip()
        if not end_date_text:
            self._set_invalid(self.end_date_edit, "End date is required.")
        else:
            try:
                parse_date_input(end_date_text)
                self._set_valid(self.end_date_edit)
            except ValueError:
                self._set_invalid(self.end_date_edit, "Enter a valid end date.")

        start_time_text = self.start_time_edit.text().strip()
        if not is_valid_time_24h(start_time_text, allow_blank=True):
            self._set_invalid(self.start_time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.start_time_edit)

        end_time_text = self.end_time_edit.text().strip()
        if not is_valid_time_24h(end_time_text, allow_blank=True):
            self._set_invalid(self.end_time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.end_time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
        else:
            self._set_valid(self.site_combo)

        game_type_text = self.game_type_combo.currentText().strip()
        if game_type_text and game_type_text.lower() not in self._game_type_lookup:
            self._set_invalid(self.game_type_combo, "Select a valid Game Type.")
        else:
            self._set_valid(self.game_type_combo)

        game_name_text = self.game_name_combo.currentText().strip()
        if game_name_text:
            if not game_type_text:
                self._set_invalid(self.game_type_combo, "Select a Game Type for this Game Name.")
                self._set_invalid(self.game_name_combo, "Select a valid Game Name for the chosen type.")
            else:
                type_key = None
                for key in self.game_names_by_type:
                    if key.lower() == game_type_text.lower():
                        type_key = key
                        break
                valid_names = self.game_names_by_type.get(type_key, []) if type_key else []
                valid_lookup = {name.lower(): name for name in valid_names if name}
                if game_name_text.lower() not in valid_lookup:
                    self._set_invalid(self.game_name_combo, "Select a valid Game Name for the chosen type.")
                else:
                    self._set_valid(self.game_name_combo)
        else:
            self._set_valid(self.game_name_combo)

        start_total_text = self.start_total_edit.text().strip()
        if not start_total_text:
            self._set_invalid(self.start_total_edit, "Starting Total SC is required.")
        else:
            valid, _result = validate_currency(start_total_text)
            if not valid:
                self._set_invalid(self.start_total_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.start_total_edit)

        start_redeem_text = self.start_redeem_edit.text().strip()
        if not start_redeem_text:
            self._set_invalid(self.start_redeem_edit, "Starting Redeemable is required.")
        else:
            valid, _result = validate_currency(start_redeem_text)
            if not valid:
                self._set_invalid(self.start_redeem_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.start_redeem_edit)

        end_total_text = self.end_total_edit.text().strip()
        if not end_total_text:
            self._set_invalid(self.end_total_edit, "Ending Total SC is required.")
        else:
            valid, _result = validate_currency(end_total_text)
            if not valid:
                self._set_invalid(self.end_total_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.end_total_edit)

        end_redeem_text = self.end_redeem_edit.text().strip()
        if not end_redeem_text:
            self._set_invalid(self.end_redeem_edit, "Ending Redeemable is required.")
        else:
            valid, _result = validate_currency(end_redeem_text)
            if not valid:
                self._set_invalid(self.end_redeem_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.end_redeem_edit)

        wager_text = self.wager_edit.text().strip()
        if wager_text:
            valid, _result = validate_currency(wager_text)
            if not valid:
                self._set_invalid(self.wager_edit, "Enter a valid wager (max 2 decimals).")
            else:
                self._set_valid(self.wager_edit)
        else:
            self._set_valid(self.wager_edit)

    def _update_completers(self):
        for combo in (
            self.user_combo,
            self.site_combo,
            self.game_type_combo,
            self.game_name_combo,
        ):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _set_now(self, target_edit):
        target_edit.setText(datetime.now().strftime("%H:%M"))

    def _format_date_for_input(self, date_str):
        if not date_str:
            return ""
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return date_str

    def _format_time_for_input(self, time_str):
        if not time_str:
            return ""
        return time_str[:5]

    def _lookup_ids(self, site_name, user_name):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        conn.close()
        return (site_row["id"] if site_row else None, user_row["id"] if user_row else None)

    def _update_balance_label(self):
        if not self.session_mgr:
            return
        site_name = self.site_combo.currentText().strip()
        user_name = self.user_combo.currentText().strip()
        start_total_text = self.start_total_edit.text().strip()
        if not site_name or not user_name or not start_total_text:
            self.balance_value.setText("—")
            self.balance_value.setProperty("status", "neutral")
            self.balance_value.style().unpolish(self.balance_value)
            self.balance_value.style().polish(self.balance_value)
            return
        valid, result = validate_currency(start_total_text)
        if not valid:
            self.balance_value.setText("—")
            self.balance_value.setProperty("status", "neutral")
            self.balance_value.style().unpolish(self.balance_value)
            self.balance_value.style().polish(self.balance_value)
            return
        site_id, user_id = self._lookup_ids(site_name, user_name)
        if not site_id or not user_id:
            self.balance_value.setText("—")
            self.balance_value.setProperty("status", "neutral")
            self.balance_value.style().unpolish(self.balance_value)
            self.balance_value.style().polish(self.balance_value)
            return
        session_date = self.start_date_edit.text().strip() or None
        session_time = self.start_time_edit.text().strip() or None
        try:
            parsed_date = parse_date_input(session_date).strftime("%Y-%m-%d") if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.balance_value.setText("—")
            self.balance_value.setProperty("status", "neutral")
            self.balance_value.style().unpolish(self.balance_value)
            self.balance_value.style().polish(self.balance_value)
            return
        info = self.session_mgr.detect_freebies(
            site_id, user_id, result, parsed_date, parsed_time
        )
        expected_total = float(info.get("expected_total_sc", 0.0))
        freebies_sc = float(info.get("freebies_sc", 0.0))
        freebies_dollar = float(info.get("freebies_dollar", 0.0))
        missing_sc = float(info.get("missing_sc", 0.0))
        if freebies_sc > 0:
            self.balance_value.setProperty("status", "positive")
            self.balance_value.setText(
                f"+ Detected {freebies_sc:.2f} SC in extra balance (${freebies_dollar:.2f})"
            )
        elif missing_sc > 0:
            self.balance_value.setProperty("status", "negative")
            self.balance_value.setText(
                f"- WARNING: Starting balance is {missing_sc:.2f} SC less than expected ({expected_total:.2f})"
            )
        else:
            self.balance_value.setProperty("status", "neutral")
            self.balance_value.setText(f"Matches expected balance ({expected_total:.2f} SC)")
        self.balance_value.style().unpolish(self.balance_value)
        self.balance_value.style().polish(self.balance_value)

    def _update_rtp_tooltip(self):
        """Update the RTP tooltip with Expected and Actual RTP when a game is selected"""
        game_name = self.game_name_combo.currentText().strip()
        if not game_name:
            self.rtp_tooltip.setText("")
            return
        
        # Fetch game RTP info from database
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT rtp, actual_rtp FROM games WHERE name = ?
            """,
            (game_name,),
        )
        row = c.fetchone()
        conn.close()
        
        if row:
            exp_rtp = row['rtp']
            act_rtp = row['actual_rtp']
            
            exp_str = f"{exp_rtp:.2f}%" if exp_rtp is not None else "—"
            act_str = f"{act_rtp:.2f}%" if act_rtp is not None else "—"
            
            self.rtp_tooltip.setText(f"Exp RTP: {exp_str} / Act RTP: {act_str}")
        else:
            self.rtp_tooltip.setText("")

    def _load_session(self):
        self.start_date_edit.setText(self._format_date_for_input(self.session["session_date"]))
        self.start_time_edit.setText(self._format_time_for_input(self.session["start_time"]))
        end_date = self.session["end_date"] or self.session["session_date"]
        self.end_date_edit.setText(self._format_date_for_input(end_date))
        self.end_time_edit.setText(self._format_time_for_input(self.session["end_time"]))
        self.user_combo.setCurrentText(self.session["user_name"])
        self.site_combo.setCurrentText(self.session["site_name"])
        self.game_type_combo.blockSignals(True)
        if self.session["game_type"]:
            self.game_type_combo.setCurrentText(self.session["game_type"])
        self.game_type_combo.blockSignals(False)
        self.game_name_combo.blockSignals(True)
        if self.session["game_name"]:
            self.game_name_combo.setCurrentText(self.session["game_name"])
        self.game_name_combo.blockSignals(False)
        self._update_game_names()
        self.start_total_edit.setText(str(self.session["starting_sc_balance"]))
        start_redeem = (
            self.session["starting_redeemable_sc"]
            if self.session["starting_redeemable_sc"] is not None
            else self.session["starting_sc_balance"]
        )
        self.start_redeem_edit.setText(str(start_redeem))
        self.end_total_edit.setText(
            "" if self.session["ending_sc_balance"] is None else str(self.session["ending_sc_balance"])
        )
        end_redeem = (
            self.session["ending_redeemable_sc"]
            if self.session["ending_redeemable_sc"] is not None
            else self.session["ending_sc_balance"]
        )
        self.end_redeem_edit.setText("" if end_redeem is None else str(end_redeem))
        self.wager_edit.setText(
            "" if self.session["wager_amount"] is None else str(self.session["wager_amount"])
        )
        self.notes_edit.setPlainText(self.session["notes"] or "")
        self._update_balance_label()
        self._update_rtp_tooltip()

    def collect_data(self):
        start_date_str = self.start_date_edit.text().strip()
        end_date_str = self.end_date_edit.text().strip()
        if not start_date_str or not end_date_str:
            return None, "Please enter both start and end dates."
        try:
            start_date = parse_date_input(start_date_str)
            end_date = parse_date_input(end_date_str)
        except ValueError:
            return None, "Please enter valid start/end dates."

        try:
            start_time_str = self.start_time_edit.text().strip()
            end_time_str = self.end_time_edit.text().strip()
            if start_time_str and not is_valid_time_24h(start_time_str, allow_blank=False):
                return None, "Please enter a valid start time (HH:MM or HH:MM:SS, 24-hour)."
            if end_time_str and not is_valid_time_24h(end_time_str, allow_blank=False):
                return None, "Please enter a valid end time (HH:MM or HH:MM:SS, 24-hour)."
            start_time = parse_time_input(start_time_str)
            end_time = parse_time_input(end_time_str)
        except ValueError:
            return None, "Please enter valid start/end times."

        user_name = self.user_combo.currentText().strip()
        site_name = self.site_combo.currentText().strip()
        game_type = self.game_type_combo.currentText().strip()
        game_name = self.game_name_combo.currentText().strip()
        if not user_name or not site_name:
            return None, "Please select User and Site."
        if game_name and not game_type:
            return None, "Please select a Game Type when entering a Game Name."

        valid, result = validate_currency(self.start_total_edit.text().strip() or "")
        if not valid:
            return None, result
        start_total = result

        valid, result = validate_currency(self.start_redeem_edit.text().strip() or "")
        if not valid:
            return None, result
        start_redeem = result

        valid, result = validate_currency(self.end_total_edit.text().strip() or "")
        if not valid:
            return None, result
        end_total = result

        valid, result = validate_currency(self.end_redeem_edit.text().strip() or "")
        if not valid:
            return None, result
        end_redeem = result

        if start_redeem > start_total:
            return None, "Starting Redeemable SC cannot exceed Starting Total SC."
        if end_redeem > end_total:
            return None, "Ending Redeemable SC cannot exceed Ending Total SC."

        wager_str = self.wager_edit.text().strip()
        wager_amount = None
        if wager_str:
            valid, result = validate_currency(wager_str)
            if valid:
                wager_amount = float(result)

        notes = self.notes_edit.toPlainText().strip()

        return {
            "session_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "start_time": start_time,
            "end_time": end_time,
            "user_name": user_name,
            "site_name": site_name,
            "game_type": game_type,
            "game_name": game_name,
            "wager_amount": wager_amount,
            "starting_total_sc": start_total,
            "starting_redeemable_sc": start_redeem,
            "ending_total_sc": end_total,
            "ending_redeemable_sc": end_redeem,
            "notes": notes,
        }, None


class DailySessionNotesDialog(QtWidgets.QDialog):
    def __init__(self, session_date, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Daily Session Notes - {session_date}")
        self.resize(520, 360)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel(f"Notes for {session_date}")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlainText(notes or "")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 6 + 18)
        layout.addWidget(self.notes_edit, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)

    def notes_text(self):
        return self.notes_edit.toPlainText().strip()


class GameSessionViewDialog(QtWidgets.QDialog):
    def __init__(self, session, parent=None, on_open_session=None, on_open_purchase=None, on_open_redemption=None, on_edit=None, on_delete=None, on_view_in_daily=None):
        super().__init__(parent)
        self.session = session
        self._on_open_session = on_open_session
        self.on_open_purchase = on_open_purchase
        self.on_open_redemption = on_open_redemption
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_view_in_daily = on_view_in_daily
        self.setWindowTitle("View Game Session")
        self.resize(750, 650)

        # Fetch linked purchases and redemptions
        from database import Database
        from business_logic import FIFOCalculator, SessionManager
        self.db = Database()
        fifo = FIFOCalculator(self.db)
        self.session_manager = SessionManager(self.db, fifo)
        
        # Get links for this session
        links = self.session_manager.get_links_for_session(session["id"])
        self.linked_purchases = links.get("purchases", []) if links else []
        self.linked_redemptions = links.get("redemptions", []) if links else []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Create tab widget
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_details_tab(), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()

        # Check if session is active (status is None or "Active")
        status = session["status"] if "status" in session.keys() else None
        is_active = not status or status == "Active"

        if is_active:
            end_session_btn = QtWidgets.QPushButton("End Session")
            end_session_btn.setObjectName("PrimaryButton")
            btn_row.addWidget(end_session_btn)

        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)

        btn_row.addStretch(1)
        
        view_daily_btn = None
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        if self._on_view_in_daily and not is_active:
            # Only show for closed sessions
            view_daily_btn = QtWidgets.QPushButton("View in Daily Sessions")
            btn_row.addWidget(view_daily_btn)
        if self._on_open_session:
            open_btn = QtWidgets.QPushButton("View in Game Sessions")
            btn_row.addWidget(open_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if is_active:
            end_session_btn.clicked.connect(self._handle_end_session)
        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        if view_daily_btn:
            view_daily_btn.clicked.connect(self._handle_view_in_daily)
        if self._on_open_session:
            open_btn.clicked.connect(self._handle_open_session)
        close_btn.clicked.connect(self.accept)

    def _format_date(self, value):
        """Helper to format date strings to MM/DD/YY"""
        if not value:
            return "—"
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return value

    def _create_details_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        def build_group(title):
            group = QtWidgets.QGroupBox(title)
            group_layout = QtWidgets.QGridLayout(group)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(8)
            group_layout.setColumnStretch(1, 1)
            group_layout.setColumnStretch(3, 1)
            return group, group_layout

        def add_pair(grid, row, col, label_text, value):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            grid.addWidget(label, row, col * 2)
            grid.addWidget(value_label, row, col * 2 + 1)

        def format_time(value):
            return value[:5] if value else "—"

        def format_dt(date_value, time_value):
            if not date_value and not time_value:
                return "—"
            date_part = self._format_date(date_value)
            time_part = format_time(time_value)
            if date_part == "—":
                return time_part
            if time_part == "—":
                return date_part
            return f"{date_part} {time_part}"

        def format_sc(value):
            return f"{float(value):.2f}" if value is not None else "—"

        def format_delta(value):
            if value is None:
                return "—"
            return f"{float(value):+.2f}"

        wager_display = format_currency(self.session["wager_amount"]) if self.session["wager_amount"] else "—"
        rtp_display = f"{float(self.session['rtp']):.2f}%" if self.session["rtp"] is not None else "—"
        start_total = self.session["starting_sc_balance"]
        end_total = self.session["ending_sc_balance"]
        start_redeem = (
            self.session["starting_redeemable_sc"]
            if self.session["starting_redeemable_sc"] is not None
            else self.session["starting_sc_balance"]
        )
        end_redeem = (
            self.session["ending_redeemable_sc"]
            if self.session["ending_redeemable_sc"] is not None
            else self.session["ending_sc_balance"]
        )
        delta_total = self.session["delta_total"]
        if delta_total is None and start_total is not None and end_total is not None:
            delta_total = float(end_total or 0) - float(start_total or 0)
        delta_redeem = self.session["delta_redeem"]
        if delta_redeem is None and start_redeem is not None and end_redeem is not None:
            delta_redeem = float(end_redeem or 0) - float(start_redeem or 0)
        basis_val = (
            self.session["basis_consumed"]
            if self.session["basis_consumed"] is not None
            else self.session["session_basis"]
        )
        net_val = self.session["net_taxable_pl"]
        if net_val is None:
            net_val = self.session["total_taxable"] if self.session["total_taxable"] is not None else 0.0
        net_display = f"+${float(net_val):.2f}" if float(net_val) >= 0 else f"${float(net_val):.2f}"

        session_group, session_grid = build_group("Session")
        add_pair(
            session_grid,
            0,
            0,
            "Start",
            format_dt(self.session["session_date"], self.session["start_time"]),
        )
        add_pair(
            session_grid,
            0,
            1,
            "End",
            format_dt(self.session["end_date"], self.session["end_time"]),
        )
        add_pair(session_grid, 1, 0, "Site", self.session["site_name"] or "—")
        add_pair(session_grid, 1, 1, "User", self.session["user_name"] or "—")
        add_pair(session_grid, 2, 0, "Status", self.session["status"] or "Active")
        layout.addWidget(session_group)

        game_group, game_grid = build_group("Game")
        add_pair(game_grid, 0, 0, "Game Type", self.session["game_type"] or "—")
        add_pair(game_grid, 0, 1, "Game Name", self.session["game_name"] or "—")
        add_pair(game_grid, 1, 0, "Wager Amount", wager_display)
        add_pair(game_grid, 1, 1, "RTP", rtp_display)
        layout.addWidget(game_group)

        balance_group, balance_grid = build_group("Balances")
        add_pair(balance_grid, 0, 0, "Start SC", format_sc(start_total))
        add_pair(balance_grid, 0, 1, "End SC", format_sc(end_total))
        add_pair(balance_grid, 1, 0, "Start Redeem", format_sc(start_redeem))
        add_pair(balance_grid, 1, 1, "End Redeem", format_sc(end_redeem))
        add_pair(balance_grid, 2, 0, "Δ Total", format_delta(delta_total))
        add_pair(balance_grid, 2, 1, "Δ Redeem", format_delta(delta_redeem))
        add_pair(
            balance_grid,
            3,
            0,
            "Δ Basis",
            format_currency(basis_val) if basis_val is not None else "—",
        )
        add_pair(balance_grid, 3, 1, "Net P/L", net_display if net_val is not None else "—")
        layout.addWidget(balance_group)

        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        notes_value = self.session["notes"] or ""
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 16)
            notes_layout.addWidget(notes_edit)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            notes_layout.addWidget(notes_field)
        layout.addWidget(notes_group)
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Purchases Contributing to Basis (Before/During)
        purchases_group = QtWidgets.QGroupBox("Purchases Contributing to Basis (Before/During)")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        
        # Filter for BEFORE, DURING, MANUAL relations only
        before_during_purchases = [p for p in self.linked_purchases if p["relation"] in ('BEFORE', 'DURING', 'MANUAL')]
        
        if not before_during_purchases:
            note = QtWidgets.QLabel("No purchases contributed basis before or during this session.")
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.purchases_table = QtWidgets.QTableWidget(0, 5)
            self.purchases_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Amount", "SC Received", "View"]
            )
            self.purchases_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.purchases_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.purchases_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.purchases_table.setAlternatingRowColors(True)
            self.purchases_table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            header = self.purchases_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.purchases_table.verticalHeader().setVisible(False)
            self.purchases_table.setColumnWidth(0, 90)
            self.purchases_table.setColumnWidth(1, 60)
            self.purchases_table.setColumnWidth(2, 90)
            self.purchases_table.setColumnWidth(3, 90)
            self.purchases_table.setColumnWidth(4, 70)
            purchases_layout.addWidget(self.purchases_table)
            self._populate_purchases_table(before_during_purchases)

        layout.addWidget(purchases_group, 1)

        # Redemptions Affecting This Session
        redemptions_group = QtWidgets.QGroupBox("Redemptions Affecting This Session")
        redemptions_layout = QtWidgets.QVBoxLayout(redemptions_group)
        redemptions_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.linked_redemptions:
            note = QtWidgets.QLabel("No redemptions affected this session.")
            note.setWordWrap(True)
            redemptions_layout.addWidget(note)
        else:
            self.redemptions_table = QtWidgets.QTableWidget(0, 4)
            self.redemptions_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Amount", "View"]
            )
            self.redemptions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.redemptions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.redemptions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.redemptions_table.setAlternatingRowColors(True)
            self.redemptions_table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            header = self.redemptions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.redemptions_table.verticalHeader().setVisible(False)
            self.redemptions_table.setColumnWidth(0, 90)
            self.redemptions_table.setColumnWidth(1, 60)
            self.redemptions_table.setColumnWidth(2, 100)
            self.redemptions_table.setColumnWidth(3, 70)
            redemptions_layout.addWidget(self.redemptions_table)
            self._populate_redemptions_table()

        layout.addWidget(redemptions_group, 1)
        return widget

    def _populate_purchases_table(self, purchases):
        self.purchases_table.setRowCount(len(purchases))
        for row_idx, purchase in enumerate(purchases):
            date_display = self._format_date(purchase["purchase_date"]) if purchase["purchase_date"] else "—"
            time_display = purchase["purchase_time"][:5] if purchase["purchase_time"] else "—"
            amount = format_currency(purchase["amount"])
            sc_received = f"{float(purchase['sc_received'] or 0.0):.2f}"

            values = [date_display, time_display, amount, sc_received]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (2, 3):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.purchases_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase["id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.purchases_table.setCellWidget(row_idx, 4, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self):
        # Show all redemptions (DURING, AFTER, MANUAL)
        filtered_redemptions = self.linked_redemptions
        
        self.redemptions_table.setRowCount(len(filtered_redemptions))
        for row_idx, redemption in enumerate(filtered_redemptions):
            date_display = self._format_date(redemption["redemption_date"]) if redemption["redemption_date"] else "—"
            time_display = redemption["redemption_time"][:5] if redemption["redemption_time"] else "—"
            amount = format_currency(redemption["amount"])

            values = [date_display, time_display, amount]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx == 2:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.redemptions_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, rid=redemption["id"]: self._open_redemption(rid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QHBoxLayout(view_container)
            view_layout.setContentsMargins(0, 2, 0, 2)
            view_layout.addStretch(1)
            view_layout.addWidget(view_btn)
            view_layout.addStretch(1)
            self.redemptions_table.setCellWidget(row_idx, 3, view_container)
            self.redemptions_table.setRowHeight(
                row_idx,
                max(self.redemptions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_redemption(self, redemption_id):
        if not self.on_open_redemption:
            QtWidgets.QMessageBox.information(
                self, "Redemptions Unavailable", "Redemption view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_redemption(redemption_id))

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_open_session(self):
        if self._on_open_session:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_open_session)
            return
        self.accept()

    def _handle_view_in_daily(self):
        if self._on_view_in_daily:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_view_in_daily)

    def _handle_end_session(self):
        """Open the End Session dialog for this active session"""
        parent = self.parent()
        if not parent or not hasattr(parent, 'db') or not hasattr(parent, 'session_mgr'):
            QtWidgets.QMessageBox.warning(self, "Error", "Cannot end session: parent context not available.")
            return

        # Close this view dialog
        self.accept()

        # Open the End Session dialog
        session_id = self.session["id"]
        dialog = GameSessionEndDialog(self.session, parent)

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QtWidgets.QMessageBox.warning(parent, "Invalid Entry", error)
                return
            try:
                pnl = parent.session_mgr.end_game_session(
                    session_id,
                    data["ending_total_sc"],
                    data["ending_redeemable_sc"],
                    notes=data["notes"] or None,
                    end_date=data["end_date"],
                    end_time=data["end_time"],
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(parent, "Error", f"Failed to end session: {exc}")
                return

            if data.get("wager_amount") is not None:
                conn = parent.db.get_connection()
                c = conn.cursor()
                c.execute(
                    "UPDATE game_sessions SET wager_amount = ? WHERE id = ?",
                    (data["wager_amount"], session_id),
                )
                conn.commit()
                conn.close()

            dialog.accept()
            if hasattr(parent, 'load_data'):
                parent.load_data()
            if hasattr(parent, 'on_data_changed') and parent.on_data_changed:
                parent.on_data_changed()
            if pnl >= 0:
                message = f"Session ended!\n\nProfit: +${pnl:.2f}"
            else:
                message = f"Session ended!\n\nLoss: ${pnl:.2f}"
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(parent, "Success", message)
            )

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()


class StatsBar(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatsBar")
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(18)

        self.invested_label = QtWidgets.QLabel("Invested: $0.00")
        self.redeemed_label = QtWidgets.QLabel("Redeemed: $0.00")
        self.net_label = QtWidgets.QLabel("Net Cash: $0.00")
        self.unrealized_label = QtWidgets.QLabel("Unrealized: $0.00")
        self.sessions_label = QtWidgets.QLabel("Sessions: 0")

        for label in (
            self.invested_label,
            self.redeemed_label,
            self.net_label,
            self.unrealized_label,
            self.sessions_label,
        ):
            label.setMinimumWidth(0)
            label.setObjectName("StatsLabel")
            label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
            layout.addWidget(label)
        layout.addStretch(1)

    def set_stats(self, stats):
        self.invested_label.setText(f"Invested: {format_currency(stats.get('invested', 0))}")
        self.redeemed_label.setText(f"Redeemed: {format_currency(stats.get('redeemed', 0))}")
        self.net_label.setText(f"Net Cash: {format_currency(stats.get('net_cash', 0))}")
        self.unrealized_label.setText(f"Unrealized: {format_currency(stats.get('unrealized', 0))}")
        self.sessions_label.setText(f"Sessions: {stats.get('sessions', 0)}")


class PurchasesTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr, on_data_changed=None, main_window=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.main_window = main_window
        self.all_rows = []
        self.filtered_rows = []
        self.header_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self.active_date_filter = (None, None)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QtWidgets.QPushButton("Add Purchase")
        self.view_btn = QtWidgets.QPushButton("View Purchase")
        self.edit_btn = QtWidgets.QPushButton("Edit Purchase")
        self.delete_btn = QtWidgets.QPushButton("Delete Purchase")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.add_btn.setObjectName("PrimaryButton")
        self.view_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.view_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search purchases...")
        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Date/Time",
                "User",
                "Site",
                "Amount",
                "SC Received",
                "Starting SC",
                "Card",
                "Cashback",
                "Remaining",
                "Notes",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_selected)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

        self.add_btn.clicked.connect(self._add_purchase)
        self.view_btn.clicked.connect(self._view_selected)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn.clicked.connect(self.export_csv)
        self.refresh_btn.clicked.connect(self.load_data)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))

        self._update_action_visibility()
        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT p.id, p.purchase_date, p.purchase_time, s.name as site, u.name as user_name,
                   p.amount, p.sc_received, p.starting_sc_balance, ca.name as card_name,
                   p.cashback_earned, p.remaining_amount, p.notes
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            JOIN cards ca ON p.card_id = ca.id
            ORDER BY p.purchase_date DESC, p.purchase_time DESC
            """
        )
        self.all_rows = []
        for row in c.fetchall():
            time_value = row["purchase_time"] or "00:00:00"
            dt_value = None
            try:
                dt_value = datetime.strptime(
                    f"{row['purchase_date']} {time_value}", "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                dt_value = None
            display = [
                format_date_time(row["purchase_date"], time_value),
                row["user_name"],
                row["site"],
                format_currency(row["amount"]),
                f"{float(row['sc_received'] or 0):.2f}",
                f"{float(row['starting_sc_balance'] or 0):.2f}",
                row["card_name"],
                format_currency(row["cashback_earned"] or 0.0),
                format_currency(row["remaining_amount"]),
                row["notes"] or "",
            ]
            self.all_rows.append(
                {
                    "id": row["id"],
                    "purchase_date": row["purchase_date"],
                    "purchase_time": time_value,
                    "purchase_dt": dt_value,
                    "user_name": row["user_name"],
                    "site": row["site"],
                    "amount": float(row["amount"] or 0),
                    "sc_received": float(row["sc_received"] or 0),
                    "starting_sc_balance": float(row["starting_sc_balance"] or 0),
                    "card_name": row["card_name"],
                    "cashback_earned": float(row["cashback_earned"] or 0.0),
                    "remaining_amount": float(row["remaining_amount"] or 0),
                    "notes": row["notes"] or "",
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.apply_filters()

    def apply_filters(self):
        rows = self._filter_rows()
        rows = self.sort_rows(rows)
        self.filtered_rows = rows
        self.refresh_table(rows)

    def _filter_rows(self, exclude_col=None):
        rows = list(self.all_rows)
        start_date, end_date = self.active_date_filter
        if start_date:
            rows = [r for r in rows if r["purchase_date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["purchase_date"] <= end_date]

        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in rows if term in r["search_blob"]]

        for col, values in self.header_filters.items():
            if col == exclude_col:
                continue
            if values:
                rows = [r for r in rows if r["display"][col] in values]
        return rows

    def refresh_table(self, rows):
        numeric_cols = {3, 4, 5, 7}
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in numeric_cols:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, row["id"])
                self.table.setItem(r_idx, c_idx, item)
        self._update_action_visibility()

    def eventFilter(self, obj, event):
        if getattr(self, "header", None) and obj is self.header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(self.header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(self.header, pos) is not None:
                    return False
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _update_action_visibility(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        self.view_btn.setVisible(len(selected) == 1)
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_visibility()

    def sort_rows(self, rows):
        if self.sort_column is None:
            return rows
        reverse = self.sort_order == QtCore.Qt.DescendingOrder

        def sort_key(row):
            col = self.sort_column
            if col == 0:
                return row["purchase_dt"] or datetime.min
            if col == 1:
                return row["user_name"].lower()
            if col == 2:
                return row["site"].lower()
            if col == 3:
                return row["amount"]
            if col == 4:
                return row["sc_received"]
            if col == 5:
                return row["starting_sc_balance"]
            if col == 6:
                return row["card_name"].lower()
            if col == 7:
                return row["remaining_amount"]
            if col == 8:
                return row["notes"].lower()
            return row["display"][col]

        return sorted(rows, key=sort_key, reverse=reverse)

    def _show_header_menu(self, col_index):
        header = self.table.horizontalHeader()
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        pos_x = header.sectionPosition(col_index)
        pos = header.mapToGlobal(QtCore.QPoint(pos_x, header.height()))
        action = menu.exec(pos)
        if action == sort_asc:
            self.set_sort(col_index, QtCore.Qt.AscendingOrder)
        elif action == sort_desc:
            self.set_sort(col_index, QtCore.Qt.DescendingOrder)
        elif action == clear_sort:
            self.clear_sort()
        elif action == filter_action:
            filter_rows = self._filter_rows(exclude_col=col_index)
            values = sorted({r["display"][col_index] for r in filter_rows})
            selected = self.header_filters.get(col_index, set())
            if col_index == 0:
                dialog = DateTimeFilterDialog(values, selected, self)
            else:
                dialog = ColumnFilterDialog(values, selected, self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                selected_values = dialog.selected_values()
                if selected_values:
                    self.header_filters[col_index] = selected_values
                else:
                    self.header_filters.pop(col_index, None)
                self.apply_filters()

    def set_sort(self, column, order):
        self.sort_column = column
        self.sort_order = order
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self.apply_filters()

    def clear_sort(self):
        self.sort_column = None
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        self.apply_filters()

    def clear_all_filters(self):
        self.header_filters = {}
        self.search_edit.clear()
        self.clear_sort()
        self.clear_date_filter()
        self._clear_selection()

    def apply_date_filter(self):
        from_text = self.from_edit.text().strip()
        to_text = self.to_edit.text().strip()
        start_date = None
        end_date = None
        try:
            if from_text:
                start_date = parse_date_input(from_text).strftime("%Y-%m-%d")
            if to_text:
                end_date = parse_date_input(to_text).strftime("%Y-%m-%d")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Date", "Please enter a valid date.")
            return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (start_date, end_date)
        self.apply_filters()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.apply_filters()

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            self.clear_date_filter()
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.apply_filters()

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _fetch_lookup_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        sites = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM cards WHERE active = 1 ORDER BY name")
        cards = [r["name"] for r in c.fetchall()]
        conn.close()
        return users, sites, cards

    def _add_purchase(self):
        users, sites, cards = self._fetch_lookup_data()
        dialog = PurchaseDialog(self.db, users, sites, cards, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, None)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _edit_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a purchase to edit.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Multiple Selection",
                "Please select only one purchase to edit.",
            )
            return
        self.edit_purchase_by_id(selected_ids[0])

    def edit_purchase_by_id(self, purchase_id):
        purchase = self._fetch_purchase(purchase_id)
        if not purchase:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected purchase was not found.")
            return
        users, sites, cards = self._fetch_lookup_data()
        dialog = PurchaseDialog(self.db, users, sites, cards, purchase=purchase, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, purchase_id)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _view_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a purchase to view.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Multiple Selection",
                "Please select only one purchase to view.",
            )
            return
        purchase_id = selected_ids[0]
        purchase = self._fetch_purchase(purchase_id)
        if not purchase:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected purchase was not found.")
            return
        dialog = PurchaseViewDialog(
            purchase,
            parent=self,
            on_edit=lambda: self.edit_purchase_by_id(purchase_id),
            on_delete=lambda: self._delete_purchase_by_id(purchase_id),
            on_open_session=self.main_window.open_game_session if self.main_window else None,
            on_open_redemption=self.main_window.open_redemption if self.main_window else None
        )
        dialog.exec()

    def _save_from_dialog(self, dialog, purchase_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return
        ok, message_or_id = self._save_purchase_record(data, purchase_id)
        if not ok:
            # Check if this is a site/user change error with allocations
            if "Cannot change site or user" in message_or_id and purchase_id:
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Force Change?",
                    f"{message_or_id}\n\n"
                    "Do you want to FORCE this change?\n\n"
                    "This will:\n"
                    "• Delete existing redemption allocations for this purchase\n"
                    "• Make the change\n"
                    "• Recalculate FIFO for affected users\n\n"
                    "Continue?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    ok, message_or_id = self._save_purchase_record(data, purchase_id, force_site_user_change=True)
                    if not ok:
                        QtWidgets.QMessageBox.warning(self, "Error", message_or_id)
                        return
                else:
                    return
            else:
                QtWidgets.QMessageBox.warning(self, "Error", message_or_id)
                return

        # Extract message and purchase_id from return value
        if isinstance(message_or_id, tuple):
            message, new_purchase_id = message_or_id
        else:
            message = message_or_id
            new_purchase_id = purchase_id

        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        # Only show start session prompt for new purchases (not edits)
        # Use 100ms delay to ensure purchase transaction is fully committed and visible
        # to subsequent database connections (prevents "detected extra SC" false positive)
        if purchase_id is None and new_purchase_id:
            QtCore.QTimer.singleShot(100, lambda: self._prompt_start_session(new_purchase_id, message))
        else:
            QtCore.QTimer.singleShot(0, lambda: self._show_info_message("Success", message))

    def _prompt_start_session(self, purchase_id, success_message):
        """Show dialog asking if user wants to start a session with this purchase"""
        from datetime import datetime, timedelta

        # Create custom dialog with checkbox
        prompt_dialog = QtWidgets.QDialog(self)
        prompt_dialog.setWindowTitle("Purchase Saved")
        prompt_dialog.resize(400, 150)

        layout = QtWidgets.QVBoxLayout(prompt_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Success message
        success_label = QtWidgets.QLabel(success_message)
        success_label.setWordWrap(True)
        layout.addWidget(success_label)

        # Checkbox
        start_session_cb = QtWidgets.QCheckBox("Start a gaming session now with this purchase?")
        start_session_cb.setChecked(False)
        layout.addWidget(start_session_cb)

        # Button
        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(prompt_dialog.accept)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        # Show dialog
        prompt_dialog.exec()

        # If checkbox was checked, open session dialog
        if start_session_cb.isChecked():
            # Fetch purchase data
            purchase = self._fetch_purchase(purchase_id)
            if not purchase:
                QtWidgets.QMessageBox.warning(self, "Error", "Could not load purchase data")
                return

            # Calculate starting SC: starting_sc_balance + sc_received
            starting_total_sc = float(purchase["starting_sc_balance"] or 0.0) + float(purchase["sc_received"] or 0.0)

            # Calculate session start time (purchase_time + 1 second)
            purchase_time_str = purchase["purchase_time"] or "00:00:00"
            try:
                purchase_time = datetime.strptime(purchase_time_str, "%H:%M:%S")
                session_time = purchase_time + timedelta(seconds=1)
                session_time_str = session_time.strftime("%H:%M:%S")
            except:
                session_time_str = purchase_time_str

            # Open Start Session dialog with pre-filled data
            self._open_start_session_from_purchase(
                purchase["purchase_date"],
                session_time_str,
                purchase["site_name"],
                purchase["user_name"],
                starting_total_sc
            )

    def _open_start_session_from_purchase(self, session_date, session_time, site_name, user_name, starting_total_sc):
        """Open the Start Session dialog with pre-filled values from a purchase"""
        from datetime import datetime

        # Fetch lookup data for the session dialog
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        sites = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM game_types WHERE active = 1 ORDER BY name")
        game_types = [r["name"] for r in c.fetchall()]
        c.execute(
            """
            SELECT g.name as game_name, gt.name as type_name
            FROM games g
            LEFT JOIN game_types gt ON g.game_type_id = gt.id
            WHERE g.active = 1
            ORDER BY g.name
            """
        )
        game_names_by_type = {}
        for row in c.fetchall():
            type_name = row["type_name"] or "Other"
            game_names_by_type.setdefault(type_name, []).append(row["game_name"])
        conn.close()

        # Create the dialog
        dialog = GameSessionStartDialog(
            self.db,
            self.session_mgr,
            users,
            sites,
            game_types,
            game_names_by_type,
            parent=self,
        )

        # Pre-fill the fields
        dialog.date_edit.setText(dialog._format_date_for_input(session_date))
        # Set time directly without truncating seconds (needed for purchase -> session flow)
        dialog.time_edit.setText(session_time if len(session_time) == 8 else session_time + ":00")
        dialog.site_combo.setCurrentText(site_name)
        dialog.user_combo.setCurrentText(user_name)
        dialog.start_total_edit.setText(str(starting_total_sc))
        # Leave start_redeem_edit empty so user can enter it manually

        # Connect save button - use GameSessionsTab's existing save method
        def handle_save():
            # Get the GameSessionsTab from the main window
            main_window = self.window()
            if hasattr(main_window, 'game_sessions_tab'):
                # Save the session
                main_window.game_sessions_tab._save_start_session(dialog, None)

                # Navigate to Game Sessions tab and highlight the new session
                # The session was just created, so it should be the most recent active session
                QtCore.QTimer.singleShot(100, lambda: self._navigate_to_game_sessions(main_window))

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _navigate_to_game_sessions(self, main_window):
        """Navigate to Game Sessions tab and highlight the most recent session"""
        # Switch to Game Sessions tab
        if hasattr(main_window, 'stacked') and hasattr(main_window, 'tab_group'):
            # Find the Game Sessions tab index (it's tab #2: Purchases, Redemptions, Game Sessions...)
            game_sessions_index = 2
            button = main_window.tab_group.button(game_sessions_index)
            if button:
                button.setChecked(True)
                main_window.stacked.setCurrentIndex(game_sessions_index)

                # Highlight the most recent session (first row)
                QtCore.QTimer.singleShot(50, lambda: self._highlight_first_session(main_window))

    def _highlight_first_session(self, main_window):
        """Highlight the first row in the Game Sessions table (most recent session)"""
        if hasattr(main_window, 'game_sessions_tab'):
            table = main_window.game_sessions_tab.table
            if table.rowCount() > 0:
                table.selectRow(0)
                table.scrollToTop()

    def _fetch_purchase(self, purchase_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT p.*, s.name as site_name, ca.name as card_name, u.name as user_name
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN cards ca ON p.card_id = ca.id
            JOIN users u ON p.user_id = u.id
            WHERE p.id = ?
            """,
            (purchase_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def _save_purchase_record(self, data, purchase_id, force_site_user_change=False):
        user_name = data["user_name"]
        site_name = data["site_name"]
        card_name = data["card_name"]
        pdate = data["purchase_date"]
        ptime = data["purchase_time"]
        amount = data["amount"]
        sc_received = data["sc_received"]
        start_sc = data["starting_sc_balance"]
        # Ensure cashback is rounded to 2 decimal places before saving
        cashback_earned = round(float(data.get("cashback_earned", 0.0)), 2)
        notes = data["notes"]

        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            return False, f"User '{user_name}' not found."
        user_id = user_row["id"]

        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        if not site_row:
            conn.close()
            return False, f"Site '{site_name}' not found."
        site_id = site_row["id"]

        # Map display name back to actual card name if needed
        if hasattr(self, '_card_name_map') and card_name.lower() in self._card_name_map:
            actual_card_name = self._card_name_map[card_name.lower()]
        else:
            actual_card_name = card_name
        c.execute("SELECT id FROM cards WHERE name = ? AND user_id = ?", (actual_card_name, user_id))
        card_row = c.fetchone()
        if not card_row:
            conn.close()
            return (
                False,
                f"Card '{card_name}' not found for user '{user_name}'.",
            )
        card_id = card_row["id"]

        if purchase_id:
            c.execute(
                "SELECT amount, remaining_amount, site_id, user_id, purchase_date, purchase_time FROM purchases WHERE id = ?",
                (purchase_id,),
            )
            old_purchase = c.fetchone()
            if not old_purchase:
                conn.close()
                return False, "Purchase was not found."
            old_amount = float(old_purchase["amount"] or 0)
            old_remaining = float(old_purchase["remaining_amount"] or 0)
            old_site_id = old_purchase["site_id"]
            old_user_id = old_purchase["user_id"]
            old_date = old_purchase["purchase_date"]
            old_time = old_purchase["purchase_time"] or "00:00:00"
            consumed = old_amount - old_remaining

            if consumed > 0:
                if old_amount != amount:
                    conn.close()
                    return (
                        False,
                        f"Cannot change amount - ${consumed:.2f} has been used for redemptions.",
                    )
                if old_site_id != site_id or old_user_id != user_id:
                    if not force_site_user_change:
                        conn.close()
                        return (
                            False,
                            f"Cannot change site or user - ${consumed:.2f} has been used for redemptions.",
                        )
                    # Force change requested - delete allocations for this purchase
                    c.execute("DELETE FROM redemption_allocations WHERE purchase_id = ?", (purchase_id,))
                    # Mark purchase as having no remaining amount initially (will be reset after update)
                    consumed = 0  # Reset consumed to 0 since we deleted allocations

            new_remaining = amount

            c.execute(
                """
                UPDATE purchases
                SET purchase_date=?, purchase_time=?, site_id=?, amount=?, sc_received=?,
                    starting_sc_balance=?, card_id=?, user_id=?, remaining_amount=?,
                    cashback_earned=?, notes=?
                WHERE id=?
                """,
                (
                    pdate,
                    ptime,
                    site_id,
                    amount,
                    sc_received,
                    start_sc,
                    card_id,
                    user_id,
                    new_remaining,
                    cashback_earned,
                    notes,
                    purchase_id,
                ),
            )

            site_changed = old_site_id != site_id
            user_changed = old_user_id != user_id
            amount_changed = old_amount != amount

            if site_changed or user_changed:
                c.execute(
                    """
                    SELECT id FROM site_sessions
                    WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                    ORDER BY start_date DESC LIMIT 1
                    """,
                    (old_site_id, old_user_id),
                )
                old_session = c.fetchone()
                if old_session:
                    c.execute(
                        "UPDATE site_sessions SET total_buyin = total_buyin - ? WHERE id = ?",
                        (old_amount, old_session["id"]),
                    )
                    c.execute(
                        "SELECT total_buyin FROM site_sessions WHERE id = ?",
                        (old_session["id"],),
                    )
                    updated_old = c.fetchone()
                    if updated_old and float(updated_old["total_buyin"] or 0) <= 0:
                        c.execute(
                            "SELECT COUNT(*) as count FROM redemptions WHERE site_session_id = ?",
                            (old_session["id"],),
                        )
                        if c.fetchone()["count"] == 0:
                            c.execute("DELETE FROM site_sessions WHERE id = ?", (old_session["id"],))

                conn.commit()
                conn.close()

                new_session_id = self.session_mgr.get_or_create_site_session(site_id, user_id, pdate)
                self.session_mgr.add_purchase_to_session(new_session_id, amount)
            elif amount_changed:
                c.execute(
                    """
                    SELECT id FROM site_sessions
                    WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                    ORDER BY start_date DESC LIMIT 1
                    """,
                    (site_id, user_id),
                )
                session = c.fetchone()
                if session:
                    amount_diff = amount - old_amount
                    c.execute(
                        "UPDATE site_sessions SET total_buyin = total_buyin + ? WHERE id = ?",
                        (amount_diff, session["id"]),
                    )
                conn.commit()
                conn.close()
            else:
                conn.commit()
                conn.close()

            # If we forced a site/user change, do scoped recalculation for both old and new (site, user) pairs
            if force_site_user_change and (old_site_id != site_id or old_user_id != user_id):
                # Recalculate for old pair (remove old transaction)
                self.session_mgr.auto_recalculate_affected_sessions(
                    old_site_id, old_user_id,
                    old_ts=(old_date, old_time),
                    new_ts=None,
                    scoped=True,
                    entity_type='purchase'
                )
                # Recalculate for new pair (add new transaction)
                if site_id != old_site_id or user_id != old_user_id:
                    self.session_mgr.auto_recalculate_affected_sessions(
                        site_id, user_id,
                        old_ts=None,
                        new_ts=(pdate, ptime),
                        scoped=True,
                        entity_type='purchase'
                    )
                message = "Purchase updated with forced site/user change (scoped recalculation)."
                return True, message

            # Normal edit: use scoped recalculation with both old and new timestamps
            # Build old_values and new_values for skip logic detection
            old_purchase_values = {
                'amount': old_amount,
                'purchase_date': old_date,
                'purchase_time': old_time,
                'site_id': old_site_id,
                'user_id': old_user_id,
                'notes': old_purchase["notes"] if "notes" in old_purchase.keys() else ""
            }
            new_purchase_values = {
                'amount': amount,
                'purchase_date': pdate,
                'purchase_time': ptime,
                'site_id': site_id,
                'user_id': user_id,
                'notes': notes
            }
            
            recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
                site_id, user_id,
                old_ts=(old_date, old_time),
                new_ts=(pdate, ptime),
                scoped=True,
                entity_type='purchase',
                old_values=old_purchase_values,
                new_values=new_purchase_values
            )
            
            # Log audit for purchase update
            self.db.log_audit_conditional(
                "UPDATE",
                "purchases",
                purchase_id,
                f"{user_name} - {site_name} - ${amount:.2f}",
                user_name
            )
            
            message = "Purchase updated"
            if recalc_count > 0:
                message += f" (scoped recalc: {recalc_count} session{'s' if recalc_count != 1 else ''})"
            return True, message

        c.execute(
            """
            INSERT INTO purchases
            (purchase_date, purchase_time, site_id, amount, sc_received, starting_sc_balance,
             card_id, user_id, remaining_amount, cashback_earned, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pdate,
                ptime,
                site_id,
                amount,
                sc_received,
                start_sc,
                card_id,
                user_id,
                amount,
                cashback_earned,
                notes,
            ),
        )
        purchase_id = c.lastrowid
        conn.commit()
        conn.close()

        self.db.log_audit_conditional(
            "INSERT",
            "purchases",
            purchase_id,
            f"{user_name} - {site_name} - ${amount:.2f}",
            user_name,
        )

        session_id = self.session_mgr.get_or_create_site_session(site_id, user_id, pdate)
        self.session_mgr.add_purchase_to_session(session_id, amount)
        
        # Add purchase: use scoped recalculation with new_ts only
        recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
            site_id, user_id,
            old_ts=None,
            new_ts=(pdate, ptime),
            scoped=True,
            entity_type='purchase'
        )
        message = "Purchase added"
        if recalc_count > 0:
            message += f" (recalculated {recalc_count} affected session{'s' if recalc_count != 1 else ''})"
        # Return purchase_id for new purchases so we can prompt for session start
        return True, (message, purchase_id)

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def select_purchase_by_id(self, purchase_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == purchase_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                self._update_action_visibility()
                return True
        return False

    def _needs_purchase_recalc(self, cursor, site_id, user_id, purchase_date, purchase_time):
        cursor.execute(
            """
            SELECT 1
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
            LIMIT 1
            """,
            (site_id, user_id, purchase_date, purchase_date, purchase_time),
        )
        if cursor.fetchone():
            return True
        cursor.execute(
            """
            SELECT 1
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (COALESCE(end_date, session_date) > ? OR (COALESCE(end_date, session_date) = ? AND COALESCE(end_time,'00:00:00') >= ?))
            LIMIT 1
            """,
            (site_id, user_id, purchase_date, purchase_date, purchase_time),
        )
        return cursor.fetchone() is not None

    def view_purchase_by_id(self, purchase_id):
        purchase = self._fetch_purchase(purchase_id)
        if not purchase:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected purchase was not found.")
            return
        dialog = PurchaseViewDialog(
            purchase,
            parent=self,
            on_edit=lambda: self.edit_purchase_by_id(purchase_id),
            on_delete=lambda: self._delete_purchase_by_id(purchase_id),
            on_open_session=self.main_window.open_game_session if self.main_window else None,
            on_open_redemption=self.main_window.open_redemption if self.main_window else None
        )
        dialog.exec()

    def _delete_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select purchase(s) to delete.")
            return
        if len(selected_ids) > 1:
            confirm = QtWidgets.QMessageBox.question(
                self, "Confirm", f"Delete {len(selected_ids)} purchases?"
            )
        else:
            confirm = QtWidgets.QMessageBox.question(self, "Confirm", "Delete this purchase?")
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        self._delete_selected_purchases(selected_ids)

    def _delete_selected_purchases(self, purchase_ids, skip_confirm=False):
        """Shared method to delete purchase(s) - called by both _delete_selected and _delete_purchase_by_id"""
        conn = self.db.get_connection()
        c = conn.cursor()
        deleted_count = 0
        error_messages = []
        affected = {}

        for purchase_id in purchase_ids:
            c.execute(
                """
                SELECT amount, remaining_amount, site_id, user_id, purchase_date, purchase_time
                FROM purchases
                WHERE id = ?
                """,
                (purchase_id,),
            )
            purchase = c.fetchone()
            if not purchase:
                error_messages.append(f"Purchase ID {purchase_id} not found.")
                continue

            amount = float(purchase["amount"] or 0)
            remaining = float(purchase["remaining_amount"] or 0)
            consumed = amount - remaining
            site_id = purchase["site_id"]
            user_id = purchase["user_id"]
            pdate = purchase["purchase_date"]
            ptime = purchase["purchase_time"] or "00:00:00"
            key = (site_id, user_id)
            current = affected.get(key)
            if current is None or (pdate, ptime) < current:
                affected[key] = (pdate, ptime)

            if consumed > 0:
                error_messages.append(
                    f"Purchase of ${amount:.2f} cannot be deleted - ${consumed:.2f} has been used for redemptions."
                )
                continue

            c.execute(
                """
                SELECT id FROM site_sessions
                WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                ORDER BY start_date DESC LIMIT 1
                """,
                (site_id, user_id),
            )
            session = c.fetchone()

            c.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
            deleted_count += 1

            if session:
                session_id = session["id"]
                c.execute(
                    "UPDATE site_sessions SET total_buyin = total_buyin - ? WHERE id = ?",
                    (amount, session_id),
                )
                c.execute(
                    "SELECT total_buyin, total_redeemed FROM site_sessions WHERE id = ?",
                    (session_id,),
                )
                updated = c.fetchone()
                if updated:
                    total_buyin = float(updated["total_buyin"] or 0)
                    total_redeemed = float(updated["total_redeemed"] or 0)
                    if total_buyin <= 0 and total_redeemed == 0:
                        c.execute(
                            "SELECT COUNT(*) as count FROM redemptions WHERE site_session_id = ?",
                            (session_id,),
                        )
                        if c.fetchone()["count"] == 0:
                            c.execute("DELETE FROM site_sessions WHERE id = ?", (session_id,))

        # Check which affected sessions need recalculation before closing connection
        recalc_needed = []
        for (site_id, user_id), (pdate, ptime) in affected.items():
            if self._needs_purchase_recalc(c, site_id, user_id, pdate, ptime):
                recalc_needed.append((site_id, user_id, pdate, ptime))

        conn.commit()
        conn.close()

        # Log audit for the batch delete (avoiding per-item connection overhead)
        if deleted_count > 0:
            self.db.log_audit_conditional(
                "DELETE",
                "purchases",
                None,
                f"Deleted {deleted_count} purchase(s)",
                None,
            )

        # Now do the expensive recalculations using scoped API
        total_recalc = 0
        for site_id, user_id, pdate, ptime in recalc_needed:
            # Delete purchase: use old_ts (removing transaction)
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                site_id, user_id,
                old_ts=(pdate, ptime),
                new_ts=None,
                scoped=True,
                entity_type='purchase'
            )

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        if error_messages:
            message = f"Deleted {deleted_count} purchase(s)."
            if total_recalc > 0:
                message += f" Scoped recalc: {total_recalc} session{'s' if total_recalc != 1 else ''}."
            message += "\n\nErrors:\n" + "\n".join(error_messages)
            QtWidgets.QMessageBox.warning(self, "Partial Success", message)
        else:
            message = f"Deleted {deleted_count} purchase{'s' if deleted_count != 1 else ''}"
            if total_recalc > 0:
                message += f" (scoped recalc: {total_recalc} session{'s' if total_recalc != 1 else ''})"
            QtWidgets.QMessageBox.information(self, "Success", message)

    def _delete_purchase_by_id(self, purchase_id):
        """Delete a single purchase by ID (called from View dialog)"""
        # Select the row and call existing delete logic (which will show confirmation)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == purchase_id:
                self.table.selectRow(row)
                break
        self._delete_selected()

    def export_csv(self):
        import csv

        default_name = f"purchases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Purchases",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        headers = [
            self.table.horizontalHeaderItem(i).text()
            for i in range(self.table.columnCount())
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in self.filtered_rows:
                writer.writerow(row["display"])

    def _show_info_message(self, title, message):
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        box.open()


class RedemptionsTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr, on_data_changed=None, on_open_purchase=None, main_window=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.on_open_purchase = on_open_purchase
        self.main_window = main_window
        self.all_rows = []
        self.filtered_rows = []
        self.header_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self.active_date_filter = (None, None)
        self._has_subsequent = False
        self._subsequent_ids = []
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QtWidgets.QPushButton("Add Redemption")
        self.view_btn = QtWidgets.QPushButton("View Redemption")
        self.edit_btn = QtWidgets.QPushButton("Edit Redemption")
        self.delete_btn = QtWidgets.QPushButton("Delete Redemption")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.add_btn.setObjectName("PrimaryButton")
        self.view_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.view_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search redemptions...")
        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Date/Time",
                "User",
                "Site",
                "Amount",
                "Receipt",
                "Method",
                "Processed",
                "Notes",
            ]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_selected)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

        self.add_btn.clicked.connect(self._add_redemption)
        self.view_btn.clicked.connect(self._view_selected)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn.clicked.connect(self.export_csv)
        self.refresh_btn.clicked.connect(self.load_data)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))

        self._update_action_visibility()
        self.load_data()

    def eventFilter(self, obj, event):
        if getattr(self, "header", None) and obj is self.header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(self.header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(self.header, pos) is not None:
                    return False
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT r.id, r.redemption_date, r.redemption_time, s.name as site, u.name as user_name,
                   r.amount, r.receipt_date, rm.name as method, r.processed,
                   r.more_remaining, r.notes
            FROM redemptions r
            JOIN sites s ON r.site_id = s.id
            JOIN users u ON r.user_id = u.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            ORDER BY r.redemption_date DESC, r.redemption_time DESC
            """
        )
        self.all_rows = []
        for row in c.fetchall():
            time_value = row["redemption_time"] or "00:00:00"
            dt_value = None
            try:
                dt_value = datetime.strptime(
                    f"{row['redemption_date']} {time_value}", "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                dt_value = None
            is_total_loss = float(row["amount"] or 0) == 0
            receipt_date = row["receipt_date"] or ""
            is_pending = receipt_date == ""
            if is_total_loss:
                receipt_display = row["redemption_date"]
            elif is_pending:
                receipt_display = "PENDING"
            else:
                receipt_display = receipt_date
            notes = row["notes"] or ""
            notes_display = notes[:120]
            method_display = "Loss" if is_total_loss else (row["method"] or "")
            display = [
                format_date_time(row["redemption_date"], time_value),
                row["user_name"],
                row["site"],
                format_currency(row["amount"]),
                receipt_display,
                method_display,
                "✓" if row["processed"] else "",
                notes_display,
            ]
            self.all_rows.append(
                {
                    "id": row["id"],
                    "redemption_date": row["redemption_date"],
                    "redemption_time": time_value,
                    "redemption_dt": dt_value,
                    "user_name": row["user_name"],
                    "site": row["site"],
                    "amount": float(row["amount"] or 0),
                    "receipt_date": receipt_date,
                    "method": row["method"] or "",
                    "processed": bool(row["processed"]),
                    "more_remaining": bool(row["more_remaining"]),
                    "notes": notes,
                    "status": "total_loss" if is_total_loss else ("pending" if is_pending else "normal"),
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.apply_filters()

    def apply_filters(self):
        rows = self._filter_rows()
        rows = self.sort_rows(rows)
        self.filtered_rows = rows
        self.refresh_table(rows)

    def _filter_rows(self, exclude_col=None):
        rows = list(self.all_rows)
        start_date, end_date = self.active_date_filter
        if start_date:
            rows = [r for r in rows if r["redemption_date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["redemption_date"] <= end_date]

        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in rows if term in r["search_blob"]]

        for col, values in self.header_filters.items():
            if col == exclude_col:
                continue
            if values:
                rows = [r for r in rows if r["display"][col] in values]
        return rows

    def refresh_table(self, rows):
        numeric_cols = {3}
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            status = row["status"]
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in numeric_cols:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, row["id"])
                if status == "total_loss":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                elif status == "pending":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#e67e22")))
                self.table.setItem(r_idx, c_idx, item)
        self._update_action_visibility()

    def sort_rows(self, rows):
        if self.sort_column is None:
            return rows
        reverse = self.sort_order == QtCore.Qt.DescendingOrder

        def sort_key(row):
            col = self.sort_column
            if col == 0:
                return row["redemption_dt"] or datetime.min
            if col == 1:
                return row["user_name"].lower()
            if col == 2:
                return row["site"].lower()
            if col == 3:
                return row["amount"]
            if col == 4:
                return row["receipt_date"]
            if col == 5:
                return row["method"].lower()
            if col == 6:
                return row["processed"]
            if col == 7:
                return row["notes"].lower()
            return row["display"][col]

        return sorted(rows, key=sort_key, reverse=reverse)

    def _show_header_menu(self, col_index):
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        pos_x = self.header.sectionPosition(col_index)
        pos = self.header.mapToGlobal(QtCore.QPoint(pos_x, self.header.height()))
        action = menu.exec(pos)
        if action == sort_asc:
            self.set_sort(col_index, QtCore.Qt.AscendingOrder)
        elif action == sort_desc:
            self.set_sort(col_index, QtCore.Qt.DescendingOrder)
        elif action == clear_sort:
            self.clear_sort()
        elif action == filter_action:
            filter_rows = self._filter_rows(exclude_col=col_index)
            values = sorted({r["display"][col_index] for r in filter_rows})
            selected = self.header_filters.get(col_index, set())
            if col_index == 0:
                dialog = DateTimeFilterDialog(values, selected, self)
            else:
                dialog = ColumnFilterDialog(values, selected, self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                selected_values = dialog.selected_values()
                if selected_values:
                    self.header_filters[col_index] = selected_values
                else:
                    self.header_filters.pop(col_index, None)
                self.apply_filters()

    def set_sort(self, column, order):
        self.sort_column = column
        self.sort_order = order
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self.apply_filters()

    def clear_sort(self):
        self.sort_column = None
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        self.apply_filters()

    def clear_all_filters(self):
        self.header_filters = {}
        self.search_edit.clear()
        self.clear_sort()
        self.clear_date_filter()
        self._clear_selection()

    def apply_date_filter(self):
        from_text = self.from_edit.text().strip()
        to_text = self.to_edit.text().strip()
        start_date = None
        end_date = None
        try:
            if from_text:
                start_date = parse_date_input(from_text).strftime("%Y-%m-%d")
            if to_text:
                end_date = parse_date_input(to_text).strftime("%Y-%m-%d")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Date", "Please enter a valid date.")
            return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (start_date, end_date)
        self.apply_filters()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.apply_filters()

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            self.clear_date_filter()
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.apply_filters()

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _fetch_lookup_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        sites = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM redemption_methods WHERE active = 1 ORDER BY name")
        methods = [r["name"] for r in c.fetchall()]
        conn.close()
        return users, sites, methods

    def _add_redemption(self):
        users, sites, methods = self._fetch_lookup_data()
        dialog = RedemptionDialog(self.db, users, sites, methods, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, None)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _edit_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a redemption to edit.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Multiple Selection",
                "Please select only one redemption to edit.",
            )
            return
        self.edit_redemption_by_id(selected_ids[0])

    def edit_redemption_by_id(self, redemption_id):
        if not self._check_subsequent_redemptions(redemption_id):
            return
        redemption = self._fetch_redemption(redemption_id)
        if not redemption:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected redemption was not found.")
            return
        users, sites, methods = self._fetch_lookup_data()
        dialog = RedemptionDialog(self.db, users, sites, methods, redemption=redemption, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, redemption_id)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _view_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a redemption to view.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Multiple Selection",
                "Please select only one redemption to view.",
            )
            return
        redemption_id = selected_ids[0]
        redemption = self._fetch_redemption(redemption_id)
        if not redemption:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected redemption was not found.")
            return
        allocations = self._fetch_redemption_allocations(redemption_id)
        dialog = RedemptionViewDialog(
            redemption,
            allocations,
            parent=self,
            on_edit=lambda: self.edit_redemption_by_id(redemption_id),
            on_open_purchase=self.on_open_purchase,
            on_open_session=self.main_window.open_game_session if self.main_window else None,
            on_delete=lambda: self._delete_redemption_by_id(redemption_id),
            on_view_realized=self.main_window.view_realized_position if self.main_window else None,
        )
        dialog.exec()

    def _check_subsequent_redemptions(self, redemption_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT redemption_date, site_id, user_id
            FROM redemptions
            WHERE id = ?
            """,
            (redemption_id,),
        )
        this_redemption = c.fetchone()
        self._has_subsequent = False
        self._subsequent_ids = []
        if this_redemption:
            c.execute(
                """
                SELECT id, redemption_date, amount
                FROM redemptions
                WHERE site_id = ?
                  AND user_id = ?
                  AND redemption_date >= ?
                  AND id != ?
                ORDER BY redemption_date ASC, id ASC
                """,
                (
                    this_redemption["site_id"],
                    this_redemption["user_id"],
                    this_redemption["redemption_date"],
                    redemption_id,
                ),
            )
            subsequent = c.fetchall()
            if subsequent:
                self._has_subsequent = True
                self._subsequent_ids = [row["id"] for row in subsequent]
                warning_msg = (
                    f"WARNING: This redemption has {len(subsequent)} subsequent redemption(s).\n\n"
                    "Editing this will recalculate their FIFO cost basis.\n\n"
                    "Continue with edit?"
                )
                if (
                    QtWidgets.QMessageBox.question(self, "Subsequent Redemptions", warning_msg)
                    != QtWidgets.QMessageBox.Yes
                ):
                    conn.close()
                    return False
        conn.close()
        return True

    def _save_from_dialog(self, dialog, redemption_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return
        if not self._confirm_redemption_flags(data, redemption_id):
            return
        ok, message = self._save_redemption_record(data, redemption_id)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Error", message)
            return
        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        QtCore.QTimer.singleShot(0, lambda: self._show_info_message("Success", message))

    def _fetch_redemption(self, redemption_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT r.*, s.name as site_name, rm.name as method_name, rm.method_type, u.name as user_name
            FROM redemptions r
            JOIN sites s ON r.site_id = s.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            JOIN users u ON r.user_id = u.id
            WHERE r.id = ?
            """,
            (redemption_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def _fetch_redemption_allocations(self, redemption_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT
                ra.purchase_id,
                ra.allocated_amount,
                p.purchase_date,
                p.purchase_time,
                p.amount,
                p.sc_received,
                p.remaining_amount
            FROM redemption_allocations ra
            JOIN purchases p ON ra.purchase_id = p.id
            WHERE ra.redemption_id = ?
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time,'00:00:00') ASC, p.id ASC
            """,
            (redemption_id,),
        )
        allocations = [dict(row) for row in c.fetchall()]
        conn.close()
        return allocations

    def _confirm_redemption_flags(self, data, redemption_id):
        if data.get("more_remaining"):
            return True

        user_name = data["user_name"]
        site_name = data["site_name"]
        rdate = data["redemption_date"]
        rtime = data["redemption_time"]
        amount = float(data["amount"] or 0.0)

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        if not user_row or not site_row:
            conn.close()
            return True
        user_id = user_row["id"]
        site_id = site_row["id"]

        expected_total, expected_redeemable = self.session_mgr.compute_expected_balances(
            site_id, user_id, rdate, rtime
        )
        sc_rate = float(self.session_mgr.get_sc_rate(site_id) or 1.0)
        expected_balance = float(expected_redeemable or 0.0) * sc_rate

        if redemption_id:
            c.execute(
                """
                SELECT site_id, user_id, redemption_date,
                       COALESCE(redemption_time,'00:00:00') as redemption_time,
                       amount
                FROM redemptions
                WHERE id = ?
                """,
                (redemption_id,),
            )
            old = c.fetchone()
            if old and old["site_id"] == site_id and old["user_id"] == user_id:
                try:
                    old_dt = datetime.fromisoformat(
                        f"{old['redemption_date']} {old['redemption_time']}"
                    )
                    new_dt = datetime.fromisoformat(f"{rdate} {rtime or '00:00:00'}")
                except ValueError:
                    old_dt = None
                    new_dt = None
                if old_dt and new_dt and old_dt < new_dt:
                    expected_balance += float(old["amount"] or 0.0)

        conn.close()

        remaining_balance = expected_balance - amount
        if remaining_balance <= 0.01:
            return True

        message = (
            "You selected Full redemption, but there appears to be a remaining balance.\n\n"
            f"Expected redeemable balance: {format_currency(expected_balance)}\n"
            f"Redemption amount: {format_currency(amount)}\n"
            f"Remaining balance: {format_currency(remaining_balance)}\n\n"
            "Full will consume all remaining cost basis and record the remainder as a cashflow loss.\n"
            "Game Session taxable P/L is not affected.\n\n"
            "Continue as Full?"
        )
        response = QtWidgets.QMessageBox.question(
            self,
            "Confirm Full Redemption",
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return response == QtWidgets.QMessageBox.Yes

    def _save_redemption_record(self, data, redemption_id):
        user_name = data["user_name"]
        site_name = data["site_name"]
        method_name = data["method_name"]
        rdate = data["redemption_date"]
        rtime = data["redemption_time"]
        amount = data["amount"]
        fees = data.get("fees", 0)
        receipt_date = data["receipt_date"]
        more_remaining = data["more_remaining"]
        processed = 1 if data["processed"] else 0
        notes = data["notes"]

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            return False, f"User '{user_name}' not found."
        user_id = user_row["id"]
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        if not site_row:
            conn.close()
            return False, f"Site '{site_name}' not found."
        site_id = site_row["id"]

        if not redemption_id:
            c.execute(
                """
                SELECT id, starting_sc_balance
                FROM game_sessions
                WHERE site_id = ? AND user_id = ? AND status = 'Active'
                ORDER BY session_date DESC, start_time DESC
                LIMIT 1
                """,
                (site_id, user_id),
            )
            active_session = c.fetchone()
            if active_session:
                conn.close()
                return (
                    False,
                    "Cannot create a new redemption while a session is active.",
                )

            expected_total, expected_redeemable = self.session_mgr.compute_expected_balances(
                site_id, user_id, rdate, rtime
            )
            sc_rate = self.session_mgr.get_sc_rate(site_id)
            expected_balance = expected_redeemable * sc_rate
            unsessioned_amount = amount - expected_balance
            if unsessioned_amount > 0.50:
                conn.close()
                return (
                    False,
                    "This redemption exceeds the balance we can verify from recorded sessions.\n\n"
                    f"Redemption amount: ${amount:,.2f}\n"
                    f"Expected sessioned balance: ${expected_balance:,.2f}\n"
                    f"Unsessioned amount: ${unsessioned_amount:,.2f}\n\n"
                    "What this means:\n"
                    "• We only allow redemptions against balances that were recorded in Game Sessions.\n"
                    "• This helps keep your session-based totals accurate.\n\n"
                    "What to do:\n"
                    "1) Start or end a Game Session for this site to record the current balance.\n"
                    "2) Then try the redemption again.\n\n"
                    "If this was a bonus or freeplay not captured in sessions, record it in a Game Session first.",
                )

        method_id = None
        if method_name:
            c.execute("SELECT id FROM redemption_methods WHERE name = ?", (method_name,))
            method_row = c.fetchone()
            if method_row:
                method_id = method_row["id"]

        session_id = None
        c.execute(
            """
            SELECT id FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC LIMIT 1
            """,
            (site_id, user_id),
        )
        result = c.fetchone()
        if result:
            session_id = result["id"]

        if redemption_id:
            c.execute(
                """
                SELECT r.amount, r.site_session_id, r.site_id, r.user_id,
                       r.redemption_date, r.redemption_time,
                       rt.cost_basis
                FROM redemptions r
                LEFT JOIN realized_transactions rt ON rt.redemption_id = r.id
                WHERE r.id = ?
                """,
                (redemption_id,),
            )
            old_data = c.fetchone()
            old_amount = float(old_data["amount"]) if old_data else 0.0
            old_session_id = old_data["site_session_id"] if old_data else None
            old_site_id = old_data["site_id"] if old_data else None
            old_user_id = old_data["user_id"] if old_data else None
            old_date = old_data["redemption_date"] if old_data else None
            old_time = old_data["redemption_time"] or "00:00:00" if old_data else "00:00:00"
            old_cost_basis = float(old_data["cost_basis"] or 0.0) if old_data else 0.0

            # Build old record dict for admin-only check
            old_record = {
                'site_id': old_site_id,
                'user_id': old_user_id,
                'redemption_date': old_date,
                'redemption_time': old_time,
                'amount': old_amount,
                'notes': old_data["notes"] if old_data and "notes" in old_data.keys() else None,
                'redemption_method_id': old_data["redemption_method_id"] if old_data and "redemption_method_id" in old_data.keys() else None,
                'receipt_date': old_data["receipt_date"] if old_data and "receipt_date" in old_data.keys() else None,
                'processed': old_data["processed"] if old_data and "processed" in old_data.keys() else 0,
                'fees': old_data["fees"] if old_data and "fees" in old_data.keys() else 0,
            }
            new_record = {
                'site_id': site_id,
                'user_id': user_id,
                'redemption_date': rdate,
                'redemption_time': rtime,
                'amount': amount,
                'notes': notes,
                'redemption_method_id': method_id,
                'receipt_date': receipt_date,
                'processed': 1 if processed else 0,
                'fees': fees,
            }

            # Determine which fields changed
            changed_fields = {k for k in old_record if old_record.get(k) != new_record.get(k)}

            # Administrative fields that don't affect realized_transactions
            admin_fields = {'notes', 'redemption_method_id', 'receipt_date', 'processed', 'fees'}

            # Check if only administrative fields changed
            accounting_changed = bool(changed_fields - admin_fields)

            c.execute(
                """
                UPDATE redemptions
                SET site_session_id=?, site_id=?, redemption_date=?, redemption_time=?, amount=?, fees=?, receipt_date=?,
                    redemption_method_id=?, more_remaining=?, user_id=?, processed=?, notes=?
                WHERE id=?
                """,
                (
                    session_id,
                    site_id,
                    rdate,
                    rtime,
                    amount,
                    fees,
                    receipt_date,
                    method_id,
                    1 if more_remaining else 0,
                    user_id,
                    processed,
                    notes,
                    redemption_id,
                ),
            )

            if old_session_id and accounting_changed:
                c.execute(
                    "UPDATE site_sessions SET total_redeemed = total_redeemed - ? WHERE id = ?",
                    (old_amount, old_session_id),
                )

            if session_id and session_id != old_session_id and accounting_changed:
                c.execute(
                    "UPDATE site_sessions SET total_redeemed = total_redeemed + ? WHERE id = ?",
                    (amount, session_id),
                )

            # Only delete and recalculate realized_transactions if accounting fields changed
            if accounting_changed:
                c.execute("DELETE FROM realized_transactions WHERE redemption_id = ?", (redemption_id,))
            conn.commit()
            conn.close()

            # No need to call process_redemption() here - auto_recalculate does full rebuild
            # The old reverse_cost_basis and process_redemption calls were redundant

            # Only recalculate if accounting fields changed
            total_recalc = 0
            if accounting_changed:
                if self._has_subsequent and self._subsequent_ids:
                    self._recalculate_subsequent_redemptions(self._subsequent_ids, site_id, user_id)

                # Scoped recalculation for affected pairs
                # Skip if nothing changed (same site, user, date, time, and amount)
                nothing_changed = (
                    old_site_id == site_id and
                    old_user_id == user_id and
                    old_date == rdate and
                    old_time == rtime and
                    abs(old_amount - amount) < 0.01
                )
                
                if not nothing_changed:
                    # If site/user changed, recalculate both old and new pairs
                    if old_site_id and old_user_id and (old_site_id != site_id or old_user_id != user_id):
                        # Old pair: remove old transaction
                        total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                            old_site_id, old_user_id,
                            old_ts=(old_date, old_time),
                            new_ts=None,
                            scoped=True,
                            entity_type='redemption'
                        )
                        # New pair: add new transaction
                        total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                            site_id, user_id,
                            old_ts=None,
                            new_ts=(rdate, rtime),
                            scoped=True,
                            entity_type='redemption'
                        )
                    else:
                        # Same pair: use both timestamps
                        total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                            site_id, user_id,
                            old_ts=(old_date, old_time),
                            new_ts=(rdate, rtime),
                            scoped=True,
                            entity_type='redemption'
                        )
                    # Old pair: remove old transaction
                    total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                        old_site_id, old_user_id,
                        old_ts=(old_date, old_time),
                        new_ts=None,
                        scoped=True,
                        entity_type='redemption'
                    )
                    # New pair: add new transaction
                    total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                        site_id, user_id,
                        old_ts=None,
                        new_ts=(rdate, rtime),
                        scoped=True,
                        entity_type='redemption'
                    )
                else:
                    # Same pair: use both timestamps
                    total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                        site_id, user_id,
                        old_ts=(old_date, old_time),
                        new_ts=(rdate, rtime),
                        scoped=True,
                        entity_type='redemption'
                    )

            # Log audit for redemption update
            self.db.log_audit_conditional(
                "UPDATE",
                "redemptions",
                redemption_id,
                f"{user_name} - {site_name} - ${amount:.2f}",
                user_name
            )

            message = "Redemption updated"
            if self._has_subsequent:
                message += f" (recalculated {len(self._subsequent_ids)} subsequent redemptions)"
            if total_recalc:
                message += f" (scoped recalc: {total_recalc} sessions)"
            return True, message

        c.execute(
            """
            INSERT INTO redemptions
            (site_session_id, site_id, redemption_date, redemption_time, amount, fees, receipt_date,
             redemption_method_id, more_remaining, user_id, processed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                site_id,
                rdate,
                rtime,
                amount,
                fees,
                receipt_date,
                method_id,
                1 if more_remaining else 0,
                user_id,
                processed,
                notes,
            ),
        )
        rid = c.lastrowid
        conn.commit()
        conn.close()

        # Log audit for redemption insert
        self.db.log_audit_conditional(
            "INSERT",
            "redemptions",
            rid,
            f"{user_name} - {site_name} - ${amount:.2f}",
            user_name
        )

        # Add redemption: use scoped recalculation with new_ts only
        recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
            site_id, user_id,
            old_ts=None,
            new_ts=(rdate, rtime),
            scoped=True,
            entity_type='redemption'
        )
        message = "Redemption logged"
        if recalc_count:
            message += f" (scoped recalc: {recalc_count} sessions)"
        return True, message

    def _recalculate_subsequent_redemptions(self, redemption_ids, site_id, user_id):
        for rid in redemption_ids:
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute(
                """
                SELECT amount, redemption_date, redemption_time
                FROM redemptions
                WHERE id = ?
                """,
                (rid,),
            )
            redemption = c.fetchone()
            if not redemption:
                conn.close()
                continue
            amount = float(redemption["amount"])
            rdate = redemption["redemption_date"]
            rtime = redemption["redemption_time"] or "00:00:00"
            c.execute("SELECT cost_basis FROM realized_transactions WHERE redemption_id = ?", (rid,))
            old_tax = c.fetchone()
            old_cost_basis = float(old_tax["cost_basis"]) if old_tax and old_tax["cost_basis"] else 0.0
            c.execute("DELETE FROM realized_transactions WHERE redemption_id = ?", (rid,))
            conn.commit()
            conn.close()
            if old_cost_basis > 0:
                self.session_mgr.fifo_calc.reverse_cost_basis(site_id, user_id, old_cost_basis)
            self.session_mgr.process_redemption(
                rid,
                site_id,
                amount,
                rdate,
                rtime,
                user_id,
                False,
                more_remaining=True,
                is_edit=True,
            )

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def select_redemption_by_id(self, redemption_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == redemption_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                self._update_action_visibility()
                return True
        return False

    def view_redemption_by_id(self, redemption_id):
        redemption = self._fetch_redemption(redemption_id)
        if not redemption:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected redemption was not found.")
            return
        allocations = self._fetch_redemption_allocations(redemption_id)
        dialog = RedemptionViewDialog(
            redemption,
            allocations,
            parent=self,
            on_edit=lambda: self.edit_redemption_by_id(redemption_id),
            on_open_purchase=self.on_open_purchase,
            on_open_session=self.main_window.open_game_session if self.main_window else None,
            on_delete=lambda: self._delete_redemption_by_id(redemption_id),
            on_view_realized=self.main_window.view_realized_position if self.main_window else None,
        )
        dialog.exec()

    def _delete_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select redemption(s) to delete.")
            return
        if len(selected_ids) > 1:
            confirm = QtWidgets.QMessageBox.question(
                self, "Confirm", f"Delete {len(selected_ids)} redemptions?"
            )
        else:
            confirm = QtWidgets.QMessageBox.question(self, "Confirm", "Delete this redemption?")
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        # Fetch all redemption data first with a single connection
        conn = self.db.get_connection()
        c = conn.cursor()
        redemption_data = {}
        for redemption_id in selected_ids:
            c.execute(
                "SELECT site_id, user_id, redemption_date, redemption_time FROM redemptions WHERE id = ?",
                (redemption_id,),
            )
            row = c.fetchone()
            if row:
                redemption_data[redemption_id] = row
        conn.close()

        deleted_count = 0
        error_messages = []
        pairs_to_recalc = set()

        for redemption_id in selected_ids:
            row = redemption_data.get(redemption_id)
            success = self.session_mgr.delete_redemption(int(redemption_id))
            if success:
                deleted_count += 1
                if row:
                    pairs_to_recalc.add(
                        (
                            row["site_id"],
                            row["user_id"],
                            row["redemption_date"],
                            row["redemption_time"] or "00:00:00",
                        )
                    )
            else:
                error_messages.append(f"Redemption ID {redemption_id} not found")

        total_recalc = 0
        for site_id, user_id, rdate, rtime in pairs_to_recalc:
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                site_id, user_id,
                old_ts=(rdate, rtime),
                new_ts=None,
                scoped=True,
                entity_type='redemption'
            )

        # Log audit for redemption delete
        if deleted_count > 0:
            self.db.log_audit_conditional(
                "DELETE",
                "redemptions",
                None,
                f"Deleted {deleted_count} redemption(s)",
                None
            )

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        if error_messages:
            error_text = "\n".join(error_messages)
            QtWidgets.QMessageBox.warning(
                self,
                "Partial Success",
                f"Deleted {deleted_count} redemption(s).\n\nErrors:\n{error_text}",
            )
        else:
            message = f"Deleted {deleted_count} redemption{'s' if deleted_count != 1 else ''}"
            if total_recalc:
                message += f" (scoped recalc: {total_recalc} sessions)"
            QtWidgets.QMessageBox.information(self, "Success", message)

    def _update_action_visibility(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        self.view_btn.setVisible(len(selected) == 1)
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_visibility()

    def _delete_redemption_by_id(self, redemption_id):
        """Delete a single redemption by ID (called from View dialog)"""
        # Select the row and call existing delete logic (which will show confirmation)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == redemption_id:
                self.table.selectRow(row)
                break
        self._delete_selected()

    def export_csv(self):
        import csv

        default_name = f"redemptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Redemptions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        headers = [
            self.table.horizontalHeaderItem(i).text()
            for i in range(self.table.columnCount())
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        for row in self.filtered_rows:
            writer.writerow(row["display"])

    def _show_info_message(self, title, message):
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        box.open()


class ExpensesTab(QtWidgets.QWidget):
    def __init__(self, db, on_data_changed=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.on_data_changed = on_data_changed
        self.all_rows = []
        self.filtered_rows = []
        self.header_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self.active_date_filter = (None, None)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QtWidgets.QPushButton("Add Expense")
        self.view_btn = QtWidgets.QPushButton("View Expense")
        self.edit_btn = QtWidgets.QPushButton("Edit Expense")
        self.delete_btn = QtWidgets.QPushButton("Delete Expense")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.add_btn.setObjectName("PrimaryButton")
        self.view_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.view_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search expenses...")
        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Category", "Vendor", "User", "Amount", "Description"]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_selected)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

        self.add_btn.clicked.connect(self._add_expense)
        self.view_btn.clicked.connect(self._view_selected)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn.clicked.connect(self.export_csv)
        self.refresh_btn.clicked.connect(self.load_data)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))

        self._update_action_visibility()
        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT e.id, e.expense_date, e.vendor, e.category, e.amount, e.description, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            ORDER BY e.expense_date DESC, e.id DESC
            """
        )
        self.all_rows = []
        for row in c.fetchall():
            date_value = row["expense_date"]
            try:
                date_display = datetime.strptime(date_value, "%Y-%m-%d").strftime("%m/%d/%y")
                date_dt = datetime.strptime(date_value, "%Y-%m-%d")
            except ValueError:
                date_display = date_value
                date_dt = datetime.min
            display = [
                date_display,
                row["category"] or "Other Expenses",
                row["vendor"] or "",
                row["user_name"] or "",
                format_currency(row["amount"]),
                row["description"] or "",
            ]
            self.all_rows.append(
                {
                    "id": row["id"],
                    "expense_date": date_value,
                    "expense_dt": date_dt,
                    "category": row["category"] or "Other Expenses",
                    "vendor": row["vendor"] or "",
                    "user_name": row["user_name"] or "",
                    "amount": float(row["amount"] or 0),
                    "description": row["description"] or "",
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.apply_filters()

    def apply_filters(self):
        rows = self._filter_rows()
        rows = self.sort_rows(rows)
        self.filtered_rows = rows
        self.refresh_table(rows)

    def _filter_rows(self, exclude_col=None):
        rows = list(self.all_rows)
        start_date, end_date = self.active_date_filter
        if start_date:
            rows = [r for r in rows if r["expense_date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["expense_date"] <= end_date]

        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in rows if term in r["search_blob"]]

        for col, values in self.header_filters.items():
            if col == exclude_col:
                continue
            if values:
                rows = [r for r in rows if r["display"][col] in values]
        return rows

    def refresh_table(self, rows):
        numeric_cols = {4}
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in numeric_cols:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, row["id"])
                self.table.setItem(r_idx, c_idx, item)
        self._update_action_visibility()

    def eventFilter(self, obj, event):
        if getattr(self, "header", None) and obj is self.header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(self.header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(self.header, pos) is not None:
                    return False
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _update_action_visibility(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        self.view_btn.setVisible(len(selected) == 1)
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_visibility()

    def sort_rows(self, rows):
        if self.sort_column is None:
            return rows
        reverse = self.sort_order == QtCore.Qt.DescendingOrder

        def sort_key(row):
            col = self.sort_column
            if col == 0:
                return row["expense_dt"] or datetime.min
            if col == 1:
                return row["category"].lower()
            if col == 2:
                return row["vendor"].lower()
            if col == 3:
                return row["user_name"].lower()
            if col == 4:
                return row["amount"]
            if col == 5:
                return row["description"].lower()
            return row["display"][col]

        return sorted(rows, key=sort_key, reverse=reverse)

    def _show_header_menu(self, col_index):
        header = self.table.horizontalHeader()
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        pos_x = header.sectionPosition(col_index)
        pos = header.mapToGlobal(QtCore.QPoint(pos_x, header.height()))
        action = menu.exec(pos)
        if action == sort_asc:
            self.set_sort(col_index, QtCore.Qt.AscendingOrder)
        elif action == sort_desc:
            self.set_sort(col_index, QtCore.Qt.DescendingOrder)
        elif action == clear_sort:
            self.clear_sort()
        elif action == filter_action:
            filter_rows = self._filter_rows(exclude_col=col_index)
            values = sorted({r["display"][col_index] for r in filter_rows})
            selected = self.header_filters.get(col_index, set())
            if col_index == 0:
                dialog = DateTimeFilterDialog(values, selected, self, show_time=False)
            else:
                dialog = ColumnFilterDialog(values, selected, self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                selected_values = dialog.selected_values()
                if selected_values:
                    self.header_filters[col_index] = selected_values
                else:
                    self.header_filters.pop(col_index, None)
                self.apply_filters()

    def set_sort(self, column, order):
        self.sort_column = column
        self.sort_order = order
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self.apply_filters()

    def clear_sort(self):
        self.sort_column = None
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        self.apply_filters()

    def clear_all_filters(self):
        self.header_filters = {}
        self.search_edit.clear()
        self.clear_date_filter()
        self._clear_selection()
        self.apply_filters()

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def _fetch_lookup_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r["name"] for r in c.fetchall()]
        conn.close()
        return users

    def _fetch_expense(self, expense_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT e.*, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
            """,
            (expense_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def _add_expense(self):
        users = self._fetch_lookup_data()
        dialog = ExpenseDialog(self.db, users, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, None)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _edit_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an expense to edit.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self, "Multiple Selection", "Please select only one expense to edit."
            )
            return
        self.edit_expense_by_id(selected_ids[0])

    def edit_expense_by_id(self, expense_id):
        expense = self._fetch_expense(expense_id)
        if not expense:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected expense was not found.")
            return
        users = self._fetch_lookup_data()
        dialog = ExpenseDialog(self.db, users, expense=expense, parent=self)

        def handle_save():
            self._save_from_dialog(dialog, expense_id)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _view_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an expense to view.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self, "Multiple Selection", "Please select only one expense to view."
            )
            return
        expense_id = selected_ids[0]
        expense = self._fetch_expense(expense_id)
        if not expense:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected expense was not found.")
            return
        dialog = ExpenseViewDialog(
            expense,
            parent=self,
            on_edit=lambda: self.edit_expense_by_id(expense_id),
            on_delete=lambda: self._delete_expense_by_id(expense_id),
        )
        dialog.exec()

    def _delete_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select expense(s) to delete.")
            return
        if len(selected_ids) > 1:
            confirm = QtWidgets.QMessageBox.question(
                self, "Confirm", f"Delete {len(selected_ids)} expenses?"
            )
        else:
            confirm = QtWidgets.QMessageBox.question(self, "Confirm", "Delete this expense?")
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted_count = 0
        for expense_id in selected_ids:
            c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            if c.rowcount:
                deleted_count += 1
        conn.commit()
        conn.close()

        # Log audit for the batch delete (avoiding per-item connection overhead)
        if deleted_count > 0:
            self.db.log_audit_conditional(
                "DELETE",
                "expenses",
                None,
                f"Deleted {deleted_count} expense(s)",
                None,
            )

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        self._show_info_message(
            "Success",
            f"Deleted {deleted_count} expense{'s' if deleted_count != 1 else ''}",
        )

    def _save_from_dialog(self, dialog, expense_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return
        ok, message = self._save_expense_record(data, expense_id)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Error", message)
            return
        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        QtWidgets.QMessageBox.information(self, "Success", message)

    def _delete_expense_by_id(self, expense_id):
        """Delete a single expense by ID (called from View dialog)"""
        # Select the row and call existing delete logic (which will show confirmation)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == expense_id:
                self.table.selectRow(row)
                break
        self._delete_selected()

    def _save_expense_record(self, data, expense_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        user_id = None
        if data["user_name"]:
            c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
            row = c.fetchone()
            if not row:
                conn.close()
                return False, "Selected user was not found."
            user_id = row["id"]
        if expense_id:
            c.execute(
                """
                UPDATE expenses
                SET expense_date = ?, amount = ?, vendor = ?, description = ?, category = ?, user_id = ?
                WHERE id = ?
                """,
                (
                    data["expense_date"],
                    data["amount"],
                    data["vendor"],
                    data["description"],
                    data["category"],
                    user_id,
                    expense_id,
                ),
            )
            action = "UPDATE"
            message = "Expense updated"
        else:
            c.execute(
                """
                INSERT INTO expenses (expense_date, amount, vendor, description, category, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    data["expense_date"],
                    data["amount"],
                    data["vendor"],
                    data["description"],
                    data["category"],
                    user_id,
                ),
            )
            expense_id = c.lastrowid
            action = "INSERT"
            message = "Expense added"
        conn.commit()
        conn.close()
        try:
            self.db.log_audit_conditional(action, "expenses", expense_id, f"{data['vendor']} - {format_currency(data['amount'])}", data["user_name"] or None)
        except Exception:
            pass
        return True, message

    def _show_info_message(self, title, message):
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        box.open()

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("Select")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "all":
            self.clear_date_filter()
            return
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.apply_filters()

    def apply_date_filter(self):
        start_date = None
        end_date = None
        start_text = self.from_edit.text().strip()
        end_text = self.to_edit.text().strip()
        if start_text:
            try:
                start_date = parse_date_input(start_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid start date.")
                return
        if end_text:
            try:
                end_date = parse_date_input(end_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid end date.")
                return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (
            start_date.strftime("%Y-%m-%d") if start_date else None,
            end_date.strftime("%Y-%m-%d") if end_date else None,
        )
        self.apply_filters()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.apply_filters()

    def export_csv(self):
        import csv

        default_name = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Expenses",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        headers = [
            self.table.horizontalHeaderItem(i).text()
            for i in range(self.table.columnCount())
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in self.filtered_rows:
                writer.writerow(row["display"])


class GameSessionsTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr, on_data_changed=None, main_window=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.main_window = main_window
        self.all_rows = []
        self.filtered_rows = []
        self.header_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self.active_date_filter = (None, None)
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QtWidgets.QPushButton("Start Session")
        self.view_btn = QtWidgets.QPushButton("View Session")
        self.end_btn = QtWidgets.QPushButton("End Session")
        self.edit_btn = QtWidgets.QPushButton("Edit Session")
        self.delete_btn = QtWidgets.QPushButton("Delete Session")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.active_label = QtWidgets.QLabel("Active Sessions: 0")
        self.add_btn.setObjectName("PrimaryButton")
        self.view_btn.setVisible(False)
        self.end_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.end_btn)
        actions.addWidget(self.view_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        actions.addWidget(self.active_label)
        layout.addLayout(actions)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search sessions...")
        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.columns = [
            "Date/Time",
            "Site",
            "User",
            "Game Type",
            "Game",
            "Start SC",
            "End SC",
            "Start Redeem",
            "End Redeem",
            "Δ Redeem",
            "Δ Basis",
            "Net P/L",
            "Status",
            "Notes",
        ]

        self.table = QtWidgets.QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_selected)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

        self.add_btn.clicked.connect(self._add_session)
        self.view_btn.clicked.connect(self._view_selected)
        self.end_btn.clicked.connect(self._end_selected)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.export_btn.clicked.connect(self.export_csv)
        self.refresh_btn.clicked.connect(self.load_data)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))

        self._update_action_visibility()
        self.load_data()

    def _fetch_lookup_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users WHERE active = 1 ORDER BY name")
        users = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM sites WHERE active = 1 ORDER BY name")
        sites = [r["name"] for r in c.fetchall()]
        c.execute("SELECT name FROM game_types WHERE active = 1 ORDER BY name")
        game_types = [r["name"] for r in c.fetchall()]
        c.execute(
            """
            SELECT g.name as game_name, gt.name as type_name
            FROM games g
            LEFT JOIN game_types gt ON g.game_type_id = gt.id
            WHERE g.active = 1
            ORDER BY g.name
            """
        )
        game_names_by_type = {}
        for row in c.fetchall():
            type_name = row["type_name"] or "Other"
            game_names_by_type.setdefault(type_name, []).append(row["game_name"])
        conn.close()
        return users, sites, game_types, game_names_by_type

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT 
                gs.id,
                gs.session_date,
                COALESCE(gs.start_time,'00:00:00') as start_time,
                COALESCE(gs.end_date, gs.session_date) as end_date,
                COALESCE(gs.end_time,'00:00:00') as end_time,
                s.name as site_name,
                u.name as user_name,
                gs.game_type,
                gs.game_name,
                gs.wager_amount,
                gs.rtp,
                COALESCE(gs.starting_sc_balance,0) as starting_total,
                COALESCE(gs.ending_sc_balance,0) as ending_total,
                COALESCE(gs.starting_redeemable_sc, COALESCE(gs.starting_sc_balance,0)) as starting_redeem,
                COALESCE(gs.ending_redeemable_sc, COALESCE(gs.ending_sc_balance,0)) as ending_redeem,
                gs.delta_total,
                gs.delta_redeem,
                COALESCE(gs.basis_consumed, gs.session_basis) as basis_consumed,
                COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) as net_pl,
                gs.status,
                gs.notes
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            ORDER BY gs.session_date DESC, gs.start_time DESC
            """
        )
        self.all_rows = []
        active_count = 0
        for row in c.fetchall():
            status = row["status"] or "Active"
            if status != "Closed":
                active_count += 1

            time_value = row["start_time"] or "00:00:00"
            dt_value = None
            try:
                dt_value = datetime.strptime(
                    f"{row['session_date']} {time_value}", "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                dt_value = None

            display_date = row["session_date"] or ""
            try:
                display_date = datetime.strptime(display_date, "%Y-%m-%d").strftime("%m/%d/%y")
            except Exception:
                pass
            date_time_str = display_date
            if time_value:
                date_time_str = f"{display_date} {time_value[:5]}"

            if status == "Closed" and row["end_date"] and row["session_date"]:
                try:
                    start_date = datetime.strptime(row["session_date"], "%Y-%m-%d").date()
                    end_date = datetime.strptime(row["end_date"], "%Y-%m-%d").date()
                    day_span = (end_date - start_date).days
                    if day_span > 0:
                        date_time_str = f"{date_time_str} (+{day_span}d)"
                except Exception:
                    pass

            start_total = float(row["starting_total"] or 0)
            end_total = float(row["ending_total"] or 0)
            start_redeem = float(row["starting_redeem"] or 0)
            end_redeem = float(row["ending_redeem"] or 0)

            if status == "Closed":
                end_total_display = f"{end_total:.2f}"
                end_redeem_display = f"{end_redeem:.2f}"
                delta_total = (
                    float(row["delta_total"])
                    if row["delta_total"] is not None
                    else end_total - start_total
                )
                delta_redeem = (
                    float(row["delta_redeem"])
                    if row["delta_redeem"] is not None
                    else end_redeem - start_redeem
                )
                delta_total_str = f"{delta_total:+.2f}"
                delta_redeem_str = f"{delta_redeem:+.2f}"
                basis_val = row["basis_consumed"]
                basis_display = format_currency(basis_val) if basis_val is not None else "-"
                net_val = float(row["net_pl"] or 0.0)
                net_display = f"+${net_val:.2f}" if net_val >= 0 else f"${net_val:.2f}"
            else:
                end_total_display = "-"
                end_redeem_display = "-"
                delta_total = None
                delta_redeem = None
                delta_total_str = "-"
                delta_redeem_str = "-"
                basis_display = "-"
                net_val = None
                net_display = "-"

            notes = row["notes"] or ""
            notes_display = notes[:120]

            display = [
                date_time_str,
                row["site_name"],
                row["user_name"],
                row["game_type"] or "",
                row["game_name"] or "",
                f"{start_total:.2f}",
                end_total_display,
                f"{start_redeem:.2f}",
                end_redeem_display,
                delta_redeem_str,
                basis_display,
                net_display,
                status,
                notes_display,
            ]

            if status == "Closed":
                tag = "win" if net_val is not None and net_val >= 0 else "loss"
            else:
                tag = "active"

            self.all_rows.append(
                {
                    "id": row["id"],
                    "session_date": row["session_date"],
                    "start_time": time_value,
                    "session_dt": dt_value,
                    "site_name": row["site_name"],
                    "user_name": row["user_name"],
                    "game_type": row["game_type"] or "",
                    "game_name": row["game_name"] or "",
                    "wager_amount": row["wager_amount"],
                    "rtp": row["rtp"],
                    "start_total": start_total,
                    "end_total": end_total if status == "Closed" else None,
                    "start_redeem": start_redeem,
                    "end_redeem": end_redeem if status == "Closed" else None,
                    "delta_total": delta_total,
                    "delta_redeem": delta_redeem,
                    "basis_consumed": row["basis_consumed"],
                    "net_pl": net_val,
                    "status": status,
                    "notes": notes,
                    "tag": tag,
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self._update_active_label(active_count)
        self.apply_filters()

    def _update_active_label(self, count):
        if count > 0:
            self.active_label.setText(f"Active Sessions: {count}")
            self.active_label.setStyleSheet("color: #2e7d32;")
        else:
            self.active_label.setText("Active Sessions: 0")
            self.active_label.setStyleSheet("color: #62636c;")

    def apply_filters(self):
        rows = self._filter_rows()
        rows = self.sort_rows(rows)
        self.filtered_rows = rows
        self.refresh_table(rows)

    def _filter_rows(self, exclude_col=None):
        rows = list(self.all_rows)
        start_date, end_date = self.active_date_filter
        if start_date:
            rows = [r for r in rows if r["session_date"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["session_date"] <= end_date]

        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in rows if term in r["search_blob"]]

        for col, values in self.header_filters.items():
            if col == exclude_col:
                continue
            if values:
                rows = [r for r in rows if r["display"][col] in values]
        return rows

    def refresh_table(self, rows):
        numeric_cols = {5, 6, 7, 8, 9, 10, 11}
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            status_tag = row["tag"]
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in numeric_cols:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, row["id"])
                if status_tag == "win":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#2e7d32")))
                elif status_tag == "loss":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                elif status_tag == "active":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#1d2e5c")))
                self.table.setItem(r_idx, c_idx, item)
        self._update_action_visibility()

    def eventFilter(self, obj, event):
        if getattr(self, "header", None) and obj is self.header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(self.header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(self.header, pos) is not None:
                    return False
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _update_action_visibility(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        single_selected = len(selected) == 1
        multi_selected = len(selected) > 1
        self.view_btn.setVisible(single_selected)
        self.edit_btn.setVisible(single_selected)
        self.delete_btn.setVisible(has_selection)
        show_end = False
        if single_selected:
            status_item = self.table.item(selected[0].row(), self.columns.index("Status"))
            if status_item and status_item.text() == "Active":
                show_end = True
        self.end_btn.setVisible(show_end and not multi_selected)
        if multi_selected:
            self.end_btn.setVisible(False)

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_visibility()

    def sort_rows(self, rows):
        if self.sort_column is None:
            return rows
        reverse = self.sort_order == QtCore.Qt.DescendingOrder

        def sort_key(row):
            col = self.sort_column
            if col == 0:
                return row["session_dt"] or datetime.min
            if col == 1:
                return row["site_name"].lower()
            if col == 2:
                return row["user_name"].lower()
            if col == 3:
                return row["game_type"].lower()
            if col == 4:
                return row["game_name"].lower()
            if col == 5:
                return row["start_total"]
            if col == 6:
                return row["end_total"] or 0.0
            if col == 7:
                return row["start_redeem"]
            if col == 8:
                return row["end_redeem"] or 0.0
            if col == 9:
                return row["delta_redeem"] if row["delta_redeem"] is not None else 0.0
            if col == 10:
                return row["basis_consumed"] if row["basis_consumed"] is not None else 0.0
            if col == 11:
                return row["net_pl"] if row["net_pl"] is not None else 0.0
            if col == 12:
                return row["status"].lower()
            if col == 13:
                return row["notes"].lower()
            return row["display"][col]

        return sorted(rows, key=sort_key, reverse=reverse)

    def _show_header_menu(self, col_index):
        header = self.table.horizontalHeader()
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        pos_x = header.sectionPosition(col_index)
        pos = header.mapToGlobal(QtCore.QPoint(pos_x, header.height()))
        action = menu.exec(pos)
        if action == sort_asc:
            self.set_sort(col_index, QtCore.Qt.AscendingOrder)
        elif action == sort_desc:
            self.set_sort(col_index, QtCore.Qt.DescendingOrder)
        elif action == clear_sort:
            self.clear_sort()
        elif action == filter_action:
            filter_rows = self._filter_rows(exclude_col=col_index)
            values = sorted({r["display"][col_index] for r in filter_rows})
            selected = self.header_filters.get(col_index, set())
            if col_index == 0:
                dialog = DateTimeFilterDialog(values, selected, self)
            else:
                dialog = ColumnFilterDialog(values, selected, self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                selected_values = dialog.selected_values()
                if selected_values:
                    self.header_filters[col_index] = selected_values
                else:
                    self.header_filters.pop(col_index, None)
                self.apply_filters()

    def set_sort(self, column, order):
        self.sort_column = column
        self.sort_order = order
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, order)
        self.apply_filters()

    def clear_sort(self):
        self.sort_column = None
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        self.apply_filters()

    def clear_all_filters(self):
        self.header_filters = {}
        self.search_edit.clear()
        self.clear_sort()
        self.clear_date_filter()
        self._clear_selection()

    def apply_date_filter(self):
        from_text = self.from_edit.text().strip()
        to_text = self.to_edit.text().strip()
        start_date = None
        end_date = None
        try:
            if from_text:
                start_date = parse_date_input(from_text).strftime("%Y-%m-%d")
            if to_text:
                end_date = parse_date_input(to_text).strftime("%Y-%m-%d")
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid Date", "Please enter a valid date.")
            return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (start_date, end_date)
        self.apply_filters()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.apply_filters()

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            self.clear_date_filter()
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.apply_filters()

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _add_session(self):
        users, sites, game_types, game_names_by_type = self._fetch_lookup_data()
        dialog = GameSessionStartDialog(
            self.db,
            self.session_mgr,
            users,
            sites,
            game_types,
            game_names_by_type,
            parent=self,
        )

        def handle_save():
            self._save_start_session(dialog, None)

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _fetch_session(self, session_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT gs.*, s.name as site_name, u.name as user_name
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
            """,
            (session_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def _validate_game_name(self, game_type, game_name):
        name = (game_name or "").strip()
        if not name:
            return None, ""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT g.name, gt.name as type_name
            FROM games g
            LEFT JOIN game_types gt ON g.game_type_id = gt.id
            WHERE lower(g.name) = ?
              AND g.active = 1
            """,
            (name.lower(),),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return (
                "Game name not found. Add it in Setup → Games, then return and save again.",
                None,
            )
        type_name = (row["type_name"] or "Other").strip()
        if game_type and type_name.lower() != game_type.lower():
            return (
                "Game name not found for the selected Game Type. Add it in Setup → Games, then return and save again.",
                None,
            )
        return None, row["name"]

    def _validate_game_type(self, game_type):
        name = (game_type or "").strip()
        if not name:
            return None, ""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT name FROM game_types WHERE lower(name) = ? AND active = 1",
            (name.lower(),),
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return (
                "Game Type not found. Add it in Setup → Game Types, then return and save again.",
                None,
            )
        return None, row["name"]

    def _edit_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a session to edit.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(self, "Multiple Selection", "Select one session to edit.")
            return
        self.edit_session_by_id(selected_ids[0])

    def edit_session_by_id(self, session_id):
        session = self._fetch_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return

        users, sites, game_types, game_names_by_type = self._fetch_lookup_data()
        if session["status"] == "Closed":
            dialog = GameSessionEditDialog(
                self.db,
                self.session_mgr,
                users,
                sites,
                game_types,
                game_names_by_type,
                session,
                parent=self,
            )

            def handle_save():
                self._save_closed_session(dialog, session)

            dialog.save_btn.clicked.connect(handle_save)
            dialog.exec()
        else:
            dialog = GameSessionStartDialog(
                self.db,
                self.session_mgr,
                users,
                sites,
                game_types,
                game_names_by_type,
                session=session,
                parent=self,
            )

            def handle_save():
                self._save_start_session(dialog, session_id)

            dialog.save_btn.clicked.connect(handle_save)
            dialog.exec()

    def _view_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a session to view.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(self, "Multiple Selection", "Select one session to view.")
            return
        session_id = selected_ids[0]
        self.view_session_by_id(session_id)

    def _save_start_session(self, dialog, session_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return

        user_name = data["user_name"]
        site_name = data["site_name"]
        session_date = data["session_date"]
        start_time = data["start_time"]
        start_total = data["starting_total_sc"]
        start_redeem = data["starting_redeemable_sc"]
        game_type = data["game_type"]
        game_name = data["game_name"]
        wager_amount = data["wager_amount"]
        notes = data["notes"]

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM sites WHERE name = ?", (site_name,))
        site_row = c.fetchone()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not site_row or not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", "User or site not found.")
            return
        site_id = site_row["id"]
        user_id = user_row["id"]

        type_error, canonical_type = self._validate_game_type(game_type)
        if type_error:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", type_error)
            return
        game_type = canonical_type

        game_error, canonical_game = self._validate_game_name(game_type, game_name)
        if game_error:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", game_error)
            return
        game_name = canonical_game

        if session_id:
            c.execute(
                """
                SELECT id FROM game_sessions
                WHERE site_id = ? AND user_id = ? AND status = 'Active' AND id != ?
                """,
                (site_id, user_id, session_id),
            )
            if c.fetchone():
                conn.close()
                QtWidgets.QMessageBox.warning(
                    self,
                    "Active Session Exists",
                    "Another active session already exists for this site and user.",
                )
                return
            # Get old site/user/date/time BEFORE update for recalculation
            c.execute("SELECT site_id, user_id, session_date, start_time FROM game_sessions WHERE id = ?", (session_id,))
            old_session_data = c.fetchone()
            old_site_id = old_session_data["site_id"] if old_session_data else site_id
            old_user_id = old_session_data["user_id"] if old_session_data else user_id
            old_date = old_session_data["session_date"] if old_session_data else session_date
            old_time = old_session_data["start_time"] if old_session_data else start_time

            c.execute(
                """
                UPDATE game_sessions
                SET session_date=?, start_time=?, site_id=?, user_id=?,
                    game_type=?, game_name=?, wager_amount=?,
                    starting_sc_balance=?, starting_redeemable_sc=?, notes=?
                WHERE id=?
                """,
                (
                    session_date,
                    start_time,
                    site_id,
                    user_id,
                    game_type,
                    game_name,
                    wager_amount,
                    start_total,
                    start_redeem,
                    notes,
                    session_id,
                ),
            )

            conn.commit()
            conn.close()

            # Recalculate for both old and new (site, user) if changed
            pairs = {
                (site_id, user_id, session_date, start_time),
                (old_site_id, old_user_id, old_date, old_time),
            }
            total_recalc = 0
            for s_id, u_id, sdate, stime in pairs:
                total_recalc += self.session_mgr.auto_recalculate_affected_sessions(s_id, u_id, sdate, stime)

            dialog.accept()
            self.load_data()
            if self.on_data_changed:
                self.on_data_changed()

            message = "Session updated"
            if total_recalc:
                message += f" (recalculated {total_recalc} sessions)"
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(self, "Success", message)
            )
            return

        c.execute(
            """
            SELECT id, session_date, start_time, starting_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Active'
            LIMIT 1
            """,
            (site_id, user_id),
        )
        existing_session = c.fetchone()
        if existing_session:
            conn.close()
            QtWidgets.QMessageBox.warning(
                self,
                "Active Session Exists",
                "You already have an active session for this site and user. End it first.",
            )
            return

        expected_total, _expected_redeemable = self.session_mgr.compute_expected_balances(
            site_id, user_id, session_date, start_time
        )
        if start_total < expected_total:
            deficit = expected_total - start_total
            response = QtWidgets.QMessageBox.question(
                self,
                "Starting Balance Warning",
                f"Starting SC ({start_total:.2f}) is {deficit:.2f} less than expected ({expected_total:.2f}).\n\n"
                "This usually means a missing redemption, an untracked loss, or a data entry error.\n\n"
                f"This will create a negative starting delta of -{deficit:.2f} SC.\n\n"
                "Continue anyway?",
            )
            if response != QtWidgets.QMessageBox.Yes:
                conn.close()
                return

        conn.close()

        try:
            session_id, freebies_amount, _reactivated_count, reactivated_basis = (
                self.session_mgr.start_game_session(
                    site_id,
                    user_id,
                    game_type,
                    start_total,
                    start_redeem,
                    session_date,
                    notes,
                    start_time,
                )
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to start session: {exc}")
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            UPDATE game_sessions
            SET game_name=?, wager_amount=?
            WHERE id=?
            """,
            (game_name, wager_amount, session_id),
        )
        conn.commit()
        conn.close()

        message_parts = ["Session started!"]
        if reactivated_basis and reactivated_basis > 0:
            message_parts.append(f"\n\nRecovered ${reactivated_basis:.2f} from dormant balance")
        if freebies_amount and freebies_amount > 0:
            message_parts.append(f"\nDetected ${freebies_amount:.2f} in extra SC")
        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        QtCore.QTimer.singleShot(
            0, lambda: QtWidgets.QMessageBox.information(self, "Success", "".join(message_parts))
        )

    def _end_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select an active session to end.")
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(self, "Multiple Selection", "Select one active session to end.")
            return
        session_id = selected_ids[0]
        session = self._fetch_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return
        if session["status"] != "Active":
            QtWidgets.QMessageBox.warning(self, "Not Active", "This session is already closed.")
            return

        dialog = GameSessionEndDialog(session, parent=self)

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                pnl = self.session_mgr.end_game_session(
                    session_id,
                    data["ending_total_sc"],
                    data["ending_redeemable_sc"],
                    notes=data["notes"] or None,
                    end_date=data["end_date"],
                    end_time=data["end_time"],
                )
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Error", f"Failed to end session: {exc}")
                return

            if data.get("wager_amount") is not None:
                conn = self.db.get_connection()
                c = conn.cursor()
                c.execute(
                    "UPDATE game_sessions SET wager_amount = ? WHERE id = ?",
                    (data["wager_amount"], session_id),
                )
                conn.commit()
                conn.close()

            dialog.accept()
            self.load_data()
            if self.on_data_changed:
                self.on_data_changed()
            if pnl >= 0:
                message = f"Session ended!\n\nProfit: +${pnl:.2f}"
            else:
                message = f"Session ended!\n\nLoss: ${pnl:.2f}"
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(self, "Success", message)
            )

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _save_closed_session(self, dialog, old_session):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM sites WHERE name = ?", (data["site_name"],))
        site_row = c.fetchone()
        c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
        user_row = c.fetchone()
        if not site_row or not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", "User or site not found.")
            return
        type_error, canonical_type = self._validate_game_type(data["game_type"])
        if type_error:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", type_error)
            return
        data["game_type"] = canonical_type
        game_error, canonical_game = self._validate_game_name(data["game_type"], data["game_name"])
        if game_error:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Not Found", game_error)
            return
        data["game_name"] = canonical_game
        new_site_id = site_row["id"]
        new_user_id = user_row["id"]
        old_site_id = old_session["site_id"]
        old_user_id = old_session["user_id"]
        old_date = old_session["session_date"]
        old_time = old_session["start_time"] or "00:00:00"
        
        # Look up game_id from game_name
        new_game_id = None
        if data["game_name"]:
            c.execute("SELECT id FROM games WHERE name = ?", (data["game_name"],))
            game_row = c.fetchone()
            if game_row:
                new_game_id = game_row["id"]

        # Capture old values for RTP delta calculation
        old_session_values = {
            'session_id': old_session['id'],
            'wager_amount': old_session['wager_amount'] if 'wager_amount' in old_session.keys() else None,
            'delta_total': old_session['delta_total'] if 'delta_total' in old_session.keys() else None,
            'game_id': old_session['game_id'] if 'game_id' in old_session.keys() else None,
            'id': old_session['id'],
            'notes': old_session['notes'] if 'notes' in old_session.keys() else None
        }
        
        # Build new values dict for comparison
        # Calculate delta_total that will be saved
        calculated_delta_total = data["ending_total_sc"] - data["starting_total_sc"]
        
        new_session_values = {
            'wager_amount': data["wager_amount"],
            'delta_total': calculated_delta_total,
            'game_id': new_game_id,
            'notes': data["notes"],
            'starting_total_sc': data["starting_total_sc"],
            'starting_redeemable_sc': data["starting_redeemable_sc"],
            'ending_total_sc': data["ending_total_sc"],
            'ending_redeemable_sc': data["ending_redeemable_sc"],
            'session_date': data["session_date"],
            'end_date': data["end_date"],
            'start_time': data["start_time"],
            'end_time': data["end_time"],
            'site_id': new_site_id,
            'user_id': new_user_id
        }
        
        # RTP-only pre-check (Layer 1 optimization)
        changed_fields = {k for k in old_session_values if k in new_session_values and old_session_values.get(k) != new_session_values.get(k)}
        
        # Notes-only change - skip recomputation entirely
        if changed_fields == {'notes'}:
            if data["end_date"] < data["session_date"]:
                conn.close()
                QtWidgets.QMessageBox.warning(self, "Invalid Dates", "End date is before start date.")
                return
            
            c.execute(
                """
                UPDATE game_sessions
                SET notes=?
                WHERE id=?
                """,
                (data["notes"], old_session["id"]),
            )
            conn.commit()
            conn.close()
            
            dialog.accept()
            self.load_data()
            if self.on_data_changed:
                self.on_data_changed()
            
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(self, "Success", "Session notes updated (no recalculation needed)")
            )
            return
        
        # RTP-only change - update RTP directly without full rebuild
        rtp_only_fields = {'wager_amount', 'game_id'}
        if changed_fields and changed_fields <= rtp_only_fields:
            if data["end_date"] < data["session_date"]:
                conn.close()
                QtWidgets.QMessageBox.warning(self, "Invalid Dates", "End date is before start date.")
                return
            
            # Calculate delta_total (may have changed if balances were also edited)
            delta_total = data["ending_total_sc"] - data["starting_total_sc"]
            
            # Calculate RTP: (wager + delta_total) / wager * 100
            wager = data["wager_amount"]
            if wager and float(wager) > 0:
                rtp = ((float(wager) + delta_total) / float(wager)) * 100
            else:
                rtp = None
            
            c.execute(
                """
                UPDATE game_sessions
                SET wager_amount=?,
                    game_id=?,
                    game_name=?,
                    delta_total=?,
                    rtp=?
                WHERE id=?
                """,
                (wager, new_game_id, data["game_name"], delta_total, rtp, old_session["id"]),
            )
            conn.commit()
            conn.close()
            
            # Update RTP aggregates
            self.session_mgr._update_session_rtp_only(old_session["id"], old_session_values, new_session_values)
            
            dialog.accept()
            self.load_data()
            if self.on_data_changed:
                self.on_data_changed()
            
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(self, "Success", "Session updated (RTP-only, fast path)")
            )
            return

        if data["end_date"] < data["session_date"]:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid Dates", "End date is before start date.")
            return

        c.execute(
            """
            UPDATE game_sessions
            SET session_date=?,
                end_date=?,
                start_time=?,
                end_time=?,
                site_id=?,
                user_id=?,
                game_type=?,
                game_name=?,
                wager_amount=?,
                starting_sc_balance=?,
                starting_redeemable_sc=?,
                ending_sc_balance=?,
                ending_redeemable_sc=?,
                notes=?
            WHERE id=?
            """,
            (
                data["session_date"],
                data["end_date"],
                data["start_time"],
                data["end_time"],
                new_site_id,
                new_user_id,
                data["game_type"],
                data["game_name"],
                data["wager_amount"],
                data["starting_total_sc"],
                data["starting_redeemable_sc"],
                data["ending_total_sc"],
                data["ending_redeemable_sc"],
                data["notes"],
                old_session["id"],
            ),
        )
        conn.commit()
        conn.close()

        # Scoped recalculation using new API
        # If site/user changed, recalculate both pairs
        if (new_site_id, new_user_id) != (old_site_id, old_user_id):
            # Old pair: remove old timestamp
            total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                old_site_id, old_user_id,
                old_ts=(old_date, old_time),
                new_ts=None,
                scoped=True,
                entity_type='session',
                old_values=old_session_values,
                new_values=new_session_values
            )
            # New pair: add new timestamp
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                new_site_id, new_user_id,
                old_ts=None,
                new_ts=(data["session_date"], data["start_time"]),
                scoped=True,
                entity_type='session',
                old_values=old_session_values,
                new_values=new_session_values
            )
        else:
            # Same pair: use both timestamps
            total_recalc = self.session_mgr.auto_recalculate_affected_sessions(
                new_site_id, new_user_id,
                old_ts=(old_date, old_time),
                new_ts=(data["session_date"], data["start_time"]),
                old_session_values=old_session_values,
                scoped=True,
                entity_type='session',
                old_values=old_session_values,
                new_values=new_session_values
            )

        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        message = "Session updated"
        if total_recalc:
            message += f" (recalculated {total_recalc} sessions via scoped rebuild)"
        QtCore.QTimer.singleShot(
            0, lambda: QtWidgets.QMessageBox.information(self, "Success", message)
        )

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def select_session_by_id(self, session_id):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == session_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                self._update_action_visibility()
                return True
        return False

    def view_session_by_id(self, session_id):
        session = self._fetch_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return
        
        # Debug: Check status
        print(f"DEBUG: Session {session_id} status = {session['status']}")
        print(f"DEBUG: main_window = {self.main_window}")
        
        # Create callback for View in Daily Sessions if main_window is available
        view_in_daily_callback = None
        if self.main_window:
            view_in_daily_callback = lambda: self.main_window.view_session_in_daily(session_id)
            print(f"DEBUG: view_in_daily_callback created")
        
        dialog = GameSessionViewDialog(
            session,
            parent=self,
            on_open_purchase=lambda pid: self.main_window.open_purchase(pid) if self.main_window else None,
            on_open_redemption=lambda rid: self.main_window.open_redemption(rid) if self.main_window else None,
            on_edit=lambda: self.edit_session_by_id(session_id),
            on_delete=lambda: self._delete_session_by_id(session_id),
            on_view_in_daily=view_in_daily_callback
        )
        dialog.exec()

    def _delete_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select session(s) to delete.")
            return
        if len(selected_ids) > 1:
            confirm = QtWidgets.QMessageBox.question(
                self, "Confirm", f"Delete {len(selected_ids)} sessions?"
            )
        else:
            confirm = QtWidgets.QMessageBox.question(self, "Confirm", "Delete this session?")
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted_count = 0
        error_messages = []
        affected = set()

        for session_id in selected_ids:
            c.execute(
                """
                SELECT gs.*, s.name as site_name, u.name as user_name
                FROM game_sessions gs
                JOIN sites s ON gs.site_id = s.id
                JOIN users u ON gs.user_id = u.id
                WHERE gs.id = ?
                """,
                (session_id,),
            )
            session = c.fetchone()
            if not session:
                error_messages.append(f"Session ID {session_id} not found.")
                continue

            session_date = session["session_date"]
            start_time = session["start_time"] or "00:00:00"
            affected.add((session["site_id"], session["user_id"], session_date, start_time))

            # Remove session's contribution from game RTP if it has game_id
            if session['game_id']:
                self.session_mgr.remove_session_from_game_rtp(
                    session['game_id'],
                    session['wager_amount'],
                    session['delta_total']
                )

            c.execute("DELETE FROM other_income WHERE game_session_id = ?", (session_id,))
            c.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
            deleted_count += 1

        conn.commit()
        conn.close()

        total_recalc = 0
        for site_id, user_id, sdate, stime in affected:
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, sdate, stime)

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        if error_messages:
            message = f"Deleted {deleted_count} session(s)."
            if total_recalc > 0:
                message += f" Recalculated {total_recalc} session{'s' if total_recalc != 1 else ''}."
            message += "\n\nErrors:\n" + "\n".join(error_messages)
            QtWidgets.QMessageBox.warning(self, "Partial Success", message)
        else:
            message = f"Deleted {deleted_count} session{'s' if deleted_count != 1 else ''}"
            if total_recalc > 0:
                message += f" (recalculated {total_recalc} session{'s' if total_recalc != 1 else ''})"
            QtWidgets.QMessageBox.information(self, "Success", message)

    def _delete_session_by_id(self, session_id):
        """Delete a single session by ID (called from View dialog)"""
        # Select the row and call existing delete logic (which will show confirmation)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == session_id:
                self.table.selectRow(row)
                break
        self._delete_selected()

    def export_csv(self):
        import csv

        default_name = f"game_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Game Sessions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        headers = [
            self.table.horizontalHeaderItem(i).text()
            for i in range(self.table.columnCount())
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in self.filtered_rows:
                writer.writerow(row["display"])


class DailySessionsTab(QtWidgets.QWidget):
    def __init__(
        self,
        db,
        session_mgr,
        on_data_changed=None,
        on_open_session=None,
        on_edit_session=None,
        on_delete_session=None,
        on_open_purchase=None,
        on_open_redemption=None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.on_open_session = on_open_session
        self.on_edit_session = on_edit_session
        self.on_delete_session = on_delete_session
        self.on_open_purchase = on_open_purchase
        self.on_open_redemption = on_open_redemption
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter = set()
        self.column_filters = {}
        self.sort_column = None
        self.sort_reverse = False
        self._last_sessions = []
        self.columns = [
            "Date/User/Session",
            "Game Type",
            "Game",
            "Start SC",
            "End SC",
            "Start Redeem",
            "End Redeem",
            "Δ Redeem",
            "Δ Basis",
            "Δ Total (SC)",
            "Net P/L",
            "Details",
            "Notes",
        ]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_btn)
        date_row.addWidget(self.clear_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(QtWidgets.QLabel("Users"))
        self.user_filter_btn = QtWidgets.QPushButton("Filter Users...")
        filter_row.addWidget(self.user_filter_btn)
        self.user_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.user_filter_label, set())
        filter_row.addWidget(self.user_filter_label)
        filter_row.addSpacing(12)
        filter_row.addWidget(QtWidgets.QLabel("Sites"))
        self.site_filter_btn = QtWidgets.QPushButton("Filter Sites...")
        filter_row.addWidget(self.site_filter_btn)
        self.site_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.site_filter_label, set())
        filter_row.addWidget(self.site_filter_label)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search daily sessions...")
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addStretch(1)
        self.notes_btn = QtWidgets.QPushButton("Add Notes")
        self.notes_btn.setObjectName("PrimaryButton")
        self.view_btn = QtWidgets.QPushButton("View Session")
        dynamic_width = max(self.notes_btn.sizeHint().width(), self.view_btn.sizeHint().width())
        for btn in (self.notes_btn, self.view_btn):
            btn.setFixedWidth(dynamic_width)
        self.primary_btn_placeholder = QtWidgets.QWidget()
        self.primary_btn_placeholder.setFixedWidth(dynamic_width)
        self.primary_btn_placeholder.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.primary_btn_container = QtWidgets.QWidget()
        self.primary_btn_container.setFixedWidth(dynamic_width)
        self.primary_btn_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.primary_btn_stack = QtWidgets.QStackedLayout(self.primary_btn_container)
        self.primary_btn_stack.setContentsMargins(0, 0, 0, 0)
        self.primary_btn_stack.addWidget(self.primary_btn_placeholder)
        self.primary_btn_stack.addWidget(self.notes_btn)
        self.primary_btn_stack.addWidget(self.view_btn)
        self.primary_btn_stack.setCurrentWidget(self.primary_btn_placeholder)
        self.expand_btn = QtWidgets.QPushButton("Expand All")
        self.collapse_btn = QtWidgets.QPushButton("Collapse All")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        for btn in (
            self.expand_btn,
            self.collapse_btn,
            self.refresh_btn,
            self.export_btn,
        ):
            btn.setFixedWidth(btn.sizeHint().width())
        self.actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.primary_btn_container)
        actions_layout.addWidget(self.expand_btn)
        actions_layout.addWidget(self.collapse_btn)
        actions_layout.addWidget(self.refresh_btn)
        actions_layout.addWidget(self.export_btn)
        total_width = dynamic_width + sum(btn.sizeHint().width() for btn in (
            self.expand_btn,
            self.collapse_btn,
            self.refresh_btn,
            self.export_btn,
        ))
        total_width += actions_layout.spacing() * 4
        self.actions_container.setFixedWidth(total_width)
        self.actions_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        search_row.addWidget(self.actions_container, 0, QtCore.Qt.AlignRight)
        layout.addLayout(search_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumSize(0, 0)
        self.tree.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
        )
        self.tree.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        header = self.tree.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 110)
        self.tree.setColumnWidth(2, 140)
        self.tree.setColumnWidth(3, 80)
        self.tree.setColumnWidth(4, 80)
        self.tree.setColumnWidth(5, 90)
        self.tree.setColumnWidth(6, 90)
        self.tree.setColumnWidth(7, 80)
        self.tree.setColumnWidth(8, 90)
        self.tree.setColumnWidth(9, 90)
        self.tree.setColumnWidth(10, 90)
        self.tree.setColumnWidth(11, 150)
        self.tree.setColumnWidth(12, 200)
        header.viewport().installEventFilter(self)
        self.tree.itemDoubleClicked.connect(lambda *_args: self.add_edit_notes())
        layout.addWidget(self.tree, 1)

        self.search_edit.textChanged.connect(self.refresh_view)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.notes_btn.clicked.connect(self._handle_notes_clicked)
        self.view_btn.clicked.connect(self._handle_view_clicked)
        self.expand_btn.clicked.connect(self.tree.expandAll)
        self.collapse_btn.clicked.connect(self.tree.collapseAll)
        self.refresh_btn.clicked.connect(self.refresh_view)
        self.export_btn.clicked.connect(self.export_csv)
        self.apply_btn.clicked.connect(self.apply_filters)
        self.clear_btn.clicked.connect(self.clear_filters)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))
        self.user_filter_btn.clicked.connect(self._show_user_filter)
        self.site_filter_btn.clicked.connect(self._show_site_filter)
        self.tree.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh_view()

    def eventFilter(self, obj, event):
        if getattr(self, "tree", None) is not None and obj is self.tree.header().viewport():
            header = self.tree.header()
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.tree.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(header, pos) is not None:
                    return False
                index = header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _set_filter_label(self, label, selected):
        if not selected:
            label.setText("All")
            label.setStyleSheet("color: #62636c;")
        else:
            label.setText(f"{len(selected)} selected")
            label.setStyleSheet("color: #3657c3;")

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("Select")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "all":
            self.from_edit.clear()
            self.to_edit.clear()
            self.active_date_filter = (None, None)
            self.refresh_view()
            return
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.refresh_view()

    def apply_filters(self):
        start_date = None
        end_date = None
        start_text = self.from_edit.text().strip()
        end_text = self.to_edit.text().strip()
        if start_text:
            try:
                start_date = parse_date_input(start_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid start date.")
                return
        if end_text:
            try:
                end_date = parse_date_input(end_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid end date.")
                return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (
            start_date.strftime("%Y-%m-%d") if start_date else None,
            end_date.strftime("%Y-%m-%d") if end_date else None,
        )
        self.refresh_view()

    def clear_filters(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self._set_filter_label(self.user_filter_label, self.selected_users)
        self._set_filter_label(self.site_filter_label, self.selected_sites)
        self._clear_selection()
        self.refresh_view()

    def clear_all_filters(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter = set()
        self.column_filters = {}
        self._set_filter_label(self.user_filter_label, self.selected_users)
        self._set_filter_label(self.site_filter_label, self.selected_sites)
        self.search_edit.clear()
        self._clear_selection()
        self.refresh_view()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.tree.clearSelection()
        self._update_action_buttons()

    def _show_user_filter(self):
        users = self._fetch_lookup("users")
        if not users:
            QtWidgets.QMessageBox.information(self, "No Users", "No users found.")
            return
        dialog = ColumnFilterDialog(users, self.selected_users, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_users = dialog.selected_values()
            self._set_filter_label(self.user_filter_label, self.selected_users)
            self.refresh_view()

    def _show_site_filter(self):
        sites = self._fetch_lookup("sites")
        if not sites:
            QtWidgets.QMessageBox.information(self, "No Sites", "No sites found.")
            return
        dialog = ColumnFilterDialog(sites, self.selected_sites, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_sites = dialog.selected_values()
            self._set_filter_label(self.site_filter_label, self.selected_sites)
            self.refresh_view()

    def _fetch_lookup(self, table_name):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT name FROM {table_name} WHERE active = 1 ORDER BY name")
        values = [row["name"] for row in c.fetchall()]
        conn.close()
        return values

    def _handle_sort(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.refresh_view()

    def refresh_view(self):
        sessions = self._fetch_sessions()
        self._last_sessions = sessions
        sessions = self._filter_sessions(sessions)
        data = self._group_sessions(sessions)
        self._render_tree(data)
        self._update_action_buttons()

    def _current_meta(self):
        item = self.tree.currentItem()
        if not item:
            return None
        return item.data(0, QtCore.Qt.UserRole) or {}

    def _update_action_buttons(self):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        if kind == "date":
            self.primary_btn_stack.setCurrentWidget(self.notes_btn)
        elif kind == "session":
            self.primary_btn_stack.setCurrentWidget(self.view_btn)
        else:
            self.primary_btn_stack.setCurrentWidget(self.primary_btn_placeholder)

    def _handle_notes_clicked(self):
        meta = self._current_meta() or {}
        if meta.get("kind") == "date":
            self._edit_daily_notes(meta.get("date"))

    def _handle_view_clicked(self):
        meta = self._current_meta() or {}
        if meta.get("kind") == "session":
            self._view_session(meta.get("session_id"))

    def _fetch_sessions(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        query = """
            SELECT 
                gs.session_date,
                gs.user_id,
                u.name as user_name,
                gs.site_id,
                s.name as site_name,
                gs.id,
                gs.game_type,
                gs.game_name,
                gs.starting_sc_balance,
                gs.ending_sc_balance,
                COALESCE(gs.start_time, '00:00:00') as start_time,
                COALESCE(gs.end_time, '') as end_time,
                COALESCE(gs.delta_total, gs.ending_sc_balance - gs.starting_sc_balance, 0) as delta_total,
                gs.delta_redeem,
                COALESCE(gs.starting_redeemable_sc, gs.starting_sc_balance) as starting_redeem,
                COALESCE(gs.ending_redeemable_sc, gs.ending_sc_balance) as ending_redeem,
                COALESCE(gs.basis_consumed, gs.session_basis) as basis_consumed,
                COALESCE(gs.net_taxable_pl, gs.total_taxable, 0) as total_taxable,
                gs.notes
            FROM game_sessions gs
            JOIN users u ON gs.user_id = u.id
            JOIN sites s ON gs.site_id = s.id
            WHERE gs.status = 'Closed'
        """
        params = []
        if self.selected_users:
            placeholders = ",".join("?" * len(self.selected_users))
            query += f" AND u.name IN ({placeholders})"
            params.extend(sorted(self.selected_users))
        if self.selected_sites:
            placeholders = ",".join("?" * len(self.selected_sites))
            query += f" AND s.name IN ({placeholders})"
            params.extend(sorted(self.selected_sites))

        start_date, end_date = self.active_date_filter
        if start_date and end_date:
            query += " AND gs.session_date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        elif start_date:
            query += " AND gs.session_date >= ?"
            params.append(start_date)
        elif end_date:
            query += " AND gs.session_date <= ?"
            params.append(end_date)
        else:
            current_year_start = f"{date.today().year}-01-01"
            current_year_end = date.today().strftime("%Y-%m-%d")
            query += " AND gs.session_date BETWEEN ? AND ?"
            params.extend([current_year_start, current_year_end])

        query += " ORDER BY gs.session_date DESC, u.name, s.name, gs.start_time"
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            delta_total = float(row["delta_total"] or 0.0)
            delta_redeem = row["delta_redeem"]
            if delta_redeem is None:
                start_redeem = row["starting_redeem"]
                end_redeem = row["ending_redeem"]
                if start_redeem is not None and end_redeem is not None:
                    delta_redeem = float(end_redeem) - float(start_redeem)
            if delta_redeem is not None:
                delta_redeem = float(delta_redeem)
            basis_consumed = row["basis_consumed"]
            if basis_consumed is not None:
                basis_consumed = float(basis_consumed)
            total_taxable = float(row["total_taxable"] or 0.0)
            notes = row["notes"] or ""
            game_type = row["game_type"] or ""
            game_name = row["game_name"] or ""
            start_total = row["starting_sc_balance"]
            end_total = row["ending_sc_balance"]
            start_redeem = row["starting_redeem"]
            end_redeem = row["ending_redeem"]
            search_blob = " ".join(
                str(value).lower()
                for value in (
                    row["session_date"],
                    row["user_name"],
                    row["site_name"],
                    game_type,
                    game_name,
                    f"{float(start_total):.2f}" if start_total is not None else "",
                    f"{float(end_total):.2f}" if end_total is not None else "",
                    f"{float(start_redeem):.2f}" if start_redeem is not None else "",
                    f"{float(end_redeem):.2f}" if end_redeem is not None else "",
                    f"{delta_total:.2f}",
                    f"{delta_redeem:.2f}" if delta_redeem is not None else "",
                    f"{basis_consumed:.2f}" if basis_consumed is not None else "",
                    f"{total_taxable:.2f}",
                    notes,
                )
                if value is not None
            )
            sessions.append(
                {
                    "id": row["id"],
                    "session_date": row["session_date"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "site_id": row["site_id"],
                    "site_name": row["site_name"],
                    "game_type": game_type,
                    "game_name": game_name,
                    "start_total": start_total,
                    "end_total": end_total,
                    "start_redeem": start_redeem,
                    "end_redeem": end_redeem,
                    "start_time": row["start_time"] or "",
                    "end_time": row["end_time"] or "",
                    "delta_total": delta_total,
                    "delta_redeem": delta_redeem,
                    "basis_consumed": basis_consumed,
                    "total_taxable": total_taxable,
                    "notes": notes,
                    "search_blob": search_blob,
                }
            )
        return sessions

    def _group_sessions(self, sessions):
        from collections import defaultdict

        dates = defaultdict(lambda: defaultdict(list))
        for sess in sessions:
            dates[sess["session_date"]][sess["user_id"]].append(sess)

        notes_by_date = self._fetch_notes_for_dates(dates.keys())
        data = []
        for session_date in sorted(dates.keys(), reverse=True):
            users_data = dates[session_date]
            users = []
            for user_id in sorted(
                users_data.keys(),
                key=lambda uid: users_data[uid][0]["user_name"].lower(),
            ):
                user_sessions = list(users_data[user_id])
                user_sessions.sort(key=lambda s: s["start_time"] or "")
                user_gameplay = sum(sess["delta_total"] for sess in user_sessions)
                user_delta_redeem = sum(sess["delta_redeem"] or 0.0 for sess in user_sessions)
                user_basis = sum(sess["basis_consumed"] or 0.0 for sess in user_sessions)
                user_total = sum(sess["total_taxable"] for sess in user_sessions)
                users.append(
                    {
                        "user_id": user_id,
                        "user_name": user_sessions[0]["user_name"],
                        "gameplay": user_gameplay,
                        "delta_redeem": user_delta_redeem,
                        "basis": user_basis,
                        "total": user_total,
                        "status": "Win" if user_total >= 0 else "Loss",
                        "sessions": user_sessions,
                    }
                )

            date_gameplay = sum(user["gameplay"] for user in users)
            date_delta_redeem = sum(user["delta_redeem"] for user in users)
            date_basis = sum(user["basis"] for user in users)
            date_total = sum(user["total"] for user in users)
            total_sessions = sum(len(user["sessions"]) for user in users)
            data.append(
                {
                    "date": session_date,
                    "date_gameplay": date_gameplay,
                    "date_delta_redeem": date_delta_redeem,
                    "date_basis": date_basis,
                    "date_total": date_total,
                    "status": "Win" if date_total >= 0 else "Loss",
                    "users": users,
                    "user_count": len(users),
                    "session_count": total_sessions,
                    "notes": notes_by_date.get(session_date, ""),
                }
            )

        return self._sort_data(data)

    def _sort_data(self, data):
        if self.sort_column is None:
            return data

        reverse = self.sort_reverse

        def sort_key(item):
            if self.sort_column == 0:
                return item["date"]
            if self.sort_column == 1:
                return item["date"]
            if self.sort_column == 2:
                return item["date"]
            if self.sort_column == 3:
                return item["date"]
            if self.sort_column == 4:
                return item["date"]
            if self.sort_column == 5:
                return item["date"]
            if self.sort_column == 6:
                return item["date"]
            if self.sort_column == 7:
                return item["date_delta_redeem"]
            if self.sort_column == 8:
                return item["date_basis"]
            if self.sort_column == 9:
                return item["date_gameplay"]
            if self.sort_column == 10:
                return item["date_total"]
            if self.sort_column == 11:
                return item["session_count"]
            if self.sort_column == 12:
                return 1 if item["notes"] else 0
            return item["date"]

        return sorted(data, key=sort_key, reverse=reverse)

    def _render_tree(self, data):
        self.tree.clear()
        for day in data:
            date_values = [
                day["date"],
                "",
                "",
                "",
                "",
                "",
                "",
                self._format_delta(day["date_delta_redeem"]),
                self._format_currency_or_dash(day["date_basis"]),
                self._format_delta(day["date_gameplay"]),
                self._format_signed_currency(day["date_total"]),
                f"{day['user_count']} users, {day['session_count']} sessions",
                day["notes"],
            ]
            date_item = QtWidgets.QTreeWidgetItem(date_values)
            date_item.setData(0, QtCore.Qt.UserRole, {"kind": "date", "date": day["date"]})
            self._apply_status_color(date_item, day["date_total"])
            self.tree.addTopLevelItem(date_item)

            for user in day["users"]:
                user_values = [
                    user["user_name"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    self._format_delta(user["delta_redeem"]),
                    self._format_currency_or_dash(user["basis"]),
                    self._format_delta(user["gameplay"]),
                    self._format_signed_currency(user["total"]),
                    f"{len(user['sessions'])} sessions",
                    "",
                ]
                user_item = QtWidgets.QTreeWidgetItem(user_values)
                user_item.setData(
                    0, QtCore.Qt.UserRole, {"kind": "user", "user_id": user["user_id"]}
                )
                self._apply_status_color(user_item, user["total"])
                date_item.addChild(user_item)

                for sess in user["sessions"]:
                    start_time = (sess["start_time"] or "00:00:00")[:5]
                    end_time = sess["end_time"][:5] if sess["end_time"] else ""
                    time_range = f"{start_time}-{end_time}" if end_time else f"{start_time}-Active"
                    sess_values = [
                        sess["site_name"],
                        sess["game_type"] or "",
                        sess["game_name"] or "",
                        self._format_sc(sess["start_total"]),
                        self._format_sc(sess["end_total"]),
                        self._format_sc(sess["start_redeem"]),
                        self._format_sc(sess["end_redeem"]),
                        self._format_delta(sess["delta_redeem"]),
                        self._format_currency_or_dash(sess["basis_consumed"]),
                        self._format_delta(sess["delta_total"]),
                        self._format_signed_currency(sess["total_taxable"]),
                        time_range,
                        sess["notes"],
                    ]
                    sess_item = QtWidgets.QTreeWidgetItem(sess_values)
                    sess_item.setData(
                        0,
                        QtCore.Qt.UserRole,
                        {
                            "kind": "session",
                            "session_id": sess["id"],
                            "date": sess["session_date"],
                        },
                    )
                    self._apply_status_color(sess_item, sess["total_taxable"])
                    user_item.addChild(sess_item)

    def _fetch_notes_for_dates(self, dates):
        dates = list(dates)
        if not dates:
            return {}
        conn = self.db.get_connection()
        c = conn.cursor()
        placeholders = ",".join("?" * len(dates))
        c.execute(
            f"""
            SELECT session_date, MAX(notes) as notes
            FROM daily_tax_sessions
            WHERE session_date IN ({placeholders})
            GROUP BY session_date
            """,
            dates,
        )
        notes_by_date = {row["session_date"]: row["notes"] or "" for row in c.fetchall()}
        conn.close()
        return notes_by_date

    def _format_delta(self, value):
        if value is None:
            return "-"
        return f"{float(value):+.2f}"

    def _format_sc(self, value):
        if value is None:
            return "-"
        return f"{float(value):.2f}"

    def _format_currency_or_dash(self, value):
        if value is None:
            return "-"
        return format_currency(value)

    def _filter_sessions(self, sessions, exclude_col=None, include_search=True):
        if self.date_filter and exclude_col != 0:
            sessions = [s for s in sessions if s["session_date"] in self.date_filter]
        for col_index, values in self.column_filters.items():
            if col_index == exclude_col:
                continue
            if values:
                sessions = [s for s in sessions if self._session_value_for_column(s, col_index) in values]
        if include_search:
            term = self.search_edit.text().strip().lower()
            if term:
                sessions = [s for s in sessions if term in s["search_blob"]]
        return sessions

    def _session_value_for_column(self, sess, col_index):
        if col_index == 0:
            return sess["session_date"]
        if col_index == 1:
            return sess["game_type"] or ""
        if col_index == 2:
            return sess["game_name"] or ""
        if col_index == 3:
            return self._format_sc(sess["start_total"])
        if col_index == 4:
            return self._format_sc(sess["end_total"])
        if col_index == 5:
            return self._format_sc(sess["start_redeem"])
        if col_index == 6:
            return self._format_sc(sess["end_redeem"])
        if col_index == 7:
            return self._format_delta(sess["delta_redeem"])
        if col_index == 8:
            return self._format_currency_or_dash(sess["basis_consumed"])
        if col_index == 9:
            return self._format_delta(sess["delta_total"])
        if col_index == 10:
            return self._format_signed_currency(sess["total_taxable"])
        if col_index == 11:
            start_time = (sess["start_time"] or "00:00:00")[:5]
            end_time = sess["end_time"][:5] if sess["end_time"] else ""
            return f"{start_time}-{end_time}" if end_time else f"{start_time}-Active"
        if col_index == 12:
            return sess["notes"] or ""
        return ""

    def _show_header_menu(self, col_index):
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        action = menu.exec(QtGui.QCursor.pos())
        if action == sort_asc:
            self.sort_column = col_index
            self.sort_reverse = False
            self.refresh_view()
        elif action == sort_desc:
            self.sort_column = col_index
            self.sort_reverse = True
            self.refresh_view()
        elif action == clear_sort:
            self.sort_column = None
            self.sort_reverse = False
            self.refresh_view()
        elif filter_action and action == filter_action:
            sessions = self._filter_sessions(self._last_sessions, exclude_col=col_index, include_search=True)
            if col_index == 0:
                values = sorted({s["session_date"] for s in sessions})
                dialog = DateTimeFilterDialog(values, self.date_filter, self, show_time=False)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    self.date_filter = dialog.selected_values()
                    self.refresh_view()
            else:
                values = sorted({self._session_value_for_column(s, col_index) for s in sessions})
                selected = self.column_filters.get(col_index, set())
                dialog = ColumnFilterDialog(values, selected, self)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    selected_values = dialog.selected_values()
                    if selected_values:
                        self.column_filters[col_index] = selected_values
                    else:
                        self.column_filters.pop(col_index, None)
                    self.refresh_view()

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _apply_status_color(self, item, value):
        color = "#2e7d32" if value >= 0 else "#c0392b"
        brush = QtGui.QBrush(QtGui.QColor(color))
        for col in range(item.columnCount()):
            item.setForeground(col, brush)

    def add_edit_notes(self):
        item = self.tree.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(
                self, "No Selection", "Select a day or game session."
            )
            return
        meta = item.data(0, QtCore.Qt.UserRole) or {}
        kind = meta.get("kind")
        if kind == "session":
            self._view_session(meta.get("session_id"))
        elif kind == "date":
            self._edit_daily_notes(meta.get("date"))
        else:
            QtWidgets.QMessageBox.information(
                self, "Selection", "Select a day or game session."
            )

    def _edit_daily_notes(self, session_date):
        if not session_date:
            return
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT notes FROM daily_tax_sessions WHERE session_date = ? LIMIT 1",
            (session_date,),
        )
        row = c.fetchone()
        conn.close()
        current_notes = row["notes"] if row and row["notes"] else ""

        dialog = DailySessionNotesDialog(session_date, current_notes, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_notes = dialog.notes_text()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "UPDATE daily_tax_sessions SET notes = ? WHERE session_date = ?",
            (new_notes if new_notes else None, session_date),
        )
        conn.commit()
        conn.close()
        self.refresh_view()

    def _view_session(self, session_id):
        if not session_id:
            QtWidgets.QMessageBox.information(self, "No Session", "Select a game session.")
            return
        session = self._fetch_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return

        def handle_open():
            if self.on_open_session:
                self.on_open_session(session_id)

        def handle_edit():
            if self.on_edit_session:
                self.on_edit_session(session_id)

        def handle_delete():
            if self.on_delete_session:
                self.on_delete_session(session_id)

        dialog = GameSessionViewDialog(
            session,
            parent=self,
            on_open_session=handle_open if self.on_open_session else None,
            on_open_purchase=self.on_open_purchase,
            on_open_redemption=self.on_open_redemption,
            on_edit=handle_edit if self.on_edit_session else None,
            on_delete=handle_delete if self.on_delete_session else None,
        )
        dialog.exec()

    def _fetch_session(self, session_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT gs.*, s.name as site_name, u.name as user_name
            FROM game_sessions gs
            JOIN sites s ON gs.site_id = s.id
            JOIN users u ON gs.user_id = u.id
            WHERE gs.id = ?
            """,
            (session_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def find_and_select_session(self, session_id):
        """
        Find and select a game session in the tree by session_id.
        Expands parent items (date -> user) and scrolls to center the session.
        Returns True if found, False otherwise.
        """
        # Recursively search all tree items
        def search_tree(parent_item, level=0):
            if parent_item is None:
                # Search top-level items
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    result = search_tree(item, level=1)
                    if result:
                        return result
                return None
            else:
                # Check current item
                meta = parent_item.data(0, QtCore.Qt.UserRole) or {}
                if meta.get("kind") == "session" and meta.get("session_id") == session_id:
                    return parent_item
                
                # Search children
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    result = search_tree(child, level + 1)
                    if result:
                        return result
                return None
        
        # Find the session item
        session_item = search_tree(None)
        
        if not session_item:
            return False
        
        # Expand all parent items
        parent = session_item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        
        # Select and scroll to the item
        self.tree.setCurrentItem(session_item)
        self.tree.scrollToItem(session_item, QtWidgets.QAbstractItemView.PositionAtCenter)
        
        return True

    def export_csv(self):
        import csv

        default_name = f"daily_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Daily Sessions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            for idx in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(idx)
                writer.writerow([item.text(col) for col in range(len(self.columns))])


class UnrealizedNotesDialog(QtWidgets.QDialog):
    def __init__(self, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Position Notes")
        self.resize(520, 320)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel("Position Notes")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlainText(notes or "")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 5 + 18)
        layout.addWidget(self.notes_edit, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)

    def notes_text(self):
        return self.notes_edit.toPlainText().strip()


class UnrealizedPositionDialog(QtWidgets.QDialog):
    def __init__(
        self,
        summary,
        purchases,
        parent=None,
        on_open_purchase=None,
        on_close_position=None,
    ):
        super().__init__(parent)
        self.summary = summary
        self.purchases = purchases or []
        self.on_open_purchase = on_open_purchase
        self.on_close_position = on_close_position
        self.setWindowTitle("Unrealized Position")
        self.resize(600, 520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        def build_group(title):
            group = QtWidgets.QGroupBox(title)
            group_layout = QtWidgets.QGridLayout(group)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(6)
            group_layout.setColumnStretch(1, 1)
            group_layout.setColumnStretch(3, 1)
            return group, group_layout

        def add_pair(grid, row, col, label_text, value):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            grid.addWidget(label, row, col * 2)
            grid.addWidget(value_label, row, col * 2 + 1)

        def format_date(value):
            if not value:
                return "—"
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return value

        position_group, position_grid = build_group("Position")
        add_pair(position_grid, 0, 0, "Site", summary.get("site_name", "—"))
        add_pair(position_grid, 0, 1, "User", summary.get("user_name", "—"))
        add_pair(position_grid, 1, 0, "Start Date", format_date(summary.get("start_date")))
        add_pair(position_grid, 1, 1, "Last Activity", format_date(summary.get("last_activity")))
        layout.addWidget(position_group)

        balance_group, balance_grid = build_group("Balances")
        add_pair(
            balance_grid,
            0,
            0,
            "Remaining Basis",
            format_currency(summary.get("remaining_basis", 0.0)),
        )
        add_pair(balance_grid, 0, 1, "Current SC", f"{summary.get('current_sc', 0.0):.2f}")
        add_pair(
            balance_grid,
            1,
            0,
            "Current Value",
            format_currency(summary.get("current_value", 0.0)),
        )
        add_pair(
            balance_grid,
            1,
            1,
            "Unrealized P/L",
            self._format_signed_currency(summary.get("unrealized_pnl")),
        )
        layout.addWidget(balance_group)

        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        notes_value = summary.get("notes") or ""
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
            notes_layout.addWidget(notes_edit)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            notes_layout.addWidget(notes_field)
        layout.addWidget(notes_group)

        purchases_group = QtWidgets.QGroupBox("Open Purchases")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Purchase Date", "Amount", "SC", "View"]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        header.setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 160)
        row_height = self.table.verticalHeader().defaultSectionSize()
        min_height = self.table.horizontalHeader().height() + row_height * 3 + 10
        self.table.setMinimumHeight(min_height)
        purchases_layout.addWidget(self.table)
        layout.addWidget(purchases_group, 1)
        self._populate_purchases()

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        if self.on_close_position:
            close_position_btn = QtWidgets.QPushButton("Close Position")
            close_position_btn.setObjectName("PrimaryButton")
            btn_row.addWidget(close_position_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self.on_close_position:
            close_position_btn.clicked.connect(self._handle_close_position)
        close_btn.clicked.connect(self.accept)
        close_btn.setFocus()

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _populate_purchases(self):
        self.table.setRowCount(len(self.purchases))
        for row_idx, row in enumerate(self.purchases):
            purchase_time = row["purchase_time"] if row["purchase_time"] else "00:00:00"
            date_display = format_date_time(row["purchase_date"], purchase_time)
            amount = format_currency(row["amount"])
            sc_received = f"{float(row['sc_received'] or 0.0):.2f}"

            values = [date_display, amount, sc_received]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (1, 2):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(132)
            view_btn.clicked.connect(
                lambda _checked=False, pid=row["id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.table.setCellWidget(row_idx, 3, view_container)
            self.table.setRowHeight(
                row_idx,
                max(self.table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _handle_close_position(self):
        if not self.on_close_position:
            return
        self.accept()
        QtCore.QTimer.singleShot(0, self.on_close_position)


class UnrealizedTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr, on_data_changed=None, on_open_purchase=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.on_open_purchase = on_open_purchase
        self.all_rows = []
        self.filtered_rows = []
        self.header_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self.active_date_filter = (None, None)

        self.columns = [
            "Site",
            "User",
            "Start",
            "Purchase Basis",
            "Current SC",
            "Current Value",
            "Unrealized P/L",
            "Last Activity",
            "Notes",
        ]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search unrealized positions...")
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.notes_btn = QtWidgets.QPushButton("Add Notes")
        self.notes_btn.setVisible(False)
        self.close_balance_btn = QtWidgets.QPushButton("Close Position")
        self.close_balance_btn.setObjectName("PrimaryButton")
        self.close_balance_btn.setVisible(False)
        self.view_position_btn = QtWidgets.QPushButton("View Position")
        self.view_position_btn.setVisible(False)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addStretch(1)
        for btn in (
            self.notes_btn,
            self.close_balance_btn,
            self.view_position_btn,
            self.refresh_btn,
            self.export_btn,
        ):
            btn.setFixedWidth(btn.sizeHint().width())
        self.actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.close_balance_btn)
        actions_layout.addWidget(self.notes_btn)
        actions_layout.addWidget(self.view_position_btn)
        actions_layout.addWidget(self.refresh_btn)
        actions_layout.addWidget(self.export_btn)
        total_width = sum(btn.sizeHint().width() for btn in (
            self.notes_btn,
            self.close_balance_btn,
            self.view_position_btn,
            self.refresh_btn,
            self.export_btn,
        ))
        total_width += actions_layout.spacing() * 4
        self.actions_container.setFixedWidth(total_width)
        self.actions_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        search_row.addWidget(self.actions_container, 0, QtCore.Qt.AlignRight)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_position)
        layout.addWidget(self.table, 1)
        self.table.selectionModel().selectionChanged.connect(self._update_action_buttons)

        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.refresh_btn.clicked.connect(self.load_data)
        self.export_btn.clicked.connect(self.export_csv)
        self.close_balance_btn.clicked.connect(self._close_balance)
        self.notes_btn.clicked.connect(self._add_notes)
        self.view_position_btn.clicked.connect(self._view_position)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))

        self.load_data()

    def _update_action_buttons(self):
        has_selection = bool(self.table.selectionModel().selectedRows())
        self.notes_btn.setVisible(has_selection)
        self.close_balance_btn.setVisible(has_selection)
        self.view_position_btn.setVisible(has_selection)

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("Select")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "all":
            self.clear_date_filter()
            return
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.apply_filters()

    def apply_date_filter(self):
        start_date = None
        end_date = None
        start_text = self.from_edit.text().strip()
        end_text = self.to_edit.text().strip()
        if start_text:
            try:
                start_date = parse_date_input(start_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid start date.")
                return
        if end_text:
            try:
                end_date = parse_date_input(end_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid end date.")
                return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (
            start_date.strftime("%Y-%m-%d") if start_date else None,
            end_date.strftime("%Y-%m-%d") if end_date else None,
        )
        self.apply_filters()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.apply_filters()

    def clear_all_filters(self):
        self.header_filters = {}
        self.search_edit.clear()
        self._clear_selection()
        self.clear_date_filter()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def eventFilter(self, obj, event):
        if getattr(self, "header", None) and obj is self.header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(self.header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(self.header, pos) is not None:
                    return False
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_buttons()

    def _show_header_menu(self, col_index):
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        action = menu.exec(QtGui.QCursor.pos())
        if action == sort_asc:
            self.sort_column = col_index
            self.sort_order = QtCore.Qt.AscendingOrder
            self.apply_filters()
        elif action == sort_desc:
            self.sort_column = col_index
            self.sort_order = QtCore.Qt.DescendingOrder
            self.apply_filters()
        elif action == clear_sort:
            self.sort_column = None
            self.sort_order = QtCore.Qt.AscendingOrder
            self.apply_filters()
        elif action == filter_action:
            filter_rows = self._filter_rows(exclude_col=col_index)
            values = sorted({r["display"][col_index] for r in filter_rows})
            selected = self.header_filters.get(col_index, set())
            if col_index in (2, 7):
                dialog = DateTimeFilterDialog(values, selected, self, show_time=False)
            else:
                dialog = ColumnFilterDialog(values, selected, self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                selected_values = dialog.selected_values()
                if selected_values:
                    self.header_filters[col_index] = selected_values
                else:
                    self.header_filters.pop(col_index, None)
                self.apply_filters()

    def apply_filters(self):
        rows = self._filter_rows()
        rows = self._sort_rows(rows)
        self.filtered_rows = rows
        self._refresh_table(rows)

    def _filter_rows(self, exclude_col=None):
        rows = list(self.all_rows)
        start_date, end_date = self.active_date_filter
        if start_date:
            rows = [r for r in rows if r["last_activity"] >= start_date]
        if end_date:
            rows = [r for r in rows if r["last_activity"] <= end_date]
        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in rows if term in r["search_blob"]]
        for col, values in self.header_filters.items():
            if col == exclude_col:
                continue
            if values:
                rows = [r for r in rows if r["display"][col] in values]
        return rows

    def _sort_rows(self, rows):
        if self.sort_column is None:
            return rows
        reverse = self.sort_order == QtCore.Qt.DescendingOrder
        col = self.sort_column

        def parse_currency(value):
            if value in ("Unknown", "-", ""):
                return -999999 if reverse else 999999
            return float(str(value).replace("$", "").replace(",", "").replace("+", ""))

        def sort_key(row):
            value = row["display"][col]
            if col in (3, 5, 6):
                return parse_currency(value)
            if col == 4:
                return parse_currency(value.replace("SC", "").strip())
            if col in (2, 7):
                return value
            return str(value).lower()

        return sorted(rows, key=sort_key, reverse=reverse)

    def _refresh_table(self, rows):
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            tag = row["tag"]
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in (3, 4, 5, 6):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, (row["site_id"], row["user_id"]))
                if tag == "profit":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#2e7d32")))
                elif tag == "loss":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#c0392b")))
                elif tag == "unknown":
                    item.setForeground(QtGui.QBrush(QtGui.QColor("#62636c")))
                self.table.setItem(r_idx, c_idx, item)

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute(
            """
            SELECT DISTINCT
                p.site_id,
                p.user_id,
                s.name as site_name,
                u.name as user_name
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            WHERE p.remaining_amount > 0.001
              AND (p.status IS NULL OR p.status = 'active')
            """
        )
        positions = c.fetchall()

        self.all_rows = []
        for pos in positions:
            site_id = pos["site_id"]
            user_id = pos["user_id"]
            c.execute(
                """
                SELECT 
                    MIN(purchase_date) as start_date,
                    SUM(remaining_amount) as remaining_basis,
                    SUM(sc_received) as total_sc_purchased
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND (status IS NULL OR status = 'active')
                  AND remaining_amount > 0.001
                """,
                (site_id, user_id),
            )
            purchase_data = c.fetchone()
            remaining_basis = purchase_data["remaining_basis"] or 0
            total_sc_purchased = purchase_data["total_sc_purchased"] or 0
            if remaining_basis < 0.01:
                continue

            c.execute(
                """
                SELECT ending_sc_balance, ending_redeemable_sc, session_date, end_time
                FROM game_sessions
                WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
                ORDER BY session_date DESC, end_time DESC
                LIMIT 1
                """,
                (site_id, user_id),
            )
            last_session = c.fetchone()

            if last_session:
                current_sc = (
                    last_session["ending_redeemable_sc"]
                    if last_session["ending_redeemable_sc"] is not None
                    else last_session["ending_sc_balance"]
                )
                last_activity = last_session["session_date"]
                last_time = last_session["end_time"]

                c.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) as total_redeemed
                    FROM redemptions
                    WHERE site_id = ? AND user_id = ?
                    AND (redemption_date > ? OR (redemption_date = ? AND redemption_time > ?))
                    """,
                    (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
                )
                redemptions_since = c.fetchone()["total_redeemed"]

                # Check for new purchases made after the last session
                c.execute(
                    """
                    SELECT COALESCE(SUM(sc_received), 0) as new_sc
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                    AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                    """,
                    (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
                )
                new_purchases = c.fetchone()["new_sc"]

                if redemptions_since >= current_sc:
                    # Redeemed all from session, use only new purchases
                    if new_purchases > 0:
                        c.execute(
                            """
                            SELECT starting_sc_balance, SUM(sc_received) as total_sc_received
                            FROM purchases
                            WHERE site_id = ? AND user_id = ?
                            AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                            ORDER BY purchase_date DESC, purchase_time DESC
                            LIMIT 1
                            """,
                            (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
                        )
                        recent_purchase = c.fetchone()
                        if recent_purchase and recent_purchase["starting_sc_balance"] is not None:
                            current_sc = recent_purchase["starting_sc_balance"] + recent_purchase[
                                "total_sc_received"
                            ]
                        else:
                            current_sc = new_purchases
                        last_activity = purchase_data["start_date"]
                    else:
                        current_sc = 0
                else:
                    # Session balance minus redemptions plus new purchases
                    current_sc = current_sc - redemptions_since + new_purchases
            else:
                c.execute(
                    """
                    SELECT starting_sc_balance
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                    ORDER BY purchase_date DESC, purchase_time DESC
                    LIMIT 1
                    """,
                    (site_id, user_id),
                )
                recent_purchase = c.fetchone()
                if recent_purchase and recent_purchase["starting_sc_balance"] is not None:
                    current_sc = recent_purchase["starting_sc_balance"] + total_sc_purchased
                else:
                    current_sc = total_sc_purchased

                c.execute(
                    """
                    SELECT MAX(purchase_date) as last_date
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                    """,
                    (site_id, user_id),
                )
                last_activity = c.fetchone()["last_date"] or purchase_data["start_date"]

            sc_rate = self.session_mgr.get_sc_rate(site_id)
            if current_sc is not None:
                current_value = current_sc * sc_rate
                unrealized_pnl = current_value - remaining_basis
            else:
                current_value = None
                unrealized_pnl = None

            c.execute(
                """
                SELECT notes FROM site_sessions
                WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
                ORDER BY start_date DESC
                LIMIT 1
                """,
                (site_id, user_id),
            )
            notes_row = c.fetchone()
            notes = notes_row["notes"] if notes_row and notes_row["notes"] else ""
            notes_display = notes[:120]

            if unrealized_pnl is not None:
                if unrealized_pnl > 0:
                    tag = "profit"
                elif unrealized_pnl < 0:
                    tag = "loss"
                else:
                    tag = ""
            else:
                tag = "unknown"

            values = [
                pos["site_name"],
                pos["user_name"],
                purchase_data["start_date"],
                format_currency(remaining_basis),
                f"{current_sc:.2f}" if current_sc is not None else "Unknown",
                format_currency(current_value) if current_value is not None else "Unknown",
                f"${unrealized_pnl:+.2f}" if unrealized_pnl is not None else "Unknown",
                last_activity,
                notes_display,
            ]
            search_blob = " ".join(str(v).lower() for v in values if v is not None)
            self.all_rows.append(
                {
                    "site_id": site_id,
                    "user_id": user_id,
                    "last_activity": last_activity or "",
                    "display": values,
                    "tag": tag,
                    "search_blob": search_blob,
                }
            )

        conn.close()
        self.apply_filters()

    def _selected_ids(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None, None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None, None
        data = item.data(QtCore.Qt.UserRole)
        if not data:
            return None, None
        return data[0], data[1]

    def _add_notes(self):
        site_id, user_id = self._selected_ids()
        if site_id is None or user_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Please select a position to add notes."
            )
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT id, notes FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (site_id, user_id),
        )
        session = c.fetchone()
        if session:
            session_id = session["id"]
            current_notes = session["notes"] or ""
        else:
            c.execute(
                """
                INSERT INTO site_sessions (site_id, user_id, start_date, status, total_buyin)
                VALUES (?, ?, date('now'), 'Active', 0)
                """,
                (site_id, user_id),
            )
            session_id = c.lastrowid
            current_notes = ""
        conn.commit()
        conn.close()

        dialog = UnrealizedNotesDialog(current_notes, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_notes = dialog.notes_text()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE site_sessions SET notes = ? WHERE id = ?", (new_notes, session_id))
        conn.commit()
        conn.close()
        self.load_data()

    def _view_position(self):
        site_id, user_id = self._selected_ids()
        if site_id is None or user_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Please select a position to view."
            )
            return
        summary = self._fetch_position_summary(site_id, user_id)
        if not summary:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Position not found.")
            return
        purchases = self._fetch_position_purchases(site_id, user_id)
        dialog = UnrealizedPositionDialog(
            summary,
            purchases,
            parent=self,
            on_open_purchase=self.on_open_purchase,
            on_close_position=self._close_balance,
        )
        dialog.exec()

    def _fetch_position_summary(self, site_id, user_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM sites WHERE id = ?", (site_id,))
        site_row = c.fetchone()
        c.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_row = c.fetchone()

        c.execute(
            """
            SELECT 
                MIN(purchase_date) as start_date,
                SUM(remaining_amount) as remaining_basis,
                SUM(sc_received) as total_sc_purchased
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND (status IS NULL OR status = 'active')
              AND remaining_amount > 0.001
            """,
            (site_id, user_id),
        )
        purchase_data = c.fetchone()
        remaining_basis = purchase_data["remaining_basis"] or 0.0
        total_sc_purchased = purchase_data["total_sc_purchased"] or 0.0
        if remaining_basis < 0.01:
            conn.close()
            return None

        c.execute(
            """
            SELECT ending_sc_balance, ending_redeemable_sc, session_date, end_time
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
            ORDER BY session_date DESC, end_time DESC
            LIMIT 1
            """,
            (site_id, user_id),
        )
        last_session = c.fetchone()

        if last_session:
            current_sc = (
                last_session["ending_redeemable_sc"]
                if last_session["ending_redeemable_sc"] is not None
                else last_session["ending_sc_balance"]
            )
            last_activity = last_session["session_date"]
            last_time = last_session["end_time"]

            c.execute(
                """
                SELECT COALESCE(SUM(amount), 0) as total_redeemed
                FROM redemptions
                WHERE site_id = ? AND user_id = ?
                AND (redemption_date > ? OR (redemption_date = ? AND redemption_time > ?))
                """,
                (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
            )
            redemptions_since = c.fetchone()["total_redeemed"]

            if redemptions_since >= current_sc:
                c.execute(
                    """
                    SELECT COALESCE(SUM(sc_received), 0) as new_sc
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                    AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                    """,
                    (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
                )
                new_purchases = c.fetchone()["new_sc"]

                if new_purchases > 0:
                    c.execute(
                        """
                        SELECT starting_sc_balance, SUM(sc_received) as total_sc_received
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
                        AND (purchase_date > ? OR (purchase_date = ? AND purchase_time > ?))
                        ORDER BY purchase_date DESC, purchase_time DESC
                        LIMIT 1
                        """,
                        (site_id, user_id, last_activity, last_activity, last_time or "00:00:00"),
                    )
                    recent_purchase = c.fetchone()
                    if recent_purchase and recent_purchase["starting_sc_balance"] is not None:
                        current_sc = recent_purchase["starting_sc_balance"] + recent_purchase[
                            "total_sc_received"
                        ]
                    else:
                        current_sc = new_purchases
                    last_activity = purchase_data["start_date"]
                else:
                    current_sc = 0
            else:
                current_sc -= redemptions_since
        else:
            c.execute(
                """
                SELECT starting_sc_balance
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND (status IS NULL OR status = 'active')
                ORDER BY purchase_date DESC, purchase_time DESC
                LIMIT 1
                """,
                (site_id, user_id),
            )
            recent_purchase = c.fetchone()
            if recent_purchase and recent_purchase["starting_sc_balance"] is not None:
                current_sc = recent_purchase["starting_sc_balance"] + total_sc_purchased
            else:
                current_sc = total_sc_purchased

            c.execute(
                """
                SELECT MAX(purchase_date) as last_date
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                """,
                (site_id, user_id),
            )
            last_activity = c.fetchone()["last_date"] or purchase_data["start_date"]

        sc_rate = self.session_mgr.get_sc_rate(site_id)
        current_value = current_sc * sc_rate if current_sc is not None else 0.0
        unrealized_pnl = current_value - remaining_basis

        c.execute(
            """
            SELECT notes FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC
            LIMIT 1
            """,
            (site_id, user_id),
        )
        notes_row = c.fetchone()
        notes = notes_row["notes"] if notes_row and notes_row["notes"] else ""
        conn.close()

        return {
            "site_name": site_row["name"] if site_row else "",
            "user_name": user_row["name"] if user_row else "",
            "start_date": purchase_data["start_date"],
            "remaining_basis": remaining_basis,
            "current_sc": current_sc or 0.0,
            "current_value": current_value,
            "unrealized_pnl": unrealized_pnl,
            "last_activity": last_activity,
            "notes": notes,
        }

    def _fetch_position_purchases(self, site_id, user_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT id, purchase_date, purchase_time, amount, sc_received, remaining_amount
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND (status IS NULL OR status = 'active')
              AND remaining_amount > 0.001
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
            """,
            (site_id, user_id),
        )
        purchases = [dict(row) for row in c.fetchall()]
        conn.close()
        return purchases

    def _close_balance(self):
        site_id, user_id = self._selected_ids()
        if site_id is None or user_id is None:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", "Please select a position to close."
            )
            return
        selected = self.table.selectionModel().selectedRows()
        values = [self.table.item(selected[0].row(), idx).text() for idx in range(len(self.columns))]
        site_name = values[0]
        user_name = values[1]

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT id FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Active'
            """,
            (site_id, user_id),
        )
        if c.fetchone():
            conn.close()
            QtWidgets.QMessageBox.warning(
                self,
                "Active Session",
                "Cannot close balance - you have an active session on this site.\n\n"
                "Please end the session first.",
            )
            return

        c.execute(
            """
            SELECT ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
            ORDER BY session_date DESC, end_time DESC
            LIMIT 1
            """,
            (site_id, user_id),
        )
        last_session = c.fetchone()
        current_sc_balance = last_session["ending_sc_balance"] if last_session else 0

        c.execute(
            """
            SELECT SUM(remaining_amount) as total_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
            """,
            (site_id, user_id),
        )
        result = c.fetchone()
        total_cost_basis = result["total_basis"] if result and result["total_basis"] else 0
        conn.close()

        if total_cost_basis == 0:
            QtWidgets.QMessageBox.information(
                self, "No Balance", "No active basis to close for this site/user."
            )
            return

        message = (
            f"Close balance for {site_name} ({user_name})?\n\n"
            f"Current SC balance: {current_sc_balance:.2f} SC (${current_sc_balance:.2f})\n"
            f"Cost basis: ${total_cost_basis:.2f}\n"
            f"Net loss if closed: ${total_cost_basis - current_sc_balance:.2f}\n\n"
            "This will:\n"
            f"• Mark ${current_sc_balance:.2f} SC as dormant\n"
            "• Remove from Unrealized tab\n"
            f"• Show -${total_cost_basis - current_sc_balance:.2f} cash flow loss in Realized tab\n"
            "• NO tax impact (not a deduction)\n"
            "• Dormant balance will reactivate if you play this site again\n\n"
            "Continue?"
        )
        confirm = QtWidgets.QMessageBox.question(self, "Close Balance", message)
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        today = date.today().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M:%S")

        c.execute(
            """
            SELECT ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND ending_sc_balance IS NOT NULL
            ORDER BY session_date DESC, end_time DESC
            LIMIT 1
            """,
            (site_id, user_id),
        )
        last_session = c.fetchone()
        current_sc_balance = last_session["ending_sc_balance"] if last_session else 0

        c.execute(
            """
            SELECT COALESCE(SUM(remaining_amount), 0) as total_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
            """,
            (site_id, user_id),
        )
        total_cost_basis = c.fetchone()["total_basis"]
        net_loss = total_cost_basis - current_sc_balance

        c.execute(
            """
            INSERT INTO redemptions 
            (redemption_date, redemption_time, site_id, user_id, amount, redemption_method_id, notes, processed)
            VALUES (?, ?, ?, ?, 0, NULL, ?, 1)
            """,
            (
                today,
                now,
                site_id,
                user_id,
                f"Balance Closed - Net Loss: ${net_loss:.2f} (${current_sc_balance:.2f} SC marked dormant)",
            ),
        )
        redemption_id = c.lastrowid

        c.execute(
            """
            INSERT INTO realized_transactions
            (redemption_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (today, site_id, redemption_id, net_loss, -net_loss, user_id),
        )

        c.execute(
            """
            UPDATE purchases
            SET status = 'dormant'
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0 AND status = 'active'
            """,
            (site_id, user_id),
        )

        conn.commit()
        conn.close()

        # Run FIFO allocation for this redemption so it shows up immediately
        self.session_mgr.fifo_calc._rebuild_fifo_for_pair(site_id, user_id)

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            f"Balance closed for {site_name} ({user_name})\n\n"
            f"Net cash flow loss: -${net_loss:.2f}\n"
            f"Dormant SC balance: {current_sc_balance:.2f} SC (${current_sc_balance:.2f})\n\n"
            f"The -${net_loss:.2f} will show in Realized tab\n"
            f"Dormant ${current_sc_balance:.2f} will reactivate on next session",
        )

    def export_csv(self):
        import csv

        default_name = f"unrealized_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Unrealized Positions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            for row in self.filtered_rows:
                writer.writerow(row["display"])


class RealizedNotesDialog(QtWidgets.QDialog):
    def __init__(self, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transaction Notes")
        self.resize(520, 320)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel("Transaction Notes")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlainText(notes or "")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 5 + 18)
        layout.addWidget(self.notes_edit, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)

    def notes_text(self):
        return self.notes_edit.toPlainText().strip()


class RealizedDateNotesDialog(QtWidgets.QDialog):
    def __init__(self, session_date, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Realized Notes - {session_date}")
        self.resize(520, 360)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel(f"Notes for {session_date}")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlainText(notes or "")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 6 + 18)
        layout.addWidget(self.notes_edit, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)

    def notes_text(self):
        return self.notes_edit.toPlainText().strip()


class RealizedPositionDialog(QtWidgets.QDialog):
    """View dialog for Realized Position - uses RedemptionViewDialog structure but customized for realized positions."""
    def __init__(
        self,
        position,
        allocations,
        parent=None,
        on_open_purchase=None,
        on_open_redemption=None,
    ):
        super().__init__(parent)
        self.position = position
        self.allocations = allocations or []
        self.on_open_purchase = on_open_purchase
        self.on_open_redemption = on_open_redemption
        self.setWindowTitle("View Position")
        self.resize(700, 650)
        
        # Fetch linked sessions for the redemption
        from database import Database
        from business_logic import FIFOCalculator, SessionManager
        self.db = Database()
        fifo = FIFOCalculator(self.db)
        self.session_manager = SessionManager(self.db, fifo)
        self.linked_sessions = self.session_manager.get_links_for_redemption(position["redemption_id"])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Create tab widget
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_details_tab(), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        # Buttons - only "View in Redemptions" and "Close" (no Edit/Delete)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        if self.on_open_redemption:
            open_btn = QtWidgets.QPushButton("View in Redemptions")
            btn_row.addWidget(open_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self.on_open_redemption:
            open_btn.clicked.connect(self._handle_open_redemption)
        close_btn.clicked.connect(self.accept)

    def _format_date(self, value):
        """Helper to format date strings to MM/DD/YY"""
        if not value:
            return "—"
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return value

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _create_details_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnMinimumWidth(1, 300)

        def add_row(label_text, value, row, wrap=False):
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label.setWordWrap(wrap)
            form.addWidget(label, row, 0)
            form.addWidget(value_label, row, 1)
            return row + 1

        row = 0
        row = add_row("Date:", self._format_date(self.position["session_date"]), row)
        row = add_row("User:", self.position["user_name"] or "—", row)
        row = add_row("Site:", self.position["site_name"] or "—", row)
        form.addItem(QtWidgets.QSpacerItem(1, 16), row, 0)
        row += 1
        row = add_row("Redemption Amount:", format_currency(self.position["redemption_amount"]), row)
        row = add_row("Cost Basis:", format_currency(self.position["cost_basis"]), row)
        row = add_row("Net P/L:", self._format_signed_currency(self.position["net_pl"]), row)
        
        layout.addLayout(form)
        
        # Notes section
        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        notes_value = self.position["redemption_notes"] or ""
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
            notes_layout.addWidget(notes_edit)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            notes_layout.addWidget(notes_field)
        layout.addWidget(notes_group)
        
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Calculate cost basis and unbased portion
        cost_basis = float(self.position["cost_basis"] if self.position["cost_basis"] else 0.0)
        redemption_amt = float(self.position["redemption_amount"] if self.position["redemption_amount"] else 0.0)
        unbased_portion = redemption_amt - cost_basis if cost_basis < redemption_amt else 0.0

        # Summary section
        summary_layout = QtWidgets.QGridLayout()
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        summary_layout.addWidget(QtWidgets.QLabel("Cost Basis:"), 0, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(cost_basis)), 0, 1)
        if unbased_portion > 0.01:
            summary_layout.addWidget(QtWidgets.QLabel("Unbased Portion:"), 1, 0)
            summary_layout.addWidget(QtWidgets.QLabel(format_currency(unbased_portion)), 1, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Total Redemption:"), 2, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(redemption_amt)), 2, 1)
        summary_layout.setColumnStretch(2, 1)
        
        layout.addLayout(summary_layout)
        layout.addSpacing(8)

        # Allocated Purchases table
        purchases_group = QtWidgets.QGroupBox("Allocated Purchases (FIFO)")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.allocations:
            note = QtWidgets.QLabel(
                "This redemption has no purchase basis. This may occur when cashing out freebies, bonuses, "
                "or winnings from partial redemptions. If you believe this is incorrect, use Tools → "
                "Recalculate Everything to rebuild FIFO allocations."
            )
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.purchases_table = QtWidgets.QTableWidget(0, 6)
            self.purchases_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Amount", "SC Received", "Allocated", "View"]
            )
            self.purchases_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.purchases_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.purchases_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.purchases_table.setAlternatingRowColors(True)
            self.purchases_table.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            header = self.purchases_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.purchases_table.verticalHeader().setVisible(False)
            self.purchases_table.setColumnWidth(0, 100)
            self.purchases_table.setColumnWidth(1, 80)
            self.purchases_table.setColumnWidth(2, 100)
            self.purchases_table.setColumnWidth(3, 100)
            self.purchases_table.setColumnWidth(4, 100)
            purchases_layout.addWidget(self.purchases_table)
            self._populate_purchases_table()

        layout.addWidget(purchases_group, 1)

        # Linked Game Sessions table
        sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)
        
        if not self.linked_sessions:
            note = QtWidgets.QLabel("No linked game sessions found.")
            note.setWordWrap(True)
            sessions_layout.addWidget(note)
        else:
            self.sessions_table = QtWidgets.QTableWidget(0, 6)
            self.sessions_table.setHorizontalHeaderLabels(
                ["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View"]
            )
            self.sessions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.sessions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.sessions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.sessions_table.setAlternatingRowColors(True)
            self.sessions_table.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            header = self.sessions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.sessions_table.verticalHeader().setVisible(False)
            self.sessions_table.setColumnWidth(0, 100)
            self.sessions_table.setColumnWidth(1, 80)
            self.sessions_table.setColumnWidth(2, 120)
            self.sessions_table.setColumnWidth(3, 100)
            self.sessions_table.setColumnWidth(4, 70)
            sessions_layout.addWidget(self.sessions_table)
            self._populate_sessions_table()

        layout.addWidget(sessions_group, 1)
        return widget

    def _populate_purchases_table(self):
        self.purchases_table.setRowCount(len(self.allocations))
        for row_idx, purchase in enumerate(self.allocations):
            date_display = self._format_date(purchase["purchase_date"]) if purchase["purchase_date"] else "—"
            time_display = purchase["purchase_time"][:5] if purchase["purchase_time"] else "—"
            amount = format_currency(purchase["amount"])
            sc_received = f"{float(purchase['sc_received'] or 0.0):.2f}"
            allocated = format_currency(purchase["allocated_amount"])

            values = [date_display, time_display, amount, sc_received, allocated]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (2, 3, 4):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.purchases_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase["purchase_id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.purchases_table.setCellWidget(row_idx, 5, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_sessions_table(self):
        self.sessions_table.setRowCount(len(self.linked_sessions))
        for row_idx, session in enumerate(self.linked_sessions):
            session_date = self._format_date(session["session_date"]) if session["session_date"] else "—"
            start_time = session["start_time"][:5] if session["start_time"] else "—"
            end_display = f"{self._format_date(session['end_date'])} {session['end_time'][:5]}" if session["end_date"] and session["end_time"] else "—"
            game_type = session["game_type"] or "—"
            status = session["status"] or "—"

            values = [session_date, start_time, end_display, game_type, status]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.sessions_table.setItem(row_idx, col_idx, item)

            # View button
            view_btn = QtWidgets.QPushButton("Open")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(90)
            view_btn.clicked.connect(
                lambda _checked=False, sid=session["game_session_id"]: self._open_session(sid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.sessions_table.setCellWidget(row_idx, 5, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_session(self, session_id):
        # We don't have on_open_session callback in this dialog, so just show message
        QtWidgets.QMessageBox.information(
            self, "Sessions Unavailable", "Session view is not available from this dialog."
        )

    def _handle_open_redemption(self):
        redemption_id = self.position["redemption_id"] if "redemption_id" in self.position.keys() else None
        if not redemption_id:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Redemption ID not found.")
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_redemption(redemption_id))


class RealizedTab(QtWidgets.QWidget):
    def __init__(self, db, on_data_changed=None, on_open_redemption=None, on_open_purchase=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.on_data_changed = on_data_changed
        self.on_open_redemption = on_open_redemption
        self.on_open_purchase = on_open_purchase
        self.all_transactions = []
        self.filtered_transactions = []
        self.column_filters = {}
        self.date_filter = set()
        self.sort_column = None
        self.sort_reverse = False
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self.has_tax_session_notes = self._tax_sessions_has_notes()

        self.columns = [
            "Date",
            "User",
            "Site",
            "Transaction",
            "Cost Basis",
            "Fees",
            "Net P/L",
            "Notes",
        ]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)
        date_row.addWidget(QtWidgets.QLabel("From"))
        self.from_edit = QtWidgets.QLineEdit()
        self.from_edit.setPlaceholderText("MM/DD/YY")
        self.from_calendar = QtWidgets.QPushButton("📅")
        self.from_calendar.setFixedWidth(44)
        date_row.addWidget(self.from_edit)
        date_row.addWidget(self.from_calendar)
        date_row.addWidget(QtWidgets.QLabel("To"))
        self.to_edit = QtWidgets.QLineEdit()
        self.to_edit.setPlaceholderText("MM/DD/YY")
        self.to_calendar = QtWidgets.QPushButton("📅")
        self.to_calendar.setFixedWidth(44)
        date_row.addWidget(self.to_edit)
        date_row.addWidget(self.to_calendar)
        self.apply_date_btn = QtWidgets.QPushButton("Apply")
        self.clear_date_btn = QtWidgets.QPushButton("Clear")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.last30_btn = QtWidgets.QPushButton("Last 30 Days")
        self.this_month_btn = QtWidgets.QPushButton("This Month")
        self.this_year_btn = QtWidgets.QPushButton("This Year")
        self.all_time_btn = QtWidgets.QPushButton("All Time")
        date_row.addWidget(self.apply_date_btn)
        date_row.addWidget(self.clear_date_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
        date_row.addWidget(self.all_time_btn)
        date_row.addStretch(1)
        layout.addLayout(date_row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(6)
        filter_row.addWidget(QtWidgets.QLabel("Users"))
        self.user_filter_btn = QtWidgets.QPushButton("Filter Users...")
        filter_row.addWidget(self.user_filter_btn)
        self.user_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.user_filter_label, set())
        filter_row.addWidget(self.user_filter_label)
        filter_row.addSpacing(12)
        filter_row.addWidget(QtWidgets.QLabel("Sites"))
        self.site_filter_btn = QtWidgets.QPushButton("Filter Sites...")
        filter_row.addWidget(self.site_filter_btn)
        self.site_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.site_filter_label, set())
        filter_row.addWidget(self.site_filter_label)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search realized sessions...")
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addStretch(1)

        self.date_notes_btn = QtWidgets.QPushButton("Add Notes")
        self.date_notes_btn.setObjectName("PrimaryButton")
        self.view_position_btn = QtWidgets.QPushButton("View Position")
        self.view_position_btn.setObjectName("PrimaryButton")
        for btn in (self.date_notes_btn, self.view_position_btn):
            btn.setFixedWidth(btn.sizeHint().width())

        self.date_notes_wrapper = QtWidgets.QWidget()
        date_notes_layout = QtWidgets.QHBoxLayout(self.date_notes_wrapper)
        date_notes_layout.setContentsMargins(0, 0, 0, 0)
        date_notes_layout.addStretch(1)
        date_notes_layout.addWidget(self.date_notes_btn)

        self.transaction_actions = QtWidgets.QWidget()
        transaction_layout = QtWidgets.QHBoxLayout(self.transaction_actions)
        transaction_layout.setContentsMargins(0, 0, 0, 0)
        transaction_layout.setSpacing(8)
        transaction_layout.addStretch(1)
        transaction_layout.addWidget(self.view_position_btn)

        dynamic_width = max(
            self.date_notes_btn.sizeHint().width(),
            self.view_position_btn.sizeHint().width(),
        )
        self.dynamic_placeholder = QtWidgets.QWidget()
        self.dynamic_placeholder.setFixedWidth(dynamic_width)
        self.dynamic_placeholder.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.dynamic_container = QtWidgets.QWidget()
        self.dynamic_container.setFixedWidth(dynamic_width)
        self.dynamic_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.dynamic_stack = QtWidgets.QStackedLayout(self.dynamic_container)
        self.dynamic_stack.setContentsMargins(0, 0, 0, 0)
        self.dynamic_stack.addWidget(self.dynamic_placeholder)
        self.dynamic_stack.addWidget(self.date_notes_wrapper)
        self.dynamic_stack.addWidget(self.transaction_actions)
        self.dynamic_stack.setCurrentWidget(self.dynamic_placeholder)

        self.expand_btn = QtWidgets.QPushButton("Expand All")
        self.collapse_btn = QtWidgets.QPushButton("Collapse All")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        for btn in (self.expand_btn, self.collapse_btn, self.refresh_btn, self.export_btn):
            btn.setFixedWidth(btn.sizeHint().width())

        self.actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.dynamic_container)
        actions_layout.addWidget(self.expand_btn)
        actions_layout.addWidget(self.collapse_btn)
        actions_layout.addWidget(self.refresh_btn)
        actions_layout.addWidget(self.export_btn)
        total_width = dynamic_width + sum(btn.sizeHint().width() for btn in (
            self.expand_btn,
            self.collapse_btn,
            self.refresh_btn,
            self.export_btn,
        ))
        total_width += actions_layout.spacing() * 4
        self.actions_container.setFixedWidth(total_width)
        self.actions_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        search_row.addWidget(self.actions_container, 0, QtCore.Qt.AlignRight)
        layout.addLayout(search_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumSize(0, 0)
        self.tree.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
        )
        self.tree.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        header = self.tree.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 220)
        self.tree.setColumnWidth(3, 200)
        self.tree.setColumnWidth(4, 110)
        self.tree.setColumnWidth(5, 80)
        self.tree.setColumnWidth(6, 110)
        self.tree.setColumnWidth(7, 200)
        self.header = header
        header.viewport().installEventFilter(self)
        layout.addWidget(self.tree, 1)

        self.tree.itemSelectionChanged.connect(self._update_action_buttons)
        self.tree.itemDoubleClicked.connect(self._handle_double_click)

        self.search_edit.textChanged.connect(self.refresh_view)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.date_notes_btn.clicked.connect(self._edit_date_notes)
        self.view_position_btn.clicked.connect(self._view_position)
        self.expand_btn.clicked.connect(self.tree.expandAll)
        self.collapse_btn.clicked.connect(self.tree.collapseAll)
        self.refresh_btn.clicked.connect(self.refresh_view)
        self.export_btn.clicked.connect(self.export_csv)
        self.apply_date_btn.clicked.connect(self.apply_date_filter)
        self.clear_date_btn.clicked.connect(self.clear_date_filter)
        self.today_btn.clicked.connect(lambda: self.set_quick_range("today"))
        self.last30_btn.clicked.connect(lambda: self.set_quick_range("last30"))
        self.this_month_btn.clicked.connect(lambda: self.set_quick_range("month"))
        self.this_year_btn.clicked.connect(lambda: self.set_quick_range("year"))
        self.all_time_btn.clicked.connect(lambda: self.set_quick_range("all"))
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))
        self.user_filter_btn.clicked.connect(self._show_user_filter)
        self.site_filter_btn.clicked.connect(self._show_site_filter)

        self.refresh_view()

    def _tax_sessions_has_notes(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute("PRAGMA table_info(realized_transactions)")
            has_notes = any(row["name"] == "notes" for row in c.fetchall())
        finally:
            conn.close()
        return has_notes

    def eventFilter(self, obj, event):
        if getattr(self, "tree", None) is not None and obj is self.tree.header().viewport():
            header = self.tree.header()
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.tree.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if getattr(self, "_suppress_header_menu", False):
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(header, pos) is not None:
                    return False
                index = header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _set_filter_label(self, label, selected):
        if not selected:
            label.setText("All")
            label.setStyleSheet("color: #62636c;")
        else:
            label.setText(f"{len(selected)} selected")
            label.setStyleSheet("color: #3657c3;")

    def _current_meta(self):
        item = self.tree.currentItem()
        if not item:
            return None
        return item.data(0, QtCore.Qt.UserRole) or {}

    def _update_action_buttons(self):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        if kind == "date":
            self.dynamic_stack.setCurrentWidget(self.date_notes_wrapper)
        elif kind == "transaction":
            self.dynamic_stack.setCurrentWidget(self.transaction_actions)
        else:
            self.dynamic_stack.setCurrentWidget(self.dynamic_placeholder)

    def _handle_double_click(self, *_args):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        if kind == "date":
            self._edit_date_notes()
        elif kind == "transaction":
            self._view_position()

    def pick_date(self, target_edit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        ok_btn = QtWidgets.QPushButton("Select")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def set_quick_range(self, mode):
        today = date.today()
        if mode == "all":
            self.clear_date_filter()
            return
        if mode == "today":
            start = today
            end = today
        elif mode == "last30":
            start = today - timedelta(days=30)
            end = today
        elif mode == "month":
            start = today.replace(day=1)
            end = today
        elif mode == "year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            return
        self.from_edit.setText(start.strftime("%m/%d/%y"))
        self.to_edit.setText(end.strftime("%m/%d/%y"))
        self.active_date_filter = (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        self.refresh_view()

    def apply_date_filter(self):
        start_date = None
        end_date = None
        start_text = self.from_edit.text().strip()
        end_text = self.to_edit.text().strip()
        if start_text:
            try:
                start_date = parse_date_input(start_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid start date.")
                return
        if end_text:
            try:
                end_date = parse_date_input(end_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Invalid Date", "Enter a valid end date.")
                return
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (
            start_date.strftime("%Y-%m-%d") if start_date else None,
            end_date.strftime("%Y-%m-%d") if end_date else None,
        )
        self.refresh_view()

    def clear_date_filter(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.refresh_view()

    def clear_all_filters(self):
        self.from_edit.clear()
        self.to_edit.clear()
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter = set()
        self.column_filters = {}
        self._set_filter_label(self.user_filter_label, self.selected_users)
        self._set_filter_label(self.site_filter_label, self.selected_sites)
        self.search_edit.clear()
        self._clear_selection()
        self.refresh_view()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.tree.clearSelection()
        self._update_action_buttons()

    def _show_user_filter(self):
        users = self._fetch_lookup("users")
        if not users:
            QtWidgets.QMessageBox.information(self, "No Users", "No users found.")
            return
        dialog = ColumnFilterDialog(users, self.selected_users, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_users = dialog.selected_values()
            self._set_filter_label(self.user_filter_label, self.selected_users)
            self.refresh_view()

    def _show_site_filter(self):
        sites = self._fetch_lookup("sites")
        if not sites:
            QtWidgets.QMessageBox.information(self, "No Sites", "No sites found.")
            return
        dialog = ColumnFilterDialog(sites, self.selected_sites, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_sites = dialog.selected_values()
            self._set_filter_label(self.site_filter_label, self.selected_sites)
            self.refresh_view()

    def _fetch_lookup(self, table_name):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT name FROM {table_name} WHERE active = 1 ORDER BY name")
        values = [row["name"] for row in c.fetchall()]
        conn.close()
        return values

    def _show_header_menu(self, col_index):
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        action = menu.exec(QtGui.QCursor.pos())
        if action == sort_asc:
            self.sort_column = col_index
            self.sort_reverse = False
            self.refresh_view()
        elif action == sort_desc:
            self.sort_column = col_index
            self.sort_reverse = True
            self.refresh_view()
        elif action == clear_sort:
            self.sort_column = None
            self.sort_reverse = False
            self.refresh_view()
        elif filter_action and action == filter_action:
            transactions = self._filter_transactions(
                self._last_transactions, exclude_col=col_index, include_search=True
            )
            if col_index == 0:
                values = sorted({t["session_date"] for t in transactions})
                dialog = DateTimeFilterDialog(values, self.date_filter, self, show_time=False)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    self.date_filter = dialog.selected_values()
                    self.refresh_view()
            else:
                values = sorted({self._transaction_value_for_column(t, col_index) for t in transactions})
                selected = self.column_filters.get(col_index, set())
                dialog = ColumnFilterDialog(values, selected, self)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    selected_values = dialog.selected_values()
                    if selected_values:
                        self.column_filters[col_index] = selected_values
                    else:
                        self.column_filters.pop(col_index, None)
                    self.refresh_view()

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _format_currency_or_dash(self, value):
        if value is None:
            return "-"
        return format_currency(value)

    def _transaction_value_for_column(self, tx, col_index):
        if col_index == 0:
            return tx["session_date"]
        if col_index == 1:
            return tx["user_name"]
        if col_index == 2:
            return tx["site_name"]
        if col_index == 3:
            return self._transaction_label(tx)
        if col_index == 4:
            return self._format_currency_or_dash(tx["cost_basis"])
        if col_index == 5:
            return self._format_currency_or_dash(tx.get("fees", 0))
        if col_index == 6:
            # Net P/L with fees deducted
            net_pl = tx["net_pl"]
            fees = tx.get("fees", 0) or 0
            adjusted_net_pl = net_pl - fees
            return self._format_signed_currency(adjusted_net_pl)
        if col_index == 7:
            return tx["notes"] or ""
        return ""

    def _align_numeric(self, item):
        for col in (4, 5, 6):
            item.setTextAlignment(col, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def _apply_status_color(self, item, value):
        if value is None:
            return
        color = "#2e7d32" if value >= 0 else "#c0392b"
        brush = QtGui.QBrush(QtGui.QColor(color))
        for col in range(item.columnCount()):
            item.setForeground(col, brush)

    def _transaction_label(self, tx):
        redemption_amount = tx.get("redemption_amount") or 0.0
        if redemption_amount == 0:
            return "Total Loss"
        return f"Redemption (${redemption_amount:.2f})"

    def _fetch_transactions(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        notes_select = "rt.notes as session_notes" if self.has_tax_session_notes else "NULL as session_notes"
        query = f"""
            SELECT
                rt.id as tax_session_id,
                rt.redemption_date as session_date,
                rt.redemption_id as redemption_id,
                rt.cost_basis,
                rt.net_pl,
                rt.site_id,
                s.name as site_name,
                rt.user_id,
                u.name as user_name,
                r.amount as redemption_amount,
                r.fees as fees,
                r.is_free_sc,
                r.notes as redemption_notes,
                {notes_select}
            FROM realized_transactions rt
            JOIN sites s ON rt.site_id = s.id
            JOIN users u ON rt.user_id = u.id
            LEFT JOIN redemptions r ON rt.redemption_id = r.id
        """
        params = []
        conditions = []
        if self.selected_sites:
            placeholders = ",".join("?" * len(self.selected_sites))
            conditions.append(f"s.name IN ({placeholders})")
            params.extend(list(self.selected_sites))
        if self.selected_users:
            placeholders = ",".join("?" * len(self.selected_users))
            conditions.append(f"u.name IN ({placeholders})")
            params.extend(list(self.selected_users))
        start_date, end_date = self.active_date_filter
        if start_date:
            conditions.append("rt.redemption_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("rt.redemption_date <= ?")
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY rt.redemption_date DESC, s.name ASC, u.name ASC, rt.id ASC"
        c.execute(query, params)
        transactions = []
        for row in c.fetchall():
            redemption_notes = row["redemption_notes"] or ""
            session_notes = row["session_notes"] or ""
            notes = redemption_notes or session_notes
            redemption_amount = row["redemption_amount"] or 0.0
            search_blob = " ".join(
                [
                    row["session_date"],
                    row["site_name"],
                    row["user_name"],
                    f"{row['cost_basis']:.2f}",
                    f"{row['net_pl']:.2f}",
                    f"{redemption_amount:.2f}",
                    notes,
                ]
            ).lower()
            transactions.append(
                {
                    "tax_session_id": row["tax_session_id"],
                    "redemption_id": row["redemption_id"],
                    "session_date": row["session_date"],
                    "site_id": row["site_id"],
                    "site_name": row["site_name"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "cost_basis": row["cost_basis"],
                    "net_pl": row["net_pl"],
                    "fees": (row["fees"] if "fees" in row.keys() else 0) or 0,
                    "redemption_amount": redemption_amount,
                    "is_free_sc": bool(row["is_free_sc"]),
                    "notes": notes,
                    "redemption_notes": redemption_notes,
                    "search_blob": search_blob,
                }
            )
        conn.close()
        return transactions

    def _filter_transactions(self, transactions, exclude_col=None, include_search=True):
        if self.date_filter and exclude_col != 0:
            transactions = [t for t in transactions if t["session_date"] in self.date_filter]
        for col_index, values in self.column_filters.items():
            if col_index == exclude_col:
                continue
            if values:
                transactions = [
                    t for t in transactions if self._transaction_value_for_column(t, col_index) in values
                ]
        if include_search:
            term = self.search_edit.text().strip().lower()
            if term:
                transactions = [t for t in transactions if term in t["search_blob"]]
        return transactions

    def _group_transactions(self, transactions):
        from collections import defaultdict

        dates = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for tx in transactions:
            dates[tx["session_date"]][tx["user_id"]][tx["site_id"]].append(tx)

        notes_by_date = self._fetch_notes_for_dates(dates.keys())
        data = []
        for session_date in sorted(dates.keys(), reverse=True):
            user_groups = []
            date_site_ids = set()
            total_transactions = 0
            date_cost = 0.0
            date_fees = 0.0
            date_net = 0.0
            notes_count = 0
            users_map = dates[session_date]
            for user_id in sorted(
                users_map.keys(),
                key=lambda uid: list(users_map[uid].values())[0][0]["user_name"].lower(),
            ):
                sites_map = users_map[user_id]
                site_groups = []
                user_cost = 0.0
                user_fees = 0.0
                user_net = 0.0
                user_transactions = 0
                for site_id in sorted(
                    sites_map.keys(),
                    key=lambda sid: sites_map[sid][0]["site_name"].lower(),
                ):
                    txs = sites_map[site_id]
                    total_cost = sum(tx["cost_basis"] for tx in txs)
                    total_fees = sum((tx.get("fees", 0) or 0) for tx in txs)
                    # Net totals should account for fees at the transaction level
                    total_net = sum((tx["net_pl"] - (tx.get("fees", 0) or 0)) for tx in txs)
                    transaction_count = len(txs)
                    site_groups.append(
                        {
                            "site_id": site_id,
                            "site_name": txs[0]["site_name"],
                            "total_cost": total_cost,
                            "total_fees": total_fees,
                            "total_net": total_net,
                            "transaction_count": transaction_count,
                            "transactions": txs,
                        }
                    )
                    user_cost += total_cost
                    user_fees += total_fees
                    user_net += total_net
                    user_transactions += transaction_count
                    total_transactions += transaction_count
                    date_site_ids.add(site_id)
                    notes_count += sum(1 for tx in txs if tx["notes"])

                user_groups.append(
                    {
                        "user_id": user_id,
                        "user_name": list(sites_map.values())[0][0]["user_name"],
                        "total_cost": user_cost,
                        "total_fees": user_fees,
                        "total_net": user_net,
                        "transaction_count": user_transactions,
                        "site_count": len(site_groups),
                        "sites": site_groups,
                    }
                )
                date_cost += user_cost
                date_fees += user_fees
                date_net += user_net

            date_notes = notes_by_date.get(session_date, "")
            if date_notes:
                notes_count += 1
            data.append(
                {
                    "date": session_date,
                    "date_cost": date_cost,
                    "date_fees": date_fees,
                    "date_net": date_net,
                    "user_count": len(user_groups),
                    "site_count": len(date_site_ids),
                    "transaction_count": total_transactions,
                    "notes_count": notes_count,
                    "notes": date_notes,
                    "users": user_groups,
                }
            )
        return self._sort_data(data)

    def _sort_data(self, data):
        if self.sort_column is None:
            return data
        reverse = self.sort_reverse

        def sort_key(item):
            if self.sort_column == 0:
                return item["date"]
            if self.sort_column == 1:
                return item["user_count"]
            if self.sort_column == 2:
                return item["site_count"]
            if self.sort_column == 3:
                return item["transaction_count"]
            if self.sort_column == 4:
                return item["date_cost"]
            if self.sort_column == 5:
                return item.get("date_fees", 0)
            if self.sort_column == 6:
                return item["date_net"]
            if self.sort_column == 7:
                return item["notes_count"]
            return item["date"]

        return sorted(data, key=sort_key, reverse=reverse)

    def _render_tree(self, data):
        self.tree.clear()
        for day in data:
            date_values = [
                day["date"],
                f"{day['user_count']} user(s)",
                f"{day['site_count']} site(s)",
                f"{day['transaction_count']} transaction(s)",
                self._format_currency_or_dash(day["date_cost"]),
                self._format_currency_or_dash(day.get("date_fees", 0)),
                self._format_signed_currency(day["date_net"]),
                day.get("notes", ""),
            ]
            date_item = QtWidgets.QTreeWidgetItem(date_values)
            date_item.setData(0, QtCore.Qt.UserRole, {"kind": "date", "date": day["date"]})
            self._align_numeric(date_item)
            self._apply_status_color(date_item, day["date_net"])
            self.tree.addTopLevelItem(date_item)

            for user in day["users"]:
                user_display = f"▸ {user['user_name']}"
                user_values = [
                    "",
                    user_display,
                    f"{user['site_count']} site(s)",
                    f"{user['transaction_count']} transaction(s)",
                    self._format_currency_or_dash(user["total_cost"]),
                    self._format_currency_or_dash(user.get("total_fees", 0)),
                    self._format_signed_currency(user["total_net"]),
                    "",
                ]
                user_item = QtWidgets.QTreeWidgetItem(user_values)
                user_item.setData(
                    0,
                    QtCore.Qt.UserRole,
                    {"kind": "user", "user_id": user["user_id"]},
                )
                self._align_numeric(user_item)
                self._apply_status_color(user_item, user["total_net"])
                date_item.addChild(user_item)

                for site in user["sites"]:
                    site_display = f"  └─ {site['site_name']}"
                    site_values = [
                        "",
                        "",
                        site_display,
                        f"{site['transaction_count']} transaction(s)",
                        self._format_currency_or_dash(site["total_cost"]),
                        self._format_currency_or_dash(site.get("total_fees", 0)),
                        self._format_signed_currency(site["total_net"]),
                        "",
                    ]
                    site_item = QtWidgets.QTreeWidgetItem(site_values)
                    site_item.setData(
                        0,
                        QtCore.Qt.UserRole,
                        {"kind": "site", "site_id": site["site_id"], "user_id": user["user_id"]},
                    )
                    self._align_numeric(site_item)
                    self._apply_status_color(site_item, site["total_net"])
                    user_item.addChild(site_item)

                    for tx in site["transactions"]:
                        transaction_display = f"    └─ {self._transaction_label(tx)}"
                        tx_fees = tx.get("fees", 0) or 0
                        tx_net_pl = tx["net_pl"]
                        adjusted_net_pl = tx_net_pl - tx_fees
                        tx_values = [
                            "",
                            "",
                            "",
                            transaction_display,
                            self._format_currency_or_dash(tx["cost_basis"]),
                            self._format_currency_or_dash(tx_fees),
                            self._format_signed_currency(adjusted_net_pl),
                            tx["notes"] or "",
                        ]
                        tx_item = QtWidgets.QTreeWidgetItem(tx_values)
                        tx_item.setData(
                            0,
                            QtCore.Qt.UserRole,
                            {
                                "kind": "transaction",
                                "tax_session_id": tx["tax_session_id"],
                                "redemption_id": tx["redemption_id"],
                            },
                        )
                        self._align_numeric(tx_item)
                        self._apply_status_color(tx_item, adjusted_net_pl)
                        site_item.addChild(tx_item)

    def refresh_view(self):
        transactions = self._fetch_transactions()
        self._last_transactions = transactions
        transactions = self._filter_transactions(transactions)
        data = self._group_transactions(transactions)
        self._render_tree(data)
        self._update_action_buttons()

    def _fetch_notes_for_dates(self, dates):
        dates = list(dates)
        if not dates:
            return {}
        conn = self.db.get_connection()
        c = conn.cursor()
        placeholders = ",".join("?" * len(dates))
        c.execute(
            f"""
            SELECT session_date, notes
            FROM realized_daily_notes
            WHERE session_date IN ({placeholders})
            """,
            dates,
        )
        notes_by_date = {row["session_date"]: row["notes"] or "" for row in c.fetchall()}
        conn.close()
        return notes_by_date

    def _edit_date_notes(self):
        meta = self._current_meta() or {}
        session_date = meta.get("date")
        if not session_date:
            QtWidgets.QMessageBox.information(self, "Select Date", "Select a date to add notes.")
            return
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT notes FROM realized_daily_notes WHERE session_date = ?",
            (session_date,),
        )
        row = c.fetchone()
        conn.close()
        current_notes = row["notes"] if row and row["notes"] else ""

        dialog = RealizedDateNotesDialog(session_date, current_notes, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_notes = dialog.notes_text()
        conn = self.db.get_connection()
        c = conn.cursor()
        if new_notes:
            c.execute(
                "INSERT OR REPLACE INTO realized_daily_notes (session_date, notes) VALUES (?, ?)",
                (session_date, new_notes),
            )
        else:
            c.execute("DELETE FROM realized_daily_notes WHERE session_date = ?", (session_date,))
        conn.commit()
        conn.close()
        self.refresh_view()

    def _view_position(self):
        meta = self._current_meta() or {}
        if meta.get("kind") != "transaction":
            QtWidgets.QMessageBox.information(
                self, "Select Transaction", "Select an individual transaction to view."
            )
            return
        session_id = meta.get("tax_session_id")
        if not session_id:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Transaction ID not found.")
            return
        position = self._fetch_position_details(session_id)
        if not position:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Transaction not found.")
            return
        allocations = self._fetch_redemption_allocations(position["redemption_id"])
        dialog = RealizedPositionDialog(
            position,
            allocations,
            parent=self,
            on_open_purchase=self.on_open_purchase,
            on_open_redemption=self.on_open_redemption,
        )
        dialog.exec()

    def _fetch_position_details(self, tax_session_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT
                rt.id as tax_session_id,
                rt.redemption_date as session_date,
                rt.cost_basis,
                rt.net_pl,
                rt.redemption_id,
                r.amount as redemption_amount,
                r.notes as redemption_notes,
                s.name as site_name,
                u.name as user_name
            FROM realized_transactions rt
            JOIN redemptions r ON rt.redemption_id = r.id
            JOIN sites s ON rt.site_id = s.id
            JOIN users u ON rt.user_id = u.id
            WHERE rt.id = ?
            """,
            (tax_session_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def _fetch_redemption_allocations(self, redemption_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT
                ra.purchase_id,
                ra.allocated_amount,
                p.purchase_date,
                p.purchase_time,
                p.amount,
                p.sc_received,
                p.remaining_amount
            FROM redemption_allocations ra
            JOIN purchases p ON ra.purchase_id = p.id
            WHERE ra.redemption_id = ?
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time,'00:00:00') ASC, p.id ASC
            """,
            (redemption_id,),
        )
        allocations = [dict(row) for row in c.fetchall()]
        conn.close()
        return allocations

    def find_and_select_redemption(self, redemption_id):
        """Find and select a specific redemption in the tree by expanding parent items."""
        def search_tree(item):
            # Check if this item is the transaction we're looking for
            meta = item.data(0, QtCore.Qt.UserRole)
            if meta and meta.get("kind") == "transaction" and meta.get("redemption_id") == redemption_id:
                return item
            # Recursively search children
            for i in range(item.childCount()):
                result = search_tree(item.child(i))
                if result:
                    return result
            return None

        # Search all top-level items
        for i in range(self.tree.topLevelItemCount()):
            result = search_tree(self.tree.topLevelItem(i))
            if result:
                # Expand all parents to make it visible
                parent = result.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                # Select and scroll to the item
                self.tree.setCurrentItem(result)
                self.tree.scrollToItem(result, QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
        return False

    def export_csv(self):
        import csv

        default_name = f"realized_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Realized Sessions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)

            def write_item(item):
                writer.writerow([item.text(col) for col in range(len(self.columns))])
                for idx in range(item.childCount()):
                    write_item(item.child(idx))

            for idx in range(self.tree.topLevelItemCount()):
                write_item(self.tree.topLevelItem(idx))


class ReportsTab(QtWidgets.QWidget):
    """Reports Hub with left navigation and right panel for report display"""
    
    def __init__(self, db, refresh_stats_callback, parent=None):
        super().__init__(parent)
        self.db = db
        self.refresh_stats = refresh_stats_callback
        self.reporting_service = ReportingService(db)
        self.current_report = None
        self.current_filters = ReportFilters()
        
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left navigation panel
        left_panel = QtWidgets.QWidget()
        left_panel.setObjectName("ReportsNav")
        left_panel.setFixedWidth(200)
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        
        nav_title = QtWidgets.QLabel("Reports")
        nav_title.setObjectName("SectionTitle")
        left_layout.addWidget(nav_title)
        
        # Navigation list
        self.nav_list = QtWidgets.QListWidget()
        self.nav_list.setObjectName("ReportsNavList")
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        
        # Load available reports
        available_reports = self.reporting_service.list_available_reports()
        self.reports_by_category = {}
        for report in available_reports:
            if report.category not in self.reports_by_category:
                self.reports_by_category[report.category] = []
            self.reports_by_category[report.category].append(report)
        
        # Build navigation tree
        for category in ["Dashboard", "Sites", "Games", "Sessions", "Redemptions", "Cashback", "Tax Center"]:
            if category in self.reports_by_category:
                # Category header
                category_item = QtWidgets.QListWidgetItem(category)
                category_item.setFlags(QtCore.Qt.ItemIsEnabled)
                category_item.setData(QtCore.Qt.UserRole, {"type": "category"})
                font = category_item.font()
                font.setBold(True)
                category_item.setFont(font)
                self.nav_list.addItem(category_item)
                
                # Reports in category
                for report in self.reports_by_category[category]:
                    report_item = QtWidgets.QListWidgetItem(f"  {report.title}")
                    report_item.setData(QtCore.Qt.UserRole, {"type": "report", "report": report})
                    self.nav_list.addItem(report_item)
        
        left_layout.addWidget(self.nav_list)
        left_layout.addStretch()
        
        # Right panel (report display area)
        self.right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(12)
        
        # Filter bar
        self.filter_bar = ReportFilterBar(db)
        self.filter_bar.filters_applied.connect(self._on_filters_applied)
        right_layout.addWidget(self.filter_bar)
        
        # Scroll area for report content
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        self.report_content = QtWidgets.QWidget()
        self.report_content.setObjectName("ReportContent")
        self.report_layout = QtWidgets.QVBoxLayout(self.report_content)
        self.report_layout.setContentsMargins(15, 15, 15, 15)
        self.report_layout.setSpacing(16)
        
        scroll.setWidget(self.report_content)
        right_layout.addWidget(scroll, 1)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(self.right_panel, 1)
        
        # Show welcome message initially
        self._show_welcome()
    
    def _show_welcome(self):
        """Display welcome message when no report is selected"""
        self._clear_report_content()
        welcome = QtWidgets.QLabel(
            "Select a report from the left navigation to begin.\n\n"
            "All reports support date range filtering, grouping intervals, "
            "and CSV export."
        )
        welcome.setAlignment(QtCore.Qt.AlignCenter)
        welcome.setWordWrap(True)
        welcome.setStyleSheet("color: #666; font-size: 14px; padding: 40px;")
        self.report_layout.addWidget(welcome)
        self.report_layout.addStretch()
    
    def _clear_report_content(self):
        """Remove all widgets from report content area"""
        while self.report_layout.count():
            item = self.report_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _on_nav_changed(self, row):
        """Handle navigation selection change"""
        if row < 0:
            return
        
        item = self.nav_list.item(row)
        data = item.data(QtCore.Qt.UserRole)
        
        if data["type"] == "category":
            # Category header clicked - do nothing
            return
        elif data["type"] == "report":
            self.current_report = data["report"]
            self._load_report()
    
    def _on_filters_applied(self, filters: ReportFilters):
        """Handle filter changes"""
        self.current_filters = filters
        if self.current_report:
            self._load_report()
    
    def _load_report(self):
        """Load and display the current report"""
        if not self.current_report:
            return
        
        try:
            result = self.reporting_service.run_report(
                self.current_report.report_id,
                self.current_filters
            )
            self._display_report(result)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Report Error",
                f"Failed to generate report: {str(e)}"
            )
    
    def _display_report(self, result):
        """Display report results"""
        self._clear_report_content()
        
        # Report title
        title = QtWidgets.QLabel(result.title)
        title.setObjectName("SectionTitle")
        self.report_layout.addWidget(title)
        
        # KPI cards
        if result.kpis:
            kpi_widget = KPICardsWidget(result.kpis)
            self.report_layout.addWidget(kpi_widget)
        
        # Charts (combine all series into one chart)
        if result.series:
            chart_widget = self._create_chart_widget(result.series)
            self.report_layout.addWidget(chart_widget)
        
        # Data table
        if result.rows:
            table_widget = ReportTableWidget(result.rows)
            table_widget.export_requested.connect(
                lambda: self._export_csv(result)
            )
            self.report_layout.addWidget(table_widget)
        
        self.report_layout.addStretch()
    
    def _create_chart_widget(self, series_list):
        """Create a chart widget from series data (supports multiple series)"""
        from PySide6.QtGui import QColor, QPen
        
        if not series_list:
            return QtWidgets.QWidget()
        
        # Handle single series (backward compatibility)
        if not isinstance(series_list, list):
            series_list = [series_list]
        
        chart = QChart()
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Determine chart type from first series
        first_series_type = series_list[0].series_type
        
        if first_series_type == "bar":
            series = QBarSeries()
            categories = []
            
            for series_data in series_list:
                bar_set = QBarSet(series_data.name)
                for label, value in series_data.data:
                    bar_set.append(value)
                    if not categories or label not in categories:
                        categories.append(str(label))
                
                if series_data.color:
                    bar_set.setColor(QColor(series_data.color))
                
                series.append(bar_set)
            
            chart.addSeries(series)
            
            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, QtCore.Qt.AlignBottom)
            series.attachAxis(axis_x)
            
            axis_y = QValueAxis()
            chart.addAxis(axis_y, QtCore.Qt.AlignLeft)
            series.attachAxis(axis_y)
        
        elif first_series_type == "line":
            for series_data in series_list:
                line_series = QLineSeries()
                line_series.setName(series_data.name)
                
                for idx, (label, value) in enumerate(series_data.data):
                    line_series.append(idx, value)
                
                # Apply color if specified
                if series_data.color:
                    pen = QPen(QColor(series_data.color))
                    pen.setWidth(2)
                    line_series.setPen(pen)
                
                chart.addSeries(line_series)
            
            chart.createDefaultAxes()
        
        chart.legend().setVisible(True)
        chart.legend().setAlignment(QtCore.Qt.AlignBottom)
        
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QtGui.QPainter.Antialiasing)
        chart_view.setMinimumHeight(300)
        
        return chart_view
    
    def _export_csv(self, result):
        """Export report data to CSV"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Report",
            f"{result.report_id}_{date.today().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if result.rows:
                    writer = csv.DictWriter(f, fieldnames=result.rows[0].keys())
                    writer.writeheader()
                    writer.writerows(result.rows)
            
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"Report exported to:\n{filename}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Export Failed",
                f"Failed to export report: {str(e)}"
            )


class ReportFilterBar(QtWidgets.QWidget):
    """Reusable filter bar for reports"""
    
    filters_applied = QtCore.Signal(ReportFilters)
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Date range with calendar pickers
        layout.addWidget(QtWidgets.QLabel("From:"))
        start_date_container = QtWidgets.QHBoxLayout()
        start_date_container.setSpacing(4)
        self.start_date_edit = QtWidgets.QLineEdit()
        self.start_date_edit.setPlaceholderText("MM/DD/YY")
        self.start_date_edit.setFixedWidth(90)
        start_date_container.addWidget(self.start_date_edit)
        self.start_calendar_btn = QtWidgets.QPushButton("📅")
        self.start_calendar_btn.setFixedWidth(44)
        self.start_calendar_btn.clicked.connect(self._pick_start_date)
        start_date_container.addWidget(self.start_calendar_btn)
        layout.addLayout(start_date_container)
        
        layout.addWidget(QtWidgets.QLabel("To:"))
        end_date_container = QtWidgets.QHBoxLayout()
        end_date_container.setSpacing(4)
        self.end_date_edit = QtWidgets.QLineEdit()
        self.end_date_edit.setPlaceholderText("MM/DD/YY")
        self.end_date_edit.setFixedWidth(90)
        end_date_container.addWidget(self.end_date_edit)
        self.end_calendar_btn = QtWidgets.QPushButton("📅")
        self.end_calendar_btn.setFixedWidth(44)
        self.end_calendar_btn.clicked.connect(self._pick_end_date)
        end_date_container.addWidget(self.end_calendar_btn)
        layout.addLayout(end_date_container)
        
        # Group interval
        layout.addWidget(QtWidgets.QLabel("Group:"))
        self.group_combo = QtWidgets.QComboBox()
        self.group_combo.addItems(["All Time", "Daily", "Weekly", "Monthly", "Quarterly", "Yearly"])
        self.group_combo.setCurrentText("Monthly")
        self.group_combo.setFixedWidth(120)
        layout.addWidget(self.group_combo)
        
        # User filter (autocomplete with placeholder)
        layout.addWidget(QtWidgets.QLabel("User:"))
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self._load_users()
        self.user_combo.setCurrentIndex(-1)  # No selection
        self.user_combo.lineEdit().setPlaceholderText("All Users")
        self.user_combo.setFixedWidth(160)
        layout.addWidget(self.user_combo)
        
        # Site filter (autocomplete with placeholder)
        layout.addWidget(QtWidgets.QLabel("Site:"))
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self._load_sites()
        self.site_combo.setCurrentIndex(-1)  # No selection
        self.site_combo.lineEdit().setPlaceholderText("All Sites")
        self.site_combo.setFixedWidth(160)
        layout.addWidget(self.site_combo)
        
        layout.addStretch()
        
        # Buttons
        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_filters)
        layout.addWidget(apply_btn)
        
        reset_btn = QtWidgets.QPushButton("Reset")
        reset_btn.clicked.connect(self._reset_filters)
        layout.addWidget(reset_btn)
        
        # Set default to current year
        today = date.today()
        self.start_date_edit.setText(f"01/01/{today.year % 100:02d}")
        self.end_date_edit.setText(today.strftime("%m/%d/%y"))
        
        # Setup autocompleters
        self._update_completers()
    
    def _load_users(self):
        """Load users into combo box"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name FROM users ORDER BY name")
        for row in c.fetchall():
            self.user_combo.addItem(row["name"], row["id"])
        conn.close()
    
    def _load_sites(self):
        """Load sites into combo box"""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name FROM sites ORDER BY name")
        for row in c.fetchall():
            self.site_combo.addItem(row["name"], row["id"])
        conn.close()
    
    def _update_completers(self):
        """Setup autocomplete for user and site combos"""
        for combo in (self.user_combo, self.site_combo):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchContains)
            completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
    
    def _pick_start_date(self):
        """Show calendar picker for start date"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Start Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        
        # Set initial date from current text
        current_text = self.start_date_edit.text().strip()
        if current_text:
            try:
                parsed = parse_date_input(current_text)
                calendar.setSelectedDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
            except:
                calendar.setSelectedDate(QtCore.QDate.currentDate())
        else:
            calendar.setSelectedDate(QtCore.QDate.currentDate())
        
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.start_date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
    
    def _pick_end_date(self):
        """Show calendar picker for end date"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select End Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        
        # Set initial date from current text
        current_text = self.end_date_edit.text().strip()
        if current_text:
            try:
                parsed = parse_date_input(current_text)
                calendar.setSelectedDate(QtCore.QDate(parsed.year, parsed.month, parsed.day))
            except:
                calendar.setSelectedDate(QtCore.QDate.currentDate())
        else:
            calendar.setSelectedDate(QtCore.QDate.currentDate())
        
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.end_date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
    
    def _apply_filters(self):
        """Apply current filter settings"""
        filters = ReportFilters()
        
        # Parse dates
        start_text = self.start_date_edit.text().strip()
        if start_text:
            try:
                start_date = parse_date_input(start_text)
                filters.start_date = start_date.strftime("%Y-%m-%d")
            except:
                pass
        
        end_text = self.end_date_edit.text().strip()
        if end_text:
            try:
                end_date = parse_date_input(end_text)
                filters.end_date = end_date.strftime("%Y-%m-%d")
            except:
                pass
        
        # Group interval (handle "All Time" option)
        group_text = self.group_combo.currentText()
        if group_text != "All Time":
            filters.group_interval = group_text.lower()
        else:
            filters.group_interval = None
        
        # User filter - handle editable combo
        user_text = self.user_combo.currentText().strip()
        if user_text and user_text.lower() != "all users":
            # Try to match by text first
            user_id = None
            for i in range(self.user_combo.count()):
                if self.user_combo.itemText(i).lower() == user_text.lower():
                    user_id = self.user_combo.itemData(i)
                    break
            if user_id is not None:
                filters.user_ids = [user_id]
        
        # Site filter - handle editable combo
        site_text = self.site_combo.currentText().strip()
        if site_text and site_text.lower() != "all sites":
            # Try to match by text first
            site_id = None
            for i in range(self.site_combo.count()):
                if self.site_combo.itemText(i).lower() == site_text.lower():
                    site_id = self.site_combo.itemData(i)
                    break
            if site_id is not None:
                filters.site_ids = [site_id]
        
        self.filters_applied.emit(filters)
    
    def _reset_filters(self):
        """Reset filters to defaults"""
        today = date.today()
        self.start_date_edit.setText(f"01/01/{today.year % 100:02d}")
        self.end_date_edit.setText(today.strftime("%m/%d/%y"))
        self.group_combo.setCurrentText("Monthly")
        self.user_combo.setCurrentIndex(-1)  # Clear to show placeholder
        self.user_combo.clearEditText()
        self.site_combo.setCurrentIndex(-1)  # Clear to show placeholder
        self.site_combo.clearEditText()
        self._apply_filters()


class KPICardsWidget(QtWidgets.QWidget):
    """Display KPI cards grouped by sections"""
    
    def __init__(self, kpis, parent=None):
        super().__init__(parent)
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        
        # Group KPIs by section
        sections = {}
        for kpi in kpis:
            section = kpi.section if hasattr(kpi, 'section') and kpi.section else "Overview"
            if section not in sections:
                sections[section] = []
            sections[section].append(kpi)
        
        # Display each section
        for section_name, section_kpis in sections.items():
            # Section header
            section_label = QtWidgets.QLabel(section_name)
            section_label.setObjectName("SectionHeader")
            main_layout.addWidget(section_label)
            
            # KPI cards in a row
            cards_layout = QtWidgets.QHBoxLayout()
            cards_layout.setSpacing(12)
            
            for kpi in section_kpis:
                card = self._create_kpi_card(kpi)
                cards_layout.addWidget(card)
            
            cards_layout.addStretch()
            main_layout.addLayout(cards_layout)
        
        main_layout.addStretch()
    
    def _create_kpi_card(self, kpi):
        """Create a single KPI card"""
        card = QtWidgets.QFrame()
        card.setObjectName("KPICard")
        card.setFrameShape(QtWidgets.QFrame.StyledPanel)
        card.setMinimumWidth(150)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        
        label = QtWidgets.QLabel(kpi.label)
        label.setObjectName("KPILabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        
        value = QtWidgets.QLabel(kpi.formatted_value())
        value.setObjectName("KPIValue")
        layout.addWidget(value)
        
        if kpi.trend is not None:
            trend_text = f"{kpi.trend:+.1f}%"
            trend_color = "green" if kpi.trend > 0 else "red" if kpi.trend < 0 else "gray"
            trend = QtWidgets.QLabel(trend_text)
            trend.setStyleSheet(f"color: {trend_color}; font-size: 11px;")
            layout.addWidget(trend)
        
        return card


class ReportTableWidget(QtWidgets.QWidget):
    """Display report data in a table with export button"""
    
    export_requested = QtCore.Signal()
    
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header with export button
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Data Table"))
        header.addStretch()
        export_btn = QtWidgets.QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_requested.emit)
        header.addWidget(export_btn)
        layout.addLayout(header)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        if rows:
            # Set up columns
            headers = list(rows[0].keys())
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            
            # Populate rows
            self.table.setRowCount(len(rows))
            for row_idx, row_data in enumerate(rows):
                for col_idx, (key, value) in enumerate(row_data.items()):
                    # Format value
                    if isinstance(value, float):
                        if key.lower().endswith(("rate", "percent", "rtp")):
                            display = f"{value:.1f}%"
                        else:
                            display = f"{value:,.2f}"
                    elif value is None:
                        display = ""
                    else:
                        display = str(value)
                    
                    item = QtWidgets.QTableWidgetItem(display)
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.table.setItem(row_idx, col_idx, item)
            
            self.table.resizeColumnsToContents()
        
        layout.addWidget(self.table)


class PlaceholderTab(QtWidgets.QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        title = QtWidgets.QLabel(label)
        title.setObjectName("SectionTitle")
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(title)
        layout.addStretch(1)


class SetupEditDialog(QtWidgets.QDialog):
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


class UserEditDialog(SetupEditDialog):
    def __init__(self, user=None, parent=None):
        super().__init__(parent)
        self.user = user
        self.setWindowTitle("Edit User" if user else "Add User")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)

        # Row 0: User Name (fills space) + Active (right-justified)
        form.addWidget(QtWidgets.QLabel("User Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)

        # Row 1: Notes (fills full width)
        form.addWidget(QtWidgets.QLabel("Notes"), 1, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 1, 1, 1, 3)

        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)

        if user:
            self.name_edit.setText(user["name"])
            self.active_check.setChecked(bool(user["active"]))
            self.notes_edit.setPlainText(user["notes"] or "")
            self._set_valid(self.name_edit)

    def _validate_inline(self):
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "User name is required.")
            return False
        self._set_valid(self.name_edit)
        return True

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def data(self):
        return {
            "name": self.name_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class UserViewDialog(QtWidgets.QDialog):
    def __init__(self, user, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.user = user
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View User")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        # Row 0: User Name (fills space) + Active (right-justified)
        user_name_label = QtWidgets.QLabel("User Name")
        user_name_value = QtWidgets.QLabel(user["name"])
        user_name_value.setObjectName("InfoField")
        form.addWidget(user_name_label, 0, 0)
        form.addWidget(user_name_value, 0, 1)

        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(user["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # Row 1: Notes (fills full width)
        notes_value = user["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 1, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 1, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            form.addWidget(notes_field, 1, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class SiteEditDialog(SetupEditDialog):
    def __init__(self, site=None, parent=None):
        super().__init__(parent)
        self.site = site
        self.setWindowTitle("Edit Site" if site else "Add Site")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        self.sc_rate_edit = QtWidgets.QLineEdit()
        self.sc_rate_edit.setPlaceholderText("1.0")
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)

        form.addWidget(QtWidgets.QLabel("Site Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)
        form.addWidget(QtWidgets.QLabel("SC Rate (USD/SC)"), 1, 0)
        form.addWidget(self.sc_rate_edit, 1, 1, 1, 3)
        form.addWidget(QtWidgets.QLabel("Notes"), 2, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 2, 1, 1, 3)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)
        self.sc_rate_edit.textChanged.connect(self._validate_inline)

        if site:
            self.name_edit.setText(site["name"])
            self.sc_rate_edit.setText(f"{float(site['sc_rate'] or 1.0):.4f}")
            self.active_check.setChecked(bool(site["active"]))
            self.notes_edit.setPlainText(site["notes"] or "")
        else:
            self.sc_rate_edit.setText("1.0")
        self._validate_inline()

    def _validate_inline(self):
        ok = True
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Site name is required.")
            ok = False
        else:
            self._set_valid(self.name_edit)

        sc_rate_text = self.sc_rate_edit.text().strip()
        if not sc_rate_text:
            self._set_invalid(self.sc_rate_edit, "SC rate is required.")
            ok = False
        else:
            try:
                sc_rate = float(sc_rate_text)
                if sc_rate <= 0:
                    raise ValueError
                self._set_valid(self.sc_rate_edit)
            except ValueError:
                self._set_invalid(self.sc_rate_edit, "SC rate must be a number > 0.")
                ok = False
        return ok

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def data(self):
        return {
            "name": self.name_edit.text().strip(),
            "sc_rate": float(self.sc_rate_edit.text().strip()),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class SiteViewDialog(QtWidgets.QDialog):
    def __init__(self, site, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.site = site
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Site")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        # Site Name field
        site_name_label = QtWidgets.QLabel("Site Name")
        site_name_value = QtWidgets.QLabel(site["name"])
        site_name_value.setObjectName("InfoField")
        form.addWidget(site_name_label, 0, 0)
        form.addWidget(site_name_value, 0, 1)

        # Active checkbox
        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(site["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # SC Rate field
        sc_rate_label = QtWidgets.QLabel("SC Rate")
        sc_rate_value = QtWidgets.QLabel(f"{float(site['sc_rate'] or 1.0):.4f}")
        sc_rate_value.setObjectName("InfoField")
        form.addWidget(sc_rate_label, 1, 0)
        form.addWidget(sc_rate_value, 1, 1, 1, 3)

        # Notes field
        notes_value = site["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 2, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 2, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            form.addWidget(notes_field, 2, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class CardEditDialog(SetupEditDialog):
    def __init__(self, users, card=None, parent=None):
        super().__init__(parent)
        self.users = users or []
        self.card = card
        self._user_lookup = {name.lower(): name for name in self.users}
        self.setWindowTitle("Edit Card" if card else "Add Card")
        self.resize(500, 240)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(2, 80)

        self.name_edit = QtWidgets.QLineEdit()
        self.last_four_edit = QtWidgets.QLineEdit()
        self.last_four_edit.setPlaceholderText("1234")
        self.last_four_edit.setMaxLength(4)
        self.last_four_edit.setMaximumWidth(80)
        self.last_four_edit.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.cashback_edit = QtWidgets.QLineEdit()
        self.cashback_edit.setPlaceholderText("0.00")
        self.cashback_edit.setMaximumWidth(80)
        self.cashback_edit.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(self.users)
        self.user_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)

        form.addWidget(QtWidgets.QLabel("Card Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)
        form.addWidget(QtWidgets.QLabel("User"), 1, 0)
        form.addWidget(self.user_combo, 1, 1)
        form.addWidget(QtWidgets.QLabel("Last 4"), 1, 2)
        form.addWidget(self.last_four_edit, 1, 3)
        form.addWidget(QtWidgets.QLabel("Cashback %"), 2, 0)
        form.addWidget(self.cashback_edit, 2, 1)
        form.addWidget(QtWidgets.QLabel("Notes"), 3, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 3, 1, 1, 3)
        layout.addLayout(form)

        # Add recalculate cashback button only when editing existing card
        if card:
            recalc_row = QtWidgets.QHBoxLayout()
            recalc_info = QtWidgets.QLabel("If you changed the cashback %, you can retroactively update all purchases:")
            recalc_info.setObjectName("HelperText")
            recalc_info.setWordWrap(True)
            recalc_row.addWidget(recalc_info)
            self.recalc_btn = QtWidgets.QPushButton("Recalculate All Purchases")
            self.recalc_btn.clicked.connect(self._recalculate_cashback)
            recalc_row.addWidget(self.recalc_btn)
            layout.addLayout(recalc_row)
            layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)
        self.cashback_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)

        if card:
            self.name_edit.setText(card["name"])
            self.last_four_edit.setText(card["last_four"] if "last_four" in card.keys() and card["last_four"] else "")
            self.cashback_edit.setText(f"{float(card['cashback_rate'] or 0):.2f}")
            if card["user_name"]:
                self.user_combo.setCurrentText(card["user_name"])
            self.active_check.setChecked(bool(card["active"]))
            self.notes_edit.setPlainText(card["notes"] or "")
        else:
            self.user_combo.setCurrentIndex(-1)
            self.user_combo.setEditText("")
        self._validate_inline()

    def _validate_inline(self):
        ok = True
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Card name is required.")
            ok = False
        else:
            self._set_valid(self.name_edit)

        cashback_text = self.cashback_edit.text().strip()
        if cashback_text:
            try:
                cashback = float(cashback_text)
                if cashback < 0 or cashback > 100:
                    raise ValueError
                self._set_valid(self.cashback_edit)
            except ValueError:
                self._set_invalid(self.cashback_edit, "Cashback must be between 0 and 100.")
                ok = False
        else:
            self._set_valid(self.cashback_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid user.")
            ok = False
        else:
            self._set_valid(self.user_combo)
        return ok

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def _recalculate_cashback(self):
        """Recalculate cashback for all purchases made with this card"""
        if not self.card:
            return

        # Get current cashback rate from form
        cashback_text = self.cashback_edit.text().strip()
        if not cashback_text:
            QtWidgets.QMessageBox.warning(
                self,
                "No Cashback Rate",
                "Please enter a cashback rate first."
            )
            return

        try:
            new_cashback_rate = float(cashback_text)
            if new_cashback_rate < 0 or new_cashback_rate > 100:
                raise ValueError
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Cashback Rate",
                "Please enter a valid cashback rate between 0 and 100."
            )
            return

        # Get count of purchases for this card
        from database import Database
        db = Database()
        conn = db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) as count FROM purchases WHERE card_id = ?",
            (self.card["id"],)
        )
        count = c.fetchone()["count"]
        conn.close()

        if count == 0:
            QtWidgets.QMessageBox.information(
                self,
                "No Purchases",
                "No purchases found for this card."
            )
            return

        # Show warning dialog
        reply = QtWidgets.QMessageBox.question(
            self,
            "Recalculate Cashback",
            f"This will recalculate cashback for {count} purchase(s) using the new rate of {new_cashback_rate:.2f}%.\n\nContinue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Perform the recalculation
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            conn = db.get_connection()
            c = conn.cursor()
            c.execute(
                """
                UPDATE purchases
                SET cashback_earned = amount * (? / 100.0)
                WHERE card_id = ?
                """,
                (new_cashback_rate, self.card["id"])
            )
            updated_count = c.rowcount
            conn.commit()
            conn.close()

            QtWidgets.QMessageBox.information(
                self,
                "Recalculation Complete",
                f"Successfully recalculated cashback for {updated_count} purchase(s)."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to recalculate cashback: {str(e)}"
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def data(self):
        user_text = self.user_combo.currentText().strip()
        return {
            "name": self.name_edit.text().strip(),
            "last_four": self.last_four_edit.text().strip() or None,
            "cashback_rate": float(self.cashback_edit.text().strip() or 0.0),
            "user_name": self._user_lookup.get(user_text.lower(), user_text),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class CardViewDialog(QtWidgets.QDialog):
    def __init__(self, card, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.card = card
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Card")
        self.resize(500, 240)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(2, 80)

        # Card Name field
        card_name_label = QtWidgets.QLabel("Card Name")
        card_name_value = QtWidgets.QLabel(card["name"])
        card_name_value.setObjectName("InfoField")
        form.addWidget(card_name_label, 0, 0)
        form.addWidget(card_name_value, 0, 1)

        # Active checkbox
        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(card["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # User field
        user_label = QtWidgets.QLabel("User")
        user_value = QtWidgets.QLabel(card["user_name"] or "—")
        user_value.setObjectName("InfoField")
        user_value.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        form.addWidget(user_label, 1, 0)
        form.addWidget(user_value, 1, 1)

        # Last 4 field
        last_four_label = QtWidgets.QLabel("Last 4")
        last_four_value = QtWidgets.QLabel(card["last_four"] if "last_four" in card.keys() and card["last_four"] else "—")
        last_four_value.setObjectName("InfoField")
        last_four_value.setMaximumWidth(80)
        form.addWidget(last_four_label, 1, 2)
        form.addWidget(last_four_value, 1, 3)

        # Cashback % field
        cashback_label = QtWidgets.QLabel("Cashback %")
        cashback_value = QtWidgets.QLabel(f"{float(card['cashback_rate'] or 0):.2f}")
        cashback_value.setObjectName("InfoField")
        cashback_value.setMaximumWidth(80)
        form.addWidget(cashback_label, 2, 0)
        form.addWidget(cashback_value, 2, 1)

        # Notes field
        notes_value = card["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 3, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 3, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            form.addWidget(notes_field, 3, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class MethodEditDialog(SetupEditDialog):
    def __init__(self, users, method=None, parent=None):
        super().__init__(parent)
        self.users = users or []
        self.method = method
        self._user_lookup = {name.lower(): name for name in self.users}
        self.setWindowTitle("Edit Method" if method else "Add Method")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        self.method_type_edit = QtWidgets.QLineEdit()
        self.method_type_edit.setPlaceholderText("e.g., Bank/ACH, Card, PayPal, Gift Card")
        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(self.users)
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)

        form.addWidget(QtWidgets.QLabel("Method Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)
        form.addWidget(QtWidgets.QLabel("Method Type"), 1, 0)
        form.addWidget(self.method_type_edit, 1, 1, 1, 3)
        form.addWidget(QtWidgets.QLabel("User"), 2, 0)
        form.addWidget(self.user_combo, 2, 1, 1, 3)
        form.addWidget(QtWidgets.QLabel("Notes"), 3, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 3, 1, 1, 3)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setDefault(True)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)
        self.method_type_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)

        if method:
            self.name_edit.setText(method["name"])
            if method["method_type"]:
                self.method_type_edit.setText(method["method_type"])
            if method["user_name"]:
                self.user_combo.setCurrentText(method["user_name"])
            self.active_check.setChecked(bool(method["active"]))
            self.notes_edit.setPlainText(method["notes"] or "")
        else:
            self.user_combo.setCurrentIndex(-1)
            self.user_combo.setEditText("")
        self._validate_inline()

    def _validate_inline(self):
        ok = True
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Method name is required.")
            ok = False
        else:
            self._set_valid(self.name_edit)
        
        if not self.method_type_edit.text().strip():
            self._set_invalid(self.method_type_edit, "Method type is required.")
            ok = False
        else:
            self._set_valid(self.method_type_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid user.")
            ok = False
        else:
            self._set_valid(self.user_combo)
        return ok

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def data(self):
        user_text = self.user_combo.currentText().strip()
        return {
            "name": self.name_edit.text().strip(),
            "method_type": self.method_type_edit.text().strip(),
            "user_name": self._user_lookup.get(user_text.lower(), user_text),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class MethodViewDialog(QtWidgets.QDialog):
    def __init__(self, method, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.method = method
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Method")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        # Method Name field
        method_name_label = QtWidgets.QLabel("Method Name")
        method_name_value = QtWidgets.QLabel(method["name"])
        method_name_value.setObjectName("InfoField")
        form.addWidget(method_name_label, 0, 0)
        form.addWidget(method_name_value, 0, 1)

        # Active checkbox
        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(method["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # Method Type field
        method_type_label = QtWidgets.QLabel("Method Type")
        method_type_value = QtWidgets.QLabel(method["method_type"] or "—")
        method_type_value.setObjectName("InfoField")
        form.addWidget(method_type_label, 1, 0)
        form.addWidget(method_type_value, 1, 1, 1, 3)

        # User field
        user_label = QtWidgets.QLabel("User")
        user_value = QtWidgets.QLabel(method["user_name"] or "—")
        user_value.setObjectName("InfoField")
        form.addWidget(user_label, 2, 0)
        form.addWidget(user_value, 2, 1, 1, 3)

        # Notes field
        notes_value = method["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 3, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 3, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            form.addWidget(notes_field, 3, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class GameTypeEditDialog(SetupEditDialog):
    def __init__(self, game_type=None, parent=None):
        super().__init__(parent)
        self.game_type = game_type
        self.setWindowTitle("Edit Game Type" if game_type else "Add Game Type")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        self.name_edit = QtWidgets.QLineEdit()
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)

        form.addWidget(QtWidgets.QLabel("Game Type Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)
        form.addWidget(QtWidgets.QLabel("Notes"), 1, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 1, 1, 1, 3)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)

        if game_type:
            self.name_edit.setText(game_type["name"])
            self.active_check.setChecked(bool(game_type["active"]))
            self.notes_edit.setPlainText(game_type["notes"] or "")
        self._validate_inline()

    def _validate_inline(self):
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Game type name is required.")
            return False
        self._set_valid(self.name_edit)
        return True

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def data(self):
        return {
            "name": self.name_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class GameTypeViewDialog(QtWidgets.QDialog):
    def __init__(self, game_type, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.game_type = game_type
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Game Type")
        self.resize(500, 200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        # Game Type Name field
        game_type_name_label = QtWidgets.QLabel("Game Type Name")
        game_type_name_value = QtWidgets.QLabel(game_type["name"])
        game_type_name_value.setObjectName("InfoField")
        form.addWidget(game_type_name_label, 0, 0)
        form.addWidget(game_type_name_value, 0, 1)

        # Active checkbox
        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(game_type["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # Notes field
        notes_value = game_type["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 1, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 1, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            form.addWidget(notes_field, 1, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)


class GameEditDialog(SetupEditDialog):
    def __init__(self, game_types, game=None, parent=None):
        super().__init__(parent)
        self.game_types = game_types or []
        self.game = game
        self._type_lookup = {name.lower(): name for name in self.game_types}
        self.setWindowTitle("Edit Game" if game else "Add Game")
        self.resize(500, 240)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(2, 60)

        self.name_edit = QtWidgets.QLineEdit()
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.setEditable(True)
        self.type_combo.addItems(self.game_types)
        self.rtp_edit = QtWidgets.QLineEdit()
        self.rtp_edit.setPlaceholderText("96.0")
        self.rtp_edit.setMaximumWidth(80)
        self.rtp_edit.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.type_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 4 + 12)
        self.active_check = QtWidgets.QCheckBox()
        self.active_check.setChecked(True)

        form.addWidget(QtWidgets.QLabel("Game Name"), 0, 0)
        form.addWidget(self.name_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Active"), 0, 2)
        form.addWidget(self.active_check, 0, 3)
        form.addWidget(QtWidgets.QLabel("Game Type"), 1, 0)
        form.addWidget(self.type_combo, 1, 1)
        form.addWidget(QtWidgets.QLabel("RTP %"), 1, 2)
        form.addWidget(self.rtp_edit, 1, 3)
        form.addWidget(QtWidgets.QLabel("Notes"), 2, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 2, 1, 1, 3)
        layout.addLayout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._handle_save)
        self.name_edit.textChanged.connect(self._validate_inline)
        self.type_combo.currentTextChanged.connect(self._validate_inline)
        self.rtp_edit.textChanged.connect(self._validate_inline)

        if game:
            self.name_edit.setText(game["name"])
            if game["type_name"]:
                self.type_combo.setCurrentText(game["type_name"])
            if game["rtp"] is not None:
                self.rtp_edit.setText(f"{float(game['rtp']):.2f}")
            self.notes_edit.setPlainText(game["notes"] or "")
            self.active_check.setChecked(bool(game["active"]))
        else:
            self.type_combo.setCurrentIndex(-1)
            self.type_combo.setEditText("")
        self._validate_inline()

    def _validate_inline(self):
        ok = True
        if not self.name_edit.text().strip():
            self._set_invalid(self.name_edit, "Game name is required.")
            ok = False
        else:
            self._set_valid(self.name_edit)

        type_text = self.type_combo.currentText().strip()
        if not type_text or type_text.lower() not in self._type_lookup:
            self._set_invalid(self.type_combo, "Select a valid game type.")
            ok = False
        else:
            self._set_valid(self.type_combo)

        rtp_text = self.rtp_edit.text().strip()
        if rtp_text:
            try:
                rtp_val = float(rtp_text)
                if rtp_val < 0 or rtp_val > 100:
                    raise ValueError
                self._set_valid(self.rtp_edit)
            except ValueError:
                self._set_invalid(self.rtp_edit, "RTP must be between 0 and 100.")
                ok = False
        else:
            self._set_valid(self.rtp_edit)
        return ok

    def _handle_save(self):
        if self._validate_inline():
            self.accept()

    def data(self):
        type_text = self.type_combo.currentText().strip()
        return {
            "name": self.name_edit.text().strip(),
            "type_name": self._type_lookup.get(type_text.lower(), type_text),
            "rtp": float(self.rtp_edit.text().strip()) if self.rtp_edit.text().strip() else None,
            "notes": self.notes_edit.toPlainText().strip() or None,
            "active": 1 if self.active_check.isChecked() else 0,
        }


class GameViewDialog(QtWidgets.QDialog):
    def __init__(self, game, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.game = game
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Game")
        self.resize(500, 240)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)
        form.setColumnMinimumWidth(2, 60)

        # Game Name field
        game_name_label = QtWidgets.QLabel("Game Name")
        game_name_value = QtWidgets.QLabel(game["name"])
        game_name_value.setObjectName("InfoField")
        form.addWidget(game_name_label, 0, 0)
        form.addWidget(game_name_value, 0, 1)

        # Active checkbox
        active_label = QtWidgets.QLabel("Active")
        active_check = QtWidgets.QCheckBox()
        active_check.setChecked(bool(game["active"]))
        active_check.setEnabled(False)
        form.addWidget(active_label, 0, 2)
        form.addWidget(active_check, 0, 3)

        # Game Type field
        game_type_label = QtWidgets.QLabel("Game Type")
        game_type_value = QtWidgets.QLabel(game["type_name"] or "—")
        game_type_value.setObjectName("InfoField")
        game_type_value.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        form.addWidget(game_type_label, 1, 0)
        form.addWidget(game_type_value, 1, 1)

        # Expected RTP % field
        exp_rtp_label = QtWidgets.QLabel("Expected RTP %")
        exp_rtp_value = QtWidgets.QLabel(f"{float(game['rtp']):.2f}" if game["rtp"] is not None else "—")
        exp_rtp_value.setObjectName("InfoField")
        exp_rtp_value.setMaximumWidth(80)
        form.addWidget(exp_rtp_label, 1, 2)
        form.addWidget(exp_rtp_value, 1, 3)

        # Actual RTP % field
        act_rtp_label = QtWidgets.QLabel("Actual RTP %")
        act_rtp_value = QtWidgets.QLabel(f"{float(game['actual_rtp']):.2f}" if game["actual_rtp"] is not None else "—")
        act_rtp_value.setObjectName("InfoField")
        act_rtp_value.setMaximumWidth(80)
        form.addWidget(act_rtp_label, 2, 2)
        form.addWidget(act_rtp_value, 2, 3)

        # Notes field
        notes_value = game["notes"] or ""
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_value else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(notes_label, 3, 0)
        if notes_value:
            notes_edit = QtWidgets.QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(QtCore.Qt.NoFocus)
            notes_edit.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 12)
            form.addWidget(notes_edit, 3, 1, 1, 3)
        else:
            notes_field = QtWidgets.QLabel("—")
            notes_field.setObjectName("InfoField")
            form.addWidget(notes_field, 3, 1, 1, 3)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        # Add Recalculate RTP button
        recalc_rtp_btn = QtWidgets.QPushButton("Recalculate RTP")
        btn_row.addWidget(recalc_rtp_btn)
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if self._on_delete:
            delete_btn.clicked.connect(self._handle_delete)
        recalc_rtp_btn.clicked.connect(self._handle_recalc_rtp)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)

    def _handle_recalc_rtp(self):
        """Handle Recalculate RTP button click"""
        try:
            # Import here to avoid circular dependency
            from business_logic import SessionManager, FIFOCalculator
            from database import Database
            
            db = Database()
            fifo = FIFOCalculator(db)
            session_mgr = SessionManager(db, fifo)
            
            game_id = self.game['id']
            if game_id:
                session_mgr.recalculate_game_rtp_full(game_id)
                
                # Reload game data from database to get updated actual_rtp
                conn = db.get_connection()
                c = conn.cursor()
                c.execute(
                    """SELECT g.id, g.name, g.rtp, g.actual_rtp, g.notes, g.active, gt.name as type_name
                       FROM games g
                       LEFT JOIN game_types gt ON gt.id = g.game_type_id
                       WHERE g.id = ?""",
                    (game_id,)
                )
                updated_game = c.fetchone()
                conn.close()
                
                if updated_game:
                    self.game = updated_game
                    # Update the actual_rtp display in the dialog
                    for i in range(self.layout().count()):
                        item = self.layout().itemAt(i)
                        if isinstance(item.layout(), QtWidgets.QGridLayout):
                            form = item.layout()
                            # Find the Actual RTP value label (row 2, column 3)
                            act_rtp_widget = form.itemAtPosition(2, 3)
                            if act_rtp_widget:
                                label = act_rtp_widget.widget()
                                if isinstance(label, QtWidgets.QLabel):
                                    label.setText(f"{float(updated_game['actual_rtp']):.2f}" if updated_game["actual_rtp"] is not None else "—")
                            break
                
                QtWidgets.QMessageBox.information(self, "Success", f"RTP recalculated for '{self.game['name']}'")
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Game ID not found.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to recalculate RTP: {str(e)}")



class SetupListTab(QtWidgets.QWidget):
    def __init__(
        self,
        db,
        columns,
        search_placeholder,
        add_label,
        view_label,
        edit_label,
        delete_label,
        record_label,
        export_name,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.columns = columns
        self.search_placeholder = search_placeholder
        self.record_label = record_label
        self.export_name = export_name
        self.numeric_cols = set()
        self.all_rows = []
        self.filtered_rows = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        actions = QtWidgets.QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QtWidgets.QPushButton(add_label)
        self.view_btn = QtWidgets.QPushButton(view_label)
        self.edit_btn = QtWidgets.QPushButton(edit_label)
        self.delete_btn = QtWidgets.QPushButton(delete_label)
        self.add_btn.setObjectName("PrimaryButton")
        self.view_btn.setVisible(False)
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.view_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(search_placeholder)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.search_clear_btn)
        search_row.addWidget(self.clear_filters_btn)
        search_row.addStretch(1)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._view_selected)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_record)
        self.view_btn.clicked.connect(self._view_selected)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.search_edit.textChanged.connect(self.apply_filters)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self._clear_search)
        self.refresh_btn.clicked.connect(self.load_data)
        self.export_btn.clicked.connect(self.export_csv)
        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                record_id = item.data(QtCore.Qt.UserRole)
                if record_id is not None:
                    ids.append(record_id)
        return ids

    def _clear_selection(self):
        self.table.clearSelection()
        self._update_action_visibility()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _update_action_visibility(self):
        selected = self.table.selectionModel().selectedRows()
        has_selection = bool(selected)
        single_selected = len(selected) == 1
        self.view_btn.setVisible(single_selected)
        self.edit_btn.setVisible(single_selected)
        self.delete_btn.setVisible(has_selection)

    def apply_filters(self):
        term = self.search_edit.text().strip().lower()
        if not term:
            rows = list(self.all_rows)
        else:
            rows = [r for r in self.all_rows if term in r["search_blob"]]
        self.filtered_rows = rows
        self.refresh_table(rows)

    def refresh_table(self, rows):
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row["display"]):
                item = QtWidgets.QTableWidgetItem(str(value))
                if c_idx in self.numeric_cols:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if c_idx == 0:
                    item.setData(QtCore.Qt.UserRole, row["id"])
                self.table.setItem(r_idx, c_idx, item)
        self._update_action_visibility()

    def _view_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", f"Select a {self.record_label} to view."
            )
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self, "Multiple Selection", f"Select one {self.record_label} to view."
            )
            return
        self.view_record(selected_ids[0])

    def _edit_selected(self, *_args):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", f"Select a {self.record_label} to edit."
            )
            return
        if len(selected_ids) > 1:
            QtWidgets.QMessageBox.warning(
                self, "Multiple Selection", f"Select one {self.record_label} to edit."
            )
            return
        self.edit_record(selected_ids[0])

    def _delete_selected(self):
        selected_ids = self._selected_ids()
        if not selected_ids:
            QtWidgets.QMessageBox.warning(
                self, "No Selection", f"Select {self.record_label}(s) to delete."
            )
            return
        self.delete_records(selected_ids)

    def _delete_record_by_id(self, record_id):
        """Delete a single record by ID (called from View dialog)"""
        # Select the row and call existing delete logic (which will show confirmation)
        self.table.clearSelection()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == record_id:
                self.table.selectRow(row)
                break
        self._delete_selected()

    def export_csv(self):
        import csv

        default_name = f"{self.export_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            for row in self.filtered_rows:
                writer.writerow(row["display"])

    def load_data(self):
        raise NotImplementedError

    def add_record(self):
        raise NotImplementedError

    def view_record(self, record_id):
        raise NotImplementedError

    def edit_record(self, record_id):
        raise NotImplementedError

    def delete_records(self, record_ids):
        raise NotImplementedError


class UsersSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "Active", "Notes"],
            "Search users...",
            "Add User",
            "View User",
            "Edit User",
            "Delete User",
            "user",
            "users",
            parent=parent,
        )
        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, notes, active FROM users ORDER BY name")
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            notes_display = notes[:120]
            display = [row["name"], "Yes" if row["active"] else "No", notes_display]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

    def _fetch_user(self, user_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, notes, active FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row

    def add_record(self):
        dialog = UserEditDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (name, notes, active) VALUES (?, ?, ?)",
                (data["name"], data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def view_record(self, record_id):
        user = self._fetch_user(record_id)
        if not user:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected user was not found.")
            return

        dialog = UserViewDialog(user, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()

    def edit_record(self, record_id):
        user = self._fetch_user(record_id)
        if not user:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected user was not found.")
            return
        dialog = UserEditDialog(user, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "UPDATE users SET name = ?, notes = ?, active = ? WHERE id = ?",
                (data["name"], data["notes"], data["active"], record_id),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def _dependency_summary(self, cursor, user_id):
        checks = [
            ("purchases", "SELECT COUNT(*) as cnt FROM purchases WHERE user_id = ?"),
            ("redemptions", "SELECT COUNT(*) as cnt FROM redemptions WHERE user_id = ?"),
            ("game sessions", "SELECT COUNT(*) as cnt FROM game_sessions WHERE user_id = ?"),
            ("expenses", "SELECT COUNT(*) as cnt FROM expenses WHERE user_id = ?"),
            ("cards", "SELECT COUNT(*) as cnt FROM cards WHERE user_id = ?"),
            ("methods", "SELECT COUNT(*) as cnt FROM redemption_methods WHERE user_id = ?"),
            ("realized transactions", "SELECT COUNT(*) as cnt FROM realized_transactions WHERE user_id = ?"),
            ("daily sessions", "SELECT COUNT(*) as cnt FROM daily_tax_sessions WHERE user_id = ?"),
            ("site sessions", "SELECT COUNT(*) as cnt FROM site_sessions WHERE user_id = ?"),
            ("other income", "SELECT COUNT(*) as cnt FROM other_income WHERE user_id = ?"),
        ]
        details = []
        for label, query in checks:
            cursor.execute(query, (user_id,))
            count = cursor.fetchone()["cnt"]
            if count:
                details.append(f"{label}: {count}")
        return details

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} user(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = []
        for user_id in record_ids:
            deps = self._dependency_summary(c, user_id)
            if deps:
                blocked.append(deps)
                continue
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            details = "\n".join(", ".join(dep for dep in deps) for deps in blocked)
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Some users have related records. Mark them inactive instead.\n\n" + details,
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} user(s)."
            )


class SitesSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "SC Rate", "Active", "Notes"],
            "Search sites...",
            "Add Site",
            "View Site",
            "Edit Site",
            "Delete Site",
            "site",
            "sites",
            parent=parent,
        )
        self.numeric_cols = {1}
        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, sc_rate, notes, active FROM sites ORDER BY name")
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            notes_display = notes[:120]
            display = [
                row["name"],
                f"{float(row['sc_rate'] or 1.0):.4f}",
                "Yes" if row["active"] else "No",
                notes_display,
            ]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

    def _fetch_site(self, site_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id, name, sc_rate, notes, active FROM sites WHERE id = ?",
            (site_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def add_record(self):
        dialog = SiteEditDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO sites (name, sc_rate, notes, active) VALUES (?, ?, ?, ?)",
                (data["name"], data["sc_rate"], data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def view_record(self, record_id):
        site = self._fetch_site(record_id)
        if not site:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected site was not found.")
            return
        dialog = SiteViewDialog(site, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()

    def edit_record(self, record_id):
        site = self._fetch_site(record_id)
        if not site:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected site was not found.")
            return
        dialog = SiteEditDialog(site, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "UPDATE sites SET name = ?, sc_rate = ?, notes = ?, active = ? WHERE id = ?",
                (data["name"], data["sc_rate"], data["notes"], data["active"], record_id),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def _dependency_summary(self, cursor, site_id):
        checks = [
            ("purchases", "SELECT COUNT(*) as cnt FROM purchases WHERE site_id = ?"),
            ("redemptions", "SELECT COUNT(*) as cnt FROM redemptions WHERE site_id = ?"),
            ("game sessions", "SELECT COUNT(*) as cnt FROM game_sessions WHERE site_id = ?"),
            ("realized transactions", "SELECT COUNT(*) as cnt FROM realized_transactions WHERE site_id = ?"),
            ("site sessions", "SELECT COUNT(*) as cnt FROM site_sessions WHERE site_id = ?"),
        ]
        details = []
        for label, query in checks:
            cursor.execute(query, (site_id,))
            count = cursor.fetchone()["cnt"]
            if count:
                details.append(f"{label}: {count}")
        return details

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} site(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = []
        for site_id in record_ids:
            deps = self._dependency_summary(c, site_id)
            if deps:
                blocked.append(deps)
                continue
            c.execute("DELETE FROM sites WHERE id = ?", (site_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            details = "\n".join(", ".join(dep for dep in deps) for deps in blocked)
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Some sites have related records. Mark them inactive instead.\n\n" + details,
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} site(s)."
            )


class CardsSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "Last 4", "Cashback %", "User", "Active", "Notes"],
            "Search cards...",
            "Add Card",
            "View Card",
            "Edit Card",
            "Delete Card",
            "card",
            "cards",
            parent=parent,
        )
        self.numeric_cols = {1}
        self.load_data()

    def _fetch_users(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users ORDER BY name")
        users = [row["name"] for row in c.fetchall()]
        conn.close()
        return users

    def _fetch_card(self, card_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT cards.id, cards.name, cards.last_four, cards.cashback_rate, cards.active, cards.notes,
                   users.name as user_name
            FROM cards
            LEFT JOIN users ON users.id = cards.user_id
            WHERE cards.id = ?
            """,
            (card_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT cards.id, cards.name, cards.last_four, cards.cashback_rate, cards.active, cards.notes,
                   users.name as user_name
            FROM cards
            LEFT JOIN users ON users.id = cards.user_id
            ORDER BY cards.name
            """
        )
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            notes_display = notes[:120]
            display = [
                row["name"],
                row["last_four"] or "",
                f"{float(row['cashback_rate'] or 0):.2f}",
                row["user_name"] or "",
                "Yes" if row["active"] else "No",
                notes_display,
            ]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

        # Set custom column widths - make Name column 2x wider
        header = self.table.horizontalHeader()
        header.resizeSection(0, 200)  # Name column
        header.resizeSection(1, 80)   # Last 4
        header.resizeSection(2, 100)  # Cashback %
        header.resizeSection(3, 120)  # User
        header.resizeSection(4, 80)   # Active

    def add_record(self):
        dialog = CardEditDialog(self._fetch_users(), parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected user was not found.")
            return
        user_id = user_row["id"]
        try:
            c.execute(
                """
                INSERT INTO cards (name, last_four, cashback_rate, user_id, notes, active)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (data["name"], data["last_four"], data["cashback_rate"], user_id, data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def view_record(self, record_id):
        card = self._fetch_card(record_id)
        if not card:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected card was not found.")
            return
        dialog = CardViewDialog(card, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()

    def edit_record(self, record_id):
        card = self._fetch_card(record_id)
        if not card:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected card was not found.")
            return
        dialog = CardEditDialog(self._fetch_users(), card, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected user was not found.")
            return
        user_id = user_row["id"]
        try:
            c.execute(
                """
                UPDATE cards
                SET name = ?, last_four = ?, cashback_rate = ?, user_id = ?, notes = ?, active = ?
                WHERE id = ?
                """,
                (data["name"], data["last_four"], data["cashback_rate"], user_id, data["notes"], data["active"], record_id),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} card(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = False
        for card_id in record_ids:
            c.execute("SELECT COUNT(*) as cnt FROM purchases WHERE card_id = ?", (card_id,))
            if c.fetchone()["cnt"]:
                blocked = True
                continue
            c.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Some cards are linked to purchases. Mark them inactive instead.",
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} card(s)."
            )


class MethodsSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "Method Type", "User", "Active", "Notes"],
            "Search redemption methods...",
            "Add Method",
            "View Method",
            "Edit Method",
            "Delete Method",
            "method",
            "redemption_methods",
            parent=parent,
        )
        self.load_data()

    def _fetch_users(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM users ORDER BY name")
        users = [row["name"] for row in c.fetchall()]
        conn.close()
        return users

    def _fetch_method(self, method_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT rm.id, rm.name, rm.method_type, rm.active, rm.notes, u.name as user_name
            FROM redemption_methods rm
            LEFT JOIN users u ON u.id = rm.user_id
            WHERE rm.id = ?
            """,
            (method_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT rm.id, rm.name, rm.method_type, rm.active, rm.notes, u.name as user_name
            FROM redemption_methods rm
            LEFT JOIN users u ON u.id = rm.user_id
            ORDER BY rm.name
            """
        )
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            notes_display = notes[:120]
            display = [
                row["name"],
                row["method_type"] or "",
                row["user_name"] or "",
                "Yes" if row["active"] else "No",
                notes_display,
            ]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

        # Set custom column widths
        header = self.table.horizontalHeader()
        header.resizeSection(0, 200)  # Name column
        header.resizeSection(1, 120)  # Method Type
        header.resizeSection(2, 120)  # User
        header.resizeSection(3, 80)   # Active
        header.resizeSection(4, 200)  # Notes

    def add_record(self):
        dialog = MethodEditDialog(self._fetch_users(), parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected user was not found.")
            return
        user_id = user_row["id"]
        try:
            c.execute(
                """
                INSERT INTO redemption_methods (name, method_type, user_id, notes, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data["name"], data["method_type"], user_id, data["notes"], data["active"]),
            )
            conn.commit()
            conn.close()
            self.load_data()
            QtWidgets.QMessageBox.information(self, "Success", "Method added successfully.")
        except Exception as exc:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to add method:\n{exc}")

    def view_record(self, record_id):
        method = self._fetch_method(record_id)
        if not method:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected method was not found.")
            return
        dialog = MethodViewDialog(method, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()

    def edit_record(self, record_id):
        method = self._fetch_method(record_id)
        if not method:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected method was not found.")
            return
        dialog = MethodEditDialog(self._fetch_users(), method, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (data["user_name"],))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected user was not found.")
            return
        user_id = user_row["id"]
        try:
            c.execute(
                """
                UPDATE redemption_methods
                SET name = ?, method_type = ?, user_id = ?, notes = ?, active = ?
                WHERE id = ?
                """,
                (data["name"], data["method_type"], user_id, data["notes"], data["active"], record_id),
            )
            conn.commit()
            conn.close()
            self.load_data()
            QtWidgets.QMessageBox.information(self, "Success", "Method updated successfully.")
        except Exception as exc:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to update method:\n{exc}")

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} method(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = False
        for method_id in record_ids:
            c.execute(
                "SELECT COUNT(*) as cnt FROM redemptions WHERE redemption_method_id = ?",
                (method_id,),
            )
            if c.fetchone()["cnt"]:
                blocked = True
                continue
            c.execute("DELETE FROM redemption_methods WHERE id = ?", (method_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Some methods are linked to redemptions. Mark them inactive instead.",
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} method(s)."
            )


class GameTypesSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "Active", "Notes"],
            "Search game types...",
            "Add Game Type",
            "View Game Type",
            "Edit Game Type",
            "Delete Game Type",
            "game type",
            "game_types",
            parent=parent,
        )
        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, notes, active FROM game_types ORDER BY name")
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            notes_display = notes[:120]
            display = [row["name"], "Yes" if row["active"] else "No", notes_display]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

    def _fetch_game_type(self, type_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id, name, notes, active FROM game_types WHERE id = ?",
            (type_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def add_record(self):
        dialog = GameTypeEditDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO game_types (name, notes, active) VALUES (?, ?, ?)",
                (data["name"], data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def view_record(self, record_id):
        game_type = self._fetch_game_type(record_id)
        if not game_type:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected game type was not found.")
            return
        dialog = GameTypeViewDialog(game_type, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()

    def edit_record(self, record_id):
        game_type = self._fetch_game_type(record_id)
        if not game_type:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected game type was not found.")
            return
        dialog = GameTypeEditDialog(game_type, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "UPDATE game_types SET name = ?, notes = ?, active = ? WHERE id = ?",
                (data["name"], data["notes"], data["active"], record_id),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} game type(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = False
        for type_id in record_ids:
            c.execute("SELECT COUNT(*) as cnt FROM games WHERE game_type_id = ?", (type_id,))
            if c.fetchone()["cnt"]:
                blocked = True
                continue
            c.execute("DELETE FROM game_types WHERE id = ?", (type_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Some game types are linked to games. Mark them inactive instead.",
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} game type(s)."
            )


class GamesSetupTab(SetupListTab):
    def __init__(self, db, parent=None):
        super().__init__(
            db,
            ["Name", "Game Type", "Expected RTP", "Actual RTP", "Active", "Notes"],
            "Search games...",
            "Add Game",
            "View Game",
            "Edit Game",
            "Delete Game",
            "game",
            "games",
            parent=parent,
        )
        self.numeric_cols = {2, 3}
        # Set Name column width to 300px
        self.table.setColumnWidth(0, 300)
        self.load_data()

    def _fetch_game_types(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT name FROM game_types ORDER BY name")
        types = [row["name"] for row in c.fetchall()]
        conn.close()
        return types

    def _fetch_game(self, game_id):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT g.id, g.name, g.rtp, g.actual_rtp, g.notes, g.active, gt.name as type_name
            FROM games g
            LEFT JOIN game_types gt ON gt.id = g.game_type_id
            WHERE g.id = ?
            """,
            (game_id,),
        )
        row = c.fetchone()
        conn.close()
        return row

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT g.id, g.name, g.rtp, g.actual_rtp, g.notes, g.active, gt.name as type_name
            FROM games g
            LEFT JOIN game_types gt ON gt.id = g.game_type_id
            ORDER BY g.name
            """
        )
        rows = []
        for row in c.fetchall():
            notes = (row["notes"] or "").strip()
            display = [
                row["name"],
                row["type_name"] or "",
                f"{float(row['rtp']):.2f}" if row["rtp"] is not None else "",
                f"{float(row['actual_rtp']):.2f}" if row["actual_rtp"] is not None else "",
                "Yes" if row["active"] else "No",
                notes,
            ]
            rows.append(
                {
                    "id": row["id"],
                    "display": display,
                    "search_blob": " ".join(str(v).lower() for v in display),
                }
            )
        conn.close()
        self.all_rows = rows
        self.apply_filters()

    def add_record(self):
        dialog = GameEditDialog(self._fetch_game_types(), parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM game_types WHERE name = ?", (data["type_name"],))
        type_row = c.fetchone()
        if not type_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected game type was not found.")
            return
        type_id = type_row["id"]
        try:
            c.execute(
                """
                INSERT INTO games (name, game_type_id, rtp, notes, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data["name"], type_id, data["rtp"], data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def view_record(self, record_id):
        game = self._fetch_game(record_id)
        if not game:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected game was not found.")
            return
        dialog = GameViewDialog(game, parent=self, on_edit=lambda: self.edit_record(record_id), on_delete=lambda: self._delete_record_by_id(record_id))
        dialog.exec()
        # Refresh table after dialog closes (in case RTP was recalculated)
        self.load_data()

    def edit_record(self, record_id):
        game = self._fetch_game(record_id)
        if not game:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected game was not found.")
            return
        dialog = GameEditDialog(self._fetch_game_types(), game, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        data = dialog.data()
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM game_types WHERE name = ?", (data["type_name"],))
        type_row = c.fetchone()
        if not type_row:
            conn.close()
            QtWidgets.QMessageBox.warning(self, "Invalid", "Selected game type was not found.")
            return
        type_id = type_row["id"]
        try:
            c.execute(
                """
                UPDATE games
                SET name = ?, game_type_id = ?, rtp = ?, notes = ?, active = ?
                WHERE id = ?
                """,
                (data["name"], type_id, data["rtp"], data["notes"], data["active"], record_id),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

    def delete_records(self, record_ids):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(record_ids)} game(s)?",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted = 0
        blocked = []
        for game_id in record_ids:
            c.execute("SELECT name FROM games WHERE id = ?", (game_id,))
            row = c.fetchone()
            if not row:
                continue
            game_name = row["name"]
            c.execute(
                "SELECT COUNT(*) as cnt FROM game_sessions WHERE lower(game_name) = ?",
                (game_name.lower(),),
            )
            if c.fetchone()["cnt"]:
                blocked.append(game_name)
                continue
            c.execute("DELETE FROM games WHERE id = ?", (game_id,))
            if c.rowcount:
                deleted += 1
        conn.commit()
        conn.close()

        self.load_data()
        self._clear_selection()

        if blocked:
            names = ", ".join(blocked)
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                f"Some games are linked to sessions. Mark them inactive instead.\n\n{names}",
            )
        if deleted:
            QtWidgets.QMessageBox.information(
                self, "Deleted", f"Deleted {deleted} game(s)."
            )


class ToolsSetupTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr, main_window, users_tab=None, sites_tab=None,
                 cards_tab=None, methods_tab=None, game_types_tab=None, games_tab=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.main_window = main_window

        # Store references to other setup tabs for refreshing after CSV import
        self.users_tab = users_tab
        self.sites_tab = sites_tab
        self.cards_tab = cards_tab
        self.methods_tab = methods_tab
        self.game_types_tab = game_types_tab
        self.games_tab = games_tab

        # Add scroll area to handle overflow
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QtWidgets.QWidget()
        container.setStyleSheet("QWidget#ToolsContainer { background-color: transparent; }")
        container.setObjectName("ToolsContainer")
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(20)

        # CSV Section (Collapsible)
        csv_section = QtWidgets.QWidget()
        csv_section_layout = QtWidgets.QVBoxLayout(csv_section)
        csv_section_layout.setContentsMargins(0, 0, 0, 0)
        csv_section_layout.setSpacing(10)

        # CSV Toggle Button
        self.csv_toggle_btn = QtWidgets.QPushButton("▶ CSV Import/Export")
        self.csv_toggle_btn.setCheckable(True)
        self.csv_toggle_btn.clicked.connect(self._toggle_csv_section)
        csv_section_layout.addWidget(self.csv_toggle_btn)

        # CSV Content (hidden by default)
        self.csv_content = QtWidgets.QWidget()
        csv_layout = QtWidgets.QVBoxLayout(self.csv_content)
        csv_layout.setContentsMargins(10, 10, 10, 10)
        csv_layout.setSpacing(15)
        self.csv_content.hide()

        # Upload CSV subsection
        upload_label = QtWidgets.QLabel("Upload CSV")
        upload_label.setObjectName("SectionTitle")
        csv_layout.addWidget(upload_label)

        upload_grid = QtWidgets.QGridLayout()
        upload_grid.setHorizontalSpacing(10)
        upload_grid.setVerticalSpacing(10)

        upload_buttons = [
            ("Purchases", self._upload_purchases),
            ("Sessions", self._upload_sessions),
            ("Redemptions", self._upload_redemptions),
            ("Expenses", self._upload_expenses),
            ("Users", self._upload_users),
            ("Sites", self._upload_sites),
            ("Cards", self._upload_cards),
            ("Redemption Methods", self._upload_methods),
            ("Game Types", self._upload_game_types),
            ("Games", self._upload_games),
        ]

        for idx, (label, handler) in enumerate(upload_buttons):
            btn = QtWidgets.QPushButton(f"📂 Upload {label}")
            btn.clicked.connect(handler)
            btn.setMinimumWidth(180)
            row = idx // 3
            col = idx % 3
            upload_grid.addWidget(btn, row, col)

        csv_layout.addLayout(upload_grid)

        # Download Templates subsection
        csv_layout.addSpacing(10)
        template_label = QtWidgets.QLabel("Download CSV Templates")
        template_label.setObjectName("SectionTitle")
        csv_layout.addWidget(template_label)

        template_grid = QtWidgets.QGridLayout()
        template_grid.setHorizontalSpacing(10)
        template_grid.setVerticalSpacing(10)

        template_buttons = [
            ("Purchases", self._download_template_purchases),
            ("Sessions", self._download_template_sessions),
            ("Redemptions", self._download_template_redemptions),
            ("Expenses", self._download_template_expenses),
            ("Users", self._download_template_users),
            ("Sites", self._download_template_sites),
            ("Cards", self._download_template_cards),
            ("Redemption Methods", self._download_template_methods),
            ("Game Types", self._download_template_game_types),
            ("Games", self._download_template_games),
        ]

        for idx, (label, handler) in enumerate(template_buttons):
            btn = QtWidgets.QPushButton(f"📥 {label} Template")
            btn.clicked.connect(handler)
            btn.setMinimumWidth(180)
            row = idx // 3
            col = idx % 3
            template_grid.addWidget(btn, row, col)

        csv_layout.addLayout(template_grid)

        # Download Data Backups subsection
        csv_layout.addSpacing(10)
        backup_label = QtWidgets.QLabel("Download Data as CSV")
        backup_label.setObjectName("SectionTitle")
        csv_layout.addWidget(backup_label)

        data_grid = QtWidgets.QGridLayout()
        data_grid.setHorizontalSpacing(10)
        data_grid.setVerticalSpacing(10)

        data_buttons = [
            ("Purchases", self._download_data_purchases),
            ("Sessions", self._download_data_sessions),
            ("Redemptions", self._download_data_redemptions),
            ("Expenses", self._download_data_expenses),
            ("Users", self._download_data_users),
            ("Sites", self._download_data_sites),
            ("Cards", self._download_data_cards),
            ("Redemption Methods", self._download_data_methods),
            ("Game Types", self._download_data_game_types),
            ("Games", self._download_data_games),
        ]

        for idx, (label, handler) in enumerate(data_buttons):
            btn = QtWidgets.QPushButton(f"💾 Download {label}")
            btn.clicked.connect(handler)
            btn.setMinimumWidth(180)
            row = idx // 3
            col = idx % 3
            data_grid.addWidget(btn, row, col)

        csv_layout.addLayout(data_grid)
        csv_section_layout.addWidget(self.csv_content)
        layout.addWidget(csv_section)

        # Data Recalculation Section (Collapsible)
        recalc_section = QtWidgets.QWidget()
        recalc_section_layout = QtWidgets.QVBoxLayout(recalc_section)
        recalc_section_layout.setContentsMargins(0, 0, 0, 0)
        recalc_section_layout.setSpacing(10)

        # Data Recalculation Toggle Button
        self.recalc_toggle_btn = QtWidgets.QPushButton("▶ Data Recalculation")
        self.recalc_toggle_btn.setCheckable(True)
        self.recalc_toggle_btn.clicked.connect(self._toggle_recalc_section)
        recalc_section_layout.addWidget(self.recalc_toggle_btn)

        # Data Recalculation Content (hidden by default)
        self.recalc_content = QtWidgets.QWidget()
        recalc_layout = QtWidgets.QVBoxLayout(self.recalc_content)
        recalc_layout.setContentsMargins(10, 10, 10, 10)
        recalc_layout.setSpacing(10)
        self.recalc_content.hide()

        recalc_info = QtWidgets.QLabel(
            "Recalculate session totals and FIFO cost basis. "
            "Use this after bulk imports or if you notice data inconsistencies."
        )
        recalc_info.setWordWrap(True)
        recalc_info.setObjectName("HelperText")
        recalc_layout.addWidget(recalc_info)

        # Recalculate Everything
        recalc_all_btn = QtWidgets.QPushButton("🔄 Recalculate Everything")
        recalc_all_btn.setObjectName("PrimaryButton")
        recalc_all_btn.setMaximumWidth(250)
        recalc_all_btn.clicked.connect(self._recalculate_all)
        recalc_layout.addWidget(recalc_all_btn)

        recalc_specific_label = QtWidgets.QLabel("Or recalculate specific data:")
        recalc_specific_label.setObjectName("HelperText")
        recalc_layout.addWidget(recalc_specific_label)

        # Specific recalculation buttons stacked vertically
        recalc_sessions_btn = QtWidgets.QPushButton("🎯 Recalculate Session Data")
        recalc_sessions_btn.setMaximumWidth(250)
        recalc_sessions_btn.clicked.connect(self._recalculate_sessions)
        recalc_layout.addWidget(recalc_sessions_btn)

        recalc_fifo_btn = QtWidgets.QPushButton("💰 Recalculate FIFO (Redemptions)")
        recalc_fifo_btn.setMaximumWidth(250)
        recalc_fifo_btn.clicked.connect(self._recalculate_fifo)
        recalc_layout.addWidget(recalc_fifo_btn)

        recalc_rtp_btn = QtWidgets.QPushButton("📊 Recalculate RTP")
        recalc_rtp_btn.setMaximumWidth(250)
        recalc_rtp_btn.clicked.connect(self._recalculate_rtp)
        recalc_rtp_btn.setEnabled(False)
        recalc_rtp_btn.setToolTip("RTP calculation coming soon")
        recalc_layout.addWidget(recalc_rtp_btn)

        recalc_section_layout.addWidget(self.recalc_content)
        layout.addWidget(recalc_section)

        # Database Section (Collapsible)
        db_section = QtWidgets.QWidget()
        db_section_layout = QtWidgets.QVBoxLayout(db_section)
        db_section_layout.setContentsMargins(0, 0, 0, 0)
        db_section_layout.setSpacing(10)

        # Database Tools Toggle Button
        self.db_toggle_btn = QtWidgets.QPushButton("▶ Database Tools")
        self.db_toggle_btn.setCheckable(True)
        self.db_toggle_btn.clicked.connect(self._toggle_db_section)
        db_section_layout.addWidget(self.db_toggle_btn)

        # Database Tools Content (hidden by default)
        self.db_content = QtWidgets.QWidget()
        db_layout = QtWidgets.QVBoxLayout(self.db_content)
        db_layout.setContentsMargins(10, 10, 10, 10)
        db_layout.setSpacing(10)
        self.db_content.hide()

        # Backup Settings Section
        backup_settings_label = QtWidgets.QLabel("Backup Settings")
        backup_settings_label.setObjectName("SectionTitle")
        db_layout.addWidget(backup_settings_label)

        # Row 1: Backup folder
        folder_row = QtWidgets.QHBoxLayout()
        folder_row.setSpacing(10)

        folder_label = QtWidgets.QLabel("Backup folder:")
        folder_label.setMinimumWidth(180)
        folder_row.addWidget(folder_label)

        self.backup_folder_display = QtWidgets.QLineEdit()
        self.backup_folder_display.setPlaceholderText("Not set - click to choose")
        self.backup_folder_display.setReadOnly(True)
        self.backup_folder_display.setMaximumWidth(400)
        folder_row.addWidget(self.backup_folder_display)

        folder_btn = QtWidgets.QPushButton("📁 Choose")
        folder_btn.setMaximumWidth(100)
        folder_btn.clicked.connect(self._choose_backup_folder)
        folder_row.addWidget(folder_btn)

        backup_now_btn = QtWidgets.QPushButton("💾 Backup Now")
        backup_now_btn.setObjectName("PrimaryButton")
        backup_now_btn.setMaximumWidth(150)
        backup_now_btn.clicked.connect(self._backup_database_now)
        folder_row.addWidget(backup_now_btn)

        # Last backup status inline with Backup Now button
        self.last_backup_label = QtWidgets.QLabel("Last backup: Never")
        self.last_backup_label.setObjectName("HelperText")
        folder_row.addWidget(self.last_backup_label)

        folder_row.addStretch()

        db_layout.addLayout(folder_row)

        # Row 2: Enable automatic backups
        auto_backup_row = QtWidgets.QHBoxLayout()
        auto_backup_row.setSpacing(10)

        auto_label = QtWidgets.QLabel("Enable automatic backups:")
        auto_label.setMinimumWidth(180)
        auto_backup_row.addWidget(auto_label)

        self.auto_backup_enabled_cb = QtWidgets.QCheckBox()
        self.auto_backup_enabled_cb.stateChanged.connect(self._on_auto_backup_checkbox_changed)
        auto_backup_row.addWidget(self.auto_backup_enabled_cb)

        auto_backup_row.addStretch()

        db_layout.addLayout(auto_backup_row)

        # Row 3: Check every interval (container for show/hide)
        # Use a fixed-size container that's always present in the layout
        self.interval_container = QtWidgets.QWidget()
        self.interval_container.setFixedHeight(48)
        interval_row = QtWidgets.QHBoxLayout(self.interval_container)
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(10)

        self.interval_label = QtWidgets.QLabel("Check every:")
        self.interval_label.setMinimumWidth(180)
        interval_row.addWidget(self.interval_label)

        self.backup_interval_spin = QtWidgets.QSpinBox()
        self.backup_interval_spin.setMinimum(1)
        self.backup_interval_spin.setMaximum(365)
        self.backup_interval_spin.setValue(7)
        self.backup_interval_spin.setSuffix(" days")
        self.backup_interval_spin.setMaximumWidth(120)
        self.backup_interval_spin.valueChanged.connect(self._on_auto_backup_changed)
        interval_row.addWidget(self.backup_interval_spin)

        interval_row.addSpacing(15)

        self.next_backup_label = QtWidgets.QLabel("")
        self.next_backup_label.setObjectName("HelperText")
        interval_row.addWidget(self.next_backup_label)

        interval_row.addStretch()

        db_layout.addWidget(self.interval_container)

        # Load settings
        self._load_backup_settings()

        db_layout.addSpacing(15)

        # Database Reset Section
        reset_label = QtWidgets.QLabel("Database Reset")
        reset_label.setObjectName("SectionTitle")
        db_layout.addWidget(reset_label)

        # Reset Database
        reset_db_btn = QtWidgets.QPushButton("⚠️ Reset Database")
        reset_db_btn.setMaximumWidth(200)
        reset_db_btn.setObjectName("WarningButton")
        reset_db_btn.setStyleSheet("""
            QPushButton#WarningButton {
                background-color: #d32f2f !important;
                color: white !important;
                border: 1px solid #b71c1c !important;
                font-weight: bold;
            }
            QPushButton#WarningButton:hover {
                background-color: #b71c1c !important;
            }
        """)
        reset_db_btn.clicked.connect(self._reset_database)
        db_layout.addWidget(reset_db_btn)

        reset_warning = QtWidgets.QLabel(
            "⚠️ Reset will delete ALL transaction data (Purchases, Sessions, Redemptions, Expenses). "
            "Setup data (Users, Sites, Cards, etc.) will be preserved."
        )
        reset_warning.setWordWrap(True)
        reset_warning.setMaximumWidth(500)
        reset_warning.setObjectName("HelperText")
        db_layout.addWidget(reset_warning)

        db_section_layout.addWidget(self.db_content)
        layout.addWidget(db_section)
        
        # Audit Log Section (Collapsible)
        audit_section = QtWidgets.QWidget()
        audit_section_layout = QtWidgets.QVBoxLayout(audit_section)
        audit_section_layout.setContentsMargins(0, 0, 0, 0)
        audit_section_layout.setSpacing(10)

        # Audit Log Toggle Button
        self.audit_toggle_btn = QtWidgets.QPushButton("▶ Audit Log")
        self.audit_toggle_btn.setCheckable(True)
        self.audit_toggle_btn.clicked.connect(self._toggle_audit_section)
        audit_section_layout.addWidget(self.audit_toggle_btn)

        # Audit Log Content (hidden by default)
        self.audit_content = QtWidgets.QWidget()
        audit_layout = QtWidgets.QVBoxLayout(self.audit_content)
        audit_layout.setContentsMargins(10, 10, 10, 10)
        audit_layout.setSpacing(15)
        self.audit_content.hide()

        # Enable/Disable Audit Logging
        self.audit_enabled_check = QtWidgets.QCheckBox("Enable audit logging")
        self.audit_enabled_check.stateChanged.connect(self._on_audit_enabled_changed)
        audit_layout.addWidget(self.audit_enabled_check)

        audit_info = QtWidgets.QLabel(
            "Track all create, update, and delete operations across the application."
        )
        audit_info.setWordWrap(True)
        audit_info.setObjectName("HelperText")
        audit_layout.addWidget(audit_info)

        audit_layout.addSpacing(5)

        # Actions to Log
        actions_label = QtWidgets.QLabel("Actions to log:")
        actions_label.setObjectName("SectionTitle")
        audit_layout.addWidget(actions_label)

        self.audit_insert_check = QtWidgets.QCheckBox("Create (INSERT)")
        self.audit_update_check = QtWidgets.QCheckBox("Update (UPDATE)")
        self.audit_delete_check = QtWidgets.QCheckBox("Delete (DELETE)")
        self.audit_import_check = QtWidgets.QCheckBox("Import (IMPORT)")
        self.audit_system_check = QtWidgets.QCheckBox("Database Operations (REFACTOR, BACKUP, RESTORE)")

        audit_layout.addWidget(self.audit_insert_check)
        audit_layout.addWidget(self.audit_update_check)
        audit_layout.addWidget(self.audit_delete_check)
        audit_layout.addWidget(self.audit_import_check)
        audit_layout.addWidget(self.audit_system_check)

        audit_layout.addSpacing(10)

        # Retention settings
        retention_row = QtWidgets.QHBoxLayout()
        retention_row.setSpacing(10)

        retention_label = QtWidgets.QLabel("Keep logs for:")
        retention_row.addWidget(retention_label)

        self.audit_retention_spin = QtWidgets.QSpinBox()
        self.audit_retention_spin.setMinimum(1)
        self.audit_retention_spin.setMaximum(3650)  # 10 years max
        self.audit_retention_spin.setValue(365)
        self.audit_retention_spin.setSuffix(" days")
        self.audit_retention_spin.setMaximumWidth(120)
        retention_row.addWidget(self.audit_retention_spin)

        retention_row.addStretch()
        audit_layout.addLayout(retention_row)

        retention_help = QtWidgets.QLabel("Records older than this will be automatically deleted on app startup.")
        retention_help.setWordWrap(True)
        retention_help.setObjectName("HelperText")
        audit_layout.addWidget(retention_help)

        audit_layout.addSpacing(10)

        # Default user name
        user_row = QtWidgets.QHBoxLayout()
        user_row.setSpacing(10)

        user_label = QtWidgets.QLabel("Default user name:")
        user_label.setMinimumWidth(150)
        user_row.addWidget(user_label)

        self.audit_user_edit = QtWidgets.QLineEdit()
        self.audit_user_edit.setPlaceholderText("(Optional) Name to use for audit log entries")
        self.audit_user_edit.setMaximumWidth(300)
        user_row.addWidget(self.audit_user_edit)

        user_row.addStretch()
        audit_layout.addLayout(user_row)

        audit_layout.addSpacing(10)

        # Auto-backup settings
        self.audit_backup_check = QtWidgets.QCheckBox("Auto-backup audit log")
        self.audit_backup_check.stateChanged.connect(self._on_audit_backup_changed)
        audit_layout.addWidget(self.audit_backup_check)

        self.audit_backup_interval_container = QtWidgets.QWidget()
        audit_interval_row = QtWidgets.QHBoxLayout(self.audit_backup_interval_container)
        audit_interval_row.setContentsMargins(20, 0, 0, 0)
        audit_interval_row.setSpacing(10)

        audit_interval_label = QtWidgets.QLabel("Backup every:")
        audit_interval_row.addWidget(audit_interval_label)

        self.audit_backup_interval_spin = QtWidgets.QSpinBox()
        self.audit_backup_interval_spin.setMinimum(1)
        self.audit_backup_interval_spin.setMaximum(365)
        self.audit_backup_interval_spin.setValue(30)
        self.audit_backup_interval_spin.setSuffix(" days")
        self.audit_backup_interval_spin.setMaximumWidth(120)
        audit_interval_row.addWidget(self.audit_backup_interval_spin)

        self.audit_last_backup_label = QtWidgets.QLabel("")
        self.audit_last_backup_label.setObjectName("HelperText")
        audit_interval_row.addWidget(self.audit_last_backup_label)

        audit_interval_row.addStretch()
        audit_layout.addWidget(self.audit_backup_interval_container)
        self.audit_backup_interval_container.hide()

        backup_help = QtWidgets.QLabel(
            "Exports audit log to CSV in the backups/audit_logs/ folder."
        )
        backup_help.setWordWrap(True)
        backup_help.setObjectName("HelperText")
        backup_help.setContentsMargins(20, 0, 0, 0)
        audit_layout.addWidget(backup_help)

        audit_layout.addSpacing(15)

        # Action buttons - Row 1 (Primary actions)
        audit_buttons_row1 = QtWidgets.QHBoxLayout()
        audit_buttons_row1.setSpacing(10)

        save_audit_btn = QtWidgets.QPushButton("💾 Save Settings")
        save_audit_btn.setObjectName("PrimaryButton")
        save_audit_btn.setMaximumWidth(150)
        save_audit_btn.clicked.connect(self._save_audit_settings)
        audit_buttons_row1.addWidget(save_audit_btn)

        view_log_btn = QtWidgets.QPushButton("👁 View Log")
        view_log_btn.setMaximumWidth(150)
        view_log_btn.clicked.connect(self._view_audit_log)
        audit_buttons_row1.addWidget(view_log_btn)

        export_log_btn = QtWidgets.QPushButton("📤 Export Log")
        export_log_btn.setMaximumWidth(150)
        export_log_btn.clicked.connect(self._export_audit_log)
        audit_buttons_row1.addWidget(export_log_btn)

        audit_buttons_row1.addStretch()
        audit_layout.addLayout(audit_buttons_row1)

        # Action buttons - Row 2 (Destructive actions)
        audit_buttons_row2 = QtWidgets.QHBoxLayout()
        audit_buttons_row2.setSpacing(10)

        clear_log_btn = QtWidgets.QPushButton("🗑 Clear Old Records")
        clear_log_btn.setMaximumWidth(180)
        clear_log_btn.clicked.connect(self._clear_old_audit_records)
        audit_buttons_row2.addWidget(clear_log_btn)

        clear_all_log_btn = QtWidgets.QPushButton("⚠️ Clear All Logs")
        clear_all_log_btn.setMaximumWidth(150)
        clear_all_log_btn.setObjectName("WarningButton")
        clear_all_log_btn.setStyleSheet("""
            QPushButton#WarningButton {
                background-color: #d32f2f !important;
                color: white !important;
                border: 1px solid #b71c1c !important;
                font-weight: bold;
            }
            QPushButton#WarningButton:hover {
                background-color: #b71c1c !important;
            }
        """)
        clear_all_log_btn.clicked.connect(self._clear_all_audit_logs)
        audit_buttons_row2.addWidget(clear_all_log_btn)

        audit_buttons_row2.addStretch()
        audit_layout.addLayout(audit_buttons_row2)

        audit_section_layout.addWidget(self.audit_content)
        layout.addWidget(audit_section)
        
        # Load audit settings
        self._load_audit_settings()
        
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _toggle_csv_section(self):
        """Toggle CSV section visibility"""
        if self.csv_content.isVisible():
            self.csv_content.hide()
            self.csv_toggle_btn.setText("▶ CSV Import/Export")
        else:
            self.csv_content.show()
            self.csv_toggle_btn.setText("▼ CSV Import/Export")

    def _toggle_recalc_section(self):
        """Toggle Data Recalculation section visibility"""
        if self.recalc_content.isVisible():
            self.recalc_content.hide()
            self.recalc_toggle_btn.setText("▶ Data Recalculation")
        else:
            self.recalc_content.show()
            self.recalc_toggle_btn.setText("▼ Data Recalculation")

    def _toggle_db_section(self):
        """Toggle Database Tools section visibility"""
        if self.db_content.isVisible():
            self.db_content.hide()
            self.db_toggle_btn.setText("▶ Database Tools")
        else:
            self.db_content.show()
            self.db_toggle_btn.setText("▼ Database Tools")

    def _toggle_audit_section(self):
        """Toggle Audit Log section visibility"""
        if self.audit_content.isVisible():
            self.audit_content.hide()
            self.audit_toggle_btn.setText("▶ Audit Log")
        else:
            self.audit_content.show()
            self.audit_toggle_btn.setText("▼ Audit Log")

    def _on_audit_enabled_changed(self):
        """Handle audit enabled checkbox state change"""
        # Enable/disable all audit-related controls based on checkbox state
        enabled = self.audit_enabled_check.isChecked()
        self.audit_insert_check.setEnabled(enabled)
        self.audit_update_check.setEnabled(enabled)
        self.audit_delete_check.setEnabled(enabled)
        self.audit_import_check.setEnabled(enabled)
        self.audit_system_check.setEnabled(enabled)
        self.audit_retention_spin.setEnabled(enabled)
        self.audit_user_edit.setEnabled(enabled)
        self.audit_backup_check.setEnabled(enabled)
        if not enabled:
            self.audit_backup_interval_container.hide()

    def _on_audit_backup_changed(self):
        """Handle audit backup checkbox state change"""
        if self.audit_backup_check.isChecked():
            self.audit_backup_interval_container.show()
        else:
            self.audit_backup_interval_container.hide()

    # CSV Schema Helper Methods
    def _get_table_schema(self, table_name):
        """Get schema information for a table dynamically from the database.

        Returns a dict with:
        - columns: list of column names (excluding id and auto-generated fields)
        - display_names: dict mapping column names to display-friendly names
        - csv_names: dict mapping column names to CSV-friendly names (FKs resolved)
        - foreign_keys: dict mapping FK column to (ref_table, ref_column, display_name)
        - required: set of required column names
        """
        conn = self.db.get_connection()
        c = conn.cursor()

        # Get table info
        c.execute(f"PRAGMA table_info({table_name})")
        columns_info = c.fetchall()

        # Get foreign key info
        c.execute(f"PRAGMA foreign_key_list({table_name})")
        fk_info = c.fetchall()

        conn.close()

        # Build FK map: column_name -> (referenced_table, referenced_column)
        foreign_keys = {}
        for fk in fk_info:
            fk_column = fk[3]  # from column
            ref_table = fk[2]  # referenced table
            ref_column = fk[4]  # referenced column (usually 'id')
            foreign_keys[fk_column] = (ref_table, ref_column)

        # Common FK patterns when PRAGMA foreign_key_list doesn't work
        # (SQLite doesn't always have FK constraints defined)
        fk_patterns = {
            'user_id': ('users', 'id'),
            'site_id': ('sites', 'id'),
            'card_id': ('cards', 'id'),
            'method_id': ('redemption_methods', 'id'),
            'game_type_id': ('game_types', 'id'),
            'game_id': ('games', 'id'),
        }

        # Parse columns (exclude id, created_at, etc.)
        exclude_columns = {'id', 'created_at', 'updated_at', 'timestamp'}

        # Calculated/system fields that should be excluded from CSV imports
        # These are auto-generated or derived fields that users shouldn't provide
        # Organized by table for clarity and maintainability
        calculated_fields_by_table = {
            'purchases': {
                'remaining_amount',  # FIFO calculation
                'processed',  # System flag
                'status',  # System-managed status (active/dormant)
            },
            'redemptions': {
                'site_session_id',  # Auto-linked during session creation
            },
            'game_sessions': {
                'sc_change',  # Calculated: ending - starting
                'dollar_value',  # Calculated from SC values
                'status',  # System-managed (Active/Closed)
                'processed',  # System flag
                'freebies_detected',  # Auto-calculated by detect_freebies()
                'gameplay_pnl',  # Legacy/deprecated - set to NULL during recalc
                'basis_bonus',  # Legacy/deprecated - set to NULL during recalc
                'total_taxable',  # Tax calculation
                'session_basis',  # FIFO/tax calculation
                'expected_start_total_sc',  # Auto-calculated
                'expected_start_redeemable_sc',  # Auto-calculated
                'inferred_start_total_delta',  # Auto-calculated
                'inferred_start_redeemable_delta',  # Auto-calculated
                'delta_total',  # Auto-calculated
                'delta_redeem',  # Auto-calculated
                'net_taxable_pl',  # Tax calculation
                'basis_consumed',  # FIFO/tax calculation
                'rtp',  # Will be auto-calculated in future
            },
            'games': {
                'actual_rtp',  # Auto-calculated from RTP aggregates
            },
            'expenses': set(),  # No calculated fields
        }

        # Get calculated fields for this specific table
        calculated_fields = calculated_fields_by_table.get(table_name, set())

        columns = []
        required = set()

        for col_info in columns_info:
            col_name = col_info[1]  # name
            col_type = col_info[2]  # type
            not_null = col_info[3]  # notnull
            default_val = col_info[4]  # dflt_value

            # Skip excluded columns and calculated fields
            if col_name in exclude_columns or col_name in calculated_fields:
                continue

            columns.append(col_name)

            # Mark as required if NOT NULL and no default value
            if not_null and default_val is None:
                required.add(col_name)
        
        # Special case: method_type is required for redemption_methods even though DB allows NULL
        if table_name == 'redemption_methods' and 'method_type' in columns:
            required.add('method_type')

            # Auto-detect FKs by pattern if not found
            if col_name not in foreign_keys and col_name in fk_patterns:
                foreign_keys[col_name] = fk_patterns[col_name]

        # Create display names
        display_names = {}
        csv_names = {}
        fk_details = {}

        for col in columns:
            # Convert snake_case to Title Case
            display_name = ' '.join(word.capitalize() for word in col.split('_'))
            display_names[col] = display_name

            # For foreign keys, use singular form of referenced table
            if col in foreign_keys:
                ref_table, ref_column = foreign_keys[col]
                # Convert table name to singular display name
                if ref_table == 'users':
                    csv_name = 'User'
                elif ref_table == 'sites':
                    csv_name = 'Site'
                elif ref_table == 'cards':
                    csv_name = 'Card'
                elif ref_table == 'redemption_methods':
                    csv_name = 'Method'
                elif ref_table == 'game_types':
                    csv_name = 'Game Type'
                elif ref_table == 'games':
                    csv_name = 'Game'
                else:
                    # Fallback: remove trailing 's' and capitalize
                    csv_name = ref_table.rstrip('s').replace('_', ' ').title()

                csv_names[col] = csv_name
                fk_details[col] = (ref_table, ref_column, csv_name)
            else:
                csv_names[col] = display_name

        return {
            'columns': columns,
            'display_names': display_names,
            'csv_names': csv_names,
            'foreign_keys': fk_details,
            'required': required
        }

    def _get_csv_headers(self, table_name):
        """Get CSV headers for a table (display-friendly names with FKs resolved)"""
        schema = self._get_table_schema(table_name)
        return [schema['csv_names'][col] for col in schema['columns']]

    def _get_csv_column_mapping(self, table_name):
        """Get mapping from CSV names to database column names"""
        schema = self._get_table_schema(table_name)
        return {schema['csv_names'][col]: col for col in schema['columns']}

    def _build_select_query(self, table_name):
        """Build a SELECT query that resolves all foreign keys to names.

        Returns: (query_string, headers)
        """
        schema = self._get_table_schema(table_name)

        select_parts = []
        joins = []

        # Check which referenced tables have a 'name' column
        tables_with_name = set()
        conn = self.db.get_connection()
        c = conn.cursor()

        for col, (ref_table, ref_column, csv_name) in schema['foreign_keys'].items():
            c.execute(f"PRAGMA table_info({ref_table})")
            ref_columns = [row[1] for row in c.fetchall()]
            if 'name' in ref_columns:
                tables_with_name.add(col)

        conn.close()

        for col in schema['columns']:
            if col in schema['foreign_keys']:
                ref_table, ref_column, csv_name = schema['foreign_keys'][col]
                # Create unique alias based on the column name (e.g., site_id -> site_id_ref)
                alias = f"{col}_ref"

                if col in tables_with_name:
                    # Reference table has a name column - resolve it
                    joins.append(f"LEFT JOIN {ref_table} {alias} ON {table_name}.{col} = {alias}.{ref_column}")
                    select_parts.append(f"{alias}.name")
                else:
                    # Reference table doesn't have a name column - just use the ID
                    select_parts.append(f"{table_name}.{col}")
            else:
                # Select from main table
                select_parts.append(f"{table_name}.{col}")

        # Build query
        select_clause = ", ".join(select_parts)
        join_clause = " ".join(joins)
        query = f"SELECT {select_clause} FROM {table_name} {join_clause}"

        # Get headers
        headers = self._get_csv_headers(table_name)

        return query, headers

    def _apply_import_defaults(self, table_name, record):
        """Apply default values for calculated/system fields during import.

        This ensures that auto-calculated fields are properly initialized
        when importing records that don't include these fields.

        Args:
            table_name: Name of the table being imported to
            record: Dictionary of field values (modified in place)
        """
        if table_name == 'purchases':
            # Initialize remaining_amount to full purchase amount (before FIFO allocations)
            if 'remaining_amount' not in record and 'amount' in record:
                record['remaining_amount'] = record['amount']
            # Mark as processed
            if 'processed' not in record:
                record['processed'] = 1
            # Set as active (not dormant)
            if 'status' not in record:
                record['status'] = 'active'

        elif table_name == 'redemptions':
            # Mark as unprocessed initially (will be processed during recalculation)
            if 'processed' not in record:
                record['processed'] = 0
            # Site session will be auto-linked later if needed
            if 'site_session_id' not in record:
                record['site_session_id'] = None

        elif table_name == 'game_sessions':
            # Default start_time to 00:00:00 if blank
            if 'start_time' not in record or not record.get('start_time'):
                record['start_time'] = '00:00:00'
            # game_type is nullable - don't set a default
            # Calculate SC change if both balances provided
            if 'sc_change' not in record:
                if 'ending_sc_balance' in record and 'starting_sc_balance' in record:
                    if record['ending_sc_balance'] is not None and record['starting_sc_balance'] is not None:
                        record['sc_change'] = record['ending_sc_balance'] - record['starting_sc_balance']
            # Set status based on whether session has end date/time
            if 'status' not in record:
                # If session has end_date or end_time, it's closed
                has_end_date = record.get('end_date') is not None
                has_end_time = record.get('end_time') is not None and record.get('end_time') != ''
                if has_end_date or has_end_time:
                    record['status'] = 'Closed'
                else:
                    record['status'] = 'Active'
            # Mark as processed
            if 'processed' not in record:
                record['processed'] = 1
            # Other calculated fields will be filled during "Recalculate Everything"

        # Expenses have no calculated fields to initialize

    def _upload_table_dynamic(self, table_name, unique_column, refresh_tab=None):
        """Universal CSV upload using fully dynamic schema with automatic FK detection and validation.

        Args:
            table_name: Database table name
            unique_column: Column name or tuple of column names that uniquely identify records
            refresh_tab: Optional tab widget to refresh after import

        IMPORTANT: No database modifications occur until the user confirms the final import dialog.
        """
        import csv

        # Normalize unique_column to tuple for consistent handling
        if isinstance(unique_column, str):
            unique_columns = (unique_column,)
        else:
            unique_columns = tuple(unique_column)

        # Get schema with FK info
        schema = self._get_table_schema(table_name)

        # File selection
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Select {table_name.replace('_', ' ').title()} CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return False

        # Ask if user wants to clear existing data (just captures preference, no DB changes yet)
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing_count = c.fetchone()[0]
        conn.close()

        if existing_count > 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Clear Existing Data?",
                f"There are {existing_count} existing records.\n\n"
                f"Do you want to clear all existing {table_name.replace('_', ' ')} before importing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            clear_existing = (reply == QtWidgets.QMessageBox.Yes)
        else:
            clear_existing = False

        # Read and validate CSV
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                csv_headers = reader.fieldnames

                # Validate required headers
                missing_required = []
                for col in schema['columns']:
                    csv_name = schema['csv_names'][col]
                    if col in schema['required'] and csv_name not in csv_headers:
                        missing_required.append(csv_name)

                if missing_required:
                    QtWidgets.QMessageBox.warning(
                        self, "Invalid CSV",
                        f"CSV is missing required columns:\n" + "\n".join(f"  - {col}" for col in missing_required)
                    )
                    return False

                # Read all rows
                rows = list(reader)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Error Reading CSV",
                f"Failed to read CSV file:\n{exc}"
            )
            return False

        if not rows:
            QtWidgets.QMessageBox.information(self, "Empty CSV", "The CSV file contains no data rows.")
            return False

        # Get existing records and build FK lookup tables
        conn = self.db.get_connection()
        c = conn.cursor()

        # Build FK lookup maps
        fk_lookups = {}
        for col, (ref_table, ref_column, csv_name) in schema['foreign_keys'].items():
            c.execute(f"SELECT id, name FROM {ref_table}")
            fk_lookups[col] = {row[1].lower(): row[0] for row in c.fetchall()}

        # Get existing records (only if not clearing - no need to check duplicates if we're wiping everything)
        existing_records = {}
        if not clear_existing:
            cols = ', '.join(schema['columns'])
            c.execute(f"SELECT {cols} FROM {table_name}")

            for row in c.fetchall():
                record = {schema['columns'][i]: row[i] for i in range(len(row))}
                # Build composite key from unique columns
                key_parts = []
                for col in unique_columns:
                    val = record.get(col)
                    if val is None:
                        key_parts.append('__NULL__')
                    else:
                        key_parts.append(str(val).lower())
                key = '|||'.join(key_parts)
                existing_records[key] = record

        conn.close()

        # Parse and validate CSV rows
        to_add = []
        exact_duplicates = []
        conflicts = []
        invalid_rows = []
        csv_duplicates = []
        seen_in_csv = {}  # Track what we've seen in this CSV to detect within-file duplicates

        for row_idx, csv_row in enumerate(rows, start=2):
            record = {}
            unique_vals = {}
            errors = []

            for col in schema['columns']:
                csv_name = schema['csv_names'][col]
                csv_value = csv_row.get(csv_name, '').strip()

                # Handle foreign keys
                if col in schema['foreign_keys']:
                    ref_table, ref_column, fk_display_name = schema['foreign_keys'][col]
                    if csv_value:
                        fk_id = fk_lookups[col].get(csv_value.lower())
                        if fk_id is None:
                            errors.append(f"{fk_display_name} '{csv_value}' not found")
                            record[col] = None
                        else:
                            record[col] = fk_id
                    else:
                        record[col] = None
                # Handle boolean/integer columns (processed, active, is_active, is_free_sc, more_remaining, etc.)
                elif col in ('active', 'is_active', 'processed', 'is_free_sc', 'more_remaining'):
                    if csv_value:
                        record[col] = 1 if csv_value.lower() in ('1', 'true', 'yes', 'active') else 0
                    else:
                        record[col] = 0
                # Handle date columns
                elif col in ('purchase_date', 'redemption_date', 'session_date', 'expense_date',
                            'receipt_date', 'end_date'):
                    if csv_value:
                        try:
                            # Handle formatted dates like "12/02/25 00:00" or just "12/02/25"
                            date_part = csv_value.split()[0] if ' ' in csv_value else csv_value
                            parsed_date = parse_date_input(date_part)
                            record[col] = parsed_date.strftime('%Y-%m-%d')
                        except (ValueError, AttributeError):
                            errors.append(f"Invalid date for {csv_name}: '{csv_value}'")
                            record[col] = None
                    else:
                        record[col] = None
                # Handle time columns
                elif col in ('purchase_time', 'redemption_time', 'start_time', 'end_time'):
                    if csv_value:
                        try:
                            # Handle formatted datetime like "12/02/25 00:00" - extract time
                            if ' ' in csv_value:
                                time_part = csv_value.split(' ', 1)[1] if ' ' in csv_value else csv_value
                            else:
                                time_part = csv_value
                            parsed_time = parse_time_input(time_part)
                            record[col] = parsed_time
                        except (ValueError, AttributeError):
                            # If parsing fails, keep as text
                            record[col] = csv_value
                    else:
                        record[col] = None
                # Handle numeric columns (detect by type checking common patterns)
                elif col in ('rtp', 'cashback_rate', 'sc_rate', 'amount', 'fees', 'sc_received',
                            'starting_sc_balance', 'starting_sc_balance', 'starting_redeemable_sc',
                            'ending_sc_balance', 'ending_redeemable_sc', 'wager_amount',
                            'cashback_earned', 'remaining_amount', 'dollar_value', 'freebies_detected',
                            'sc_change', 'basis_bonus', 'gameplay_pnl', 'total_taxable', 'net_taxable_pl',
                            'basis_consumed', 'session_basis'):
                    if csv_value:
                        try:
                            # Strip currency formatting ($, commas) before parsing
                            clean_value = csv_value.replace('$', '').replace(',', '').strip()
                            record[col] = float(clean_value)
                        except ValueError:
                            errors.append(f"Invalid number for {csv_name}: '{csv_value}'")
                            record[col] = None
                    else:
                        record[col] = None
                # Handle text columns
                elif csv_value:
                    record[col] = csv_value
                else:
                    record[col] = None

                # Track values for unique columns
                if col in unique_columns:
                    unique_vals[col] = csv_value if csv_value else None

            # Apply defaults for optional fields that have standard defaults
            # This must happen before validation so defaults count as "present"
            if table_name == 'game_sessions':
                if 'start_time' not in record or not record.get('start_time'):
                    record['start_time'] = '00:00:00'
                    if 'start_time' in unique_columns:
                        unique_vals['start_time'] = '00:00:00'

            # Check if all unique columns are present
            missing_cols = [schema['csv_names'][col] for col in unique_columns if col not in record or not unique_vals.get(col)]
            if missing_cols:
                errors.append(f"Missing required: {', '.join(missing_cols)}")

            # Business logic validations
            from datetime import datetime, timedelta
            today = datetime.now().date()

            # Redemptions validations
            if table_name == 'redemptions':
                if record.get('receipt_date') and record.get('redemption_date'):
                    if record['receipt_date'] < record['redemption_date']:
                        errors.append(f"Receipt date ({record['receipt_date']}) cannot be before redemption date ({record['redemption_date']})")
                if record.get('redemption_date'):
                    try:
                        redemption_date = datetime.strptime(record['redemption_date'], '%Y-%m-%d').date()
                        if redemption_date > today:
                            errors.append(f"Redemption date ({record['redemption_date']}) cannot be in the future")
                    except:
                        pass
                # Fees validation: optional, non-negative, and cannot exceed amount
                if record.get('fees') is not None:
                    if record['fees'] < 0:
                        errors.append(f"Fees cannot be negative ({record['fees']})")
                    if record.get('amount') is not None and record['fees'] > record['amount']:
                        errors.append(f"Fees ({record['fees']}) cannot exceed the redemption amount ({record['amount']})")

            # Game sessions validations
            elif table_name == 'game_sessions':
                session_date = record.get('session_date')
                start_time = record.get('start_time', '00:00:00')
                end_date = record.get('end_date')
                end_time = record.get('end_time')

                # Check session date not in future
                if session_date:
                    try:
                        sess_date = datetime.strptime(session_date, '%Y-%m-%d').date()
                        if sess_date > today:
                            errors.append(f"Session date ({session_date}) cannot be in the future")
                    except:
                        pass

                # Check end date/time validations
                if end_date and end_time and session_date and start_time:
                    try:
                        start_dt = datetime.strptime(f"{session_date} {start_time}", '%Y-%m-%d %H:%M:%S')
                        end_dt = datetime.strptime(f"{end_date} {end_time}", '%Y-%m-%d %H:%M:%S')

                        if end_dt < start_dt:
                            errors.append(f"Session cannot end ({end_date} {end_time}) before it starts ({session_date} {start_time})")
                        elif end_dt == start_dt:
                            errors.append(f"Session cannot end at the same time it starts (must be at least 1 second)")
                    except:
                        pass

                # Validate SC balances are non-negative
                if record.get('starting_sc_balance') is not None and record['starting_sc_balance'] < 0:
                    errors.append(f"Starting SC balance cannot be negative ({record['starting_sc_balance']})")
                if record.get('ending_sc_balance') is not None and record['ending_sc_balance'] < 0:
                    errors.append(f"Ending SC balance cannot be negative ({record['ending_sc_balance']})")

            # Purchases validations
            elif table_name == 'purchases':
                if record.get('purchase_date'):
                    try:
                        purchase_date = datetime.strptime(record['purchase_date'], '%Y-%m-%d').date()
                        if purchase_date > today:
                            errors.append(f"Purchase date ({record['purchase_date']}) cannot be in the future")
                    except:
                        pass
                if record.get('amount') is not None and record['amount'] <= 0:
                    errors.append(f"Purchase amount must be greater than 0 ({record['amount']})")
                if record.get('sc_received') is not None and record['sc_received'] <= 0:
                    errors.append(f"SC received must be greater than 0 ({record['sc_received']})")

            # Expenses validations
            elif table_name == 'expenses':
                if record.get('expense_date'):
                    try:
                        expense_date = datetime.strptime(record['expense_date'], '%Y-%m-%d').date()
                        if expense_date > today:
                            errors.append(f"Expense date ({record['expense_date']}) cannot be in the future")
                    except:
                        pass
                if record.get('amount') is not None and record['amount'] <= 0:
                    errors.append(f"Expense amount must be greater than 0 ({record['amount']})")

            # Check all required fields are present and not empty
            for col in schema['required']:
                if col not in record or record[col] is None or (isinstance(record[col], str) and not record[col].strip()):
                    csv_name = schema['csv_names'][col]
                    errors.append(f"Required field '{csv_name}' is missing or empty")

            # If there are validation errors, mark as invalid
            if errors:
                # Use first unique column value for display name
                display_name = unique_vals.get(unique_columns[0], '(unnamed)')
                invalid_rows.append({
                    'row': row_idx,
                    'name': display_name,
                    'errors': errors
                })
                continue

            # Build composite key
            key_parts = []
            for col in unique_columns:
                val = record.get(col)
                if val is None:
                    key_parts.append('__NULL__')
                else:
                    key_parts.append(str(val).lower())
            key = '|||'.join(key_parts)

            # Build display name for this record (use first unique column)
            display_name = unique_vals.get(unique_columns[0], '(unnamed)')

            # Check if we've already seen this key in the CSV file
            if key in seen_in_csv:
                csv_duplicates.append({
                    'row': row_idx,
                    'name': display_name,
                    'first_row': seen_in_csv[key]
                })
                continue

            # Check if record exists in database
            if key in existing_records:
                existing = existing_records[key]
                # Only compare columns that are present in the CSV (non-None in record)
                # This allows CSV to have subset of columns without triggering conflicts
                is_exact = True
                for col in schema['columns']:
                    if record.get(col) is None:
                        continue  # Skip columns not in CSV

                    csv_val = record.get(col)
                    db_val = existing.get(col)

                    # Normalize empty strings and None for text fields
                    if isinstance(csv_val, str) and not csv_val:
                        csv_val = None
                    if isinstance(db_val, str) and not db_val:
                        db_val = None

                    # For numeric columns, compare with tolerance for floating point precision
                    if isinstance(csv_val, (int, float)) and isinstance(db_val, (int, float)):
                        if abs(csv_val - db_val) > 0.01:  # Allow 1 cent difference
                            is_exact = False
                            break
                    # For other types, exact comparison
                    elif csv_val != db_val:
                        is_exact = False
                        break

                if is_exact:
                    exact_duplicates.append(display_name)
                else:
                    conflicts.append(record)
            else:
                to_add.append(record)

            # Mark this key as seen in the CSV
            seen_in_csv[key] = row_idx

        # Report CSV duplicates and invalid rows
        total_errors = len(invalid_rows) + len(csv_duplicates)
        if total_errors > 0:
            error_parts = []

            if csv_duplicates:
                csv_dup_summary = "\n".join([
                    f"Row {d['row']}: {d['name']} (duplicate of row {d['first_row']})"
                    for d in csv_duplicates[:5]
                ])
                if len(csv_duplicates) > 5:
                    csv_dup_summary += f"\n... and {len(csv_duplicates) - 5} more CSV duplicates"
                error_parts.append(f"Duplicate entries within CSV ({len(csv_duplicates)}):\n{csv_dup_summary}")

            if invalid_rows:
                invalid_summary = "\n".join([
                    f"Row {r['row']}: {r['name']} - {', '.join(r['errors'])}"
                    for r in invalid_rows[:5]
                ])
                if len(invalid_rows) > 5:
                    invalid_summary += f"\n... and {len(invalid_rows) - 5} more validation errors"
                error_parts.append(f"Validation errors ({len(invalid_rows)}):\n{invalid_summary}")

            error_message = "\n\n".join(error_parts)

            reply = QtWidgets.QMessageBox.question(
                self,
                "CSV Errors Found",
                f"Found {total_errors} problematic rows:\n\n{error_message}\n\n"
                f"Skip these rows and import {len(to_add) + len(conflicts)} valid rows?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return False

        # Report findings
        if not to_add and not conflicts:
            QtWidgets.QMessageBox.information(
                self, "No Changes",
                f"All valid records in the CSV already exist in the database.\n\n"
                f"Exact duplicates skipped: {len(exact_duplicates)}\n"
                f"CSV duplicates skipped: {len(csv_duplicates)}\n"
                f"Invalid rows skipped: {len(invalid_rows)}"
            )
            return False

        # Handle conflicts
        update_conflicts = False
        if conflicts:
            conflict_list = "\n".join([f"  - {rec[unique_columns[0]]}" for rec in conflicts[:10]])
            if len(conflicts) > 10:
                conflict_list += f"\n  ... and {len(conflicts) - 10} more"


            # Build display text for unique columns
            unique_col_display = ' + '.join([schema['csv_names'][col] for col in unique_columns])
            reply = QtWidgets.QMessageBox.question(
                self,
                "Handle Conflicts?",
                f"Found {len(conflicts)} records with same {unique_col_display} but different data:\n\n"
                f"{conflict_list}\n\n"
                "Do you want to UPDATE these records with the CSV values?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            update_conflicts = (reply == QtWidgets.QMessageBox.Yes)

        # Close the connection used for reading - no database changes should happen until final confirmation
        conn.close()

        # Final confirmation
        summary_parts = []
        if clear_existing:
            summary_parts.append(f"Clear {existing_count} existing records")
        if to_add:
            summary_parts.append(f"Add {len(to_add)} new records")
        if conflicts and update_conflicts:
            summary_parts.append(f"Update {len(conflicts)} conflicting records")
        elif conflicts:
            summary_parts.append(f"Skip {len(conflicts)} conflicting records")
        if exact_duplicates:
            summary_parts.append(f"Skip {len(exact_duplicates)} exact duplicates")
        if csv_duplicates:
            summary_parts.append(f"Skip {len(csv_duplicates)} CSV duplicates")
        if invalid_rows:
            summary_parts.append(f"Skip {len(invalid_rows)} invalid rows")

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Import",
            f"Ready to import {table_name.replace('_', ' ')}:\n\n" +
            "\n".join(f"  • {part}" for part in summary_parts) + "\n\n"
            "Proceed with import?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return False

        # Perform import
        try:
            conn = self.db.get_connection()
            c = conn.cursor()

            # Clear existing if requested
            if clear_existing:
                c.execute(f"DELETE FROM {table_name}")

            # Add new records
            added = 0
            for record in to_add:
                # Add default values for calculated/system fields based on table
                self._apply_import_defaults(table_name, record)

                cols = ', '.join(record.keys())
                placeholders = ', '.join(['?'] * len(record))
                values = tuple(record.values())
                c.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
                added += 1

            # Update conflicts if requested
            updated = 0
            if update_conflicts:
                for record in conflicts:
                    # Add default values for calculated/system fields based on table
                    self._apply_import_defaults(table_name, record)

                    # Build SET clause (exclude unique columns from update)
                    set_cols = [f"{col} = ?" for col in record.keys() if col not in unique_columns]
                    set_clause = ', '.join(set_cols)
                    values = [record[col] for col in record.keys() if col not in unique_columns]

                    # Build WHERE clause for composite unique columns
                    where_parts = []
                    for col in unique_columns:
                        val = record[col]
                        if val is None:
                            where_parts.append(f"{col} IS NULL")
                        else:
                            where_parts.append(f"LOWER({col}) = ?")
                            values.append(str(val).lower())
                    where_clause = ' AND '.join(where_parts)

                    c.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}",
                        values
                    )
                    updated += 1

            conn.commit()

            # Log audit
            details = f"Imported from CSV: {added} added"
            if updated:
                details += f", {updated} updated"
            if exact_duplicates:
                details += f", {len(exact_duplicates)} skipped (duplicates)"
            if invalid_rows:
                details += f", {len(invalid_rows)} skipped (invalid)"
            self.db.log_audit("IMPORT", table_name, details=details)

            conn.close()

            # Refresh UI
            if refresh_tab and hasattr(refresh_tab, 'load_data'):
                refresh_tab.load_data()

            # Show success
            QtWidgets.QMessageBox.information(
                self, "Import Complete",
                f"{table_name.replace('_', ' ').title()} imported successfully!\n\n"
                f"Added: {added}\n"
                f"Updated: {updated}\n"
                f"Skipped: {len(exact_duplicates) + len(csv_duplicates) + len(invalid_rows) + (len(conflicts) if not update_conflicts else 0)}"
            )
            return True

        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Import Failed",
                f"Failed to import {table_name}:\n{exc}"
            )
            return False

    def _upload_simple_table(self, table_name, unique_column, refresh_tab=None):
        """Generic CSV upload for simple tables (no foreign keys to resolve).

        Args:
            table_name: Database table name
            unique_column: Column name that uniquely identifies records (e.g., 'name')
            refresh_tab: Optional tab widget to refresh after import
        """
        import csv

        # Get schema
        schema = self._get_table_schema(table_name)
        column_mapping = self._get_csv_column_mapping(table_name)

        # File selection
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Select {table_name.replace('_', ' ').title()} CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return False

        # Ask if user wants to clear existing data
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing_count = c.fetchone()[0]
        conn.close()

        if existing_count > 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Clear Existing Data?",
                f"There are {existing_count} existing records.\n\n"
                f"Do you want to clear all existing {table_name.replace('_', ' ')} before importing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            clear_existing = (reply == QtWidgets.QMessageBox.Yes)
        else:
            clear_existing = False

        # Read and validate CSV
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                csv_headers = reader.fieldnames

                # Validate required headers
                missing_required = []
                for col in schema['columns']:
                    display_name = schema['display_names'][col]
                    if col in schema['required'] and display_name not in csv_headers:
                        missing_required.append(display_name)

                if missing_required:
                    QtWidgets.QMessageBox.warning(
                        self, "Invalid CSV",
                        f"CSV is missing required columns:\n" + "\n".join(f"  - {col}" for col in missing_required)
                    )
                    return False

                # Read all rows
                rows = list(reader)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Error Reading CSV",
                f"Failed to read CSV file:\n{exc}"
            )
            return False

        if not rows:
            QtWidgets.QMessageBox.information(self, "Empty CSV", "The CSV file contains no data rows.")
            return False

        # Get existing records for duplicate detection
        conn = self.db.get_connection()
        c = conn.cursor()

        # Build SELECT for all columns
        cols = ', '.join(schema['columns'])
        c.execute(f"SELECT {cols} FROM {table_name}")
        existing_records = {}

        for row in c.fetchall():
            # Create dict from row
            record = {schema['columns'][i]: row[i] for i in range(len(row))}
            # Use unique column as key (case-insensitive)
            key = str(record[unique_column]).lower() if record[unique_column] else None
            if key:
                existing_records[key] = record

        conn.close()

        # Analyze duplicates and conflicts
        to_add = []
        exact_duplicates = []
        conflicts = []

        for csv_row in rows:
            # Parse CSV row into database columns
            record = {}
            unique_val = None

            for col in schema['columns']:
                display_name = schema['display_names'][col]
                csv_value = csv_row.get(display_name, '').strip()

                # Parse value based on column name patterns
                if col in ('active', 'is_active'):
                    # Boolean/integer columns
                    record[col] = 1 if csv_value.lower() in ('1', 'true', 'yes', 'active') else 0
                elif csv_value:
                    record[col] = csv_value
                else:
                    record[col] = None

                if col == unique_column:
                    unique_val = csv_value

            if not unique_val:
                continue

            key = unique_val.lower()

            # Check if record exists
            if key in existing_records:
                existing = existing_records[key]
                # Check for exact duplicate (all columns match)
                is_exact = all(record.get(col) == existing.get(col) for col in schema['columns'])

                if is_exact:
                    exact_duplicates.append(unique_val)
                else:
                    conflicts.append(record)
            else:
                to_add.append(record)

        # Report findings
        if not to_add and not conflicts:
            QtWidgets.QMessageBox.information(
                self, "No Changes",
                f"All records in the CSV already exist in the database.\n\n"
                f"Exact duplicates skipped: {len(exact_duplicates)}"
            )
            return

        # Handle conflicts
        update_conflicts = False
        if conflicts:
            conflict_list = "\n".join([f"  - {rec[unique_column]}" for rec in conflicts[:10]])
            if len(conflicts) > 10:
                conflict_list += f"\n  ... and {len(conflicts) - 10} more"

            reply = QtWidgets.QMessageBox.question(
                self,
                "Handle Conflicts?",
                f"Found {len(conflicts)} records with same {unique_column} but different data:\n\n"
                f"{conflict_list}\n\n"
                "Do you want to UPDATE these records with the CSV values?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            update_conflicts = (reply == QtWidgets.QMessageBox.Yes)

        # Close the connection used for reading - no database changes should happen until final confirmation
        conn.close()

        # Final confirmation
        summary_parts = []
        if clear_existing:
            summary_parts.append(f"Clear {existing_count} existing records")
        if to_add:
            summary_parts.append(f"Add {len(to_add)} new records")
        if conflicts and update_conflicts:
            summary_parts.append(f"Update {len(conflicts)} conflicting records")
        elif conflicts:
            summary_parts.append(f"Skip {len(conflicts)} conflicting records")
        if exact_duplicates:
            summary_parts.append(f"Skip {len(exact_duplicates)} exact duplicates")

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Import",
            f"Ready to import {table_name.replace('_', ' ')}:\n\n" +
            "\n".join(f"  • {part}" for part in summary_parts) + "\n\n"
            "Proceed with import?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return False

        # Perform import
        try:
            conn = self.db.get_connection()
            c = conn.cursor()

            # Clear existing if requested
            if clear_existing:
                c.execute(f"DELETE FROM {table_name}")

            # Add new records
            added = 0
            for record in to_add:
                cols = ', '.join(record.keys())
                placeholders = ', '.join(['?'] * len(record))
                values = tuple(record.values())
                c.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
                added += 1

            # Update conflicts if requested
            updated = 0
            if update_conflicts:
                for record in conflicts:
                    # Build SET clause
                    set_cols = [f"{col} = ?" for col in record.keys() if col != unique_column]
                    set_clause = ', '.join(set_cols)
                    values = [record[col] for col in record.keys() if col != unique_column]
                    values.append(record[unique_column].lower())

                    c.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE LOWER({unique_column}) = ?",
                        values
                    )
                    updated += 1

            conn.commit()

            # Log audit
            details = f"Imported from CSV: {added} added"
            if updated:
                details += f", {updated} updated"
            if exact_duplicates:
                details += f", {len(exact_duplicates)} skipped"
            self.db.log_audit_conditional("IMPORT", table_name, details=details)

            conn.close()

            # Refresh UI
            if refresh_tab and hasattr(refresh_tab, 'load_data'):
                refresh_tab.load_data()

            # Show success
            QtWidgets.QMessageBox.information(
                self, "Import Complete",
                f"{table_name.replace('_', ' ').title()} imported successfully!\n\n"
                f"Added: {added}\n"
                f"Updated: {updated}\n"
                f"Skipped: {len(exact_duplicates) + (len(conflicts) if not update_conflicts else 0)}"
            )

        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Import Failed",
                f"Failed to import {table_name}:\n{exc}"
            )
            return

    def _upload_table_with_fk(self, table_name, unique_column, foreign_keys, refresh_tab=None):
        """Generic CSV upload for tables with foreign key relationships.

        Args:
            table_name: Database table name
            unique_column: Column name that uniquely identifies records
            foreign_keys: Dict mapping FK column names to (ref_table, display_name)
                         e.g., {"user_id": ("users", "User")}
            refresh_tab: Optional tab widget to refresh after import
        """
        import csv

        # Get schema
        schema = self._get_table_schema(table_name)

        # File selection
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, f"Select {table_name.replace('_', ' ').title()} CSV", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return False

        # Ask if user wants to clear existing data
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing_count = c.fetchone()[0]
        conn.close()

        if existing_count > 0:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Clear Existing Data?",
                f"There are {existing_count} existing records.\n\n"
                f"Do you want to clear all existing {table_name.replace('_', ' ')} before importing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            clear_existing = (reply == QtWidgets.QMessageBox.Yes)
        else:
            clear_existing = False

        # Read and validate CSV
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                csv_headers = reader.fieldnames

                # Validate required headers
                missing_required = []
                for col in schema['columns']:
                    display_name = schema['display_names'][col]
                    if col in schema['required'] and display_name not in csv_headers:
                        missing_required.append(display_name)

                if missing_required:
                    QtWidgets.QMessageBox.warning(
                        self, "Invalid CSV",
                        f"CSV is missing required columns:\n" + "\n".join(f"  - {col}" for col in missing_required)
                    )
                    return False

                # Read all rows
                rows = list(reader)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Error Reading CSV",
                f"Failed to read CSV file:\n{exc}"
            )
            return False

        if not rows:
            QtWidgets.QMessageBox.information(self, "Empty CSV", "The CSV file contains no data rows.")
            return False

        # Get existing records and FK lookup tables
        conn = self.db.get_connection()
        c = conn.cursor()

        # Build FK lookup maps
        fk_lookups = {}
        for fk_col, (ref_table, display_name) in foreign_keys.items():
            c.execute(f"SELECT id, name FROM {ref_table}")
            fk_lookups[fk_col] = {row[1].lower(): row[0] for row in c.fetchall()}

        # Get existing records
        cols = ', '.join(schema['columns'])
        c.execute(f"SELECT {cols} FROM {table_name}")
        existing_records = {}

        for row in c.fetchall():
            record = {schema['columns'][i]: row[i] for i in range(len(row))}
            key = str(record[unique_column]).lower() if record[unique_column] else None
            if key:
                existing_records[key] = record

        conn.close()

        # Parse and validate CSV rows
        to_add = []
        exact_duplicates = []
        conflicts = []
        invalid_rows = []

        for row_idx, csv_row in enumerate(rows, start=2):  # start=2 for Excel-style row numbers
            record = {}
            unique_val = None
            errors = []

            for col in schema['columns']:
                display_name = schema['display_names'][col]
                csv_value = csv_row.get(display_name, '').strip()

                # Handle foreign keys
                if col in foreign_keys:
                    ref_table, fk_display_name = foreign_keys[col]
                    if csv_value:
                        # Look up FK
                        fk_id = fk_lookups[col].get(csv_value.lower())
                        if fk_id is None:
                            errors.append(f"{fk_display_name} '{csv_value}' not found")
                            record[col] = None
                        else:
                            record[col] = fk_id
                    else:
                        record[col] = None
                # Handle boolean/integer columns (processed, active, is_active, is_free_sc, more_remaining, etc.)
                elif col in ('active', 'is_active', 'processed', 'is_free_sc', 'more_remaining'):
                    if csv_value:
                        record[col] = 1 if csv_value.lower() in ('1', 'true', 'yes', 'active') else 0
                    else:
                        record[col] = 0
                # Handle numeric columns
                elif col in ('rtp', 'cashback_rate', 'sc_rate'):
                    if csv_value:
                        try:
                            record[col] = float(csv_value)
                        except ValueError:
                            errors.append(f"Invalid number for {display_name}: '{csv_value}'")
                            record[col] = None
                    else:
                        record[col] = None
                # Handle text columns
                elif csv_value:
                    record[col] = csv_value
                else:
                    record[col] = None

                if col == unique_column:
                    unique_val = csv_value

            if not unique_val:
                errors.append(f"Missing {schema['display_names'][unique_column]}")

            # If there are validation errors, mark as invalid
            if errors:
                invalid_rows.append({
                    'row': row_idx,
                    'name': unique_val or '(unnamed)',
                    'errors': errors
                })
                continue

            key = unique_val.lower()

            # Check if record exists
            if key in existing_records:
                existing = existing_records[key]
                is_exact = all(record.get(col) == existing.get(col) for col in schema['columns'])

                if is_exact:
                    exact_duplicates.append(unique_val)
                else:
                    conflicts.append(record)
            else:
                to_add.append(record)

        # Report invalid rows
        if invalid_rows:
            error_summary = "\n".join([
                f"Row {r['row']}: {r['name']} - {', '.join(r['errors'])}"
                for r in invalid_rows[:10]
            ])
            if len(invalid_rows) > 10:
                error_summary += f"\n... and {len(invalid_rows) - 10} more errors"

            reply = QtWidgets.QMessageBox.question(
                self,
                "Validation Errors",
                f"Found {len(invalid_rows)} invalid rows:\n\n{error_summary}\n\n"
                f"Skip these rows and import {len(to_add) + len(conflicts)} valid rows?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return False

        # Report findings
        if not to_add and not conflicts:
            QtWidgets.QMessageBox.information(
                self, "No Changes",
                f"All valid records in the CSV already exist in the database.\n\n"
                f"Exact duplicates skipped: {len(exact_duplicates)}\n"
                f"Invalid rows skipped: {len(invalid_rows)}"
            )
            return False

        # Handle conflicts
        update_conflicts = False
        if conflicts:
            conflict_list = "\n".join([f"  - {rec[unique_column]}" for rec in conflicts[:10]])
            if len(conflicts) > 10:
                conflict_list += f"\n  ... and {len(conflicts) - 10} more"

            reply = QtWidgets.QMessageBox.question(
                self,
                "Handle Conflicts?",
                f"Found {len(conflicts)} records with same {unique_column} but different data:\n\n"
                f"{conflict_list}\n\n"
                "Do you want to UPDATE these records with the CSV values?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.Cancel:
                return False
            update_conflicts = (reply == QtWidgets.QMessageBox.Yes)

        # Close the connection used for reading - no database changes should happen until final confirmation
        conn.close()

        # Final confirmation
        summary_parts = []
        if clear_existing:
            summary_parts.append(f"Clear {existing_count} existing records")
        if to_add:
            summary_parts.append(f"Add {len(to_add)} new records")
        if conflicts and update_conflicts:
            summary_parts.append(f"Update {len(conflicts)} conflicting records")
        elif conflicts:
            summary_parts.append(f"Skip {len(conflicts)} conflicting records")
        if exact_duplicates:
            summary_parts.append(f"Skip {len(exact_duplicates)} exact duplicates")
        if csv_duplicates:
            summary_parts.append(f"Skip {len(csv_duplicates)} CSV duplicates")
        if invalid_rows:
            summary_parts.append(f"Skip {len(invalid_rows)} invalid rows")

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Import",
            f"Ready to import {table_name.replace('_', ' ')}:\n\n" +
            "\n".join(f"  • {part}" for part in summary_parts) + "\n\n"
            "Proceed with import?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return False

        # Perform import
        try:
            conn = self.db.get_connection()
            c = conn.cursor()

            # Clear existing if requested
            if clear_existing:
                c.execute(f"DELETE FROM {table_name}")

            # Add new records
            added = 0
            for record in to_add:
                cols = ', '.join(record.keys())
                placeholders = ', '.join(['?'] * len(record))
                values = tuple(record.values())
                c.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", values)
                added += 1

            # Update conflicts if requested
            updated = 0
            if update_conflicts:
                for record in conflicts:
                    set_cols = [f"{col} = ?" for col in record.keys() if col != unique_column]
                    set_clause = ', '.join(set_cols)
                    values = [record[col] for col in record.keys() if col != unique_column]
                    values.append(record[unique_column].lower())

                    c.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE LOWER({unique_column}) = ?",
                        values
                    )
                    updated += 1

            conn.commit()

            # Log audit
            details = f"Imported from CSV: {added} added"
            if updated:
                details += f", {updated} updated"
            if exact_duplicates:
                details += f", {len(exact_duplicates)} skipped (duplicates)"
            if invalid_rows:
                details += f", {len(invalid_rows)} skipped (invalid)"
            self.db.log_audit("IMPORT", table_name, details=details)

            conn.close()

            # Refresh UI
            if refresh_tab and hasattr(refresh_tab, 'load_data'):
                refresh_tab.load_data()

            # Show success
            QtWidgets.QMessageBox.information(
                self, "Import Complete",
                f"{table_name.replace('_', ' ').title()} imported successfully!\n\n"
                f"Added: {added}\n"
                f"Updated: {updated}\n"
                f"Skipped: {len(exact_duplicates) + len(csv_duplicates) + len(invalid_rows) + (len(conflicts) if not update_conflicts else 0)}"
            )

        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self, "Import Failed",
                f"Failed to import {table_name}:\n{exc}"
            )
            return

    # CSV Upload Methods for Transactional Data
    def _upload_purchases(self):
        """Upload Purchases from CSV with recalculation prompt"""
        refresh_tab = self.main_window.purchases_tab if self.main_window else None
        # Use composite key: date, time, site, user, and amount to identify unique purchases
        success = self._upload_table_dynamic("purchases",
            unique_column=("purchase_date", "purchase_time", "site_id", "user_id", "amount"),
            refresh_tab=refresh_tab)
        if success:
            self._prompt_recalculate_after_import("Purchases")

    def _upload_sessions(self):
        """Upload Game Sessions from CSV with recalculation prompt"""
        refresh_tab = self.main_window.game_sessions_tab if self.main_window else None
        # Use composite key: date, start time, site, and user to identify unique sessions
        success = self._upload_table_dynamic("game_sessions",
            unique_column=("session_date", "start_time", "site_id", "user_id"),
            refresh_tab=refresh_tab)
        if success:
            self._prompt_recalculate_after_import("Game Sessions")

    def _upload_redemptions(self):
        """Upload Redemptions from CSV with recalculation prompt"""
        refresh_tab = self.main_window.redemptions_tab if self.main_window else None
        # Use composite key: date, time, site, user, and amount to identify unique redemptions
        success = self._upload_table_dynamic("redemptions",
            unique_column=("redemption_date", "redemption_time", "site_id", "user_id", "amount"),
            refresh_tab=refresh_tab)
        if success:
            self._prompt_recalculate_after_import("Redemptions")

    def _upload_expenses(self):
        """Upload Expenses from CSV with recalculation prompt"""
        refresh_tab = self.main_window.expenses_tab if self.main_window else None
        # Use composite key: date, vendor, and amount to identify unique expenses
        success = self._upload_table_dynamic("expenses",
            unique_column=("expense_date", "vendor", "amount"),
            refresh_tab=refresh_tab)
        if success:
            self._prompt_recalculate_after_import("Expenses")

    def _prompt_recalculate_after_import(self, data_type):
        """Prompt user to recalculate everything after importing transactional data"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Recalculate After Import?",
            f"It is recommended to run 'Recalculate Everything' to ensure all session totals "
            "and FIFO cost basis are properly updated after importing {data_type}.\n\n"
            "Would you like to recalculate everything now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        if reply == QtWidgets.QMessageBox.Yes:
            self._recalculate_all()

    def _upload_users(self):
        """Upload Users from CSV using dynamic schema"""
        self._upload_table_dynamic("users", unique_column="name", refresh_tab=self.users_tab)

    def _upload_sites(self):
        """Upload Sites from CSV using dynamic schema"""
        self._upload_table_dynamic("sites", unique_column="name", refresh_tab=self.sites_tab)

    def _upload_cards(self):
        """Upload Cards from CSV using dynamic schema with composite key"""
        self._upload_table_dynamic("cards", unique_column=("name", "user_id"), refresh_tab=self.cards_tab)

    def _upload_methods(self):
        """Upload Redemption Methods from CSV using dynamic schema with composite key"""
        self._upload_table_dynamic("redemption_methods", unique_column=("name", "user_id"), refresh_tab=self.methods_tab)

    def _upload_game_types(self):
        """Upload Game Types from CSV using dynamic schema"""
        self._upload_table_dynamic("game_types", unique_column="name", refresh_tab=self.game_types_tab)

    def _upload_games(self):
        """Upload Games from CSV using dynamic schema"""
        self._upload_table_dynamic("games", unique_column="name", refresh_tab=self.games_tab)

    # CSV Template Download Methods
    def _download_template_purchases(self):
        headers = self._get_csv_headers("purchases")
        self._download_template("purchases", headers, "purchases_template.csv")

    def _download_template_sessions(self):
        headers = self._get_csv_headers("game_sessions")
        self._download_template("game_sessions", headers, "sessions_template.csv")

    def _download_template_redemptions(self):
        headers = self._get_csv_headers("redemptions")
        self._download_template("redemptions", headers, "redemptions_template.csv")

    def _download_template_expenses(self):
        headers = self._get_csv_headers("expenses")
        self._download_template("expenses", headers, "expenses_template.csv")

    def _download_template_users(self):
        headers = self._get_csv_headers("users")
        self._download_template("users", headers, "users_template.csv")

    def _download_template_sites(self):
        headers = self._get_csv_headers("sites")
        self._download_template("sites", headers, "sites_template.csv")

    def _download_template_cards(self):
        headers = self._get_csv_headers("cards")
        self._download_template("cards", headers, "cards_template.csv")

    def _download_template_methods(self):
        headers = self._get_csv_headers("redemption_methods")
        self._download_template("redemption_methods", headers, "redemption_methods_template.csv")

    def _download_template_game_types(self):
        headers = self._get_csv_headers("game_types")
        self._download_template("game_types", headers, "game_types_template.csv")

    def _download_template_games(self):
        headers = self._get_csv_headers("games")
        self._download_template("games", headers, "games_template.csv")

    def _download_template(self, data_type, headers, filename):
        """Generate and download a CSV template"""
        import csv
        from datetime import datetime

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            f"Download {data_type.title()} Template",
            filename,
            "CSV Files (*.csv)"
        )

        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

            QtWidgets.QMessageBox.information(
                self,
                "Template Downloaded",
                f"Template saved to:\n{path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Failed to save template:\n{str(e)}"
            )

    # CSV Data Download Methods
    def _download_data_purchases(self):
        self._download_data("purchases")

    def _download_data_sessions(self):
        self._download_data("sessions")

    def _download_data_redemptions(self):
        self._download_data("redemptions")

    def _download_data_expenses(self):
        self._download_data("expenses")

    def _download_data_users(self):
        self._download_data("users")

    def _download_data_sites(self):
        self._download_data("sites")

    def _download_data_cards(self):
        self._download_data("cards")

    def _download_data_methods(self):
        self._download_data("redemption_methods")

    def _download_data_game_types(self):
        self._download_data("game_types")

    def _download_data_games(self):
        self._download_data("games")

    def _download_data(self, table_name):
        """Download current data as CSV using dynamic schema"""
        import csv
        from datetime import datetime

        # Handle table name mapping
        actual_table = "game_sessions" if table_name == "sessions" else table_name

        filename = f"{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            f"Download {table_name.replace('_', ' ').title()} Data",
            filename,
            "CSV Files (*.csv)"
        )

        if not path:
            return

        try:
            conn = self.db.get_connection()
            c = conn.cursor()

            # Build dynamic query that resolves all foreign keys
            query, headers = self._build_select_query(actual_table)

            # Execute query
            c.execute(query)
            rows = c.fetchall()
            conn.close()

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in rows:
                    writer.writerow(row)

            QtWidgets.QMessageBox.information(
                self,
                "Data Downloaded",
                f"Downloaded {len(rows)} record(s) to:\n{path}"
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Failed to download data:\n{str(e)}"
            )

    # Recalculation Methods
    def _recalculate_all(self):
        """Recalculate everything (uses existing rebuild_all functionality)"""
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Recalculate Everything",
            "This will recalculate all session totals and FIFO cost basis for the entire database.\n\n"
            "This may take a while depending on the amount of data.\n\n"
            "Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if confirm != QtWidgets.QMessageBox.Yes:
            return

        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            "Recalculating all data...\nThis may take a minute.",
            None,
            0,
            0,
            self
        )
        progress.setWindowTitle("Recalculating")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            result = self.session_mgr.rebuild_all_derived()

            # Refresh all tabs
            if self.main_window:
                self.main_window.purchases_tab.load_data()
                self.main_window.redemptions_tab.load_data()
                self.main_window.game_sessions_tab.load_data()
                self.main_window.daily_sessions_tab.refresh_view()
                self.main_window.unrealized_tab.load_data()
                self.main_window.realized_tab.refresh_view()
                self.main_window.refresh_stats()

            progress.close()

            summary = (
                f"Recalculation Complete!\n\n"
                f"Pairs processed: {result.get('pairs_processed', 0)}\n"
                f"Sessions recalculated: {result.get('sessions_processed', 0)}"
            )
            QtWidgets.QMessageBox.information(self, "Complete", summary)

        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Recalculation failed:\n{str(e)}"
            )

    def _recalculate_sessions(self):
        """Recalculate session data only"""
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Recalculate Sessions",
            "This will recalculate game session totals.\n\n"
            "Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if confirm != QtWidgets.QMessageBox.Yes:
            return

        progress = QtWidgets.QProgressDialog(
            "Recalculating session data...",
            None,
            0,
            0,
            self
        )
        progress.setWindowTitle("Recalculating")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            # Recalculate sessions (this is part of rebuild_all_derived)
            result = self.session_mgr.rebuild_all_derived()

            if self.main_window:
                self.main_window.game_sessions_tab.load_data()
                self.main_window.daily_sessions_tab.refresh_view()
                self.main_window.refresh_stats()

            progress.close()
            QtWidgets.QMessageBox.information(
                self,
                "Complete",
                f"Session recalculation complete!\n\nSessions processed: {result.get('sessions_processed', 0)}"
            )

        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Recalculation failed:\n{str(e)}"
            )

    def _recalculate_fifo(self):
        """Recalculate FIFO cost basis only"""
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Recalculate FIFO",
            "This will recalculate FIFO cost basis for all redemptions.\n\n"
            "Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if confirm != QtWidgets.QMessageBox.Yes:
            return

        progress = QtWidgets.QProgressDialog(
            "Recalculating FIFO cost basis...",
            None,
            0,
            0,
            self
        )
        progress.setWindowTitle("Recalculating")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()

        try:
            result = self.session_mgr.rebuild_all_derived()

            if self.main_window:
                self.main_window.redemptions_tab.load_data()
                self.main_window.realized_tab.refresh_view()
                self.main_window.unrealized_tab.load_data()
                self.main_window.refresh_stats()

            progress.close()
            QtWidgets.QMessageBox.information(
                self,
                "Complete",
                f"FIFO recalculation complete!\n\nPairs processed: {result.get('pairs_processed', 0)}"
            )

        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Recalculation failed:\n{str(e)}"
            )

    def _recalculate_rtp(self):
        """Placeholder for RTP recalculation"""
        QtWidgets.QMessageBox.information(
            self,
            "Coming Soon",
            "RTP recalculation will be implemented in a future update."
        )

    # Audit Log Methods
    def _load_audit_settings(self):
        """Load audit log settings from database and populate UI"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Helper to get setting with default
            def get_setting(key, default):
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row["value"] if row else default
            
            # Load enabled state
            enabled = int(get_setting("audit_log_enabled", "0"))
            self.audit_enabled_check.setChecked(bool(enabled))
            
            # Load which action types are enabled
            actions = get_setting("audit_log_actions", "INSERT,UPDATE,DELETE,IMPORT,REFACTOR")
            action_list = [a.strip() for a in actions.split(",")]
            self.audit_insert_check.setChecked("INSERT" in action_list)
            self.audit_update_check.setChecked("UPDATE" in action_list)
            self.audit_delete_check.setChecked("DELETE" in action_list)
            self.audit_import_check.setChecked("IMPORT" in action_list)
            self.audit_system_check.setChecked("REFACTOR" in action_list or "BACKUP" in action_list)
            
            # Load retention days
            try:
                retention = int(get_setting("audit_log_retention_days", "365"))
                self.audit_retention_spin.setValue(retention)
            except:
                self.audit_retention_spin.setValue(365)
            
            # Load default user
            default_user = get_setting("audit_log_default_user", "")
            self.audit_user_edit.setText(default_user)
            
            # Load auto-backup settings
            auto_backup = int(get_setting("audit_log_auto_backup", "0"))
            self.audit_backup_check.setChecked(bool(auto_backup))
            
            backup_interval = int(get_setting("audit_log_backup_interval_days", "30"))
            self.audit_backup_interval_spin.setValue(backup_interval)
            
            conn.close()
            
            # Show/hide backup interval based on checkbox
            if self.audit_backup_check.isChecked():
                self.audit_backup_interval_container.show()
            else:
                self.audit_backup_interval_container.hide()
            
            # Enable/disable controls based on enabled state
            self._on_audit_enabled_changed()
            
        except Exception as e:
            print(f"Error loading audit settings: {e}")
            # Set defaults if loading fails
            self.audit_enabled_check.setChecked(False)
            self.audit_retention_spin.setValue(365)
            self.audit_backup_interval_spin.setValue(30)

    def _save_audit_settings(self):
        """Save audit log settings to database"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Save enabled state
            enabled = "1" if self.audit_enabled_check.isChecked() else "0"
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_enabled", enabled))
            
            # Build comma-separated list of enabled actions
            actions = []
            if self.audit_insert_check.isChecked():
                actions.append("INSERT")
            if self.audit_update_check.isChecked():
                actions.append("UPDATE")
            if self.audit_delete_check.isChecked():
                actions.append("DELETE")
            if self.audit_import_check.isChecked():
                actions.append("IMPORT")
            if self.audit_system_check.isChecked():
                actions.append("REFACTOR")
            
            actions_str = ",".join(actions)
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_actions", actions_str))
            
            # Save retention days
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_retention_days", str(self.audit_retention_spin.value())))
            
            # Save default user (can be empty)
            default_user = self.audit_user_edit.text().strip()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_default_user", default_user))
            
            # Save auto-backup settings
            auto_backup = "1" if self.audit_backup_check.isChecked() else "0"
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_auto_backup", auto_backup))
            
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                          ("audit_log_backup_interval_days", str(self.audit_backup_interval_spin.value())))
            
            conn.commit()
            conn.close()

            QtWidgets.QMessageBox.information(self, "Settings Saved", "Audit log settings saved successfully.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to save audit settings:\n{str(e)}")

    def _view_audit_log(self):
        """Show the audit log viewer dialog"""
        dialog = AuditLogViewerDialog(self.db, self)
        dialog.exec()

    def _export_audit_log(self):
        """Export audit log to CSV"""
        try:
            import csv
            from datetime import datetime
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                QtWidgets.QMessageBox.information(self, "No Data", "No audit log records to export.")
                return
            
            # Create audit_logs backup folder if needed
            backup_folder = os.path.join(os.path.dirname(self.db.db_path), "backups", "audit_logs")
            os.makedirs(backup_folder, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_log_{timestamp}.csv"
            export_path = os.path.join(backup_folder, filename)
            
            # Export to CSV
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Action', 'Table', 'Record ID', 'Details', 'User'])
                
                for row in rows:
                    writer.writerow([
                        row['timestamp'] if 'timestamp' in row.keys() else '',
                        row['action'] if 'action' in row.keys() else '',
                        row['table_name'] if 'table_name' in row.keys() else '',
                        row['record_id'] if 'record_id' in row.keys() else '',
                        row['details'] if 'details' in row.keys() else '',
                        row['user_name'] if 'user_name' in row.keys() else ''
                    ])
            
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"Audit log exported to:\n{export_path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export audit log:\n{str(e)}"
            )

    def _clear_old_audit_records(self):
        """Delete audit log records older than retention setting"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get retention setting
            cursor.execute("SELECT value FROM settings WHERE key = 'audit_log_retention_days'")
            result = cursor.fetchone()
            retention_days = int(result["value"]) if result else 365
            
            # Delete old records
            cursor.execute("""
                DELETE FROM audit_log
                WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
            """, (retention_days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "Records Cleared",
                f"Deleted {deleted_count} audit log record(s) older than {retention_days} days."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear old audit records:\n{str(e)}"
            )

    def _clear_all_audit_logs(self):
        """Delete ALL audit log records after confirmation"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "⚠️ Clear All Audit Logs",
            "Are you sure you want to delete ALL audit log records?\n\n"
            "⚠️ WARNING: This action cannot be undone!\n\n"
            "This will permanently erase the entire audit log history.\n\n"
            "Consider exporting the log first if you need to keep a record.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Count records before deletion
            cursor.execute("SELECT COUNT(*) as count FROM audit_log")
            result = cursor.fetchone()
            total_count = result["count"] if result else 0
            
            # Delete all records
            cursor.execute("DELETE FROM audit_log")
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "All Records Cleared",
                f"Successfully deleted all {total_count} audit log record(s)."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear all audit records:\n{str(e)}"
            )

    def _clear_all_audit_logs(self):
        """Delete ALL audit log records after confirmation"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "⚠️ Clear All Audit Logs",
            "Are you sure you want to delete ALL audit log records?\n\n"
            "⚠️ WARNING: This action cannot be undone!\n\n"
            "This will permanently erase the entire audit log history.\n\n"
            "Consider exporting the log first if you need to keep a record.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Count records before deletion
            cursor.execute("SELECT COUNT(*) as count FROM audit_log")
            result = cursor.fetchone()
            total_count = result["count"] if result else 0
            
            # Delete all records
            cursor.execute("DELETE FROM audit_log")
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "All Records Cleared",
                f"Successfully deleted all {total_count} audit log record(s)."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear all audit records:\n{str(e)}"
            )

    # Database Methods
    def _backup_database(self):
        """Create a database backup"""
        import shutil
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"session_backup_{timestamp}.db"

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Backup Database",
            default_name,
            "Database Files (*.db)"
        )

        if not path:
            return

        try:
            # Get the database file path
            db_path = self.db.db_path

            # Copy the database file
            shutil.copy2(db_path, path)

            QtWidgets.QMessageBox.information(
                self,
                "Backup Complete",
                f"Database backed up to:\n{path}"
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Backup Failed",
                f"Failed to backup database:\n{str(e)}"
            )

    def _load_backup_settings(self):
        """Load automatic backup settings from database"""
        from datetime import datetime, timedelta
        conn = self.db.get_connection()
        c = conn.cursor()

        # Load enabled status
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_enabled'")
        result = c.fetchone()
        enabled = result['value'] == '1' if result else False
        self.auto_backup_enabled_cb.setChecked(enabled)

        # Set visibility of interval widgets based on enabled status
        self.interval_label.setVisible(enabled)
        self.backup_interval_spin.setVisible(enabled)
        self.next_backup_label.setVisible(enabled)

        # Load interval
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_interval_days'")
        result = c.fetchone()
        interval = int(result['value']) if result else 7
        self.backup_interval_spin.setValue(interval)

        # Load folder
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_folder'")
        result = c.fetchone()
        folder = result['value'] if result else ""
        self.backup_folder_display.setText(folder)

        # Load last backup date
        c.execute("SELECT value FROM settings WHERE key = 'last_backup_date'")
        result = c.fetchone()
        last_backup = result['value'] if result else ""

        if last_backup:
            try:
                last_date = datetime.fromisoformat(last_backup)
                days_ago = (datetime.now() - last_date).days

                # Check if backup is due
                if enabled and days_ago >= interval:
                    self.last_backup_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
                    self.last_backup_label.setText(f"⚠️ Last backup: {days_ago} days ago (OVERDUE)")
                else:
                    # Clear any custom styling
                    self.last_backup_label.setStyleSheet("")
                    if days_ago == 0:
                        self.last_backup_label.setText("Last backup: Today")
                    elif days_ago == 1:
                        self.last_backup_label.setText("Last backup: 1 day ago")
                    else:
                        self.last_backup_label.setText(f"Last backup: {days_ago} days ago")
            except:
                self.last_backup_label.setStyleSheet("")
                self.last_backup_label.setText("Last backup: Never")
        else:
            self.last_backup_label.setStyleSheet("")
            self.last_backup_label.setText("Last backup: Never")

        # Calculate next backup time
        self._update_next_backup_label(enabled, last_backup, interval)

        conn.close()

    def _save_backup_settings(self):
        """Save automatic backup settings to database"""
        conn = self.db.get_connection()
        c = conn.cursor()

        enabled = '1' if self.auto_backup_enabled_cb.isChecked() else '0'
        interval = str(self.backup_interval_spin.value())

        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_enabled', ?)", (enabled,))
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_interval_days', ?)", (interval,))

        conn.commit()
        conn.close()

        # Refresh the last backup label to update overdue status
        self._load_backup_settings()

    def _on_auto_backup_checkbox_changed(self):
        """Called when automatic backup checkbox state changes"""
        # Toggle visibility of interval widgets (container stays in layout with fixed height)
        is_enabled = self.auto_backup_enabled_cb.isChecked()
        self.interval_label.setVisible(is_enabled)
        self.backup_interval_spin.setVisible(is_enabled)
        self.next_backup_label.setVisible(is_enabled)
        # Save settings
        self._save_backup_settings()

    def _on_auto_backup_changed(self):
        """Called when automatic backup interval changes"""
        self._save_backup_settings()

    def _update_next_backup_label(self, enabled, last_backup, interval):
        """Update the next backup time label"""
        from datetime import datetime, timedelta

        if not enabled:
            self.next_backup_label.setText("")
            return

        if not last_backup:
            self.next_backup_label.setText("Next backup: Now (no previous backup)")
            return

        try:
            last_date = datetime.fromisoformat(last_backup)
            next_date = last_date + timedelta(days=interval)
            now = datetime.now()

            # Calculate time until next backup
            time_until = next_date - now

            if time_until.total_seconds() <= 0:
                self.next_backup_label.setText("Next backup: Now (overdue)")
            else:
                days = time_until.days
                hours = int(time_until.seconds / 3600)

                if days > 0:
                    if hours > 0:
                        self.next_backup_label.setText(f"Next automatic backup in {days} days, {hours} hours")
                    else:
                        self.next_backup_label.setText(f"Next automatic backup in {days} days")
                elif hours > 0:
                    self.next_backup_label.setText(f"Next automatic backup in {hours} hours")
                else:
                    minutes = int(time_until.seconds / 60)
                    self.next_backup_label.setText(f"Next automatic backup in {minutes} minutes")
        except:
            self.next_backup_label.setText("")

    def _choose_backup_folder(self):
        """Let user choose automatic backup folder"""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose Automatic Backup Folder"
        )

        if folder:
            self.backup_folder_display.setText(folder)

            # Save to database
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('auto_backup_folder', ?)", (folder,))
            conn.commit()
            conn.close()

    def _backup_database_now(self):
        """Perform backup using automatic backup settings"""
        from datetime import datetime
        import shutil
        import os

        # Get backup folder from settings
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_folder'")
        result = c.fetchone()
        backup_folder = result['value'] if result else ""
        conn.close()

        # If no folder set, prompt user to choose
        if not backup_folder or not os.path.exists(backup_folder):
            reply = QtWidgets.QMessageBox.question(
                self,
                "Backup Folder Not Set",
                "No backup folder is configured. Would you like to choose one now?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self._choose_backup_folder()
                # Reload the folder setting
                conn = self.db.get_connection()
                c = conn.cursor()
                c.execute("SELECT value FROM settings WHERE key = 'auto_backup_folder'")
                result = c.fetchone()
                backup_folder = result['value'] if result else ""
                conn.close()

                if not backup_folder:
                    return
            else:
                return

        try:
            # Create database subdirectory if it doesn't exist
            database_folder = os.path.join(backup_folder, "database")
            os.makedirs(database_folder, exist_ok=True)
            
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_filename = f"auto_backup_{timestamp}.db"
            backup_path = os.path.join(database_folder, backup_filename)

            # Copy database
            shutil.copy2(self.db.db_path, backup_path)

            # Update last backup date
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_backup_date', ?)",
                      (datetime.now().isoformat(),))
            conn.commit()
            conn.close()

            # Refresh the UI
            self._load_backup_settings()

            # Dismiss any backup due notification in main window
            if self.main_window:
                self.main_window._dismiss_notification("backup_due")

            QtWidgets.QMessageBox.information(
                self,
                "Backup Complete",
                f"Database backed up successfully to:\n\n{backup_path}"
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Backup Failed",
                f"Failed to backup database:\n{str(e)}"
            )

    def _reset_database(self):
        """Reset database (delete all transaction data, keep setup data)"""
        # First warning
        confirm1 = QtWidgets.QMessageBox.question(
            self,
            "⚠️ Reset Database",
            "⚠️ WARNING ⚠️\n\n"
            "This will PERMANENTLY DELETE:\n"
            "  • All Purchases\n"
            "  • All Game Sessions\n"
            "  • All Redemptions\n"
            "  • All Expenses\n"
            "  • All tax session data\n\n"
            "Setup data (Users, Sites, Cards, Methods, Game Types, Games) will be preserved.\n\n"
            "It is STRONGLY RECOMMENDED to backup your database first.\n\n"
            "Do you want to create a backup now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel
        )

        if confirm1 == QtWidgets.QMessageBox.Cancel:
            return

        if confirm1 == QtWidgets.QMessageBox.Yes:
            self._backup_database()

        # Second confirmation
        confirm2 = QtWidgets.QMessageBox.question(
            self,
            "⚠️ Final Confirmation",
            "Are you ABSOLUTELY SURE you want to delete all transaction data?\n\n"
            "This CANNOT be undone!",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if confirm2 != QtWidgets.QMessageBox.Yes:
            return

        try:
            conn = self.db.get_connection()
            c = conn.cursor()

            # Delete all transaction data
            c.execute("DELETE FROM game_sessions")
            c.execute("DELETE FROM daily_tax_sessions")
            c.execute("DELETE FROM realized_transactions")
            c.execute("DELETE FROM purchases")
            c.execute("DELETE FROM redemptions")
            c.execute("DELETE FROM expenses")
            c.execute("DELETE FROM site_sessions")
            c.execute("DELETE FROM redemption_allocations")
            c.execute("DELETE FROM other_income")

            conn.commit()
            conn.close()

            # Refresh all tabs
            if self.main_window:
                self.main_window.purchases_tab.load_data()
                self.main_window.redemptions_tab.load_data()
                self.main_window.game_sessions_tab.load_data()
                self.main_window.daily_sessions_tab.refresh_view()
                self.main_window.unrealized_tab.load_data()
                self.main_window.realized_tab.refresh_view()
                self.main_window.expenses_tab.load_data()
                self.main_window.refresh_stats()

            QtWidgets.QMessageBox.information(
                self,
                "Reset Complete",
                "All transaction data has been deleted.\n\n"
                "Setup data (Users, Sites, Cards, etc.) has been preserved."
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Reset Failed",
                f"Failed to reset database:\n{str(e)}"
            )

    def _show_not_implemented(self, feature):
        """Show not implemented message"""
        QtWidgets.QMessageBox.information(
            self,
            "Coming Soon",
            f"{feature} functionality will be implemented in a future update."
        )


class SetupTab(QtWidgets.QWidget):
    def __init__(self, db, session_mgr=None, main_window=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.main_window = main_window
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.sub_tab_bar = QtWidgets.QWidget()
        sub_tab_layout = FlowLayout(
            self.sub_tab_bar, margin=0, spacing=8, align=QtCore.Qt.AlignLeft
        )
        self.sub_tab_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )

        self.sub_group = QtWidgets.QButtonGroup(self)
        self.sub_group.setExclusive(True)
        self.sub_stacked = QtWidgets.QStackedWidget()
        self.sub_stacked.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
        )

        # Create tabs and store references
        self.users_tab = UsersSetupTab(self.db)
        self.sites_tab = SitesSetupTab(self.db)
        self.cards_tab = CardsSetupTab(self.db)
        self.methods_tab = MethodsSetupTab(self.db)
        self.game_types_tab = GameTypesSetupTab(self.db)
        self.games_tab = GamesSetupTab(self.db)
        self.tools_tab = ToolsSetupTab(
            self.db,
            self.session_mgr,
            self.main_window,
            users_tab=self.users_tab,
            sites_tab=self.sites_tab,
            cards_tab=self.cards_tab,
            methods_tab=self.methods_tab,
            game_types_tab=self.game_types_tab,
            games_tab=self.games_tab
        )

        tabs = [
            ("Users", self.users_tab),
            ("Sites", self.sites_tab),
            ("Cards", self.cards_tab),
            ("Redemption Methods", self.methods_tab),
            ("Game Types", self.game_types_tab),
            ("Games", self.games_tab),
            ("Tools", self.tools_tab),
        ]

        for idx, (label, widget) in enumerate(tabs):
            widget.setMinimumSize(0, 0)
            widget.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
            )
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("TabButton")
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            self.sub_group.addButton(btn, idx)
            sub_tab_layout.addWidget(btn)
            self.sub_stacked.addWidget(widget)

        self.sub_group.buttonClicked.connect(self._on_sub_tab_clicked)
        self.sub_stacked.currentChanged.connect(self._sync_sub_tab_selection)
        if self.sub_group.button(0):
            self.sub_group.button(0).setChecked(True)
            self.sub_stacked.setCurrentIndex(0)

        layout.addWidget(self.sub_tab_bar)
        layout.addWidget(self.sub_stacked, 1)

    def _on_sub_tab_clicked(self, button):
        index = self.sub_group.id(button)
        if index >= 0:
            self.sub_stacked.setCurrentIndex(index)

    def _sync_sub_tab_selection(self, index):
        button = self.sub_group.button(index)
        if button:
            button.setChecked(True)


class AuditLogViewerDialog(QtWidgets.QDialog):
    """Dialog for viewing and managing audit log records"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Audit Log Viewer")
        self.resize(1200, 600)
        
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Filters section
        filters_group = QtWidgets.QGroupBox("Filters")
        filters_layout = QtWidgets.QHBoxLayout(filters_group)
        
        # Limit filter
        filters_layout.addWidget(QtWidgets.QLabel("Show:"))
        self.limit_combo = QtWidgets.QComboBox()
        self.limit_combo.addItems(["100", "500", "1000", "5000", "All"])
        self.limit_combo.setCurrentText("500")
        filters_layout.addWidget(self.limit_combo)
        
        # Action filter
        filters_layout.addWidget(QtWidgets.QLabel("Action:"))
        self.action_combo = QtWidgets.QComboBox()
        self.action_combo.addItems(["All", "INSERT", "UPDATE", "DELETE", "IMPORT", "REFACTOR", "BACKUP", "RESTORE"])
        filters_layout.addWidget(self.action_combo)
        
        # Table filter
        filters_layout.addWidget(QtWidgets.QLabel("Table:"))
        self.table_combo = QtWidgets.QComboBox()
        self.table_combo.addItem("All")
        # Populate with actual table names
        self._populate_table_filter()
        filters_layout.addWidget(self.table_combo)
        
        # Search field
        filters_layout.addWidget(QtWidgets.QLabel("Search:"))
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search details...")
        self.search_edit.setMinimumWidth(200)
        filters_layout.addWidget(self.search_edit)
        
        # Refresh button in filters
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load_audit_data)
        filters_layout.addWidget(refresh_btn)
        
        filters_layout.addStretch()
        layout.addWidget(filters_group)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Action", "Table", "Record ID", "Details", "User"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # Timestamp
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Action
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Table
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # Record ID
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)           # Details
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # User
        
        layout.addWidget(self.table, 1)
        
        # Info label
        self.info_label = QtWidgets.QLabel("Loading...")
        layout.addWidget(self.info_label)
        
        # Button bar
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        export_btn = QtWidgets.QPushButton("Export to CSV")
        export_btn.clicked.connect(self._export_to_csv)
        button_layout.addWidget(export_btn)
        
        clear_btn = QtWidgets.QPushButton("Clear Old Records")
        clear_btn.clicked.connect(self._clear_old_records)
        button_layout.addWidget(clear_btn)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Connect filter changes to reload
        self.limit_combo.currentTextChanged.connect(self._load_audit_data)
        self.action_combo.currentTextChanged.connect(self._load_audit_data)
        self.table_combo.currentTextChanged.connect(self._load_audit_data)
        self.search_edit.textChanged.connect(self._apply_search_filter)
        
        # Load initial data
        self._load_audit_data()
    
    def _populate_table_filter(self):
        """Populate table filter with unique table names from audit log"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT table_name FROM audit_log ORDER BY table_name")
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                table_name = row["table_name"] if "table_name" in row.keys() else row[0]
                if table_name:
                    self.table_combo.addItem(table_name)
        except Exception as e:
            print(f"Error populating table filter: {e}")
    
    def _load_audit_data(self):
        """Load audit log data based on current filters"""
        try:
            # Build query with filters
            query = "SELECT timestamp, action, table_name, record_id, details, user_name FROM audit_log WHERE 1=1"
            params = []
            
            # Action filter
            action_filter = self.action_combo.currentText()
            if action_filter != "All":
                query += " AND action = ?"
                params.append(action_filter)
            
            # Table filter
            table_filter = self.table_combo.currentText()
            if table_filter != "All":
                query += " AND table_name = ?"
                params.append(table_filter)
            
            # Order by timestamp descending (newest first)
            query += " ORDER BY timestamp DESC"
            
            # Limit
            limit_text = self.limit_combo.currentText()
            if limit_text != "All":
                query += f" LIMIT {limit_text}"
            
            # Execute query
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            # Populate table
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(
                    row["timestamp"] if "timestamp" in row.keys() else ""
                ))
                self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(
                    row["action"] if "action" in row.keys() else ""
                ))
                self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(
                    row["table_name"] if "table_name" in row.keys() else ""
                ))
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(
                    str(row["record_id"]) if "record_id" in row.keys() and row["record_id"] else ""
                ))
                self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(
                    row["details"] if "details" in row.keys() else ""
                ))
                self.table.setItem(i, 5, QtWidgets.QTableWidgetItem(
                    row["user_name"] if "user_name" in row.keys() else ""
                ))
            
            self.table.setSortingEnabled(True)
            
            # Update info label
            total_count = len(rows)
            self.info_label.setText(f"Showing {total_count} record(s)")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load audit log:\n{str(e)}"
            )
            self.info_label.setText("Error loading data")
    
    def _apply_search_filter(self):
        """Filter visible rows based on search text"""
        search_text = self.search_edit.text().strip().lower()
        
        for row in range(self.table.rowCount()):
            show_row = False
            if not search_text:
                show_row = True
            else:
                # Search in all columns
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item and search_text in item.text().lower():
                        show_row = True
                        break
            
            self.table.setRowHidden(row, not show_row)
        
        # Update info label with visible count
        visible_count = sum(1 for row in range(self.table.rowCount()) if not self.table.isRowHidden(row))
        self.info_label.setText(f"Showing {visible_count} of {self.table.rowCount()} record(s)")
    
    def _export_to_csv(self):
        """Export current filtered view to CSV"""
        try:
            import csv
            from datetime import datetime
            
            # Create audit_logs backup folder if needed
            backup_folder = os.path.join(os.path.dirname(self.db.db_path), "backups", "audit_logs")
            os.makedirs(backup_folder, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_log_{timestamp}.csv"
            export_path = os.path.join(backup_folder, filename)
            
            # Export visible rows to CSV
            with open(export_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Action', 'Table', 'Record ID', 'Details', 'User'])
                
                for row in range(self.table.rowCount()):
                    if not self.table.isRowHidden(row):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)
            
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"Audit log exported to:\n{export_path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export audit log:\n{str(e)}"
            )
    
    def _clear_old_records(self):
        """Delete audit log records older than retention setting"""
        try:
            # Get retention setting
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'audit_log_retention_days'")
            result = cursor.fetchone()
            retention_days = int(result["value"]) if result else 365
            conn.close()
            
            # Confirm with user
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Clear",
                f"Delete all audit log records older than {retention_days} days?\nThis cannot be undone.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply != QtWidgets.QMessageBox.Yes:
                return
            
            # Delete old records
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM audit_log
                WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
            """, (retention_days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "Records Cleared",
                f"Deleted {deleted_count} audit log record(s) older than {retention_days} days."
            )
            
            # Reload data
            self._load_audit_data()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear old audit records:\n{str(e)}"
            )


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Session - Social Casino Tracker (Qt)")
        self.resize(1400, 900)
        self.setMinimumSize(0, 0)
        self._did_fit_screen = False
        self.db = Database()
        self.session_mgr = SessionManager(self.db, FIFOCalculator(self.db))
        self.completer_filter = ComboCompleterFilter(self)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app._completer_filter = self.completer_filter
            app.installEventFilter(self.completer_filter)

        # Load theme preference
        self.current_theme = self._load_theme_preference()

        self._apply_style()

        central = QtWidgets.QWidget()
        central.setMinimumSize(0, 0)
        central.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        main_layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)

        self.stats_bar = StatsBar()
        main_layout.addWidget(self.stats_bar)
        notification_row = QtWidgets.QHBoxLayout()
        notification_row.addStretch(1)

        # Notification bell button
        self.notification_btn = QtWidgets.QPushButton("🔔")
        self.notification_btn.setFixedSize(50, 40)
        self.notification_btn.setToolTip("Notifications")
        self.notification_btn.clicked.connect(self._show_notifications)

        # Notification badge (red circle with count)
        self.notification_badge = QtWidgets.QLabel("")
        self.notification_badge.setFixedSize(18, 18)
        self.notification_badge.setAlignment(QtCore.Qt.AlignCenter)
        self.notification_badge.setStyleSheet("""
            QLabel {
                background-color: #d32f2f;
                color: white;
                border-radius: 9px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        self.notification_badge.hide()

        # Stack bell and badge
        notification_stack = QtWidgets.QWidget()
        notification_stack.setFixedSize(50, 40)
        stack_layout = QtWidgets.QGridLayout(notification_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.addWidget(self.notification_btn, 0, 0)
        stack_layout.addWidget(self.notification_badge, 0, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)

        notification_row.addWidget(notification_stack)

        # Settings gear button
        self.settings_btn = QtWidgets.QPushButton("⚙️")
        self.settings_btn.setFixedSize(50, 40)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._show_settings_menu)
        notification_row.addWidget(self.settings_btn)

        main_layout.addLayout(notification_row)

        # Notification list
        self.notifications = []

        self.tab_bar = QtWidgets.QWidget()
        tab_bar_layout = FlowLayout(self.tab_bar, margin=0, spacing=8, align=QtCore.Qt.AlignCenter)
        self.tab_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.tab_bar.setMinimumWidth(0)

        self.tab_group = QtWidgets.QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.stacked = QtWidgets.QStackedWidget()
        self.stacked.setMinimumSize(0, 0)
        self.stacked.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.tab_buttons = []

        self.purchases_tab = PurchasesTab(self.db, self.session_mgr, self.refresh_stats, main_window=self)
        self.redemptions_tab = RedemptionsTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            on_open_purchase=self.open_purchase,
            main_window=self,
        )
        self.game_sessions_tab = GameSessionsTab(
            self.db, self.session_mgr, self.refresh_stats, main_window=self
        )
        self.daily_sessions_tab = DailySessionsTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            self.open_game_session,
            self.edit_game_session,
            self.delete_game_session,
            on_open_purchase=self.open_purchase,
            on_open_redemption=self.open_redemption,
        )
        self.unrealized_tab = UnrealizedTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            on_open_purchase=self.open_purchase,
        )
        self.realized_tab = RealizedTab(
            self.db,
            self.refresh_stats,
            on_open_redemption=self.open_redemption,
            on_open_purchase=self.open_purchase,
        )
        self.expenses_tab = ExpensesTab(self.db, self.refresh_stats)
        self.reports_tab = ReportsTab(self.db, self.refresh_stats, self)
        self.setup_tab = SetupTab(self.db, self.session_mgr, self)

        tabs = [
            ("Purchases", self.purchases_tab),
            ("Redemptions", self.redemptions_tab),
            ("Game Sessions", self.game_sessions_tab),
            ("Daily Sessions", self.daily_sessions_tab),
            ("Unrealized", self.unrealized_tab),
            ("Realized", self.realized_tab),
            ("Expenses", self.expenses_tab),
            ("Reports", self.reports_tab),
            ("Setup", self.setup_tab),
        ]

        for idx, (label, widget) in enumerate(tabs):
            widget.setMinimumSize(0, 0)
            widget.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored
            )
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setObjectName("TabButton")
            btn.setMinimumWidth(0)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            self.tab_group.addButton(btn, idx)
            tab_bar_layout.addWidget(btn)
            self.tab_buttons.append((btn, label))
            self.stacked.addWidget(widget)

        self.tab_group.buttonClicked.connect(self._on_tab_clicked)
        self.stacked.currentChanged.connect(self._sync_tab_selection)
        if self.tab_group.button(0):
            self.tab_group.button(0).setChecked(True)
            self.stacked.setCurrentIndex(0)

        main_layout.addWidget(self.tab_bar)
        self.tab_tip = QtWidgets.QLabel("")
        self.tab_tip.setObjectName("TabTip")
        self.tab_tip.setWordWrap(True)
        self.tab_tip.setAlignment(QtCore.Qt.AlignCenter)
        self.tab_tip.setMinimumHeight(self.tab_tip.fontMetrics().lineSpacing() * 2 + 10)
        main_layout.addWidget(self.tab_tip)
        main_layout.addWidget(self.stacked, 1)
        self.setCentralWidget(central)
        self._fit_to_screen()

        self.tab_descriptions = {
            "Purchases": "Log every sweep coin purchase here. This is your cost basis.",
            "Redemptions": "Log every cash-out here so FIFO and taxable results stay accurate.",
            "Game Sessions": "Start/end play sessions here to track SC changes and session P/L.",
            "Daily Sessions": "Daily rollup of closed sessions for tax reporting. Click a date to add notes or a session to view details.",
            "Unrealized": "Shows money still at risk: remaining purchase basis vs current redeemable value.",
            "Realized": "Summary of closed balances and cash flow you’ve already realized.",
            "Expenses": "Track business expenses tied to play or operations.",
            "Reports": "Generate summaries and exports for taxes or analysis.",
            "Setup": "Manage users, sites, games, and other lookup lists.",
        }

        self.refresh_stats()
        self._update_tab_tip(0)

        # Check if backup is due on startup
        self._check_backup_due()

    def _fit_to_screen(self):
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        margin = 40
        max_width = max(0, available.width() - margin)
        max_height = max(0, available.height() - margin)
        if max_width == 0 or max_height == 0:
            return
        self.setMaximumSize(max_width, max_height)
        target_width = min(self.width(), max_width)
        target_height = min(self.height(), max_height)
        self.resize(target_width, target_height)
        self.move(
            available.x() + max(0, (available.width() - target_width) // 2),
            available.y(),
        )

    def showEvent(self, event):
        super().showEvent(event)
        if not self._did_fit_screen:
            self._fit_to_screen()
            self._did_fit_screen = True

    def refresh_stats(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(amount), 0) as total FROM purchases")
        invested = float(c.fetchone()["total"])
        c.execute("SELECT COALESCE(SUM(amount), 0) as total FROM redemptions")
        redeemed = float(c.fetchone()["total"])
        c.execute("SELECT COALESCE(SUM(remaining_amount), 0) as total FROM purchases")
        unrealized = float(c.fetchone()["total"])
        c.execute("SELECT COUNT(*) as total FROM game_sessions WHERE status = 'Closed'")
        sessions = int(c.fetchone()["total"])
        conn.close()

        self.stats_bar.set_stats(
            {
                "invested": invested,
                "redeemed": redeemed,
                "net_cash": redeemed - invested,
                "unrealized": unrealized,
                "sessions": sessions,
            }
        )
        
        # Refresh tabs to reflect changes
        if hasattr(self, 'unrealized_tab'):
            self.unrealized_tab.load_data()
        if hasattr(self, 'daily_sessions_tab'):
            self.daily_sessions_tab.refresh_view()
        if hasattr(self, 'realized_tab'):
            self.realized_tab.refresh_view()

    def _rebuild_all(self):
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Rebuild All",
            "Rebuild FIFO and session calculations for the entire database?\n\n"
            "This may take a while and will refresh all tabs.",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            result = self.session_mgr.rebuild_all_derived()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self.purchases_tab.load_data()
        self.redemptions_tab.load_data()
        self.game_sessions_tab.load_data()
        self.daily_sessions_tab.refresh_view()
        self.unrealized_tab.load_data()
        self.realized_tab.refresh_view()
        self.refresh_stats()

        summary = (
            f"Pairs processed: {result.get('pairs_processed', 0)}\n"
            f"Sessions recalculated: {result.get('sessions_processed', 0)}"
        )
        QtWidgets.QMessageBox.information(self, "Rebuild Complete", summary)

    def _add_notification(self, title, message, notification_id=None):
        """Add a notification to the list"""
        notification = {
            'id': notification_id or f"notif_{len(self.notifications)}",
            'title': title,
            'message': message,
            'timestamp': QtCore.QDateTime.currentDateTime()
        }
        self.notifications.append(notification)
        self._update_notification_badge()

    def _update_notification_badge(self):
        """Update the notification badge count"""
        count = len(self.notifications)
        if count > 0:
            self.notification_badge.setText(str(count))
            self.notification_badge.show()
        else:
            self.notification_badge.hide()

    def _show_notifications(self):
        """Show notifications dropdown"""
        if not self.notifications:
            QtWidgets.QMessageBox.information(
                self,
                "Notifications",
                "No notifications"
            )
            return

        # Create notifications dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Notifications")
        dialog.setMinimumWidth(400)

        layout = QtWidgets.QVBoxLayout(dialog)

        for notif in self.notifications:
            notif_widget = QtWidgets.QWidget()
            notif_layout = QtWidgets.QVBoxLayout(notif_widget)
            notif_layout.setContentsMargins(10, 10, 10, 10)

            title_label = QtWidgets.QLabel(notif['title'])
            title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
            notif_layout.addWidget(title_label)

            message_label = QtWidgets.QLabel(notif['message'])
            message_label.setWordWrap(True)
            notif_layout.addWidget(message_label)

            time_label = QtWidgets.QLabel(notif['timestamp'].toString("MMM d, yyyy h:mm AP"))
            time_label.setObjectName("HelperText")
            notif_layout.addWidget(time_label)

            dismiss_btn = QtWidgets.QPushButton("Dismiss")
            dismiss_btn.setMaximumWidth(100)
            dismiss_btn.clicked.connect(lambda checked, n=notif: self._dismiss_notification(n['id'], dialog))
            notif_layout.addWidget(dismiss_btn)

            notif_widget.setStyleSheet("QWidget { background: #f7f9ff; border: 1px solid #dfeaff; border-radius: 8px; }")
            layout.addWidget(notif_widget)

        clear_all_btn = QtWidgets.QPushButton("Clear All")
        clear_all_btn.clicked.connect(lambda: self._clear_all_notifications(dialog))
        layout.addWidget(clear_all_btn)

        dialog.exec_()

    def _dismiss_notification(self, notification_id, dialog=None):
        """Dismiss a single notification"""
        self.notifications = [n for n in self.notifications if n['id'] != notification_id]
        self._update_notification_badge()
        if dialog:
            dialog.close()
            if self.notifications:
                self._show_notifications()

    def _clear_all_notifications(self, dialog=None):
        """Clear all notifications"""
        self.notifications = []
        self._update_notification_badge()
        if dialog:
            dialog.close()

    def _show_settings_menu(self):
        """Show settings dropdown menu"""
        # Create settings dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(500)

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Setup Section
        setup_label = QtWidgets.QLabel("Setup")
        setup_label.setObjectName("SectionTitle")
        layout.addWidget(setup_label)

        setup_buttons = [
            ("Users", 0),
            ("Sites", 1),
            ("Cards", 2),
            ("Redemption Methods", 3),
            ("Game Types", 4),
            ("Games", 5),
            ("Tools", 6),
        ]

        for label, index in setup_buttons:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(lambda checked, idx=index: self._navigate_to_setup_tab(idx, dialog))
            layout.addWidget(btn)

        layout.addSpacing(10)

        # Display Section
        display_label = QtWidgets.QLabel("Display")
        display_label.setObjectName("SectionTitle")
        layout.addWidget(display_label)

        # Theme toggle
        theme_row = QtWidgets.QHBoxLayout()
        theme_label = QtWidgets.QLabel("Theme:")
        theme_row.addWidget(theme_label)

        self.theme_toggle_light = QtWidgets.QRadioButton("Light")
        self.theme_toggle_dark = QtWidgets.QRadioButton("Dark")

        if self.current_theme == 'light':
            self.theme_toggle_light.setChecked(True)
        else:
            self.theme_toggle_dark.setChecked(True)

        self.theme_toggle_light.toggled.connect(lambda checked: self._toggle_theme('light', checked, dialog))
        self.theme_toggle_dark.toggled.connect(lambda checked: self._toggle_theme('dark', checked, dialog))

        theme_row.addWidget(self.theme_toggle_light)
        theme_row.addWidget(self.theme_toggle_dark)
        theme_row.addStretch()

        layout.addLayout(theme_row)

        layout.addStretch()

        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def _navigate_to_setup_tab(self, setup_index, settings_dialog):
        """Navigate to a specific Setup sub-tab"""
        # First close the dialog
        settings_dialog.accept()

        # Use QTimer to defer the navigation until after dialog is fully closed
        QtCore.QTimer.singleShot(0, lambda: self._do_navigation(setup_index))

    def _do_navigation(self, setup_index):
        """Perform the actual navigation to setup tab"""
        # Switch to Setup tab
        for i, (btn, label) in enumerate(self.tab_buttons):
            if label == "Setup":
                btn.setChecked(True)
                self.stacked.setCurrentIndex(i)

                # Switch to the specific setup sub-tab
                if hasattr(self, 'setup_tab'):
                    if hasattr(self.setup_tab, 'sub_group') and hasattr(self.setup_tab, 'sub_stacked'):
                        # First set the stacked widget index
                        self.setup_tab.sub_stacked.setCurrentIndex(setup_index)
                        # Then check the corresponding button
                        sub_button = self.setup_tab.sub_group.button(setup_index)
                        if sub_button:
                            sub_button.setChecked(True)
                break

    def _toggle_theme(self, theme, checked, dialog):
        """Toggle between light and dark theme"""
        if checked:
            self._save_theme_preference(theme)
            # Close dialog and schedule reopen to avoid modal session warning
            dialog.accept()
            QtCore.QTimer.singleShot(100, self._show_settings_menu)

    def _check_backup_due(self):
        """Check if automatic backup is due and show notification/dialog"""
        from datetime import datetime
        import os

        conn = self.db.get_connection()
        c = conn.cursor()

        # Check if auto backup is enabled
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_enabled'")
        result = c.fetchone()
        if not result or result['value'] != '1':
            conn.close()
            return

        # Get backup settings
        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_interval_days'")
        result = c.fetchone()
        interval = int(result['value']) if result else 7

        c.execute("SELECT value FROM settings WHERE key = 'last_backup_date'")
        result = c.fetchone()
        last_backup = result['value'] if result else ""

        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_folder'")
        result = c.fetchone()
        backup_folder = result['value'] if result else ""

        conn.close()

        # Check if backup is due
        days_since_backup = None
        if last_backup:
            try:
                last_date = datetime.fromisoformat(last_backup)
                days_since_backup = (datetime.now() - last_date).days
            except:
                days_since_backup = None

        is_due = (days_since_backup is None) or (days_since_backup >= interval)

        if is_due:
            # Add notification
            if days_since_backup is None:
                msg = "No backup has been created yet. Would you like to create one now?"
            else:
                msg = f"It's been {days_since_backup} days since your last backup. Would you like to backup now?"

            self._add_notification(
                "Database Backup Due",
                msg,
                "backup_due"
            )

            # Show popup dialog
            reply = QtWidgets.QMessageBox.question(
                self,
                "⚠️ Database Backup Due",
                f"{msg}\n\nYou can dismiss this reminder, and you won't be reminded again until the next backup cycle.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self._perform_automatic_backup(backup_folder)

        # Start background timer (check every hour)
        self.backup_timer = QtCore.QTimer(self)
        self.backup_timer.timeout.connect(self._check_backup_timer)
        self.backup_timer.start(3600000)  # 1 hour in milliseconds

    def _check_backup_timer(self):
        """Background timer to check if backup becomes due"""
        from datetime import datetime

        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_enabled'")
        result = c.fetchone()
        if not result or result['value'] != '1':
            conn.close()
            return

        c.execute("SELECT value FROM settings WHERE key = 'auto_backup_interval_days'")
        result = c.fetchone()
        interval = int(result['value']) if result else 7

        c.execute("SELECT value FROM settings WHERE key = 'last_backup_date'")
        result = c.fetchone()
        last_backup = result['value'] if result else ""

        conn.close()

        if last_backup:
            try:
                last_date = datetime.fromisoformat(last_backup)
                days_since_backup = (datetime.now() - last_date).days

                if days_since_backup >= interval:
                    # Check if we already have this notification
                    has_notification = any(n['id'] == 'backup_due' for n in self.notifications)
                    if not has_notification:
                        self._add_notification(
                            "Database Backup Due",
                            f"It's been {days_since_backup} days since your last backup.",
                            "backup_due"
                        )
            except:
                pass

    def _perform_automatic_backup(self, backup_folder):
        """Perform automatic backup to the configured folder"""
        from datetime import datetime
        import shutil
        import os

        if not backup_folder or not os.path.exists(backup_folder):
            QtWidgets.QMessageBox.warning(
                self,
                "Backup Folder Not Set",
                "Please configure the automatic backup folder in Setup > Tools > Database Tools."
            )
            return

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_filename = f"auto_backup_{timestamp}.db"
            backup_path = os.path.join(backup_folder, backup_filename)

            # Copy database
            shutil.copy2(self.db.db_path, backup_path)

            # Update last backup date
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_backup_date', ?)",
                      (datetime.now().isoformat(),))
            conn.commit()
            conn.close()

            # Remove the backup due notification
            self._dismiss_notification("backup_due")

            QtWidgets.QMessageBox.information(
                self,
                "Backup Complete",
                f"Database backed up to:\n{backup_path}"
            )

            # Refresh the tools tab if it's open
            if hasattr(self, 'setup_tab'):
                for i in range(self.setup_tab.sub_stacked.count()):
                    widget = self.setup_tab.sub_stacked.widget(i)
                    if isinstance(widget, ToolsSetupTab):
                        widget._load_backup_settings()
                        break

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Backup Failed",
                f"Failed to backup database:\n{str(e)}"
            )

    def open_game_session(self, session_id):
        target_index = self.stacked.indexOf(self.game_sessions_tab)
        if target_index < 0:
            return
        self.stacked.setCurrentIndex(target_index)
        if not self.game_sessions_tab.select_session_by_id(session_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "Session not visible with current filters.",
            )
            return
        self.game_sessions_tab.view_session_by_id(session_id)

    def view_realized_position(self, redemption_id):
        """Navigate to Realized tab and highlight the specified redemption."""
        # Switch to Realized tab (index 5)
        realized_tab_index = 5
        if self.tab_group.button(realized_tab_index):
            self.tab_group.button(realized_tab_index).setChecked(True)
            self.stacked.setCurrentIndex(realized_tab_index)
        
        # Find and select the redemption in the tree
        if not self.realized_tab.find_and_select_redemption(redemption_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "This redemption is not currently visible in the Realized tab. "
                "It may be filtered out by date or site/user filters."
            )

    def view_realized_position(self, redemption_id):
        """Navigate to Realized tab and highlight the specified redemption."""
        # Switch to Realized tab (index 5)
        realized_tab_index = 5
        if self.tab_group.button(realized_tab_index):
            self.tab_group.button(realized_tab_index).setChecked(True)
            self.stacked.setCurrentIndex(realized_tab_index)
        
        # Find and select the redemption in the tree
        if not self.realized_tab.find_and_select_redemption(redemption_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "This redemption is not currently visible in the Realized tab. "
                "It may be filtered out by date or site/user filters."
            )

    def view_session_in_daily(self, session_id):
        """Navigate to Daily Sessions tab and highlight the specified session."""
        # Switch to Daily Sessions tab (index 3)
        daily_tab_index = 3
        if self.tab_group.button(daily_tab_index):
            self.tab_group.button(daily_tab_index).setChecked(True)
            self.stacked.setCurrentIndex(daily_tab_index)
        
        # Find and select the session in the tree
        if not self.daily_sessions_tab.find_and_select_session(session_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "This session is not currently visible in the Daily Sessions tab. "
                "It may be filtered out by date or site/user filters, or is still Active."
            )

    def open_redemption(self, redemption_id):
        target_index = self.stacked.indexOf(self.redemptions_tab)
        if target_index < 0:
            return
        self.stacked.setCurrentIndex(target_index)
        if not self.redemptions_tab.select_redemption_by_id(redemption_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "Redemption not visible with current filters.",
            )
            return
        self.redemptions_tab.view_redemption_by_id(redemption_id)

    def open_purchase(self, purchase_id):
        target_index = self.stacked.indexOf(self.purchases_tab)
        if target_index < 0:
            return
        self.stacked.setCurrentIndex(target_index)
        if not self.purchases_tab.select_purchase_by_id(purchase_id):
            QtWidgets.QMessageBox.information(
                self,
                "Not Found",
                "Purchase not visible with current filters.",
            )
            return
        self.purchases_tab.view_purchase_by_id(purchase_id)

    def edit_game_session(self, session_id):
        target_index = self.stacked.indexOf(self.game_sessions_tab)
        if target_index < 0:
            return
        self.stacked.setCurrentIndex(target_index)
        self.game_sessions_tab.edit_session_by_id(session_id)

    def delete_game_session(self, session_id):
        """Delete a game session by ID (called from DailySessionsTab)"""
        if hasattr(self, 'game_sessions_tab'):
            self.game_sessions_tab._delete_session_by_id(session_id)

    def _on_tab_clicked(self, button):
        tab_index = self.tab_group.id(button)
        if tab_index >= 0:
            self.stacked.setCurrentIndex(tab_index)

    def _sync_tab_selection(self, index):
        button = self.tab_group.button(index)
        if button:
            button.setChecked(True)
        self._update_tab_tip(index)

    def _update_tab_tip(self, index):
        label = ""
        if 0 <= index < len(self.tab_buttons):
            label = self.tab_buttons[index][1]
        self.tab_tip.setText(self.tab_descriptions.get(label, ""))

    def _apply_style(self):
        self.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

        # Get colors based on theme
        if self.current_theme == 'dark':
            colors = self._get_dark_theme_colors()
        else:
            colors = self._get_light_theme_colors()

        self.setStyleSheet(
            f"""
            QMainWindow {{ background: {colors['bg']}; }}
            QWidget {{ color: {colors['text']}; font-size: 12px; }}
            QDialog, QMessageBox {{ background: {colors['surface']}; }}
            QFrame#StatsBar {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
            }}
            QFrame#StatsBar QLabel {{
                color: {colors['text']};
            }}
            QLabel#SectionTitle {{ font-size: 14px; font-weight: 600; color: {colors['text']}; }}
            QLabel#SectionHeader {{ font-size: 13px; font-weight: 600; color: {colors['text_muted']}; }}

            #TabButton {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
                padding: 6px 14px;
                color: {colors['text_muted']};
            }}
            #TabButton:hover {{
                background: {colors['surface2']};
            }}
            #TabButton:checked {{
                background: {colors['accent']};
                color: white;
                border: 1px solid {colors['accent_hover']};
            }}

            QStackedWidget {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}

            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
                background: {colors['input_bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 26px;
            }}
            QLineEdit[invalid="true"], QTextEdit[invalid="true"], QPlainTextEdit[invalid="true"], QComboBox[invalid="true"] {{
                border: 1px solid #c0392b;
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 1px solid {colors['focus']};
            }}
            QComboBox {{
                padding-right: 30px;
            }}
            QComboBox::editable {{
                background: {colors['input_bg']};
                color: {colors['text']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid {colors['border']};
                background: {colors['surface2']};
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QComboBox::down-arrow {{
                image: url("icons/chevron-down.svg");
                width: 10px;
                height: 6px;
            }}
            QAbstractItemView,
            QListView,
            QComboBox QAbstractItemView {{
                background: {colors['input_bg']};
                color: {colors['text']};
                selection-background-color: {colors['selection']};
                selection-color: {colors['text']};
            }}
            QPlainTextEdit#NotesField {{
                min-height: 78px;
            }}
            QLabel#InfoField {{
                background: {colors['input_bg']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 26px;
            }}
            QLabel#InfoField[status="positive"] {{ color: #2e7d32; }}
            QLabel#InfoField[status="negative"] {{ color: #c0392b; }}
            QLabel#InfoField[status="neutral"] {{ color: {colors['text_muted']}; }}
            QLabel#HelperText {{ color: {colors['text_muted']}; font-size: 11px; }}
            QLabel#TabTip {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 10px;
                padding: 6px 12px;
                color: {colors['accent_hover']};
                font-weight: 500;
            }}
            QRadioButton[invalid="true"] {{ color: #c0392b; }}
            QMenu {{
                background: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
            }}
            QMenu::item:selected {{
                background: {colors['selection']};
            }}
            QCalendarWidget QWidget {{
                background: {colors['surface']};
            }}
            QCalendarWidget QToolButton {{
                background: {colors['surface2']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QCalendarWidget QMenu {{
                background: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
            }}
            QCalendarWidget QSpinBox {{
                background: {colors['input_bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 2px 6px;
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                background: {colors['input_bg']};
                color: {colors['text']};
                selection-background-color: {colors['selection']};
                selection-color: {colors['text']};
            }}
            QPushButton {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 26px;
            }}
            QPushButton:hover {{ background: {colors['surface2']}; }}
            QPushButton#PrimaryButton {{
                background: {colors['accent']};
                border: 1px solid {colors['accent_hover']};
                color: white;
            }}
            QPushButton#PrimaryButton:hover {{ background: {colors['accent_hover']}; }}
            QPushButton#MiniButton {{
                padding: 4px 10px;
                min-height: 20px;
            }}
            QToolButton#InfoButton {{
                background: {colors['surface2']};
                border: 1px solid {colors['border']};
                border-radius: 9px;
                min-width: 18px;
                min-height: 18px;
                padding: 0;
                font-weight: 600;
            }}
            QToolButton#InfoButton:hover {{ background: {colors['border']}; }}
            QCheckBox, QRadioButton {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {colors['focus']};
                border-radius: 4px;
                background: {colors['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background: {colors['accent']};
                border: 1px solid {colors['accent_hover']};
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {colors['focus']};
                border-radius: 8px;
                background: {colors['input_bg']};
            }}
            QRadioButton::indicator:checked {{
                background: {colors['accent']};
                border: 1px solid {colors['accent_hover']};
            }}

            QTableWidget {{
                background: {colors['surface']};
                gridline-color: {colors['border']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QTreeWidget, QTreeView {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QTreeWidget::item, QTreeView::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {colors['border']};
            }}
            QTreeWidget::item:selected, QTreeView::item:selected {{
                background: {colors['selection']};
            }}
            QHeaderView::section {{
                background: {colors['surface2']};
                border: 1px solid {colors['border']};
                padding: 6px;
                font-weight: 600;
            }}
            QTableWidget::item:selected {{
                background: {colors['selection']};
            }}
            QScrollBar:vertical {{
                background: {colors['surface']};
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['scrollbar']};
                min-height: 30px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                background: none;
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {colors['surface']};
                height: 12px;
                margin: 2px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['scrollbar']};
                min-width: 30px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                background: none;
                width: 0;
            }}
            
            QTabWidget::pane {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 16px;
                margin-right: 4px;
                color: {colors['text_muted']};
            }}
            QTabBar::tab:selected {{
                background: {colors['surface']};
                color: {colors['accent']};
                font-weight: 600;
                border-color: {colors['border']};
            }}
            QTabBar::tab:hover {{
                background: {colors['surface2']};
            }}
            
            /* Reports Tab Styles */
            QWidget#ReportsNav {{
                background: {colors['surface']};
                border-right: 1px solid {colors['border']};
            }}
            QListWidget#ReportsNavList {{
                background: {colors['surface']};
                border: none;
                font-size: 13px;
            }}
            QListWidget#ReportsNavList::item {{
                padding: 8px 12px;
                border-radius: 6px;
                margin: 2px 0;
            }}
            QListWidget#ReportsNavList::item:hover {{
                background: {colors['surface2']};
            }}
            QListWidget#ReportsNavList::item:selected {{
                background: {colors['selection']};
                color: {colors['accent']};
                font-weight: 500;
            }}
            QFrame#KPICard {{
                background: {colors['surface']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QLabel#KPILabel {{
                color: {colors['text_muted']};
                font-size: 11px;
                font-weight: 500;
            }}
            QLabel#KPIValue {{
                color: {colors['text']};
                font-size: 18px;
                font-weight: 600;
            }}
            """
        )

    def _get_light_theme_colors(self):
        """Get light theme color palette"""
        return {
            'bg': '#ffffff',  # blue-1 light
            'surface': '#f7f9ff',  # blue-2
            'surface2': '#edf2fe',  # blue-3
            'border': '#dfeaff',  # blue-6
            'input_bg': '#fdfdfe',  # blue-1
            'text': '#1e1f24',  # gray-12
            'text_muted': '#62636c',  # gray-11
            'accent': '#3d63dd',  # blue-9
            'accent_hover': '#3657c3',  # blue-10
            'selection': '#d0dfff',  # blue-4
            'focus': '#a6bff9',  # blue-7
            'scrollbar': '#b9bbc6',  # gray-9
        }

    def _get_dark_theme_colors(self):
        """Get dark theme color palette based on Radix UI colors"""
        return {
            'bg': '#111113',  # gray-1
            'surface': '#19191b',  # gray-2
            'surface2': '#222325',  # gray-3
            'border': '#292a2e',  # gray-4
            'input_bg': '#222325',  # gray-3
            'text': '#eeeef0',  # gray-12
            'text_muted': '#b2b3bd',  # gray-11
            'accent': '#3d63dd',  # blue-9
            'accent_hover': '#5480ff',  # blue-8 lighter
            'selection': '#172448',  # blue-3
            'focus': '#243974',  # blue-5
            'scrollbar': '#6c6e79',  # gray-9
        }

    def _load_theme_preference(self):
        """Load theme preference from database"""
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key = 'theme'")
            result = c.fetchone()
            conn.close()
            return result['value'] if result else 'light'
        except:
            return 'light'

    def _save_theme_preference(self, theme):
        """Save theme preference to database"""
        try:
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('theme', ?)", (theme,))
            conn.commit()
            conn.close()
            self.current_theme = theme
            self._apply_style()
        except Exception as e:
            print(f"Failed to save theme preference: {e}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
