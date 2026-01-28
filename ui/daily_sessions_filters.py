"""Filter dialogs and header helpers for Daily Sessions"""
from PySide6 import QtWidgets, QtCore, QtGui


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
            item.setCheckState(QtCore.Qt.Checked if value in self._selected else QtCore.Qt.Unchecked)
            self.list_widget.addItem(item)

    def _apply_search(self):
        term = self.search_edit.text().strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(term not in item.text().lower())

    def _select_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(QtCore.Qt.Checked)

    def _clear_all(self):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(QtCore.Qt.Unchecked)

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
            if not value:
                continue
            if self._show_time:
                date_part, _, time_part = value.partition(" ")
            else:
                date_part, time_part = value, ""
            year, month, day = date_part.split("-")
            grouped.setdefault(year, {}).setdefault(month, {}).setdefault(day, set()).add(time_part)

        for year in sorted(grouped.keys()):
            year_item = QtWidgets.QTreeWidgetItem([year])
            self.tree.addTopLevelItem(year_item)
            for month in sorted(grouped[year].keys()):
                month_item = QtWidgets.QTreeWidgetItem([month])
                year_item.addChild(month_item)
                for day in sorted(grouped[year][month].keys()):
                    day_item = QtWidgets.QTreeWidgetItem([day])
                    month_item.addChild(day_item)
                    times = sorted(grouped[year][month][day])
                    if not self._show_time:
                        times = [""]
                    for time_value in times:
                        label = f"{year}-{month}-{day} {time_value}".strip()
                        leaf = QtWidgets.QTreeWidgetItem([label])
                        leaf.setCheckState(0, QtCore.Qt.Checked if label in self._selected else QtCore.Qt.Unchecked)
                        day_item.addChild(leaf)

        self._update_check_states()

    def _update_check_states(self):
        self._updating = True
        all_selected = not self._selected
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._set_item_checked_recursive(root.child(i), all_selected)
        if self._selected:
            for leaf in self._leaf_items():
                leaf.setCheckState(0, QtCore.Qt.Checked if leaf.text(0) in self._selected else QtCore.Qt.Unchecked)
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
                stack.extend(item.child(i) for i in range(item.childCount()))
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
                selected.add(leaf.text(0))
        if len(selected) == len(self._values):
            return set()
        return selected
