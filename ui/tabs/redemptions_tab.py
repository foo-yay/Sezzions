"""
Redemptions tab - Manage redemptions
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from bisect import bisect_left, bisect_right
from datetime import date, datetime
from typing import Literal, Optional
from app_facade import AppFacade
from models.redemption import Redemption
from ui.date_filter_widget import DateFilterWidget
from ui.table_header_filters import TableHeaderFilter
from ui.input_parsers import parse_date_input
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from tools.time_utils import (
    parse_time_input,
    current_time_with_seconds,
    format_time_display,
    time_to_db_string,
)
from ui.adjustment_dialogs import ViewAdjustmentsDialog
from tools.timezone_utils import get_accounting_timezone_name, get_entry_timezone_name


RedemptionConfirmationDecision = Literal[
    "ok",
    "warn_full_selected_but_balance_remaining",
    "warn_partial_selected_but_looks_like_full_cashout",
    "info_redeems_all_redeemable_but_balance_remains",
]


def classify_redemption_confirmation(
    *,
    amount: Decimal,
    expected_total_balance: Optional[Decimal],
    expected_redeemable_balance: Optional[Decimal],
    is_partial: bool,
    threshold: Decimal = Decimal("0.50"),
) -> RedemptionConfirmationDecision:
    """Classify whether the UI should prompt for full vs partial.

    All amounts are in the same currency units (typically $).
    """
    if expected_total_balance is None:
        return "ok"

    expected_total_balance = expected_total_balance or Decimal("0.00")
    expected_redeemable_balance = expected_redeemable_balance or Decimal("0.00")

    remaining_total = expected_total_balance - amount
    remaining_redeemable = expected_redeemable_balance - amount

    # Full selected but total balance appears to remain.
    if not is_partial and remaining_total > threshold:
        return "warn_full_selected_but_balance_remaining"

    # Partial selected but this looks like a full site cashout.
    if is_partial and remaining_total <= threshold:
        return "warn_partial_selected_but_looks_like_full_cashout"

    # The key "middle ground": redeeming all redeemable (or a hair above) is still
    # a partial redemption when total balance remains.
    if is_partial and remaining_total > threshold and remaining_redeemable <= threshold:
        return "info_redeems_all_redeemable_but_balance_remains"

    return "ok"


class RedemptionsTab(QtWidgets.QWidget):
    """Tab for managing redemptions"""

    @staticmethod
    def _is_zero_basis_close_marker(redemption: Redemption) -> bool:
        """True when a $0 close marker is informational rather than a real loss."""
        try:
            amount = Decimal(str(redemption.amount or 0))
        except Exception:
            amount = Decimal("0.00")

        notes = (redemption.notes or "").strip()
        return (
            amount == Decimal("0.00")
            and notes.startswith("Balance Closed")
            and "Net Loss: $0.00" in notes
        )
    
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
        year_start = date(date.today().year, 1, 1)
        self.date_filter = DateFilterWidget(
            default_start=year_start,
            default_end=date.today(),
        )
        self.date_filter.filter_changed.connect(self.refresh_data)
        layout.addWidget(self.date_filter)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("➕ Add Redemption")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_redemption)
        toolbar.addWidget(add_btn)

        self.view_btn = QtWidgets.QPushButton("👁️ View")
        self.view_btn.clicked.connect(self._view_redemption)
        self.view_btn.setVisible(False)
        toolbar.addWidget(self.view_btn)

        self.edit_btn = QtWidgets.QPushButton("✏️ Edit")
        self.edit_btn.clicked.connect(self._edit_redemption)
        self.edit_btn.setVisible(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_redemption)
        self.delete_btn.setVisible(False)
        toolbar.addWidget(self.delete_btn)

        self.mark_received_btn = QtWidgets.QPushButton("📬 Mark Received")
        self.mark_received_btn.setToolTip("Set receipt date for selected redemption(s)")
        self.mark_received_btn.clicked.connect(self._mark_received)
        self.mark_received_btn.setVisible(False)
        toolbar.addWidget(self.mark_received_btn)

        self.mark_processed_btn = QtWidgets.QPushButton("✅ Mark Processed")
        self.mark_processed_btn.setToolTip("Mark selected redemption(s) as processed")
        self.mark_processed_btn.clicked.connect(self._mark_processed)
        self.mark_processed_btn.setVisible(False)
        toolbar.addWidget(self.mark_processed_btn)

        # Cancel / Uncancel (Issue #148)
        self.cancel_btn = QtWidgets.QPushButton("🚫 Cancel")
        self.cancel_btn.setToolTip("Cancel selected pending redemption (reverses FIFO)")
        self.cancel_btn.clicked.connect(self._cancel_redemption)
        self.cancel_btn.setVisible(False)
        toolbar.addWidget(self.cancel_btn)

        self.uncancel_btn = QtWidgets.QPushButton("↩️ Uncancel")
        self.uncancel_btn.setToolTip("Uncancel selected redemption (re-applies FIFO)")
        self.uncancel_btn.clicked.connect(self._uncancel_redemption)
        self.uncancel_btn.setVisible(False)
        toolbar.addWidget(self.uncancel_btn)

        toolbar.addStretch()

        self.pending_filter_check = QtWidgets.QCheckBox("Pending")
        self.pending_filter_check.setToolTip("Show only redemptions with no receipt date")
        self.pending_filter_check.toggled.connect(self._on_quick_filter_toggled)
        toolbar.addWidget(self.pending_filter_check)

        self.unprocessed_filter_check = QtWidgets.QCheckBox("Unprocessed")
        self.unprocessed_filter_check.setToolTip("Show only redemptions that are not processed")
        self.unprocessed_filter_check.toggled.connect(self._on_quick_filter_toggled)
        toolbar.addWidget(self.unprocessed_filter_check)

        export_btn = QtWidgets.QPushButton("📤 Export CSV")
        export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(export_btn)
        
        refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Date/Time", "User", "Site", "Cost Basis", "Amount", "Unbased", "Type", "Receipt", "Method", "Processed", "Notes"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._view_redemption)
        
        # Context menu setup
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table)
        
        # Stats bar and keyboard shortcut
        self.stats_bar = SpreadsheetStatsBar()
        layout.addWidget(self.stats_bar)

        self._header_initialized = False

        self.table_filter = TableHeaderFilter(self.table, date_columns=[0], refresh_callback=self.refresh_data)
        
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self._copy_selection)

        self._load_quick_filter_state()
        
        # Load data
        self.refresh_data()

    def _get_settings_object(self):
        """Get settings object for reading/writing persistent UI preferences."""
        if self.main_window is not None and hasattr(self.main_window, "settings"):
            settings = getattr(self.main_window, "settings")
            if hasattr(settings, "get") and hasattr(settings, "set"):
                return settings

        widget = self.parentWidget()
        while widget:
            if hasattr(widget, "settings"):
                settings = getattr(widget, "settings")
                if hasattr(settings, "get") and hasattr(settings, "set"):
                    return settings
            widget = widget.parentWidget()
        return None

    def _load_quick_filter_state(self):
        settings = self._get_settings_object()
        if settings is None:
            return
        pending_checked = bool(settings.get("quick_filter_redemptions_pending", False))
        unprocessed_checked = bool(settings.get("quick_filter_redemptions_unprocessed", False))
        self.pending_filter_check.blockSignals(True)
        self.unprocessed_filter_check.blockSignals(True)
        self.pending_filter_check.setChecked(pending_checked)
        self.unprocessed_filter_check.setChecked(unprocessed_checked)
        self.pending_filter_check.blockSignals(False)
        self.unprocessed_filter_check.blockSignals(False)

    def _save_quick_filter_state(self):
        settings = self._get_settings_object()
        if settings is None:
            return
        settings.set("quick_filter_redemptions_pending", self.pending_filter_check.isChecked())
        settings.set("quick_filter_redemptions_unprocessed", self.unprocessed_filter_check.isChecked())

    def _on_quick_filter_toggled(self, _checked: bool):
        self._save_quick_filter_state()
        self._populate_table()
    
    def focus_search(self):
        """Focus the search bar (for Cmd+F/Ctrl+F shortcut - Issue #99)"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_data(self):
        """Reload redemptions from database"""
        start_date, end_date = self.date_filter.get_date_range()
        self.redemptions = self.facade.get_all_redemptions(start_date=start_date, end_date=end_date)
        self._populate_table()
    
    def _populate_table(self):
        """Populate table with redemptions"""
        filtered = self._get_filtered_redemptions()

        # Precompute per (user_id, site_id) adjustment/checkpoint timelines for "Adjusted" badges.
        adjusted_icon = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation)
        adjustment_timeline: dict[tuple[int, int], tuple[list[datetime], list[datetime], list[datetime]]] = {}
        try:
            pairs = {(int(r.user_id), int(r.site_id)) for r in filtered if getattr(r, "user_id", None) and getattr(r, "site_id", None)}
            for (user_id, site_id) in pairs:
                adjs = self.facade.adjustment_service.get_by_user_and_site(user_id=user_id, site_id=site_id, include_deleted=False)
                checkpoints: list[datetime] = []
                events: list[datetime] = []
                for adj in adjs:
                    eff_time = getattr(adj, "effective_time", None) or "00:00:00"
                    try:
                        eff_dt = datetime.combine(adj.effective_date, datetime.strptime(eff_time, "%H:%M:%S").time())
                    except Exception:
                        eff_dt = datetime.combine(adj.effective_date, datetime.strptime("00:00:00", "%H:%M:%S").time())
                    events.append(eff_dt)
                    if getattr(adj, "type", None) is not None and getattr(adj.type, "value", "") == "BALANCE_CHECKPOINT_CORRECTION":
                        checkpoints.append(eff_dt)
                checkpoints.sort()
                events.sort()
                full_redemptions = self.facade.get_full_redemption_datetimes_for_user_site(user_id=user_id, site_id=site_id)
                adjustment_timeline[(user_id, site_id)] = (checkpoints, events, full_redemptions)
        except Exception:
            adjustment_timeline = {}

        # Important: QTableWidget will actively reorder rows while we call setItem()
        # if sorting is enabled. That can lead to “mixed” rows (wrong amounts/sites)
        # and apparent duplicates depending on sort/filter/search.
        sorting_was_enabled = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(filtered))

            for row, redemption in enumerate(filtered):
                time_val = redemption.redemption_time or "00:00:00"
                if time_val and len(time_val) > 5:
                    time_val = time_val
                date_time = f"{redemption.redemption_date} {time_val}".strip()
                entry_tz = getattr(redemption, "redemption_entry_time_zone", None)
                accounting_tz = get_accounting_timezone_name()
                if entry_tz and entry_tz != accounting_tz:
                    date_time = f"{date_time} 🌐"

                is_total_loss = float(redemption.amount) == 0
                is_zero_basis_close_marker = self._is_zero_basis_close_marker(redemption)
                r_status = getattr(redemption, 'status', 'PENDING') or 'PENDING'
                receipt_date = redemption.receipt_date.isoformat() if redemption.receipt_date else ""
                is_pending = receipt_date == ""

                if r_status == 'CANCELED':
                    receipt_display = "CANCELED"
                elif r_status == 'PENDING_CANCEL':
                    receipt_display = "PENDING CANCEL"
                elif is_total_loss:
                    receipt_display = str(redemption.redemption_date)
                elif is_pending:
                    receipt_display = "PENDING"
                else:
                    receipt_display = receipt_date

                if is_zero_basis_close_marker:
                    method_display = "Closed"
                else:
                    method_display = "Loss" if is_total_loss else (getattr(redemption, 'method_name', None) or "")

                if r_status == 'CANCELED':
                    row_status = "canceled"
                elif r_status == 'PENDING_CANCEL':
                    row_status = "pending_cancel"
                elif is_zero_basis_close_marker:
                    row_status = "closed_marker"
                elif is_total_loss:
                    row_status = "total_loss"
                elif is_pending:
                    row_status = "pending"
                else:
                    row_status = "normal"

                # Date/Time
                date_item = QtWidgets.QTableWidgetItem(date_time)
                date_item.setData(QtCore.Qt.UserRole, redemption.id)
                if entry_tz and entry_tz != accounting_tz:
                    date_item.setToolTip(
                        f"Entered in travel mode ({entry_tz}). Accounting TZ: {accounting_tz}."
                    )
                self.table.setItem(row, 0, date_item)

                # User
                user = getattr(redemption, 'user_name', None) or "—"
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(user))

                # Site
                site = getattr(redemption, 'site_name', None) or "—"
                site_item = QtWidgets.QTableWidgetItem(site)
                try:
                    key = (int(redemption.user_id), int(redemption.site_id))
                    checkpoints, events, full_redemptions = adjustment_timeline.get(key, ([], [], []))
                    r_time = redemption.redemption_time or "00:00:00"
                    r_dt = datetime.combine(redemption.redemption_date, datetime.strptime(r_time, "%H:%M:%S").time())

                    cp_i = bisect_right(checkpoints, r_dt) - 1
                    prev_cp = checkpoints[cp_i] if cp_i >= 0 else None

                    red_i = bisect_left(full_redemptions, r_dt)
                    prev_full = full_redemptions[red_i - 1] if red_i - 1 >= 0 else None

                    start_bound = prev_cp
                    if prev_full is not None and (start_bound is None or prev_full > start_bound):
                        start_bound = prev_full

                    end_bound = r_dt

                    left = bisect_left(events, start_bound) if start_bound else 0
                    right = bisect_right(events, end_bound)
                    has_applicable_adjustments = left < right
                    if has_applicable_adjustments:
                        site_item.setIcon(adjusted_icon)
                        site_item.setToolTip(
                            "Adjusted: this redemption has adjustments/checkpoints at-or-before this redemption (Tools)."
                        )
                except Exception:
                    pass
                self.table.setItem(row, 2, site_item)

                # Cost Basis / Unbased
                amount_value = Decimal(str(redemption.amount))
                allocated_basis = getattr(redemption, "allocated_basis", None)
                if allocated_basis is not None:
                    try:
                        allocated_basis = Decimal(str(allocated_basis))
                    except Exception:
                        allocated_basis = None
                realized_cost_basis = getattr(redemption, "realized_cost_basis", None)
                if realized_cost_basis is not None:
                    try:
                        realized_cost_basis = Decimal(str(realized_cost_basis))
                    except Exception:
                        realized_cost_basis = None

                if getattr(redemption, "is_free_sc", False):
                    cost_basis_value = Decimal("0")
                    unbased_value = amount_value
                else:
                    cost_basis_value = realized_cost_basis
                    if cost_basis_value is None and allocated_basis is not None:
                        cost_basis_value = allocated_basis
                    if allocated_basis is None:
                        unbased_value = None
                    else:
                        unbased_value = amount_value - allocated_basis
                        if unbased_value < Decimal("0"):
                            unbased_value = Decimal("0")

                if cost_basis_value is None:
                    cost_basis_display = "—"
                else:
                    cost_basis_display = f"${float(cost_basis_value):.2f}"
                cost_basis_item = QtWidgets.QTableWidgetItem(cost_basis_display)
                cost_basis_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 3, cost_basis_item)

                # Amount
                amount_str = f"${float(redemption.amount):.2f}"
                amount_item = QtWidgets.QTableWidgetItem(amount_str)
                amount_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 4, amount_item)

                # Unbased
                unbased_display = "—" if unbased_value is None else f"${float(unbased_value):.2f}"
                unbased_item = QtWidgets.QTableWidgetItem(unbased_display)
                unbased_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 5, unbased_item)

                # Type (Full/Partial)
                type_display = "Full" if not redemption.more_remaining else "Partial"
                type_item = QtWidgets.QTableWidgetItem(type_display)
                type_item.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                self.table.setItem(row, 6, type_item)

                # Receipt
                receipt_item = QtWidgets.QTableWidgetItem(receipt_display)
                self.table.setItem(row, 7, receipt_item)

                # Method
                self.table.setItem(row, 8, QtWidgets.QTableWidgetItem(method_display))

                # Processed
                processed_item = QtWidgets.QTableWidgetItem("✓" if redemption.processed else "")
                processed_item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, 9, processed_item)

                # Notes
                notes = (redemption.notes or "")[:100]
                self.table.setItem(row, 10, QtWidgets.QTableWidgetItem(notes))

                if row_status == "total_loss":
                    color = QtGui.QColor("#c0392b")
                elif row_status == "canceled":
                    color = QtGui.QColor("#95a5a6")
                elif row_status == "pending_cancel":
                    color = QtGui.QColor("#8e44ad")
                elif row_status == "pending":
                    color = QtGui.QColor("#e67e22")
                else:
                    color = None

                if color:
                    for col in range(0, 10):
                        item = self.table.item(row, col)
                        if item:
                            item.setForeground(QtGui.QBrush(color))

        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        # Re-apply any active header sort now that all items are in place.
        if getattr(self, "table_filter", None) is not None and self.table_filter.sort_column is not None:
            self.table_filter.sort_by_column(self.table_filter.sort_column, self.table_filter.sort_order)
        else:
            self.table.setSortingEnabled(sorting_was_enabled)
            header = self.table.horizontalHeader()
            if header is not None:
                header.setSortIndicatorShown(False)
        
        self._apply_header_sizing()
        self.table_filter.apply_filters()

    def _get_filtered_redemptions(self):
        search_text = self.search_edit.text().lower()
        pending_only = self.pending_filter_check.isChecked()
        unprocessed_only = self.unprocessed_filter_check.isChecked()

        quick_filtered = []
        for r in self.redemptions:
            if pending_only:
                r_status = getattr(r, 'status', 'PENDING') or 'PENDING'
                if bool(r.receipt_date) or r_status in ('CANCELED', 'PENDING_CANCEL'):
                    continue
            if unprocessed_only and bool(r.processed):
                continue
            quick_filtered.append(r)

        if search_text:
            filtered = []
            for r in quick_filtered:
                receipt_status = "pending" if not r.receipt_date else "received"
                processed_status = "processed" if r.processed else "unprocessed"
                amount_value = Decimal(str(r.amount))
                allocated_basis = getattr(r, "allocated_basis", None)
                if allocated_basis is not None:
                    try:
                        allocated_basis = Decimal(str(allocated_basis))
                    except Exception:
                        allocated_basis = None
                realized_cost_basis = getattr(r, "realized_cost_basis", None)
                if realized_cost_basis is not None:
                    try:
                        realized_cost_basis = Decimal(str(realized_cost_basis))
                    except Exception:
                        realized_cost_basis = None

                if getattr(r, "is_free_sc", False):
                    cost_basis_value = Decimal("0")
                    unbased_value = amount_value
                else:
                    cost_basis_value = realized_cost_basis
                    if cost_basis_value is None and allocated_basis is not None:
                        cost_basis_value = allocated_basis
                    if allocated_basis is None:
                        unbased_value = None
                    else:
                        unbased_value = amount_value - allocated_basis
                        if unbased_value < Decimal("0"):
                            unbased_value = Decimal("0")
                parts = [
                    str(r.redemption_date),
                    getattr(r, 'user_name', '') or '',
                    getattr(r, 'site_name', '') or '',
                    getattr(r, 'method_name', '') or '',
                    str(r.amount),
                    str(cost_basis_value) if cost_basis_value is not None else '',
                    str(unbased_value) if unbased_value is not None else '',
                    receipt_status,
                    processed_status,
                    r.notes or '',
                ]
                haystack = " ".join(parts).lower()
                if search_text in haystack:
                    filtered.append(r)
        else:
            filtered = quick_filtered

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
        # Check if any cells are selected
        has_selection = self.table.selectionModel().hasSelection()
        
        # Get unique rows that have any selected cells
        selected_rows = self._get_selected_row_numbers()
        self.view_btn.setVisible(len(selected_rows) == 1)

        # Edit/Delete/Mark buttons — single PENDING redemption for single-item actions
        selected_redemptions = [self._get_redemption_for_row(r) for r in selected_rows]
        selected_redemptions = [r for r in selected_redemptions if r is not None]

        single_pending = (
            len(selected_redemptions) == 1
            and getattr(selected_redemptions[0], 'status', 'PENDING') == 'PENDING'
        )
        single_cancellable = (
            single_pending
            and getattr(selected_redemptions[0], 'receipt_date', None) is None
        )
        single_canceled = (
            len(selected_redemptions) == 1
            and getattr(selected_redemptions[0], 'status', 'PENDING') == 'CANCELED'
        )
        single_pending_cancel = (
            len(selected_redemptions) == 1
            and getattr(selected_redemptions[0], 'status', 'PENDING') == 'PENDING_CANCEL'
        )

        self.edit_btn.setVisible(len(selected_rows) == 1 and not single_canceled and not single_pending_cancel)
        self.delete_btn.setVisible(len(selected_rows) > 0)
        # Bulk actions: only for PENDING rows
        pending_count = sum(
            1 for r in selected_redemptions
            if getattr(r, 'status', 'PENDING') == 'PENDING'
        )
        self.mark_received_btn.setVisible(pending_count > 0)
        self.mark_processed_btn.setVisible(pending_count > 0)

        # Cancel / Uncancel (Issue #148)
        self.cancel_btn.setVisible(single_cancellable)
        self.uncancel_btn.setVisible(single_canceled)

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
    
    def _get_selected_redemption_id(self):
        """Get ID of selected redemption"""
        ids = self._get_selected_redemption_ids()
        return ids[0] if ids else None

    def _get_selected_redemption_ids(self):
        ids = []
        for row in self._get_selected_row_numbers():
            item = self.table.item(row, 0)
            if item is not None:
                value = item.data(QtCore.Qt.UserRole)
                if value is not None:
                    ids.append(value)
        return ids

    def _get_redemption_for_row(self, row: int):
        """Return the Redemption model for a table row, looked up from self.redemptions."""
        item = self.table.item(row, 0)
        if item is None:
            return None
        rid = item.data(QtCore.Qt.UserRole)
        if rid is None:
            return None
        for r in self.redemptions:
            if r.id == rid:
                return r
        return None
    
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
                amount = dialog.get_amount()
                
                # Note: Business validation (amount, sessions, balance) is handled in
                # RedemptionDialog._validate_and_accept() before the dialog closes.
                # If we reach this point, all validation has passed.

                # Calculate expected balance for partial/full confirmation
                expected_total, expected_redeemable = self.facade.compute_expected_balances(
                    dialog.user_id,
                    dialog.site_id,
                    redemption_date,
                    redemption_time
                )
                site = self.facade.get_site(dialog.site_id)
                sc_rate = Decimal(str(site.sc_rate if site else 1.0))
                expected_total_balance = (expected_total or Decimal("0.00")) * sc_rate
                expected_redeemable_balance = (expected_redeemable or Decimal("0.00")) * sc_rate

                if not self._confirm_partial_vs_balance(
                    amount,
                    expected_total_balance,
                    expected_redeemable_balance,
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
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()

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
        if getattr(redemption, 'status', 'PENDING') != 'PENDING':
            QtWidgets.QMessageBox.information(
                self,
                "Edit Locked",
                "Only PENDING redemptions can be edited.",
            )
            return

        dialog = RedemptionDialog(self.facade, self, redemption)
        if dialog.exec():
            try:
                # Determine if this is a metadata-only edit (receipt_date, processed flag, notes)
                # Metadata-only edits don't require balance validation or FIFO reprocessing
                
                # Normalize redemption_time for comparison (None and "00:00:00" are equivalent)
                old_time = redemption.redemption_time or "00:00:00"
                new_time = dialog.get_time() or "00:00:00"
                
                # Debug logging to diagnose field change detection
                import logging
                logger = logging.getLogger(__name__)
                logger.info("=== Redemption Edit Debug ===")
                logger.info(f"Old redemption: id={redemption.id}")
                logger.info(f"  user_id: {redemption.user_id} -> {dialog.user_id} (changed: {redemption.user_id != dialog.user_id})")
                logger.info(f"  site_id: {redemption.site_id} -> {dialog.site_id} (changed: {redemption.site_id != dialog.site_id})")
                logger.info(f"  amount: {redemption.amount} -> {dialog.get_amount()} (changed: {redemption.amount != dialog.get_amount()})")
                logger.info(f"  redemption_date: {redemption.redemption_date} -> {dialog.get_date()} (changed: {redemption.redemption_date != dialog.get_date()})")
                logger.info(f"  redemption_time: {old_time} -> {new_time} (changed: {old_time != new_time})")
                logger.info(f"  more_remaining: {redemption.more_remaining} -> {dialog.is_partial_selected()} (changed: {redemption.more_remaining != dialog.is_partial_selected()})")
                logger.info(f"  fees: {redemption.fees} -> {dialog.get_fees()} (changed: {redemption.fees != dialog.get_fees()})")
                logger.info(f"  redemption_method_id: {redemption.redemption_method_id} -> {dialog.method_id} (changed: {redemption.redemption_method_id != dialog.method_id})")
                logger.info(f"  receipt_date: {redemption.receipt_date} -> {dialog.get_receipt_date()} (changed: {redemption.receipt_date != dialog.get_receipt_date()})")
                logger.info(f"  processed: {redemption.processed} -> {dialog.processed_check.isChecked()} (changed: {redemption.processed != dialog.processed_check.isChecked()})")
                logger.info(f"  notes: {redemption.notes} -> {dialog.notes_edit.toPlainText() or None}")
                
                entry_tz_override = None
                original_tz = redemption.redemption_entry_time_zone or get_accounting_timezone_name()
                current_tz = get_entry_timezone_name() or get_accounting_timezone_name()
                if current_tz != original_tz:
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "Update Entry Time Zone?",
                        f"This redemption was originally entered in {original_tz}.\n"
                        f"Current entry mode is {current_tz}.\n\n"
                        "Update the entry time zone to current?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
                        QtWidgets.QMessageBox.No,
                    )
                    if reply == QtWidgets.QMessageBox.Cancel:
                        return
                    if reply == QtWidgets.QMessageBox.Yes:
                        entry_tz_override = current_tz
                accounting_fields_changed = (
                    redemption.user_id != dialog.user_id or
                    redemption.site_id != dialog.site_id or
                    redemption.amount != dialog.get_amount() or
                    redemption.redemption_date != dialog.get_date() or
                    old_time != new_time or
                    redemption.more_remaining != dialog.is_partial_selected() or
                    redemption.fees != dialog.get_fees() or
                    redemption.redemption_method_id != dialog.method_id or
                    entry_tz_override is not None
                )
                
                logger.info(f"accounting_fields_changed: {accounting_fields_changed}")
                logger.info("===========================")
                
                if accounting_fields_changed:
                    # Accounting fields changed - use full reprocess path with validation
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
                    expected_total_balance = (expected_total or Decimal("0.00")) * sc_rate
                    expected_redeemable_balance = (expected_redeemable or Decimal("0.00")) * sc_rate
                    amount = dialog.get_amount()

                    if not self._confirm_partial_vs_balance(
                        amount,
                        expected_total_balance,
                        expected_redeemable_balance,
                        dialog.is_partial_selected(),
                    ):
                        return

                    update_kwargs = {
                        "user_id": dialog.user_id,
                        "site_id": dialog.site_id,
                        "amount": amount,
                        "fees": dialog.get_fees(),
                        "redemption_date": redemption_date,
                        "redemption_method_id": dialog.method_id,
                        "redemption_time": redemption_time,
                        "receipt_date": dialog.get_receipt_date(),
                        "processed": dialog.processed_check.isChecked(),
                        "more_remaining": dialog.is_partial_selected(),
                        "notes": dialog.notes_edit.toPlainText() or None,
                    }
                    if entry_tz_override:
                        update_kwargs["redemption_entry_time_zone"] = entry_tz_override

                    self.facade.update_redemption_reprocess(
                        redemption_id,
                        **update_kwargs,
                    )
                else:
                    # Metadata-only edit - use lightweight update path (no validation, no rebuild)
                    update_kwargs = {
                        "receipt_date": dialog.get_receipt_date(),
                        "processed": dialog.processed_check.isChecked(),
                        "notes": dialog.notes_edit.toPlainText() or None,
                    }
                    if entry_tz_override:
                        update_kwargs["redemption_entry_time_zone"] = entry_tz_override
                    self.facade.update_redemption(redemption_id, **update_kwargs)
                
                self.refresh_data()
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption updated"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to update redemption:\n{str(e)}"
                )

    def _confirm_partial_vs_balance(
        self,
        amount: Decimal,
        expected_total_balance: Decimal,
        expected_redeemable_balance: Decimal,
        is_partial: bool,
    ) -> bool:
        decision = classify_redemption_confirmation(
            amount=amount,
            expected_total_balance=expected_total_balance,
            expected_redeemable_balance=expected_redeemable_balance,
            is_partial=is_partial,
        )

        if decision == "warn_full_selected_but_balance_remaining":
            reply = QtWidgets.QMessageBox.question(
                self,
                "Balance Remaining",
                "This redemption is below the expected TOTAL balance for this site/user.\n\n"
                f"Expected total balance: ${float(expected_total_balance):,.2f}\n"
                f"Redemption amount: ${float(amount):,.2f}\n\n"
                "It looks like a partial cashout (balance remains). Continue as Full?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            return reply == QtWidgets.QMessageBox.Yes

        if decision == "warn_partial_selected_but_looks_like_full_cashout":
            reply = QtWidgets.QMessageBox.question(
                self,
                "Likely Full Cashout",
                "This redemption is at or above the expected TOTAL balance.\n\n"
                f"Expected total balance: ${float(expected_total_balance):,.2f}\n"
                f"Redemption amount: ${float(amount):,.2f}\n\n"
                "It looks like a full cashout. Continue as Partial?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            return reply == QtWidgets.QMessageBox.Yes

        if decision == "info_redeems_all_redeemable_but_balance_remains":
            QtWidgets.QMessageBox.information(
                self,
                "Redeems All Redeemable",
                "This redemption matches (or slightly exceeds) the expected REDEEMABLE balance,\n"
                "but is below the expected TOTAL balance.\n\n"
                f"Expected redeemable: ${float(expected_redeemable_balance):,.2f}\n"
                f"Expected total: ${float(expected_total_balance):,.2f}\n"
                f"Redemption amount: ${float(amount):,.2f}\n\n"
                "This is a valid PARTIAL redemption (non-redeemable balance remains).",
            )
            return True

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

        # For bulk operations (3+), show concise warning
        # For smaller operations, show detailed impact
        is_bulk = len(redemptions) >= 3
        
        if is_bulk:
            # Get summary info for bulk delete
            affected_pairs = set()
            total_amount = sum(float(r.amount) for r in redemptions)
            
            for redemption in redemptions:
                affected_pairs.add((redemption.site_id, redemption.user_id))
            
            msg = f"⚠️ BULK DELETE WARNING ⚠️\n\n"
            msg += f"You are about to delete {len(redemptions)} redemption(s):\n"
            msg += f"• Total amount: ${total_amount:,.2f}\n"
            msg += f"• Affecting {len(affected_pairs)} user/site pair(s)\n\n"
            msg += "This will:\n"
            msg += "• Reverse FIFO allocations for these redemptions\n"
            msg += "• Trigger recalculation for affected pairs\n"
            msg += "• Recalculate game session balances\n\n"
            msg += "Consider using Tools > Recalculate for data fixes instead.\n\n"
            msg += "Are you sure you want to proceed?"
        else:
            # Check detailed impact for small deletes (using service layer)
            warning_messages = []
            for redemption in redemptions:
                impact = self.facade.redemption_service.get_deletion_impact(redemption.id)
                if impact:
                    warning_messages.append(impact)
            
            if len(redemptions) == 1:
                redemption = redemptions[0]
                msg = f"Delete redemption of ${float(redemption.amount):.2f} on {redemption.redemption_date}?\n\n"
            else:
                msg = f"Delete {len(redemptions)} redemptions?\n\n"
            
            msg += "This will:\n"
            msg += "• Reverse FIFO allocations\n"
            msg += "• Trigger recalculation for affected pairs\n"
            msg += "• Recalculate game session balances\n"
            
            if warning_messages:
                msg += "\n\n⚠️ DELETION IMPACT:\n\n" + "\n\n".join(warning_messages)

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # Use bulk delete for better performance
                if hasattr(self.facade, 'delete_redemptions_bulk'):
                    self.facade.delete_redemptions_bulk(redemption_ids)
                else:
                    # Fallback to individual deletes if bulk method not available
                    for redemption_id in redemption_ids:
                        self.facade.delete_redemption(redemption_id)
                self.refresh_data()
                if hasattr(self, "main_window") and self.main_window is not None:
                    self.main_window.refresh_all_tabs()
                QtWidgets.QMessageBox.information(
                    self, "Success", "Redemption(s) deleted"
                )
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                QtWidgets.QMessageBox.warning(
                    self, "Error", f"Failed to delete redemption(s):\n{str(e)}\n\n{error_detail}"
                )
    
    def _cancel_redemption(self):
        """Cancel the selected PENDING redemption."""
        redemption_id = self._get_selected_redemption_id()
        if not redemption_id:
            return
        redemption = next((r for r in self.redemptions if r.id == redemption_id), None)
        if not redemption:
            return

        # Check for active session
        has_active = (
            self.facade.game_session_service.get_active_session(
                redemption.user_id, redemption.site_id
            ) is not None
        )

        if has_active:
            site_label = getattr(redemption, 'site_name', None) or f"site #{redemption.site_id}"
            confirm_msg = (
                f"An active session is in progress for {site_label}.\n"
                "This cancellation will be queued and will complete automatically "
                "when the session ends.\n\nProceed?"
            )
            reply = QtWidgets.QMessageBox.question(
                self, "Queue Cancellation", confirm_msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

        reason, ok = QtWidgets.QInputDialog.getText(
            self, "Cancel Reason",
            "Enter a reason for cancellation (optional):"
        )
        if not ok:
            return

        try:
            self.facade.cancel_redemption(redemption_id, reason=reason)
            self.refresh_data()
            if hasattr(self, "main_window") and self.main_window is not None:
                self.main_window.refresh_all_tabs()
            if has_active:
                QtWidgets.QMessageBox.information(
                    self, "Cancellation Queued",
                    "Cancellation queued. It will complete when the active session ends."
                )
            else:
                QtWidgets.QMessageBox.information(
                    self, "Canceled",
                    f"Redemption #{redemption_id} canceled successfully."
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to cancel redemption:\n{str(e)}"
            )

    def _uncancel_redemption(self):
        """Restore a CANCELED redemption back to PENDING."""
        redemption_id = self._get_selected_redemption_id()
        if not redemption_id:
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Uncancel Redemption",
            f"Uncancel redemption #{redemption_id}?\n\n"
            "This will re-apply FIFO allocations and restore it to PENDING status.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            self.facade.uncancel_redemption(redemption_id)
            self.refresh_data()
            if hasattr(self, "main_window") and self.main_window is not None:
                self.main_window.refresh_all_tabs()
            QtWidgets.QMessageBox.information(
                self, "Uncanceled",
                f"Redemption #{redemption_id} restored to PENDING."
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Error", f"Failed to uncancel redemption:\n{str(e)}"
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
        self.pending_filter_check.setChecked(False)
        self.unprocessed_filter_check.setChecked(False)
        self.table.clearSelection()
        self._on_selection_changed()
        self.refresh_data()
        if hasattr(self, "table_filter"):
            self.table_filter.clear_all_filters()

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

    def _mark_received(self):
        """Open Mark Received dialog and bulk-set receipt_date for selected rows."""
        ids = self._get_selected_redemption_ids()
        if not ids:
            return

        dialog = MarkReceivedDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        receipt_date = dialog.get_receipt_date()
        # receipt_date may be None (Clear was used)
        count = len(ids)
        try:
            self.facade.bulk_update_redemption_metadata(ids, receipt_date=receipt_date)
            self.refresh_data()
            self.table.clearSelection()
            self._on_selection_changed()
            if hasattr(self, "main_window") and self.main_window is not None:
                # Refresh notification bell after dismissals
                if hasattr(self.main_window, "_refresh_notification_badge"):
                    self.main_window._refresh_notification_badge()
            if receipt_date is not None:
                msg = (
                    f"Receipt date set to {receipt_date.strftime('%m/%d/%y')} "
                    f"for {count} redemption(s)."
                )
            else:
                msg = f"Receipt date cleared for {count} redemption(s)."
            QtWidgets.QMessageBox.information(self, "Mark Received", msg)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to update:\n{str(e)}")

    def _mark_processed(self):
        """Bulk-set processed=True for all selected rows."""
        ids = self._get_selected_redemption_ids()
        if not ids:
            return

        count = len(ids)
        try:
            self.facade.bulk_update_redemption_metadata(ids, processed=True)
            self.refresh_data()
            self.table.clearSelection()
            self._on_selection_changed()
            QtWidgets.QMessageBox.information(
                self, "Mark Processed",
                f"{count} redemption(s) marked as processed."
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to update:\n{str(e)}")

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
        self.setMinimumHeight(560)
        self.resize(850, 560)

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
        self.time_edit.setPlaceholderText("HH:MM:SS")
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
        self.datetime_section = QtWidgets.QWidget()
        self.datetime_section.setObjectName("SectionBackground")
        datetime_section_layout = QtWidgets.QVBoxLayout(self.datetime_section)
        datetime_section_layout.setContentsMargins(12, 10, 12, 10)
        datetime_section_layout.setSpacing(8)
        
        datetime_row = QtWidgets.QHBoxLayout()
        datetime_row.setSpacing(12)
        
        date_label = QtWidgets.QLabel("Date:")
        date_label.setObjectName("FieldLabel")
        datetime_row.addWidget(date_label)
        
        # Date field with embedded calendar button
        date_container = QtWidgets.QWidget()
        date_layout = QtWidgets.QHBoxLayout(date_container)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.setSpacing(4)
        self.date_edit.setFixedWidth(110)
        date_layout.addWidget(self.date_edit)
        date_layout.addWidget(self.calendar_btn)
        datetime_row.addWidget(date_container)
        
        datetime_row.addWidget(self.today_btn)
        datetime_row.addSpacing(30)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("FieldLabel")
        datetime_row.addWidget(time_label)
        
        self.time_edit.setFixedWidth(90)
        datetime_row.addWidget(self.time_edit)
        datetime_row.addWidget(self.now_btn)
        datetime_row.addStretch(1)
        
        datetime_section_layout.addLayout(datetime_row)
        
        # Timestamp adjustment info banner (hidden by default, styled like balance check)
        self.timestamp_info_label = QtWidgets.QLabel()
        self.timestamp_info_label.setObjectName("HelperText")
        self.timestamp_info_label.setProperty("status", "info")
        self.timestamp_info_label.setWordWrap(True)
        self.timestamp_info_label.setVisible(False)
        datetime_section_layout.addWidget(self.timestamp_info_label)

        
        form.addWidget(self.datetime_section)

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
        self.user_combo.currentTextChanged.connect(self._update_timestamp_info)
        self.site_combo.currentTextChanged.connect(self._update_timestamp_info)
        self.date_edit.textChanged.connect(self._update_timestamp_info)
        self.time_edit.textChanged.connect(self._update_timestamp_info)

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
        self._update_timestamp_info()
    
    def _toggle_notes(self):
        """Toggle notes section visibility"""
        self.notes_collapsed = not self.notes_collapsed
        self.notes_section.setVisible(not self.notes_collapsed)
        if self.notes_collapsed:
            self.notes_toggle.setText("📝 Add Notes...")
            self.setMinimumHeight(560)
            self.setMaximumHeight(560)
            self.resize(self.width(), 560)
        else:
            self.notes_toggle.setText("📝 Notes ▼")
            self.setMinimumHeight(690)
            self.setMaximumHeight(16777215)
            self.resize(self.width(), 690)
    
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
                receipt_date = parse_date_input(receipt_text)
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
        
        # Method types are global - get them directly from the service
        all_method_types = self.facade.get_all_redemption_method_types(active_only=True)
        method_type_names = sorted([mt.name for mt in all_method_types if mt.name])

        self.method_type_combo.blockSignals(True)
        self.method_type_combo.clear()
        self.method_type_combo.addItems(method_type_names)
        if self.user_id is None:
            self.method_type_combo.lineEdit().setPlaceholderText("Select a user first")
        else:
            self.method_type_combo.lineEdit().setPlaceholderText("")

        if preserve and current and current in method_type_names:
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
        """Set time to current time with seconds precision."""
        current_time = current_time_with_seconds()
        self.time_edit.setText(format_time_display(current_time))

    def get_date(self) -> date:
        date_str = self.date_edit.text().strip()
        parsed = parse_date_input(date_str) if date_str else None
        return parsed if parsed else date.today()

    def get_time(self) -> Optional[str]:
        """
        Parse time input and return database string with seconds precision.
        
        Rules (Issue #90):
        - Empty → current time with seconds
        - HH:MM → append :00
        - HH:MM:SS → preserve
        """
        time_str = self.time_edit.text().strip()
        
        if not time_str:
            # Blank time → current time with seconds
            return time_to_db_string(current_time_with_seconds())
        
        # Parse user input (handles both HH:MM and HH:MM:SS)
        parsed_time = parse_time_input(time_str)
        if parsed_time is None:
            # Invalid format → fallback to current time
            return time_to_db_string(current_time_with_seconds())
        
        return time_to_db_string(parsed_time)

    def get_receipt_date(self) -> Optional[date]:
        receipt_str = self.receipt_edit.text().strip()
        if not receipt_str:
            return None
        return parse_date_input(receipt_str)

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

        # Business validations - check session requirements and unsessioned SC
        amount = self.get_amount()
        redemption_date = self.get_date()
        redemption_time = self.get_time() or "00:00:00"
        
        # Block manual $0 redemptions - these should only come from "Close Position"
        if amount == Decimal("0.00"):
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Redemption Amount",
                "Cannot manually create a $0 redemption.\n\n"
                "To document a total loss:\n"
                "1. Go to the Unrealized tab\n"
                "2. Select the site/user position\n"
                "3. Click 'Close Position'\n\n"
                "This ensures proper accounting cleanup and marks purchases as dormant."
            )
            return
        
        # Validate real redemptions require game sessions
        if amount > Decimal("0.00"):
            # IMPORTANT: Get the ADJUSTED timestamp that will actually be used
            # The timestamp service may auto-increment the time if there's a conflict
            adjusted_date_str, adjusted_time_str, _ = self.facade.timestamp_service.ensure_unique_timestamp(
                user_id=self.user_id,
                site_id=self.site_id,
                date_val=redemption_date,
                time_str=redemption_time,
                exclude_id=self.redemption.id if self.redemption else None,
                event_type="redemption"
            )
            
            # Convert adjusted date string back to date object if needed
            if isinstance(adjusted_date_str, str):
                from datetime import datetime as dt_module
                adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
            else:
                adjusted_date = adjusted_date_str

            # Check if there's at least one CLOSED session for this site/user
            # using the ADJUSTED timestamp (stored as UTC in DB)
            from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc
            tz_name = get_configured_timezone_name()
            utc_date_str, utc_time_str = local_date_time_to_utc(adjusted_date, adjusted_time_str, tz_name)

            db = self.facade.game_session_repo.db
            cursor = db._connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) as session_count
                FROM game_sessions
                WHERE site_id = ? AND user_id = ?
                  AND status = 'Closed'
                  AND end_date IS NOT NULL
                  AND (end_date < ? OR (end_date = ? AND end_time <= ?))
            """, (self.site_id, self.user_id, utc_date_str, utc_date_str, utc_time_str))
            result = cursor.fetchone()
            has_closed_sessions = result["session_count"] > 0 if result else False
            
            if not has_closed_sessions:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Redemption Requires Session",
                    "No game sessions have been recorded for this site and user.\n\n"
                    f"Redemption amount: ${float(amount):,.2f}\n\n"
                    "What this means:\n"
                    "• We only allow redemptions against balances that were recorded in Game Sessions.\n"
                    "• You must record at least one game session before redeeming.\n\n"
                    "What to do:\n"
                    "1) Create a Game Session for this site/user showing your balance.\n"
                    "2) Close the session to establish a verified balance.\n"
                    "3) Then try the redemption again.\n\n"
                    "If this was a bonus or freeplay, record it in a Game Session first."
                )
                return
            
            # Check if redemption exceeds verified balance
            # SKIP THIS CHECK if we're editing and accounting fields haven't changed
            skip_balance_check = False
            if self.redemption:  # Editing mode
                # Check if accounting fields are unchanged
                amount_unchanged = self.redemption.amount == amount
                user_unchanged = self.redemption.user_id == self.user_id
                site_unchanged = self.redemption.site_id == self.site_id
                date_unchanged = self.redemption.redemption_date == redemption_date
                time_unchanged = (self.redemption.redemption_time or "00:00:00") == redemption_time
                
                skip_balance_check = (amount_unchanged and user_unchanged and 
                                     site_unchanged and date_unchanged and time_unchanged)
            
            if not skip_balance_check:
                expected_total, expected_redeemable = self.facade.compute_expected_balances(
                    self.user_id,
                    self.site_id,
                    adjusted_date,
                    adjusted_time_str
                )
                site = self.facade.get_site(self.site_id)
                sc_rate = Decimal(str(site.sc_rate if site else 1.0))
                expected_redeemable_balance = (expected_redeemable or Decimal("0.00")) * sc_rate
                
                if amount > expected_redeemable_balance:
                    unsessioned_amount = amount - expected_redeemable_balance
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Redemption Exceeds Session Balance",
                        "This redemption exceeds the balance we can verify from recorded sessions.\n\n"
                        f"Redemption amount: ${float(amount):,.2f}\n"
                        f"Expected redeemable balance: ${float(expected_redeemable_balance):,.2f}\n"
                        f"Unsessioned amount: ${float(unsessioned_amount):,.2f}\n\n"
                        "What this means:\n"
                        "• Your redemption is higher than the verified balance from game sessions.\n"
                        "• This helps keep your session-based totals accurate.\n\n"
                        "What to do:\n"
                        "1) Create/close a Game Session showing your current balance.\n"
                        "2) Then try the redemption again.\n\n"
                        "If this was a bonus or freeplay not captured in sessions, record it in a Game Session first."
                    )
                    return

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
                time_str = time_str
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


    def _update_timestamp_info(self):
        """Check for timestamp conflicts and show info banner if adjustment needed"""
        from datetime import datetime
        
        site_text = self.site_combo.currentText().strip()
        user_text = self.user_combo.currentText().strip()
        date_text = self.date_edit.text().strip()
        time_text = self.time_edit.text().strip()

        # Hide banner if we don't have all required fields
        if not site_text or not user_text or not date_text:
            self.timestamp_info_label.setVisible(False)
            return

        # Validate lookups
        if site_text.lower() not in self._site_lookup or user_text.lower() not in self._user_lookup:
            self.timestamp_info_label.setVisible(False)
            return

        # Parse date
        parsed_date = None
        for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(date_text, fmt).date()
                break
            except ValueError:
                continue
        if parsed_date is None:
            self.timestamp_info_label.setVisible(False)
            return

        # Parse time (use current time if not provided)
        if time_text:
            try:
                if len(time_text) == 5:
                    datetime.strptime(time_text, "%H:%M")
                    parsed_time = f"{time_text}:00"
                elif len(time_text) == 8:
                    datetime.strptime(time_text, "%H:%M:%S")
                    parsed_time = time_text
                else:
                    self.timestamp_info_label.setVisible(False)
                    return
            except Exception:
                self.timestamp_info_label.setVisible(False)
                return
        else:
            parsed_time = datetime.now().strftime("%H:%M:%S")

        user_id = self._user_lookup[user_text.lower()]
        site_id = self._site_lookup[site_text.lower()]

        # Check for timestamp conflicts
        try:
            adjusted_date_str, adjusted_time_str, will_adjust = self.facade.timestamp_service.ensure_unique_timestamp(
                user_id=user_id,
                site_id=site_id,
                date_val=parsed_date,
                time_str=parsed_time,
                exclude_id=self.redemption.id if self.redemption else None,
                event_type="redemption"
            )
            
            if will_adjust:
                banner_text = f"ℹ️ Time will be adjusted to {adjusted_time_str} ({parsed_time} already in use)"
                self.timestamp_info_label.setText(banner_text)
                was_visible = self.timestamp_info_label.isVisible()
                self.timestamp_info_label.setVisible(True)
                # Expand dialog slightly when banner first appears (just enough for the banner)
                if not was_visible:
                    self.timestamp_info_label.updateGeometry()
                    self.datetime_section.updateGeometry()
            else:
                self.timestamp_info_label.setVisible(False)
        except Exception as e:
            # Silently hide banner on error
            self.timestamp_info_label.setVisible(False)


class RedemptionViewDialog(QtWidgets.QDialog):
    """Modern redemption view dialog with streamlined sectioned layout"""

    def __init__(self, redemption: Redemption, facade: AppFacade, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.redemption = redemption
        self.facade = facade
        self._on_edit = on_edit
        self._on_delete = on_delete

        self.adjustments = []
        self.period_adjustments = []
        self.period_boundary_checkpoints = []
        self.period_window_start = None
        self.period_window_end = None
        if getattr(self.redemption, "id", None):
            try:
                self.adjustments = self.facade.adjustment_service.get_by_related(
                    "redemptions", int(self.redemption.id), include_deleted=False
                )
            except Exception:
                self.adjustments = []

        try:
            anchor_time = getattr(self.redemption, "redemption_time", None) or "23:59:59"
            self.period_window_start, self.period_window_end = self.facade.adjustment_service.get_checkpoint_window_for_timestamp(
                user_id=int(self.redemption.user_id),
                site_id=int(self.redemption.site_id),
                anchor_date=self.redemption.redemption_date,
                anchor_time=anchor_time,
            )

            prev_full, _next_full = self.facade.get_full_redemption_window_for_timestamp(
                user_id=int(self.redemption.user_id),
                site_id=int(self.redemption.site_id),
                anchor_date=self.redemption.redemption_date,
                anchor_time=anchor_time,
            )

            start_bound_dt = None
            if self.period_window_start is not None:
                start_cp_time = getattr(self.period_window_start, "effective_time", None) or "00:00:00"
                start_bound_dt = self.facade._to_dt(self.period_window_start.effective_date, start_cp_time)
            if prev_full is not None:
                prev_full_dt = self.facade._to_dt(prev_full[0], prev_full[1])
                if start_bound_dt is None or prev_full_dt > start_bound_dt:
                    start_bound_dt = prev_full_dt

            end_bound_dt = self.facade._to_dt(self.redemption.redemption_date, anchor_time)

            start_date = start_bound_dt.date() if start_bound_dt else None
            start_time = start_bound_dt.strftime("%H:%M:%S") if start_bound_dt else "00:00:00"
            end_date = end_bound_dt.date()
            end_time = end_bound_dt.strftime("%H:%M:%S")

            raw_period = self.facade.adjustment_service.get_active_adjustments_in_window(
                user_id=int(self.redemption.user_id),
                site_id=int(self.redemption.site_id),
                start_date=start_date,
                start_time=start_time,
                end_date=end_date,
                end_time=end_time,
            )

            self.period_boundary_checkpoints = []
            if self.period_window_start is not None and start_bound_dt is not None:
                start_cp_time = getattr(self.period_window_start, "effective_time", None) or "00:00:00"
                start_cp_dt = self.facade._to_dt(self.period_window_start.effective_date, start_cp_time)
                if start_cp_dt >= start_bound_dt and start_cp_dt <= end_bound_dt:
                    self.period_boundary_checkpoints.append(self.period_window_start)

            anchor_ids = {int(a.id) for a in self.period_boundary_checkpoints if getattr(a, "id", None)}
            self.period_adjustments = [a for a in raw_period if getattr(a, "id", None) not in anchor_ids]
        except Exception:
            self.period_adjustments = []
            self.period_boundary_checkpoints = []
            self.period_window_start = None
            self.period_window_end = None

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

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SetupSubTabs")
        self.tabs.addTab(self._create_details_tab(user_name, site_name, method_name, method_type), "Details")
        self.tabs.addTab(self._create_related_tab(), "Related")
        if self.adjustments or self.period_adjustments or self.period_boundary_checkpoints:
            self.tabs.addTab(self._create_adjustments_tab(), "Adjustments")
        layout.addWidget(self.tabs, 1)

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
            """Format time for display with full HH:MM:SS precision (Issue #90)"""
            return value if value else "—"
        
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
        date_label.setObjectName("MutedLabel")
        when_grid.addWidget(date_label, 0, 0)
        when_grid.addWidget(make_selectable_label(format_date(self.redemption.redemption_date)), 0, 1)
        
        time_label = QtWidgets.QLabel("Time:")
        time_label.setObjectName("MutedLabel")
        when_grid.addWidget(time_label, 1, 0)
        
        # Time with travel mode badge
        time_container = QtWidgets.QWidget()
        time_layout = QtWidgets.QHBoxLayout(time_container)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(4)
        time_layout.addWidget(make_selectable_label(format_time(self.redemption.redemption_time)))
        
        entry_tz = getattr(self.redemption, "redemption_entry_time_zone", None)
        accounting_tz = get_accounting_timezone_name()
        if entry_tz and entry_tz != accounting_tz:
            globe_label = QtWidgets.QLabel("🌐")
            globe_label.setToolTip(f"Entered in travel mode ({entry_tz}). Accounting TZ: {accounting_tz}.")
            time_layout.addWidget(globe_label)
        
        time_layout.addStretch()
        when_grid.addWidget(time_container, 1, 1)
        
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
        user_label.setObjectName("MutedLabel")
        details_grid.addWidget(user_label, 0, 0)
        details_grid.addWidget(make_selectable_label(user_name or "—"), 0, 1)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("MutedLabel")
        details_grid.addWidget(site_label, 1, 0)
        details_grid.addWidget(make_selectable_label(site_name or "—"), 1, 1)
        
        method_type_label = QtWidgets.QLabel("Method Type:")
        method_type_label.setObjectName("MutedLabel")
        details_grid.addWidget(method_type_label, 2, 0)
        details_grid.addWidget(make_selectable_label(method_type or "—"), 2, 1)
        
        method_label = QtWidgets.QLabel("Method:")
        method_label.setObjectName("MutedLabel")
        details_grid.addWidget(method_label, 3, 0)
        details_grid.addWidget(make_selectable_label(method_name or "—"), 3, 1)
        
        amount_label = QtWidgets.QLabel("Amount:")
        amount_label.setObjectName("MutedLabel")
        details_grid.addWidget(amount_label, 4, 0)
        details_grid.addWidget(make_selectable_label(f"${float(self.redemption.amount):.2f}"), 4, 1)
        
        fees_label = QtWidgets.QLabel("Fees:")
        fees_label.setObjectName("MutedLabel")
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
        redemption_type_label.setObjectName("MutedLabel")
        processing_grid.addWidget(redemption_type_label, 0, 0)
        type_text = "Partial" if self.redemption.more_remaining else "Full"
        processing_grid.addWidget(make_selectable_label(type_text), 0, 1)
        
        receipt_label = QtWidgets.QLabel("Receipt Date:")
        receipt_label.setObjectName("MutedLabel")
        processing_grid.addWidget(receipt_label, 1, 0)
        receipt_text = format_date(self.redemption.receipt_date) if self.redemption.receipt_date else "—"
        processing_grid.addWidget(make_selectable_label(receipt_text), 1, 1)
        
        processed_label = QtWidgets.QLabel("Processed:")
        processed_label.setObjectName("MutedLabel")
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
            notes_empty.setObjectName("MutedLabel")
            notes_font = notes_empty.font()
            notes_font.setItalic(True)
            notes_empty.setFont(notes_font)
            notes_layout.addWidget(notes_empty)
        
        layout.addWidget(notes_section)

        if self.adjustments or self.period_adjustments or self.period_boundary_checkpoints:
            adj_section, adj_layout = create_section("🧩 Adjustments & Checkpoints")
            total = len(self.period_adjustments) + len(self.period_boundary_checkpoints) + len(self.adjustments)
            summary = QtWidgets.QLabel(
                f"This redemption has {total} adjustment(s)/checkpoint(s) available for review."
            )
            summary.setWordWrap(True)
            summary.setObjectName("HelperText")
            adj_layout.addWidget(summary)
            btn_row = QtWidgets.QHBoxLayout()
            btn_row.addStretch(1)
            open_btn = QtWidgets.QPushButton("👁️ View Adjustments")
            open_btn.clicked.connect(self._open_adjustments_tab)
            btn_row.addWidget(open_btn)
            adj_layout.addLayout(btn_row)
            layout.addWidget(adj_section)

        layout.addStretch(1)
        return widget

    def _create_adjustments_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        def _make_table() -> QtWidgets.QTableWidget:
            table = QtWidgets.QTableWidget(0, 5)
            table.setHorizontalHeaderLabels(["Effective", "Type", "Delta/Total SC", "Redeemable SC", "View"])
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(44)

            header = table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
            table.setColumnWidth(4, 170)
            return table

        def _populate_table(table: QtWidgets.QTableWidget, adjustments_list: list) -> None:
            adjustments_sorted = sorted(
                adjustments_list,
                key=lambda a: (str(a.effective_date), str(a.effective_time or "00:00:00"), int(a.id or 0)),
                reverse=True,
            )
            table.setRowCount(len(adjustments_sorted))
            for row_idx, adj in enumerate(adjustments_sorted):
                effective = f"{adj.effective_date} {adj.effective_time or '00:00:00'}"
                type_str = "Basis" if adj.type.value == "BASIS_USD_CORRECTION" else "Checkpoint"
                if adj.type.value == "BASIS_USD_CORRECTION":
                    delta_total_str = f"${adj.delta_basis_usd:,.2f}"
                    redeemable_str = ""
                else:
                    delta_total_str = f"{adj.checkpoint_total_sc:,.2f}"
                    redeemable_str = f"{adj.checkpoint_redeemable_sc:,.2f}"

                table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(effective))
                table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(type_str))
                delta_item = QtWidgets.QTableWidgetItem(delta_total_str)
                delta_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row_idx, 2, delta_item)
                redeem_item = QtWidgets.QTableWidgetItem(redeemable_str)
                redeem_item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                table.setItem(row_idx, 3, redeem_item)

                view_btn = QtWidgets.QPushButton("👁️ View Adjustment")
                view_btn.setObjectName("MiniButton")
                view_btn.setFixedHeight(24)
                view_btn.setFixedWidth(150)
                adj_id = adj.id
                view_btn.clicked.connect(lambda _checked=False, aid=adj_id: self._open_adjustment_dialog(aid))
                view_container = QtWidgets.QWidget()
                view_layout = QtWidgets.QGridLayout(view_container)
                view_layout.setContentsMargins(6, 4, 6, 4)
                view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
                table.setCellWidget(row_idx, 4, view_container)
                table.setRowHeight(
                    row_idx,
                    max(table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
                )

        period_group = QtWidgets.QGroupBox("Basis Period (Checkpoint Window)")
        period_layout = QtWidgets.QVBoxLayout(period_group)
        period_layout.setContentsMargins(8, 10, 8, 8)
        window_rows = (self.period_boundary_checkpoints or []) + (self.period_adjustments or [])
        if window_rows:
            period_table = _make_table()
            _populate_table(period_table, window_rows)
            period_layout.addWidget(period_table)
        else:
            empty = QtWidgets.QLabel("No active adjustments/checkpoints found in this checkpoint window.")
            empty.setObjectName("MutedLabel")
            period_layout.addWidget(empty)
        layout.addWidget(period_group)

        if self.adjustments:
            linked_group = QtWidgets.QGroupBox("Explicitly Linked to This Redemption")
            linked_layout = QtWidgets.QVBoxLayout(linked_group)
            linked_layout.setContentsMargins(8, 10, 8, 8)
            linked_table = _make_table()
            _populate_table(linked_table, self.adjustments)
            linked_layout.addWidget(linked_table)
            layout.addWidget(linked_group)
        layout.addStretch(1)
        return widget

    def _open_adjustments_tab(self) -> None:
        if not hasattr(self, "tabs") or self.tabs is None:
            return
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Adjustments":
                self.tabs.setCurrentIndex(i)
                return

    def _open_adjustment_dialog(self, adjustment_id: Optional[int]) -> None:
        if not adjustment_id:
            return
        dialog = ViewAdjustmentsDialog(
            self.facade,
            parent=self,
            initial_user_id=self.redemption.user_id,
            initial_site_id=self.redemption.site_id,
            preselect_adjustment_id=int(adjustment_id),
        )
        dialog.exec()
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
                    end_display = f"{session.end_date} {end_time}"
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


class MarkReceivedDialog(QtWidgets.QDialog):
    """
    Dialog for bulk-setting the Receipt Date on selected redemptions.

    Mirrors the date-picker style used in RedemptionDialog:
    - QLineEdit (MM/DD/YY) + 📅 calendar button + Today button
    - Cancel / Clear / Save buttons styled per app theme
    - Clear sets receipt_date to None (clears existing date)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mark Received — Set Receipt Date")
        self.setMinimumWidth(360)
        self._result_date: Optional[date] = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # --- Section header ---
        header = QtWidgets.QLabel("📬  Set Receipt Date")
        header.setObjectName("SectionHeader")
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(header)

        # --- Info label ---
        info = QtWidgets.QLabel(
            "Enter the date the redemption(s) were received.\n"
            "Leave blank and click Save to set today's date."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(info)

        # --- Date row ---
        date_section = QtWidgets.QWidget()
        date_section.setObjectName("SectionBackground")
        date_layout_outer = QtWidgets.QVBoxLayout(date_section)
        date_layout_outer.setContentsMargins(12, 10, 12, 10)

        date_row = QtWidgets.QHBoxLayout()
        date_row.setSpacing(6)

        date_label = QtWidgets.QLabel("Receipt Date:")
        date_label.setObjectName("FieldLabel")
        date_row.addWidget(date_label)

        self.date_edit = QtWidgets.QLineEdit()
        self.date_edit.setPlaceholderText("MM/DD/YY")
        self.date_edit.setFixedWidth(110)
        # Default to today
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))
        date_row.addWidget(self.date_edit)

        cal_btn = QtWidgets.QPushButton("📅")
        cal_btn.setFixedWidth(44)
        cal_btn.setToolTip("Open calendar picker")
        cal_btn.clicked.connect(self._pick_date)
        date_row.addWidget(cal_btn)

        today_btn = QtWidgets.QPushButton("Today")
        today_btn.clicked.connect(self._set_today)
        date_row.addWidget(today_btn)

        date_row.addStretch()
        date_layout_outer.addLayout(date_row)
        layout.addWidget(date_section)

        layout.addStretch()

        # --- Action buttons ---
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QtWidgets.QPushButton("✖️ Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        clear_btn = QtWidgets.QPushButton("🧹 Clear")
        clear_btn.setToolTip("Clear receipt date (set to blank)")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)

        save_btn = QtWidgets.QPushButton("💾 Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    def _pick_date(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Select Date")
        cal_layout = QtWidgets.QVBoxLayout(dialog)
        calendar = QtWidgets.QCalendarWidget()
        calendar.setSelectedDate(QtCore.QDate.currentDate())
        # Pre-load existing value if parseable
        existing = parse_date_input(self.date_edit.text().strip())
        if existing:
            calendar.setSelectedDate(
                QtCore.QDate(existing.year, existing.month, existing.day)
            )
        cal_layout.addWidget(calendar)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QtWidgets.QPushButton("Select")
        cancel_cal_btn = QtWidgets.QPushButton("✖️ Cancel")
        btn_row.addWidget(cancel_cal_btn)
        btn_row.addWidget(ok_btn)
        cal_layout.addLayout(btn_row)
        cancel_cal_btn.clicked.connect(dialog.reject)
        ok_btn.clicked.connect(dialog.accept)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.date_edit.setText(calendar.selectedDate().toString("MM/dd/yy"))

    def _set_today(self):
        self.date_edit.setText(date.today().strftime("%m/%d/%y"))

    def _on_save(self):
        text = self.date_edit.text().strip()
        if text:
            parsed = parse_date_input(text)
            if parsed is None:
                QtWidgets.QMessageBox.warning(
                    self, "Invalid Date",
                    f"Cannot parse date: '{text}'\nUse MM/DD/YY format."
                )
                return
            self._result_date = parsed
        else:
            # Blank field → default to today
            self._result_date = date.today()
        self.accept()

    def _on_clear(self):
        """Clear sets receipt_date = None."""
        self._result_date = None
        self.accept()

    def get_receipt_date(self) -> Optional[date]:
        """Returns the chosen date, or None if Clear was used."""
        return self._result_date

