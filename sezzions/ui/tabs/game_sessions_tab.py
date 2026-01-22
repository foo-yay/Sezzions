"""
Game Sessions Tab - Track gameplay sessions with P/L calculations
"""
import re
from datetime import datetime, date
from decimal import Decimal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QDialog, QLineEdit, QComboBox,
    QLabel, QHeaderView, QCalendarWidget, QFileDialog, QGroupBox,
    QPlainTextEdit, QTabWidget, QListView, QCompleter, QSizePolicy,
    QGridLayout, QApplication
)
from PySide6.QtCore import Qt, QTime, QDate, QTimer
from PySide6.QtGui import QColor
from ui.date_filter_widget import DateFilterWidget
from ui.tabs.purchases_tab import PurchaseViewDialog
from ui.tabs.redemptions_tab import RedemptionViewDialog


TIME_24H_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d(?:\:[0-5]\d)?$")


def parse_date_input(value: str) -> date:
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


def parse_time_input(value: str) -> str:
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


def is_valid_time_24h(value: str, allow_blank: bool = True) -> bool:
    value = value.strip()
    if not value:
        return allow_blank
    return bool(TIME_24H_RE.match(value))


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


def format_currency(value) -> str:
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "—"


class GameSessionsTab(QWidget):
    """Tab for managing game sessions with P/L tracking"""
    
    def __init__(self, facade, main_window=None):
        super().__init__()
        self.facade = facade
        self.main_window = main_window
        self.sessions = []
        self.filtered_sessions = []
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Game Sessions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search sessions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_sessions)
        header_layout.addWidget(self.search_edit)

        self.search_clear_btn = QPushButton("Clear")
        self.search_clear_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.search_clear_btn)

        self.clear_filters_btn = QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)

        layout.addLayout(header_layout)

        info = QLabel("Start/end play sessions here to track SC changes and session P/L.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)

        self.date_filter = DateFilterWidget()
        self.date_filter.filter_changed.connect(self.apply_filters)
        layout.addWidget(self.date_filter)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_button = QPushButton("➕ Start Session")
        self.view_button = QPushButton("👁️ View Session")
        self.end_button = QPushButton("⏹️ End Session")
        self.edit_button = QPushButton("✏️ Edit Session")
        self.delete_button = QPushButton("🗑️ Delete Session")
        self.export_button = QPushButton("📤 Export CSV")
        self.refresh_button = QPushButton("🔄 Refresh")
        self.active_label = QLabel("Active Sessions: 0")

        self.add_button.setObjectName("PrimaryButton")
        self.view_button.setVisible(False)
        self.end_button.setVisible(False)
        self.edit_button.setVisible(False)
        self.delete_button.setVisible(False)

        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.end_button)
        toolbar.addWidget(self.view_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.active_label)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)

        self.columns = [
            "Date/Time",
            "Site",
            "User",
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

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self.view_session)
        layout.addWidget(self.table)

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self.add_button.clicked.connect(self.add_session)
        self.view_button.clicked.connect(self.view_session)
        self.end_button.clicked.connect(self.end_session)
        self.edit_button.clicked.connect(self.edit_session)
        self.delete_button.clicked.connect(self.delete_session)
        self.export_button.clicked.connect(self.export_csv)
        self.refresh_button.clicked.connect(self.load_data)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
    
    def load_data(self):
        """Load all game sessions from database"""
        try:
            self.sessions = self.facade.game_session_service.list_sessions()
            self.apply_filters()
            self._on_selection_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load sessions:\n{str(e)}")
    
    def _filter_sessions(self):
        """Filter sessions based on search text"""
        self.apply_filters()
    
    def apply_filters(self):
        filtered = self._get_filtered_sessions()
        self.filtered_sessions = filtered
        self._populate_table(filtered)
        self._update_active_label()

    def _get_filtered_sessions(self):
        rows = list(self.sessions)

        start_date, end_date = self.date_filter.get_date_range()
        if start_date:
            rows = [s for s in rows if s.session_date >= start_date]
        if end_date:
            rows = [s for s in rows if s.session_date <= end_date]

        search_text = self.search_edit.text().lower().strip()
        if search_text:
            rows = [
                s for s in rows
                if search_text in str(s.session_date).lower()
                or (hasattr(s, 'user_name') and s.user_name and search_text in s.user_name.lower())
                or (hasattr(s, 'site_name') and s.site_name and search_text in s.site_name.lower())
                or (hasattr(s, 'game_name') and s.game_name and search_text in s.game_name.lower())
                or (s.notes and search_text in s.notes.lower())
            ]

        rows.sort(key=lambda s: (s.session_date, s.session_time or "00:00:00"), reverse=True)
        return rows

    def _populate_table(self, rows):
        try:
            users = {u.id: u.name for u in self.facade.get_all_users()}
            sites = {s.id: s.name for s in self.facade.get_all_sites()}
            games = {g.id: g for g in self.facade.list_all_games()}

            self.table.setRowCount(len(rows))

            for row, session in enumerate(rows):
                time_val = session.session_time or "00:00:00"
                if time_val and len(time_val) > 5:
                    time_val = time_val[:5]
                date_time = f"{session.session_date} {time_val}".strip()

                game = games.get(session.game_id)
                game_name = game.name if game else "—"

                values = [
                    date_time,
                    sites.get(session.site_id, "—"),
                    users.get(session.user_id, "—"),
                    game_name,
                    f"{session.starting_balance:,.2f}",
                ]

                if session.status == "Active":
                    values.extend(["—", f"{session.starting_redeemable:,.2f}", "—", "—", "—", "—", "Active", session.notes or ""])
                else:
                    delta_redeem = session.delta_redeem if session.delta_redeem is not None else Decimal("0.00")
                    basis = session.basis_consumed if session.basis_consumed is not None else Decimal("0.00")
                    net_pl = session.net_taxable_pl if session.net_taxable_pl is not None else Decimal("0.00")
                    values.extend([
                        f"{session.ending_balance:,.2f}",
                        f"{session.starting_redeemable:,.2f}",
                        f"{session.ending_redeemable:,.2f}",
                        f"{delta_redeem:,.2f}",
                        f"${basis:,.2f}",
                        f"${net_pl:,.2f}",
                        session.status or "Closed",
                        session.notes or ""
                    ])

                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setData(Qt.UserRole, session.id)
                    self.table.setItem(row, col, item)

                if session.status != "Active":
                    net_pl = session.net_taxable_pl if session.net_taxable_pl is not None else Decimal("0.00")
                    pl_item = self.table.item(row, 10)
                    if pl_item:
                        if net_pl > 0:
                            pl_item.setForeground(QColor(0, 128, 0))
                        elif net_pl < 0:
                            pl_item.setForeground(QColor(200, 0, 0))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load sessions: {e}")
    
    def add_session(self):
        """Show dialog to add new session"""
        dialog = StartSessionDialog(self.facade, parent=self)

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                self.facade.create_game_session(
                    user_id=data["user_id"],
                    site_id=data["site_id"],
                    game_id=data["game_id"],
                    session_date=data["session_date"],
                    starting_balance=data["starting_total_sc"],
                    ending_balance=Decimal("0.00"),
                    starting_redeemable=data["starting_redeemable_sc"],
                    ending_redeemable=Decimal("0.00"),
                    purchases_during=Decimal("0.00"),
                    redemptions_during=Decimal("0.00"),
                    session_time=data["start_time"],
                    notes=data["notes"],
                    calculate_pl=False,
                )
                dialog.accept()
                self.load_data()
                QMessageBox.information(self, "Success", "Session started successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start session: {e}")

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()
    
    def edit_session(self):
        """Edit selected session"""
        ids = self._selected_ids()
        if len(ids) != 1:
            QMessageBox.warning(self, "Warning", "Please select a single session to edit")
            return

        self._edit_session_by_id(ids[0])

    def _edit_session_by_id(self, session_id: int):
        session = self.facade.get_game_session(session_id)
        if not session:
            QMessageBox.warning(self, "Warning", "Session not found")
            return

        if (session.status or "Active") == "Closed":
            dialog = EditClosedSessionDialog(self.facade, session=session, parent=self)
        else:
            dialog = EditSessionDialog(self.facade, session=session, parent=self)

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                update_kwargs = {
                    "user_id": data["user_id"],
                    "site_id": data["site_id"],
                    "game_id": data["game_id"],
                    "session_date": data["session_date"],
                    "starting_balance": data["starting_total_sc"],
                    "starting_redeemable": data["starting_redeemable_sc"],
                    "session_time": data["start_time"],
                    "notes": data["notes"],
                }
                if (session.status or "Active") == "Closed":
                    update_kwargs.update(
                        {
                            "ending_balance": data["ending_total_sc"],
                            "ending_redeemable": data["ending_redeemable_sc"],
                            "end_date": data["end_date"],
                            "end_time": data["end_time"],
                            "status": "Closed",
                        }
                    )
                self.facade.update_game_session(session_id=session_id, **update_kwargs)
                dialog.accept()
                self.load_data()
                QMessageBox.information(self, "Success", "Session updated successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update session: {e}")

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def view_session(self):
        """View selected session"""
        ids = self._selected_ids()
        if len(ids) != 1:
            QMessageBox.warning(self, "Warning", "Please select a single session to view")
            return

        session_id = ids[0]
        session = self.facade.get_game_session(session_id)
        if not session:
            QMessageBox.warning(self, "Warning", "Session not found")
            return

        def handle_edit():
            dialog.close()
            self._edit_session_by_id(session_id)

        def handle_delete():
            dialog.close()
            self._delete_sessions([session_id])

        def handle_end():
            dialog.close()
            self._end_session_by_id(session_id)

        def handle_open_purchase(purchase_id: int):
            self._open_purchase_by_id(purchase_id)

        def handle_open_redemption(redemption_id: int):
            self._open_redemption_by_id(redemption_id)

        dialog = ViewSessionDialog(
            self.facade,
            session=session,
            parent=self,
            on_edit=handle_edit,
            on_delete=handle_delete,
            on_open_purchase=handle_open_purchase,
            on_open_redemption=handle_open_redemption,
            on_end=handle_end,
        )
        dialog.exec()

    def open_session_by_id(self, session_id: int):
        self.load_data()
        found = False
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == session_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                found = True
                break
        if not found:
            QMessageBox.warning(self, "Warning", "Session not found")
            return
        self.view_session()

    def end_session(self):
        """End (close) selected session"""
        ids = self._selected_ids()
        if len(ids) != 1:
            QMessageBox.warning(self, "Warning", "Please select a single session to end")
            return

        session_id = ids[0]
        session = self.facade.get_game_session(session_id)
        if not session:
            QMessageBox.warning(self, "Warning", "Session not found")
            return

        if session.status != "Active":
            QMessageBox.information(self, "Not Active", "This session is already closed")
            return

        self._end_session_by_id(session_id)

    def _end_session_by_id(self, session_id: int):
        session = self.facade.get_game_session(session_id)
        if not session:
            QMessageBox.warning(self, "Warning", "Session not found")
            return

        dialog = EndSessionDialog(session, parent=self)

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QMessageBox.warning(self, "Invalid Entry", error)
                return
            try:
                self.facade.update_game_session(
                    session_id=session_id,
                    ending_balance=data["ending_total_sc"],
                    ending_redeemable=data["ending_redeemable_sc"],
                    end_date=data["end_date"],
                    end_time=data["end_time"],
                    notes=data["notes"],
                    status="Closed",
                    recalculate_pl=True,
                )
                dialog.accept()
                self.load_data()
                QMessageBox.information(self, "Success", "Session closed successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to close session: {e}")

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

    def _open_purchase_by_id(self, purchase_id: int):
        if self.main_window and hasattr(self.main_window, "open_purchase"):
            self.main_window.open_purchase(purchase_id)
            return
        purchase = self.facade.get_purchase(purchase_id)
        if not purchase:
            QMessageBox.warning(self, "Warning", "Purchase not found")
            return
        dialog = PurchaseViewDialog(purchase, self.facade, parent=self)
        dialog.exec()

    def _open_redemption_by_id(self, redemption_id: int):
        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            QMessageBox.warning(self, "Warning", "Redemption not found")
            return
        dialog = RedemptionViewDialog(redemption, self.facade, parent=self)
        dialog.exec()
    
    def delete_session(self):
        """Delete selected session"""
        ids = self._selected_ids()
        if not ids:
            QMessageBox.warning(self, "Warning", "Please select session(s) to delete")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete {len(ids)} session(s)?\n\n"
            "This will remove the session(s) and their P/L calculations.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._delete_sessions(ids)

    def _delete_sessions(self, ids):
        try:
            for session_id in ids:
                self.facade.delete_game_session(session_id)
            self.load_data()
            QMessageBox.information(self, "Success", "Session(s) deleted successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete session: {e}")

    def export_csv(self):
        import csv

        if not self.filtered_sessions:
            QMessageBox.information(self, "Export", "No data to export")
            return

        default_name = f"game_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Game Sessions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        users = {u.id: u.name for u in self.facade.get_all_users()}
        sites = {s.id: s.name for s in self.facade.get_all_sites()}
        game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        games = {g.id: g for g in self.facade.list_all_games()}

        headers = [
            "Date", "Time", "Site", "User", "Game Type", "Game Name",
            "Start Total", "End Total", "Start Redeemable", "End Redeemable",
            "Delta Redeemable", "Basis Consumed", "Net P/L", "Status", "Notes"
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for session in self.filtered_sessions:
                game = games.get(session.game_id)
                game_name = game.name if game else ""
                game_type = game_types.get(game.game_type_id, "") if game else ""
                writer.writerow([
                    session.session_date,
                    session.session_time,
                    sites.get(session.site_id, ""),
                    users.get(session.user_id, ""),
                    game_type,
                    game_name,
                    session.starting_balance,
                    session.ending_balance if session.status != "Active" else "",
                    session.starting_redeemable,
                    session.ending_redeemable if session.status != "Active" else "",
                    session.delta_redeem if session.status != "Active" else "",
                    session.basis_consumed if session.status != "Active" else "",
                    session.net_taxable_pl if session.status != "Active" else "",
                    session.status,
                    session.notes or "",
                ])

    def _selected_ids(self):
        selected_rows = self.table.selectionModel().selectedRows()
        ids = []
        for row in selected_rows:
            item = self.table.item(row.row(), 0)
            if item:
                ids.append(item.data(Qt.UserRole))
        return ids

    def _on_selection_changed(self):
        ids = self._selected_ids()
        has_selection = bool(ids)
        sessions_by_id = {s.id: s for s in self.sessions}
        selected_sessions = [sessions_by_id.get(i) for i in ids if i in sessions_by_id]
        has_active = any(s and s.status == "Active" for s in selected_sessions)

        self.view_button.setVisible(len(ids) == 1)
        self.end_button.setVisible(has_active)
        self.edit_button.setVisible(has_selection)
        self.delete_button.setVisible(has_selection)

    def _update_active_label(self):
        count = len([s for s in self.sessions if s.status == "Active"])
        self.active_label.setText(f"Active Sessions: {count}")

    def _clear_search(self):
        self.search_edit.clear()
        self.apply_filters()

    def clear_all_filters(self):
        self.search_edit.clear()
        self.date_filter.set_all_time()
        self.apply_filters()


class StartSessionDialog(QDialog):
    def __init__(self, facade, session=None, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.session = session
        self._game_names_by_type = {}
        self._game_lookup = {}
        self._game_types_by_id = {}
        self._games_by_id = {}

        users = self.facade.get_all_users()
        sites = self.facade.get_all_sites()
        types = self.facade.get_all_game_types()
        games = self.facade.list_all_games()

        self._user_lookup = {u.name.lower(): u for u in users}
        self._site_lookup = {s.name.lower(): s for s in sites}
        self._game_type_lookup = {t.name.lower(): t for t in types}
        self._game_types_by_id = {t.id: t for t in types}
        self._games_by_id = {g.id: g for g in games}

        for game in games:
            type_obj = self._game_types_by_id.get(game.game_type_id)
            type_name = type_obj.name if type_obj else ""
            if type_name:
                self._game_names_by_type.setdefault(type_name, []).append(game.name)
                self._game_lookup[(type_name.lower(), game.name.lower())] = game

        user_names = [u.name for u in users]
        site_names = [s.name for s in sites]
        game_types = [t.name for t in types]

        self.setWindowTitle("Edit Session" if session else "Start Session")
        self.resize(640, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        session_group = QGroupBox("Session")
        session_grid = QGridLayout(session_group)
        session_grid.setHorizontalSpacing(10)
        session_grid.setVerticalSpacing(8)
        session_grid.setColumnStretch(1, 1)
        session_grid.setColumnStretch(3, 1)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QPushButton("Today")
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)
        date_row = QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.addItems(site_names)

        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.addItems(user_names)

        session_grid.addWidget(QLabel("Date"), 0, 0)
        session_grid.addLayout(date_row, 0, 1)
        session_grid.addWidget(QLabel("Start Time"), 0, 2)
        session_grid.addLayout(time_row, 0, 3)
        session_grid.addWidget(QLabel("Site"), 1, 0)
        session_grid.addWidget(self.site_combo, 1, 1)
        session_grid.addWidget(QLabel("User"), 1, 2)
        session_grid.addWidget(self.user_combo, 1, 3)
        layout.addWidget(session_group)

        game_group = QGroupBox("Game")
        game_grid = QGridLayout(game_group)
        game_grid.setHorizontalSpacing(10)
        game_grid.setVerticalSpacing(8)
        game_grid.setColumnStretch(1, 1)
        game_grid.setColumnStretch(3, 1)

        self.game_type_combo = QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")

        self.rtp_tooltip = QLabel("")
        self.rtp_tooltip.setObjectName("HelperText")
        self.rtp_tooltip.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.rtp_tooltip.setWordWrap(True)

        game_grid.addWidget(QLabel("Game Type"), 0, 0)
        game_grid.addWidget(self.game_type_combo, 0, 1)
        game_grid.addWidget(QLabel("Game Name"), 0, 2)
        game_grid.addWidget(self.game_name_combo, 0, 3)
        game_grid.addWidget(self.rtp_tooltip, 1, 0, 1, 4)
        layout.addWidget(game_group)

        balance_group = QGroupBox("Starting Balances")
        balance_grid = QGridLayout(balance_group)
        balance_grid.setHorizontalSpacing(10)
        balance_grid.setVerticalSpacing(8)
        balance_grid.setColumnStretch(1, 1)
        balance_grid.setColumnStretch(3, 1)

        self.start_total_edit = QLineEdit()
        self.start_redeem_edit = QLineEdit()

        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.balance_label = QLabel("Balance Check")
        self.balance_label.setToolTip(balance_tooltip)
        self.balance_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.freebie_label = QLabel("")
        self.freebie_label.setWordWrap(True)
        self.freebie_label.setObjectName("InfoField")
        self.freebie_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.freebie_label.setProperty("status", "neutral")
        self.freebie_label.setToolTip(balance_tooltip)

        balance_grid.addWidget(QLabel("Starting Total SC"), 0, 0)
        balance_grid.addWidget(self.start_total_edit, 0, 1)
        balance_grid.addWidget(QLabel("Starting Redeemable"), 0, 2)
        balance_grid.addWidget(self.start_redeem_edit, 0, 3)
        balance_grid.addWidget(self.balance_label, 1, 0)
        balance_grid.addWidget(self.freebie_label, 1, 1, 1, 3)
        layout.addWidget(balance_group)

        self.notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(self.notes_group)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(self.notes_group)
        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.clear_btn = QPushButton("Clear")
        self.save_btn = QPushButton("Save")
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

    def _update_game_names(self):
        game_type = self.game_type_combo.currentText().strip()
        if not game_type:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return

        if game_type.lower() not in self._game_type_lookup:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)
            self._validate_inline()
            return

        type_key = None
        for key in self._game_names_by_type:
            if key.lower() == game_type.lower():
                type_key = key
                break
        names = list(self._game_names_by_type.get(type_key, [])) if type_key else []
        current = self.game_name_combo.currentText().strip()
        if "" not in names:
            names.insert(0, "")
        self.game_name_combo.blockSignals(True)
        self.game_name_combo.clear()
        self.game_name_combo.addItems(names)
        self.game_name_combo.lineEdit().setPlaceholderText("")
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
                for key in self._game_names_by_type:
                    if key.lower() == game_type_text.lower():
                        type_key = key
                        break
                valid_names = self._game_names_by_type.get(type_key, []) if type_key else []
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
            completer = QCompleter(combo.model())
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchStartsWith)
            completer.setCompletionMode(QCompleter.InlineCompletion)
            popup = QListView()
            popup.setStyleSheet(
                "QListView { background: #fdfdfe; color: #1e1f24; }"
                "QListView::item:selected { background: #d0dfff; color: #1e1f24; }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("Select")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _format_date_for_input(self, value):
        if not value:
            return ""
        try:
            if isinstance(value, date):
                parsed = value
            else:
                parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
            return parsed.strftime("%m/%d/%y")
        except ValueError:
            return str(value)

    def _format_time_for_input(self, time_str):
        if not time_str:
            return ""
        return str(time_str)[:5]

    def _lookup_ids(self, site_name, user_name):
        site = self._site_lookup.get(site_name.lower())
        user = self._user_lookup.get(user_name.lower())
        return (site.id if site else None, user.id if user else None)

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
            parsed_date = parse_date_input(session_date) if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.freebie_label.setText("—")
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.style().unpolish(self.freebie_label)
            self.freebie_label.style().polish(self.freebie_label)
            return

        expected_total, _expected_redeem = self.facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=parsed_date or date.today(),
            session_time=parsed_time or datetime.now().strftime("%H:%M:%S"),
        )
        site = self.facade.get_site(site_id)
        sc_rate = Decimal(str(site.sc_rate if site else 1.0))
        freebies_sc = max(0.0, float(result) - float(expected_total))
        missing_sc = max(0.0, float(expected_total) - float(result))
        freebies_dollar = float(Decimal(str(freebies_sc)) * sc_rate)
        if freebies_sc > 0:
            self.freebie_label.setProperty("status", "positive")
            self.freebie_label.setText(
                f"+ Detected {freebies_sc:.2f} SC in extra balance (${freebies_dollar:.2f})"
            )
        elif missing_sc > 0:
            self.freebie_label.setProperty("status", "negative")
            self.freebie_label.setText(
                f"- WARNING: Starting balance is {missing_sc:.2f} SC less than expected ({float(expected_total):.2f})"
            )
        else:
            self.freebie_label.setProperty("status", "neutral")
            self.freebie_label.setText(f"Matches expected balance ({float(expected_total):.2f} SC)")
        self.freebie_label.style().unpolish(self.freebie_label)
        self.freebie_label.style().polish(self.freebie_label)

    def _update_rtp_tooltip(self):
        game_name = self.game_name_combo.currentText().strip()
        game_type = self.game_type_combo.currentText().strip()
        if not game_name or not game_type:
            self.rtp_tooltip.setText("")
            return
        game = self._game_lookup.get((game_type.lower(), game_name.lower()))
        if game and game.rtp is not None:
            exp_str = f"{float(game.rtp):.2f}%"
            self.rtp_tooltip.setText(f"Exp RTP: {exp_str} / Act RTP: —")
        else:
            self.rtp_tooltip.setText("")

    def _load_session(self):
        self.date_edit.setText(self._format_date_for_input(self.session.session_date))
        self.time_edit.setText(self._format_time_for_input(self.session.session_time))

        user_name = None
        for name, user_obj in self._user_lookup.items():
            if user_obj.id == self.session.user_id:
                user_name = user_obj.name
                break
        site_name = None
        for name, site_obj in self._site_lookup.items():
            if site_obj.id == self.session.site_id:
                site_name = site_obj.name
                break
        if user_name:
            self.user_combo.setCurrentText(user_name)
        if site_name:
            self.site_combo.setCurrentText(site_name)

        game = self._games_by_id.get(self.session.game_id)
        game_type_name = None
        if game:
            type_obj = self._game_types_by_id.get(game.game_type_id)
            game_type_name = type_obj.name if type_obj else None
        if game_type_name:
            self.game_type_combo.blockSignals(True)
            self.game_type_combo.setCurrentText(game_type_name)
            self.game_type_combo.blockSignals(False)
        else:
            self.game_type_combo.blockSignals(True)
            self.game_type_combo.setCurrentIndex(-1)
            if self.game_type_combo.isEditable():
                self.game_type_combo.setEditText("")
            self.game_type_combo.blockSignals(False)

        if game and game.name:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.setCurrentText(game.name)
            self.game_name_combo.blockSignals(False)
        else:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.clear()
            self.game_name_combo.setEditText("")
            if self.game_name_combo.lineEdit() is not None:
                self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            self.game_name_combo.blockSignals(False)

        self._update_game_names()

        self.start_total_edit.setText(str(self.session.starting_balance))
        start_redeem = self.session.starting_redeemable
        self.start_redeem_edit.setText(str(start_redeem))
        self.notes_edit.setPlainText(self.session.notes or "")
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

        game = None
        if game_name:
            game = self._game_lookup.get((game_type.lower(), game_name.lower())) if game_type else None
            if not game:
                return None, "Please select a valid Game Name for the chosen type."
        game_id = game.id if game else None

        user = self._user_lookup.get(user_name.lower())
        site = self._site_lookup.get(site_name.lower())
        if not user or not site:
            return None, "Please select a valid User and Site."

        notes = self.notes_edit.toPlainText().strip()

        return {
            "session_date": sdate,
            "start_time": stime,
            "user_id": user.id,
            "site_id": site.id,
            "game_id": game_id,
            "starting_total_sc": Decimal(str(start_total)),
            "starting_redeemable_sc": Decimal(str(start_redeem)),
            "notes": notes,
        }, None


