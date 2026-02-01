"""
Daily Sessions Tab - Aggregate game sessions by date
Shows hierarchical view: Date → User → Individual Sessions
"""
from PySide6 import QtWidgets, QtCore, QtGui
import shiboken6
from decimal import Decimal
from datetime import date, datetime
from app_facade import AppFacade
from ui.date_filter_widget import DateFilterWidget
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from ui.daily_sessions_filters import (
    ColumnFilterDialog,
    DateTimeFilterDialog,
    header_resize_section_index,
    header_menu_position,
)
from ui.tabs.game_sessions_tab import ViewSessionDialog


class DailySessionsTab(QtWidgets.QWidget):
    """Tab for viewing daily aggregated game sessions"""

    def __init__(self, facade: AppFacade, main_window=None):
        super().__init__()
        self.facade = facade
        self.main_window = main_window
        self.sessions = []
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter_values = set()
        self.column_filters = {}
        self.sort_column = None
        self.sort_reverse = False
        self._last_sessions = []
        self._suppress_header_menu = False
        
        # Build columns list based on tax withholding feature state
        self.columns = [
            "Date/User/Site",
            "Game",
            "Δ Redeem",
            "Δ Basis",
            "Δ Total (SC)",
            "Net P/L",
        ]
        
        # Add Tax Set-Aside column only if feature is enabled
        self.tax_column_enabled = False
        if hasattr(facade, 'tax_withholding_service'):
            try:
                config = facade.tax_withholding_service.get_config()
                if config.enabled:
                    self.columns.append("Tax Set-Aside")
                    self.tax_column_enabled = True
            except Exception:
                pass
        
        self.columns.extend(["Details", "Notes"])
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Search (header row)
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search daily sessions...")
        self.search_edit.setMaximumWidth(300)
        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Daily Sessions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        header_layout.addWidget(self.search_edit)
        header_layout.addWidget(self.search_clear_btn)
        header_layout.addWidget(self.clear_filters_btn)
        
        layout.addLayout(header_layout)
        
        # Info label
        info = QtWidgets.QLabel(
            "Daily rollup of closed sessions for tax reporting. "
            "Click a date to add notes or a session to view details."
        )
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filter (preferred widget)
        year_start = date(date.today().year, 1, 1)
        self.date_filter_widget = DateFilterWidget(
            default_start=year_start,
            default_end=date.today(),
        )
        self.date_filter_widget.filter_changed.connect(self.apply_date_filter)
        layout.addWidget(self.date_filter_widget)

        # Action row
        action_row = QtWidgets.QHBoxLayout()
        action_row.setSpacing(8)

        self.user_filter_btn = QtWidgets.QPushButton("👤 Filter Users...")
        self.user_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.user_filter_label, set())
        self.site_filter_btn = QtWidgets.QPushButton("🌐 Filter Sites...")
        self.site_filter_label = QtWidgets.QLabel("All")
        self._set_filter_label(self.site_filter_label, set())

        action_row.addWidget(self.user_filter_btn)
        action_row.addWidget(self.user_filter_label)
        action_row.addSpacing(12)
        action_row.addWidget(self.site_filter_btn)
        action_row.addWidget(self.site_filter_label)
        action_row.addStretch(1)

        self.notes_btn = QtWidgets.QPushButton("➕ Add Notes")
        self.notes_btn.setObjectName("PrimaryButton")
        self.view_btn = QtWidgets.QPushButton("👁️ View Session")
        view_text_width = self.view_btn.fontMetrics().horizontalAdvance(self.view_btn.text()) + 24
        dynamic_width = max(
            self.notes_btn.sizeHint().width(),
            self.view_btn.sizeHint().width(),
            view_text_width,
        )
        for btn in (self.notes_btn, self.view_btn):
            btn.setMinimumWidth(dynamic_width)
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

        self.expand_btn = QtWidgets.QPushButton("➕ Expand All")
        self.collapse_btn = QtWidgets.QPushButton("➖ Collapse All")
        self.export_btn = QtWidgets.QPushButton("📤 Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")

        self.actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.primary_btn_container)
        actions_layout.addWidget(self.expand_btn)
        actions_layout.addWidget(self.collapse_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.refresh_btn)
        action_row.addWidget(self.actions_container, 0, QtCore.Qt.AlignRight)
        layout.addLayout(action_row)
        
        # Tree widget
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 160)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 90)
        self.tree.setColumnWidth(4, 90)
        self.tree.setColumnWidth(5, 90)
        self.tree.setColumnWidth(6, 150)
        self.tree.setColumnWidth(7, 200)
        header.viewport().installEventFilter(self)
        self.tree.itemDoubleClicked.connect(lambda *_args: self.add_edit_notes())
        
        # Enable custom context menu for spreadsheet UX
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.tree, 1)
        
        # Add spreadsheet stats bar
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)
        
        # Set up keyboard shortcuts for spreadsheet UX
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.tree)
        copy_shortcut.activated.connect(self._copy_selection)

        self.search_edit.textChanged.connect(self.refresh_view)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.notes_btn.clicked.connect(self._handle_notes_clicked)
        self.view_btn.clicked.connect(self._handle_view_clicked)
        self.expand_btn.clicked.connect(self.tree.expandAll)
        self.collapse_btn.clicked.connect(self.tree.collapseAll)
        self.refresh_btn.clicked.connect(self.refresh_view)
        self.export_btn.clicked.connect(self._export_csv)
        self.user_filter_btn.clicked.connect(self._show_user_filter)
        self.site_filter_btn.clicked.connect(self._show_site_filter)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

        self.refresh_view()
    
    def _on_selection_changed(self):
        """Update stats bar and action buttons on selection change"""
        grid = SpreadsheetUXController.extract_selection_grid(self.tree)
        stats = SpreadsheetUXController.compute_stats(grid)
        self.stats_bar.update_stats(stats)
        self._update_action_buttons()

    def eventFilter(self, obj, event):
        if getattr(self, "tree", None) is not None and obj is self.tree.header().viewport():
            if not shiboken6.isValid(self.tree):
                return False
            header = self.tree.header()
            if not shiboken6.isValid(header):
                return False
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

    def apply_date_filter(self):
        start_date, end_date = self.date_filter_widget.get_date_range()
        self.active_date_filter = (start_date, end_date)
        self.refresh_view()

    def refresh_view(self):
        start_date, end_date = self.active_date_filter
        self.sessions = self.facade.get_daily_sessions_rows(
            start_date=start_date,
            end_date=end_date,
            selected_users=sorted(self.selected_users),
            selected_sites=sorted(self.selected_sites),
        )
        self._last_sessions = list(self.sessions)
        sessions = self._filter_sessions(self.sessions)
        data = self.facade.daily_sessions_service.group_sessions(sessions)
        data = self._sort_data(data)
        self._render_tree(data)
        self._update_action_buttons()
    
    def refresh_data(self):
        """Standardized refresh method for global refresh system (Issue #9)."""
        self.refresh_view()
    
    def _render_tree(self, data):
        self.tree.clear()
        for day in data:
            date_values = [
                f"📅 {day['date']}",
                "",
                self._format_delta(day["date_delta_redeem"]),
                self._format_currency_or_dash(day["date_basis"]),
                self._format_delta(day["date_gameplay"]),
                self._format_signed_currency(day["date_total"]),
            ]
            
            # Add tax column only if enabled
            if self.tax_column_enabled:
                date_tax = day.get("date_tax_withholding", 0)
                date_values.append(self._format_currency_or_dash(date_tax) if date_tax > 0 else "—")
            
            date_values.extend([
                f"{day['user_count']} users, {day['session_count']} sessions",
                day["notes"],
            ])
            date_item = QtWidgets.QTreeWidgetItem(date_values)
            date_item.setData(0, QtCore.Qt.UserRole, {"kind": "date", "date": day["date"]})
            self._apply_status_color(date_item, day["date_total"])
            self.tree.addTopLevelItem(date_item)

            for user in day["users"]:
                user_values = [
                    f"👤 {user['user_name']}",
                    "",
                    self._format_delta(user["delta_redeem"]),
                    self._format_currency_or_dash(user["basis"]),
                    self._format_delta(user["gameplay"]),
                    self._format_signed_currency(user["total"]),
                ]
                
                # Add tax column only if enabled
                if self.tax_column_enabled:
                    user_tax = user.get("tax_withholding", 0)
                    user_values.append(self._format_currency_or_dash(user_tax) if user_tax > 0 else "—")
                
                user_values.extend([
                    f"{len(user['sites'])} sites, {sum(len(site['sessions']) for site in user['sites'])} sessions",
                    "",
                ])
                user_item = QtWidgets.QTreeWidgetItem(user_values)
                user_item.setData(0, QtCore.Qt.UserRole, {"kind": "user", "user_id": user["user_id"]})
                self._apply_status_color(user_item, user["total"])
                date_item.addChild(user_item)

                for site in user["sites"]:
                    site_values = [
                        f"🏢 {site['site_name']}",
                        "",
                        self._format_delta(site["delta_redeem"]),
                        self._format_currency_or_dash(site["basis"]),
                        self._format_delta(site["gameplay"]),
                        self._format_signed_currency(site["total"]),
                    ]
                    
                    # Add tax column only if enabled
                    if self.tax_column_enabled:
                        site_tax = site.get("tax_withholding", 0)
                        site_values.append(self._format_currency_or_dash(site_tax) if site_tax > 0 else "—")
                    
                    site_values.extend([
                        f"{len(site['sessions'])} sessions",
                        "",
                    ])
                    site_item = QtWidgets.QTreeWidgetItem(site_values)
                    site_item.setData(0, QtCore.Qt.UserRole, {"kind": "site", "site_id": site["site_id"]})
                    self._apply_status_color(site_item, site["total"])
                    user_item.addChild(site_item)

                    for sess in site["sessions"]:
                        # Check if session spans multiple days
                        is_multi_day = sess.get("end_date") and sess.get("end_date") != sess.get("session_date")
                        
                        # Format time display
                        start_time = (sess["start_time"] or "00:00:00")[:5]
                        end_time = sess["end_time"][:5] if sess["end_time"] else ""
                        status = sess.get("status") or ""
                        
                        if is_multi_day and end_time:
                            # Show full dates for multi-day sessions
                            start_date = sess.get("session_date", "")
                            end_date = sess.get("end_date", "")
                            time_range = f"{start_date} {start_time} → {end_date} {end_time}"
                        elif end_time:
                            # Same day session
                            time_range = f"{start_time} → {end_time}"
                        elif status == "Closed":
                            time_range = f"{start_time} → Closed"
                        else:
                            time_range = f"{start_time} → Active"
                        
                        # Add clock emoji for multi-day sessions
                        session_prefix = "🕐 ⤷" if is_multi_day else "⤷"
                        
                        sess_values = [
                            f"{session_prefix} {sess['game_name'] or 'Unknown'}",
                            "",
                            self._format_delta(sess["delta_redeem"]),
                            self._format_currency_or_dash(sess["basis_consumed"]),
                            self._format_delta(sess["delta_total"]),
                            self._format_signed_currency(sess["total_taxable"]),
                        ]
                        
                        # Add tax column only if enabled
                        if self.tax_column_enabled:
                            sess_tax = sess.get("tax_withholding_amount", 0)
                            sess_values.append(self._format_currency_or_dash(sess_tax) if sess_tax and sess_tax > 0 else "—")
                        
                        sess_values.extend([
                            time_range,
                            sess["notes"],
                        ])
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
                        site_item.addChild(sess_item)

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
        try:
            return f"${float(value):,.2f}"
        except Exception:
            return "-"

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

    def _filter_sessions(self, sessions, exclude_col=None, include_search=True):
        if self.date_filter_values and exclude_col != 0:
            sessions = [s for s in sessions if s["session_date"] in self.date_filter_values]
        for col_index, values in self.column_filters.items():
            if col_index == exclude_col:
                continue
            if values:
                sessions = [s for s in sessions if self._session_value_for_column(s, col_index) in values]
        if include_search:
            term = self.search_edit.text().strip().lower()
            if term:
                sessions = [s for s in sessions if term in (s.get("search_blob") or "")]
        return sessions

    def _session_value_for_column(self, sess, col_index):
        if col_index == 0:
            return sess["session_date"]
        if col_index == 1:
            return sess["game_name"] or ""
        if col_index == 2:
            return self._format_delta(sess["delta_redeem"])
        if col_index == 3:
            return self._format_currency_or_dash(sess["basis_consumed"])
        if col_index == 4:
            return self._format_delta(sess["delta_total"])
        if col_index == 5:
            return self._format_signed_currency(sess["total_taxable"])
        
        # Tax column (index 6) only if feature enabled
        if self.tax_column_enabled and col_index == 6:
            amount = sess.get("tax_withholding_amount")
            if amount is not None and amount > 0:
                return f"${float(amount):,.2f}"
            return "—"
        
        # Adjust Details column index based on whether tax column is present
        details_col = 7 if self.tax_column_enabled else 6
        if col_index == details_col:
            # Check if session spans multiple days
            is_multi_day = sess.get("end_date") and sess.get("end_date") != sess.get("session_date")
            
            start_time = (sess["start_time"] or "00:00:00")[:5]
            end_time = sess["end_time"][:5] if sess["end_time"] else ""
            status = sess.get("status") or ""
            
            if is_multi_day and end_time:
                # Show full dates for multi-day sessions
                start_date = sess.get("session_date", "")
                end_date = sess.get("end_date", "")
                return f"{start_date} {start_time} → {end_date} {end_time}"
            elif end_time:
                # Same day session
                return f"{start_time} → {end_time}"
            elif status == "Closed":
                return f"{start_time} → Closed"
            else:
                return f"{start_time} → Active"
        
        # Notes column (last column, index varies based on tax column)
        notes_col = 8 if self.tax_column_enabled else 7
        if col_index == notes_col:
            return sess["notes"] or ""
        return ""

    def _show_header_menu(self, col_index):
        menu = QtWidgets.QMenu(self)
        sort_asc = menu.addAction("Sort Ascending")
        sort_desc = menu.addAction("Sort Descending")
        clear_sort = menu.addAction("Clear Sort")
        menu.addSeparator()
        filter_action = menu.addAction("Filter...")
        action = menu.exec(header_menu_position(self.tree.header(), col_index, menu))
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
                dialog = DateTimeFilterDialog(values, self.date_filter_values, self, show_time=False)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    self.date_filter_values = dialog.selected_values()
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

    def _sort_data(self, data):
        if self.sort_column is None:
            return data
        reverse = self.sort_reverse

        def sort_key(item):
            if self.sort_column in (0, 1):
                return item["date"]
            if self.sort_column == 2:
                return item["date_delta_redeem"]
            if self.sort_column == 3:
                return item["date_basis"]
            if self.sort_column == 4:
                return item["date_gameplay"]
            if self.sort_column == 5:
                return item["date_total"]
            
            # Tax column (6) only if enabled
            if self.tax_column_enabled and self.sort_column == 6:
                return item.get("date_tax_withholding", 0)
            
            # Details column (varies based on tax column)
            details_col = 7 if self.tax_column_enabled else 6
            if self.sort_column == details_col:
                return item["session_count"]
            
            # Notes column (last, varies based on tax column)
            notes_col = 8 if self.tax_column_enabled else 7
            if self.sort_column == notes_col:
                return 1 if item["notes"] else 0
            
            return item["date"]

        return sorted(data, key=sort_key, reverse=reverse)

    def _current_meta(self):
        item = self.tree.currentItem()
        if not item:
            return None
        return item.data(0, QtCore.Qt.UserRole) or {}

    def _update_action_buttons(self):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        has_selection = self.tree.selectionModel().hasSelection()
        
        if kind == "date":
            self.primary_btn_stack.setCurrentWidget(self.notes_btn)
        elif kind == "session":
            self.primary_btn_stack.setCurrentWidget(self.view_btn)
        else:
            self.primary_btn_stack.setCurrentWidget(self.primary_btn_placeholder)
        
        # Update spreadsheet stats bar
        if has_selection:
            grid = SpreadsheetUXController.extract_selection_grid(self.tree)
            stats = SpreadsheetUXController.compute_stats(grid)
            self.stats_bar.update_stats(stats)
        else:
            self.stats_bar.clear_stats()

    def _handle_notes_clicked(self):
        meta = self._current_meta() or {}
        if meta.get("kind") == "date":
            self._edit_daily_notes(meta.get("date"))

    def _handle_view_clicked(self):
        meta = self._current_meta() or {}
        if meta.get("kind") == "session":
            self._view_session(meta.get("session_id"))

    def add_edit_notes(self):
        item = self.tree.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "No Selection", "Select a day or game session.")
            return
        meta = item.data(0, QtCore.Qt.UserRole) or {}
        kind = meta.get("kind")
        if kind == "session":
            self._view_session(meta.get("session_id"))
        elif kind == "date":
            self._edit_daily_notes(meta.get("date"))
        else:
            QtWidgets.QMessageBox.information(self, "Selection", "Select a day or game session.")

    def _edit_daily_notes(self, session_date):
        if not session_date:
            return
        current_notes = self.facade.get_daily_note_for_date(session_date)
        dialog = DailySessionNotesDialog(session_date, current_notes, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_notes = dialog.notes_text()
        user_ids = [s["user_id"] for s in self.sessions if s["session_date"] == session_date]
        self.facade.set_daily_note_for_date(session_date, user_ids, new_notes)
        self.refresh_view()

    def _view_session(self, session_id):
        if not session_id:
            QtWidgets.QMessageBox.information(self, "No Session", "Select a game session.")
            return
        session = self.facade.get_game_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Selected session was not found.")
            return

        def handle_open():
            if self.main_window and hasattr(self.main_window, "open_session"):
                self.main_window.open_session(session_id)

        def handle_open_purchase(purchase_id: int):
            if self.main_window and hasattr(self.main_window, "open_purchase"):
                self.main_window.open_purchase(purchase_id)

        def handle_open_redemption(redemption_id: int):
            if self.main_window and hasattr(self.main_window, "open_redemption"):
                self.main_window.open_redemption(redemption_id)

        dialog = ViewSessionDialog(
            self.facade,
            session=session,
            parent=self,
            on_open_session=handle_open,
            on_open_purchase=handle_open_purchase,
            on_open_redemption=handle_open_redemption,
        )
        dialog.exec()

    def _show_user_filter(self):
        users = [u.name for u in self.facade.get_all_users(active_only=True)]
        if not users:
            QtWidgets.QMessageBox.information(self, "No Users", "No users found.")
            return
        dialog = ColumnFilterDialog(users, self.selected_users, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_users = dialog.selected_values()
            self._set_filter_label(self.user_filter_label, self.selected_users)
            self.refresh_view()

    def _show_site_filter(self):
        sites = [s.name for s in self.facade.get_all_sites(active_only=True)]
        if not sites:
            QtWidgets.QMessageBox.information(self, "No Sites", "No sites found.")
            return
        dialog = ColumnFilterDialog(sites, self.selected_sites, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_sites = dialog.selected_values()
            self._set_filter_label(self.site_filter_label, self.selected_sites)
            self.refresh_view()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.tree.clearSelection()
        self._update_action_buttons()

    def clear_all_filters(self):
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter_values = set()
        self.column_filters = {}
        self._set_filter_label(self.user_filter_label, self.selected_users)
        self._set_filter_label(self.site_filter_label, self.selected_sites)
        self.search_edit.clear()
        self._clear_selection()
        year_start = date(date.today().year, 1, 1)
        self.date_filter_widget.start_date.setText(year_start.strftime("%m/%d/%y"))
        self.date_filter_widget.end_date.setText(date.today().strftime("%m/%d/%y"))
        self.apply_date_filter()
    
    def find_and_select_session(self, session_id):
        def search_tree(parent_item):
            if parent_item is None:
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    result = search_tree(item)
                    if result:
                        return result
                return None
            meta = parent_item.data(0, QtCore.Qt.UserRole) or {}
            if meta.get("kind") == "session" and meta.get("session_id") == session_id:
                return parent_item
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                result = search_tree(child)
                if result:
                    return result
            return None

        session_item = search_tree(None)
        if not session_item:
            return False
        parent = session_item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree.setCurrentItem(session_item)
        self.tree.scrollToItem(session_item, QtWidgets.QAbstractItemView.PositionAtCenter)
        return True

    def view_daily_by_date(self, session_date):
        normalized = self._normalize_date_value(session_date)
        if not normalized:
            return
        date_text = normalized.strftime("%m/%d/%y")
        self.date_filter_widget.start_date.setText(date_text)
        self.date_filter_widget.end_date.setText(date_text)
        self.apply_date_filter()
        self.find_and_select_date(normalized)

    def find_and_select_date(self, session_date):
        normalized = self._normalize_date_value(session_date)
        if not normalized:
            return False
        target = normalized.isoformat()

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            meta = item.data(0, QtCore.Qt.UserRole) or {}
            if meta.get("kind") == "date" and meta.get("date") == target:
                item.setExpanded(True)
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item, QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
        return False

    def _normalize_date_value(self, value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            return None
    
    def _export_csv(self):
        """Export to CSV"""
        if not self.sessions:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Daily Sessions", 
            f"daily_sessions_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                import csv
                def iter_items(parent=None):
                    if parent is None:
                        for i in range(self.tree.topLevelItemCount()):
                            item = self.tree.topLevelItem(i)
                            yield item
                            yield from iter_items(item)
                    else:
                        for i in range(parent.childCount()):
                            child = parent.child(i)
                            yield child
                            yield from iter_items(child)

                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.columns)
                    for item in iter_items():
                        row_data = []
                        for col in range(len(self.columns)):
                            text = item.text(col)
                            if text.startswith('$') or text.startswith('-$'):
                                text = text.replace('$', '').replace(',', '')
                            row_data.append(text)
                        writer.writerow(row_data)
                
                QtWidgets.QMessageBox.information(
                    self, "Export Complete", 
                    f"Exported {len(self.sessions)} sessions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )
    
    def _copy_selection(self):
        """Copy selected cells to clipboard as TSV"""
        grid = SpreadsheetUXController.extract_selection_grid(self.tree)
        SpreadsheetUXController.copy_to_clipboard(grid)

    def _copy_with_headers(self):
        """Copy selected cells to clipboard with column headers"""
        grid = SpreadsheetUXController.extract_selection_grid(self.tree, include_headers=True)
        SpreadsheetUXController.copy_to_clipboard(grid)
    
    def _show_context_menu(self, position):
        """Show context menu for tree"""
        if not self.tree.selectionModel().hasSelection():
            return
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.tree.viewport().mapToGlobal(position))


class DailySessionNotesDialog(QtWidgets.QDialog):
    def __init__(self, session_date, notes, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Daily Session Notes - {session_date}")
        self.resize(520, 320)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QtWidgets.QLabel("Daily Session Notes")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setObjectName("NotesField")
        self.notes_edit.setPlainText(notes or "")
        layout.addWidget(self.notes_edit, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        clear_btn = QtWidgets.QPushButton("🧹 Clear")
        save_btn = QtWidgets.QPushButton("💾 Save")
        save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        cancel_btn.clicked.connect(self.reject)
        clear_btn.clicked.connect(lambda: self.notes_edit.clear())
        save_btn.clicked.connect(self.accept)

    def notes_text(self):
        return self.notes_edit.toPlainText().strip()
