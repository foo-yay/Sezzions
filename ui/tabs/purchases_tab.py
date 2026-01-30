"""
Purchases tab - Manage purchases with FIFO tracking
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Optional
from app_facade import AppFacade
from models.purchase import Purchase
from ui.date_filter_widget import DateFilterWidget
from ui.table_header_filters import TableHeaderFilter
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar


class PurchasesTab(QtWidgets.QWidget):
    """Tab for managing purchases"""
    
    def __init__(self, facade: AppFacade, main_window=None):
        super().__init__()
        self.facade = facade
        self.main_window = main_window
        self.purchases = []
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Purchases")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Search
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search purchases...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_purchases)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)
        
        layout.addLayout(header_layout)

        info = QtWidgets.QLabel("Log every sweep coin purchase here. This is your cost basis.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Date Filter
        self.date_filter = DateFilterWidget()
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("➕ Add Purchase")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_purchase)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View Purchase")
        self.view_btn.clicked.connect(self._view_purchase)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)
        
        self.edit_btn = QtWidgets.QPushButton("✏️ Edit Purchase")
        self.edit_btn.clicked.connect(self._edit_purchase)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete Purchase")
        self.delete_btn.clicked.connect(self._delete_purchase)
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
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Date/Time", "User", "Site", "Amount", "SC Received", "Starting SC",
            "Card", "Cashback", "Remaining", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_purchase)
        
        # Enable custom context menu for spreadsheet UX
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)

        # Add spreadsheet stats bar
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)

        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.refresh_data)

        self._header_initialized = False
        
        # Set up keyboard shortcuts for spreadsheet UX
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)
        
        # Load data
        self.refresh_data()
    
    def refresh_data(self):
        """Reload purchases from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.purchases = self.facade.get_all_purchases(start_date=start_date, end_date=end_date)
        self._populate_table()
    
    def _populate_table(self):
        """Populate table with purchases"""
        search_text = self.search_edit.text().lower()
        
        # Filter purchases
        if search_text:
            filtered = []
            for p in self.purchases:
                parts = [
                    str(p.purchase_date),
                    getattr(p, 'user_name', '') or '',
                    getattr(p, 'site_name', '') or '',
                    getattr(p, 'card_name', '') or '',
                    str(p.amount),
                    str(p.sc_received),
                    str(p.starting_sc_balance),
                    str(p.cashback_earned),
                    str(p.remaining_amount),
                    p.notes or '',
                ]
                haystack = " ".join(parts).lower()
                if search_text in haystack:
                    filtered.append(p)
        else:
            filtered = self.purchases
        
        # Sort by date/time descending
        filtered.sort(key=lambda p: p.datetime_str, reverse=True)
        
        self.table.setRowCount(len(filtered))
        
        for row, purchase in enumerate(filtered):
            # Date/Time
            time_val = purchase.purchase_time or ""
            if time_val and len(time_val) > 5:
                time_val = time_val[:5]
            date_time = f"{purchase.purchase_date} {time_val}".strip()
            date_item = QtWidgets.QTableWidgetItem(date_time)
            date_item.setData(QtCore.Qt.UserRole, purchase.id)
            self.table.setItem(row, 0, date_item)

            # User
            user = getattr(purchase, 'user_name', None) or "—"
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(user))

            # Site
            site = getattr(purchase, 'site_name', None) or "—"
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(site))

            # Amount
            amount_str = f"${float(purchase.amount):.2f}"
            amount_item = QtWidgets.QTableWidgetItem(amount_str)
            amount_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 3, amount_item)

            # SC Received
            sc_str = f"{float(purchase.sc_received):.2f}"
            sc_item = QtWidgets.QTableWidgetItem(sc_str)
            sc_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 4, sc_item)

            # Starting SC
            start_sc_str = f"{float(purchase.starting_sc_balance):.2f}"
            start_sc_item = QtWidgets.QTableWidgetItem(start_sc_str)
            start_sc_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 5, start_sc_item)

            # Card
            card = getattr(purchase, 'card_name', None) or "—"
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(card))

            # Cashback
            cashback_str = f"${float(purchase.cashback_earned):.2f}"
            cashback_item = QtWidgets.QTableWidgetItem(cashback_str)
            cashback_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 7, cashback_item)

            # Remaining (FIFO indicator)
            remaining_str = f"${float(purchase.remaining_amount):.2f}"
            remaining_item = QtWidgets.QTableWidgetItem(remaining_str)
            remaining_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            if purchase.is_fully_consumed:
                remaining_item.setForeground(QtGui.QColor("#999"))
            elif purchase.consumed_amount > 0:
                remaining_item.setForeground(QtGui.QColor("#ff9800"))
            self.table.setItem(row, 8, remaining_item)

            # Notes
            notes = (purchase.notes or "")[:100]
            self.table.setItem(row, 9, QtWidgets.QTableWidgetItem(notes))
        
        self._apply_header_sizing()
        self.table_filter.apply_filters()
    
    def _filter_purchases(self):
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
        # Check if any cells are selected
        has_selection = self.table.selectionModel().hasSelection()
        
        # Get unique rows that have any selected cells
        selected_rows = self._get_selected_row_numbers()
        self.view_btn.setVisible(len(selected_rows) == 1)
        self.edit_btn.setVisible(len(selected_rows) == 1)
        self.delete_btn.setVisible(len(selected_rows) > 0)
        
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
    
    def _get_selected_purchase_id(self):
        """Get ID of selected purchase"""
        ids = self._get_selected_purchase_ids()
        return ids[0] if ids else None

    def _get_selected_purchase_ids(self):
        """Get IDs of selected purchases (any cell from each row)"""
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids
    
    def _add_purchase(self):
        """Show dialog to add new purchase"""
        dialog = PurchaseDialog(self.facade, self)
        
        while dialog.exec():
            try:
                purchase_date = dialog.get_date()
                # Get time once and reuse it - don't call get_time() multiple times
                # because it returns datetime.now() each time if field is empty!
                purchase_time = dialog.get_time()
                
                # For balance check, we need to compute expected balance BEFORE this purchase
                # So we subtract 1 second from the purchase time to get the moment just before
                from datetime import datetime, timedelta
                try:
                    purchase_dt = datetime.strptime(purchase_time, "%H:%M:%S")
                    balance_check_time = (purchase_dt - timedelta(seconds=1)).strftime("%H:%M:%S")
                except:
                    balance_check_time = purchase_time
                
                expected_total, _expected_redeem = self.facade.compute_expected_balances(
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    session_date=purchase_date,
                    session_time=balance_check_time,
                )
                starting_sc = dialog.get_starting_sc_balance()
                sc_received = dialog.get_sc_received()
                
                pre_purchase_balance = Decimal(str(starting_sc)) - Decimal(str(sc_received))
                balance_delta = pre_purchase_balance - Decimal(str(expected_total))
                if abs(balance_delta) > Decimal("0.50"):
                    direction = "higher" if balance_delta > 0 else "lower"
                    response = QtWidgets.QMessageBox.question(
                        self,
                        "Balance Mismatch Detected",
                        "The calculated pre-purchase balance does not match the expected balance from recorded sessions.\n\n"
                        f"Post-purchase SC (entered): {float(starting_sc):,.2f} SC\n"
                        f"SC received: {float(sc_received):,.2f} SC\n"
                        f"Pre-purchase balance: {float(pre_purchase_balance):,.2f} SC\n"
                        f"Expected pre-purchase: {float(expected_total):,.2f} SC\n"
                        f"Difference: {float(balance_delta):,.2f} SC ({direction})\n\n"
                        "This usually means:\n"
                        "• Untracked wins/losses or freebies\n"
                        "• A missing Game Session\n\n"
                        "Continue anyway?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No,
                    )
                    if response != QtWidgets.QMessageBox.Yes:
                        # User said No - loop back to let them edit the dialog again
                        continue
                        
                purchase = self.facade.create_purchase(
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    amount=dialog.get_amount(),
                    sc_received=dialog.get_sc_received(),
                    starting_sc_balance=starting_sc,
                    cashback_earned=dialog.get_cashback_earned(),
                    purchase_date=purchase_date,
                    card_id=dialog.card_id,
                    purchase_time=purchase_time,
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                message = f"Purchase of ${float(purchase.amount):.2f} created"
                QtCore.QTimer.singleShot(100, lambda: self._prompt_start_session(purchase.id, message))
                break  # Success - exit the loop
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to create purchase:\n{str(e)}"
                )
                break  # Error - exit the loop
    
    def _edit_purchase(self):
        """Show dialog to edit selected purchase"""
        purchase_id = self._get_selected_purchase_id()
        if not purchase_id:
            return
        
        purchase = self.facade.get_purchase(purchase_id)
        if not purchase:
            return

        dialog = PurchaseDialog(self.facade, self, purchase)
        
        while dialog.exec():
            try:
                force_site_user_change = False

                if purchase.consumed_amount > 0:
                    # Legacy parity: amount cannot change once consumed.
                    new_amount = dialog.get_amount()
                    if new_amount != purchase.amount:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Cannot Change Amount",
                            f"This purchase has ${float(purchase.consumed_amount):.2f} consumed.\n\n"
                            "You cannot change the purchase amount once it has allocations."
                        )
                        break  # Exit the loop

                    # Site/user changes are allowed only with explicit user confirmation.
                    if dialog.user_id != purchase.user_id or dialog.site_id != purchase.site_id:
                        reply = QtWidgets.QMessageBox.question(
                            self,
                            "Force Site/User Change?",
                            "This purchase has already been allocated by FIFO.\n\n"
                            "Changing User/Site will clear and rebuild FIFO allocations and realized P/L for the affected pairs.\n\n"
                            "Proceed?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        )
                        if reply != QtWidgets.QMessageBox.Yes:
                            break  # Exit the loop
                        force_site_user_change = True

                purchase_date = dialog.get_date()
                purchase_time = dialog.get_time()
                expected_total, _expected_redeem = self.facade.compute_expected_balances(
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    session_date=purchase_date,
                    session_time=purchase_time,
                )
                starting_sc = dialog.get_starting_sc_balance()
                sc_received = dialog.get_sc_received()
                pre_purchase_balance = Decimal(str(starting_sc)) - Decimal(str(sc_received))
                balance_delta = pre_purchase_balance - Decimal(str(expected_total))
                if abs(balance_delta) > Decimal("0.50"):
                    direction = "higher" if balance_delta > 0 else "lower"
                    response = QtWidgets.QMessageBox.question(
                        self,
                        "Balance Mismatch Detected",
                        "The calculated pre-purchase balance does not match the expected balance from recorded sessions.\n\n"
                        f"Post-purchase SC (entered): {float(starting_sc):,.2f} SC\n"
                        f"SC received: {float(sc_received):,.2f} SC\n"
                        f"Pre-purchase balance: {float(pre_purchase_balance):,.2f} SC\n"
                        f"Expected pre-purchase: {float(expected_total):,.2f} SC\n"
                        f"Difference: {float(balance_delta):,.2f} SC ({direction})\n\n"
                        "This usually means:\n"
                        "• Untracked wins/losses or freebies\n"
                        "• A missing Game Session\n\n"
                        "Continue anyway?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No,
                    )
                    if response != QtWidgets.QMessageBox.Yes:
                        # User said No - loop back to let them edit the dialog again
                        continue

                # Check if purchase has FIFO allocations or is dormant
                old_purchase = self.facade.get_purchase(purchase_id)
                needs_reprocessing = False
                if old_purchase:
                    has_allocations = old_purchase.consumed_amount > 0
                    is_dormant = old_purchase.status == 'dormant'
                    
                    # Check if user is changing critical fields
                    critical_change = (
                        dialog.get_amount() != old_purchase.amount or
                        dialog.user_id != old_purchase.user_id or
                        dialog.site_id != old_purchase.site_id or
                        purchase_date != old_purchase.purchase_date
                    )
                    
                    if (has_allocations or is_dormant) and critical_change:
                        needs_reprocessing = True
                        consumed_msg = f"${float(old_purchase.consumed_amount):.2f} consumed by redemptions" if has_allocations else ""
                        dormant_msg = "marked dormant (closed position)" if is_dormant else ""
                        status_msg = " and ".join(filter(None, [consumed_msg, dormant_msg]))
                        
                        response = QtWidgets.QMessageBox.question(
                            self,
                            "Reprocess Redemptions?",
                            f"This purchase has {status_msg}.\n\n"
                            "Editing will reprocess all redemptions for this site/user pair.\n\n"
                            "This will:\n"
                            "• Rebuild FIFO allocations from scratch\n"
                            "• Recalculate all realized transactions\n"
                            "• Update all cost basis amounts\n\n"
                            "Continue?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.No,
                        )
                        if response != QtWidgets.QMessageBox.Yes:
                            break  # Exit the loop

                updated = self.facade.update_purchase(
                    purchase_id,
                    force_site_user_change=force_site_user_change,
                    user_id=dialog.user_id,
                    site_id=dialog.site_id,
                    amount=dialog.get_amount(),
                    sc_received=dialog.get_sc_received(),
                    starting_sc_balance=starting_sc,
                    cashback_earned=dialog.get_cashback_earned(),
                    purchase_date=purchase_date,
                    card_id=dialog.card_id,
                    purchase_time=purchase_time,
                    notes=dialog.notes_edit.toPlainText() or None
                )
                self.refresh_data()
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()
                QtWidgets.QMessageBox.information(
                    self, "Success", f"Purchase updated"
                )
                break  # Success - exit the loop
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update purchase:\n{str(e)}"
                )
                break  # Error - exit the loop
    
    def _delete_purchase(self):
        """Delete selected purchase"""
        purchase_ids = self._get_selected_purchase_ids()
        if not purchase_ids:
            return

        purchases = []
        needs_reprocessing = []
        for purchase_id in purchase_ids:
            purchase = self.facade.get_purchase(purchase_id)
            if not purchase:
                continue
            
            is_dormant = purchase.status == 'dormant'
            
            if purchase.consumed_amount > 0 or is_dormant:
                needs_reprocessing.append((purchase, is_dormant))
            purchases.append(purchase)

        if needs_reprocessing:
            consumed_list = "\n".join([
                f"  • ${float(p.amount):.2f} on {p.purchase_date} "
                f"({'dormant' if dormant else f'${float(p.consumed_amount):.2f} consumed'})"
                for p, dormant in needs_reprocessing
            ])
            response = QtWidgets.QMessageBox.question(
                self, "Reprocess After Delete?",
                f"{len(needs_reprocessing)} purchase(es) have FIFO allocations or are dormant:\n\n"
                f"{consumed_list}\n\n"
                "Deleting will trigger reprocessing of all redemptions for affected site/user pairs.\n\n"
                "Continue with deletion and reprocessing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if response != QtWidgets.QMessageBox.Yes:
                return

        count = len(purchases)
        if count == 0:
            return

        if count == 1:
            purchase = purchases[0]
            prompt = (
                f"Delete purchase of ${float(purchase.amount):.2f} on {purchase.purchase_date}?\n\n"
                "This cannot be undone."
            )
        else:
            prompt = (
                f"Delete {count} purchases?\n\n"
                "This cannot be undone."
            )

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                for purchase in purchases:
                    self.facade.delete_purchase(purchase.id)
                self.refresh_data()
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Purchase(s) deleted"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete purchase(s):\n{str(e)}"
                )

    def _view_purchase(self):
        """Show dialog to view selected purchase"""
        purchase_id = self._get_selected_purchase_id()
        if not purchase_id:
            return

        purchase = self.facade.get_purchase(purchase_id)
        if not purchase:
            return

        # Look up display names
        user = self.facade.get_user(purchase.user_id)
        site = self.facade.get_site(purchase.site_id)
        card = self.facade.get_card(purchase.card_id) if purchase.card_id else None
        
        user_name = user.name if user else ""
        site_name = site.name if site else ""
        card_name = card.name if card else ""

        def handle_edit():
            dialog.close()
            self._edit_purchase()

        def handle_delete():
            dialog.close()
            self._delete_purchase()

        dialog = PurchaseViewDialog(
            self.facade,
            purchase,
            parent=self,
            user_name=user_name,
            site_name=site_name,
            card_name=card_name,
            on_edit=handle_edit,
            on_delete=handle_delete
        )
        dialog.exec()

    def open_purchase_by_id(self, purchase_id: int):
        self.refresh_data()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(QtCore.Qt.UserRole) == purchase_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break
        purchase = self.facade.get_purchase(purchase_id)
        if not purchase:
            return
        
        # Look up display names
        user = self.facade.get_user(purchase.user_id)
        site = self.facade.get_site(purchase.site_id)
        card = self.facade.get_card(purchase.card_id) if purchase.card_id else None
        
        user_name = user.name if user else ""
        site_name = site.name if site else ""
        card_name = card.name if card else ""
        
        dialog = PurchaseViewDialog(
            self.facade,
            purchase,
            parent=self,
            user_name=user_name,
            site_name=site_name,
            card_name=card_name
        )
        dialog.exec()

    def _prompt_start_session(self, purchase_id: int, success_message: str):
        prompt_dialog = QtWidgets.QDialog(self)
        prompt_dialog.setWindowTitle("Purchase Saved")
        prompt_dialog.resize(420, 160)

        layout = QtWidgets.QVBoxLayout(prompt_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        success_label = QtWidgets.QLabel(success_message)
        success_label.setWordWrap(True)
        layout.addWidget(success_label)

        start_session_cb = QtWidgets.QCheckBox("Start a gaming session now with this purchase?")
        start_session_cb.setChecked(False)
        layout.addWidget(start_session_cb)

        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(prompt_dialog.accept)
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        prompt_dialog.exec()

        if start_session_cb.isChecked():
            purchase = self.facade.get_purchase(purchase_id)
            if not purchase:
                QtWidgets.QMessageBox.warning(self, "Error", "Could not load purchase data")
                return

            # Use the user-entered starting_sc_balance directly
            # This is the POST-purchase balance that the user saw on the site
            starting_total_sc = float(purchase.starting_sc_balance or 0.0)
            
            purchase_time = purchase.purchase_time or "00:00:00"
            if len(purchase_time) == 5:
                purchase_time = f"{purchase_time}:00"
            
            # Use the same time as the purchase - this represents the moment you got the SC
            # and are ready to start playing with it
            session_time = purchase_time
                
            if len(purchase_time) == 5:
                purchase_time = f"{purchase_time}:00"
            try:
                session_time = (datetime.strptime(purchase_time, "%H:%M:%S") + timedelta(seconds=1)).strftime("%H:%M:%S")
            except Exception:
                session_time = purchase_time

            site_name = getattr(purchase, "site_name", "") or ""
            user_name = getattr(purchase, "user_name", "") or ""
            if not site_name:
                site = self.facade.get_site(purchase.site_id)
                site_name = site.name if site else ""
            if not user_name:
                user = self.facade.get_user(purchase.user_id)
                user_name = user.name if user else ""

            self._open_start_session_from_purchase(
                purchase.purchase_date,
                session_time,
                site_name,
                user_name,
                starting_total_sc,
            )

    def _open_start_session_from_purchase(self, session_date, session_time, site_name, user_name, starting_total_sc):
        if not self.main_window or not hasattr(self.main_window, "game_sessions_tab"):
            return

        from ui.tabs.game_sessions_tab import StartSessionDialog
        dialog = StartSessionDialog(self.facade, parent=self)
        dialog.date_edit.setText(dialog._format_date_for_input(session_date))
        dialog.time_edit.setText(session_time)
        dialog.site_combo.setCurrentText(site_name)
        dialog.user_combo.setCurrentText(user_name)
        dialog.start_total_edit.setText(str(starting_total_sc))

        def handle_save():
            data, error = dialog.collect_data()
            if error:
                QtWidgets.QMessageBox.warning(self, "Invalid Entry", error)
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
                index = getattr(self.main_window, "_tab_index", {}).get("game_sessions", 2)
                self.main_window.tab_bar.setCurrentIndex(index)
                if hasattr(self.main_window.game_sessions_tab, "load_data"):
                    self.main_window.game_sessions_tab.load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to start session: {e}")

        dialog.save_btn.clicked.connect(handle_save)
        dialog.exec()

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
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()
        self.refresh_data()

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

    def _export_csv(self):
        """Export purchases to CSV"""
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Purchases",
            f"purchases_{date.today().isoformat()}.csv",
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
                    f"Exported purchases to:\n{filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", f"Failed to export:\n{str(e)}"
                )


