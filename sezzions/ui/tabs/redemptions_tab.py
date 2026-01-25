"""
Redemptions tab - Manage redemptions
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, datetime
from typing import Optional
from app_facade import AppFacade
from models.redemption import Redemption
from ui.date_filter_widget import DateFilterWidget
from ui.table_header_filters import TableHeaderFilter


class RedemptionsTab(QtWidgets.QWidget):
    """Tab for managing redemptions"""
    
    def __init__(self, facade: AppFacade, main_window=None):
        super().__init__()
        self.facade = facade
        self.main_window = main_window
        self.redemptions = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Redemptions")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search redemptions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_redemptions)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        
        layout.addLayout(header_layout)

        info = QtWidgets.QLabel("Log every cash-out here so FIFO and taxable results stay accurate.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filter
        self.date_filter = DateFilterWidget()
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("➕ Add Redemption")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_redemption)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View Redemption")
        self.view_btn.clicked.connect(self._view_redemption)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit Redemption")
        self.edit_btn.clicked.connect(self._edit_redemption)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete Redemption")
        self.delete_btn.clicked.connect(self._delete_redemption)
        self.delete_btn.setVisible(False)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()

        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date/Time", "User", "Site", "Amount", "Receipt", "Method", "Processed", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_redemption)
        layout.addWidget(self.table)

        self._header_initialized = False

        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.refresh_data)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload redemptions from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.redemptions = self.facade.get_all_redemptions(start_date=start_date, end_date=end_date)
        self._populate_table()
        self.table_filter.apply_filters()
    
    def _populate_table(self):
        """Populate table with redemptions"""
        filtered = self._get_filtered_redemptions()
        
        self.table.setRowCount(len(filtered))
        
        for row, redemption in enumerate(filtered):
            time_val = redemption.redemption_time or "00:00:00"
            if time_val and len(time_val) > 5:
                time_val = time_val[:5]
            date_time = f"{redemption.redemption_date} {time_val}".strip()

            is_total_loss = float(redemption.amount) == 0
            receipt_date = redemption.receipt_date.isoformat() if redemption.receipt_date else ""
            is_pending = receipt_date == ""
            if is_total_loss:
                receipt_display = str(redemption.redemption_date)
            elif is_pending:
                receipt_display = "PENDING"
            else:
                receipt_display = receipt_date

            method_display = "Loss" if is_total_loss else (getattr(redemption, 'method_name', None) or "")

            status = "total_loss" if is_total_loss else ("pending" if is_pending else "normal")

            # Date/Time
            date_item = QtWidgets.QTableWidgetItem(date_time)
            date_item.setData(QtCore.Qt.UserRole, redemption.id)
            self.table.setItem(row, 0, date_item)

            # User
            user = getattr(redemption, 'user_name', None) or "—"
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(user))

            # Site
            site = getattr(redemption, 'site_name', None) or "—"
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(site))

            # Amount
            amount_str = f"${float(redemption.amount):.2f}"
            amount_item = QtWidgets.QTableWidgetItem(amount_str)
            amount_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 3, amount_item)

            # Receipt
            receipt_item = QtWidgets.QTableWidgetItem(receipt_display)
            self.table.setItem(row, 4, receipt_item)

            # Method
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(method_display))

            # Processed
            processed_item = QtWidgets.QTableWidgetItem("✓" if redemption.processed else "")
            processed_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(row, 6, processed_item)

            # Notes
            notes = (redemption.notes or "")[:100]
            self.table.setItem(row, 7, QtWidgets.QTableWidgetItem(notes))

            if status == "total_loss":
                color = QtGui.QColor("#c0392b")
            elif status == "pending":
                color = QtGui.QColor("#e67e22")
            else:
                color = None

            if color:
                for col in range(0, 8):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QtGui.QBrush(color))
        
        self._apply_header_sizing()
        self.table_filter.apply_filters()

    def _get_filtered_redemptions(self):
        search_text = self.search_edit.text().lower()

        if search_text:
            filtered = []
            for r in self.redemptions:
                receipt_status = "pending" if not r.receipt_date else "received"
                processed_status = "processed" if r.processed else "unprocessed"
                parts = [
                    str(r.redemption_date),
                    getattr(r, 'user_name', '') or '',
                    getattr(r, 'site_name', '') or '',
                    getattr(r, 'method_name', '') or '',
                    str(r.amount),
                    receipt_status,
                    processed_status,
                    r.notes or '',
                ]
                haystack = " ".join(parts).lower()
                if search_text in haystack:
                    filtered.append(r)
        else:
            filtered = self.redemptions

        filtered.sort(key=lambda r: r.datetime_str, reverse=True)
        return filtered
    
    def _filter_redemptions(self):
        """Filter table based on search"""
        self._populate_table()

    def _apply_header_sizing(self):
        header = self.table.horizontalHeader()
        if header is None:
            return
        self.table.resizeColumnToContents(0)
        fm = header.fontMetrics()
        for col in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(col)
            if item is None:
                continue
            text = item.text()
            min_width = fm.horizontalAdvance(text) + 24
            if header.sectionSize(col) < min_width:
                header.resizeSection(col, min_width)
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        last = self.table.columnCount() - 1
        header.setSectionResizeMode(last, QtWidgets.QHeaderView.Stretch)
    
    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = bool(selected_rows)
        self.view_btn.setVisible(len(selected_rows) == 1)
        self.edit_btn.setVisible(len(selected_rows) == 1)
        self.delete_btn.setVisible(has_selection)
    
    def _get_selected_redemption_id(self):
        """Get ID of selected redemption"""
        ids = self._get_selected_redemption_ids()
        return ids[0] if ids else None

    def _get_selected_redemption_ids(self):
        ids = []
        for row in self.table.selectionModel().selectedRows():
            item = self.table.item(row.row(), 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids
    
    def _add_redemption(self):
        """Show dialog to add new redemption"""
        dialog = RedemptionDialog(self.facade, self)
        if dialog.exec():
            try:
                active_session = self.facade.get_active_game_session(dialog.user_id, dialog.site_id)
                if active_session:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Cannot Create Redemption",
                        "Cannot create a new redemption while a session is active."
                    )
                    return

                redemption_date = dialog.get_date()
                redemption_time = dialog.get_time() or "00:00:00"
                expected_total, expected_redeemable = self.facade.compute_expected_balances(
                    dialog.user_id,
                    dialog.site_id,
                    redemption_date,
                    redemption_time
                )
                site = self.facade.get_site(dialog.site_id)
                sc_rate = Decimal(str(site.sc_rate if site else 1.0))
                expected_balance = (expected_redeemable or Decimal("0.00")) * sc_rate
                amount = dialog.get_amount()
                unsessioned_amount = amount - expected_balance
                if unsessioned_amount > Decimal("0.50"):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Redemption Requires Session",
                        "This redemption exceeds the balance we can verify from recorded sessions.\n\n"
                        f"Redemption amount: ${float(amount):,.2f}\n"
                        f"Expected sessioned balance: {float(expected_balance):,.2f} SC\n"
                        f"Unsessioned amount: {float(unsessioned_amount):,.2f} SC\n\n"
                        "What this means:\n"
                        "• We only allow redemptions against balances that were recorded in Game Sessions.\n"
                        "• This helps keep your session-based totals accurate.\n\n"
                        "What to do:\n"
                        "1) Start or end a Game Session for this site to record the current balance.\n"
                        "2) Then try the redemption again.\n\n"
                        "If this was a bonus or freeplay not captured in sessions, record it in a Game Session first."
                    )
                    return

                if not self._confirm_partial_vs_balance(
                    amount,
                    expected_balance,
                    dialog.is_partial_selected(),
                ):
                    return

                redemption = self.facade.create_redemption(
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    amount=dialog.get_amount(),
                    fees=dialog.get_fees(),
                    redemption_date=redemption_date,
                    apply_fifo=True,  # Always apply FIFO like legacy app
                    redemption_method_id=dialog.method_id,
                    redemption_time=dialog.get_time(),
                    receipt_date=dialog.get_receipt_date(),
                    processed=dialog.processed_check.isChecked(),
                    more_remaining=dialog.is_partial_selected(),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()

                QtWidgets.QMessageBox.information(
                    self, "Success", f"Redemption of ${float(redemption.amount):.2f} created"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create redemption:\n{str(e)}"
                )

    def _view_redemption(self):
        """Show dialog to view selected redemption"""
        redemption_id = self._get_selected_redemption_id()
        if not redemption_id:
            return

        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            return

        def handle_edit():
            dialog.close()
            self._edit_redemption()

        def handle_delete():
            dialog.close()
            self._delete_redemption()

        dialog = RedemptionViewDialog(
            redemption,
            self.facade,
            parent=self,
            on_edit=handle_edit,
            on_delete=handle_delete
        )
        dialog.exec()

    def view_redemption_by_id(self, redemption_id: int):
        """Navigate to and open a specific redemption by ID."""
        if redemption_id is None:
            return

        # Ensure the redemption is visible in the table
        if hasattr(self, "date_filter") and self.date_filter is not None:
            self.date_filter.set_all_time()
        if hasattr(self, "search_edit") and self.search_edit is not None:
            self.search_edit.clear()

        # Refresh table data
        self.refresh_data()

        target_row = None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == redemption_id:
                target_row = row
                break

        if target_row is not None:
            self.table.selectRow(target_row)
            self.table.scrollToItem(self.table.item(target_row, 0))
            self._view_redemption()
            return

        # Fallback: open dialog even if the row isn't currently in view
        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            return

        dialog = RedemptionViewDialog(
            redemption,
            self.facade,
            parent=self,
        )
        dialog.exec()

    def _edit_redemption(self):
        """Show dialog to edit selected redemption"""
        redemption_id = self._get_selected_redemption_id()
        if not redemption_id:
            return

        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            return

        dialog = RedemptionDialog(self.facade, self, redemption)
        if dialog.exec():
            try:
                if redemption.has_fifo_allocation:
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "Reprocess Redemption?",
                        "This redemption has existing FIFO allocations.\n\n"
                        "Editing will reprocess this redemption and subsequent redemptions for the affected pairs.\n\n"
                        "Continue?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    )
                    if reply != QtWidgets.QMessageBox.Yes:
                        return

                redemption_date = dialog.get_date()
                redemption_time = dialog.get_time() or "00:00:00"
                expected_total, expected_redeemable = self.facade.compute_expected_balances(
                    dialog.user_id,
                    dialog.site_id,
                    redemption_date,
                    redemption_time,
                )
                site = self.facade.get_site(dialog.site_id)
                sc_rate = Decimal(str(site.sc_rate if site else 1.0))
                expected_balance = (expected_redeemable or Decimal("0.00")) * sc_rate
                amount = dialog.get_amount()

                if not self._confirm_partial_vs_balance(
                    amount,
                    expected_balance,
                    dialog.is_partial_selected(),
                ):
                    return

                self.facade.update_redemption_reprocess(
                    redemption_id,
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    amount=amount,
                    fees=dialog.get_fees(),
                    redemption_date=redemption_date,
                    redemption_method_id=dialog.method_id,
                    redemption_time=redemption_time,
                    receipt_date=dialog.get_receipt_date(),
                    processed=dialog.processed_check.isChecked(),
                    more_remaining=dialog.is_partial_selected(),
                    notes=dialog.notes_edit.toPlainText() or None,
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update redemption:\n{str(e)}"
                )

    def _confirm_partial_vs_balance(self, amount: Decimal, expected_balance: Decimal, is_partial: bool) -> bool:
        if expected_balance is None:
            return True

        diff = expected_balance - amount
        threshold = Decimal("0.50")

        if not is_partial and diff > threshold:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Balance Remaining",
                "This redemption is below the expected balance for this site/user.\n\n"
                f"Expected balance: {float(expected_balance):,.2f} SC\n"
                f"Redemption amount: ${float(amount):,.2f}\n\n"
                "It looks like a partial cashout (balance remains). Continue as Full?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            return reply == QtWidgets.QMessageBox.Yes

        if is_partial and diff <= threshold:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Likely Full Redemption",
                "This redemption is at or above the expected balance.\n\n"
                f"Expected balance: {float(expected_balance):,.2f} SC\n"
                f"Redemption amount: ${float(amount):,.2f}\n\n"
                "It looks like a full cashout. Continue as Partial?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            return reply == QtWidgets.QMessageBox.Yes

        return True
    
    def _delete_redemption(self):
        """Delete selected redemption"""
        redemption_ids = self._get_selected_redemption_ids()
        if not redemption_ids:
            return

        redemptions = []
        for redemption_id in redemption_ids:
            redemption = self.facade.get_redemption(redemption_id)
            if redemption:
                redemptions.append(redemption)

        if not redemptions:
            return

        if len(redemptions) == 1:
            redemption = redemptions[0]
            msg = (
                f"Delete redemption of ${float(redemption.amount):.2f} on {redemption.redemption_date}?\n\n"
                "This cannot be undone."
            )
        else:
            msg = (
                f"Delete {len(redemptions)} redemptions?\n\n"
                "This cannot be undone."
            )

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for redemption in redemptions:
                    self.facade.delete_redemption(redemption.id)
                self.refresh_data()
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete redemption(s):\n{str(e)}"
                )

    def _clear_search(self):
        """Clear search filter"""
        self.search_edit.clear()
        self.table.clearSelection()
        self._on_selection_changed()
        self._populate_table()

    def _clear_all_filters(self):
        """Clear search and reset date filter"""
        self.search_edit.clear()
        self.date_filter.set_all_time()
        self.table.clearSelection()
        self._on_selection_changed()
        self.refresh_data()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()

    def _export_csv(self):
        """Export redemptions to CSV"""
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Redemptions",
            f"redemptions_{date.today().isoformat()}.csv",
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
                    f"Exported redemptions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )


class RedemptionDialog(QtWidgets.QDialog):
    """Modern redemption dialog with streamlined sectioned layout"""

    def __init__(self, facade: AppFacade, parent=None, redemption: Redemption = None):
        super().__init__(parent)
        self.facade = facade
        self.redemption = redemption
        self.user_id = redemption.user_id if redemption else None
        self.site_id = redemption.site_id if redemption else None
        self.method_id = redemption.redemption_method_id if redemption else None

        self.setWindowTitle("Edit Redemption" if redemption else "Add Redemption")
        self.setMinimumWidth(850)
        self.setMinimumHeight(520)
        self.resize(850, 520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Initialize widgets
        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.today_btn = QtWidgets.QPushButton("Today")
        self.calendar_btn = QtWidgets.QPushButton("📅")
        self.calendar_btn.setFixedWidth(44)
        self.today_btn.clicked.connect(self._set_today)
        self.calendar_btn.clicked.connect(lambda: self._pick_date(self.date_edit))

        self.time_edit = QtWidgets.QLineEdit()
        self.time_edit.setPlaceholderText("HH:MM")
        self.now_btn = QtWidgets.QPushButton("Now")
        self.now_btn.clicked.connect(self._set_now)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setEditable(True)
        self.user_combo.lineEdit().setPlaceholderText("Choose...")
        users = facade.get_all_users(active_only=True)
        self._user_lookup = {u.name.lower(): u.id for u in users}
        self.user_combo.addItems([u.name for u in users])

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        self.site_combo.lineEdit().setPlaceholderText("Choose...")
        sites = facade.get_all_sites(active_only=True)
        self._site_lookup = {s.name.lower(): s.id for s in sites}
        self.site_combo.addItems([s.name for s in sites])

        self.method_type_combo = QtWidgets.QComboBox()
        self.method_type_combo.setEditable(True)
        self.method_type_combo.lineEdit().setPlaceholderText("Select user first...")

        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.lineEdit().setPlaceholderText("Select method type first...")

        self._methods = facade.get_all_redemption_methods(active_only=True)
        self._method_lookup = {m.name.lower(): m.id for m in self._methods}
        self._method_by_id = {m.id: m.name for m in self._methods}
        self._method_type_lookup = {m.id: m.method_type for m in self._methods}

        self.amount_edit = QtWidgets.QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        
        self.fees_edit = QtWidgets.QLineEdit()
        self.fees_edit.setPlaceholderText("0.00")

        self.receipt_edit = QtWidgets.QLineEdit()
        self.receipt_edit.setPlaceholderText("MM/DD/YY")
        self.receipt_btn = QtWidgets.QPushButton("📅")
        self.receipt_btn.setFixedWidth(44)
        self.receipt_btn.clicked.connect(lambda: self._pick_date(self.receipt_edit))

        # Radio buttons for redemption type
        self.partial_radio = QtWidgets.QRadioButton("Partial")
        self.full_radio = QtWidgets.QRadioButton("Full")
        self.redemption_type_group = QtWidgets.QButtonGroup(self)
        self.redemption_type_group.addButton(self.partial_radio)
        self.redemption_type_group.addButton(self.full_radio)
        
        # Help button for redemption type
        self.redemption_help_btn = QtWidgets.QPushButton("?")
        self.redemption_help_btn.setFixedSize(22, 22)
        self.redemption_help_btn.setToolTip("Click for explanation of Partial vs Full")
        self.redemption_help_btn.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.redemption_help_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.redemption_help_btn.setStyleSheet("""
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
        self.redemption_help_btn.clicked.connect(self._show_redemption_type_help)

        self.processed_check = QtWidgets.QCheckBox()

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Form layout
        form = QtWidgets.QVBoxLayout()
        form.setSpacing(12)

        # Date/Time row (no header, compact)
        datetime_section = QtWidgets.QWidget()
        datetime_section.setObjectName("SectionBackground")
        datetime_layout = QtWidgets.QHBoxLayout(datetime_section)
        datetime_layout.setContentsMargins(12, 10, 12, 10)
        datetime_layout.setSpacing(12)
        
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(date_label)
        
        # Date field with embedded calendar button
        date_container = QtWidgets.QWidget()
        date_layout = QtWidgets.QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(4)
        self.date_edit.setFixedWidth(110)
        date_layout.addWidget(self.date_edit)
        date_layout.addWidget(self.calendar_btn)
        datetime_layout.addWidget(date_container)
        
        datetime_layout.addWidget(self.today_btn)
        datetime_layout.addSpacing(30)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        datetime_layout.addWidget(time_label)
        
        self.time_edit.setFixedWidth(90)
        datetime_layout.addWidget(self.time_edit)
        datetime_layout.addWidget(self.now_btn)
        datetime_layout.addStretch(1)
        
        form.addWidget(datetime_section)

        # Main Redemption Details card with 2-column grid
        main_header = self._create_section_header("💰  Redemption Details")
        form.addWidget(main_header)
        
        main_section = QtWidgets.QWidget()
        main_section.setObjectName("SectionBackground")
        main_grid = QtWidgets.QGridLayout(main_section)
        main_grid.setContentsMargins(12, 12, 12, 12)
        main_grid.setHorizontalSpacing(30)
        main_grid.setVerticalSpacing(10)
        
        # Left Column
        row = 0
        
        # User
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        user_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(user_label, row, 0)
        self.user_combo.setMinimumWidth(200)
        main_grid.addWidget(self.user_combo, row, 1)
        
        # Amount (right column)
        amount_label = QtWidgets.QLabel("Amount ($):")
        amount_label.setObjectName("FieldLabel")
        amount_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(amount_label, row, 2)
        self.amount_edit.setFixedWidth(140)
        main_grid.addWidget(self.amount_edit, row, 3)
        
        row += 1
        
        # Site
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        site_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(site_label, row, 0)
        self.site_combo.setMinimumWidth(200)
        main_grid.addWidget(self.site_combo, row, 1)
        
        # Fees (right column)
        fees_label = QtWidgets.QLabel("Fees ($):")
        fees_label.setObjectName("FieldLabel")
        fees_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(fees_label, row, 2)
        self.fees_edit.setFixedWidth(140)
        main_grid.addWidget(self.fees_edit, row, 3)
        
        row += 1
        
        # Method Type
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setObjectName("FieldLabel")
        method_type_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(method_type_label, row, 0)
        self.method_type_combo.setMinimumWidth(200)
        main_grid.addWidget(self.method_type_combo, row, 1)
        
        # Redemption Type (right column) - radio buttons with help
        redemption_type_label = QtWidgets.QLabel("Redemption Type:")
        redemption_type_label.setObjectName("FieldLabel")
        redemption_type_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(redemption_type_label, row, 2)
        
        redemption_type_container = QtWidgets.QWidget()
        redemption_type_layout = QtWidgets.QHBoxLayout(redemption_type_container)
        redemption_type_layout.setContentsMargins(0, 0, 0, 0)
        redemption_type_layout.setSpacing(8)
        redemption_type_layout.setAlignment(QtCore.Qt.AlignVCenter)
        redemption_type_layout.addWidget(self.partial_radio)
        redemption_type_layout.addWidget(self.full_radio)
        redemption_type_layout.addWidget(self.redemption_help_btn, 0, QtCore.Qt.AlignVCenter)
        redemption_type_layout.addStretch(1)
        main_grid.addWidget(redemption_type_container, row, 3)
        
        row += 1
        
        # Method
        method_label = QtWidgets.QLabel("Method:")
        method_label.setObjectName("FieldLabel")
        method_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(method_label, row, 0)
        self.method_combo.setMinimumWidth(200)
        main_grid.addWidget(self.method_combo, row, 1)
        
        # Receipt Date (right column)
        receipt_label = QtWidgets.QLabel("Receipt Date:")
        receipt_label.setObjectName("FieldLabel")
        receipt_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(receipt_label, row, 2)
        
        receipt_container = QtWidgets.QWidget()
        receipt_layout = QtWidgets.QHBoxLayout(receipt_container)
        receipt_layout.setContentsMargins(0, 0, 0, 0)
        receipt_layout.setSpacing(4)
        self.receipt_edit.setFixedWidth(110)
        receipt_layout.addWidget(self.receipt_edit)
        receipt_layout.addWidget(self.receipt_btn)
        receipt_layout.addStretch(1)
        main_grid.addWidget(receipt_container, row, 3)
        
        row += 1
        
        # Processed checkbox with label (right column only)
        processed_label = QtWidgets.QLabel("Processed:")
        processed_label.setObjectName("FieldLabel")
        processed_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(processed_label, row, 2)
        main_grid.addWidget(self.processed_check, row, 3)
        
        main_grid.setColumnStretch(1, 1)
        main_grid.setColumnStretch(3, 1)
        
        form.addWidget(main_section)

        # Collapsible Notes
        self.notes_collapsed = True
        self.notes_toggle = QtWidgets.QPushButton("📝 Add Notes...")
        self.notes_toggle.setObjectName("SectionHeader")
        self.notes_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.notes_toggle.setFlat(True)
        self.notes_toggle.clicked.connect(self._toggle_notes)
        form.addWidget(self.notes_toggle)
        
        self.notes_section = QtWidgets.QWidget()
        self.notes_section.setObjectName("SectionBackground")
        self.notes_section.setVisible(False)
        notes_layout = QtWidgets.QVBoxLayout(self.notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.addWidget(self.notes_edit)
        form.addWidget(self.notes_section)

        layout.addLayout(form)
        
        # Add stretch to push buttons to bottom when dialog is resized
        layout.addStretch(1)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        self.clear_btn = QtWidgets.QPushButton("🧹 Clear")
        self.save_btn = QtWidgets.QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._validate_and_accept)

        self.user_combo.currentTextChanged.connect(self._on_user_changed)
        self.site_combo.currentTextChanged.connect(self._on_site_changed)
        self.method_type_combo.currentTextChanged.connect(self._on_method_type_changed)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.method_type_combo.currentTextChanged.connect(self._validate_inline)
        self.method_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.fees_edit.textChanged.connect(self._validate_inline)
        self.receipt_edit.textChanged.connect(self._validate_inline)
        self.partial_radio.toggled.connect(self._validate_inline)
        self.full_radio.toggled.connect(self._validate_inline)

        # Set tab order: User -> Site -> Method Type -> Method -> Amount -> Fees -> Redemption Type -> Receipt Date -> Processed -> Save
        self.setTabOrder(self.user_combo, self.site_combo)
        self.setTabOrder(self.site_combo, self.method_type_combo)
        self.setTabOrder(self.method_type_combo, self.method_combo)
        self.setTabOrder(self.method_combo, self.amount_edit)
        self.setTabOrder(self.amount_edit, self.fees_edit)
        self.setTabOrder(self.fees_edit, self.partial_radio)
        self.setTabOrder(self.partial_radio, self.full_radio)
        self.setTabOrder(self.full_radio, self.receipt_edit)
        self.setTabOrder(self.receipt_edit, self.processed_check)
        self.setTabOrder(self.processed_check, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)
        self.setTabOrder(self.cancel_btn, self.clear_btn)

        self._update_method_types_for_user(preserve=False)

        if redemption:
            self._load_redemption()
        else:
            self._clear_form()

        self._validate_inline()
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(520)
            self.setMaximumHeight(520)
            self.resize(self.width(), 520)
        else:
            self.notes_toggle.setText("📝 Notes ▼")
            self.setMinimumHeight(650)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), 650)
    
    def _show_redemption_type_help(self):
        """Show help dialog explaining redemption types"""
        QtWidgets.QMessageBox.information(
            self,
            "Redemption Type Help",
            "<b>Partial:</b> Balance remains after this redemption. More purchases can be redeemed later.<br><br>"
            "<b>Full:</b> This redemption closes out the remaining basis. No more redemptions will be allocated from these purchases."
        )
    
    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        
        when_section = QtWidgets.QWidget()
        when_section.setObjectName("SectionBackground")
        when_layout = QtWidgets.QGridLayout(when_section)
        when_layout.setContentsMargins(12, 12, 12, 12)
        when_layout.setHorizontalSpacing(12)
        when_layout.setVerticalSpacing(8)
        
        # Row 0: Date label | Time label
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        when_layout.addWidget(date_label, 0, 0, 1, 4)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        when_layout.addWidget(time_label, 0, 4, 1, 3)
        
        # Row 1: Date + buttons | Time + button
        when_layout.addWidget(self.date_edit, 1, 0, 1, 2)
        when_layout.addWidget(self.calendar_btn, 1, 2)
        when_layout.addWidget(self.today_btn, 1, 3)
        when_layout.addWidget(self.time_edit, 1, 4, 1, 2)
        when_layout.addWidget(self.now_btn, 1, 6)
        
        when_layout.setColumnStretch(0, 1)
        when_layout.setColumnStretch(1, 1)
        when_layout.setColumnStretch(4, 1)
        when_layout.setColumnStretch(5, 1)
        
        form.addWidget(when_section, 1, 0, 1, 7)

        # Section 2: Transaction Details
        section2_header = self._create_section_header("🏪  Transaction")
        form.addWidget(section2_header, 2, 0, 1, 7)
        
        trans_section = QtWidgets.QWidget()
        trans_section.setObjectName("SectionBackground")
        trans_layout = QtWidgets.QGridLayout(trans_section)
        trans_layout.setContentsMargins(12, 12, 12, 12)
        trans_layout.setHorizontalSpacing(12)
        trans_layout.setVerticalSpacing(8)
        
        # Row 0: User label | Site label (50/50 in 6-column grid)
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("FieldLabel")
        trans_layout.addWidget(user_label, 0, 0, 1, 3)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("FieldLabel")
        trans_layout.addWidget(site_label, 0, 3, 1, 3)
        
        # Row 1: User | Site (50/50)
        trans_layout.addWidget(self.user_combo, 1, 0, 1, 3)
        trans_layout.addWidget(self.site_combo, 1, 3, 1, 3)
        
        # Add vertical spacer
        spacer1 = QtWidgets.QSpacerItem(1, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        trans_layout.addItem(spacer1, 2, 0)

        # Row 3: Method Type label | Method label (50/50)
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setObjectName("FieldLabel")
        trans_layout.addWidget(method_type_label, 3, 0, 1, 3)
        
        method_label = QtWidgets.QLabel("Method:")
        method_label.setObjectName("FieldLabel")
        trans_layout.addWidget(method_label, 3, 3, 1, 3)
        
        # Row 4: Method Type | Method (50/50)
        trans_layout.addWidget(self.method_type_combo, 4, 0, 1, 3)
        trans_layout.addWidget(self.method_combo, 4, 3, 1, 3)
        
        trans_layout.setColumnStretch(0, 1)
        trans_layout.setColumnStretch(1, 1)
        trans_layout.setColumnStretch(2, 1)
        trans_layout.setColumnStretch(3, 1)
        trans_layout.setColumnStretch(4, 1)
        trans_layout.setColumnStretch(5, 1)
        
        form.addWidget(trans_section, 3, 0, 1, 7)

        # Section 3: Amount Details
        section3_header = self._create_section_header("💰  Amount Details")
        form.addWidget(section3_header, 4, 0, 1, 7)
        
        amount_section = QtWidgets.QWidget()
        amount_section.setObjectName("SectionBackground")
        amount_layout = QtWidgets.QVBoxLayout(amount_section)
        amount_layout.setContentsMargins(12, 12, 12, 12)
        amount_layout.setSpacing(8)
        
        # Row 0: Labels for Amount | Fees | Redemption Type
        labels_row = QtWidgets.QHBoxLayout()
        labels_row.setSpacing(12)
        
        amount_label = QtWidgets.QLabel("Amount ($):")
        amount_label.setObjectName("FieldLabel")
        labels_row.addWidget(amount_label, 1)
        
        fees_label = QtWidgets.QLabel("Fees ($):")
        fees_label.setObjectName("FieldLabel")
        labels_row.addWidget(fees_label, 1)
        
        type_label = QtWidgets.QLabel("Redemption Type:")
        type_label.setObjectName("FieldLabel")
        labels_row.addWidget(type_label, 2)
        
        amount_layout.addLayout(labels_row)
        
        # Row 1: Amount field | Fees field | Radio buttons
        fields_row = QtWidgets.QHBoxLayout()
        fields_row.setSpacing(12)
        
        fields_row.addWidget(self.amount_edit, 1)
        fields_row.addWidget(self.fees_edit, 1)
        
        type_group = QtWidgets.QHBoxLayout()
        type_group.setSpacing(12)
        type_group.addWidget(self.partial_radio)
        type_group.addWidget(self.final_radio)
        fields_row.addLayout(type_group, 2)
        
        amount_layout.addLayout(fields_row)
        
        # Add vertical spacer
        amount_layout.addSpacing(15)

        # Row 2: Receipt Date label | Processed checkbox label
        receipt_labels_row = QtWidgets.QHBoxLayout()
        receipt_labels_row.setSpacing(12)
        
        receipt_label = QtWidgets.QLabel("Receipt Date:")
        receipt_label.setObjectName("FieldLabel")
        receipt_labels_row.addWidget(receipt_label, 1)
        
        processed_label = QtWidgets.QLabel("Processed:")
        processed_label.setObjectName("FieldLabel")
        receipt_labels_row.addWidget(processed_label, 1)
        
        amount_layout.addLayout(receipt_labels_row)
        
        # Row 3: Receipt Date field + button | Processed checkbox
        receipt_fields_row = QtWidgets.QHBoxLayout()
        receipt_fields_row.setSpacing(12)
        
        receipt_input_row = QtWidgets.QHBoxLayout()
        receipt_input_row.setSpacing(4)
        receipt_input_row.addWidget(self.receipt_edit)
        receipt_input_row.addWidget(self.receipt_btn)
        receipt_fields_row.addLayout(receipt_input_row, 1)
        
        receipt_fields_row.addWidget(self.processed_check, 1)
        
        amount_layout.addLayout(receipt_fields_row)
        
        form.addWidget(amount_section, 5, 0, 1, 7)

        # Section 4: Notes
        section4_header = self._create_section_header("📝  Notes")
        form.addWidget(section4_header, 6, 0, 1, 7)
        
        notes_section = QtWidgets.QWidget()
        notes_section.setObjectName("SectionBackground")
        notes_layout = QtWidgets.QVBoxLayout(notes_section)
        notes_layout.setContentsMargins(12, 12, 12, 12)
        notes_layout.setSpacing(5)
        
        notes_layout.addWidget(self.notes_edit)
        
        form.addWidget(notes_section, 7, 0, 1, 7)

        form.setColumnStretch(0, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(4, 1)
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        layout.addStretch(1)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        self.clear_btn = QtWidgets.QPushButton("🧹 Clear")
        self.save_btn = QtWidgets.QPushButton("💾 Save")
        self.save_btn.setObjectName("PrimaryButton")
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.clear_btn.clicked.connect(self._clear_form)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._validate_and_accept)

        self.user_combo.currentTextChanged.connect(self._on_user_changed)
        self.site_combo.currentTextChanged.connect(self._on_site_changed)
        self.method_type_combo.currentTextChanged.connect(self._on_method_type_changed)
        self.method_combo.currentTextChanged.connect(self._on_method_changed)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.method_type_combo.currentTextChanged.connect(self._validate_inline)
        self.method_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.fees_edit.textChanged.connect(self._validate_inline)
        self.receipt_edit.textChanged.connect(self._validate_inline)
        self.partial_radio.toggled.connect(self._validate_inline)
        self.final_radio.toggled.connect(self._validate_inline)

        self._update_method_types_for_user(preserve=False)

        if redemption:
            self._load_redemption()
        else:
            self._clear_form()

        self._validate_inline()
    
    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label

    def _set_invalid(self, widget, message: str):
        widget.setProperty("invalid", True)
        widget.setToolTip(message)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_valid(self, widget):
        widget.setProperty("invalid", False)
        widget.setToolTip("")
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _validate_inline(self) -> bool:
        valid = True

        date_text = self.date_edit.text().strip()
        if not date_text:
            self._set_invalid(self.date_edit, "Date is required.")
            valid = False
            redemption_date = None
        else:
            try:
                redemption_date = self.get_date()
                if redemption_date > date.today():
                    self._set_invalid(self.date_edit, "Date cannot be in the future.")
                    valid = False
                else:
                    self._set_valid(self.date_edit)
            except Exception:
                redemption_date = None
                self._set_invalid(self.date_edit, "Enter a valid date.")
                valid = False

        time_text = self.time_edit.text().strip()
        if time_text:
            try:
                if len(time_text) == 5:
                    datetime.strptime(time_text, "%H:%M")
                elif len(time_text) == 8:
                    datetime.strptime(time_text, "%H:%M:%S")
                else:
                    raise ValueError("Invalid format")
                self._set_valid(self.time_edit)
            except Exception:
                self._set_invalid(self.time_edit, "Use 24-hour time HH:MM or HH:MM:SS.")
                valid = False
        else:
            self._set_valid(self.time_edit)

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            self._set_invalid(self.user_combo, "Select a valid User.")
            valid = False
        else:
            self._set_valid(self.user_combo)

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            self._set_invalid(self.site_combo, "Select a valid Site.")
            valid = False
        else:
            self._set_valid(self.site_combo)

        method_type_text = self.method_type_combo.currentText().strip()
        valid_method_types = {
            self.method_type_combo.itemText(i).lower()
            for i in range(self.method_type_combo.count())
            if self.method_type_combo.itemText(i)
        }
        if not method_type_text:
            self._set_invalid(self.method_type_combo, "Method Type is required.")
            valid = False
        elif method_type_text.lower() not in valid_method_types:
            self._set_invalid(self.method_type_combo, "Select a valid Method Type from the list.")
            valid = False
        else:
            self._set_valid(self.method_type_combo)

        amount_text = self.amount_edit.text().strip()
        amount_value = None
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
            valid = False
        else:
            try:
                amount_value = Decimal(amount_text)
                if amount_value < 0:
                    raise ValueError("negative")
                self._set_valid(self.amount_edit)
            except Exception:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
                valid = False

        fees_text = self.fees_edit.text().strip()
        if fees_text:
            try:
                fees_value = Decimal(fees_text)
                if fees_value < 0:
                    raise ValueError("negative")
                if amount_value is not None and fees_value > amount_value:
                    self._set_invalid(self.fees_edit, "Fees cannot exceed the redemption amount.")
                    valid = False
                else:
                    self._set_valid(self.fees_edit)
            except Exception:
                self._set_invalid(self.fees_edit, "Enter a valid fee amount (max 2 decimals).")
                valid = False
        else:
            self._set_valid(self.fees_edit)

        receipt_text = self.receipt_edit.text().strip()
        if receipt_text:
            try:
                receipt_date = self._parse_date(receipt_text)
                if redemption_date and receipt_date < redemption_date:
                    self._set_invalid(self.receipt_edit, "Receipt date cannot be before redemption date.")
                    valid = False
                else:
                    self._set_valid(self.receipt_edit)
            except Exception:
                self._set_invalid(self.receipt_edit, "Enter a valid receipt date.")
                valid = False
        else:
            self._set_valid(self.receipt_edit)

        method_text = self.method_combo.currentText().strip()
        valid_methods = {self.method_combo.itemText(i).lower() for i in range(self.method_combo.count())}
        if not method_text:
            self._set_invalid(self.method_combo, "Method is required.")
            valid = False
        elif method_text.lower() not in valid_methods:
            self._set_invalid(self.method_combo, "Select a valid Method.")
            valid = False
        else:
            self._set_valid(self.method_combo)

        if not self.partial_radio.isChecked() and not self.full_radio.isChecked():
            self._set_invalid(self.partial_radio, "Select Partial or Full.")
            self._set_invalid(self.full_radio, "Select Partial or Full.")
            valid = False
        else:
            self._set_valid(self.partial_radio)
            self._set_valid(self.full_radio)

        return valid

    def _on_user_changed(self, _value: str = ""):
        user_text = self.user_combo.currentText().strip()
        self.user_id = self._user_lookup.get(user_text.lower()) if user_text else None
        self._update_method_types_for_user(preserve=True)

    def _on_site_changed(self, _value: str = ""):
        site_text = self.site_combo.currentText().strip()
        self.site_id = self._site_lookup.get(site_text.lower()) if site_text else None

    def _on_method_type_changed(self, _value: str = ""):
        self._update_methods_for_type(preserve=True)

    def _on_method_changed(self, _value: str = ""):
        method_text = self.method_combo.currentText().strip()
        self.method_id = self._method_lookup.get(method_text.lower()) if method_text else None

    def _get_methods_for_user(self) -> list:
        if self.user_id is None:
            return []
        return [m for m in self._methods if m.user_id is None or m.user_id == self.user_id]

    def _update_method_types_for_user(self, preserve: bool = False):
        current = self.method_type_combo.currentText().strip()
        method_types = sorted({(m.method_type or "").strip() for m in self._get_methods_for_user() if m.method_type})

        self.method_type_combo.blockSignals(True)
        self.method_type_combo.clear()
        self.method_type_combo.addItems(method_types)
        if self.user_id is None:
            self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")
        else:
            self.method_type_combo.lineEdit().setPlaceholderText("")

        if preserve and current and current in method_types:
            self.method_type_combo.setCurrentText(current)
        else:
            self.method_type_combo.setCurrentIndex(-1)
            self.method_type_combo.setEditText("")
        self.method_type_combo.blockSignals(False)

        self._update_methods_for_type(preserve=preserve)

    def _update_methods_for_type(self, preserve: bool = False):
        current = self.method_combo.currentText().strip()
        method_type = self.method_type_combo.currentText().strip()
        if not method_type:
            methods = []
        else:
            methods = [m for m in self._get_methods_for_user() if (m.method_type or "") == method_type]
        method_names = [m.name for m in methods]

        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        self.method_combo.addItems(method_names)
        if not method_type:
            self.method_combo.lineEdit().setPlaceholderText("Select a method type first")
        else:
            self.method_combo.lineEdit().setPlaceholderText("")
        if preserve and current and current in method_names:
            self.method_combo.setCurrentText(current)
        else:
            self.method_combo.setCurrentIndex(-1)
            self.method_combo.setEditText("")
        self.method_combo.blockSignals(False)
        self._validate_inline()

    def _pick_date(self, target: QtWidgets.QLineEdit):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        cancel_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            target.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))

    def _parse_date(self, date_str: str) -> date:
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError("Invalid date")

    def get_date(self) -> date:
        date_str = self.date_edit.text().strip()
        return self._parse_date(date_str) if date_str else date.today()

    def get_time(self) -> Optional[str]:
        time_str = self.time_edit.text().strip()
        if not time_str:
            return datetime.now().strftime("%H:%M:%S")
        if len(time_str) == 5:
            return f"{time_str}:00"
        return time_str

    def get_receipt_date(self) -> Optional[date]:
        receipt_str = self.receipt_edit.text().strip()
        if not receipt_str:
            return None
        return self._parse_date(receipt_str)

    def get_amount(self) -> Decimal:
        return Decimal(self.amount_edit.text().strip())

    def get_fees(self) -> Decimal:
        text = self.fees_edit.text().strip()
        return Decimal(text) if text else Decimal("0.00")

    def is_partial_selected(self) -> bool:
        return self.partial_radio.isChecked()

    def _validate_and_accept(self):
        if not self._methods:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Redemption Methods",
                "No redemption methods are set up. Please add one in Setup → Redemption Methods."
            )
            return
        if not self._validate_inline():
            return

        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "User is required")
            return
        self.user_id = self._user_lookup[user_text.lower()]

        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Site is required")
            return
        self.site_id = self._site_lookup[site_text.lower()]

        method_type_text = self.method_type_combo.currentText().strip()
        valid_method_types = {
            self.method_type_combo.itemText(i).lower()
            for i in range(self.method_type_combo.count())
            if self.method_type_combo.itemText(i)
        }
        if not method_type_text or method_type_text.lower() not in valid_method_types:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Method Type is required")
            return

        method_text = self.method_combo.currentText().strip()
        if not method_text:
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Method is required")
            return
        if method_text:
            method_key = method_text.lower()
            if method_key not in self._method_lookup:
                QtWidgets.QMessageBox.warning(self, "Validation Error", "Select a valid Method")
                return
            self.method_id = self._method_lookup[method_key]
        else:
            self.method_id = None

        self.accept()

    def _clear_form(self):
        self.user_id = None
        self.site_id = None
        self.method_id = None
        self.date_edit.clear()
        self.time_edit.clear()
        self.user_combo.setCurrentIndex(-1)
        self.user_combo.setEditText("")
        self.site_combo.setCurrentIndex(-1)
        self.site_combo.setEditText("")
        self.method_type_combo.setCurrentIndex(-1)
        self.method_type_combo.setEditText("")
        self.method_combo.setCurrentIndex(-1)
        self.method_combo.setEditText("")
        self.amount_edit.clear()
        self.fees_edit.clear()
        self.receipt_edit.clear()
        self.partial_radio.setAutoExclusive(False)
        self.full_radio.setAutoExclusive(False)
        self.partial_radio.setChecked(False)
        self.full_radio.setChecked(False)
        self.partial_radio.setAutoExclusive(True)
        self.full_radio.setAutoExclusive(True)
        self.processed_check.setChecked(False)
        self.notes_edit.clear()
        self._set_today()
        self._update_method_types_for_user(preserve=False)
        self._validate_inline()

    def _load_redemption(self):
        self.date_edit.setText(self.redemption.redemption_date.strftime("%m/%d/%y"))
        if self.redemption.redemption_time:
            time_str = self.redemption.redemption_time
            if len(time_str) > 5:
                time_str = time_str[:5]
            self.time_edit.setText(time_str)

        user_name = getattr(self.redemption, "user_name", None)
        if not user_name:
            user = self.facade.get_user(self.redemption.user_id)
            user_name = user.name if user else ""
        if user_name:
            self.user_combo.setCurrentText(user_name)
            self._on_user_changed(user_name)

        site_name = getattr(self.redemption, "site_name", None)
        if not site_name:
            site = self.facade.get_site(self.redemption.site_id)
            site_name = site.name if site else ""
        if site_name:
            self.site_combo.setCurrentText(site_name)

        method_type_value = getattr(self.redemption, "method_type", None)
        if not method_type_value and self.redemption.redemption_method_id in self._method_type_lookup:
            method_type_value = self._method_type_lookup[self.redemption.redemption_method_id]
        if method_type_value:
            self.method_type_combo.setCurrentText(method_type_value)
            self._update_methods_for_type(preserve=False)

        method_name = getattr(self.redemption, "method_name", None)
        if not method_name and self.redemption.redemption_method_id in self._method_by_id:
            method_name = self._method_by_id[self.redemption.redemption_method_id]
        if method_name:
            self.method_combo.setCurrentText(method_name)

        self.amount_edit.setText(f"{self.redemption.amount:.2f}")
        self.fees_edit.setText(f"{self.redemption.fees:.2f}")
        if self.redemption.receipt_date:
            self.receipt_edit.setText(self.redemption.receipt_date.strftime("%m/%d/%y"))
        self.processed_check.setChecked(bool(self.redemption.processed))
        if self.redemption.more_remaining:
            self.partial_radio.setChecked(True)
        else:
            self.full_radio.setChecked(True)
        if self.redemption.notes:
            self.notes_edit.setPlainText(self.redemption.notes)


