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
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload redemptions from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.redemptions = self.facade.get_all_redemptions(start_date=start_date, end_date=end_date)
        self._populate_table()
    
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

    def _get_filtered_redemptions(self):
        search_text = self.search_edit.text().lower()

        if search_text:
            filtered = [r for r in self.redemptions
                        if search_text in str(r.redemption_date).lower()
                        or (hasattr(r, 'user_name') and r.user_name and search_text in r.user_name.lower())
                        or (hasattr(r, 'site_name') and r.site_name and search_text in r.site_name.lower())
                        or (hasattr(r, 'method_name') and r.method_name and search_text in r.method_name.lower())
                        or (r.notes and search_text in r.notes.lower())]
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
        self.edit_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)
    
    def _get_selected_redemption_id(self):
        """Get ID of selected redemption"""
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).data(QtCore.Qt.UserRole)
    
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
                self.facade.update_redemption(
                    redemption_id,
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    amount=dialog.get_amount(),
                    fees=dialog.get_fees(),
                    redemption_date=dialog.get_date(),
                    redemption_method_id=dialog.method_id,
                    redemption_time=dialog.get_time(),
                    receipt_date=dialog.get_receipt_date(),
                    processed=dialog.processed_check.isChecked(),
                    more_remaining=dialog.is_partial_selected(),
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update redemption:\n{str(e)}"
                )
    
    def _delete_redemption(self):
        """Delete selected redemption"""
        redemption_id = self._get_selected_redemption_id()
        if not redemption_id:
            return
        
        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            return
        
        msg = f"Delete redemption of ${float(redemption.amount):.2f} on {redemption.redemption_date}?\n\nThis cannot be undone."
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.facade.delete_redemption(redemption_id)
                self.refresh_data()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete redemption:\n{str(e)}"
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
        self.refresh_data()

    def _export_csv(self):
        """Export redemptions to CSV"""
        filtered = self._get_filtered_redemptions()
        if not filtered:
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
                    writer.writerow([
                        "Date", "Time", "User", "Site", "Amount",
                        "Receipt Date", "Method", "Processed", "Notes"
                    ])
                    for redemption in filtered:
                        writer.writerow([
                            redemption.redemption_date,
                            redemption.redemption_time or "",
                            getattr(redemption, 'user_name', '') or "",
                            getattr(redemption, 'site_name', '') or "",
                            redemption.amount,
                            redemption.receipt_date or "",
                            getattr(redemption, 'method_name', '') or "",
                            "Yes" if redemption.processed else "No",
                            redemption.notes or ""
                        ])

                QtWidgets.QMessageBox.information(
                    self, "Export Complete",
                    f"Exported {len(filtered)} redemptions to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )


class RedemptionDialog(QtWidgets.QDialog):
    """Dialog for adding/editing redemptions"""

    def __init__(self, facade: AppFacade, parent=None, redemption: Redemption = None):
        super().__init__(parent)
        self.facade = facade
        self.redemption = redemption
        self.user_id = redemption.user_id if redemption else None
        self.site_id = redemption.site_id if redemption else None
        self.method_id = redemption.redemption_method_id if redemption else None

        self.setWindowTitle("Edit Redemption" if redemption else "Add Redemption")
        self.resize(540, 520)

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
        self.calendar_btn.clicked.connect(lambda: self._pick_date(self.date_edit))

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
        users = facade.get_all_users(active_only=True)
        user_names = [u.name for u in users]
        self.user_combo.addItems(user_names)
        self._user_lookup = {u.name.lower(): u.id for u in users}

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        sites = facade.get_all_sites(active_only=True)
        site_names = [s.name for s in sites]
        self.site_combo.addItems(site_names)
        self._site_lookup = {s.name.lower(): s.id for s in sites}

        self.method_type_combo = QtWidgets.QComboBox()
        self.method_type_combo.setEditable(True)
        self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")

        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.lineEdit().setPlaceholderText("Select a method type first")

        self._methods = facade.get_all_redemption_methods(active_only=True)
        self._method_lookup = {m.name.lower(): m.id for m in self._methods}
        self._method_by_id = {m.id: m.name for m in self._methods}
        self._method_type_lookup = {m.id: m.method_type for m in self._methods}

        self.amount_edit = QtWidgets.QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        self.fees_edit = QtWidgets.QLineEdit()
        self.fees_edit.setPlaceholderText("Optional fees")

        amount_row = QtWidgets.QHBoxLayout()
        amount_row.setSpacing(8)
        amount_row.addWidget(self.amount_edit, 2)
        amount_row.addWidget(QtWidgets.QLabel("Fees:"))
        amount_row.addWidget(self.fees_edit, 1)

        self.receipt_edit = QtWidgets.QLineEdit()
        self.receipt_edit.setPlaceholderText("MM/DD/YY")
        self.receipt_btn = QtWidgets.QPushButton("📅")
        self.receipt_btn.setFixedWidth(44)
        self.receipt_btn.clicked.connect(lambda: self._pick_date(self.receipt_edit))
        receipt_row = QtWidgets.QHBoxLayout()
        receipt_row.setSpacing(8)
        receipt_row.addWidget(self.receipt_edit, 1)
        receipt_row.addWidget(self.receipt_btn)

        self.partial_radio = QtWidgets.QRadioButton("Partial (balance remains)")
        self.final_radio = QtWidgets.QRadioButton("Full (close basis)")
        self.redemption_group = QtWidgets.QButtonGroup(self)
        self.redemption_group.addButton(self.partial_radio)
        self.redemption_group.addButton(self.final_radio)

        type_row = QtWidgets.QHBoxLayout()
        type_row.setSpacing(12)
        type_row.addWidget(self.partial_radio)
        type_row.addWidget(self.final_radio)
        type_row.addStretch(1)

        self.processed_check = QtWidgets.QCheckBox("Processed")
        checkbox_row = QtWidgets.QHBoxLayout()
        checkbox_row.setSpacing(12)
        checkbox_row.addWidget(self.processed_check)
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
        form.addWidget(QtWidgets.QLabel("Method Type"), 4, 0)
        form.addWidget(self.method_type_combo, 4, 1)
        form.addWidget(QtWidgets.QLabel("Method"), 5, 0)
        form.addWidget(self.method_combo, 5, 1)
        form.addWidget(QtWidgets.QLabel("Amount"), 6, 0)
        form.addLayout(amount_row, 6, 1)
        form.addWidget(QtWidgets.QLabel("Receipt Date"), 7, 0)
        form.addLayout(receipt_row, 7, 1)
        form.addWidget(QtWidgets.QLabel("Redemption Type"), 8, 0)
        form.addLayout(type_row, 8, 1)
        form.addWidget(QtWidgets.QLabel("Flags"), 9, 0)
        form.addLayout(checkbox_row, 9, 1)
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

        if not self.partial_radio.isChecked() and not self.final_radio.isChecked():
            self._set_invalid(self.partial_radio, "Select Partial or Full.")
            self._set_invalid(self.final_radio, "Select Partial or Full.")
            valid = False
        else:
            self._set_valid(self.partial_radio)
            self._set_valid(self.final_radio)

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
        cancel_btn = QtWidgets.QPushButton("Cancel")
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
        self.partial_radio.setChecked(False)
        self.final_radio.setChecked(False)
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
            self.final_radio.setChecked(True)
        if self.redemption.notes:
            self.notes_edit.setPlainText(self.redemption.notes)


class RedemptionViewDialog(QtWidgets.QDialog):
    """Dialog for viewing redemption details (read-only)"""

    def __init__(self, redemption: Redemption, facade: AppFacade, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.redemption = redemption
        self.facade = facade
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.setWindowTitle("View Redemption")
        self.resize(640, 520)

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

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(user_name, site_name, method_name, method_type), "Details")
        tabs.addTab(self._create_related_tab(), "Related")
        layout.addWidget(tabs, 1)

        btn_row = QtWidgets.QHBoxLayout()
        if self._on_delete:
            delete_btn = QtWidgets.QPushButton("Delete")
            delete_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(delete_btn)

        btn_row.addStretch(1)

        if self._on_edit:
            edit_btn = QtWidgets.QPushButton("Edit")
            edit_btn.clicked.connect(self._on_edit)
            btn_row.addWidget(edit_btn)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _create_details_tab(self, user_name: str, site_name: str, method_name: str, method_type: Optional[str]) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        form = QtWidgets.QGridLayout(widget)
        form.setContentsMargins(10, 10, 10, 10)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(1, 1)

        def fmt(value):
            if value is None or value == "":
                return "—"
            return str(value)

        row = 0
        def add_row(label_text, value):
            nonlocal row
            label = QtWidgets.QLabel(label_text)
            label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("InfoField")
            value_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            form.addWidget(label, row, 0)
            form.addWidget(value_label, row, 1, 1, 3)
            row += 1

        add_row("Date:", fmt(self.redemption.redemption_date))
        add_row("Time:", fmt(self.redemption.redemption_time))
        add_row("User:", user_name or "—")
        add_row("Site:", site_name or "—")
        add_row("Amount:", f"${float(self.redemption.amount):.2f}")
        add_row("Fees:", f"${float(self.redemption.fees):.2f}")
        add_row("Receipt Date:", fmt(self.redemption.receipt_date))
        add_row("Method Type:", method_type or "—")
        add_row("Method:", method_name or "—")
        add_row("Processed:", "Yes" if self.redemption.processed else "No")
        add_row("Type:", "Partial" if self.redemption.more_remaining else "Full")

        notes_text = self.redemption.notes or ""
        notes_label = QtWidgets.QLabel("Notes:")
        notes_label.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_text else QtCore.Qt.AlignVCenter)
        )
        notes_value = QtWidgets.QLabel(notes_text or "—")
        notes_value.setObjectName("InfoField")
        notes_value.setWordWrap(True)
        notes_value.setAlignment(
            QtCore.Qt.AlignLeft | (QtCore.Qt.AlignTop if notes_text else QtCore.Qt.AlignVCenter)
        )
        form.addWidget(
            notes_label,
            row,
            0,
            QtCore.Qt.AlignTop if notes_text else QtCore.Qt.AlignVCenter,
        )
        form.addWidget(notes_value, row, 1, 1, 3)

        return widget

    def _create_related_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        allocations = self._fetch_allocations()
        linked_sessions = self._get_linked_sessions()

        try:
            allocated_total = sum(Decimal(str(a.get("allocated_amount") or "0")) for a in allocations)
        except Exception:
            allocated_total = Decimal("0")
        try:
            redemption_amount = Decimal(str(getattr(self.redemption, "amount", "0") or "0"))
        except Exception:
            redemption_amount = Decimal("0")
        unbased = redemption_amount - allocated_total
        if unbased < Decimal("0"):
            unbased = Decimal("0")

        summary = QtWidgets.QLabel(
            f"Allocated basis: ${allocated_total:.2f}    Unbased portion: ${unbased:.2f}"
        )
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
                ["Purchase Date", "Time", "Amount", "Allocated", "Remaining", "View Purchase"]
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
                table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"${float(a.get('allocated_amount') or 0):.2f}"))
                table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(f"${float(a.get('remaining_amount') or 0):.2f}"))

                view_btn = QtWidgets.QPushButton("View Purchase")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(120)
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
            table = QtWidgets.QTableWidget(0, 5)
            table.setHorizontalHeaderLabels(["Session Date", "Start Time", "End Date/Time", "Status", "View Session"])
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
            table.setColumnWidth(3, 80)
            table.setColumnWidth(4, 120)

            table.setRowCount(len(linked_sessions))
            for row_idx, session in enumerate(linked_sessions):
                table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(session.session_date)))
                table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(((session.session_time or "00:00:00")[:5]) if (session.session_time is not None) else "00:00"))
                end_display = "—"
                if getattr(session, "end_date", None):
                    end_time = (getattr(session, "end_time", None) or "00:00:00")
                    end_display = f"{session.end_date} {end_time[:5]}"
                table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(end_display))
                table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(session.status or "—"))

                view_btn = QtWidgets.QPushButton("View Session")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(110)
                sid = session.id
                view_btn.clicked.connect(lambda _checked=False, sid=sid: self._open_session(sid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row_idx, 4, view_container)
                table.setRowHeight(
                    row_idx,
                    max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
                )

            sessions_layout.addWidget(table)

        layout.addWidget(sessions_group, 1)
        layout.addStretch()
        return widget

    def _fetch_allocations(self):
        if not getattr(self.redemption, "id", None):
            return []
        query = """
            SELECT
                ra.purchase_id,
                ra.allocated_amount,
                p.amount,
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
