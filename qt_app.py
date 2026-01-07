#!/usr/bin/env python3
"""
qt_app.py - PySide6/Qt UI for Session
Run: python3 qt_app.py
"""
import sys
from PySide6 import QtCore, QtWidgets

from database import Database


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
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.all_rows = []
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(10)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search purchases...")
        self.search_edit.textChanged.connect(self.apply_filter)

        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self.search_edit.clear)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setObjectName("PrimaryButton")

        export_btn = QtWidgets.QPushButton("Export CSV")
        export_btn.clicked.connect(self.export_csv)

        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(clear_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date/Time", "Site", "User", "Amount", "SC Received", "Remaining", "Notes"]
        )
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumSize(0, 0)
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        self.table.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        header.setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT p.purchase_date, p.purchase_time, s.name as site, u.name as user_name,
                   p.amount, p.sc_received, p.remaining_amount, p.notes
            FROM purchases p
            JOIN sites s ON p.site_id = s.id
            JOIN users u ON p.user_id = u.id
            ORDER BY p.purchase_date DESC, p.purchase_time DESC
            """
        )
        self.all_rows = [
            (
                format_date_time(row["purchase_date"], row["purchase_time"]),
                row["site"],
                row["user_name"],
                format_currency(row["amount"]),
                f"{float(row['sc_received'] or 0):.2f}",
                format_currency(row["remaining_amount"]),
                (row["notes"] or "")[:120],
            )
            for row in c.fetchall()
        ]
        conn.close()
        self.apply_filter()

    def apply_filter(self):
        term = self.search_edit.text().strip().lower()
        if term:
            rows = [r for r in self.all_rows if term in " ".join(str(v).lower() for v in r)]
        else:
            rows = self.all_rows

        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, value in enumerate(row):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.table.setItem(r_idx, c_idx, item)

    def export_csv(self):
        import csv
        from datetime import datetime

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
            for row in range(self.table.rowCount()):
                writer.writerow(
                    [
                        self.table.item(row, col).text() if self.table.item(row, col) else ""
                        for col in range(self.table.columnCount())
                    ]
                )


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
            ("Purchases", PurchasesTab(self.db)),
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

            QLineEdit, QTextEdit, QComboBox {
                background: #fdfdfe;
                border: 1px solid #dfeaff;
                border-radius: 8px;
                padding: 6px 10px;
                min-height: 26px;
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
            """
        )


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
