"""
Unrealized tab - View open positions (sites with remaining basis)
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, datetime
from app_facade import AppFacade
from models.unrealized_position import UnrealizedPosition
from ui.date_filter_widget import DateFilterWidget
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar


class UnrealizedTab(QtWidgets.QWidget):
    """Tab for viewing unrealized positions (open positions with remaining basis)"""
    
    def __init__(self, facade: AppFacade, main_window=None):
        super().__init__()
        self.facade = facade
        self.main_window = main_window
        self.positions = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Unrealized Positions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search positions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_positions)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        
        layout.addLayout(header_layout)
        
        # Info label
        info = QtWidgets.QLabel(
            "Shows open positions with remaining purchase basis. Unrealized P/L is NOT taxable until you close a position."
        )
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filter
        self.date_filter = DateFilterWidget(
            default_start=date(2000, 1, 1),
            default_end=date.today(),
        )
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addStretch(1)

        self.close_btn = QtWidgets.QPushButton("🔒 Close Position")
        self.close_btn.setToolTip("Create $0 redemption to mark position dormant")
        self.close_btn.clicked.connect(self._close_balance)
        self.close_btn.setVisible(False)
        
        self.view_btn = QtWidgets.QPushButton("👁️ View Position")
        self.view_btn.clicked.connect(self._view_position)
        self.view_btn.setVisible(False)

        self.notes_btn = QtWidgets.QPushButton("📝 Add Notes")
        self.notes_btn.clicked.connect(self._add_notes)
        self.notes_btn.setVisible(False)

        toolbar.addWidget(self.view_btn)
        toolbar.addWidget(self.close_btn)
        toolbar.addWidget(self.notes_btn)

        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)

        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Site", "User", "Start Date", "Remaining Basis", 
            "Total SC (Est.)", "Redeemable SC (Position)", "Current Value", "Est. Unrealized P/L", 
            "Last Activity", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._add_notes)
        
        # Enable custom context menu for spreadsheet UX
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Add spreadsheet stats bar
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)
        
        self.table_filter = TableHeaderFilter(self.table, date_columns=[2, 7], refresh_callback=self.refresh_data)
        
        # Set up keyboard shortcuts for spreadsheet UX
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)
        
        # Totals
        totals_layout = QtWidgets.QHBoxLayout()
        totals_layout.addStretch()
        self.totals_label = QtWidgets.QLabel()
        self.totals_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        totals_layout.addWidget(self.totals_label)
        layout.addLayout(totals_layout)
        
        # Load data
        self.refresh_data()
    
    def focus_search(self):
        """Focus the search bar (for Cmd+F/Ctrl+F shortcut - Issue #99)"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_data(self):
        """Reload unrealized positions from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.positions = self.facade.get_unrealized_positions(start_date=start_date, end_date=end_date)
        self._populate_table(self.positions)
        self._update_totals()
    
    def _populate_table(self, positions):
        """Populate table with position data"""
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(positions))
        
            for row, pos in enumerate(positions):
                # Store position data
                site_item = QtWidgets.QTableWidgetItem(pos.site_name)
                site_item.setData(QtCore.Qt.UserRole, (pos.site_id, pos.user_id))
                self.table.setItem(row, 0, site_item)
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(pos.user_name))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(pos.start_date)))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"${pos.purchase_basis:,.2f}"))
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{pos.total_sc:,.2f}"))
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(f"{pos.redeemable_sc:,.2f}"))
                self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(f"${pos.current_value:,.2f}"))
                
                # Color P/L
                pl_item = QtWidgets.QTableWidgetItem(f"${pos.unrealized_pl:,.2f}")
                if pos.unrealized_pl > 0:
                    pl_item.setForeground(QtGui.QBrush(QtGui.QColor(0, 150, 0)))  # Green
                elif pos.unrealized_pl < 0:
                    pl_item.setForeground(QtGui.QBrush(QtGui.QColor(200, 0, 0)))  # Red
                self.table.setItem(row, 7, pl_item)
                
                self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(str(pos.last_activity) if pos.last_activity else ""))
                self.table.setItem(row, 9, QtWidgets.QTableWidgetItem(pos.notes))
                
                # Right-align numbers
                for col in [3, 4, 5, 6, 7]:
                    self.table.item(row, col).setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

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

        self.table_filter.apply_filters()
    
    def _update_totals(self):
        """Update totals footer"""
        if not self.positions:
            self.totals_label.setText("")
            return
        
        total_basis = sum(p.purchase_basis for p in self.positions)
        total_value = sum(p.current_value for p in self.positions)
        total_pl = sum(p.unrealized_pl for p in self.positions)
        
        color = "green" if total_pl >= 0 else "red"
        self.totals_label.setText(
            f"Totals: Basis: ${total_basis:,.2f} | Value: ${total_value:,.2f} | "
            f"<span style='color: {color}'>Unrealized P/L: ${total_pl:,.2f}</span>"
        )
    
    def _filter_positions(self, text):
        """Filter positions by search text"""
        if not text:
            self._populate_table(self.positions)
            return
        
        text = text.lower()
        filtered = [
            p for p in self.positions
            if text in p.site_name.lower() or text in p.user_name.lower()
        ]
        self._populate_table(filtered)

    def _clear_search(self):
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        self._populate_table(self.positions)

    def _clear_all_filters(self):
        self.search_edit.clear()
        self.date_filter.set_all_time()
        self.table.clearSelection()
        self._on_selection_changed()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()
        self.refresh_data()
    
    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        # Check if any cells are selected
        has_selection = self.table.selectionModel().hasSelection()
        
        # Get unique rows that have any selected cells
        selected_rows = self._get_selected_row_numbers()
        single = len(selected_rows) == 1
        self.view_btn.setVisible(single)
        self.notes_btn.setVisible(single)
        self.close_btn.setVisible(single)
        
        # Update spreadsheet stats bar
        if has_selection:
            grid = SpreadsheetUXController.extract_selection_grid(self.table)
            stats = SpreadsheetUXController.compute_stats(grid)
            self.stats_bar.update_stats(stats)
        else:
            self.stats_bar.clear_stats()

    def _get_selected_row_numbers(self):
        """Get list of unique row numbers that have any selected cells"""
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return []
        return sorted(set(index.row() for index in selected_indexes))
    
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
        
        menu = QtWidgets.QMenu(self)
        
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)
        
        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)
        
        menu.exec_(self.table.viewport().mapToGlobal(position))
    
    def _close_balance(self):
        """Close position (create $0 redemption to mark dormant)"""
        pos = self._selected_position()
        if not pos:
            return

        total_basis = pos.purchase_basis
        current_sc = pos.total_sc
        current_value = pos.current_value
        # When closing: the loss is the FULL cost basis (you're abandoning it all)
        net_loss = total_basis

        if total_basis <= 0:
            QtWidgets.QMessageBox.information(
                self, "No Balance", "No active basis to close for this site/user."
            )
            return

        message = (
            f"Close balance for {pos.site_name} ({pos.user_name})?\n\n"
            f"Current SC balance: {current_sc:.2f} SC (${current_value:.2f})\n"
            f"Cost basis: ${total_basis:.2f}\n"
            f"Net loss: ${net_loss:.2f} (abandoning all basis)\n\n"
            "This will:\n"
            f"• Mark {current_sc:.2f} SC as dormant (no basis attached)\n"
            "• Remove from Unrealized tab\n"
            f"• Show -${net_loss:.2f} cash flow loss in Realized tab\n"
            "• NO tax impact (not a deduction)\n"
            "• Dormant balance will reactivate if you play this site again\n\n"
            "Continue?"
        )
        confirm = QtWidgets.QMessageBox.question(self, "Close Balance", message)
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        try:
            result = self.facade.close_unrealized_position(
                pos.site_id,
                pos.user_id,
                current_sc=current_sc,
                current_value=current_value,
                total_basis=total_basis,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to close balance:\n{exc}")
            return

        self.refresh_data()
        QtWidgets.QMessageBox.information(
            self,
            "Success",
            f"Balance closed for {pos.site_name} ({pos.user_name})\n\n"
            f"Net cash flow loss: -${result['net_loss']:.2f}\n"
            f"Dormant SC balance: {result['current_sc']:.2f} SC (${result['current_value']:.2f})\n\n"
            f"The -${result['net_loss']:.2f} will show in Realized tab\n"
            f"Dormant ${result['current_value']:.2f} will reactivate on next session",
        )
    
    def _add_notes(self):
        """Add/edit notes for position"""
        pos = self._selected_position()
        if not pos:
            return

        dialog = UnrealizedNotesDialog(pos.notes, parent=self)
        if dialog.exec():
            notes = dialog.notes_text()
            try:
                self.facade.update_unrealized_notes(pos.site_id, pos.user_id, notes)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Notes", f"Failed to save notes:\n{exc}")
                return
            self.refresh_data()

    def _view_position(self):
        pos = self._selected_position()
        if not pos:
            return

        purchases = self.facade.get_unrealized_open_purchases(pos.site_id, pos.user_id)
        sessions = self.facade.get_unrealized_sessions(pos.site_id, pos.user_id)

        dialog = UnrealizedPositionDialog(
            pos,
            purchases,
            sessions,
            parent=self,
            on_open_purchase=self._open_purchase,
            on_open_session=self._open_session,
            on_close_position=self._close_balance,
        )
        dialog.exec()

    def _selected_position(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        data = item.data(QtCore.Qt.UserRole)
        if not data:
            return None
        site_id, user_id = data
        for pos in self.positions:
            if pos.site_id == site_id and pos.user_id == user_id:
                return pos
        return None

    def _open_purchase(self, purchase_id: int):
        if self.main_window and hasattr(self.main_window, "open_purchase"):
            self.main_window.open_purchase(purchase_id)

    def _open_session(self, session_id: int):
        if self.main_window and hasattr(self.main_window, "open_session"):
            self.main_window.open_session(session_id)
    
    def _export_csv(self):
        """Export positions to CSV"""
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Unrealized Positions", 
            f"unrealized_positions_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                import csv
                with open(filename, 'w', newline='') as f:
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
                
                QtWidgets.QMessageBox.information(
                    self, "Export Complete", 
                    f"Exported positions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )


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


class UnrealizedPositionDialog(QtWidgets.QDialog):
    def __init__(
        self,
        position: UnrealizedPosition,
        purchases,
        sessions,
        parent=None,
        on_open_purchase=None,
        on_open_session=None,
        on_close_position=None,
    ):
        super().__init__(parent)
        self.position = position
        self.purchases = purchases or []
        self.sessions = sessions or []
        self.on_open_purchase = on_open_purchase
        self.on_open_session = on_open_session
        self.on_close_position = on_close_position
        self.setWindowTitle("Unrealized Position")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        btn_row = QtWidgets.QHBoxLayout()
        if self.on_close_position:
            close_position_btn = QtWidgets.QPushButton("🔒 Close Position")
            close_position_btn.clicked.connect(self._handle_close_position)
            btn_row.addWidget(close_position_btn)
        
        btn_row.addStretch(1)
        
        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        
        layout.addLayout(btn_row)

    def _create_details_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        def make_selectable_label(text, bold=False, align_right=False, color=None):
            """Create a selectable QLabel"""
            label = QtWidgets.QLabel(text)
            if bold:
                font = label.font()
                font.setBold(True)
                label.setFont(font)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
            label.setCursor(QtCore.Qt.IBeamCursor)
            if align_right:
                label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            if color:
                label.setStyleSheet(f"color: {color};")
            return label
        
        def create_section(title_text):
            """Create a section container with header"""
            section_widget = QtWidgets.QWidget()
            section_widget.setObjectName("SectionBackground")
            section_layout = QtWidgets.QVBoxLayout(section_widget)
            section_layout.setContentsMargins(10, 8, 10, 8)
            section_layout.setSpacing(6)
            
            # Section header
            section_header = QtWidgets.QLabel(title_text)
            section_header.setObjectName("SectionHeader")
            section_layout.addWidget(section_header)
            
            return section_widget, section_layout

        # ========== TOP HEADER (Full Width) ==========
        header_section, header_layout = create_section("📊 Position Details")
        header_grid = QtWidgets.QGridLayout()
        header_grid.setContentsMargins(0, 4, 0, 0)
        header_grid.setHorizontalSpacing(12)
        header_grid.setVerticalSpacing(6)
        header_grid.setColumnStretch(1, 1)
        header_grid.setColumnStretch(3, 1)
        
        # Left column
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("MutedLabel")
        header_grid.addWidget(site_label, 0, 0)
        header_grid.addWidget(make_selectable_label(self.position.site_name), 0, 1)
        
        start_date_label = QtWidgets.QLabel("Start Date:")
        start_date_label.setObjectName("MutedLabel")
        header_grid.addWidget(start_date_label, 1, 0)
        header_grid.addWidget(make_selectable_label(self._format_date(self.position.start_date)), 1, 1)
        
        # Right column
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("MutedLabel")
        header_grid.addWidget(user_label, 0, 2)
        header_grid.addWidget(make_selectable_label(self.position.user_name), 0, 3)
        
        last_activity_label = QtWidgets.QLabel("Last Activity:")
        last_activity_label.setObjectName("MutedLabel")
        header_grid.addWidget(last_activity_label, 1, 2)
        header_grid.addWidget(make_selectable_label(self._format_date(self.position.last_activity)), 1, 3)
        
        header_layout.addLayout(header_grid)
        layout.addWidget(header_section)

        # ========== TWO-COLUMN LAYOUT ==========
        columns_widget = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(12)
        
        # ========== LEFT COLUMN ==========
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)
        
        # Key Metrics Section
        metrics_section, metrics_layout = create_section("💰 Key Metrics")
        metrics_grid = QtWidgets.QGridLayout()
        metrics_grid.setContentsMargins(0, 4, 0, 0)
        metrics_grid.setHorizontalSpacing(12)
        metrics_grid.setVerticalSpacing(6)
        
        basis_label = QtWidgets.QLabel("Remaining Basis:")
        basis_label.setObjectName("MutedLabel")
        metrics_grid.addWidget(basis_label, 0, 0)
        metrics_grid.addWidget(make_selectable_label(self._format_currency(self.position.purchase_basis), align_right=True), 0, 1)
        
        # Unrealized P/L with color
        unrealized_pl = float(self.position.unrealized_pl or 0)
        pl_color = "green" if unrealized_pl >= 0 else "red"
        unrealized_label = QtWidgets.QLabel("Unrealized P/L:")
        unrealized_label.setObjectName("MutedLabel")
        metrics_grid.addWidget(unrealized_label, 1, 0)
        metrics_grid.addWidget(make_selectable_label(self._format_signed_currency(self.position.unrealized_pl), align_right=True, color=pl_color), 1, 1)
        
        metrics_grid.setColumnStretch(1, 1)
        metrics_layout.addLayout(metrics_grid)
        left_column.addWidget(metrics_section)
        left_column.addStretch(1)
        
        columns_layout.addLayout(left_column, 1)
        
        # ========== RIGHT COLUMN ==========
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)
        
        # Current Values Section
        values_section, values_layout = create_section("📈 Current Values")
        values_grid = QtWidgets.QGridLayout()
        values_grid.setContentsMargins(0, 4, 0, 0)
        values_grid.setHorizontalSpacing(12)
        values_grid.setVerticalSpacing(6)
        
        current_sc_label = QtWidgets.QLabel("Current SC:")
        current_sc_label.setObjectName("MutedLabel")
        values_grid.addWidget(current_sc_label, 0, 0)
        values_grid.addWidget(make_selectable_label(f"{float(self.position.current_sc):.2f}", align_right=True), 0, 1)
        
        current_value_label = QtWidgets.QLabel("Current Value:")
        current_value_label.setObjectName("MutedLabel")
        values_grid.addWidget(current_value_label, 1, 0)
        values_grid.addWidget(make_selectable_label(self._format_currency(self.position.current_value), align_right=True), 1, 1)
        
        values_grid.setColumnStretch(1, 1)
        values_layout.addLayout(values_grid)
        right_column.addWidget(values_section)
        right_column.addStretch(1)
        
        columns_layout.addLayout(right_column, 1)
        
        layout.addWidget(columns_widget)

        # ========== NOTES SECTION (Full Width Below) ==========
        notes_section, notes_layout = create_section("📝 Notes")
        notes_value = self.position.notes or ""
        
        if notes_value:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(notes_value)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setObjectName("MutedLabel")
            notes_font = notes_empty.font()
            notes_font.setItalic(True)
            notes_empty.setFont(notes_font)
            notes_layout.addWidget(notes_empty)
        
        layout.addWidget(notes_section)
        layout.addStretch(1)
        return widget

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        purchases_group = QtWidgets.QGroupBox("Open Purchases")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        purchases_table = self._build_purchases_table()
        purchases_layout.addWidget(purchases_table)
        layout.addWidget(purchases_group)

        sessions_group = QtWidgets.QGroupBox("Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)
        sessions_table = self._build_sessions_table()
        sessions_layout.addWidget(sessions_table)
        layout.addWidget(sessions_group, 1)

        return widget

    def _build_purchases_table(self):
        table = QtWidgets.QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Purchase Date", "Amount", "SC", "Remaining", "View"]
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(1, 110)
        table.setColumnWidth(2, 90)
        table.setColumnWidth(3, 110)
        table.setColumnWidth(4, 140)

        table.setRowCount(len(self.purchases))
        for row_idx, row in enumerate(self.purchases):
            date_display = self._format_date_time(row.get("purchase_date"), row.get("purchase_time"))
            amount = self._format_currency(row.get("amount", 0))
            sc_received = f"{float(row.get('sc_received') or 0.0):.2f}"
            remaining = self._format_currency(row.get("remaining_amount", 0))

            values = [date_display, amount, sc_received, remaining]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (1, 2, 3):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("👁️ View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(128)
            purchase_id = row.get("id")
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase_id: self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            table.setCellWidget(row_idx, 4, view_container)
            table.setRowHeight(
                row_idx,
                max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

        return table

    def _build_sessions_table(self):
        table = QtWidgets.QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ["Session Date", "Game", "Ending SC", "Status", "View"]
        )
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(44)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(2, 110)
        table.setColumnWidth(3, 90)
        table.setColumnWidth(4, 120)

        table.setRowCount(len(self.sessions))
        for row_idx, row in enumerate(self.sessions):
            date_display = self._format_date_time(row.get("session_date"), row.get("session_time"))
            game_name = row.get("game_name") or ""
            ending_sc = row.get("ending_redeemable") or row.get("ending_balance") or 0
            ending_sc_text = f"{float(ending_sc):.2f}"
            status = row.get("status") or ""

            values = [date_display, game_name, ending_sc_text, status]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx == 2:
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("👁️ View Session")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(114)
            session_id = row.get("id")
            view_btn.clicked.connect(
                lambda _checked=False, sid=session_id: self._open_session(sid)
            )
            view_container = QtWidgets.QWidget()
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            table.setCellWidget(row_idx, 4, view_container)
            table.setRowHeight(
                row_idx,
                max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

        return table

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase or not purchase_id:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_session(self, session_id):
        if not self.on_open_session or not session_id:
            QtWidgets.QMessageBox.information(
                self, "Sessions Unavailable", "Session view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_session(session_id))

    def _handle_close_position(self):
        if not self.on_close_position:
            return
        self.accept()
        QtCore.QTimer.singleShot(0, self.on_close_position)

    def _format_date(self, value):
        if not value:
            return "—"
        if isinstance(value, date):
            return value.strftime("%m/%d/%y")
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
        except Exception:
            return str(value)

    def _format_date_time(self, date_value, time_value):
        if not date_value:
            return "—"
        time_str = time_value or "00:00:00"
        if len(time_str) == 5:
            time_str = f"{time_str}:00"
        try:
            parsed = datetime.strptime(f"{date_value} {time_str}", "%Y-%m-%d %H:%M:%S")
            return parsed.strftime("%m/%d/%y %H:%M")
        except Exception:
            return str(date_value)

    def _format_currency(self, value):
        try:
            return f"${Decimal(str(value)):.2f}"
        except Exception:
            return f"${value}"

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"
