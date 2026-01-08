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
        self.resize(520, 420)

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
        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.setEditable(True)
        self.card_combo.addItems(card_names)
        self._user_lookup = {name.lower(): name for name in user_names}
        self._site_lookup = {name.lower(): name for name in site_names}

        self.amount_edit = QtWidgets.QLineEdit()
        self.sc_edit = QtWidgets.QLineEdit()
        self.start_sc_edit = QtWidgets.QLineEdit()
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
        form.addWidget(QtWidgets.QLabel("Card"), 4, 0)
        form.addWidget(self.card_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Amount"), 5, 0)
        form.addWidget(self.amount_edit, 5, 1)
        form.addWidget(QtWidgets.QLabel("SC Received"), 6, 0)
        form.addWidget(self.sc_edit, 6, 1)
        form.addWidget(QtWidgets.QLabel("Starting SC"), 7, 0)
        form.addWidget(self.start_sc_edit, 7, 1)
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(notes_label, 8, 0)
        form.addWidget(self.notes_edit, 8, 1)

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
        self._preserve_card_selection = True
        self.user_combo.setCurrentText(self.purchase["user_name"])
        self._preserve_card_selection = False
        self.site_combo.setCurrentText(self.purchase["site_name"])
        self.card_combo.setCurrentText(self.purchase["card_name"])
        self.amount_edit.setText(str(self.purchase["amount"]))
        self.sc_edit.setText(str(self.purchase["sc_received"]))
        self.start_sc_edit.setText(str(self.purchase["starting_sc_balance"]))
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

        return {
            "user_name": user_name,
            "site_name": site_name,
            "card_name": card_name,
            "purchase_date": pdate.strftime("%Y-%m-%d"),
            "purchase_time": ptime,
            "amount": amount,
            "sc_received": sc_received,
            "starting_sc_balance": start_sc,
            "notes": notes,
        }, None


class PurchaseViewDialog(QtWidgets.QDialog):
    def __init__(self, purchase, parent=None, on_edit=None):
        super().__init__(parent)
        self.purchase = purchase
        self._on_edit = on_edit
        self.setWindowTitle("View Purchase")
        self.resize(540, 520)

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

        row = 0
        row = add_row("Date", format_date(purchase["purchase_date"]), row)
        row = add_row("Time", format_time(purchase["purchase_time"]), row)
        row = add_row("User", purchase["user_name"] or "—", row)
        row = add_row("Site", purchase["site_name"] or "—", row)
        row = add_row("Card", purchase["card_name"] or "—", row)
        row = add_row("Amount", format_currency(purchase["amount"]), row)
        row = add_row("SC Received", f"{float(purchase['sc_received'] or 0):.2f}", row)
        row = add_row("Starting SC", f"{float(purchase['starting_sc_balance'] or 0):.2f}", row)
        row = add_row("Remaining", format_currency(purchase["remaining_amount"]), row)

        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        notes_edit = QtWidgets.QPlainTextEdit()
        notes_edit.setObjectName("NotesField")
        notes_edit.setReadOnly(True)
        notes_edit.setPlainText(purchase["notes"] or "")
        notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        form.addWidget(notes_label, row, 0)
        form.addWidget(notes_edit, row, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)


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
    def __init__(self, redemption, parent=None, on_edit=None):
        super().__init__(parent)
        self.redemption = redemption
        self._on_edit = on_edit
        self.setWindowTitle("View Redemption")
        self.resize(560, 560)

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
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        notes_edit = QtWidgets.QPlainTextEdit()
        notes_edit.setObjectName("NotesField")
        notes_edit.setReadOnly(True)
        notes_edit.setPlainText(redemption["notes"] or "")
        notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        form.addWidget(notes_label, row, 0)
        form.addWidget(notes_edit, row, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            btn_row.addWidget(edit_btn)
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        close_btn.clicked.connect(self.accept)

    def _handle_edit(self):
        if self._on_edit:
            self.accept()
            QtCore.QTimer.singleShot(0, self._on_edit)


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

        self.game_type_combo = QtWidgets.QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QtWidgets.QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.addItems([""] + self._all_game_names())
        self.game_helper = QtWidgets.QLabel("Game Name requires a Game Type.")
        self.game_helper.setObjectName("HelperText")
        self.game_helper.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.start_total_edit = QtWidgets.QLineEdit()
        self.start_redeem_edit = QtWidgets.QLineEdit()

        self.freebie_label = QtWidgets.QLabel("")
        self.freebie_label.setWordWrap(True)
        self.freebie_label.setObjectName("InfoField")
        self.freebie_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.freebie_label.setProperty("status", "neutral")
        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.freebie_label.setToolTip(balance_tooltip)
        self.balance_label = QtWidgets.QLabel("Balance Check")
        self.balance_label.setToolTip(balance_tooltip)
        self.balance_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Date"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("Start Time"), 1, 0)
        form.addLayout(time_row, 1, 1)
        form.addWidget(QtWidgets.QLabel("User"), 2, 0)
        form.addWidget(self.user_combo, 2, 1)
        form.addWidget(QtWidgets.QLabel("Site"), 3, 0)
        form.addWidget(self.site_combo, 3, 1)
        form.addWidget(QtWidgets.QLabel("Game Type"), 4, 0)
        form.addWidget(self.game_type_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Game Name"), 5, 0)
        form.addWidget(self.game_name_combo, 5, 1)
        form.addWidget(self.game_helper, 6, 0, 1, 2)
        form.addWidget(QtWidgets.QLabel("Starting Total SC"), 7, 0)
        form.addWidget(self.start_total_edit, 7, 1)
        form.addWidget(QtWidgets.QLabel("Starting Redeemable"), 8, 0)
        form.addWidget(self.start_redeem_edit, 8, 1)
        form.addWidget(self.balance_label, 9, 0)
        form.addWidget(self.freebie_label, 9, 1)
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
            names = self._all_game_names()
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

        form = QtWidgets.QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

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

        self.game_type_combo = QtWidgets.QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QtWidgets.QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.addItems([""] + self._all_game_names())
        self.game_helper = QtWidgets.QLabel("Game Name requires a Game Type.")
        self.game_helper.setObjectName("HelperText")
        self.game_helper.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

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

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QtWidgets.QLabel("Start Date"), 0, 0)
        form.addLayout(start_date_row, 0, 1)
        form.addWidget(QtWidgets.QLabel("Start Time"), 1, 0)
        form.addLayout(start_time_row, 1, 1)
        form.addWidget(QtWidgets.QLabel("End Date"), 2, 0)
        form.addLayout(end_date_row, 2, 1)
        form.addWidget(QtWidgets.QLabel("End Time"), 3, 0)
        form.addLayout(end_time_row, 3, 1)
        form.addWidget(QtWidgets.QLabel("User"), 4, 0)
        form.addWidget(self.user_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Site"), 5, 0)
        form.addWidget(self.site_combo, 5, 1)
        form.addWidget(QtWidgets.QLabel("Game Type"), 6, 0)
        form.addWidget(self.game_type_combo, 6, 1)
        form.addWidget(QtWidgets.QLabel("Game Name"), 7, 0)
        form.addWidget(self.game_name_combo, 7, 1)
        form.addWidget(self.game_helper, 8, 0, 1, 2)
        form.addWidget(QtWidgets.QLabel("Starting Total SC"), 9, 0)
        form.addWidget(self.start_total_edit, 9, 1)
        form.addWidget(QtWidgets.QLabel("Starting Redeemable"), 10, 0)
        form.addWidget(self.start_redeem_edit, 10, 1)
        form.addWidget(self.balance_label, 11, 0)
        form.addWidget(self.balance_value, 11, 1)
        form.addWidget(QtWidgets.QLabel("Ending Total SC"), 12, 0)
        form.addWidget(self.end_total_edit, 12, 1)
        form.addWidget(QtWidgets.QLabel("Ending Redeemable"), 13, 0)
        form.addWidget(self.end_redeem_edit, 13, 1)
        notes_label = QtWidgets.QLabel("Notes")
        notes_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form.addWidget(notes_label, 14, 0)
        form.addWidget(self.notes_edit, 14, 1)

        layout.addLayout(form)
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
            names = self._all_game_names()
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
        if self.session and self.session.get("wager_amount") is not None:
            wager_amount = float(self.session.get("wager_amount") or 0.0)

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
    def __init__(self, session, parent=None, on_open_session=None, on_edit=None):
        super().__init__(parent)
        self.session = session
        self._on_open_session = on_open_session
        self._on_edit = on_edit
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
        notes_edit = QtWidgets.QPlainTextEdit()
        notes_edit.setObjectName("NotesField")
        notes_edit.setReadOnly(True)
        notes_edit.setPlainText(session["notes"] or "")
        notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 16)
        notes_layout.addWidget(notes_edit)
        layout.addWidget(notes_group)
        layout.addSpacing(4)

        btn_row = QtWidgets.QHBoxLayout()
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
        if self._on_edit:
            edit_btn.clicked.connect(self._handle_edit)
        if self._on_open_session:
            open_btn.clicked.connect(self._handle_open_session)
        close_btn.clicked.connect(self.accept)

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

        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Date/Time",
                "User",
                "Site",
                "Amount",
                "SC Received",
                "Starting SC",
                "Card",
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
                   p.remaining_amount, p.notes
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
            purchase, parent=self, on_edit=lambda: self.edit_purchase_by_id(purchase_id)
        )
        dialog.exec()

    def _save_from_dialog(self, dialog, purchase_id):
        data, error = dialog.collect_data()
        if error:
            QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
            return
        ok, message = self._save_purchase_record(data, purchase_id)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Error", message)
            return
        dialog.accept()
        self.load_data()
        if self.on_data_changed:
            self.on_data_changed()
        QtWidgets.QMessageBox.information(self, "Success", message)

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
                    starting_sc_balance=?, card_id=?, user_id=?, remaining_amount=?, notes=?
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
             card_id, user_id, remaining_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return True, message

    def _selected_ids(self):
        ids = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

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

        conn = self.db.get_connection()
        c = conn.cursor()
        deleted_count = 0
        error_messages = []
        affected = set()

        for purchase_id in selected_ids:
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
            affected.add((site_id, user_id, pdate, ptime))

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
        for site_id, user_id, pdate, ptime in affected:
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


class RedemptionsTab(QtWidgets.QWidget):
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
        dialog = RedemptionViewDialog(
            redemption, parent=self, on_edit=lambda: self.edit_redemption_by_id(redemption_id)
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
        QtWidgets.QMessageBox.information(self, "Success", message)

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
            session, parent=self, on_edit=lambda: self.edit_session_by_id(session_id)
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
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.session_mgr = session_mgr
        self.on_data_changed = on_data_changed
        self.on_open_session = on_open_session
        self.on_edit_session = on_edit_session
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

        info_label = QtWidgets.QLabel(
            "Daily sessions automatically roll up game sessions and other income for tax reporting"
        )
        info_label.setObjectName("HelperText")
        layout.addWidget(info_label)

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
        date_row.addWidget(self.apply_btn)
        date_row.addWidget(self.clear_btn)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.last30_btn)
        date_row.addWidget(self.this_month_btn)
        date_row.addWidget(self.this_year_btn)
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
        self.notes_btn = QtWidgets.QPushButton("Add/Edit Notes")
        self.expand_btn = QtWidgets.QPushButton("Expand All")
        self.collapse_btn = QtWidgets.QPushButton("Collapse All")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        search_row.addWidget(self.notes_btn)
        search_row.addWidget(self.expand_btn)
        search_row.addWidget(self.collapse_btn)
        search_row.addWidget(self.refresh_btn)
        search_row.addWidget(self.export_btn)
        layout.addLayout(search_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
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
        self.notes_btn.clicked.connect(self.add_edit_notes)
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
        self.from_calendar.clicked.connect(lambda: self.pick_date(self.from_edit))
        self.to_calendar.clicked.connect(lambda: self.pick_date(self.to_edit))
        self.user_filter_btn.clicked.connect(self._show_user_filter)
        self.site_filter_btn.clicked.connect(self._show_site_filter)

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
        self.refresh_view()

    def _clear_search(self):
        self.search_edit.clear()

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

        dialog = GameSessionViewDialog(
            session,
            parent=self,
            on_open_session=handle_open if self.on_open_session else None,
            on_edit=handle_edit if self.on_edit_session else None,
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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Session - Social Casino Tracker (Qt)")
        self.resize(1400, 900)
        self.setMinimumSize(0, 0)
        self.db = Database()
        self.session_mgr = SessionManager(self.db, FIFOCalculator(self.db))
        self.completer_filter = ComboCompleterFilter(self)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app._completer_filter = self.completer_filter
            app.installEventFilter(self.completer_filter)

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

        self.tab_bar = QtWidgets.QWidget()
        tab_bar_layout = FlowLayout(self.tab_bar, margin=0, spacing=8, align=QtCore.Qt.AlignCenter)
        self.tab_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.tab_bar.setMinimumWidth(0)

        self.tab_group = QtWidgets.QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.stacked = QtWidgets.QStackedWidget()
        self.stacked.setMinimumSize(0, 0)
        self.stacked.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.tab_buttons = []

        self.purchases_tab = PurchasesTab(self.db, self.session_mgr, self.refresh_stats)
        self.redemptions_tab = RedemptionsTab(self.db, self.session_mgr, self.refresh_stats)
        self.game_sessions_tab = GameSessionsTab(self.db, self.session_mgr, self.refresh_stats)
        self.daily_sessions_tab = DailySessionsTab(
            self.db,
            self.session_mgr,
            self.refresh_stats,
            self.open_game_session,
            self.edit_game_session,
        )

        tabs = [
            ("Purchases", self.purchases_tab),
            ("Redemptions", self.redemptions_tab),
            ("Game Sessions", self.game_sessions_tab),
            ("Daily Sessions", self.daily_sessions_tab),
            ("Unrealized", PlaceholderTab("Unrealized")),
            ("Realized", PlaceholderTab("Realized")),
            ("Expenses", PlaceholderTab("Expenses")),
            ("Reports", PlaceholderTab("Reports")),
            ("Setup", PlaceholderTab("Setup")),
        ]

        for idx, (label, widget) in enumerate(tabs):
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
        main_layout.addWidget(self.stacked, 1)
        self.setCentralWidget(central)

        self.refresh_stats()

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

    def edit_game_session(self, session_id):
        target_index = self.stacked.indexOf(self.game_sessions_tab)
        if target_index < 0:
            return
        self.stacked.setCurrentIndex(target_index)
        self.game_sessions_tab.edit_session_by_id(session_id)

    def _on_tab_clicked(self, button):
        tab_index = self.tab_group.id(button)
        if tab_index >= 0:
            self.stacked.setCurrentIndex(tab_index)

    def _sync_tab_selection(self, index):
        button = self.tab_group.button(index)
        if button:
            button.setChecked(True)

    def _apply_style(self):
        self.setStyle(QtWidgets.QStyleFactory.create("Fusion"))
        self.setStyleSheet(
            """
            QMainWindow { background: #ffffff; }
            QWidget { color: #1e1f24; font-size: 12px; }
            QDialog, QMessageBox { background: #f7f9ff; }
            QFrame#StatsBar {
                background: #f7f9ff;
                border: 1px solid #dfeaff;
                border-radius: 10px;
            }
            QFrame#StatsBar QLabel {
                color: #1e1f24;
            }
            QLabel#SectionTitle { font-size: 14px; font-weight: 600; }

            #TabButton {
                background: #f7f9ff;
                border: 1px solid #dfeaff;
                border-radius: 10px;
                padding: 6px 14px;
                color: #62636c;
            }
            #TabButton:hover {
                background: #edf2fe;
            }
            #TabButton:checked {
                background: #3d63dd;
                color: white;
                border: 1px solid #3657c3;
            }

            QStackedWidget {
                background: #f7f9ff;
                border: 1px solid #dfeaff;
                border-radius: 12px;
            }

            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
                background: #fdfdfe;
                border: 1px solid #dfeaff;
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 26px;
            }
            QLineEdit[invalid="true"], QTextEdit[invalid="true"], QPlainTextEdit[invalid="true"], QComboBox[invalid="true"] {
                border: 1px solid #c0392b;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
                border: 1px solid #a6bff9;
            }
            QComboBox {
                padding-right: 30px;
            }
            QComboBox::editable {
                background: #fdfdfe;
                color: #1e1f24;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #dfeaff;
                background: #edf2fe;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::down-arrow {
                image: url("icons/chevron-down.svg");
                width: 10px;
                height: 6px;
            }
            QAbstractItemView,
            QListView,
            QComboBox QAbstractItemView {
                background: #fdfdfe;
                color: #1e1f24;
                selection-background-color: #d0dfff;
                selection-color: #1e1f24;
            }
            QPlainTextEdit#NotesField {
                min-height: 78px;
            }
            QLabel#InfoField {
                background: #fdfdfe;
                border: 1px solid #dfeaff;
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 26px;
            }
            QLabel#InfoField[status="positive"] { color: #2e7d32; }
            QLabel#InfoField[status="negative"] { color: #c0392b; }
            QLabel#InfoField[status="neutral"] { color: #62636c; }
            QLabel#HelperText { color: #62636c; font-size: 11px; }
            QRadioButton[invalid="true"] { color: #c0392b; }
            QMenu {
                background: #fdfdfe;
                color: #1e1f24;
                border: 1px solid #dfeaff;
            }
            QMenu::item:selected {
                background: #d0dfff;
            }
            QCalendarWidget QWidget {
                background: #f7f9ff;
            }
            QCalendarWidget QToolButton {
                background: #edf2fe;
                color: #1e1f24;
                border: 1px solid #dfeaff;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QCalendarWidget QMenu {
                background: #fdfdfe;
                color: #1e1f24;
                border: 1px solid #dfeaff;
            }
            QCalendarWidget QSpinBox {
                background: #fdfdfe;
                color: #1e1f24;
                border: 1px solid #dfeaff;
                border-radius: 6px;
                padding: 2px 6px;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background: #fdfdfe;
                color: #1e1f24;
                selection-background-color: #d0dfff;
                selection-color: #1e1f24;
            }
            QPushButton {
                background: #f7f9ff;
                border: 1px solid #dfeaff;
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 26px;
            }
            QPushButton:hover { background: #edf2fe; }
            QPushButton#PrimaryButton {
                background: #3d63dd;
                border: 1px solid #3657c3;
                color: white;
            }
            QPushButton#PrimaryButton:hover { background: #3657c3; }
            QToolButton#InfoButton {
                background: #edf2fe;
                border: 1px solid #dfeaff;
                border-radius: 9px;
                min-width: 18px;
                min-height: 18px;
                padding: 0;
                font-weight: 600;
            }
            QToolButton#InfoButton:hover { background: #dfeaff; }
            QCheckBox, QRadioButton {
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #a6bff9;
                border-radius: 4px;
                background: #fdfdfe;
            }
            QCheckBox::indicator:checked {
                background: #3d63dd;
                border: 1px solid #3657c3;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #a6bff9;
                border-radius: 8px;
                background: #fdfdfe;
            }
            QRadioButton::indicator:checked {
                background: #3d63dd;
                border: 1px solid #3657c3;
            }

            QTableWidget {
                background: #f7f9ff;
                gridline-color: #dfeaff;
                border: 1px solid #dfeaff;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #edf2fe;
                border: 1px solid #dfeaff;
                padding: 6px;
                font-weight: 600;
            }
            QTableWidget::item:selected {
                background: #d0dfff;
            }
            QScrollBar:vertical {
                background: #f7f9ff;
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #b9bbc6;
                min-height: 30px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: none;
                height: 0;
            }
            QScrollBar:horizontal {
                background: #f7f9ff;
                height: 12px;
                margin: 2px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background: #b9bbc6;
                min-width: 30px;
                border-radius: 6px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                background: none;
                width: 0;
            }
            """
        )


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
