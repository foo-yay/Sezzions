"""Reusable header sorting/filtering for QTableWidget (legacy-style)."""
from PySide6 import QtWidgets, QtCore
import shiboken6
from ui.daily_sessions_filters import (
    ColumnFilterDialog,
    DateTimeFilterDialog,
    header_resize_section_index,
    header_menu_position,
)


class TableHeaderFilter(QtCore.QObject):
    """Adds Excel-style sort/filter menus to QTableWidget headers."""

    def __init__(self, table: QtWidgets.QTableWidget, date_columns=None, refresh_callback=None):
        super().__init__(table)
        self.table = table
        self.date_columns = set(date_columns or [])
        self.refresh_callback = refresh_callback
        self.column_filters = {}
        self.sort_column = None
        self.sort_order = QtCore.Qt.AscendingOrder
        self._suppress_header_menu = False
        self._header_left_pressed = False

        self._base_headers = []
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            self._base_headers.append(item.text() if item else str(i))

        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        # Guard against calls during/after destruction (common in tests)
        if not hasattr(self, 'table') or not shiboken6.isValid(self.table):
            return False
        header = self.table.horizontalHeader()
        if not shiboken6.isValid(header):
            return False
        if obj is header.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                # Track a genuine header click. This prevents stray MouseButtonRelease events (e.g.,
                # after dismissing modal dialogs) from unexpectedly opening the header menu.
                self._header_left_pressed = True
                return False
            if event.type() == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                handle = header_resize_section_index(header, pos)
                if handle is not None:
                    self._suppress_header_menu = True
                    self.table.resizeColumnToContents(handle)
                    return True
            if event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == QtCore.Qt.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if not self._header_left_pressed:
                    return False
                self._header_left_pressed = False
                if self._suppress_header_menu:
                    self._suppress_header_menu = False
                    return True
                if header_resize_section_index(header, pos) is not None:
                    return False
                index = header.logicalIndexAt(pos)
                if index >= 0:
                    self._show_header_menu(index)
                    return True
            if event.type() in (QtCore.QEvent.Leave, QtCore.QEvent.FocusOut):
                self._header_left_pressed = False
        return super().eventFilter(obj, event)

    def _show_header_menu(self, col_index: int):
        header_text = self._base_headers[col_index]
        menu = QtWidgets.QMenu(self.table)

        sort_asc = menu.addAction("Sort A → Z")
        sort_desc = menu.addAction("Sort Z → A")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction(f"Filter {header_text}...")
        clear_filter = menu.addAction("Clear Filter")

        action = menu.exec(header_menu_position(self.table.horizontalHeader(), col_index, menu))
        if action == sort_asc:
            self.sort_by_column(col_index, QtCore.Qt.AscendingOrder)
        elif action == sort_desc:
            self.sort_by_column(col_index, QtCore.Qt.DescendingOrder)
        elif action == clear_sort:
            self.clear_sort()
        elif action == filter_action:
            self.show_filter_dialog(col_index)
        elif action == clear_filter:
            self.clear_filter(col_index)

    def _column_values(self, col_index: int):
        values = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, col_index)
            values.append(item.text() if item else "")
        return values

    def show_filter_dialog(self, col_index: int):
        values = self._column_values(col_index)
        values = sorted({v for v in values if v is not None})
        selected = self.column_filters.get(col_index, set())

        if col_index in self.date_columns:
            dialog = DateTimeFilterDialog(values, selected, self.table, show_time=True)
        else:
            dialog = ColumnFilterDialog(values, selected, self.table)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            selected_values = dialog.selected_values()
            if selected_values:
                self.column_filters[col_index] = selected_values
            else:
                self.column_filters.pop(col_index, None)
            self.apply_filters()

    def apply_filters(self):
        if not self.column_filters:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return

        for row in range(self.table.rowCount()):
            hide = False
            for col, selected in self.column_filters.items():
                if not selected:
                    continue
                item = self.table.item(row, col)
                value = item.text() if item else ""
                if value not in selected:
                    hide = True
                    break
            self.table.setRowHidden(row, hide)

    def clear_filter(self, col_index: int):
        if col_index in self.column_filters:
            self.column_filters.pop(col_index, None)
            self.apply_filters()

    def clear_all_filters(self):
        self.column_filters = {}
        self.apply_filters()

    def sort_by_column(self, col_index: int, order: QtCore.Qt.SortOrder):
        self.table.setSortingEnabled(True)
        self.table.sortItems(col_index, order)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(col_index, order)
        self.sort_column = col_index
        self.sort_order = order

    def clear_sort(self):
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(False)
        self.table.setSortingEnabled(False)
        if self.refresh_callback:
            self.refresh_callback()