class EditSessionDialog(StartSessionDialog):
    def __init__(self, facade, session, parent=None):
        super().__init__(facade, session=session, parent=parent)


class EditClosedSessionDialog(StartSessionDialog):
    def __init__(self, facade, session, parent=None):
        self.end_date_edit = None
        self.end_time_edit = None
        self.end_total_edit = None
        self.end_redeem_edit = None
        super().__init__(facade, session=session, parent=parent)
        self.setWindowTitle("Edit Closed Session")

        end_group = QGroupBox("Ending Balances")
        end_grid = QGridLayout(end_group)
        end_grid.setHorizontalSpacing(10)
        end_grid.setVerticalSpacing(8)
        end_grid.setColumnStretch(1, 1)
        end_grid.setColumnStretch(3, 1)

        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("MM/DD/YY")
        self.end_time_edit = QLineEdit()
        self.end_time_edit.setPlaceholderText("HH:MM")
        self.end_total_edit = QLineEdit()
        self.end_redeem_edit = QLineEdit()

        end_grid.addWidget(QLabel("End Date"), 0, 0)
        end_grid.addWidget(self.end_date_edit, 0, 1)
        end_grid.addWidget(QLabel("End Time"), 0, 2)
        end_grid.addWidget(self.end_time_edit, 0, 3)
        end_grid.addWidget(QLabel("Ending Total SC"), 1, 0)
        end_grid.addWidget(self.end_total_edit, 1, 1)
        end_grid.addWidget(QLabel("Ending Redeemable"), 1, 2)
        end_grid.addWidget(self.end_redeem_edit, 1, 3)

        layout = self.layout()
        insert_at = layout.indexOf(self.notes_group) if self.notes_group else max(layout.count() - 2, 0)
        layout.insertWidget(insert_at, end_group)

        end_date = session.end_date or session.session_date
        if end_date:
            self.end_date_edit.setText(end_date.strftime("%m/%d/%y"))
        end_time = session.end_time or session.session_time
        if end_time:
            self.end_time_edit.setText(end_time[:5])
        self.end_total_edit.setText(str(session.ending_balance or ""))
        self.end_redeem_edit.setText(str(session.ending_redeemable or ""))

        self.end_date_edit.textChanged.connect(self._validate_inline)
        self.end_time_edit.textChanged.connect(self._validate_inline)
        self.end_total_edit.textChanged.connect(self._validate_inline)
        self.end_redeem_edit.textChanged.connect(self._validate_inline)
        self._validate_inline()

    def _validate_inline(self):
        super()._validate_inline()
        if not all(
            (
                self.end_date_edit,
                self.end_time_edit,
                self.end_total_edit,
                self.end_redeem_edit,
            )
        ):
            return

        end_date_text = self.end_date_edit.text().strip()
        if not end_date_text:
            self._set_invalid(self.end_date_edit, "End date is required.")
        else:
            try:
                parse_date_input(end_date_text)
                self._set_valid(self.end_date_edit)
            except ValueError:
                self._set_invalid(self.end_date_edit, "Enter a valid end date.")

        end_time_text = self.end_time_edit.text().strip()
        if not is_valid_time_24h(end_time_text, allow_blank=True):
            self._set_invalid(self.end_time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.end_time_edit)

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

    def collect_data(self):
        data, error = super().collect_data()
        if error:
            return None, error

        end_date_text = self.end_date_edit.text().strip()
        if not end_date_text:
            return None, "Please enter an end date."
        try:
            end_date = parse_date_input(end_date_text)
        except ValueError:
            return None, "Please enter a valid end date."

        end_time_text = self.end_time_edit.text().strip()
        if end_time_text and not is_valid_time_24h(end_time_text, allow_blank=False):
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            end_time = parse_time_input(end_time_text)
        except ValueError:
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS)."

        end_total_text = self.end_total_edit.text().strip()
        if not end_total_text:
            return None, "Please enter Ending Total SC."
        valid, result = validate_currency(end_total_text)
        if not valid:
            return None, result
        end_total = result

        end_redeem_text = self.end_redeem_edit.text().strip()
        if not end_redeem_text:
            return None, "Please enter Ending Redeemable SC."
        valid, result = validate_currency(end_redeem_text)
        if not valid:
            return None, result
        end_redeem = result

        if end_redeem > end_total:
            return None, "Ending Redeemable SC cannot exceed Ending Total SC."

        data.update(
            {
                "end_date": end_date,
                "end_time": end_time,
                "ending_total_sc": Decimal(str(end_total)),
                "ending_redeemable_sc": Decimal(str(end_redeem)),
            }
        )
        return data, None


