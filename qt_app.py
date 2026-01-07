#!/usr/bin/env python3
"""
qt_app.py - PySide6/Qt UI for Session
Run: python3 qt_app.py
"""
import os
import sys
from datetime import date, datetime, timedelta
from PySide6 import QtCore, QtWidgets

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
    def __init__(self, values, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter")
        self.resize(320, 440)
        self._values = list(values)
        self._selected = set(selected or [])
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
            grouped.setdefault(year, {}).setdefault(month_num, {}).setdefault(day, {}).setdefault(time_label, []).append(
                value
            )

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
                    for time_label in sorted(grouped[year][month_num][day].keys()):
                        leaf_values = grouped[year][month_num][day][time_label]
                        leaf_item = QtWidgets.QTreeWidgetItem([time_label])
                        leaf_item.setFlags(leaf_item.flags() | QtCore.Qt.ItemIsUserCheckable)
                        leaf_item.setData(0, QtCore.Qt.UserRole, leaf_values)
                        day_item.addChild(leaf_item)

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
        if os.environ.get("QT_DEBUG_COMPLETER") == "1":
            print(
                "[CompleterDebug] key=%s obj=%s focus=%s type=%s"
                % (
                    key,
                    obj.__class__.__name__,
                    focus_widget.__class__.__name__ if focus_widget else "None",
                    obj.metaObject().className() if hasattr(obj, "metaObject") else type(obj).__name__,
                )
            )
        combo = None
        if isinstance(focus_widget, QtWidgets.QLineEdit):
            combo = self._combo_for_line_edit(focus_widget)
        elif isinstance(focus_widget, QtWidgets.QComboBox):
            combo = focus_widget if focus_widget.isEditable() else None
        if combo is not None and combo.isEditable():
            line_edit = combo.lineEdit()
            text = line_edit.text() if line_edit is not None else combo.currentText()
            committed = self._commit_from_combo(combo, text)
            if os.environ.get("QT_DEBUG_COMPLETER") == "1":
                print("[CompleterDebug] committed=%s" % committed)
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
        for row in range(model.rowCount()):
            idx = model.index(row, column)
            data = model.data(idx)
            if data is None:
                continue
            if text.lower() in str(data).lower():
                combo.setCurrentText(str(data))
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
        form.addWidget(QtWidgets.QLabel("Notes"), 8, 0)
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

        if purchase:
            self._load_purchase()
        else:
            self._clear_form()

        self._update_completers()

    def _update_completers(self):
        for combo in (self.user_combo, self.site_combo, self.card_combo):
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

        start_sc_str = self.start_sc_edit.text().strip() or "0"
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
        self.edit_btn = QtWidgets.QPushButton("Edit Purchase")
        self.delete_btn = QtWidgets.QPushButton("Delete Purchase")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.add_btn.setObjectName("PrimaryButton")
        self.edit_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        actions.addWidget(self.refresh_btn)
        actions.addWidget(self.export_btn)
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
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setMinimumSectionSize(40)
        header.setSectionsClickable(False)
        self.header = header
        header.viewport().installEventFilter(self)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._update_action_visibility)

        self.add_btn.clicked.connect(self._add_purchase)
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
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                index = self.header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
        return super().eventFilter(obj, event)

    def _update_action_visibility(self):
        has_selection = bool(self.table.selectionModel().selectedRows())
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
        purchase_id = selected_ids[0]
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

        tabs = [
            ("Purchases", PurchasesTab(self.db, self.session_mgr, self.refresh_stats)),
            ("Redemptions", PlaceholderTab("Redemptions")),
            ("Game Sessions", PlaceholderTab("Game Sessions")),
            ("Daily Sessions", PlaceholderTab("Daily Sessions")),
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
    if os.environ.get("QT_DEBUG_COMPLETER") == "1":
        print("[CompleterDebug] enabled")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
