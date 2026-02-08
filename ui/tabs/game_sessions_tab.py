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
    QGridLayout, QApplication, QCheckBox, QSpacerItem, QMenu
)
from PySide6.QtCore import Qt, QTime, QDate, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from ui.date_filter_widget import DateFilterWidget
from ui.tabs.purchases_tab import PurchaseViewDialog
from ui.tabs.redemptions_tab import RedemptionViewDialog
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from ui.input_parsers import parse_date_input, parse_time_input


TIME_24H_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d(?:\:[0-5]\d)?$")


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

        year_start = date(date.today().year, 1, 1)
        self.date_filter = DateFilterWidget(
            default_start=year_start,
            default_end=date.today(),
        )
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
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setMinimumSectionSize(40)
        self.table.verticalHeader().setVisible(False)
        self.table.itemDoubleClicked.connect(self.view_session)
        
        # Enable custom context menu for spreadsheet UX
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Add spreadsheet stats bar
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)
        
        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.load_data)
        
        # Set up keyboard shortcuts for spreadsheet UX
        copy_shortcut = QShortcut(QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)

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
    
    def refresh_data(self):
        """Standardized refresh method for global refresh system (Issue #9)."""
        self.load_data()
    
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
            # Resolve names the same way _populate_table does (so search matches what's displayed)
            users = {u.id: u.name for u in self.facade.get_all_users()}
            sites = {s.id: s.name for s in self.facade.get_all_sites()}
            games = {g.id: g for g in self.facade.list_all_games()}
            
            filtered = []
            for s in rows:
                user_name = users.get(s.user_id, '')
                site_name = sites.get(s.site_id, '')
                game = games.get(s.game_id)
                game_name = game.name if game else ''
                
                parts = [
                    str(s.session_date),
                    user_name,
                    site_name,
                    game_name,
                    s.status or '',
                    str(s.starting_balance),
                    str(s.ending_balance),
                    str(s.starting_redeemable),
                    str(s.ending_redeemable),
                    str(s.delta_total) if s.delta_total is not None else '',
                    str(s.delta_redeem) if s.delta_redeem is not None else '',
                    str(s.basis_consumed) if s.basis_consumed is not None else '',
                    str(s.net_taxable_pl) if s.net_taxable_pl is not None else '',
                    s.notes or '',
                ]
                haystack = " ".join(parts).lower()
                if search_text in haystack:
                    filtered.append(s)
            rows = filtered

        rows.sort(key=lambda s: (s.session_date, s.session_time or "00:00:00"), reverse=True)
        return rows

    def _populate_table(self, rows):
        try:
            users = {u.id: u.name for u in self.facade.get_all_users()}
            sites = {s.id: s.name for s in self.facade.get_all_sites()}
            games = {g.id: g for g in self.facade.list_all_games()}

            sorting_was_enabled = self.table.isSortingEnabled()
            self.table.setSortingEnabled(False)
            self.table.setUpdatesEnabled(False)
            self.table.blockSignals(True)
            try:
                self.table.clearContents()
                self.table.setRowCount(len(rows))

                for row, session in enumerate(rows):
                    time_val = session.session_time or "00:00:00"
                    if time_val and len(time_val) > 5:
                        time_val = time_val
                    date_time = f"{session.session_date} {time_val}".strip()
                    
                    # Add multi-day indicator if session spans multiple days
                    if session.end_date and session.end_date != session.session_date:
                        date_time += " (+1d)"

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

            finally:
                self.table.blockSignals(False)
                self.table.setUpdatesEnabled(True)

            if getattr(self, "table_filter", None) is not None and self.table_filter.sort_column is not None:
                self.table_filter.sort_by_column(self.table_filter.sort_column, self.table_filter.sort_order)
            else:
                self.table.setSortingEnabled(sorting_was_enabled)
                header = self.table.horizontalHeader()
                if header is not None:
                    header.setSortIndicatorShown(False)
            self.table.resizeColumnToContents(0)
            self.table_filter.apply_filters()
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
                    game_type_id=data["game_type_id"],
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

        # Check if editing could affect subsequent redemptions (using service layer)
        impact = self.facade.game_session_service.get_deletion_impact(session_id)
        if impact:
            reply = QMessageBox.question(
                self, "Edit May Affect Redemptions",
                f"⚠️ This session has subsequent activity:\n\n{impact}\n\n"
                "If you change the session date/time or ending balance, "
                "subsequent redemptions may temporarily exceed expected balance.\n\n"
                "Continue with edit?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
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
                    "game_type_id": data["game_type_id"],
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
                            "wager_amount": Decimal(str(data.get("wager_amount") or 0)),
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

        def handle_view_in_daily():
            if not self.main_window or not hasattr(self.main_window, "daily_sessions_tab"):
                return
            index = getattr(self.main_window, "_tab_index", {}).get("daily_sessions", 3)
            self.main_window.tab_bar.setCurrentIndex(index)
            daily_tab = self.main_window.daily_sessions_tab
            if hasattr(daily_tab, "find_and_select_session"):
                QTimer.singleShot(0, lambda: daily_tab.find_and_select_session(session_id))

        dialog = ViewSessionDialog(
            self.facade,
            session=session,
            parent=self,
            on_edit=handle_edit,
            on_delete=handle_delete,
            on_open_purchase=handle_open_purchase,
            on_open_redemption=handle_open_redemption,
            on_view_in_daily=handle_view_in_daily,
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

        dialog = EndSessionDialog(self.facade, session, parent=self)

        def open_prefilled_next_session_dialog(ending_total_sc: Decimal, ending_redeemable_sc: Decimal) -> None:
            start_dialog = StartSessionDialog(self.facade, parent=self)

            user = None
            site = None
            try:
                user = self.facade.get_user(session.user_id)
                site = self.facade.get_site(session.site_id)
            except Exception:
                user = None
                site = None

            if user and getattr(user, "name", None):
                start_dialog.user_combo.setCurrentText(user.name)
            if site and getattr(site, "name", None):
                start_dialog.site_combo.setCurrentText(site.name)

            start_dialog.start_total_edit.setText(str(ending_total_sc))
            start_dialog.start_redeem_edit.setText(str(ending_redeemable_sc))

            # Force explicit game selection for the next session.
            start_dialog.game_type_combo.blockSignals(True)
            start_dialog.game_type_combo.setCurrentIndex(-1)
            if start_dialog.game_type_combo.isEditable():
                start_dialog.game_type_combo.setEditText("")
            start_dialog.game_type_combo.blockSignals(False)

            start_dialog.game_name_combo.blockSignals(True)
            start_dialog.game_name_combo.clear()
            start_dialog.game_name_combo.setEditText("")
            if start_dialog.game_name_combo.lineEdit() is not None:
                start_dialog.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")
            start_dialog.game_name_combo.blockSignals(False)

            start_dialog._update_game_names()
            start_dialog._update_balance_check()
            start_dialog.game_type_combo.setFocus()

            def handle_start_save():
                data, error = start_dialog.collect_data()
                if error:
                    QMessageBox.warning(self, "Invalid Entry", error)
                    return
                try:
                    self.facade.create_game_session(
                        user_id=data["user_id"],
                        site_id=data["site_id"],
                        game_id=data["game_id"],
                        game_type_id=data["game_type_id"],
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
                    start_dialog.accept()
                    self.load_data()
                    QMessageBox.information(self, "Success", "Session started successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to start session: {e}")

            start_dialog.save_btn.clicked.connect(handle_start_save)
            start_dialog.exec()

        def handle_close(then_start_new: bool):
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
                    wager_amount=Decimal(str(data["wager_amount"] or 0)),
                    notes=data["notes"],
                    status="Closed",
                    recalculate_pl=True,
                )
                dialog.accept()
                self.load_data()
                if then_start_new:
                    open_prefilled_next_session_dialog(data["ending_total_sc"], data["ending_redeemable_sc"])
                else:
                    QMessageBox.information(self, "Success", "Session closed successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to close session: {e}")

        dialog.save_btn.clicked.connect(lambda: handle_close(False))
        if hasattr(dialog, "end_and_start_btn"):
            dialog.end_and_start_btn.clicked.connect(lambda: handle_close(True))
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

        # For bulk operations (3+), show concise warning
        # For smaller operations, show detailed impact
        is_bulk = len(ids) >= 3
        
        if is_bulk:
            # Get summary info for bulk delete
            affected_pairs = set()
            closed_count = 0
            for session_id in ids:
                try:
                    session = self.facade.get_game_session(session_id)
                    if session:
                        affected_pairs.add((session.site_id, session.user_id))
                        if session.status == "Closed":
                            closed_count += 1
                except:
                    pass
            
            confirm_msg = f"⚠️ BULK DELETE WARNING ⚠️\n\n"
            confirm_msg += f"You are about to delete {len(ids)} session(s):\n"
            confirm_msg += f"• {closed_count} closed session(s) with P/L calculations\n"
            confirm_msg += f"• Affecting {len(affected_pairs)} user/site pair(s)\n\n"
            confirm_msg += "This will:\n"
            confirm_msg += "• Remove all session records and P/L calculations\n"
            confirm_msg += "• Trigger recalculation for affected pairs\n"
            confirm_msg += "• May affect subsequent redemption validations\n\n"
            confirm_msg += "Consider using Tools > Recalculate for data fixes instead.\n\n"
            confirm_msg += "Are you sure you want to proceed?"
        else:
            # Check detailed impact for small deletes
            warning_messages = []
            for session_id in ids:
                impact = self.facade.game_session_service.get_deletion_impact(session_id)
                if impact:
                    warning_messages.append(impact)
            
            if len(ids) == 1:
                session = self.facade.get_game_session(ids[0])
                if session:
                    site = self.facade.get_site(session.site_id)
                    user = self.facade.get_user(session.user_id)
                    confirm_msg = f"Delete session for {site.name if site else 'Unknown'} / {user.name if user else 'Unknown'}?\n\n"
                    confirm_msg += f"Date: {session.session_date} at {session.session_time}\n"
                    if session.status == "Closed":
                        confirm_msg += f"P/L: ${float(session.profit_loss or 0):,.2f}\n"
                        confirm_msg += f"Ending Balance: {float(session.ending_balance or 0):,.2f} SC\n"
                else:
                    confirm_msg = "Are you sure you want to delete this session?\n"
            else:
                confirm_msg = f"Are you sure you want to delete {len(ids)} session(s)?\n\n"
                confirm_msg += "This will remove the session(s) and their P/L calculations."
            
            if warning_messages:
                confirm_msg += "\n\n⚠️ DELETION IMPACT:\n\n" + "\n\n".join(warning_messages)
                confirm_msg += "\n\nTo complete your changes:\n"
                confirm_msg += "1. Delete this session (continue below)\n"
                confirm_msg += "2. Add a replacement session showing the correct balance\n"
                confirm_msg += "3. Recalculation will automatically fix all links and validations"
            else:
                # No specific impact detected, but still inform user
                confirm_msg += "\n\nThis will trigger recalculation for the affected user/site pair."
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            confirm_msg,
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._delete_sessions(ids)
    
    def _delete_sessions(self, ids):
        try:
            # Use bulk delete if available, otherwise fall back to individual deletes
            if hasattr(self.facade, 'delete_game_sessions_bulk'):
                self.facade.delete_game_sessions_bulk(ids)
            else:
                for session_id in ids:
                    self.facade.delete_game_session(session_id)
            self.load_data()
            QMessageBox.information(self, "Success", "Session(s) deleted successfully!")
        except Exception as e:
            import traceback
            # Show error in a custom dialog that's scrollable and limited in size
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton
            dialog = QDialog(self)
            dialog.setWindowTitle("Delete Error")
            dialog.setMinimumWidth(600)
            dialog.setMinimumHeight(400)
            dialog.setMaximumHeight(600)
            layout = QVBoxLayout(dialog)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(f"Failed to delete session(s):\n\n{str(e)}\n\n{traceback.format_exc()}")
            layout.addWidget(text_edit)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            dialog.exec()


    def export_csv(self):
        import csv

        if self.table.rowCount() == 0:
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

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
            writer.writerow(headers)
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue
                row_values = []
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_values.append(item.text() if item else "")
                writer.writerow(row_values)

    def _selected_ids(self):
        selected_row_numbers = self._get_selected_row_numbers()
        ids = []
        for row in selected_row_numbers:
            item = self.table.item(row, 0)
            if item:
                ids.append(item.data(Qt.UserRole))
        return ids
    
    def _get_selected_row_numbers(self):
        """Get unique row numbers that have any selected cells"""
        selected_indexes = self.table.selectedIndexes()
        return sorted(set(index.row() for index in selected_indexes))

    def _on_selection_changed(self):
        # Update stats bar
        grid = SpreadsheetUXController.extract_selection_grid(self.table)
        stats = SpreadsheetUXController.compute_stats(grid)
        self.stats_bar.update_stats(stats)
        
        ids = self._selected_ids()
        has_selection = bool(ids)
        sessions_by_id = {s.id: s for s in self.sessions}
        selected_sessions = [sessions_by_id.get(i) for i in ids if i in sessions_by_id]
        has_active = any(s and s.status == "Active" for s in selected_sessions)

        single_selected = len(ids) == 1
        self.view_button.setVisible(single_selected)
        self.end_button.setVisible(single_selected and has_active)
        self.edit_button.setVisible(single_selected)
        self.delete_button.setVisible(has_selection)

    def _update_active_label(self):
        count = len([s for s in self.sessions if s.status == "Active"])
        self.active_label.setText(f"Active Sessions: {count}")

    def _clear_search(self):
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        self.apply_filters()

    def clear_all_filters(self):
        self.search_edit.clear()
        self.date_filter.set_all_time()
        self.table.clearSelection()
        self._on_selection_changed()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()
        self.apply_filters()
    
    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        grid = SpreadsheetUXController.extract_selection_grid(self.table)
        SpreadsheetUXController.copy_to_clipboard(grid)
    
    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        grid = SpreadsheetUXController.extract_selection_grid(self.table, include_headers=True)
        SpreadsheetUXController.copy_to_clipboard(grid)
    
    def _show_context_menu(self, position):
        """Show context menu for table"""
        if not self.table.selectionModel().hasSelection():
            return
        
        menu = QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))