class RedemptionViewDialog(QtWidgets.QDialog):
    """Modern redemption view dialog with streamlined sectioned layout"""

    def __init__(self, redemption: Redemption, facade: AppFacade, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.redemption = redemption
        self.facade = facade
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.setWindowTitle("View Redemption")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)

        user_name = getattr(self.redemption, 'user_name', None)
        if not user_name:
            user = self.facade.get_user(self.redemption.user_id)
            user_name = user.name if user else "—"

        site_name = getattr(self.redemption, 'site_name', None)
        if not site_name:
            site = self.facade.get_site(self.redemption.site_id)
            site_name = site.name if site else "—"

        method_name = getattr(self.redemption, 'method_name', None)
        if not method_name and self.redemption.redemption_method_id:
            methods = self.facade.get_all_redemption_methods(active_only=False)
            method_name = next((m.name for m in methods if m.id == self.redemption.redemption_method_id), "—")

        method_type = getattr(self.redemption, 'method_type', None)
        if not method_type and self.redemption.redemption_method_id:
            methods = self.facade.get_all_redemption_methods(active_only=False)
            method_type = next((m.method_type for m in methods if m.id == self.redemption.redemption_method_id), None)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        self._games = {g.id: g for g in self.facade.list_all_games()}

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(user_name, site_name, method_name, method_type), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("🗑️ Delete")
            delete_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(delete_btn)

        btn_row.addStretch(1)

        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("✏️ Edit")
            edit_btn.clicked.connect(self._on_edit)
            btn_row.addWidget(edit_btn)

        view_realized_btn = None
        if getattr(self.redemption, "id", None):
            view_realized_btn = QtWidgets.QPushButton("👁️ View Realized Position")
            view_realized_btn.clicked.connect(self._open_realized_position)
            btn_row.addWidget(view_realized_btn)

        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _create_details_tab(self, user_name: str, site_name: str, method_name: str, method_type: Optional[str]) -> QtWidgets.QWidget:
        """Create modern sectioned details tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # Format helpers
        def format_date(value):
            if not value:
                return "—"
            if isinstance(value, date):
                return value.strftime("%m/%d/%y")
            try:
                return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
            except ValueError:
                return str(value)

        def format_time(value):
            return value[:5] if value else "—"
        
        def make_selectable_label(text, bold=False, align_right=False):
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

        # ========== TWO-COLUMN LAYOUT ==========
        columns_widget = QtWidgets.QWidget()
        columns_layout = QtWidgets.QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(12)
        
        # ========== LEFT COLUMN ==========
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)
        
        # When Section
        when_section, when_layout = create_section("📅 When")
        when_grid = QtWidgets.QGridLayout()
        when_grid.setContentsMargins(0, 4, 0, 0)
        when_grid.setHorizontalSpacing(12)
        when_grid.setVerticalSpacing(6)
        
        date_label = QtWidgets.QLabel("Date:")
        date_label.setStyleSheet("color: palette(mid);")
        when_grid.addWidget(date_label, 0, 0)
        when_grid.addWidget(make_selectable_label(format_date(self.redemption.redemption_date)), 0, 1)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setStyleSheet("color: palette(mid);")
        when_grid.addWidget(time_label, 1, 0)
        when_grid.addWidget(make_selectable_label(format_time(self.redemption.redemption_time)), 1, 1)
        
        when_grid.setColumnStretch(1, 1)
        when_layout.addLayout(when_grid)
        left_column.addWidget(when_section)
        
        # Transaction Details Section
        details_section, details_layout = create_section("🏪 Transaction Details")
        details_grid = QtWidgets.QGridLayout()
        details_grid.setContentsMargins(0, 4, 0, 0)
        details_grid.setHorizontalSpacing(12)
        details_grid.setVerticalSpacing(6)
        
        user_label = QtWidgets.QLabel("User:")
        user_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(user_label, 0, 0)
        details_grid.addWidget(make_selectable_label(user_name or "—"), 0, 1)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(site_label, 1, 0)
        details_grid.addWidget(make_selectable_label(site_name or "—"), 1, 1)
        
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(method_type_label, 2, 0)
        details_grid.addWidget(make_selectable_label(method_type or "—"), 2, 1)
        
        method_label = QtWidgets.QLabel("Method:")
        method_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(method_label, 3, 0)
        details_grid.addWidget(make_selectable_label(method_name or "—"), 3, 1)
        
        amount_label = QtWidgets.QLabel("Amount:")
        amount_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(amount_label, 4, 0)
        details_grid.addWidget(make_selectable_label(f"${float(self.redemption.amount):.2f}"), 4, 1)
        
        fees_label = QtWidgets.QLabel("Fees:")
        fees_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(fees_label, 5, 0)
        details_grid.addWidget(make_selectable_label(f"${float(self.redemption.fees):.2f}"), 5, 1)
        
        details_grid.setColumnStretch(1, 1)
        details_layout.addLayout(details_grid)
        left_column.addWidget(details_section)
        left_column.addStretch(1)
        
        columns_layout.addLayout(left_column, 1)
        
        # ========== RIGHT COLUMN ==========
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)
        
        # Processing Details Section
        processing_section, processing_layout = create_section("⚙️ Processing Details")
        processing_grid = QtWidgets.QGridLayout()
        processing_grid.setContentsMargins(0, 4, 0, 0)
        processing_grid.setHorizontalSpacing(12)
        processing_grid.setVerticalSpacing(6)
        
        redemption_type_label = QtWidgets.QLabel("Redemption Type:")
        redemption_type_label.setStyleSheet("color: palette(mid);")
        processing_grid.addWidget(redemption_type_label, 0, 0)
        type_text = "Partial" if self.redemption.more_remaining else "Full"
        processing_grid.addWidget(make_selectable_label(type_text), 0, 1)
        
        receipt_label = QtWidgets.QLabel("Receipt Date:")
        receipt_label.setStyleSheet("color: palette(mid);")
        processing_grid.addWidget(receipt_label, 1, 0)
        receipt_text = format_date(self.redemption.receipt_date) if self.redemption.receipt_date else "—"
        processing_grid.addWidget(make_selectable_label(receipt_text), 1, 1)
        
        processed_label = QtWidgets.QLabel("Processed:")
        processed_label.setStyleSheet("color: palette(mid);")
        processing_grid.addWidget(processed_label, 2, 0)
        processed_text = "Yes" if self.redemption.processed else "No"
        processing_grid.addWidget(make_selectable_label(processed_text), 2, 1)
        
        processing_grid.setColumnStretch(1, 1)
        processing_layout.addLayout(processing_grid)
        right_column.addWidget(processing_section)
        right_column.addStretch(1)
        
        columns_layout.addLayout(right_column, 1)
        
        layout.addWidget(columns_widget)

        # ========== NOTES SECTION (Full Width Below) ==========
        notes_section, notes_layout = create_section("📝 Notes")
        notes_value = self.redemption.notes or ""
        
        if notes_value:
            notes_display = QtWidgets.QTextEdit()
            notes_display.setReadOnly(True)
            notes_display.setPlainText(notes_value)
            notes_display.setMaximumHeight(80)
            notes_display.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            notes_layout.addWidget(notes_display)
        else:
            notes_empty = QtWidgets.QLabel("—")
            notes_empty.setStyleSheet("color: palette(mid); font-style: italic;")
            notes_layout.addWidget(notes_empty)
        
        layout.addWidget(notes_section)
        layout.addStretch(1)
        return widget
        form.setColumnStretch(5, 1)

        layout.addLayout(form)
        layout.addStretch(1)

        return widget
    
    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label

    def _create_related_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        allocations = self._fetch_allocations()
        linked_sessions = self._get_linked_sessions()

        allocated_total = Decimal("0")
        for alloc in allocations:
            try:
                allocated_total += Decimal(str(alloc.get("allocated_amount") or "0"))
            except Exception:
                continue

        redemption_amount = Decimal(str(getattr(self.redemption, "amount", "0") or "0"))
        realized = self._fetch_realized_transaction()
        realized_cost_basis = Decimal(str(realized.get("cost_basis", "0") or "0")) if realized else Decimal("0")

        if getattr(self.redemption, "is_free_sc", False):
            unbased = redemption_amount
            summary_text = f"Cost basis: $0.00 (Free SC)    Unbased portion: ${unbased:.2f}"
        else:
            unbased = redemption_amount - allocated_total
            if unbased < Decimal("0"):
                unbased = Decimal("0")
            summary_text = (
                f"Allocated basis: ${allocated_total:.2f}    "
                f"Cost basis: ${realized_cost_basis:.2f}    "
                f"Unbased portion: ${unbased:.2f}"
            )

        summary = QtWidgets.QLabel(summary_text)
        summary.setStyleSheet("color: #444;")
        layout.addWidget(summary)

        # Allocated Purchases
        purchases_group = QtWidgets.QGroupBox("Allocated Purchases (FIFO)")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)

        if not allocations:
            note = QtWidgets.QLabel(
                "No FIFO allocations found for this redemption. If this seems wrong, run Tools → Recalculate Everything."
            )
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            table = QtWidgets.QTableWidget(0, 6)
            table.setHorizontalHeaderLabels(
                ["Purchase Date", "Time", "Amount", "SC Received", "Allocated", "View Purchase"]
            )
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            header = table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 110)
            table.setColumnWidth(1, 70)
            table.setColumnWidth(2, 90)
            table.setColumnWidth(3, 90)
            table.setColumnWidth(4, 90)
            table.setColumnWidth(5, 120)

            table.setRowCount(len(allocations))
            for row_idx, a in enumerate(allocations):
                table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(a.get("purchase_date") or "—")))
                tval = (a.get("purchase_time") or "00:00:00")[:5]
                table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(tval))
                table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(f"${float(a.get('amount') or 0):.2f}"))
                table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"{float(a.get('sc_received') or 0):.2f}"))
                table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(f"${float(a.get('allocated_amount') or 0):.2f}"))

                view_btn = QtWidgets.QPushButton("👁️ View Purchase")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                pid = a.get("purchase_id")
                view_btn.clicked.connect(lambda _checked=False, pid=pid: self._open_purchase(pid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row_idx, 5, view_container)
                table.setRowHeight(
                    row_idx,
                    max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
                )

            purchases_layout.addWidget(table)

        layout.addWidget(purchases_group, 1)

        # Linked Sessions
        sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)

        if not linked_sessions:
            note = QtWidgets.QLabel("No linked game sessions found.")
            note.setWordWrap(True)
            sessions_layout.addWidget(note)
        else:
            table = QtWidgets.QTableWidget(0, 6)
            table.setHorizontalHeaderLabels([
                "Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View Session"
            ])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            header = table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 110)
            table.setColumnWidth(1, 80)
            table.setColumnWidth(2, 140)
            table.setColumnWidth(3, 120)
            table.setColumnWidth(4, 80)
            table.setColumnWidth(5, 120)

            table.setRowCount(len(linked_sessions))
            for row_idx, session in enumerate(linked_sessions):
                table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(session.session_date)))
                table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(((session.session_time or "00:00:00")[:5]) if (session.session_time is not None) else "00:00"))
                end_display = "—"
                if getattr(session, "end_date", None):
                    end_time = (getattr(session, "end_time", None) or "00:00:00")
                    end_display = f"{session.end_date} {end_time[:5]}"
                table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(end_display))
                game = self._games.get(session.game_id)
                game_type = self._game_types.get(game.game_type_id, "—") if game else "—"
                table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(game_type))
                table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(session.status or "—"))
                view_btn = QtWidgets.QPushButton("👁️ View Session")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                sid = session.id
                view_btn.clicked.connect(lambda _checked=False, sid=sid: self._open_session(sid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row_idx, 5, view_container)
                table.setRowHeight(
                    row_idx,
                    max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
                )

            sessions_layout.addWidget(table)

        layout.addWidget(sessions_group, 1)
        layout.addStretch()
        return widget

    def _fetch_realized_transaction(self):
        if not getattr(self.redemption, "id", None):
            return None
        return self.facade.db.fetch_one(
            "SELECT cost_basis, payout, net_pl FROM realized_transactions WHERE redemption_id = ?",
            (self.redemption.id,),
        )

    def _fetch_allocations(self):
        if not getattr(self.redemption, "id", None):
            return []
        query = """
            SELECT
                ra.purchase_id,
                ra.allocated_amount,
                p.amount,
                p.sc_received,
                p.purchase_date,
                p.purchase_time,
                p.remaining_amount
            FROM redemption_allocations ra
            JOIN purchases p ON p.id = ra.purchase_id
            WHERE ra.redemption_id = ?
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time, '00:00:00') ASC, p.id ASC
        """
        return self.facade.db.fetch_all(query, (self.redemption.id,))

    def _get_linked_sessions(self):
        return self.facade.get_linked_sessions_for_redemption(self.redemption.id)

    def _to_datetime(self, date_value, time_value):
        if not date_value:
            return None
        try:
            d = date_value
            if isinstance(d, str):
                d = datetime.strptime(d, "%Y-%m-%d").date()
            t = (time_value or "00:00:00").strip() or "00:00:00"
            if len(t) == 5:
                t = f"{t}:00"
            return datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _open_purchase(self, purchase_id: int):
        if purchase_id is None:
            return
        parent = self.parent()
        if parent and hasattr(parent, "main_window"):
            main_window = parent.main_window
            if main_window and hasattr(main_window, "open_purchase"):
                self.accept()
                main_window.open_purchase(purchase_id)
                return

        purchase = self.facade.get_purchase(purchase_id)
        if not purchase:
            QtWidgets.QMessageBox.warning(self, "Warning", "Purchase not found")
            return
        from ui.tabs.purchases_tab import PurchaseViewDialog

        self.accept()
        dialog = PurchaseViewDialog(purchase=purchase, facade=self.facade, parent=self)
        dialog.exec()

    def _open_session(self, session_id: int):
        parent = self.parent()
        main_window = None
        while parent is not None:
            if hasattr(parent, "main_window") and parent.main_window is not None:
                main_window = parent.main_window
                break
            parent = parent.parent()

        if main_window and hasattr(main_window, "open_session"):
            self.accept()
            main_window.open_session(session_id)
            return

        session = self.facade.get_game_session(session_id)
        if not session:
            QtWidgets.QMessageBox.warning(self, "Warning", "Session not found")
            return
        from ui.tabs.game_sessions_tab import ViewSessionDialog

        self.accept()
        dialog = ViewSessionDialog(self.facade, session=session, parent=self)
        dialog.exec()

    def _open_realized_position(self):
        redemption_id = getattr(self.redemption, "id", None)
        if not redemption_id:
            return

        parent = self.parent()
        main_window = None
        while parent is not None:
            if hasattr(parent, "main_window") and parent.main_window is not None:
                main_window = parent.main_window
                break
            parent = parent.parent()

        if main_window and hasattr(main_window, "open_realized_by_redemption"):
            self.accept()
            main_window.open_realized_by_redemption(redemption_id)
            return