class PurchaseDialog(QtWidgets.QDialog):
    """Modern purchase dialog with streamlined layout"""
    
    def __init__(self, facade: AppFacade, parent=None, purchase: Purchase = None):
        super().__init__(parent)
        self.facade = facade
        self.purchase = purchase
        self.user_id = purchase.user_id if purchase else None
        self.site_id = purchase.site_id if purchase else None
        self.card_id = purchase.card_id if purchase else None
        
        self.setWindowTitle("Edit Purchase" if purchase else "Add Purchase")
        self.setMinimumWidth(750)
        self.setMinimumHeight(520)
        self.resize(750, 520)
        
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
        self.calendar_btn.clicked.connect(self._pick_date)

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

        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.setEditable(True)
        self.card_combo.lineEdit().setPlaceholderText("Choose user first...")

        self.amount_edit = QtWidgets.QLineEdit()
        self.amount_edit.setPlaceholderText("0.00")
        
        self.sc_edit = QtWidgets.QLineEdit()
        self.sc_edit.setPlaceholderText("0.00")
        
        self.start_sc_edit = QtWidgets.QLineEdit()
        self.start_sc_edit.setPlaceholderText("0.00")
        
        self.balance_check_label = QtWidgets.QLabel("—")
        self.balance_check_label.setObjectName("HelperText")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.setWordWrap(True)

        self.cashback_edit = QtWidgets.QLineEdit()
        self.cashback_edit.setPlaceholderText("Auto-calc (editable)")
        self.cashback_edit.setFocusPolicy(QtCore.Qt.ClickFocus)  # Exclude from tab chain

        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Optional...")
        self.notes_edit.setFixedHeight(80)
        self.notes_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Add subtle section separators using frames
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

        # Main Purchase Details card with 2-column grid
        main_header = self._create_section_header("💳  Purchase Details")
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
        self.user_combo.setMinimumWidth(180)
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
        self.site_combo.setMinimumWidth(180)
        main_grid.addWidget(self.site_combo, row, 1)
        
        # Cashback (right column)
        cashback_label = QtWidgets.QLabel("Cashback ($):")
        cashback_label.setObjectName("FieldLabel")
        cashback_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(cashback_label, row, 2)
        self.cashback_edit.setFixedWidth(140)
        main_grid.addWidget(self.cashback_edit, row, 3)
        
        row += 1
        
        # Payment Card
        card_label = QtWidgets.QLabel("Payment Card:")
        card_label.setObjectName("FieldLabel")
        card_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(card_label, row, 0)
        self.card_combo.setMinimumWidth(180)
        main_grid.addWidget(self.card_combo, row, 1)
        
        # SC Received (right column)
        sc_label = QtWidgets.QLabel("SC Received:")
        sc_label.setObjectName("FieldLabel")
        sc_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        main_grid.addWidget(sc_label, row, 2)
        self.sc_edit.setFixedWidth(140)
        main_grid.addWidget(self.sc_edit, row, 3)
        
        row += 1
        
        # Empty left (for alignment)
        # Starting SC Balance (right column)
        start_sc_label = QtWidgets.QLabel("Post-Purchase SC:")
        start_sc_label.setObjectName("FieldLabel")
        start_sc_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        start_sc_label.setToolTip("Your TOTAL SC balance shown on the site AFTER this purchase completes.\n\nFor example: if you had 50 SC, bought 100 SC, you should enter 150 SC here.")
        main_grid.addWidget(start_sc_label, row, 2)
        self.start_sc_edit.setFixedWidth(140)
        self.start_sc_edit.setToolTip("Enter the TOTAL balance shown on site after purchase.\n\nNOT the amount you just bought - the TOTAL including what you had before.")
        main_grid.addWidget(self.start_sc_edit, row, 3)
        
        row += 1
        
        # Balance check (spans all columns)
        balance_container = QtWidgets.QWidget()
        balance_container.setObjectName("BalanceCheck")
        balance_layout = QtWidgets.QHBoxLayout(balance_container)
        balance_layout.setContentsMargins(8, 8, 8, 8)
        balance_layout.addWidget(self.balance_check_label)
        main_grid.addWidget(balance_container, row, 0, 1, 4)
        
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
        self.site_combo.currentTextChanged.connect(self._validate_inline)
        self.card_combo.currentTextChanged.connect(self._on_card_changed)
        self.amount_edit.textChanged.connect(self._on_amount_changed)
        self.date_edit.textChanged.connect(self._validate_inline)
        self.time_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._validate_inline)
        self.card_combo.currentTextChanged.connect(self._validate_inline)
        self.amount_edit.textChanged.connect(self._validate_inline)
        self.sc_edit.textChanged.connect(self._validate_inline)
        self.start_sc_edit.textChanged.connect(self._validate_inline)
        self.user_combo.currentTextChanged.connect(self._update_balance_check)
        self.site_combo.currentTextChanged.connect(self._update_balance_check)
        self.date_edit.textChanged.connect(self._update_balance_check)
        self.time_edit.textChanged.connect(self._update_balance_check)
        self.start_sc_edit.textChanged.connect(self._update_balance_check)
        
        # Set tab order: Date -> Time -> User -> Site -> Card -> Amount -> SC Received -> Starting SC Balance -> Save
        # Cashback has ClickFocus policy so it's excluded from tab chain
        self.setTabOrder(self.date_edit, self.time_edit)
        self.setTabOrder(self.time_edit, self.user_combo)
        self.setTabOrder(self.user_combo, self.site_combo)
        self.setTabOrder(self.site_combo, self.card_combo)
        self.setTabOrder(self.card_combo, self.amount_edit)
        self.setTabOrder(self.amount_edit, self.sc_edit)
        self.setTabOrder(self.sc_edit, self.start_sc_edit)
        self.setTabOrder(self.start_sc_edit, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)
        self.setTabOrder(self.cancel_btn, self.clear_btn)

        if purchase:
            self._load_purchase()
        else:
            self._clear_form()

        self._update_completers()
        self._validate_inline()
        self._update_balance_check()
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            # Shrink dialog back to original height
            self.setMinimumHeight(520)
            self.setMaximumHeight(520)
            self.resize(self.width(), 520)
        else:
            self.notes_toggle.setText("📝 Notes ▼")
            # Expand dialog height to accommodate notes
            self.setMinimumHeight(650)
            self.setMaximumHeight(16777215)  # Reset to default max
            self.resize(self.width(), 650)
            self.notes_edit.setFocus()
    
    def _create_section_header(self, text: str) -> QtWidgets.QLabel:
        """Create a section header"""
        label = QtWidgets.QLabel(text)
        label.setObjectName("SectionHeader")
        return label
    
    def _update_completers(self):
        for combo in (self.user_combo, self.site_combo, self.card_combo):
            if not combo.isEditable():
                combo.setCompleter(None)
                continue
            completer = QtWidgets.QCompleter(combo.model())
            completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            completer.setFilterMode(QtCore.Qt.MatchStartsWith)
            completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
            popup = QtWidgets.QListView()
            popup.setStyleSheet(
                "QListView { background: palette(base); color: palette(text); }"
                "QListView::item:selected { background: palette(highlight); color: palette(highlighted-text); }"
            )
            completer.setPopup(popup)
            combo.setCompleter(completer)
            line_edit = combo.lineEdit()
            if line_edit is not None:
                line_edit.setCompleter(completer)
                app = QtWidgets.QApplication.instance()
                if app is not None and hasattr(app, "_completer_filter"):
                    line_edit.installEventFilter(app._completer_filter)

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
        else:
            try:
                parsed = self.get_date()
                if parsed > date.today():
                    self._set_invalid(self.date_edit, "Date cannot be in the future.")
                    valid = False
                else:
                    self._set_valid(self.date_edit)
            except Exception:
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

        card_text = self.card_combo.currentText().strip()
        if not card_text:
            self._set_invalid(self.card_combo, "Card is required.")
            valid = False
        elif not hasattr(self, "_card_map") or card_text.lower() not in self._card_map:
            self._set_invalid(self.card_combo, "Select a valid Card for the chosen User.")
            valid = False
        else:
            self._set_valid(self.card_combo)

        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            self._set_invalid(self.amount_edit, "Amount is required.")
            valid = False
        else:
            try:
                amount_val = Decimal(amount_text)
                if amount_val <= 0:
                    raise ValueError("non-positive")
                self._set_valid(self.amount_edit)
            except Exception:
                self._set_invalid(self.amount_edit, "Enter a valid amount (max 2 decimals).")
                valid = False

        sc_text = self.sc_edit.text().strip()
        if not sc_text:
            self._set_invalid(self.sc_edit, "SC Received is required.")
            valid = False
        else:
            try:
                sc_val = Decimal(sc_text)
                if sc_val < 0:
                    raise ValueError("negative")
                self._set_valid(self.sc_edit)
            except Exception:
                self._set_invalid(self.sc_edit, "Enter a valid SC amount (max 2 decimals).")
                valid = False

        start_sc_text = self.start_sc_edit.text().strip()
        if not start_sc_text:
            self._set_invalid(self.start_sc_edit, "Starting SC is required.")
            valid = False
        else:
            try:
                start_sc_val = Decimal(start_sc_text)
                if start_sc_val < 0:
                    raise ValueError("negative")
                self._set_valid(self.start_sc_edit)
            except Exception:
                self._set_invalid(self.start_sc_edit, "Enter a valid Starting SC (max 2 decimals).")
                valid = False

        cashback_text = self.cashback_edit.text().strip()
        if cashback_text:
            try:
                cashback_val = Decimal(cashback_text)
                if cashback_val < 0:
                    raise ValueError("negative")
                self._set_valid(self.cashback_edit)
            except Exception:
                self._set_invalid(self.cashback_edit, "Enter a valid cashback amount (max 2 decimals).")
                valid = False
        else:
            self._set_valid(self.cashback_edit)

        return valid

    def _update_balance_check(self):
        site_text = self.site_combo.currentText().strip()
        user_text = self.user_combo.currentText().strip()
        start_sc_text = self.start_sc_edit.text().strip()

        if not site_text or not user_text or not start_sc_text:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        if user_text.lower() not in self._user_lookup or site_text.lower() not in self._site_lookup:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        try:
            start_sc_val = Decimal(start_sc_text)
        except Exception:
            self.balance_check_label.setText("—")
            self.balance_check_label.setProperty("status", "neutral")
            self.balance_check_label.style().unpolish(self.balance_check_label)
            self.balance_check_label.style().polish(self.balance_check_label)
            return

        date_text = self.date_edit.text().strip()
        if date_text:
            parsed_date = None
            for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
                try:
                    parsed_date = datetime.strptime(date_text, fmt).date()
                    break
                except ValueError:
                    continue
            if parsed_date is None:
                self.balance_check_label.setText("—")
                self.balance_check_label.setProperty("status", "neutral")
                self.balance_check_label.style().unpolish(self.balance_check_label)
                self.balance_check_label.style().polish(self.balance_check_label)
                return
        else:
            parsed_date = date.today()

        time_text = self.time_edit.text().strip()
        if time_text:
            try:
                if len(time_text) == 5:
                    datetime.strptime(time_text, "%H:%M")
                    parsed_time = f"{time_text}:00"
                elif len(time_text) == 8:
                    datetime.strptime(time_text, "%H:%M:%S")
                    parsed_time = time_text
                else:
                    raise ValueError("Invalid format")
            except Exception:
                self.balance_check_label.setText("—")
                self.balance_check_label.setProperty("status", "neutral")
                self.balance_check_label.style().unpolish(self.balance_check_label)
                self.balance_check_label.style().polish(self.balance_check_label)
                return
        else:
            parsed_time = datetime.now().strftime("%H:%M:%S")

        user_id = self._user_lookup[user_text.lower()]
        site_id = self._site_lookup[site_text.lower()]
        expected_total, _expected_redeem = self.facade.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=parsed_date,
            session_time=parsed_time,
        )

        # Get SC received to calculate pre-purchase balance
        sc_received_text = self.sc_edit.text().strip()
        try:
            sc_received_val = Decimal(sc_received_text) if sc_received_text else Decimal("0.00")
        except Exception:
            sc_received_val = Decimal("0.00")
        
        # Calculate the pre-purchase balance (what balance was BEFORE this purchase)
        pre_purchase_balance = Decimal(str(start_sc_val)) - sc_received_val
        delta = pre_purchase_balance - Decimal(str(expected_total))
        
        # Calculate expected post-purchase balance for display
        expected_post_purchase = Decimal(str(expected_total)) + sc_received_val
        
        if abs(delta) <= Decimal("0.01"):
            # Balance matches expected - all good
            self.balance_check_label.setProperty("status", "match")
            self.balance_check_label.setText("✓ Balance Check: No problems detected")
        elif delta > Decimal("0.01"):
            # Balance is higher than expected
            self.balance_check_label.setProperty("status", "warning")
            self.balance_check_label.setText(
                f"✗ Balance Check: Starting SC balance is {float(delta):.2f} higher than expected ({float(expected_post_purchase):.2f} SC)"
            )
        else:
            # Balance is lower than expected (problem)
            self.balance_check_label.setProperty("status", "error")
            self.balance_check_label.setText(
                f"✗ Balance Check: Starting SC balance is {float(abs(delta)):.2f} lower than expected ({float(expected_post_purchase):.2f} SC)"
            )

        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)
    
    def _on_user_changed(self, _value: str = ""):
        """Update user_id when selection changes"""
        user_name = self.user_combo.currentText().strip()
        if not user_name or user_name.lower() not in self._user_lookup:
            self.user_id = None
            self.card_combo.blockSignals(True)
            self.card_combo.clear()
            self.card_combo.setCurrentIndex(-1)
            self.card_combo.setEditText("")
            self.card_combo.lineEdit().setPlaceholderText("Select a user first")
            self.card_combo.blockSignals(False)
            self._card_map = {}
            return

        self.user_id = self._user_lookup[user_name.lower()]
        self.cashback_edit.clear()
        self._load_cards_for_user()

    def _on_card_changed(self, value: str):
        """Update card_id and cashback display when selection changes"""
        card_name = value.strip()
        if not card_name:
            self.card_id = None
            self.cashback_edit.clear()
            return

        if not hasattr(self, "_card_map") or card_name.lower() not in self._card_map:
            self.card_id = None
            self.cashback_edit.clear()
            return

        card = self._card_map[card_name.lower()]
        self.card_id = card.id
        self._recalculate_cashback(card.cashback_rate)

    def _on_amount_changed(self, _value: str):
        """Recalculate cashback when amount changes"""
        if not self.card_id:
            return
        card = self.facade.get_card(self.card_id)
        if card:
            self._recalculate_cashback(card.cashback_rate)

    def _recalculate_cashback(self, cashback_rate: float):
        amount_text = self.amount_edit.text().strip()
        if not amount_text:
            return
        try:
            amount_val = Decimal(amount_text)
            cashback = (amount_val * Decimal(str(cashback_rate)) / Decimal("100")).quantize(Decimal("0.01"))
            # Update cashback field (user can still manually override)
            self.cashback_edit.setText(f"{cashback:.2f}")
        except Exception:
            pass

    def _load_cards_for_user(self):
        """Load cards for selected user"""
        self._card_map = {}
        self.card_combo.blockSignals(True)
        self.card_combo.clear()

        if self.user_id:
            cards = self.facade.get_all_cards(user_id=self.user_id, active_only=True)
            for card in cards:
                display_name = card.display_name()
                self._card_map[display_name.lower()] = card
                self.card_combo.addItem(display_name)

        self.card_combo.blockSignals(False)
        self.card_combo.setCurrentIndex(-1)
        self.card_combo.setEditText("")
        self.card_combo.lineEdit().setPlaceholderText("")
        self._update_completers()
    
    def _pick_date(self):
        """Show date picker dialog"""
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
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _set_now(self):
        self.time_edit.setText(datetime.now().strftime("%H:%M"))
    
    def get_date(self) -> date:
        """Parse and return date"""
        date_str = self.date_edit.text().strip()
        if not date_str:
            return date.today()
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return date.today()

    def get_time(self) -> Optional[str]:
        time_str = self.time_edit.text().strip()
        if not time_str:
            return datetime.now().strftime("%H:%M:%S")
        if len(time_str) == 5:
            return f"{time_str}:00"
        return time_str
    
    def get_amount(self) -> Decimal:
        """Parse and return amount"""
        return Decimal(self.amount_edit.text().strip())

    def get_sc_received(self) -> Decimal:
        return Decimal(self.sc_edit.text().strip())

    def get_starting_sc_balance(self) -> Decimal:
        return Decimal(self.start_sc_edit.text().strip())

    def get_cashback_earned(self) -> Decimal:
        """Get cashback from the editable field"""
        try:
            text = self.cashback_edit.text().strip()
            if text:
                return Decimal(text)
            return Decimal("0.00")
        except Exception:
            return Decimal("0.00")
    
    def _validate_and_accept(self):
        """Validate input and accept dialog"""
        if not self._validate_inline():
            return
        user_text = self.user_combo.currentText().strip()
        if not user_text or user_text.lower() not in self._user_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "User is required"
            )
            return

        self.user_id = self._user_lookup[user_text.lower()]
        
        site_text = self.site_combo.currentText().strip()
        if not site_text or site_text.lower() not in self._site_lookup:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Site is required"
            )
            return

        self.site_id = self._site_lookup[site_text.lower()]

        card_text = self.card_combo.currentText().strip()
        if not card_text or not hasattr(self, "_card_map") or card_text.lower() not in self._card_map:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Card is required"
            )
            return

        self.card_id = self._card_map[card_text.lower()].id
        
        # Validate amount
        amount_str = self.amount_edit.text().strip()
        if not amount_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount is required"
            )
            return
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Amount must be greater than zero"
                )
                return
        except:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Amount must be a valid number"
            )
            return

        # Validate SC received
        sc_str = self.sc_edit.text().strip()
        if not sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received is required"
            )
            return
        try:
            sc_val = Decimal(sc_str)
            if sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "SC Received must be a valid number"
            )
            return

        # Validate starting SC
        start_sc_str = self.start_sc_edit.text().strip()
        if not start_sc_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC is required"
            )
            return
        try:
            start_sc_val = Decimal(start_sc_str)
            if start_sc_val < 0:
                raise ValueError("negative")
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Starting SC must be a valid number"
            )
            return
        
        # Validate date
        date_str = self.date_edit.text().strip()
        if not date_str:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date is required"
            )
            return
        
        try:
            self.get_date()
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Validation Error", "Date must be in MM/DD/YY format"
            )
            return
        
        # Validate time if provided
        time_str = self.time_edit.text().strip()
        if time_str:
            try:
                if len(time_str) == 5:
                    datetime.strptime(time_str, "%H:%M")
                elif len(time_str) == 8:
                    datetime.strptime(time_str, "%H:%M:%S")
                else:
                    raise ValueError("Invalid format")
            except Exception:
                QtWidgets.QMessageBox.warning(
                    self, "Validation Error", "Time must be in HH:MM format"
                )
                return
        
        self.accept()

    def _clear_form(self):
        self.user_id = None
        self.site_id = None
        self.card_id = None
        self.date_edit.clear()
        self.time_edit.clear()
        self.user_combo.setCurrentIndex(-1)
        self.user_combo.setEditText("")
        self.site_combo.setCurrentIndex(-1)
        self.site_combo.setEditText("")
        self.card_combo.clear()
        self.card_combo.setCurrentIndex(-1)
        self.card_combo.setEditText("")
        self.card_combo.lineEdit().setPlaceholderText("Select user first...")
        self.cashback_edit.clear()
        self.amount_edit.clear()
        self.sc_edit.clear()
        self.start_sc_edit.clear()
        self.notes_edit.clear()
        self._set_today()
        self.balance_check_label.setText("—")
        self.balance_check_label.setProperty("status", "neutral")
        self.balance_check_label.style().unpolish(self.balance_check_label)
        self.balance_check_label.style().polish(self.balance_check_label)

    def _load_purchase(self):
        self.date_edit.setText(self.purchase.purchase_date.strftime("%m/%d/%y"))
        if self.purchase.purchase_time:
            time_str = self.purchase.purchase_time
            if len(time_str) > 5:
                time_str = time_str[:5]
            self.time_edit.setText(time_str)

        user_name = getattr(self.purchase, "user_name", None)
        if not user_name:
            user = self.facade.get_user(self.purchase.user_id)
            user_name = user.name if user else ""
        if user_name:
            self.user_combo.setCurrentText(user_name)
            self._on_user_changed()

        site_name = getattr(self.purchase, "site_name", None)
        if not site_name:
            site = self.facade.get_site(self.purchase.site_id)
            site_name = site.name if site else ""
        if site_name:
            self.site_combo.setCurrentText(site_name)

        if self.purchase.card_id:
            card = self.facade.get_card(self.purchase.card_id)
            if card:
                display = card.display_name()
                self.card_combo.setCurrentText(display)

        self.amount_edit.setText(f"{float(self.purchase.amount):.2f}")
        self.cashback_edit.setText(f"{float(self.purchase.cashback_earned):.2f}")
        self.sc_edit.setText(f"{float(self.purchase.sc_received):.2f}")
        self.start_sc_edit.setText(f"{float(self.purchase.starting_sc_balance):.2f}")

        if self.purchase.notes:
            self.notes_edit.setPlainText(self.purchase.notes)