class StartSessionDialog(QDialog):
    """Modern session dialog with streamlined sectioned layout"""
    
    def __init__(self, facade, session=None, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.session = session
        self._time_edited = False
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
        self.setMinimumWidth(750)
        # Notes are collapsible; compute tight/expanded heights after load.
        self._min_height_no_notes = 0
        self._min_height_with_notes = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setContentsMargins(10, 10, 10, 10)

        # Initialize widgets
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QPushButton("Today")
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(self._pick_date)

        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM:SS")
        self.now_btn = QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)

        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.lineEdit().setPlaceholderText("Choose...")
        self.user_combo.addItems(user_names)

        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.lineEdit().setPlaceholderText("Choose...")
        self.site_combo.addItems(site_names)

        self.game_type_combo = QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.lineEdit().setPlaceholderText("Choose...")
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")

        # RTP Display (value label, not input)
        self.rtp_display = QLabel("—")
        self.rtp_display.setObjectName("ValueChip")
        self.rtp_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.rtp_display.setFixedHeight(28)

        self.start_total_edit = QLineEdit()
        self.start_total_edit.setPlaceholderText("0.00")
        
        self.start_redeem_edit = QLineEdit()
        self.start_redeem_edit.setPlaceholderText("0.00")

        # Balance Check Display (value label, not input)
        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.balance_check_display = QLabel("—")
        self.balance_check_display.setObjectName("ValueChip")
        self.balance_check_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.balance_check_display.setFixedHeight(28)
        self.balance_check_display.setWordWrap(True)
        self.balance_check_display.setProperty("status", "neutral")
        self.balance_check_display.setToolTip(balance_tooltip)

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Date/Time section (no header, compact like Add Purchase)
        datetime_section = QWidget()
        datetime_section.setObjectName("SectionBackground")
        datetime_layout = QHBoxLayout(datetime_section)
        datetime_layout.setContentsMargins(12, 10, 12, 10)
        datetime_layout.setSpacing(12)
        
        date_label = QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(date_label)
        
        # Date field with embedded calendar button
        date_container = QWidget()
        date_layout = QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(4)
        self.date_edit.setFixedWidth(110)
        date_layout.addWidget(self.date_edit)
        date_layout.addWidget(self.calendar_btn)
        datetime_layout.addWidget(date_container)
        
        datetime_layout.addWidget(self.today_btn)
        datetime_layout.addSpacing(30)
        
        time_label = QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(time_label)
        
        self.time_edit.setFixedWidth(90)
        datetime_layout.addWidget(self.time_edit)
        datetime_layout.addWidget(self.now_btn)
        datetime_layout.addStretch(1)
        
        form.addWidget(datetime_section, 0, 0, 1, 7)

        # Section 1: Session Details (2-column grid)
        section1_header = self._create_section_header("🎮  Session Details")
        form.addWidget(section1_header, 1, 0, 1, 7)
        
        session_section = QWidget()
        session_section.setObjectName("SectionBackground")
        session_grid = QGridLayout(session_section)
        session_grid.setContentsMargins(10, 10, 10, 10)
        session_grid.setHorizontalSpacing(30)
        session_grid.setVerticalSpacing(8)
        
        row = 0
        
        # Left Column - User
        user_label = QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(user_label, row, 0)
        self.user_combo.setMinimumWidth(180)
        session_grid.addWidget(self.user_combo, row, 1)
        
        # Right Column - Site
        site_label = QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        site_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(site_label, row, 2)
        self.site_combo.setMinimumWidth(180)
        session_grid.addWidget(self.site_combo, row, 3)
        
        row += 1
        
        # Left Column - Game Type
        game_type_label = QLabel("Game Type:")
        game_type_label.setObjectName("FieldLabel")
        game_type_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(game_type_label, row, 0)
        self.game_type_combo.setMinimumWidth(180)
        session_grid.addWidget(self.game_type_combo, row, 1)
        
        # Right Column - Game
        game_name_label = QLabel("Game:")
        game_name_label.setObjectName("FieldLabel")
        game_name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(game_name_label, row, 2)
        self.game_name_combo.setMinimumWidth(180)
        session_grid.addWidget(self.game_name_combo, row, 3)
        
        row += 1
        
        # RTP Display (right column only, below Game)
        rtp_label = QLabel("RTP:")
        rtp_label.setObjectName("FieldLabel")
        rtp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(rtp_label, row, 2)
        session_grid.addWidget(self.rtp_display, row, 3)
        
        session_grid.setColumnStretch(1, 1)
        session_grid.setColumnStretch(3, 1)
        
        form.addWidget(session_section, 2, 0, 1, 7)

        # Section 2: Balance Details (2-column grid)
        section2_header = self._create_section_header("💰  Balance Details")
        form.addWidget(section2_header, 3, 0, 1, 7)
        
        balance_section = QWidget()
        balance_section.setObjectName("SectionBackground")
        balance_grid = QGridLayout(balance_section)
        balance_grid.setContentsMargins(10, 10, 10, 10)
        balance_grid.setHorizontalSpacing(30)
        balance_grid.setVerticalSpacing(8)
        
        row = 0
        
        # Left Column - Starting Total SC
        start_total_label = QLabel("Starting Total SC:")
        start_total_label.setObjectName("FieldLabel")
        start_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(start_total_label, row, 0)
        self.start_total_edit.setFixedWidth(140)
        balance_grid.addWidget(self.start_total_edit, row, 1)
        
        # Right Column - Starting Redeemable
        start_redeem_label = QLabel("Starting Redeemable:")
        start_redeem_label.setObjectName("FieldLabel")
        start_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(start_redeem_label, row, 2)
        self.start_redeem_edit.setFixedWidth(140)
        balance_grid.addWidget(self.start_redeem_edit, row, 3)
        
        row += 1
        
        # Balance Check Display (label in col 0, display spans cols 1-3)
        balance_check_label = QLabel("Balance Check:")
        balance_check_label.setObjectName("FieldLabel")
        balance_check_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_check_label.setToolTip(
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        balance_grid.addWidget(balance_check_label, row, 0)
        balance_grid.addWidget(self.balance_check_display, row, 1, 1, 3)
        
        balance_grid.setColumnStretch(1, 1)
        balance_grid.setColumnStretch(3, 1)
        
        form.addWidget(balance_section, 4, 0, 1, 7)

        # Collapsible Notes Section (like Add Purchase)
        self.notes_collapsed = True
        self.notes_toggle = QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        form.addWidget(self.notes_toggle, 5, 0, 1, 7)
        
        self.notes_section = QWidget()
        self.notes_section.setObjectName("SectionBackground")
        self.notes_section.setVisible(False)
        notes_layout = QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.addWidget(self.notes_edit)
        form.addWidget(self.notes_section, 6, 0, 1, 7)

        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        layout.addStretch(1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("✖️ Cancel")
        self.clear_btn = QPushButton("🧹 Clear")
        self.save_btn = QPushButton("💾 Save")
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
        self.game_name_combo.currentTextChanged.connect(self._update_rtp_display)
        self.site_combo.currentTextChanged.connect(self._update_balance_check)
        self.user_combo.currentTextChanged.connect(self._update_balance_check)
        self.start_total_edit.textChanged.connect(self._update_balance_check)
        self.date_edit.textChanged.connect(self._update_balance_check)
        self.time_edit.textChanged.connect(self._update_balance_check)
        self.time_edit.textEdited.connect(self._mark_time_edited)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.start_total_edit.textChanged.connect(self._validate_inline)
        self.start_redeem_edit.textChanged.connect(self._validate_inline)
        
        # Set tab order: Date -> Time -> User -> Site -> Game Type -> Game -> Starting SC -> Starting Redeemable -> Notes -> Save
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.user_combo)
        self.setTabOrder(self.user_combo, self.site_combo)
        self.setTabOrder(self.site_combo, self.game_type_combo)
        self.setTabOrder(self.game_type_combo, self.game_name_combo)
        self.setTabOrder(self.game_name_combo, self.start_total_edit)
        self.setTabOrder(self.start_total_edit, self.start_redeem_edit)
        self.setTabOrder(self.start_redeem_edit, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)
        self.setTabOrder(self.cancel_btn, self.clear_btn)

        if session:
            self._load_session()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()

        # Start with notes collapsed and dialog tight.
        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))
    
    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header"""
        label = QLabel(text)
        label.setObjectName("SectionHeader")
        return label

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
        """Set time to current time with seconds precision."""
        self.time_edit.setText(datetime.now().strftime("%H:%M:%S"))

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
        cancel_btn = QPushButton("✖️ Cancel")
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

    def _update_balance_check(self):
        """Update balance check display with styled value chip"""
        site_name = self.site_combo.currentText().strip()
        user_name = self.user_combo.currentText().strip()
        start_total_text = self.start_total_edit.text().strip()
        if not site_name or not user_name or not start_total_text:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        valid, result = validate_currency(start_total_text)
        if not valid:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        site_id, user_id = self._lookup_ids(site_name, user_name)
        if not site_id or not user_id:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        session_date = self.date_edit.text().strip() or None
        session_time = self.time_edit.text().strip() or None
        try:
            parsed_date = parse_date_input(session_date) if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        site_name = self.site_combo.currentText().strip()
        user_name = self.user_combo.currentText().strip()
        start_total_text = self.start_total_edit.text().strip()
        if not site_name or not user_name or not start_total_text:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        valid, result = validate_currency(start_total_text)
        if not valid:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        site_id, user_id = self._lookup_ids(site_name, user_name)
        if not site_id or not user_id:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        session_date = self.date_edit.text().strip() or None
        session_time = self.time_edit.text().strip() or None
        try:
            parsed_date = parse_date_input(session_date) if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return

        if not self._time_edited and parsed_date == date.today():
            # Only auto-update time if the field doesn't already have seconds
            # (e.g., it was manually entered as HH:MM or is empty)
            current_text = self.time_edit.text().strip()
            if current_text and len(current_text) > 5:
                # Time has seconds (HH:MM:SS), don't overwrite it
                pass
            else:
                now_text = datetime.now().strftime("%H:%M")
                if current_text != now_text:
                    self.time_edit.setText(now_text)
                parsed_time = parse_time_input(now_text)
        
        # For balance check: if time ends with :00 (user entered HH:MM), check up to :59
        # This handles purchases saved with full seconds in the same minute
        balance_check_time = parsed_time or datetime.now().strftime("%H:%M:%S")
        if balance_check_time and balance_check_time.endswith(":00"):
            # Replace :00 with :59 to include all purchases in this minute
            balance_check_time = balance_check_time[:-2] + "59"

        expected_total, _expected_redeem = self.facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=parsed_date or date.today(),
            session_time=balance_check_time,
        )
        site = self.facade.get_site(site_id)
        sc_rate = Decimal(str(site.sc_rate if site else 1.0))
        freebies_sc = max(0.0, float(result) - float(expected_total))
        missing_sc = max(0.0, float(expected_total) - float(result))
        freebies_dollar = float(Decimal(str(freebies_sc)) * sc_rate)
        if freebies_sc > 0:
            self.balance_check_display.setProperty("status", "positive")
            self.balance_check_display.setText(
                f"+ {freebies_sc:.2f} SC extra (${freebies_dollar:.2f})"
            )
        elif missing_sc > 0:
            self.balance_check_display.setProperty("status", "negative")
            self.balance_check_display.setText(
                f"- {missing_sc:.2f} SC less than expected"
            )
        else:
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.setText(f"Matches expected ({float(expected_total):.2f} SC)")
        self.balance_check_display.style().unpolish(self.balance_check_display)
        self.balance_check_display.style().polish(self.balance_check_display)

    def _update_rtp_display(self):
        """Update RTP display with compact styled chip"""
        game_name = self.game_name_combo.currentText().strip()
        game_type = self.game_type_combo.currentText().strip()
        if not game_name or not game_type:
            self.rtp_display.setText("—")
            return
        game = self._game_lookup.get((game_type.lower(), game_name.lower()))
        if not game:
            self.rtp_display.setText("—")
            return
        
        # Build RTP display from available data (expected and/or actual)
        parts = []
        if game.rtp is not None:
            parts.append(f"Exp: {float(game.rtp):.2f}%")
        if getattr(game, "actual_rtp", None) is not None:
            parts.append(f"Act: {float(game.actual_rtp):.2f}%")
        
        if parts:
            self.rtp_display.setText(" / ".join(parts))
        else:
            self.rtp_display.setText("—")

    def _load_session(self):
        self.date_edit.setText(self._format_date_for_input(self.session.session_date))
        self.time_edit.setText(self._format_time_for_input(self.session.session_time))
        self._time_edited = True

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
        elif self.session.game_type_id:
            # If no game but there's a game_type_id, load it directly
            type_obj = self._game_types_by_id.get(self.session.game_type_id)
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

        # Notes start collapsed even if notes exist (dialog opens compact).
        self.notes_collapsed = True
        self.notes_section.setVisible(False)
        if self.session.notes:
            self.notes_toggle.setText("📝 Show Notes...")
        else:
            self.notes_toggle.setText("📝 Add Notes...")

        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))
        
        self._update_balance_check()
        self._update_rtp_display()

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
        self._time_edited = False
        self.balance_check_display.setText("—")
        self.balance_check_display.setProperty("status", "neutral")
        self.balance_check_display.style().unpolish(self.balance_check_display)
        self.balance_check_display.style().polish(self.balance_check_display)
        self.rtp_display.setText("—")
        
        # Collapse notes section
        self.notes_collapsed = True
        self.notes_section.setVisible(False)
        self.notes_toggle.setText("📝 Add Notes...")

        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))
        
        self._validate_inline()
    
    def _compute_height_presets(self) -> None:
        """Compute min heights for collapsed vs expanded notes states."""
        self.notes_section.setVisible(False)
        self.adjustSize()
        collapsed_hint = int(self.sizeHint().height())
        self._min_height_no_notes = max(collapsed_hint, 580)

        self.notes_section.setVisible(True)
        self.adjustSize()
        expanded_hint = int(self.sizeHint().height())
        self._min_height_with_notes = max(expanded_hint, self._min_height_no_notes + 80)

        self.notes_section.setVisible(not self.notes_collapsed)

    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            if (self.notes_edit.toPlainText().strip() or ""):
                self.notes_toggle.setText("📝 Show Notes...")
            else:
                self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(self._min_height_no_notes)
            self.resize(self.width(), self._min_height_no_notes)
        else:
            self.notes_toggle.setText("📝 Notes")
            self.setMinimumHeight(self._min_height_with_notes)
            self.resize(self.width(), max(self.height(), self._min_height_with_notes))
            self.notes_edit.setFocus()

    def _mark_time_edited(self, _text):
        self._time_edited = True

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
        
        # Get game_type_id: from selected game, or from game_type selection
        game_type_id = None
        if game:
            game_type_id = game.game_type_id
        elif game_type:
            game_type_obj = self._game_type_lookup.get(game_type.lower())
            game_type_id = game_type_obj.id if game_type_obj else None

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
            "game_type_id": game_type_id,
            "starting_total_sc": Decimal(str(start_total)),
            "starting_redeemable_sc": Decimal(str(start_redeem)),
            "notes": notes,
        }, None


class EditSessionDialog(StartSessionDialog):
    def __init__(self, facade, session, parent=None):
        super().__init__(facade, session=session, parent=parent)


class EditClosedSessionDialog(QDialog):
    """Modern edit closed session dialog with comprehensive sectioned layout"""
    
    def __init__(self, facade, session, parent=None):
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

        self.setWindowTitle("Edit Closed Session")
        self.setMinimumWidth(750)
        # Notes are collapsible; compute tight/expanded heights after load.
        self._min_height_no_notes = 0
        self._min_height_with_notes = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setContentsMargins(10, 10, 10, 10)

        # Initialize widgets
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.start_calendar_btn = QPushButton("📅")
        self.start_calendar_btn.setFixedWidth(44)
        self.start_today_btn = QPushButton("Today")
        self.start_calendar_btn.clicked.connect(self._pick_start_date)
        self.start_today_btn.clicked.connect(self._set_start_today)
        
        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM:SS")
        self.start_now_btn = QPushButton("Now")
        self.start_now_btn.clicked.connect(self._set_start_now)

        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("MM/DD/YY")
        self.end_calendar_btn = QPushButton("📅")
        self.end_calendar_btn.setFixedWidth(44)
        self.end_today_btn = QPushButton("Today")
        self.end_calendar_btn.clicked.connect(self._pick_end_date)
        self.end_today_btn.clicked.connect(self._set_end_today)
        
        self.end_time_edit = QLineEdit()
        self.end_time_edit.setPlaceholderText("HH:MM:SS")
        self.end_now_btn = QPushButton("Now")
        self.end_now_btn.clicked.connect(self._set_end_now)

        self.user_combo = QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.lineEdit().setPlaceholderText("Choose...")
        self.user_combo.addItems(user_names)

        self.site_combo = QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.lineEdit().setPlaceholderText("Choose...")
        self.site_combo.addItems(site_names)

        self.game_type_combo = QComboBox()
        self.game_type_combo.setEditable(True)
        self.game_type_combo.lineEdit().setPlaceholderText("Choose...")
        self.game_type_combo.addItems(game_types)

        self.game_name_combo = QComboBox()
        self.game_name_combo.setEditable(True)
        self.game_name_combo.lineEdit().setPlaceholderText("Select a game type first")

        self.wager_edit = QLineEdit()
        self.wager_edit.setPlaceholderText("Optional")

        # RTP Display (value label, not input)
        self.rtp_display = QLabel("—")
        self.rtp_display.setObjectName("ValueChip")
        self.rtp_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.rtp_display.setFixedHeight(28)
        
        # RTP Help button
        self.rtp_help_btn = QPushButton("?")
        self.rtp_help_btn.setFixedSize(22, 22)
        self.rtp_help_btn.setToolTip("Click for RTP explanation")
        self.rtp_help_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rtp_help_btn.setCursor(Qt.PointingHandCursor)
        self.rtp_help_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: 1px solid #0052a3;
                border-radius: 11px;
                font-weight: bold;
                font-size: 11px;
                padding: 0px;
                margin: 0px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
        """)
        self.rtp_help_btn.clicked.connect(self._show_rtp_help)

        self.start_total_edit = QLineEdit()
        self.start_total_edit.setPlaceholderText("0.00")
        self.start_redeem_edit = QLineEdit()
        self.start_redeem_edit.setPlaceholderText("0.00")

        # Balance Check Display (value label, not input)
        balance_tooltip = (
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        self.balance_check_display = QLabel("—")
        self.balance_check_display.setObjectName("ValueChip")
        self.balance_check_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.balance_check_display.setFixedHeight(28)
        self.balance_check_display.setWordWrap(True)
        self.balance_check_display.setProperty("status", "neutral")
        self.balance_check_display.setToolTip(balance_tooltip)

        self.end_total_edit = QLineEdit()
        self.end_total_edit.setPlaceholderText("0.00")
        self.end_redeem_edit = QLineEdit()
        self.end_redeem_edit.setPlaceholderText("0.00")

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Date/Time Section (combined start and end in one section)
        datetime_section = QWidget()
        datetime_section.setObjectName("SectionBackground")
        datetime_layout = QVBoxLayout(datetime_section)
        datetime_layout.setContentsMargins(12, 10, 12, 10)
        datetime_layout.setSpacing(8)
        
        # Row 1: Start Date/Time
        start_row = QHBoxLayout()
        start_row.setSpacing(12)
        
        start_date_label = QLabel("Start Date:")
        start_date_label.setObjectName("FieldLabel")
        start_date_label.setFixedWidth(70)
        start_row.addWidget(start_date_label)
        
        # Start date field with embedded calendar button
        start_date_container = QWidget()
        start_date_layout = QHBoxLayout(start_date_container)
        start_date_layout.setContentsMargins(0, 0, 0, 0)
        start_date_layout.setSpacing(4)
        self.date_edit.setFixedWidth(110)
        start_date_layout.addWidget(self.date_edit)
        start_date_layout.addWidget(self.start_calendar_btn)
        start_row.addWidget(start_date_container)
        
        start_row.addWidget(self.start_today_btn)
        start_row.addSpacing(30)
        
        start_time_label = QLabel("Start Time:")
        start_time_label.setObjectName("FieldLabel")
        start_time_label.setFixedWidth(70)
        start_row.addWidget(start_time_label)
        
        self.time_edit.setFixedWidth(90)
        start_row.addWidget(self.time_edit)
        start_row.addWidget(self.start_now_btn)
        start_row.addStretch(1)
        
        datetime_layout.addLayout(start_row)
        
        # Row 2: End Date/Time
        end_row = QHBoxLayout()
        end_row.setSpacing(12)
        
        end_date_label = QLabel("End Date:")
        end_date_label.setObjectName("FieldLabel")
        end_date_label.setFixedWidth(70)
        end_row.addWidget(end_date_label)
        
        # End date field with embedded calendar button
        end_date_container = QWidget()
        end_date_layout = QHBoxLayout(end_date_container)
        end_date_layout.setContentsMargins(0, 0, 0, 0)
        end_date_layout.setSpacing(4)
        self.end_date_edit.setFixedWidth(110)
        end_date_layout.addWidget(self.end_date_edit)
        end_date_layout.addWidget(self.end_calendar_btn)
        end_row.addWidget(end_date_container)
        
        end_row.addWidget(self.end_today_btn)
        end_row.addSpacing(30)
        
        end_time_label = QLabel("End Time:")
        end_time_label.setObjectName("FieldLabel")
        end_time_label.setFixedWidth(70)
        end_row.addWidget(end_time_label)
        
        self.end_time_edit.setFixedWidth(90)
        end_row.addWidget(self.end_time_edit)
        end_row.addWidget(self.end_now_btn)
        end_row.addStretch(1)
        
        datetime_layout.addLayout(end_row)
        
        form.addWidget(datetime_section, 0, 0, 1, 7)

        # Section 1: Session Details (2-column grid)
        section1_header = self._create_section_header("🎮  Session Details")
        form.addWidget(section1_header, 1, 0, 1, 7)
        
        session_section = QWidget()
        session_section.setObjectName("SectionBackground")
        session_grid = QGridLayout(session_section)
        session_grid.setContentsMargins(10, 10, 10, 10)
        session_grid.setHorizontalSpacing(30)
        session_grid.setVerticalSpacing(8)
        
        row = 0
        
        # Left Column - User
        user_label = QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(user_label, row, 0)
        self.user_combo.setMinimumWidth(180)
        session_grid.addWidget(self.user_combo, row, 1)
        
        # Right Column - Site
        site_label = QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        site_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(site_label, row, 2)
        self.site_combo.setMinimumWidth(180)
        session_grid.addWidget(self.site_combo, row, 3)
        
        row += 1
        
        # Left Column - Game Type
        game_type_label = QLabel("Game Type:")
        game_type_label.setObjectName("FieldLabel")
        game_type_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(game_type_label, row, 0)
        self.game_type_combo.setMinimumWidth(180)
        session_grid.addWidget(self.game_type_combo, row, 1)
        
        # Right Column - Game
        game_name_label = QLabel("Game:")
        game_name_label.setObjectName("FieldLabel")
        game_name_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        session_grid.addWidget(game_name_label, row, 2)
        self.game_name_combo.setMinimumWidth(180)
        session_grid.addWidget(self.game_name_combo, row, 3)
        
        session_grid.setColumnStretch(1, 1)
        session_grid.setColumnStretch(3, 1)
        
        form.addWidget(session_section, 2, 0, 1, 7)

        # Section 2: Balance Details (2-column grid with all balance fields)
        section2_header = self._create_section_header("💰  Balance Details")
        form.addWidget(section2_header, 3, 0, 1, 7)
        
        balance_section = QWidget()
        balance_section.setObjectName("SectionBackground")
        balance_grid = QGridLayout(balance_section)
        balance_grid.setContentsMargins(10, 10, 10, 10)
        balance_grid.setHorizontalSpacing(30)
        balance_grid.setVerticalSpacing(8)
        
        row = 0
        
        # Left Column - Starting Total SC
        start_total_label = QLabel("Starting Total SC:")
        start_total_label.setObjectName("FieldLabel")
        start_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(start_total_label, row, 0)
        self.start_total_edit.setFixedWidth(140)
        balance_grid.addWidget(self.start_total_edit, row, 1)
        
        # Right Column - Starting Redeemable
        start_redeem_label = QLabel("Starting Redeemable:")
        start_redeem_label.setObjectName("FieldLabel")
        start_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(start_redeem_label, row, 2)
        self.start_redeem_edit.setFixedWidth(140)
        balance_grid.addWidget(self.start_redeem_edit, row, 3)
        
        row += 1
        
        # Left Column - Ending Total SC
        end_total_label = QLabel("Ending Total SC:")
        end_total_label.setObjectName("FieldLabel")
        end_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(end_total_label, row, 0)
        self.end_total_edit.setFixedWidth(140)
        balance_grid.addWidget(self.end_total_edit, row, 1)
        
        # Right Column - Ending Redeemable
        end_redeem_label = QLabel("Ending Redeemable:")
        end_redeem_label.setObjectName("FieldLabel")
        end_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(end_redeem_label, row, 2)
        self.end_redeem_edit.setFixedWidth(140)
        balance_grid.addWidget(self.end_redeem_edit, row, 3)
        
        row += 1
        
        # Balance Check Display (label in col 0, display spans cols 1-3)
        balance_check_label = QLabel("Balance Check:")
        balance_check_label.setObjectName("FieldLabel")
        balance_check_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_check_label.setToolTip(
            "Compares your starting total SC to the expected balance from prior sessions, purchases, "
            "and redemptions. This helps flag missing entries or unexpected bonuses. It does not "
            "change tax results until the session is closed."
        )
        balance_grid.addWidget(balance_check_label, row, 0)
        balance_grid.addWidget(self.balance_check_display, row, 1, 1, 3)
        
        row += 1
        
        # Left Column - Wager
        wager_label = QLabel("Wager:")
        wager_label.setObjectName("FieldLabel")
        wager_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(wager_label, row, 0)
        self.wager_edit.setFixedWidth(140)
        balance_grid.addWidget(self.wager_edit, row, 1)
        
        # Right Column - RTP Display with help button
        rtp_label = QLabel("RTP:")
        rtp_label.setObjectName("FieldLabel")
        rtp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balance_grid.addWidget(rtp_label, row, 2)
        
        # RTP container with display and help button
        rtp_container = QWidget()
        rtp_layout = QHBoxLayout(rtp_container)
        rtp_layout.setContentsMargins(0, 0, 0, 0)
        rtp_layout.setSpacing(6)
        rtp_layout.addWidget(self.rtp_display)
        rtp_layout.addWidget(self.rtp_help_btn, 0, Qt.AlignVCenter)
        rtp_layout.addStretch(1)
        balance_grid.addWidget(rtp_container, row, 3)
        
        balance_grid.setColumnStretch(1, 1)
        balance_grid.setColumnStretch(3, 1)
        
        form.addWidget(balance_section, 4, 0, 1, 7)

        # Collapsible Notes Section (like Add Session)
        self.notes_collapsed = True
        self.notes_toggle = QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        form.addWidget(self.notes_toggle, 5, 0, 1, 7)
        
        self.notes_section = QWidget()
        self.notes_section.setObjectName("SectionBackground")
        self.notes_section.setVisible(False)
        notes_layout = QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.addWidget(self.notes_edit)
        form.addWidget(self.notes_section, 6, 0, 1, 7)

        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        layout.addStretch(1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("✖️ Cancel")
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self.reject)
        self.game_type_combo.currentTextChanged.connect(self._update_game_names)
        self.game_type_combo.currentTextChanged.connect(self._validate_inline)
        self.game_name_combo.currentTextChanged.connect(self._validate_inline)
        self.game_name_combo.currentTextChanged.connect(self._update_rtp_display)
        self.site_combo.currentTextChanged.connect(self._update_balance_check)
        self.user_combo.currentTextChanged.connect(self._update_balance_check)
        self.start_total_edit.textChanged.connect(self._update_balance_check)
        self.date_edit.textChanged.connect(self._update_balance_check)
        self.time_edit.textChanged.connect(self._update_balance_check)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.start_total_edit.textChanged.connect(self._validate_inline)
        self.start_redeem_edit.textChanged.connect(self._validate_inline)
        self.end_date_edit.textChanged.connect(self._validate_inline)
        self.end_time_edit.textChanged.connect(self._validate_inline)
        self.end_total_edit.textChanged.connect(self._validate_inline)
        self.end_redeem_edit.textChanged.connect(self._validate_inline)
        self.wager_edit.textChanged.connect(self._validate_inline)
        
        # Connect fields that affect RTP calculation
        self.wager_edit.textChanged.connect(self._update_rtp_display)
        self.start_total_edit.textChanged.connect(self._update_rtp_display)
        self.end_total_edit.textChanged.connect(self._update_rtp_display)
        self.game_name_combo.currentTextChanged.connect(self._update_rtp_display)
        
        # Set tab order: Start date -> Start time -> End Date -> End Time -> User -> Site -> 
        # Game Type -> Game Name -> Wager -> Start Total -> Start Redeem -> End total -> End redeem -> Notes -> Save
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.end_date_edit)
        self.setTabOrder(self.end_date_edit, self.end_time_edit)
        self.setTabOrder(self.end_time_edit, self.user_combo)
        self.setTabOrder(self.user_combo, self.site_combo)
        self.setTabOrder(self.site_combo, self.game_type_combo)
        self.setTabOrder(self.game_type_combo, self.game_name_combo)
        self.setTabOrder(self.game_name_combo, self.wager_edit)
        self.setTabOrder(self.wager_edit, self.start_total_edit)
        self.setTabOrder(self.start_total_edit, self.start_redeem_edit)
        self.setTabOrder(self.start_redeem_edit, self.end_total_edit)
        self.setTabOrder(self.end_total_edit, self.end_redeem_edit)
        self.setTabOrder(self.end_redeem_edit, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)

        self._load_session()
        self._validate_inline()

        # Start with notes collapsed and dialog tight.
        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))
    
    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header"""
        label = QLabel(text)
        label.setObjectName("SectionHeader")
        return label
    
    def _update_game_names(self):
        """Update game names based on selected game type"""
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
        self._validate_inline()
    
    def _update_rtp_display(self):
        """Update RTP display: Exp (static) / Act (aggregate) / Session (this session only, real-time)"""
        game_type_text = self.game_type_combo.currentText().strip()
        game_name_text = self.game_name_combo.currentText().strip()
        
        if not game_type_text or not game_name_text:
            self.rtp_display.setText("—")
            return
        
        key = (game_type_text.lower(), game_name_text.lower())
        game = self._game_lookup.get(key)
        
        if not game:
            self.rtp_display.setText("—")
            return
        
        # Build RTP display from available data (expected, actual, and/or session)
        parts = []
        
        # Part 1: Expected RTP (static from game setup)
        if game.rtp is not None:
            parts.append(f"Exp: {float(game.rtp):.2f}%")
        
        # Part 2: Actual RTP (current aggregate, excluding this session)
        try:
            # Use facade's database connection
            conn = self.facade.game_session_service.session_repo.db._connection
            c = conn.cursor()
            
            # Get current aggregates
            c.execute('''
                SELECT total_wager, total_delta, session_count 
                FROM game_rtp_aggregates 
                WHERE game_id = ?
            ''', (game.id,))
            agg_row = c.fetchone()
            
            if agg_row:
                current_total_wager = float(agg_row['total_wager'])
                current_total_delta = float(agg_row['total_delta'])
                
                # Subtract THIS session's current contribution (since we're editing it)
                old_wager = float(self.session.wager_amount or 0)
                old_delta = float(self.session.delta_total or 0) if hasattr(self.session, 'delta_total') and self.session.delta_total is not None else (float(self.session.ending_balance or 0) - float(self.session.starting_balance or 0))
                
                # Act = aggregate without this session
                act_total_wager = current_total_wager - old_wager
                act_total_delta = current_total_delta - old_delta
                
                if act_total_wager > 0:
                    actual_rtp = ((act_total_wager + act_total_delta) / act_total_wager) * 100.0
                    parts.append(f"Act: {actual_rtp:.2f}%")
        except Exception:
            # Fallback to game's stored actual_rtp
            if getattr(game, "actual_rtp", None) is not None:
                parts.append(f"Act: {float(game.actual_rtp):.2f}%")
        
        # Part 3: Session RTP (this session only, real-time calculation)
        wager_text = self.wager_edit.text().strip()
        start_total_text = self.start_total_edit.text().strip()
        end_total_text = self.end_total_edit.text().strip()
        
        # Validate wager
        if wager_text:
            valid, result = validate_currency(wager_text)
            if valid:
                wager_amount = float(result)
                
                # Calculate delta_total from balances
                if start_total_text and end_total_text:
                    valid_start, result_start = validate_currency(start_total_text)
                    valid_end, result_end = validate_currency(end_total_text)
                    if valid_start and valid_end and wager_amount > 0:
                        delta_total = float(result_end) - float(result_start)
                        
                        # Session RTP formula: ((wager + delta_total) / wager) * 100
                        session_rtp = ((wager_amount + delta_total) / wager_amount) * 100.0
                        parts.append(f"Session: {session_rtp:.2f}%")
        
        # Build final display string
        if parts:
            self.rtp_display.setText(" / ".join(parts))
        else:
            self.rtp_display.setText("—")
    
    def _update_balance_check(self):
        """Update balance check display with proper calculation"""
        site_name = self.site_combo.currentText().strip()
        user_name = self.user_combo.currentText().strip()
        start_total_text = self.start_total_edit.text().strip()
        
        if not site_name or not user_name or not start_total_text:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        
        valid, result = validate_currency(start_total_text)
        if not valid:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        
        site_id, user_id = self._lookup_ids(site_name, user_name)
        if not site_id or not user_id:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        
        session_date = self.date_edit.text().strip() or None
        session_time = self.time_edit.text().strip() or None
        try:
            parsed_date = parse_date_input(session_date) if session_date else None
            parsed_time = parse_time_input(session_time) if session_time else None
        except ValueError:
            self.balance_check_display.setText("—")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
            return
        
        try:
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
                self.balance_check_display.setProperty("status", "positive")
                self.balance_check_display.setText(
                    f"+ {freebies_sc:.2f} SC extra (${freebies_dollar:.2f})"
                )
            elif missing_sc > 0:
                self.balance_check_display.setProperty("status", "negative")
                self.balance_check_display.setText(
                    f"- {missing_sc:.2f} SC less than expected"
                )
            else:
                self.balance_check_display.setProperty("status", "neutral")
                self.balance_check_display.setText(f"Matches expected ({float(expected_total):.2f} SC)")
            
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
        except Exception:
            # If any error occurs, just show neutral
            self.balance_check_display.setText("Balance check available")
            self.balance_check_display.setProperty("status", "neutral")
            self.balance_check_display.style().unpolish(self.balance_check_display)
            self.balance_check_display.style().polish(self.balance_check_display)
    
    def _lookup_ids(self, site_name, user_name):
        """Lookup site and user IDs by name"""
        site = self._site_lookup.get(site_name.lower())
        user = self._user_lookup.get(user_name.lower())
        return (site.id if site else None, user.id if user else None)
    
    def _set_start_today(self):
        """Set start date to today"""
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))
    
    def _set_start_now(self):
        """Set start time to now"""
        self.time_edit.setText(datetime.now().strftime("%H:%M"))
    
    def _set_end_today(self):
        """Set end date to today"""
        self.end_date_edit.setText(date.today().strftime("%m/%d/%y"))
    
    def _set_end_now(self):
        """Set end time to now"""
        self.end_time_edit.setText(datetime.now().strftime("%H:%M"))
    
    def _pick_start_date(self):
        """Pick start date from calendar"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Start Date")
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("Select")
        cancel_btn = QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
    
    def _pick_end_date(self):
        """Pick end date from calendar"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select End Date")
        layout = QVBoxLayout(dialog)
        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("Select")
        cancel_btn = QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QDialog.Accepted:
            self.end_date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _compute_height_presets(self) -> None:
        """Compute min heights for collapsed vs expanded notes states."""
        self.notes_section.setVisible(False)
        self.adjustSize()
        collapsed_hint = int(self.sizeHint().height())
        self._min_height_no_notes = max(collapsed_hint, 620)

        self.notes_section.setVisible(True)
        self.adjustSize()
        expanded_hint = int(self.sizeHint().height())
        self._min_height_with_notes = max(expanded_hint, self._min_height_no_notes + 80)

        self.notes_section.setVisible(not self.notes_collapsed)
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            if (self.notes_edit.toPlainText().strip() or ""):
                self.notes_toggle.setText("📝 Show Notes...")
            else:
                self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(self._min_height_no_notes)
            self.resize(self.width(), self._min_height_no_notes)
        else:
            self.notes_toggle.setText("📝 Notes")
            self.setMinimumHeight(self._min_height_with_notes)
            self.resize(self.width(), max(self.height(), self._min_height_with_notes))
            self.notes_edit.setFocus()
    
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
    
    def _show_rtp_help(self):
        """Show help dialog explaining RTP components"""
        QMessageBox.information(
            self,
            "RTP (Return to Player) Explanation",
            "<b>Exp (Expected):</b> The game's advertised/theoretical RTP percentage from the setup tab. "
            "This is the static baseline provided by the casino.<br><br>"
            "<b>Act (Actual):</b> The cumulative RTP across ALL other closed sessions for this game "
            "(excluding this session). Calculated as ((total_wager + total_delta) / total_wager) × 100.<br><br>"
            "<b>Session:</b> The RTP for THIS specific session only, calculated in real-time as you type. "
            "Formula: ((wager + delta_total) / wager) × 100, where delta_total = ending_balance - starting_balance.<br><br>"
            "<i>When you save, the Actual RTP will be updated to include this session's contribution.</i>"
        )
    
    def collect_data(self):
        """Collect and validate all form data for closed session"""
        # Validate and collect user/site
        user_name = self.user_combo.currentText().strip()
        site_name = self.site_combo.currentText().strip()
        if not user_name or not site_name:
            return None, "Please select User and Site."
        
        user = self._user_lookup.get(user_name.lower())
        site = self._site_lookup.get(site_name.lower())
        if not user or not site:
            return None, "Please select a valid User and Site."
        
        # Validate start date
        start_date_str = self.date_edit.text().strip()
        if not start_date_str:
            return None, "Please enter a start date."
        try:
            start_date = parse_date_input(start_date_str)
        except ValueError:
            return None, "Please enter a valid start date."
        
        # Validate start time
        start_time_str = self.time_edit.text().strip()
        if start_time_str and not is_valid_time_24h(start_time_str, allow_blank=False):
            return None, "Please enter a valid start time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            start_time = parse_time_input(start_time_str)
        except ValueError:
            return None, "Please enter a valid start time (HH:MM or HH:MM:SS)."
        
        # Validate end date
        end_date_str = self.end_date_edit.text().strip()
        if not end_date_str:
            return None, "Please enter an end date."
        try:
            end_date = parse_date_input(end_date_str)
        except ValueError:
            return None, "Please enter a valid end date."
        
        # Validate end time
        end_time_str = self.end_time_edit.text().strip()
        if end_time_str and not is_valid_time_24h(end_time_str, allow_blank=False):
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS, 24-hour)."
        try:
            end_time = parse_time_input(end_time_str)
        except ValueError:
            return None, "Please enter a valid end time (HH:MM or HH:MM:SS)."
        
        # Validate game type and game name
        game_type = self.game_type_combo.currentText().strip()
        game_name = self.game_name_combo.currentText().strip()
        
        game = None
        game_id = None
        if game_name:
            if not game_type:
                return None, "Please select a Game Type when entering a Game Name."
            game = self._game_lookup.get((game_type.lower(), game_name.lower()))
            if not game:
                return None, "Please select a valid Game Name for the chosen type."
            game_id = game.id
        
        # Get game_type_id: from selected game, or from game_type selection
        game_type_id = None
        if game:
            game_type_id = game.game_type_id
        elif game_type:
            game_type_obj = self._game_type_lookup.get(game_type.lower())
            game_type_id = game_type_obj.id if game_type_obj else None
        
        # Validate wager amount
        wager_str = self.wager_edit.text().strip()
        wager_amount = None
        if wager_str:
            valid, result = validate_currency(wager_str)
            if not valid:
                return None, result
            wager_amount = result
        
        # Validate starting balances
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
        
        # Validate ending balances
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
        
        notes = self.notes_edit.toPlainText().strip()
        
        return {
            "session_date": start_date,
            "start_time": start_time,
            "end_date": end_date,
            "end_time": end_time,
            "user_id": user.id,
            "site_id": site.id,
            "game_id": game_id,
            "game_type_id": game_type_id,
            "game_name": game_name,
            "starting_total_sc": Decimal(str(start_total)),
            "starting_redeemable_sc": Decimal(str(start_redeem)),
            "ending_total_sc": Decimal(str(end_total)),
            "ending_redeemable_sc": Decimal(str(end_redeem)),
            "wager_amount": wager_amount,
            "notes": notes,
        }, None
    
    def _validate_inline(self):
        """Validate all fields"""
        # Validate start date
        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Start date is required.")
        else:
            try:
                parse_date_input(date_text)
                self._set_valid(self.date_edit)
            except ValueError:
                self._set_invalid(self.date_edit, "Enter a valid start date.")

        # Validate start time
        time_text = self.time_edit.text().strip()
        if not is_valid_time_24h(time_text, allow_blank=True):
            self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.time_edit)

        # Validate end date
        end_date_text = self.end_date_edit.text().strip()
        if not end_date_text:
            self._set_invalid(self.end_date_edit, "End date is required.")
        else:
            try:
                parse_date_input(end_date_text)
                self._set_valid(self.end_date_edit)
            except ValueError:
                self._set_invalid(self.end_date_edit, "Enter a valid end date.")

        # Validate end time
        end_time_text = self.end_time_edit.text().strip()
        if not is_valid_time_24h(end_time_text, allow_blank=True):
            self._set_invalid(self.end_time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
        else:
            self._set_valid(self.end_time_edit)

        # Validate user
        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
        else:
            self._set_valid(self.user_combo)

        # Validate site
        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
        else:
            self._set_valid(self.site_combo)

        # Validate game type
        game_type_text = self.game_type_combo.currentText().strip()
        if game_type_text and game_type_text.lower() not in self._game_type_lookup:
            self._set_invalid(self.game_type_combo, "Select a valid Game Type.")
        else:
            self._set_valid(self.game_type_combo)

        # Validate game name
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

        # Validate starting balances
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

        # Validate ending balances
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

        # Validate wager (optional)
        wager_text = self.wager_edit.text().strip()
        if wager_text:
            valid, _result = validate_currency(wager_text)
            if not valid:
                self._set_invalid(self.wager_edit, "Enter a valid amount (max 2 decimals).")
            else:
                self._set_valid(self.wager_edit)
        else:
            self._set_valid(self.wager_edit)
    
    def _load_session(self):
        """Load session data into fields"""
        self.date_edit.setText(self.session.session_date.strftime("%m/%d/%y") if self.session.session_date else "")
        self.time_edit.setText(self.session.session_time if self.session.session_time else "")
        
        end_date = self.session.end_date or self.session.session_date
        if end_date:
            self.end_date_edit.setText(end_date.strftime("%m/%d/%y"))
        end_time = self.session.end_time or self.session.session_time
        if end_time:
            self.end_time_edit.setText(end_time)

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
        if game and game.name:
            self.game_name_combo.blockSignals(True)
            self.game_name_combo.setCurrentText(game.name)
            self.game_name_combo.blockSignals(False)

        self._update_game_names()

        self.start_total_edit.setText(str(self.session.starting_balance))
        self.start_redeem_edit.setText(str(self.session.starting_redeemable))
        self.end_total_edit.setText(str(self.session.ending_balance or ""))
        self.end_redeem_edit.setText(str(self.session.ending_redeemable or ""))
        if getattr(self.session, "wager_amount", None) is not None:
            self.wager_edit.setText(str(self.session.wager_amount or ""))
        self.notes_edit.setPlainText(self.session.notes or "")

        # Notes start collapsed even if notes exist (dialog opens compact).
        self.notes_collapsed = True
        self.notes_section.setVisible(False)
        if self.session.notes:
            self.notes_toggle.setText("📝 Show Notes...")
        else:
            self.notes_toggle.setText("📝 Add Notes...")

        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))
        
        self._update_balance_check()
        self._update_rtp_display()


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
        self.resize(750, 600)

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
        close_btn = QPushButton("✖️ Close")
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
        """Create details tab with modern sectioned layout"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Get lookups
        users = {u.id: u.name for u in self.facade.get_all_users()}
        sites = {s.id: s.name for s in self.facade.get_all_sites()}
        games = {g.id: g for g in self.facade.list_all_games()}
        game_types_list = self.facade.get_all_game_types()

        game = games.get(self.session.game_id) if self.session.game_id else None
        game_name = game.name if game else "—"
        game_type_name = "—"
        if game and game.game_type_id:
            for gt in game_types_list:
                if gt.id == game.game_type_id:
                    game_type_name = gt.name
                    break

        is_active = not self.session.status or self.session.status == "Active"
        status_text = self.session.status or "Active"

        # ─────── Section 1: Session Details ───────
        details_header = self._create_section_header(f"📋  Session Details - {status_text}")
        layout.addWidget(details_header)

        details_section = QWidget()
        details_section.setObjectName("SectionBackground")
        details_grid = QGridLayout(details_section)
        details_grid.setContentsMargins(12, 12, 12, 12)
        details_grid.setHorizontalSpacing(20)
        details_grid.setVerticalSpacing(8)

        # Row 0: Start Date/Time (left), End Date/Time (right)
        start_dt_label = QLabel("Start Date / Time:")
        start_dt_label.setObjectName("MutedLabel")
        details_grid.addWidget(start_dt_label, 0, 0)

        start_dt_value = self._format_datetime(self.session.session_date, self.session.session_time)
        start_dt_display = QLabel(start_dt_value)
        start_dt_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        start_dt_display.setCursor(Qt.IBeamCursor)
        details_grid.addWidget(start_dt_display, 0, 1)

        end_dt_label = QLabel("End Date / Time:")
        end_dt_label.setObjectName("MutedLabel")
        details_grid.addWidget(end_dt_label, 0, 2)

        end_dt_value = self._format_datetime(self.session.end_date, self.session.end_time) if self.session.end_date else "—"
        end_dt_display = QLabel(end_dt_value)
        end_dt_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        end_dt_display.setCursor(Qt.IBeamCursor)
        details_grid.addWidget(end_dt_display, 0, 3)

        # Row 1: User (left), Site (right)
        user_label = QLabel("User:")
        user_label.setObjectName("MutedLabel")
        details_grid.addWidget(user_label, 1, 0)

        user_name = users.get(self.session.user_id, "—")
        user_display = QLabel(user_name)
        user_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        user_display.setCursor(Qt.IBeamCursor)
        details_grid.addWidget(user_display, 1, 1)

        site_label = QLabel("Site:")
        site_label.setObjectName("MutedLabel")
        details_grid.addWidget(site_label, 1, 2)

        site_name = sites.get(self.session.site_id, "—")
        site_display = QLabel(site_name)
        site_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        site_display.setCursor(Qt.IBeamCursor)
        details_grid.addWidget(site_display, 1, 3)

        details_grid.setColumnStretch(1, 1)
        details_grid.setColumnStretch(3, 1)
        layout.addWidget(details_section)

        # ========== TWO-COLUMN LAYOUT: Game Stats | Balances/Outcomes ==========
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(12)

        # ========== LEFT: Game Stats ==========
        game_stats_section = QWidget()
        game_stats_section.setObjectName("SectionBackground")
        game_stats_layout = QVBoxLayout(game_stats_section)
        game_stats_layout.setContentsMargins(10, 8, 10, 8)
        game_stats_layout.setSpacing(6)

        # Subsection header
        game_stats_label = QLabel("🎮 Game Stats")
        game_stats_label.setObjectName("SectionHeader")
        game_stats_layout.addWidget(game_stats_label)

        game_stats_grid = QGridLayout()
        game_stats_grid.setContentsMargins(0, 4, 0, 0)
        game_stats_grid.setHorizontalSpacing(12)
        game_stats_grid.setVerticalSpacing(6)

        row = 0
        game_type_label = QLabel("Game Type:")
        game_type_label.setObjectName("MutedLabel")
        game_stats_grid.addWidget(game_type_label, row, 0)
        game_type_value = QLabel(game_type_name)
        game_type_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        game_type_value.setCursor(Qt.IBeamCursor)
        game_stats_grid.addWidget(game_type_value, row, 1)

        row += 1
        game_name_label = QLabel("Game Name:")
        game_name_label.setObjectName("MutedLabel")
        game_stats_grid.addWidget(game_name_label, row, 0)
        game_name_value = QLabel(game_name)
        game_name_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        game_name_value.setCursor(Qt.IBeamCursor)
        game_stats_grid.addWidget(game_name_value, row, 1)

        row += 1
        wager_label = QLabel("Wager:")
        wager_label.setObjectName("MutedLabel")
        game_stats_grid.addWidget(wager_label, row, 0)
        wager_value = self.session.wager_amount if self.session.wager_amount is not None else None
        wager_display = format_currency(wager_value) if wager_value not in (None, "") else "—"
        wager_value_label = QLabel(wager_display)
        wager_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        wager_value_label.setCursor(Qt.IBeamCursor)
        game_stats_grid.addWidget(wager_value_label, row, 1)

        row += 1
        rtp_label = QLabel("RTP:")
        rtp_label.setObjectName("MutedLabel")
        game_stats_grid.addWidget(rtp_label, row, 0)
        rtp_display = self._calculate_rtp_display(game)
        rtp_value_label = QLabel(rtp_display)
        rtp_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rtp_value_label.setCursor(Qt.IBeamCursor)
        game_stats_grid.addWidget(rtp_value_label, row, 1)

        game_stats_grid.setColumnStretch(1, 1)
        game_stats_layout.addLayout(game_stats_grid)
        game_stats_layout.addStretch(1)

        columns_layout.addWidget(game_stats_section, 1)

        # ========== RIGHT: Balances/Outcomes ==========
        balances_section = QWidget()
        balances_section.setObjectName("SectionBackground")
        balances_layout = QVBoxLayout(balances_section)
        balances_layout.setContentsMargins(10, 8, 10, 8)
        balances_layout.setSpacing(6)

        # Subsection header
        balances_label = QLabel("💰 Balances/Outcomes")
        balances_label.setObjectName("SectionHeader")
        balances_layout.addWidget(balances_label)

        # Table container with subtle border and background
        table_container = QWidget()
        table_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        balances_grid = QGridLayout(table_container)
        balances_grid.setContentsMargins(0, 0, 0, 0)
        balances_grid.setHorizontalSpacing(0)
        balances_grid.setVerticalSpacing(0)

        # Column headers (no empty cell, start at column 1)
        row = 0
        
        start_header = QLabel("Start")
        start_header.setAlignment(Qt.AlignCenter)
        start_header.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(start_header, row, 1)

        end_header = QLabel("End")
        end_header.setAlignment(Qt.AlignCenter)
        end_header.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(end_header, row, 2)

        delta_header = QLabel("Delta")
        delta_header.setAlignment(Qt.AlignCenter)
        delta_header.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(delta_header, row, 3)

        # Row: Total SC
        row += 1
        total_label = QLabel("Total SC:")
        total_label.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(total_label, row, 0)

        start_sc = f"{float(self.session.starting_balance or 0):.2f}"
        start_sc_label = QLabel(start_sc)
        start_sc_label.setAlignment(Qt.AlignCenter)
        start_sc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        start_sc_label.setCursor(Qt.IBeamCursor)
        start_sc_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2);")
        balances_grid.addWidget(start_sc_label, row, 1)

        end_sc = f"{float(self.session.ending_balance or 0):.2f}" if not is_active and self.session.ending_balance is not None else "—"
        end_sc_label = QLabel(end_sc)
        end_sc_label.setAlignment(Qt.AlignCenter)
        end_sc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        end_sc_label.setCursor(Qt.IBeamCursor)
        end_sc_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none;")
        balances_grid.addWidget(end_sc_label, row, 2)

        delta_total = self.session.delta_total if not is_active else None
        if not is_active and delta_total is None and self.session.starting_balance is not None and self.session.ending_balance is not None:
            delta_total = float(self.session.ending_balance) - float(self.session.starting_balance)
        delta_total_str = f"{float(delta_total):+.2f}" if delta_total is not None else "—"
        delta_color = "#2e7d32" if delta_total is not None and delta_total >= 0 else ("#c62828" if delta_total is not None else "black")
        delta_total_label = QLabel(delta_total_str)
        delta_total_label.setAlignment(Qt.AlignCenter)
        delta_total_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        delta_total_label.setCursor(Qt.IBeamCursor)
        delta_total_label.setStyleSheet(f"color: {delta_color}; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none;")
        balances_grid.addWidget(delta_total_label, row, 3)

        # Row: Redeemable
        row += 1
        redeem_label = QLabel("Redeemable:")
        redeem_label.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(redeem_label, row, 0)

        start_redeem = f"{float(self.session.starting_redeemable or 0):.2f}"
        start_redeem_label = QLabel(start_redeem)
        start_redeem_label.setAlignment(Qt.AlignCenter)
        start_redeem_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        start_redeem_label.setCursor(Qt.IBeamCursor)
        start_redeem_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-top: none;")
        balances_grid.addWidget(start_redeem_label, row, 1)

        end_redeem = f"{float(self.session.ending_redeemable or 0):.2f}" if not is_active and self.session.ending_redeemable is not None else "—"
        end_redeem_label = QLabel(end_redeem)
        end_redeem_label.setAlignment(Qt.AlignCenter)
        end_redeem_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        end_redeem_label.setCursor(Qt.IBeamCursor)
        end_redeem_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none; border-top: none;")
        balances_grid.addWidget(end_redeem_label, row, 2)

        delta_redeem = self.session.delta_redeem if not is_active else None
        if not is_active and delta_redeem is None and self.session.starting_redeemable is not None and self.session.ending_redeemable is not None:
            delta_redeem = float(self.session.ending_redeemable) - float(self.session.starting_redeemable)
        delta_redeem_str = f"{float(delta_redeem):+.2f}" if delta_redeem is not None else "—"
        delta_redeem_color = "#2e7d32" if delta_redeem is not None and delta_redeem >= 0 else ("#c62828" if delta_redeem is not None else "black")
        delta_redeem_label = QLabel(delta_redeem_str)
        delta_redeem_label.setAlignment(Qt.AlignCenter)
        delta_redeem_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        delta_redeem_label.setCursor(Qt.IBeamCursor)
        delta_redeem_label.setStyleSheet(f"color: {delta_redeem_color}; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none; border-top: none;")
        balances_grid.addWidget(delta_redeem_label, row, 3)

        # Row: Basis
        row += 1
        basis_label = QLabel("Basis:")
        basis_label.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(basis_label, row, 0)

        start_basis_label = QLabel("0.00")
        start_basis_label.setAlignment(Qt.AlignCenter)
        start_basis_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        start_basis_label.setCursor(Qt.IBeamCursor)
        start_basis_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-top: none;")
        balances_grid.addWidget(start_basis_label, row, 1)

        basis_val = None if is_active else (self.session.basis_consumed if self.session.basis_consumed is not None else self.session.session_basis)
        end_basis_str = format_currency(basis_val) if basis_val is not None else "—"
        end_basis_label = QLabel(end_basis_str)
        end_basis_label.setAlignment(Qt.AlignCenter)
        end_basis_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        end_basis_label.setCursor(Qt.IBeamCursor)
        end_basis_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none; border-top: none;")
        balances_grid.addWidget(end_basis_label, row, 2)

        delta_basis_label = QLabel(end_basis_str)
        delta_basis_label.setAlignment(Qt.AlignCenter)
        delta_basis_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        delta_basis_label.setCursor(Qt.IBeamCursor)
        delta_basis_label.setStyleSheet("color: black; padding: 6px; border: 1px solid rgba(0, 0, 0, 0.2); border-left: none; border-top: none;")
        balances_grid.addWidget(delta_basis_label, row, 3)

        # Spacer row
        row += 1
        spacer = QWidget()
        spacer.setFixedHeight(12)
        balances_grid.addWidget(spacer, row, 0, 1, 4)
        
        # Row: Net P/L
        row += 1
        net_pl_label = QLabel("Net P/L:")
        net_pl_label.setStyleSheet("font-weight: bold; padding: 6px;")
        balances_grid.addWidget(net_pl_label, row, 0)

        net_val = None if is_active else self.session.net_taxable_pl
        if net_val is None and not is_active:
            net_val = 0.0
        net_display = f"+${float(net_val):.2f}" if net_val is not None and float(net_val) >= 0 else (f"${float(net_val):.2f}" if net_val is not None else "—")
        net_color = "#2e7d32" if net_val is not None and net_val >= 0 else ("#c62828" if net_val is not None else "black")
        net_pl_value = QLabel(net_display)
        net_pl_value.setAlignment(Qt.AlignCenter)
        net_pl_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        net_pl_value.setCursor(Qt.IBeamCursor)
        net_pl_value.setStyleSheet(f"color: {net_color}; padding: 6px;")
        balances_grid.addWidget(net_pl_value, row, 1, 1, 3)

        balances_grid.setColumnStretch(1, 1)
        balances_grid.setColumnStretch(2, 1)
        balances_grid.setColumnStretch(3, 1)

        balances_layout.addWidget(table_container)
        balances_layout.addStretch(1)

        columns_layout.addWidget(balances_section, 1)
        
        layout.addWidget(columns_widget)

        # ─────── Notes (as subsection like Game Stats/Balances) ───────
        notes_section = QWidget()
        notes_section.setObjectName("SectionBackground")
        notes_layout = QVBoxLayout(notes_section)
        notes_layout.setContentsMargins(10, 8, 10, 8)
        notes_layout.setSpacing(6)

        # Subsection header
        notes_label = QLabel("📝 Notes")
        notes_label.setObjectName("SectionHeader")
        notes_layout.addWidget(notes_label)

        notes_value = self.session.notes or ""
        if notes_value:
            notes_display = QPlainTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(notes_value)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            notes_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QLabel("—")
            notes_empty.setObjectName("MutedLabel")
            notes_font = notes_empty.font()
            notes_font.setItalic(True)
            notes_empty.setFont(notes_font)
            notes_layout.addWidget(notes_empty)

        layout.addWidget(notes_section)

        layout.addStretch(1)
        return widget

    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header"""
        label = QLabel(text)
        label.setObjectName("SectionHeader")
        return label

    def _create_value_chip(self, text, status="neutral"):
        """Create a ValueChip label"""
        chip = QLabel(text)
        chip.setObjectName("ValueChip")
        chip.setProperty("status", status)
        chip.setTextInteractionFlags(Qt.TextSelectableByMouse)
        chip.setAlignment(Qt.AlignCenter)
        return chip

    def _add_stat_row(self, grid, row, col, label_text, value_text, status="neutral"):
        """Add a label/value pair to the stats grid"""
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        grid.addWidget(label, row, col)

        value = self._create_value_chip(value_text, status)
        grid.addWidget(value, row, col + 1)

    def _format_datetime(self, date_val, time_val):
        """Format date and time for display"""
        if not date_val:
            return "—"
        date_str = self._format_date(date_val)
        time_str = time_val if time_val else "00:00"
        return f"{date_str} {time_str}"

    def _calculate_rtp_display(self, game):
        """Calculate and format RTP display"""
        if not game:
            return "—"
        
        # Build RTP display from available data (expected, actual, and/or session)
        parts = []
        if game.rtp is not None:
            parts.append(f"Exp: {float(game.rtp):.2f}%")
        
        act_rtp = float(game.actual_rtp) if getattr(game, "actual_rtp", None) is not None else None
        if act_rtp is not None:
            parts.append(f"Act: {act_rtp:.2f}%")
        
        session_rtp = float(self.session.rtp) if self.session.rtp is not None else None
        if session_rtp is not None:
            parts.append(f"Session: {session_rtp:.2f}%")
        
        return " / ".join(parts) if parts else "—"

    def _create_related_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        purchases_group = QGroupBox("Purchases Contributing to Basis (Before/During)")
        purchases_layout = QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        purchases = self._filter_purchases(self.linked_purchases)
        if not purchases:
            note = QLabel("No purchases contributed basis before or during this session.")
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.purchases_table = QTableWidget(0, 4)
            self.purchases_table.setHorizontalHeaderLabels(
                ["Date/Time", "Amount", "SC Received", "View"]
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
            self.purchases_table.setColumnWidth(0, 140)
            self.purchases_table.setColumnWidth(1, 90)
            self.purchases_table.setColumnWidth(2, 90)
            self.purchases_table.setColumnWidth(3, 120)
            purchases_layout.addWidget(self.purchases_table)
            self._populate_purchases_table(purchases)
        layout.addWidget(purchases_group, 1)

        redemptions_group = QGroupBox("Redemptions Affecting This Session")
        redemptions_layout = QVBoxLayout(redemptions_group)
        redemptions_layout.setContentsMargins(8, 10, 8, 8)
        redemptions = self._filter_redemptions(self.linked_redemptions, include_after=True)
        if not redemptions:
            note = QLabel("No redemptions affected this session.")
            note.setWordWrap(True)
            redemptions_layout.addWidget(note)
        else:
            self.redemptions_table = QTableWidget(0, 4)
            self.redemptions_table.setHorizontalHeaderLabels(
                ["Date/Time", "Amount", "Method", "View Redemption"]
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
            self.redemptions_table.setColumnWidth(0, 140)
            self.redemptions_table.setColumnWidth(1, 100)
            self.redemptions_table.setColumnWidth(2, 140)
            self.redemptions_table.setColumnWidth(3, 130)
            redemptions_layout.addWidget(self.redemptions_table)
            self._populate_redemptions_table(redemptions)
        layout.addWidget(redemptions_group, 1)
        return widget

    def _filter_purchases(self, purchases):
        allowed = {"BEFORE", "DURING", "MANUAL"}
        filtered = []
        for purchase in purchases:
            relation = (getattr(purchase, "link_relation", None) or "DURING").upper()
            if relation in allowed:
                filtered.append(purchase)
        return filtered

    def _filter_redemptions(self, redemptions, include_after: bool):
        allowed = {"DURING", "MANUAL"}
        if include_after:
            allowed.add("AFTER")
        filtered = []
        for redemption in redemptions:
            relation = (getattr(redemption, "link_relation", None) or "DURING").upper()
            if relation in allowed:
                filtered.append(redemption)
        return filtered

    def _toggle_after_cashouts(self):
        if not getattr(self, "redemptions_table", None):
            return
        include_after = self.include_after_check.isChecked()
        redemptions = self._filter_redemptions(self.linked_redemptions, include_after=include_after)
        self._populate_redemptions_table(redemptions)

    def _populate_purchases_table(self, purchases):
        self.purchases_table.setRowCount(len(purchases))
        for row_idx, purchase in enumerate(purchases):
            date_display = self._format_date(purchase.purchase_date) if purchase.purchase_date else "—"
            time_display = purchase.purchase_time if purchase.purchase_time else "—"
            date_time_display = f"{date_display} {time_display}" if date_display != "—" else time_display
            amount = format_currency(purchase.amount)
            sc_received = f"{float(purchase.sc_received or 0.0):.2f}"
            values = [date_time_display, amount, sc_received]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx in (1, 2):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.purchases_table.setItem(row_idx, col_idx, item)

            view_btn = QPushButton("👁️ View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase.id: self._open_purchase(pid)
            )
            view_container = QWidget()
            view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            view_layout = QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, Qt.AlignCenter)
            self.purchases_table.setCellWidget(row_idx, 3, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self, redemptions):
        self.redemptions_table.setRowCount(len(redemptions))
        for row_idx, redemption in enumerate(redemptions):
            date_display = self._format_date(redemption.redemption_date) if redemption.redemption_date else "—"
            time_display = (redemption.redemption_time or "00:00:00")[:5]
            date_time_display = f"{date_display} {time_display}" if date_display != "—" else time_display
            amount = format_currency(redemption.amount)

            is_total_loss = float(redemption.amount) == 0
            method_display = "Loss" if is_total_loss else (getattr(redemption, "method_name", None) or "—")

            values = [date_time_display, amount, method_display]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_idx == 1:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.redemptions_table.setItem(row_idx, col_idx, item)

            view_btn = QPushButton("👁️ View Redemption")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
            view_btn.clicked.connect(
                lambda _checked=False, rid=redemption.id: self._open_redemption(rid)
            )
            view_container = QWidget()
            view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            view_layout = QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, Qt.AlignCenter)
            self.redemptions_table.setCellWidget(row_idx, 3, view_container)
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
    """Modern end session dialog - modeled after Edit/Add Purchase and Redemption dialogs"""
    
    def __init__(self, facade, session, parent=None):
        super().__init__(parent)
        self.facade = facade
        self.session = session
        self.setWindowTitle("End Game Session")
        self.setMinimumWidth(700)
        # Heights are computed from layout size hints so the dialog starts
        # tight when notes are collapsed, but expands cleanly when shown.
        self._min_height_no_notes = 0
        self._min_height_with_notes = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setContentsMargins(10, 10, 10, 10)

        # ─────── Header Section: Start (read-only) + End (input) - 2 column layout ───────
        datetime_section = QWidget()
        datetime_section.setObjectName("SectionBackground")
        datetime_layout = QGridLayout(datetime_section)
        datetime_layout.setContentsMargins(12, 12, 12, 12)
        datetime_layout.setHorizontalSpacing(20)
        datetime_layout.setVerticalSpacing(8)

        # Left Column: Start Date + End Date with buttons
        # Row 0: Start Date
        start_date_label = QLabel("Start Date:")
        start_date_label.setObjectName("FieldLabel")
        start_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        datetime_layout.addWidget(start_date_label, 0, 0)

        self.start_date_display = QLabel(self._format_date(self.session.session_date))
        self.start_date_display.setObjectName("ValueChip")
        self.start_date_display.setProperty("status", "neutral")
        self.start_date_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        datetime_layout.addWidget(self.start_date_display, 0, 1)

        # Row 1: End Date with buttons
        end_date_label = QLabel("End Date:")
        end_date_label.setObjectName("FieldLabel")
        end_date_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        datetime_layout.addWidget(end_date_label, 1, 0)

        end_date_container = QWidget()
        end_date_layout = QHBoxLayout(end_date_container)
        end_date_layout.setContentsMargins(0, 0, 0, 0)
        end_date_layout.setSpacing(8)
        
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.date_edit.setFixedWidth(110)
        end_date_layout.addWidget(self.date_edit)
        
        self.calendar_btn = QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        end_date_layout.addWidget(self.calendar_btn)
        
        self.today_btn = QPushButton("Today")
        end_date_layout.addWidget(self.today_btn)
        end_date_layout.addStretch(1)
        
        datetime_layout.addWidget(end_date_container, 1, 1)

        # Right Column: Start Time + End Time with button
        # Row 0: Start Time
        start_time_label = QLabel("Start Time:")
        start_time_label.setObjectName("FieldLabel")
        start_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        datetime_layout.addWidget(start_time_label, 0, 2)

        self.start_time_display = QLabel(self._format_time(self.session.session_time))
        self.start_time_display.setObjectName("ValueChip")
        self.start_time_display.setProperty("status", "neutral")
        self.start_time_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        datetime_layout.addWidget(self.start_time_display, 0, 3)

        # Row 1: End Time with button
        end_time_label = QLabel("End Time:")
        end_time_label.setObjectName("FieldLabel")
        end_time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        datetime_layout.addWidget(end_time_label, 1, 2)

        end_time_container = QWidget()
        end_time_layout = QHBoxLayout(end_time_container)
        end_time_layout.setContentsMargins(0, 0, 0, 0)
        end_time_layout.setSpacing(8)
        
        self.time_edit = QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM:SS")
        self.time_edit.setFixedWidth(90)
        end_time_layout.addWidget(self.time_edit)
        
        self.now_btn = QPushButton("Now")
        end_time_layout.addWidget(self.now_btn)
        end_time_layout.addStretch(1)
        
        datetime_layout.addWidget(end_time_container, 1, 3)

        form.addWidget(datetime_section, 0, 0, 1, 7)

        # ─────── Section 1: Balances (Inputs) ───────
        section1_header = self._create_section_header("💰  Balances")
        form.addWidget(section1_header, 1, 0, 1, 7)

        balances_section = QWidget()
        balances_section.setObjectName("SectionBackground")
        balances_layout = QGridLayout(balances_section)
        balances_layout.setContentsMargins(12, 12, 12, 12)
        balances_layout.setHorizontalSpacing(20)
        balances_layout.setVerticalSpacing(8)

        # Left Column: End Total SC, Wager Amount
        # Right Column: End Redeemable SC
        row = 0
        
        # Left: End Total SC
        end_total_label = QLabel("End Total SC:")
        end_total_label.setObjectName("FieldLabel")
        end_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balances_layout.addWidget(end_total_label, row, 0)
        
        self.end_total_edit = QLineEdit()
        self.end_total_edit.setPlaceholderText("0.00")
        self.end_total_edit.setFixedWidth(140)
        balances_layout.addWidget(self.end_total_edit, row, 1)

        # Right: End Redeemable SC
        end_redeem_label = QLabel("End Redeemable SC:")
        end_redeem_label.setObjectName("FieldLabel")
        end_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balances_layout.addWidget(end_redeem_label, row, 2)
        
        self.end_redeem_edit = QLineEdit()
        self.end_redeem_edit.setPlaceholderText("0.00")
        self.end_redeem_edit.setFixedWidth(140)
        balances_layout.addWidget(self.end_redeem_edit, row, 3)

        # Left: Wager Amount
        row += 1
        wager_label = QLabel("Wager Amount:")
        wager_label.setObjectName("FieldLabel")
        wager_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        balances_layout.addWidget(wager_label, row, 0)
        
        self.wager_edit = QLineEdit()
        self.wager_edit.setPlaceholderText("0.00")
        self.wager_edit.setFixedWidth(140)
        balances_layout.addWidget(self.wager_edit, row, 1)

        balances_layout.setColumnStretch(1, 1)
        balances_layout.setColumnStretch(3, 1)
        form.addWidget(balances_section, 2, 0, 1, 7)

        # ─────── Section 2: Session Details (Read-only calculated) ───────
        section2_header = self._create_section_header("📊  Session Details")
        form.addWidget(section2_header, 3, 0, 1, 7)

        details_section = QWidget()
        details_section.setObjectName("SectionBackground")
        details_layout = QGridLayout(details_section)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setHorizontalSpacing(20)
        details_layout.setVerticalSpacing(8)

        # Left Column: Start SC, Δ Total, Δ Redeemable, RTP
        # Right Column: Start Redeemable, Δ Basis, Net P/L
        row = 0
        
        # Left: Start SC
        start_sc_label = QLabel("Start SC:")
        start_sc_label.setObjectName("FieldLabel")
        start_sc_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(start_sc_label, row, 0)
        
        self.start_sc_display = QLabel(f"{float(self.session.starting_balance or 0):.2f}")
        self.start_sc_display.setObjectName("ValueChip")
        self.start_sc_display.setProperty("status", "neutral")
        self.start_sc_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.start_sc_display, row, 1)

        # Right: Start Redeemable
        start_redeem_label = QLabel("Start Redeemable:")
        start_redeem_label.setObjectName("FieldLabel")
        start_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(start_redeem_label, row, 2)
        
        self.start_redeem_display = QLabel(f"{float(self.session.starting_redeemable or 0):.2f}")
        self.start_redeem_display.setObjectName("ValueChip")
        self.start_redeem_display.setProperty("status", "neutral")
        self.start_redeem_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.start_redeem_display, row, 3)

        # Left: Δ Total
        row += 1
        delta_total_label = QLabel("Δ Total:")
        delta_total_label.setObjectName("FieldLabel")
        delta_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(delta_total_label, row, 0)
        
        self.delta_total_display = QLabel("—")
        self.delta_total_display.setObjectName("ValueChip")
        self.delta_total_display.setProperty("status", "neutral")
        self.delta_total_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.delta_total_display, row, 1)

        # Right: Δ Basis
        delta_basis_label = QLabel("Δ Basis:")
        delta_basis_label.setObjectName("FieldLabel")
        delta_basis_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(delta_basis_label, row, 2)
        
        self.delta_basis_display = QLabel("—")
        self.delta_basis_display.setObjectName("ValueChip")
        self.delta_basis_display.setProperty("status", "neutral")
        self.delta_basis_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.delta_basis_display, row, 3)

        # Left: Δ Redeemable
        row += 1
        delta_redeem_label = QLabel("Δ Redeemable:")
        delta_redeem_label.setObjectName("FieldLabel")
        delta_redeem_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(delta_redeem_label, row, 0)
        
        self.delta_redeem_display = QLabel("—")
        self.delta_redeem_display.setObjectName("ValueChip")
        self.delta_redeem_display.setProperty("status", "neutral")
        self.delta_redeem_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.delta_redeem_display, row, 1)

        # Right: Net P/L
        net_pl_label = QLabel("Net P/L:")
        net_pl_label.setObjectName("FieldLabel")
        net_pl_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(net_pl_label, row, 2)
        
        self.net_pl_display = QLabel("—")
        self.net_pl_display.setObjectName("ValueChip")
        self.net_pl_display.setProperty("status", "neutral")
        self.net_pl_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.net_pl_display, row, 3)

        # Left: Game Type
        row += 1
        game_type_label = QLabel("Game Type:")
        game_type_label.setObjectName("FieldLabel")
        game_type_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(game_type_label, row, 0)
        
        self.game_type_display = QLabel(self._get_game_type())
        self.game_type_display.setObjectName("ValueChip")
        self.game_type_display.setProperty("status", "neutral")
        self.game_type_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.game_type_display, row, 1)

        # Right: Game
        game_label = QLabel("Game:")
        game_label.setObjectName("FieldLabel")
        game_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(game_label, row, 2)
        
        self.game_display = QLabel(self._get_game_name())
        self.game_display.setObjectName("ValueChip")
        self.game_display.setProperty("status", "neutral")
        self.game_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        details_layout.addWidget(self.game_display, row, 3)

        # Left: RTP (spans both columns)
        row += 1
        rtp_label = QLabel("RTP:")
        rtp_label.setObjectName("FieldLabel")
        rtp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        details_layout.addWidget(rtp_label, row, 0)
        
        rtp_container = QWidget()
        rtp_layout = QHBoxLayout(rtp_container)
        rtp_layout.setContentsMargins(0, 0, 0, 0)
        rtp_layout.setSpacing(6)
        
        self.rtp_display = QLabel("—")
        self.rtp_display.setObjectName("ValueChip")
        self.rtp_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.rtp_display.setFixedHeight(28)
        self.rtp_display.setProperty("status", "neutral")
        self.rtp_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rtp_layout.addWidget(self.rtp_display)
        
        self.rtp_help_btn = QPushButton("?")
        self.rtp_help_btn.setFixedSize(22, 22)
        self.rtp_help_btn.setToolTip("Click for RTP explanation")
        self.rtp_help_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rtp_help_btn.setCursor(Qt.PointingHandCursor)
        self.rtp_help_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                border: 1px solid #0052a3;
                border-radius: 11px;
                font-weight: bold;
                font-size: 11px;
                padding: 0px;
                margin: 0px;
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
        """)
        self.rtp_help_btn.clicked.connect(self._show_rtp_help)
        rtp_layout.addWidget(self.rtp_help_btn)
        rtp_layout.addStretch(1)
        details_layout.addWidget(rtp_container, row, 1, 1, 3)

        details_layout.setColumnStretch(1, 1)
        details_layout.setColumnStretch(3, 1)
        form.addWidget(details_section, 4, 0, 1, 7)

        # ─────── Section 3: Notes (Collapsible) ───────
        self.notes_collapsed = True
        self.notes_toggle = QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        form.addWidget(self.notes_toggle, 5, 0, 1, 7)

        self.notes_section = QWidget()
        self.notes_section.setObjectName("SectionBackground")
        self.notes_section.setVisible(False)
        notes_section_layout = QVBoxLayout(self.notes_section)
        notes_section_layout.setContentsMargins(12, 12, 12, 12)
        
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(90)
        self.notes_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        notes_section_layout.addWidget(self.notes_edit)
        
        form.addWidget(self.notes_section, 6, 0, 1, 7)

        # Auto-populate notes if they exist, but start collapsed so the dialog
        # opens compact. Expanding will resize the dialog accordingly.
        existing_notes = self.session.notes or ""
        if existing_notes:
            self.notes_edit.setPlainText(existing_notes)
            self.notes_toggle.setText("📝 Show Notes...")

        form.setColumnStretch(0, 1)
        form.setColumnStretch(4, 1)

        layout.addLayout(form)
        layout.addStretch(1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("✖️ Cancel")
        # Note: Qt uses '&' to denote mnemonics; use '&&' to render a literal '&'.
        self.end_and_start_btn = QPushButton("🎮 End && Start New")
        self.save_btn = QPushButton("💾 End Session")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.end_and_start_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.today_btn.clicked.connect(self._set_today)
        self.now_btn.clicked.connect(self._set_now)
        self.calendar_btn.clicked.connect(self._pick_date)
        self.end_total_edit.textChanged.connect(self._update_session_details)
        self.end_redeem_edit.textChanged.connect(self._update_session_details)
        self.wager_edit.textChanged.connect(self._update_session_details)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.end_total_edit.textChanged.connect(self._validate_inline)
        self.end_redeem_edit.textChanged.connect(self._validate_inline)
        self.wager_edit.textChanged.connect(self._validate_inline)

        # Set tab order
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.end_total_edit)
        self.setTabOrder(self.end_total_edit, self.end_redeem_edit)
        self.setTabOrder(self.end_redeem_edit, self.wager_edit)
        self.setTabOrder(self.wager_edit, self.notes_edit)
        self.setTabOrder(self.notes_edit, self.save_btn)

        # Initialize
        self._set_today()
        self._set_now()
        self._validate_inline()
        
        self._update_session_details()

        # Compute tight collapsed/expanded heights and start collapsed.
        # This avoids "Session Details" being scrunched while keeping the
        # initial dialog smaller when notes already exist.
        self._compute_height_presets()
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), max(self.height(), self._min_height_no_notes))

    def _compute_height_presets(self) -> None:
        """Compute min heights for collapsed vs expanded notes states."""
        self.notes_section.setVisible(False)
        self.adjustSize()
        collapsed_hint = int(self.sizeHint().height())
        self._min_height_no_notes = max(collapsed_hint, 580)

        self.notes_section.setVisible(True)
        self.adjustSize()
        expanded_hint = int(self.sizeHint().height())
        self._min_height_with_notes = max(expanded_hint, self._min_height_no_notes + 100)

        self.notes_section.setVisible(True)
        self.notes_collapsed = False
        self.notes_toggle.setText("📝 Notes")
        self.setMinimumHeight(self._min_height_with_notes)
        self.resize(self.width(), max(self.height(), self._min_height_with_notes))

        self.notes_section.setVisible(False)
        self.notes_collapsed = True
        if (self.session.notes or ""):
            self.notes_toggle.setText("📝 Show Notes...")
        else:
            self.notes_toggle.setText("📝 Add Notes...")
        self.setMinimumHeight(self._min_height_no_notes)
        self.resize(self.width(), self._min_height_no_notes)
    
    def _get_game_type(self) -> str:
        """Get game type name for this session"""
        if not self.session.game_id:
            return "—"
        try:
            game = self.facade.get_game(self.session.game_id)
            if not game or not getattr(game, "game_type_id", None):
                return "—"

            game_type = self.facade.get_game_type(game.game_type_id)
            if game_type and getattr(game_type, "name", None):
                return game_type.name
        except Exception:
            return "—"
        return "—"
    
    def _get_game_name(self) -> str:
        """Get game name for this session"""
        if not self.session.game_id:
            return "—"
        try:
            game = self.facade.get_game(self.session.game_id)
            if game and getattr(game, "name", None):
                return game.name
        except Exception:
            return "—"
        return "—"
    
    def _create_section_header(self, text: str) -> QLabel:
        """Create a section header"""
        label = QLabel(text)
        label.setObjectName("SectionHeader")
        return label
    
    def _format_date(self, date_val):
        """Format date for display"""
        if not date_val:
            return "—"
        if isinstance(date_val, str):
            try:
                dt = datetime.strptime(date_val, "%Y-%m-%d")
                return dt.strftime("%m/%d/%Y")
            except:
                return str(date_val)
        return date_val.strftime("%m/%d/%Y") if hasattr(date_val, 'strftime') else str(date_val)
    
    def _format_time(self, time_val):
        """Format time for display"""
        if not time_val:
            return "—"
        if isinstance(time_val, str):
            # Already formatted as HH:MM:SS or HH:MM
            return time_val if len(time_val) >= 5 else time_val
        return time_val.strftime("%H:%M") if hasattr(time_val, 'strftime') else str(time_val)
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            if (self.session.notes or ""):
                self.notes_toggle.setText("📝 Show Notes...")
            else:
                self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(self._min_height_no_notes)
            self.resize(self.width(), self._min_height_no_notes)
        else:
            self.notes_toggle.setText("📝 Notes")
            self.setMinimumHeight(self._min_height_with_notes)
            self.resize(self.width(), max(self.height(), self._min_height_with_notes))
            self.notes_edit.setFocus()
    
    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        """Set time to current time with seconds precision."""
        self.time_edit.setText(datetime.now().strftime("%H:%M:%S"))

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
        cancel_btn = QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))
    
    def _show_rtp_help(self):
        """Show help dialog explaining RTP components"""
        QMessageBox.information(
            self,
            "RTP (Return to Player) Explanation",
            "<b>Exp (Expected):</b> The game's advertised/theoretical RTP percentage from the setup tab. "
            "This is the static baseline provided by the casino.<br><br>"
            "<b>Act (Actual):</b> The cumulative RTP across ALL other closed sessions for this game "
            "(excluding this session). Calculated as ((total_wager + total_delta) / total_wager) × 100.<br><br>"
            "<b>Session:</b> The RTP for THIS specific session only, calculated in real-time as you type. "
            "Formula: ((wager + delta_total) / wager) × 100, where delta_total = ending_balance - starting_balance.<br><br>"
            "<i>When you save, the Actual RTP will be updated to include this session's contribution.</i>"
        )

    def _update_rtp_display(self, delta_total, wager):
        """Update RTP display: Exp / Act / Session (real-time) - reuses logic from Edit Closed Session
        
        Shows all available metrics (expected, actual, and/or session)
        """
        parts = []
        
        # Part 1 & 2: Expected and Actual RTP (only if we have a game_id)
        if self.session.game_id:
            # Get game data using facade
            try:
                game = self.facade.game_repo.get_by_id(self.session.game_id) if self.facade.game_repo else None
                if game:
                    # Expected RTP
                    if game.rtp is not None:
                        parts.append(f"Exp: {float(game.rtp):.2f}%")
                    
                    # Actual RTP from aggregates
                    try:
                        conn = self.facade.game_session_service.session_repo.db._connection
                        c = conn.cursor()
                        c.execute(
                            """
                            SELECT total_wager, total_delta, session_count
                            FROM game_rtp_aggregates
                            WHERE game_id = ?
                            """,
                            (game.id,),
                        )
                        agg_row = c.fetchone()
                        if agg_row:
                            total_wager = float(agg_row["total_wager"] or 0)
                            total_delta = float(agg_row["total_delta"] or 0)
                            if total_wager > 0:
                                actual_rtp = ((total_wager + total_delta) / total_wager) * 100.0
                                parts.append(f"Act: {actual_rtp:.2f}%")
                    except Exception:
                        if getattr(game, "actual_rtp", None) is not None:
                            parts.append(f"Act: {float(game.actual_rtp):.2f}%")
            except:
                pass
        
        # Part 3: Session RTP (real-time calculation - always attempt if wager provided)
        if wager is not None and delta_total is not None:
            try:
                wager_float = float(wager)
                delta_total_float = float(delta_total)
                if wager_float > 0:
                    session_rtp = ((wager_float + delta_total_float) / wager_float) * 100.0
                    parts.append(f"Session: {session_rtp:.2f}%")
            except (ValueError, TypeError, ZeroDivisionError):
                pass

        if parts:
            self.rtp_display.setText(" / ".join(parts))
        else:
            self.rtp_display.setText("—")
        self.rtp_display.setProperty("status", "neutral")
        self.rtp_display.style().unpolish(self.rtp_display)
        self.rtp_display.style().polish(self.rtp_display)
    
    def _update_session_details(self):
        """Update all calculated fields in real-time - reuses P/L calculation logic"""
        start_total = Decimal(str(self.session.starting_balance or 0))
        start_redeem = Decimal(str(self.session.starting_redeemable or 0))

        # Parse user inputs
        end_total_text = self.end_total_edit.text().strip()
        end_redeem_text = self.end_redeem_edit.text().strip()
        wager_text = self.wager_edit.text().strip()

        end_total = None
        end_redeem = None
        wager = None

        if end_total_text:
            valid, result = validate_currency(end_total_text)
            if valid:
                end_total = Decimal(str(result))

        if end_redeem_text:
            valid, result = validate_currency(end_redeem_text)
            if valid:
                end_redeem = Decimal(str(result))

        if wager_text:
            valid, result = validate_currency(wager_text)
            if valid:
                wager = Decimal(str(result))

        # Calculate and display Δ Total
        delta_total = None
        if end_total is not None:
            delta_total = end_total - start_total
            self._update_value_chip(
                self.delta_total_display,
                f"{float(delta_total):+.2f}",
                "positive" if delta_total > 0 else ("negative" if delta_total < 0 else "neutral")
            )
        else:
            self._update_value_chip(self.delta_total_display, "—", "neutral")

        # Calculate and display Δ Redeemable
        delta_redeem = None
        if end_redeem is not None:
            delta_redeem = end_redeem - start_redeem
            self._update_value_chip(
                self.delta_redeem_display,
                f"{float(delta_redeem):+.2f}",
                "positive" if delta_redeem > 0 else ("negative" if delta_redeem < 0 else "neutral")
            )
        else:
            self._update_value_chip(self.delta_redeem_display, "—", "neutral")

        # Calculate Δ Basis and Net P/L (if we have both ending values)
        if end_total is not None and end_redeem is not None:
            # Get site SC rate
            site = self.facade.site_repo.get_by_id(self.session.site_id) if self.facade.site_repo else None
            sc_rate = Decimal(str(getattr(site, "sc_rate", "1.0"))) if site else Decimal("1.0")

            # Retrieve expected start redeemable
            expected_start_redeem = Decimal(str(self.session.expected_start_redeemable or start_redeem))
            
            # Calculate session basis by querying purchases up to session end
            # This is the LIVE calculation - matches backend logic in game_session_service.py
            from datetime import datetime
            from ..input_parsers import parse_date_input, parse_time_input
            
            # Get previous session's end datetime (checkpoint)
            prev_checkpoint_dt = None
            prev_sessions = self.facade.game_session_repo.get_chronological(
                self.session.user_id,
                self.session.site_id
            )
            for prev_sess in prev_sessions:
                if prev_sess.status == "Closed" and prev_sess.id != self.session.id:
                    if prev_sess.end_date:
                        prev_end_time = prev_sess.end_time or "00:00:00"
                        if len(prev_end_time) == 5:
                            prev_end_time = f"{prev_end_time}:00"
                        prev_checkpoint_dt = datetime.combine(
                            prev_sess.end_date,
                            datetime.strptime(prev_end_time, "%H:%M:%S").time()
                        )
            
            # Get session end datetime from dialog fields
            try:
                session_end_date_str = self.date_edit.text().strip()
                session_end_date_val = parse_date_input(session_end_date_str)
                if not session_end_date_val:
                    # Can't calculate without valid date - fallback to session object value
                    session_end_date_val = self.session.end_date or self.session.session_date
                
                session_end_time_str = self.time_edit.text().strip() or "00:00:00"
                if len(session_end_time_str) == 5:
                    session_end_time_str = f"{session_end_time_str}:00"
                
                session_end_dt = datetime.combine(
                    session_end_date_val,
                    datetime.strptime(session_end_time_str, "%H:%M:%S").time()
                )
            except (ValueError, AttributeError):
                # If parsing fails, use session's existing end date or session start date
                fallback_date = self.session.end_date or self.session.session_date
                fallback_time = self.session.end_time or self.session.session_time or "00:00:00"
                if len(fallback_time) == 5:
                    fallback_time = f"{fallback_time}:00"
                session_end_dt = datetime.combine(
                    fallback_date,
                    datetime.strptime(fallback_time, "%H:%M:%S").time()
                )
            
            # Query purchases between prev checkpoint and session end
            all_purchases = self.facade.purchase_repo.get_by_user_and_site(
                self.session.user_id,
                self.session.site_id
            )
            
            session_basis = Decimal("0.00")
            for purch in all_purchases:
                purch_time_str = purch.purchase_time or "00:00:00"
                if len(purch_time_str) == 5:
                    purch_time_str = f"{purch_time_str}:00"
                purch_dt = datetime.combine(
                    purch.purchase_date,
                    datetime.strptime(purch_time_str, "%H:%M:%S").time()
                )
                
                # Check if purchase is in window (after prev checkpoint, before or at session end)
                if prev_checkpoint_dt and purch_dt < prev_checkpoint_dt:
                    continue  # Before checkpoint
                if purch_dt <= session_end_dt:
                    session_basis += Decimal(str(purch.amount))
                else:
                    break  # Purchases are sorted chronologically

            # Calculate discoverable SC (freeplay/bonus)
            discoverable_sc = max(Decimal("0.00"), start_redeem - expected_start_redeem)

            # Calculate locked SC processing (basis consumption logic)
            locked_start = max(Decimal("0.00"), start_total - start_redeem)
            locked_end = max(Decimal("0.00"), end_total - end_redeem)
            locked_processed = max(Decimal("0.00"), locked_start - locked_end)
            basis_consumed = min(session_basis, locked_processed * sc_rate)

            # Calculate Net P/L
            net_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed

            # Display Δ Basis
            self._update_value_chip(
                self.delta_basis_display,
                f"${float(basis_consumed):,.2f}",
                "negative" if basis_consumed > 0 else "neutral"
            )

            # Display Net P/L
            if net_pl > 0:
                self._update_value_chip(self.net_pl_display, f"+${float(net_pl):,.2f}", "positive")
            elif net_pl < 0:
                self._update_value_chip(self.net_pl_display, f"${float(net_pl):,.2f}", "negative")
            else:
                self._update_value_chip(self.net_pl_display, "$0.00", "neutral")
        else:
            self._update_value_chip(self.delta_basis_display, "—", "neutral")
            self._update_value_chip(self.net_pl_display, "—", "neutral")

        # Update RTP display
        self._update_rtp_display(delta_total, wager)

    def _update_value_chip(self, label, text, status):
        """Helper to update a ValueChip label with text and status"""
        label.setText(text)
        label.setProperty("status", status)
        label.style().unpolish(label)
        label.style().polish(label)

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