class ViewSessionDialog(QDialog):
    def __init__(
        self,
        facade,
        session,
        parent=None,
        on_open_session=None,
        on_open_purchase=None,
        on_open_redemption=None,
        on_edit=None,
        on_delete=None,
        on_view_in_daily=None,
        on_end=None,
    ):
        super().__init__(parent)
        self.facade = facade
        self.session = session
        self._on_open_session = on_open_session
        self.on_open_purchase = on_open_purchase
        self.on_open_redemption = on_open_redemption
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_view_in_daily = on_view_in_daily
        self._on_end = on_end
        self.setWindowTitle("View Game Session")
        self.resize(750, 650)

        self.linked_purchases = self._get_linked_purchases()
        self.linked_redemptions = self._get_linked_redemptions()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        btn_row = QHBoxLayout()

        status = self.session.status or "Active"
        is_active = status == "Active"

        if is_active and self._on_end:
            end_session_btn = QPushButton("⏹️ End Session")
            end_session_btn.setObjectName("PrimaryButton")
            btn_row.addWidget(end_session_btn)

        if self._on_delete:
            delete_btn = QPushButton("🗑️ Delete")
            btn_row.addWidget(delete_btn)

        btn_row.addStretch(1)

        view_daily_btn = None
        if self._on_edit:
            edit_btn = QPushButton("✏️ Edit")
            btn_row.addWidget(edit_btn)
        if self._on_view_in_daily and not is_active:
            view_daily_btn = QPushButton("📅 View in Daily Sessions")
            btn_row.addWidget(view_daily_btn)
        if self._on_open_session:
            open_btn = QPushButton("🎮 View in Game Sessions")
            btn_row.addWidget(open_btn)
        close_btn = QPushButton("Close")
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if is_active and self._on_end:
            end_session_btn.clicked.connect(self._on_end)
        if self._on_delete:
            delete_btn.clicked.connect(self._on_delete)
        if self._on_edit:
            edit_btn.clicked.connect(self._on_edit)
        if view_daily_btn:
            view_daily_btn.clicked.connect(self._on_view_in_daily)
        if self._on_open_session:
            def _handle_open_session():
                self._on_open_session()
                self.accept()

            open_btn.clicked.connect(_handle_open_session)
        close_btn.clicked.connect(self.accept)

    def _to_datetime(self, date_value, time_value):
        if not date_value:
            return None
        try:
            if isinstance(date_value, date):
                dval = date_value
            else:
                dval = datetime.strptime(str(date_value), "%Y-%m-%d").date()
        except ValueError:
            return None
        tval = "00:00:00"
        if time_value:
            try:
                tval = parse_time_input(str(time_value))
            except ValueError:
                tval = "00:00:00"
        return datetime.strptime(f"{dval} {tval}", "%Y-%m-%d %H:%M:%S")

    def _get_linked_purchases(self):
        events = self.facade.get_linked_events_for_session(self.session.id)
        return events.get("purchases", [])

    def _get_linked_redemptions(self):
        events = self.facade.get_linked_events_for_session(self.session.id)
        return events.get("redemptions", [])

    def _format_date(self, value):
        if not value:
            return "—"
        try:
            if isinstance(value, date):
                return value.strftime("%m/%d/%y")
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
        except ValueError:
            return str(value)

    def _create_details_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        users = {u.id: u.name for u in self.facade.get_all_users()}
        sites = {s.id: s.name for s in self.facade.get_all_sites()}
        game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        games = {g.id: g for g in self.facade.list_all_games()}

        def build_group(title):
            group = QGroupBox(title)
            group_layout = QGridLayout(group)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(8)
            group_layout.setColumnStretch(1, 1)
            group_layout.setColumnStretch(3, 1)
            return group, group_layout

        def add_pair(grid, row, col, label_text, value):
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            value_label = QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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

        game = games.get(self.session.game_id)
        game_name = game.name if game else "—"
        game_type = game_types.get(game.game_type_id, "—") if game else "—"
        rtp_display = f"{float(game.rtp):.2f}%" if game and game.rtp is not None else "—"

        is_active = not self.session.status or self.session.status == "Active"
        start_total = self.session.starting_balance
        end_total = None if is_active else self.session.ending_balance
        start_redeem = self.session.starting_redeemable
        end_redeem = None if is_active else self.session.ending_redeemable
        delta_total = None if is_active else self.session.delta_total
        if not is_active and delta_total is None and start_total is not None and end_total is not None:
            delta_total = float(end_total or 0) - float(start_total or 0)
        delta_redeem = None if is_active else self.session.delta_redeem
        if not is_active and delta_redeem is None and start_redeem is not None and end_redeem is not None:
            delta_redeem = float(end_redeem or 0) - float(start_redeem or 0)
        basis_val = None if is_active else (
            self.session.basis_consumed if self.session.basis_consumed is not None else self.session.session_basis
        )
        net_val = None if is_active else self.session.net_taxable_pl
        if net_val is None and not is_active:
            net_val = 0.0
        net_display = f"+${float(net_val):.2f}" if net_val is not None and float(net_val) >= 0 else (
            f"${float(net_val):.2f}" if net_val is not None else "—"
        )

        session_group, session_grid = build_group("Session")
        add_pair(
            session_grid,
            0,
            0,
            "Start",
            format_dt(self.session.session_date, self.session.session_time),
        )
        end_value = format_dt(self.session.end_date, self.session.end_time) if self.session.end_date else "—"
        add_pair(session_grid, 0, 1, "End", end_value)
        add_pair(session_grid, 1, 0, "Site", sites.get(self.session.site_id, "—"))
        add_pair(session_grid, 1, 1, "User", users.get(self.session.user_id, "—"))
        add_pair(session_grid, 2, 0, "Status", self.session.status or "Active")
        layout.addWidget(session_group)

        game_group, game_grid = build_group("Game")
        add_pair(game_grid, 0, 0, "Game Type", game_type or "—")
        add_pair(game_grid, 0, 1, "Game Name", game_name or "—")
        add_pair(game_grid, 1, 0, "Wager Amount", "—")
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
        add_pair(balance_grid, 3, 1, "Net P/L", net_display)
        layout.addWidget(balance_group)

        notes_group = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_group)
        notes_value = self.session.notes or ""
        if notes_value:
            notes_edit = QPlainTextEdit()
            notes_edit.setObjectName("NotesField")
            notes_edit.setReadOnly(True)
            notes_edit.setFocusPolicy(Qt.NoFocus)
            notes_edit.setTextInteractionFlags(Qt.NoTextInteraction)
            notes_edit.setPlainText(notes_value)
            notes_edit.setMinimumHeight(notes_edit.fontMetrics().lineSpacing() * 4 + 16)
            notes_layout.addWidget(notes_edit)
        else:
            notes_field = QLabel("—")
            notes_field.setObjectName("InfoField")
            notes_field.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            notes_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            fixed_height = max(notes_field.sizeHint().height(), 26)
            notes_field.setFixedHeight(fixed_height)
            notes_layout.addWidget(notes_field)
        layout.addWidget(notes_group)
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        purchases_group = QGroupBox("Purchases Contributing to Basis (Before/During)")
        purchases_layout = QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        if not self.linked_purchases:
            note = QLabel("No purchases contributed basis before or during this session.")
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.purchases_table = QTableWidget(0, 5)
            self.purchases_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Amount", "SC Received", "View"]
            )
            self.purchases_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.purchases_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.purchases_table.setSelectionMode(QTableWidget.SingleSelection)
            self.purchases_table.setAlternatingRowColors(True)
            self.purchases_table.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            header = self.purchases_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.purchases_table.verticalHeader().setVisible(False)
            self.purchases_table.setColumnWidth(0, 90)
            self.purchases_table.setColumnWidth(1, 60)
            self.purchases_table.setColumnWidth(2, 90)
            self.purchases_table.setColumnWidth(3, 90)
            self.purchases_table.setColumnWidth(4, 70)
            purchases_layout.addWidget(self.purchases_table)
            self._populate_purchases_table(self.linked_purchases)
        layout.addWidget(purchases_group, 1)

        redemptions_group = QGroupBox("Redemptions Affecting This Session")
        redemptions_layout = QVBoxLayout(redemptions_group)
        redemptions_layout.setContentsMargins(8, 10, 8, 8)
        if not self.linked_redemptions:
            note = QLabel("No redemptions affected this session.")
            note.setWordWrap(True)
            redemptions_layout.addWidget(note)
        else:
            self.redemptions_table = QTableWidget(0, 5)
            self.redemptions_table.setHorizontalHeaderLabels(
                ["Date", "Time", "Amount", "Method", "View Redemption"]
            )
            self.redemptions_table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.redemptions_table.setSelectionBehavior(QTableWidget.SelectRows)
            self.redemptions_table.setSelectionMode(QTableWidget.SingleSelection)
            self.redemptions_table.setAlternatingRowColors(True)
            self.redemptions_table.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
            header = self.redemptions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.redemptions_table.verticalHeader().setVisible(False)
            self.redemptions_table.setColumnWidth(0, 90)
            self.redemptions_table.setColumnWidth(1, 60)
            self.redemptions_table.setColumnWidth(2, 100)
            self.redemptions_table.setColumnWidth(3, 120)
            self.redemptions_table.setColumnWidth(4, 130)
            redemptions_layout.addWidget(self.redemptions_table)
            self._populate_redemptions_table(self.linked_redemptions)
        layout.addWidget(redemptions_group, 1)
        return widget

    def _populate_purchases_table(self, purchases):
        self.purchases_table.setRowCount(len(purchases))
        for row_idx, purchase in enumerate(purchases):
            date_display = self._format_date(purchase.purchase_date) if purchase.purchase_date else "—"
            time_display = purchase.purchase_time[:5] if purchase.purchase_time else "—"
            amount = format_currency(purchase.amount)
            sc_received = f"{float(purchase.sc_received or 0.0):.2f}"

            values = [date_display, time_display, amount, sc_received]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx in (2, 3):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.purchases_table.setItem(row_idx, col_idx, item)

            view_btn = QPushButton("View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(120)
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase.id: self._open_purchase(pid)
            )
            view_container = QWidget()
            view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            view_layout = QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, Qt.AlignCenter)
            self.purchases_table.setCellWidget(row_idx, 4, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self, redemptions):
        self.redemptions_table.setRowCount(len(redemptions))
        for row_idx, redemption in enumerate(redemptions):
            date_display = self._format_date(redemption.redemption_date) if redemption.redemption_date else "—"
            time_display = (redemption.redemption_time or "00:00:00")[:5]
            amount = format_currency(redemption.amount)

            is_total_loss = float(redemption.amount) == 0
            method_display = "Loss" if is_total_loss else (getattr(redemption, "method_name", None) or "—")

            values = [date_display, time_display, amount, method_display]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx == 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.redemptions_table.setItem(row_idx, col_idx, item)

            view_btn = QPushButton("View Redemption")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(120)
            view_btn.clicked.connect(
                lambda _checked=False, rid=redemption.id: self._open_redemption(rid)
            )
            view_container = QWidget()
            view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            view_layout = QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, Qt.AlignCenter)
            self.redemptions_table.setCellWidget(row_idx, 4, view_container)
            self.redemptions_table.setRowHeight(
                row_idx,
                max(self.redemptions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_redemption(self, redemption_id):
        if not self.on_open_redemption:
            QMessageBox.information(
                self, "Redemptions Unavailable", "Redemption view is not available here."
            )
            return
        self.accept()
        self.on_open_redemption(redemption_id)


class EndSessionDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("End Game Session")
        self.resize(640, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        start_total = float(session.starting_balance or 0.0)
        start_redeem = float(session.starting_redeemable or 0.0)

        info = QLabel(
            f"Starting Total SC: {start_total:.2f} | Starting Redeemable: {start_redeem:.2f}"
        )
        layout.addWidget(info)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QPushButton("Today")
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)
        date_row = QHBoxLayout()
        date_row.setSpacing(8)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.calendar_btn)
        date_row.addWidget(self.today_btn)

        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)
        time_row = QHBoxLayout()
        time_row.setSpacing(8)
        time_row.addWidget(self.time_edit, 1)
        time_row.addWidget(self.now_btn)

        self.end_total_edit = QLineEdit()
        self.end_redeem_edit = QLineEdit()
        self.wager_edit = QLineEdit()

        self.locked_label = QLabel("—")
        self.locked_label.setObjectName("InfoField")
        self.locked_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.locked_label.setProperty("status", "neutral")
        self.pnl_label = QLabel("—")
        self.pnl_label.setObjectName("InfoField")
        self.pnl_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.pnl_label.setProperty("status", "neutral")

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlaceholderText("Notes...")
        self.notes_edit.setMinimumHeight(self.notes_edit.fontMetrics().lineSpacing() * 3 + 12)

        form.addWidget(QLabel("End Date"), 0, 0)
        form.addLayout(date_row, 0, 1)
        form.addWidget(QLabel("End Time"), 1, 0)
        form.addLayout(time_row, 1, 1)
        form.addWidget(QLabel("Ending Total SC"), 2, 0)
        form.addWidget(self.end_total_edit, 2, 1)
        form.addWidget(QLabel("Ending Redeemable"), 3, 0)
        form.addWidget(self.end_redeem_edit, 3, 1)
        form.addWidget(QLabel("Wager Amount"), 4, 0)
        form.addWidget(self.wager_edit, 4, 1)
        locked_title = QLabel("Locked SC")
        locked_title.setToolTip("Total SC minus Redeemable SC")
        locked_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.addWidget(locked_title, 5, 0)
        form.addWidget(self.locked_label, 5, 1)
        redeem_change_label = QLabel("Redeemable Change")
        redeem_change_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.addWidget(redeem_change_label, 6, 0)
        form.addWidget(self.pnl_label, 6, 1)
        notes_label = QLabel("Notes")
        notes_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.addWidget(notes_label, 7, 0)
        form.addWidget(self.notes_edit, 7, 1)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("End Session")
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
        self._validate_inline()

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _pick_date(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("Select")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QDialog.Accepted:
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
            self._set_invalid(self.date_edit, "End Date is required.")
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
                self._set_invalid(self.wager_edit, "Enter a valid amount (max 2 decimals).")
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
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS)."

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
        wager_text = self.wager_edit.text().strip()
        if wager_text:
            valid, result = validate_currency(wager_text)
            if not valid:
                return None, result
            wager_amount = result

        notes = self.notes_edit.toPlainText().strip()

        return {
            "end_date": end_date,
            "end_time": end_time,
            "ending_total_sc": Decimal(str(end_total)),
            "ending_redeemable_sc": Decimal(str(end_redeem)),
            "wager_amount": wager_amount,
            "notes": notes,
        }, None
