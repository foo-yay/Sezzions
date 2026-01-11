#!/usr/bin/env python3
"""
qt_app.py - PySide6/Qt UI for Session
Run: python3 qt_app.py
"""
import sys
import re
from datetime import date, datetime, timedelta
from PySide6 import QtCore, QtGui, QtWidgets

from database import Database
from business_logic import FIFOCalculator, SessionManager


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
        self.card_combo.addItems(card_names)
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
        if not user_name:
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            # Clear cashback fields when user is cleared
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()
            return
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE name = ?", (user_name,))
        user_row = c.fetchone()
        if not user_row:
            conn.close()
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            # Clear cashback fields when user not found
            self.cashback_rate_label.setText("—")
            self.cashback_edit.clear()
            return
        user_id = user_row["id"]
        c.execute("SELECT name FROM cards WHERE user_id = ? AND active = 1 ORDER BY name", (user_id,))
        cards = [r["name"] for r in c.fetchall()]
        conn.close()
        preserve = getattr(self, "_preserve_card_selection", False)
        current = self.card_combo.currentText().strip()
        self.card_combo.blockSignals(True)
        self.card_combo.clear()
        self.card_combo.addItems(cards)
        if preserve and current in cards:
            self.card_combo.setCurrentText(current)
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

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (card_name,))
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

        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (card_name,))
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
        valid_cards = {
            self.card_combo.itemText(i).lower()
            for i in range(self.card_combo.count())
            if self.card_combo.itemText(i)
        }
        if not card_text or card_text.lower() not in valid_cards:
            self._set_invalid(self.card_combo, "Select a valid Card for the chosen User.")
        else:
            self._set_valid(self.card_combo)

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
        self._preserve_card_selection = True
        self.user_combo.setCurrentText(self.purchase["user_name"])
        # Trigger user change to filter cards
        self._on_user_change(self.purchase["user_name"])
        self._preserve_card_selection = False

        self.site_combo.setCurrentText(self.purchase["site_name"])
        self.card_combo.setCurrentText(self.purchase["card_name"])
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
            c.execute("SELECT cashback_rate FROM cards WHERE name = ?", (card_name,))
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
    def __init__(self, purchase, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.purchase = purchase
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Purchase")
        self.resize(600, 560)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
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
        row = add_row("Date", format_date(purchase["purchase_date"]), row)
        row = add_row("Time", format_time(purchase["purchase_time"]), row)
        row = add_row("User", purchase["user_name"] or "—", row)
        row = add_row("Site", purchase["site_name"] or "—", row)
        row = add_row("Card", purchase["card_name"] or "—", row)
        row = add_row("Amount", format_currency(purchase["amount"]), row)
        row = add_row("SC Received", f"{float(purchase['sc_received'] or 0):.2f}", row)
        row = add_row("Starting SC", f"{float(purchase['starting_sc_balance'] or 0):.2f}", row)
        row = add_row("Cashback Earned", format_currency(purchase["cashback_earned"] or 0.0), row)
        row = add_row("Remaining", format_currency(purchase["remaining_amount"]), row)

        notes_label = QtWidgets.QLabel("Notes")
        notes_value = purchase["notes"] or ""
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
        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.addItems(method_names)
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}

        self.amount_edit = QtWidgets.QLineEdit()
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
        form.addWidget(QtWidgets.QLabel("Method"), 4, 0)
        form.addWidget(self.method_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Amount"), 5, 0)
        form.addWidget(self.amount_edit, 5, 1)
        form.addWidget(QtWidgets.QLabel("Receipt Date"), 6, 0)
        form.addLayout(receipt_row, 6, 1)
        form.addWidget(QtWidgets.QLabel("Redemption Type"), 7, 0)
        form.addLayout(type_row, 7, 1)
        form.addWidget(QtWidgets.QLabel("Flags"), 8, 0)
        form.addLayout(checkbox_row, 8, 1)
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
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.method_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
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
            self.method_combo.clear()
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
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
            return
        user_id = user_row["id"]
        c.execute(
            """
            SELECT name FROM redemption_methods
            WHERE active = 1 AND (user_id IS NULL OR user_id = ?)
            ORDER BY name
            """,
            (user_id,),
        )
        methods = [r["name"] for r in c.fetchall()]
        conn.close()
        preserve = getattr(self, "_preserve_method_selection", False)
        current = self.method_combo.currentText().strip()
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        self.method_combo.addItems(methods)
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
        self._preserve_method_selection = True
        self.user_combo.setCurrentText(self.redemption["user_name"])
        self._preserve_method_selection = False
        self.site_combo.setCurrentText(self.redemption["site_name"])
        if self.redemption["method_name"]:
            self.method_combo.setCurrentText(self.redemption["method_name"])
        else:
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
        self.amount_edit.setText(str(self.redemption["amount"]))
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
        for combo in (self.user_combo, self.site_combo, self.method_combo):
            combo.setCurrentIndex(-1)
            combo.setEditText("")
        self.amount_edit.clear()
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
            "receipt_date": receipt_date.strftime("%Y-%m-%d") if receipt_date else None,
            "more_remaining": self.partial_radio.isChecked(),
            "processed": self.processed_check.isChecked(),
            "notes": notes,
        }, None