class PurchaseViewDialog(QtWidgets.QDialog):
    """Modern view-only purchase dialog with sectioned layout"""
    
    def __init__(self, facade: AppFacade, purchase: Purchase, parent=None,
                 user_name: str = "", site_name: str = "", card_name: str = "",
                 on_edit=None, on_delete=None):
        super().__init__(parent)
        self.facade = facade
        self.purchase = purchase
        self._on_edit = on_edit
        self._on_delete = on_delete
        
        self.setWindowTitle(f"Purchase Details (ID: {purchase.id})")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.linked_sessions = self._get_linked_sessions()
        self.linked_redemptions = self._get_linked_redemptions()
        self._game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        self._games = {g.id: g for g in self.facade.list_all_games()}

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("SetupSubTabs")
        tabs.addTab(self._create_details_tab(user_name, site_name, card_name), "Details")
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

        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _create_details_tab(self, user_name: str, site_name: str, card_name: str) -> QtWidgets.QWidget:
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
        when_grid.addWidget(make_selectable_label(format_date(self.purchase.purchase_date)), 0, 1)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setStyleSheet("color: palette(mid);")
        when_grid.addWidget(time_label, 1, 0)
        when_grid.addWidget(make_selectable_label(format_time(self.purchase.purchase_time)), 1, 1)
        
        when_grid.setColumnStretch(1, 1)
        when_layout.addLayout(when_grid)
        left_column.addWidget(when_section)
        
        # Details Section
        details_section, details_layout = create_section("🏪 Details")
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
        
        card_label = QtWidgets.QLabel("Card:")
        card_label.setStyleSheet("color: palette(mid);")
        details_grid.addWidget(card_label, 2, 0)
        details_grid.addWidget(make_selectable_label(card_name or "—"), 2, 1)
        
        details_grid.setColumnStretch(1, 1)
        details_layout.addLayout(details_grid)
        left_column.addWidget(details_section)
        left_column.addStretch(1)
        
        columns_layout.addLayout(left_column, 1)
        
        # ========== RIGHT COLUMN ==========
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(10)
        
        # Balances Section
        balances_section, balances_layout = create_section("💰 Balances")
        balances_grid = QtWidgets.QGridLayout()
        balances_grid.setContentsMargins(0, 4, 0, 0)
        balances_grid.setHorizontalSpacing(12)
        balances_grid.setVerticalSpacing(6)
        
        amount_val = f"${float(self.purchase.amount):.2f}"
        cashback_val = f"${float(self.purchase.cashback_earned):.2f}"
        start_sc_val = f"{float(self.purchase.starting_sc_balance):.2f}"
        sc_val = f"{float(self.purchase.sc_received):.2f}"
        basis_val = f"${float(self.purchase.remaining_amount):.2f}"
        
        amount_label = QtWidgets.QLabel("Amount:")
        amount_label.setStyleSheet("color: palette(mid);")
        balances_grid.addWidget(amount_label, 0, 0)
        balances_grid.addWidget(make_selectable_label(amount_val, align_right=True), 0, 1)
        
        cashback_label = QtWidgets.QLabel("Cashback:")
        cashback_label.setStyleSheet("color: palette(mid);")
        balances_grid.addWidget(cashback_label, 1, 0)
        balances_grid.addWidget(make_selectable_label(cashback_val, align_right=True), 1, 1)
        
        start_sc_label = QtWidgets.QLabel("Starting SC:")
        start_sc_label.setStyleSheet("color: palette(mid);")
        balances_grid.addWidget(start_sc_label, 2, 0)
        balances_grid.addWidget(make_selectable_label(start_sc_val, align_right=True), 2, 1)
        
        sc_label = QtWidgets.QLabel("SC Received:")
        sc_label.setStyleSheet("color: palette(mid);")
        balances_grid.addWidget(sc_label, 3, 0)
        balances_grid.addWidget(make_selectable_label(sc_val, align_right=True), 3, 1)
        
        basis_label = QtWidgets.QLabel("Remaining Basis:")
        basis_label.setStyleSheet("color: palette(mid);")
        balances_grid.addWidget(basis_label, 4, 0)
        balances_grid.addWidget(make_selectable_label(basis_val, align_right=True), 4, 1)
        
        balances_grid.setColumnStretch(1, 1)
        balances_layout.addLayout(balances_grid)
        right_column.addWidget(balances_section)
        right_column.addStretch(1)
        
        columns_layout.addLayout(right_column, 1)
        
        layout.addWidget(columns_widget)

        # ========== NOTES SECTION (Full Width Below) ==========
        notes_section, notes_layout = create_section("📝 Notes")
        notes_value = self.purchase.notes or ""
        
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

        allocations = self._fetch_allocated_redemptions()

        if not self.linked_sessions and not allocations:
            placeholder = QtWidgets.QLabel("No related sessions or redemptions found.")
            placeholder.setStyleSheet("color: palette(mid); font-style: italic;")
            layout.addWidget(placeholder)
            layout.addStretch()
            return widget

        if allocations:
            summary_layout = QtWidgets.QHBoxLayout()
            allocated_total = sum(Decimal(str(a.get("allocated_amount") or "0")) for a in allocations)
            original_amount = Decimal(str(self.purchase.amount or 0))
            remaining_amount = Decimal(str(self.purchase.remaining_amount or 0))
            summary_layout.addWidget(QtWidgets.QLabel(f"Original Amount: ${original_amount:.2f}"))
            summary_layout.addSpacing(12)
            summary_layout.addWidget(QtWidgets.QLabel(f"Allocated: ${allocated_total:.2f}"))
            summary_layout.addSpacing(12)
            summary_layout.addWidget(QtWidgets.QLabel(f"Remaining Basis: ${remaining_amount:.2f}"))
            summary_layout.addStretch(1)
            layout.addLayout(summary_layout)

            redemptions_group = QtWidgets.QGroupBox("Allocated Redemptions")
            redemptions_layout = QtWidgets.QVBoxLayout(redemptions_group)
            redemptions_layout.setContentsMargins(8, 10, 8, 8)

            table = QtWidgets.QTableWidget(0, 4)
            table.setHorizontalHeaderLabels([
                "Redemption Date/Time", "Redemption Amount", "Allocated", "View Redemption"
            ])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 160)
            table.setColumnWidth(1, 140)
            table.setColumnWidth(2, 110)
            table.setColumnWidth(3, 120)
            
            row_height = table.verticalHeader().defaultSectionSize()
            header_height = table.horizontalHeader().height()
            table.setMaximumHeight(header_height + (row_height * 3) + 10)

            table.setRowCount(len(allocations))
            for row, alloc in enumerate(allocations):
                date_val = str(alloc.get("redemption_date") or "—")
                time_val = (alloc.get("redemption_time") or "00:00:00")[:5]
                date_time_display = f"{date_val} {time_val}" if date_val != "—" else time_val
                date_item = QtWidgets.QTableWidgetItem(date_time_display)
                date_item.setData(QtCore.Qt.UserRole, alloc.get("redemption_id"))
                table.setItem(row, 0, date_item)
                table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"${float(alloc.get('amount') or 0):.2f}"))
                table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"${float(alloc.get('allocated_amount') or 0):.2f}"))

                view_btn = QtWidgets.QPushButton("👁️ View Redemption")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                rid = alloc.get("redemption_id")
                view_btn.clicked.connect(lambda _checked=False, rid=rid: self._open_redemption_by_id(rid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row, 3, view_container)
                table.setRowHeight(
                    row,
                    max(table.rowHeight(row), view_btn.sizeHint().height() + 16),
                )

            redemptions_layout.addWidget(table)
            layout.addWidget(redemptions_group)

        if self.linked_sessions:
            sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
            sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
            sessions_layout.setContentsMargins(8, 10, 8, 8)

            table = QtWidgets.QTableWidget(0, 5)
            table.setHorizontalHeaderLabels([
                "Session Date/Time", "End Date/Time", "Game", "Status", "View Session"
            ])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            header = table.horizontalHeader()
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(0, 160)
            table.setColumnWidth(1, 140)
            table.setColumnWidth(2, 150)
            table.setColumnWidth(3, 90)
            table.setColumnWidth(4, 120)
            
            row_height = table.verticalHeader().defaultSectionSize()
            header_height = table.horizontalHeader().height()
            table.setMaximumHeight(header_height + (row_height * 3) + 10)

            table.setRowCount(len(self.linked_sessions))
            for row, session in enumerate(self.linked_sessions):
                session_date = str(session.session_date)
                start_time = (session.session_time or "")[:5]
                start_display = f"{session_date} {start_time}" if session_date else "—"
                date_item = QtWidgets.QTableWidgetItem(start_display)
                date_item.setData(QtCore.Qt.UserRole, session.id)
                table.setItem(row, 0, date_item)
                end_display = "—"
                if getattr(session, "end_date", None):
                    end_time = (getattr(session, "end_time", None) or "00:00:00")[:5]
                    end_display = f"{session.end_date} {end_time}"
                table.setItem(row, 1, QtWidgets.QTableWidgetItem(end_display))

                game = self._games.get(session.game_id)
                game_name = game.name if game else "—"
                table.setItem(row, 2, QtWidgets.QTableWidgetItem(game_name))
                table.setItem(row, 3, QtWidgets.QTableWidgetItem(session.status or "Active"))

                view_btn = QtWidgets.QPushButton("👁️ View Session")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
                view_btn.clicked.connect(lambda _checked=False, sid=session.id: self._open_session_by_id(sid))
                view_container = QtWidgets.QWidget()
                view_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row, 4, view_container)
                table.setRowHeight(
                    row,
                    max(table.rowHeight(row), view_btn.sizeHint().height() + 16),
                )

            sessions_layout.addWidget(table)
            layout.addWidget(sessions_group)

        layout.addStretch()
        return widget

    def _fetch_allocated_redemptions(self):
        if not getattr(self.purchase, "id", None):
            return []
        query = """
            SELECT r.id as redemption_id, r.redemption_date, r.redemption_time, r.amount, ra.allocated_amount
            FROM redemption_allocations ra
            JOIN redemptions r ON r.id = ra.redemption_id
            WHERE ra.purchase_id = ?
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time,'00:00:00') ASC, r.id ASC
        """
        return self.facade.db.fetch_all(query, (self.purchase.id,))

    def _open_session_by_id(self, session_id: int):
        parent = self.parent()
        if parent and hasattr(parent, "main_window"):
            main_window = parent.main_window
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

    def _open_redemption_by_id(self, redemption_id: int):
        from ui.tabs.redemptions_tab import RedemptionViewDialog
        parent = self.parent()
        if parent and hasattr(parent, "main_window"):
            main_window = parent.main_window
            if main_window and hasattr(main_window, "open_redemption"):
                self.accept()
                main_window.open_redemption(redemption_id)
                return

        redemption = self.facade.get_redemption(redemption_id)
        if not redemption:
            QtWidgets.QMessageBox.warning(self, "Warning", "Redemption not found")
            return

        self.accept()
        dialog = RedemptionViewDialog(redemption=redemption, facade=self.facade, parent=self)
        dialog.exec()

    def _get_linked_sessions(self):
        return self.facade.get_linked_sessions_for_purchase(self.purchase.id)

    def _get_linked_redemptions(self):
        return self.facade.get_redemptions_allocated_to_purchase(self.purchase.id)
    