class RedemptionViewDialog(QtWidgets.QDialog):
    def __init__(
        self, redemption, allocations=None, parent=None, on_edit=None, on_open=None, on_open_purchase=None, on_delete=None
    ):
        super().__init__(parent)
        self.redemption = redemption
        self.allocations = allocations or []
        self._on_edit = on_edit
        self._on_open = on_open
        self.on_open_purchase = on_open_purchase
        self._on_delete = on_delete
        self.setWindowTitle("View Redemption")
        self.resize(600, 620)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

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

        amount = float(redemption["amount"] or 0.0)
        method_name = redemption["method_name"] or ""
        if amount == 0:
            method_name = "Loss"

        receipt_date = redemption["receipt_date"] or ""
        if amount == 0:
            receipt_display = "N/A"
        elif receipt_date:
            receipt_display = format_date(receipt_date)
        else:
            receipt_display = "PENDING"

        redemption_type = "Partial" if redemption["more_remaining"] else "Full"
        processed_display = "Yes" if redemption["processed"] else "No"

        row = 0
        row = add_row("Date", format_date(redemption["redemption_date"]), row)
        row = add_row("Time", format_time(redemption["redemption_time"]), row)
        row = add_row("User", redemption["user_name"] or "—", row)
        row = add_row("Site", redemption["site_name"] or "—", row)
        row = add_row("Amount", format_currency(amount), row)
        row = add_row("Receipt Date", receipt_display, row)
        row = add_row("Method", method_name or "—", row)
        row = add_row("Redemption Type", redemption_type, row)
        row = add_row("Processed", processed_display, row)

        notes_label = QtWidgets.QLabel("Notes")
        notes_value = redemption["notes"] or ""
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
        layout.addSpacing(8)

        allocations_group = QtWidgets.QGroupBox("Purchase Allocations")
        allocations_layout = QtWidgets.QVBoxLayout(allocations_group)
        allocations_layout.setContentsMargins(8, 10, 8, 8)

        if not self.allocations:
            note = QtWidgets.QLabel(
                "No purchase allocation info available. Run FIFO rebuilds to backfill allocations."
            )
            note.setWordWrap(True)
            allocations_layout.addWidget(note)
        else:
            self.allocations_table = QtWidgets.QTableWidget(0, 6)
            self.allocations_table.setHorizontalHeaderLabels(
                ["Purchase Date", "Amount", "SC", "Allocated", "Remaining", "View"]
            )
            self.allocations_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.allocations_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.allocations_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.allocations_table.setAlternatingRowColors(True)
            self.allocations_table.setMinimumSize(0, 0)
            self.allocations_table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            self.allocations_table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
            self.allocations_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            header = self.allocations_table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            header.setMinimumSectionSize(40)
            self.allocations_table.verticalHeader().setVisible(False)
            self.allocations_table.setColumnWidth(0, 160)
            self.allocations_table.setColumnWidth(1, 90)
            self.allocations_table.setColumnWidth(2, 80)
            self.allocations_table.setColumnWidth(3, 90)
            self.allocations_table.setColumnWidth(4, 90)
            self.allocations_table.setColumnWidth(5, 120)
            row_height = self.allocations_table.verticalHeader().defaultSectionSize()
            min_height = self.allocations_table.horizontalHeader().height() + row_height * 3 + 10
            self.allocations_table.setMinimumHeight(min_height)
            allocations_layout.addWidget(self.allocations_table)
            self._populate_allocations()

        layout.addWidget(allocations_group, 1)

        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
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
        if self._on_open:
            open_btn.clicked.connect(self._handle_open)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)

    def _handle_open(self):
        if self._on_open:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_open)

    def _handle_delete(self):
        if self._on_delete:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_delete)

    def _populate_allocations(self):
        self.allocations_table.setRowCount(len(self.allocations))
        for row_idx, row in enumerate(self.allocations):
            purchase_time = row.get("purchase_time") or "00:00:00"
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

            view_btn = QtWidgets.QPushButton("View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(120)
            view_btn.clicked.connect(
                lambda _checked=False, pid=row["purchase_id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QHBoxLayout(view_container)
            view_layout.setContentsMargins(0, 0, 0, 0)
            view_layout.addStretch(1)
            view_layout.addWidget(view_btn)
            view_layout.addStretch(1)
            self.allocations_table.setCellWidget(row_idx, 5, view_container)

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))


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
        self.game_name_combo.addItems([""])

        self.game_helper = QtWidgets.QLabel("Game Name requires a Game Type.")
        self.game_helper.setObjectName("HelperText")
        self.game_helper.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        game_grid.addWidget(QtWidgets.QLabel("Game Type"), 0, 0)
        game_grid.addWidget(self.game_type_combo, 0, 1)
        game_grid.addWidget(QtWidgets.QLabel("Game Name"), 0, 2)
        game_grid.addWidget(self.game_name_combo, 0, 3)
        game_grid.addWidget(self.game_helper, 1, 0, 1, 4)
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
        type_key = None
        if game_type:
            for key in self.game_names_by_type:
                if key.lower() == game_type.lower():
                    type_key = key
                    break
            names = list(self.game_names_by_type.get(type_key, [])) if type_key else []
        else:
            names = []
        current = self.game_name_combo.currentText().strip()
        if "" not in names:
            names.insert(0, "")
        self.game_name_combo.blockSignals(True)
        self.game_name_combo.clear()
        self.game_name_combo.addItems(names)
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
        self.game_name_combo.addItems([""])

        self.game_helper = QtWidgets.QLabel("Game Name requires a Game Type.")
        self.game_helper.setObjectName("HelperText")
        self.game_helper.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        game_grid.addWidget(QtWidgets.QLabel("Game Type"), 0, 0)
        game_grid.addWidget(self.game_type_combo, 0, 1)
        game_grid.addWidget(QtWidgets.QLabel("Game Name"), 0, 2)
        game_grid.addWidget(self.game_name_combo, 0, 3)
        game_grid.addWidget(self.game_helper, 1, 0, 1, 4)
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
        balance_grid.addWidget(self.balance_label, 2, 0)
        balance_grid.addWidget(self.balance_value, 2, 1, 1, 3)
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
        type_key = None
        if game_type:
            for key in self.game_names_by_type:
                if key.lower() == game_type.lower():
                    type_key = key
                    break
            names = list(self.game_names_by_type.get(type_key, [])) if type_key else []
        else:
            names = []
        current = self.game_name_combo.currentText().strip()
        if "" not in names:
            names.insert(0, "")
        self.game_name_combo.blockSignals(True)
        self.game_name_combo.clear()
        self.game_name_combo.addItems(names)
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
        self.notes_edit.setPlainText(self.session["notes"] or "")
        self._update_balance_label()

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

        wager_amount = None
        if self.session:
            try:
                # Handle both dict and sqlite3.Row objects
                wager_val = self.session["wager_amount"] if "wager_amount" in self.session.keys() else None
                if wager_val is not None:
                    wager_amount = float(wager_val or 0.0)
            except (KeyError, TypeError):
                pass

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
    def __init__(self, session, parent=None, on_open_session=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.session = session
        self._on_open_session = on_open_session
        self._on_edit = on_edit
        self._on_delete = on_delete
        self.setWindowTitle("View Game Session")
        self.resize(700, 520)

        layout = QtWidgets.QVBoxLayout(self)
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

        def format_date(value):
            if not value:
                return "—"
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return value

        def format_time(value):
            return value[:5] if value else "—"

        def format_dt(date_value, time_value):
            if not date_value and not time_value:
                return "—"
            date_part = format_date(date_value)
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

        wager_display = format_currency(session["wager_amount"]) if session["wager_amount"] else "—"
        rtp_display = f"{float(session['rtp']):.2f}%" if session["rtp"] is not None else "—"
        start_total = session["starting_sc_balance"]
        end_total = session["ending_sc_balance"]
        start_redeem = (
            session["starting_redeemable_sc"]
            if session["starting_redeemable_sc"] is not None
            else session["starting_sc_balance"]
        )
        end_redeem = (
            session["ending_redeemable_sc"]
            if session["ending_redeemable_sc"] is not None
            else session["ending_sc_balance"]
        )
        delta_total = session["delta_total"]
        if delta_total is None and start_total is not None and end_total is not None:
            delta_total = float(end_total or 0) - float(start_total or 0)
        delta_redeem = session["delta_redeem"]
        if delta_redeem is None and start_redeem is not None and end_redeem is not None:
            delta_redeem = float(end_redeem or 0) - float(start_redeem or 0)
        basis_val = (
            session["basis_consumed"]
            if session["basis_consumed"] is not None
            else session["session_basis"]
        )
        net_val = session["net_taxable_pl"]
        if net_val is None:
            net_val = session["total_taxable"] if session["total_taxable"] is not None else 0.0
        net_display = f"+${float(net_val):.2f}" if float(net_val) >= 0 else f"${float(net_val):.2f}"

        session_group, session_grid = build_group("Session")
        add_pair(
            session_grid,
            0,
            0,
            "Start",
            format_dt(session["session_date"], session["start_time"]),
        )
        add_pair(
            session_grid,
            0,
            1,
            "End",
            format_dt(session["end_date"], session["end_time"]),
        )
        add_pair(session_grid, 1, 0, "Site", session["site_name"] or "—")
        add_pair(session_grid, 1, 1, "User", session["user_name"] or "—")
        add_pair(session_grid, 2, 0, "Status", session["status"] or "Active")
        layout.addWidget(session_group)

        game_group, game_grid = build_group("Game")
        add_pair(game_grid, 0, 0, "Game Type", session["game_type"] or "—")
        add_pair(game_grid, 0, 1, "Game Name", session["game_name"] or "—")
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
        notes_value = session["notes"] or ""
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
        layout.addSpacing(4)

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
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
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
        if self._on_open_session:
            open_btn.clicked.connect(self._handle_open_session)
        close_btn.clicked.connect(self.accept)

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
    def __init__(self, db, session_mgr, on_data_changed=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
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
            on_delete=lambda: self._delete_purchase_by_id(purchase_id)
        )
        dialog.exec()

    def _save_from_dialog(self, dialog, purchase_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return
        ok, message_or_id = self._save_purchase_record(data, purchase_id)
        if not ok:
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
        if purchase_id is None and new_purchase_id:
            self._prompt_start_session(new_purchase_id, message)
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
        dialog.time_edit.setText(dialog._format_time_for_input(session_time))
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

    def _save_purchase_record(self, data, purchase_id):
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

        c.execute("SELECT id FROM cards WHERE name = ? AND user_id = ?", (card_name, user_id))
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
                "SELECT amount, remaining_amount, site_id, user_id FROM purchases WHERE id = ?",
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
            consumed = old_amount - old_remaining

            if consumed > 0:
                if old_amount != amount:
                    conn.close()
                    return (
                        False,
                        f"Cannot change amount - ${consumed:.2f} has been used for redemptions.",
                    )
                if old_site_id != site_id or old_user_id != user_id:
                    conn.close()
                    return (
                        False,
                        f"Cannot change site or user - ${consumed:.2f} has been used for redemptions.",
                    )

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

            recalc_count = self.session_mgr.auto_recalculate_affected_sessions(
                site_id, user_id, pdate, ptime
            )
            message = "Purchase updated"
            if recalc_count > 0:
                message += f" (recalculated {recalc_count} affected session{'s' if recalc_count != 1 else ''})"
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

        try:
            self.db.log_audit(
                "INSERT",
                "purchases",
                purchase_id,
                f"{user_name} - {site_name} - ${amount:.2f}",
                user_name,
            )
        except Exception:
            pass

        session_id = self.session_mgr.get_or_create_site_session(site_id, user_id, pdate)
        self.session_mgr.add_purchase_to_session(session_id, amount)
        recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, pdate, ptime)
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

    def _needs_purchase_recalc(self, site_id, user_id, purchase_date, purchase_time):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT 1
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
            LIMIT 1
            """,
            (site_id, user_id, purchase_date, purchase_date, purchase_time),
        )
        if c.fetchone():
            conn.close()
            return True
        c.execute(
            """
            SELECT 1
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (COALESCE(end_date, session_date) > ? OR (COALESCE(end_date, session_date) = ? AND COALESCE(end_time,'00:00:00') >= ?))
            LIMIT 1
            """,
            (site_id, user_id, purchase_date, purchase_date, purchase_time),
        )
        has_sessions = c.fetchone() is not None
        conn.close()
        return has_sessions

    def view_purchase_by_id(self, purchase_id):
        purchase = self._fetch_purchase(purchase_id)
        if not purchase:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected purchase was not found.")
            return
        dialog = PurchaseViewDialog(
            purchase,
            parent=self,
            on_edit=lambda: self.edit_purchase_by_id(purchase_id),
            on_delete=lambda: self._delete_purchase_by_id(purchase_id)
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
            try:
                self.db.log_audit("DELETE", "purchases", purchase_id, f"Deleted ${amount:.2f}", None)
            except Exception:
                pass

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

        conn.commit()
        conn.close()

        total_recalc = 0
        for (site_id, user_id), (pdate, ptime) in affected.items():
            if not self._needs_purchase_recalc(site_id, user_id, pdate, ptime):
                continue
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(
                site_id, user_id, pdate, ptime
            )

        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()

        if error_messages:
            message = f"Deleted {deleted_count} purchase(s)."
            if total_recalc > 0:
                message += f" Recalculated {total_recalc} session{'s' if total_recalc != 1 else ''}."
            message += "\n\nErrors:\n" + "\n".join(error_messages)
            QtWidgets.QMessageBox.warning(self, "Partial Success", message)
        else:
            message = f"Deleted {deleted_count} purchase{'s' if deleted_count != 1 else ''}"
            if total_recalc > 0:
                message += f" (recalculated {total_recalc} affected session{'s' if total_recalc != 1 else ''})"
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
            on_delete=lambda: self._delete_redemption_by_id(redemption_id),
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
            SELECT r.*, s.name as site_name, rm.name as method_name, u.name as user_name
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
                       ts.cost_basis
                FROM redemptions r
                LEFT JOIN tax_sessions ts ON ts.redemption_id = r.id
                WHERE r.id = ?
                """,
                (redemption_id,),
            )
            old_data = c.fetchone()
            old_amount = float(old_data["amount"]) if old_data else 0.0
            old_session_id = old_data["site_session_id"] if old_data else None
            old_site_id = old_data["site_id"] if old_data else None
            old_user_id = old_data["user_id"] if old_data else None
            old_cost_basis = float(old_data["cost_basis"] or 0.0) if old_data else 0.0

            c.execute(
                """
                UPDATE redemptions
                SET site_session_id=?, site_id=?, redemption_date=?, redemption_time=?, amount=?, receipt_date=?,
                    redemption_method_id=?, more_remaining=?, user_id=?, processed=?, notes=?
                WHERE id=?
                """,
                (
                    session_id,
                    site_id,
                    rdate,
                    rtime,
                    amount,
                    receipt_date,
                    method_id,
                    1 if more_remaining else 0,
                    user_id,
                    processed,
                    notes,
                    redemption_id,
                ),
            )

            if old_session_id:
                c.execute(
                    "UPDATE site_sessions SET total_redeemed = total_redeemed - ? WHERE id = ?",
                    (old_amount, old_session_id),
                )

            if session_id and session_id != old_session_id:
                c.execute(
                    "UPDATE site_sessions SET total_redeemed = total_redeemed + ? WHERE id = ?",
                    (amount, session_id),
                )

            c.execute("DELETE FROM tax_sessions WHERE redemption_id = ?", (redemption_id,))
            conn.commit()
            conn.close()

            if old_cost_basis > 0 and old_site_id and old_user_id:
                self.session_mgr.fifo_calc.reverse_cost_basis(old_site_id, old_user_id, old_cost_basis)

            self.session_mgr.process_redemption(
                redemption_id, site_id, amount, rdate, rtime, user_id, False, more_remaining, is_edit=True
            )

            if self._has_subsequent and self._subsequent_ids:
                self._recalculate_subsequent_redemptions(self._subsequent_ids, site_id, user_id)

            pairs_to_recalc = {(site_id, user_id)}
            if old_site_id and old_user_id:
                pairs_to_recalc.add((old_site_id, old_user_id))
            total_recalc = 0
            for sid, uid in pairs_to_recalc:
                total_recalc += self.session_mgr.auto_recalculate_affected_sessions(sid, uid, rdate, rtime)

            message = "Redemption updated"
            if self._has_subsequent:
                message += f" (recalculated {len(self._subsequent_ids)} subsequent redemptions)"
            if total_recalc:
                message += f" (recalculated {total_recalc} sessions)"
            return True, message

        c.execute(
            """
            INSERT INTO redemptions
            (site_session_id, site_id, redemption_date, redemption_time, amount, receipt_date,
             redemption_method_id, more_remaining, user_id, processed, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                site_id,
                rdate,
                rtime,
                amount,
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

        self.session_mgr.process_redemption(rid, site_id, amount, rdate, rtime, user_id, False, more_remaining)
        recalc_count = self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, rdate, rtime)
        message = "Redemption logged"
        if recalc_count:
            message += f" (recalculated {recalc_count} sessions)"
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
            c.execute("SELECT cost_basis FROM tax_sessions WHERE redemption_id = ?", (rid,))
            old_tax = c.fetchone()
            old_cost_basis = float(old_tax["cost_basis"]) if old_tax and old_tax["cost_basis"] else 0.0
            c.execute("DELETE FROM tax_sessions WHERE redemption_id = ?", (rid,))
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
            on_delete=lambda: self._delete_redemption_by_id(redemption_id),
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

        deleted_count = 0
        error_messages = []
        pairs_to_recalc = set()

        for redemption_id in selected_ids:
            conn = self.db.get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT site_id, user_id, redemption_date, redemption_time FROM redemptions WHERE id = ?",
                (redemption_id,),
            )
            row = c.fetchone()
            conn.close()

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
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, rdate, rtime)

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
                message += f" (recalculated {total_recalc} sessions)"
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
                try:
                    self.db.log_audit(
                        "DELETE",
                        "expenses",
                        expense_id,
                        "Expense deleted",
                        None,
                    )
                except Exception:
                    pass
        conn.commit()
        conn.close()

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
            self.db.log_audit(action, "expenses", expense_id, f"{data['vendor']} - {format_currency(data['amount'])}", data["user_name"] or None)
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
    def __init__(self, db, session_mgr, on_data_changed=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
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
        session = self._fetch_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return
        dialog = GameSessionViewDialog(
            session, parent=self, on_edit=lambda: self.edit_session_by_id(session_id), on_delete=lambda: self._delete_session_by_id(session_id)
        )
        dialog.exec()

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

            dialog.accept()
            self.load_data()
            if self.on_data_changed:
                self.on_data_changed()
            QtCore.QTimer.singleShot(
                0, lambda: QtWidgets.QMessageBox.information(self, "Success", "Session updated")
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

        pairs = {
            (new_site_id, new_user_id, data["session_date"], data["start_time"]),
            (old_site_id, old_user_id, old_date, old_time),
        }
        total_recalc = 0
        for site_id, user_id, sdate, stime in pairs:
            total_recalc += self.session_mgr.auto_recalculate_affected_sessions(site_id, user_id, sdate, stime)

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
        dialog = GameSessionViewDialog(
            session, parent=self, on_edit=lambda: self.edit_session_by_id(session_id), on_delete=lambda: self._delete_session_by_id(session_id)
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
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.on_open_session = on_open_session
        self.on_edit_session = on_edit_session
        self.on_delete_session = on_delete_session
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
            purchase_time = row.get("purchase_time") or "00:00:00"
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
            INSERT INTO tax_sessions
            (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
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
        self.setWindowTitle("Realized Position")
        self.resize(720, 520)

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

        amount = float(position["redemption_amount"] or 0.0)
        position_group, position_grid = build_group("Position")
        add_pair(position_grid, 0, 0, "Date", format_date(position["session_date"]))
        add_pair(position_grid, 0, 1, "User", position["user_name"] or "—")
        add_pair(position_grid, 1, 0, "Site", position["site_name"] or "—")
        layout.addWidget(position_group)

        results_group, results_grid = build_group("Results")
        add_pair(results_grid, 0, 0, "Redemption Amount", format_currency(amount))
        add_pair(results_grid, 0, 1, "Cost Basis", format_currency(position["cost_basis"]))
        add_pair(results_grid, 1, 0, "Net P/L", self._format_signed_currency(position["net_pl"]))
        layout.addWidget(results_group)

        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        notes_value = position["redemption_notes"] or ""
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

        allocations_group = QtWidgets.QGroupBox("Purchase Allocations")
        allocations_layout = QtWidgets.QVBoxLayout(allocations_group)
        allocations_layout.setContentsMargins(8, 10, 8, 8)

        if not self.allocations:
            note = QtWidgets.QLabel(
                "No purchase allocation info available. Run FIFO rebuilds to backfill allocations."
            )
            note.setWordWrap(True)
            allocations_layout.addWidget(note)
        else:
            self.table = QtWidgets.QTableWidget(0, 6)
            self.table.setHorizontalHeaderLabels(
                ["Purchase Date", "Amount", "SC", "Allocated", "Remaining", "View"]
            )
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.table.setAlternatingRowColors(True)
            self.table.setMinimumSize(0, 0)
            self.table.setSizePolicy(
                QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
            )
            self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
            self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            header = self.table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(5, QtWidgets.QHeaderView.Fixed)
            header.setMinimumSectionSize(40)
            self.table.verticalHeader().setVisible(False)
            self.table.setColumnWidth(5, 120)
            row_height = self.table.verticalHeader().defaultSectionSize()
            min_height = self.table.horizontalHeader().height() + row_height * 3 + 10
            self.table.setMinimumHeight(min_height)
            allocations_layout.addWidget(self.table)
            self._populate_allocations()

        layout.addWidget(allocations_group, 1)

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

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _populate_allocations(self):
        self.table.setRowCount(len(self.allocations))
        for row_idx, row in enumerate(self.allocations):
            purchase_time = row.get("purchase_time") or "00:00:00"
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
                self.table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(120)
            view_btn.clicked.connect(
                lambda _checked=False, pid=row["purchase_id"]: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QHBoxLayout(view_container)
            view_layout.setContentsMargins(0, 0, 0, 0)
            view_layout.addStretch(1)
            view_layout.addWidget(view_btn)
            view_layout.addStretch(1)
            self.table.setCellWidget(row_idx, 5, view_container)

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

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
        self.tree.setColumnWidth(5, 110)
        self.tree.setColumnWidth(6, 200)
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
            c.execute("PRAGMA table_info(tax_sessions)")
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
            return self._format_signed_currency(tx["net_pl"])
        if col_index == 6:
            return tx["notes"] or ""
        return ""

    def _align_numeric(self, item):
        for col in (4, 5):
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
        notes_select = "ts.notes as session_notes" if self.has_tax_session_notes else "NULL as session_notes"
        query = f"""
            SELECT
                ts.id as tax_session_id,
                ts.session_date,
                ts.redemption_id as redemption_id,
                ts.cost_basis,
                ts.net_pl,
                ts.site_id,
                s.name as site_name,
                ts.user_id,
                u.name as user_name,
                r.amount as redemption_amount,
                r.is_free_sc,
                r.notes as redemption_notes,
                {notes_select}
            FROM tax_sessions ts
            JOIN sites s ON ts.site_id = s.id
            JOIN users u ON ts.user_id = u.id
            LEFT JOIN redemptions r ON ts.redemption_id = r.id
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
            conditions.append("ts.session_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("ts.session_date <= ?")
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY ts.session_date DESC, s.name ASC, u.name ASC, ts.id ASC"
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
                user_net = 0.0
                user_transactions = 0
                for site_id in sorted(
                    sites_map.keys(),
                    key=lambda sid: sites_map[sid][0]["site_name"].lower(),
                ):
                    txs = sites_map[site_id]
                    total_cost = sum(tx["cost_basis"] for tx in txs)
                    total_net = sum(tx["net_pl"] for tx in txs)
                    transaction_count = len(txs)
                    site_groups.append(
                        {
                            "site_id": site_id,
                            "site_name": txs[0]["site_name"],
                            "total_cost": total_cost,
                            "total_net": total_net,
                            "transaction_count": transaction_count,
                            "transactions": txs,
                        }
                    )
                    user_cost += total_cost
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
                        "total_net": user_net,
                        "transaction_count": user_transactions,
                        "site_count": len(site_groups),
                        "sites": site_groups,
                    }
                )
                date_cost += user_cost
                date_net += user_net

            date_notes = notes_by_date.get(session_date, "")
            if date_notes:
                notes_count += 1
            data.append(
                {
                    "date": session_date,
                    "date_cost": date_cost,
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
                return item["date_net"]
            if self.sort_column == 6:
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
                        tx_values = [
                            "",
                            "",
                            "",
                            transaction_display,
                            self._format_currency_or_dash(tx["cost_basis"]),
                            self._format_signed_currency(tx["net_pl"]),
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
                        self._apply_status_color(tx_item, tx["net_pl"])
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
                ts.id as tax_session_id,
                ts.session_date,
                ts.cost_basis,
                ts.net_pl,
                ts.redemption_id,
                r.amount as redemption_amount,
                r.notes as redemption_notes,
                s.name as site_name,
                u.name as user_name
            FROM tax_sessions ts
            JOIN redemptions r ON ts.redemption_id = r.id
            JOIN sites s ON ts.site_id = s.id
            JOIN users u ON ts.user_id = u.id
            WHERE ts.id = ?
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
        form.addWidget(QtWidgets.QLabel("Cashback %"), 1, 2)
        form.addWidget(self.cashback_edit, 1, 3)
        form.addWidget(QtWidgets.QLabel("Notes"), 2, 0, QtCore.Qt.AlignTop)
        form.addWidget(self.notes_edit, 2, 1, 1, 3)
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
            f"This will recalculate cashback for {count} purchase(s) using the new rate of {new_cashback_rate:.2f}%.\n\n"
            f"This action cannot be undone.\n\n"
            f"Continue?",
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

        # Cashback % field
        cashback_label = QtWidgets.QLabel("Cashback %")
        cashback_value = QtWidgets.QLabel(f"{float(card['cashback_rate'] or 0):.2f}")
        cashback_value.setObjectName("InfoField")
        cashback_value.setMaximumWidth(80)
        form.addWidget(cashback_label, 1, 2)
        form.addWidget(cashback_value, 1, 3)

        # Notes field
        notes_value = card["notes"] or ""
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
        form.addWidget(QtWidgets.QLabel("User"), 1, 0)
        form.addWidget(self.user_combo, 1, 1, 1, 3)
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
        self.user_combo.currentTextChanged.connect(self._validate_inline)

        if method:
            self.name_edit.setText(method["name"])
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

        # User field
        user_label = QtWidgets.QLabel("User")
        user_value = QtWidgets.QLabel(method["user_name"] or "—")
        user_value.setObjectName("InfoField")
        form.addWidget(user_label, 1, 0)
        form.addWidget(user_value, 1, 1, 1, 3)

        # Notes field
        notes_value = method["notes"] or ""
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

        # RTP % field
        rtp_label = QtWidgets.QLabel("RTP %")
        rtp_value = QtWidgets.QLabel(f"{float(game['rtp']):.2f}" if game["rtp"] is not None else "—")
        rtp_value.setObjectName("InfoField")
        rtp_value.setMaximumWidth(80)
        form.addWidget(rtp_label, 1, 2)
        form.addWidget(rtp_value, 1, 3)

        # Notes field
        notes_value = game["notes"] or ""
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
            ("tax sessions", "SELECT COUNT(*) as cnt FROM tax_sessions WHERE user_id = ?"),
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
            ("tax sessions", "SELECT COUNT(*) as cnt FROM tax_sessions WHERE site_id = ?"),
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
            ["Name", "Cashback %", "User", "Active", "Notes"],
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
            SELECT cards.id, cards.name, cards.cashback_rate, cards.active, cards.notes,
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
            SELECT cards.id, cards.name, cards.cashback_rate, cards.active, cards.notes,
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
        header.resizeSection(0, 240)  # Name column - 2x default width
        header.resizeSection(1, 120)  # Cashback %
        header.resizeSection(2, 120)  # User
        header.resizeSection(3, 80)   # Active

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
                INSERT INTO cards (name, cashback_rate, user_id, notes, active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data["name"], data["cashback_rate"], user_id, data["notes"], data["active"]),
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
                SET name = ?, cashback_rate = ?, user_id = ?, notes = ?, active = ?
                WHERE id = ?
                """,
                (data["name"], data["cashback_rate"], user_id, data["notes"], data["active"], record_id),
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
            ["Name", "User", "Active", "Notes"],
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
            SELECT rm.id, rm.name, rm.active, rm.notes, u.name as user_name
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
            SELECT rm.id, rm.name, rm.active, rm.notes, u.name as user_name
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
        header.resizeSection(0, 240)  # Name column - 2x default width
        header.resizeSection(1, 120)  # User
        header.resizeSection(2, 80)   # Active

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
                INSERT INTO redemption_methods (name, user_id, notes, active)
                VALUES (?, ?, ?, ?)
                """,
                (data["name"], user_id, data["notes"], data["active"]),
            )
            conn.commit()
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", str(exc))
        finally:
            conn.close()
        self.load_data()

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
                SET name = ?, user_id = ?, notes = ?, active = ?
                WHERE id = ?
                """,
                (data["name"], user_id, data["notes"], data["active"], record_id),
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
            ["Name", "Game Type", "RTP", "Active", "Notes"],
            "Search games...",
            "Add Game",
            "View Game",
            "Edit Game",
            "Delete Game",
            "game",
            "games",
            parent=parent,
        )
        self.numeric_cols = {2}
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
            SELECT g.id, g.name, g.rtp, g.notes, g.active, gt.name as type_name
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
            SELECT g.id, g.name, g.rtp, g.notes, g.active, gt.name as type_name
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
    def __init__(self, db, session_mgr, main_window, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.main_window = main_window

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

    # CSV Upload Methods (Placeholders for now)
    def _upload_purchases(self):
        self._show_not_implemented("Upload Purchases CSV")

    def _upload_sessions(self):
        self._show_not_implemented("Upload Sessions CSV")

    def _upload_redemptions(self):
        self._show_not_implemented("Upload Redemptions CSV")

    def _upload_expenses(self):
        self._show_not_implemented("Upload Expenses CSV")

    def _upload_users(self):
        self._show_not_implemented("Upload Users CSV")

    def _upload_sites(self):
        self._show_not_implemented("Upload Sites CSV")

    def _upload_cards(self):
        self._show_not_implemented("Upload Cards CSV")

    def _upload_methods(self):
        self._show_not_implemented("Upload Redemption Methods CSV")

    def _upload_game_types(self):
        self._show_not_implemented("Upload Game Types CSV")

    def _upload_games(self):
        self._show_not_implemented("Upload Games CSV")

    # CSV Template Download Methods
    def _download_template_purchases(self):
        self._download_template(
            "purchases",
            ["Date", "Time", "Site", "User", "Amount", "SC Received", "Starting SC", "Card", "Notes"],
            "purchases_template.csv"
        )

    def _download_template_sessions(self):
        self._download_template(
            "sessions",
            ["Date", "Start Time", "End Time", "Site", "User", "Game Type", "Game Name",
             "Starting Total SC", "Starting Redeemable", "Ending Total SC", "Ending Redeemable",
             "Wager Amount", "Notes"],
            "sessions_template.csv"
        )

    def _download_template_redemptions(self):
        self._download_template(
            "redemptions",
            ["Date", "Time", "Site", "User", "Amount", "Method", "Notes"],
            "redemptions_template.csv"
        )

    def _download_template_expenses(self):
        self._download_template(
            "expenses",
            ["Date", "Category", "Vendor", "User", "Amount", "Description"],
            "expenses_template.csv"
        )

    def _download_template_users(self):
        self._download_template(
            "users",
            ["Name", "Active"],
            "users_template.csv"
        )

    def _download_template_sites(self):
        self._download_template(
            "sites",
            ["Name", "SC Rate", "Active"],
            "sites_template.csv"
        )

    def _download_template_cards(self):
        self._download_template(
            "cards",
            ["Name", "User", "Cashback Rate", "Active"],
            "cards_template.csv"
        )

    def _download_template_methods(self):
        self._download_template(
            "methods",
            ["Name", "Active"],
            "redemption_methods_template.csv"
        )

    def _download_template_game_types(self):
        self._download_template(
            "game_types",
            ["Name", "Active"],
            "game_types_template.csv"
        )

    def _download_template_games(self):
        self._download_template(
            "games",
            ["Name", "Game Type", "RTP", "Active"],
            "games_template.csv"
        )

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
        """Download current data as CSV"""
        import csv
        from datetime import datetime

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

            # Get data based on table
            if table_name == "purchases":
                c.execute("""
                    SELECT p.purchase_date, p.purchase_time, s.name as site, u.name as user,
                           p.amount, p.sc_received, p.starting_sc_balance, ca.name as card, p.notes
                    FROM purchases p
                    JOIN sites s ON p.site_id = s.id
                    JOIN users u ON p.user_id = u.id
                    JOIN cards ca ON p.card_id = ca.id
                    ORDER BY p.purchase_date, p.purchase_time
                """)
                headers = ["Date", "Time", "Site", "User", "Amount", "SC Received", "Starting SC", "Card", "Notes"]

            elif table_name == "sessions":
                c.execute("""
                    SELECT session_date, start_time, end_time,
                           site_name, user_name, game_type, game_name,
                           starting_sc_balance, starting_redeemable_sc,
                           ending_sc_balance, ending_redeemable_sc,
                           wager_amount, notes
                    FROM game_sessions
                    ORDER BY session_date, start_time
                """)
                headers = ["Date", "Start Time", "End Time", "Site", "User", "Game Type", "Game Name",
                          "Starting Total SC", "Starting Redeemable", "Ending Total SC", "Ending Redeemable",
                          "Wager Amount", "Notes"]

            elif table_name == "redemptions":
                c.execute("""
                    SELECT r.redemption_date, r.redemption_time, s.name as site, u.name as user,
                           r.amount, m.name as method, r.notes
                    FROM redemptions r
                    JOIN sites s ON r.site_id = s.id
                    JOIN users u ON r.user_id = u.id
                    JOIN redemption_methods m ON r.method_id = m.id
                    ORDER BY r.redemption_date, r.redemption_time
                """)
                headers = ["Date", "Time", "Site", "User", "Amount", "Method", "Notes"]

            elif table_name == "expenses":
                c.execute("""
                    SELECT e.expense_date, e.category, e.vendor, u.name as user, e.amount, e.description
                    FROM expenses e
                    LEFT JOIN users u ON e.user_id = u.id
                    ORDER BY e.expense_date
                """)
                headers = ["Date", "Category", "Vendor", "User", "Amount", "Description"]

            elif table_name == "users":
                c.execute("SELECT name, active FROM users ORDER BY name")
                headers = ["Name", "Active"]

            elif table_name == "sites":
                c.execute("SELECT name, sc_rate, active FROM sites ORDER BY name")
                headers = ["Name", "SC Rate", "Active"]

            elif table_name == "cards":
                c.execute("""
                    SELECT c.name, u.name as user, c.cashback_rate, c.active
                    FROM cards c
                    JOIN users u ON c.user_id = u.id
                    ORDER BY c.name
                """)
                headers = ["Name", "User", "Cashback Rate", "Active"]

            elif table_name == "redemption_methods":
                c.execute("SELECT name, active FROM redemption_methods ORDER BY name")
                headers = ["Name", "Active"]

            elif table_name == "game_types":
                c.execute("SELECT name, active FROM game_types ORDER BY name")
                headers = ["Name", "Active"]

            elif table_name == "games":
                c.execute("""
                    SELECT g.name, gt.name as game_type, g.rtp, g.active
                    FROM games g
                    LEFT JOIN game_types gt ON g.game_type_id = gt.id
                    ORDER BY g.name
                """)
                headers = ["Name", "Game Type", "RTP", "Active"]

            else:
                conn.close()
                QtWidgets.QMessageBox.warning(self, "Error", f"Unknown table: {table_name}")
                return

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
            # Create timestamped backup filename
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
            c.execute("DELETE FROM daily_sessions")
            c.execute("DELETE FROM purchases")
            c.execute("DELETE FROM redemptions")
            c.execute("DELETE FROM expenses")
            c.execute("DELETE FROM site_sessions")
            c.execute("DELETE FROM purchase_allocations")

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

        tabs = [
            ("Users", UsersSetupTab(self.db)),
            ("Sites", SitesSetupTab(self.db)),
            ("Cards", CardsSetupTab(self.db)),
            ("Redemption Methods", MethodsSetupTab(self.db)),
            ("Game Types", GameTypesSetupTab(self.db)),
            ("Games", GamesSetupTab(self.db)),
            ("Tools", ToolsSetupTab(self.db, self.session_mgr, self.main_window)),
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

        self.purchases_tab = PurchasesTab(self.db, self.session_mgr, self.refresh_stats)
        self.redemptions_tab = RedemptionsTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            on_open_purchase=self.open_purchase,
        )
        self.game_sessions_tab = GameSessionsTab(self.db, self.session_mgr, self.refresh_stats)
        self.daily_sessions_tab = DailySessionsTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            self.open_game_session,
            self.edit_game_session,
            self.delete_game_session,
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
        self.setup_tab = SetupTab(self.db, self.session_mgr, self)

        tabs = [
            ("Purchases", self.purchases_tab),
            ("Redemptions", self.redemptions_tab),
            ("Game Sessions", self.game_sessions_tab),
            ("Daily Sessions", self.daily_sessions_tab),
            ("Unrealized", self.unrealized_tab),
            ("Realized", self.realized_tab),
            ("Expenses", self.expenses_tab),
            ("Reports", PlaceholderTab("Reports")),
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
            QLabel#SectionTitle {{ font-size: 14px; font-weight: 600; }}

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
