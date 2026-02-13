"""
Realized tab - grouped realized cash flow view
"""
from PySide6 import QtWidgets, QtCore, QtGui
from decimal import Decimal
from datetime import date, datetime

from app_facade import AppFacade
from ui.adjustment_dialogs import ViewAdjustmentsDialog
from ui.date_filter_widget import DateFilterWidget
from ui.spreadsheet_ux import SpreadsheetUXController
from ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from ui.daily_sessions_filters import (
    ColumnFilterDialog,
    DateTimeFilterDialog,
    header_resize_section_index,
    header_menu_position,
)
from ui.input_parsers import parse_date_input


def format_currency(value):
    try:
        return f"${Decimal(str(value)):.2f}"
    except Exception:
        return "-"


class RealizedDateNotesDialog(QtWidgets.QDialog):
    def __init__(self, session_date: str, notes: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Notes for {session_date}")
        self.resize(520, 320)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.notes_edit = QtWidgets.QPlainTextEdit()
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


class RealizedPositionDialog(QtWidgets.QDialog):
    """Modern realized position view dialog with streamlined sectioned layout"""

    def __init__(
        self,
        position,
        allocations,
        linked_sessions,
        parent=None,
        on_open_purchase=None,
        on_open_redemption=None,
        on_open_daily_sessions=None,
        on_open_session=None,
        facade: AppFacade | None = None,
    ):
        super().__init__(parent)
        self.position = position
        self.allocations = allocations or []
        self.linked_sessions = linked_sessions or []
        self.on_open_purchase = on_open_purchase
        self.on_open_redemption = on_open_redemption
        self.on_open_daily_sessions = on_open_daily_sessions
        self.on_open_session = on_open_session
        self.facade = facade

        self.adjustments = []
        redemption_id = None
        try:
            redemption_id = int(self.position.get("redemption_id")) if self.position.get("redemption_id") else None
        except Exception:
            redemption_id = None
        if self.facade and redemption_id:
            try:
                self.adjustments = self.facade.adjustment_service.get_by_related(
                    "redemptions", redemption_id, include_deleted=False
                )
            except Exception:
                self.adjustments = []
        
        self.setWindowTitle("View Position")
        self.setMinimumWidth(700)
        self.setMinimumHeight(550)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("SetupSubTabs")
        self.tabs.addTab(self._create_details_tab(), "Details")
        self.tabs.addTab(self._create_related_tab(), "Related")
        if self.adjustments:
            self.tabs.addTab(self._create_adjustments_tab(), "Adjustments")
        layout.addWidget(self.tabs, 1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        
        if self.on_open_redemption:
            open_btn = QtWidgets.QPushButton("👁️ View in Redemptions")
            open_btn.clicked.connect(self._handle_open_redemption)
            btn_row.addWidget(open_btn)
        
        close_btn = QtWidgets.QPushButton("✖️ Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        
        layout.addLayout(btn_row)

    def _create_details_tab(self):
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
            section_layout.setContentsMargins(10, 6, 10, 8)
            section_layout.setSpacing(4)
            
            # Section header
            section_header = QtWidgets.QLabel(title_text)
            section_header.setObjectName("SectionHeader")
            section_layout.addWidget(section_header)
            
            return section_widget, section_layout

        # ========== POSITION DETAILS (Full Width, 2 Columns) ==========
        position_section, position_layout = create_section("📋 Position Details")
        position_grid = QtWidgets.QGridLayout()
        position_grid.setContentsMargins(0, 4, 0, 0)
        position_grid.setHorizontalSpacing(20)
        position_grid.setVerticalSpacing(6)
        
        # Left column
        date_label = QtWidgets.QLabel("Redemption Date:")
        date_label.setObjectName("MutedLabel")
        position_grid.addWidget(date_label, 0, 0)
        position_grid.addWidget(make_selectable_label(format_date(self.position.get("redemption_date"))), 0, 1)
        
        user_label = QtWidgets.QLabel("User:")
        user_label.setObjectName("MutedLabel")
        position_grid.addWidget(user_label, 1, 0)
        position_grid.addWidget(make_selectable_label(self.position.get("user_name") or "—"), 1, 1)
        
        # Right column
        time_label = QtWidgets.QLabel("Redemption Time:")
        time_label.setObjectName("MutedLabel")
        position_grid.addWidget(time_label, 0, 2)
        position_grid.addWidget(make_selectable_label(format_time(self.position.get("redemption_time"))), 0, 3)
        
        site_label = QtWidgets.QLabel("Site:")
        site_label.setObjectName("MutedLabel")
        position_grid.addWidget(site_label, 1, 2)
        position_grid.addWidget(make_selectable_label(self.position.get("site_name") or "—"), 1, 3)
        
        position_grid.setColumnStretch(1, 1)
        position_grid.setColumnStretch(3, 1)
        position_layout.addLayout(position_grid)
        layout.addWidget(position_section)

        # ========== TWO SUB-SECTION COLUMNS ==========
        subsections_widget = QtWidgets.QWidget()
        subsections_layout = QtWidgets.QHBoxLayout(subsections_widget)
        subsections_layout.setContentsMargins(0, 0, 0, 0)
        subsections_layout.setSpacing(12)
        subsections_layout.setAlignment(QtCore.Qt.AlignTop)
        
        # ========== LEFT SUB-SECTION: Financial Summary ==========
        financial_section, financial_layout = create_section("💰 Financial Summary")
        financial_grid = QtWidgets.QGridLayout()
        financial_grid.setContentsMargins(0, 4, 0, 0)
        financial_grid.setHorizontalSpacing(12)
        financial_grid.setVerticalSpacing(6)
        
        redemption_label = QtWidgets.QLabel("Redemption Amount:")
        redemption_label.setObjectName("MutedLabel")
        financial_grid.addWidget(redemption_label, 0, 0)
        financial_grid.addWidget(make_selectable_label(format_currency(self.position.get("redemption_amount"))), 0, 1)
        
        basis_label = QtWidgets.QLabel("Cost Basis:")
        basis_label.setObjectName("MutedLabel")
        financial_grid.addWidget(basis_label, 1, 0)
        financial_grid.addWidget(make_selectable_label(format_currency(self.position.get("cost_basis"))), 1, 1)
        
        fees_label = QtWidgets.QLabel("Fees:")
        fees_label.setObjectName("MutedLabel")
        financial_grid.addWidget(fees_label, 2, 0)
        financial_grid.addWidget(make_selectable_label(format_currency(self.position.get("fees"))), 2, 1)
        
        pl_label = QtWidgets.QLabel("Realized P/L:")
        pl_label.setObjectName("MutedLabel")
        financial_grid.addWidget(pl_label, 3, 0)
        
        # Color code P/L
        net_pl = self.position.get("net_pl")
        pl_text = self._format_signed_currency(net_pl)
        pl_color = None
        if net_pl:
            try:
                pl_val = Decimal(str(net_pl))
                if pl_val > 0:
                    pl_color = "green"
                elif pl_val < 0:
                    pl_color = "red"
            except:
                pass
        
        financial_grid.addWidget(make_selectable_label(pl_text, color=pl_color), 3, 1)
        
        financial_grid.setColumnStretch(1, 1)
        financial_layout.addLayout(financial_grid)
        financial_layout.addStretch(1)
        subsections_layout.addWidget(financial_section, 1)
        
        # ========== RIGHT SUB-SECTION: Processing Details ==========
        processing_section, processing_layout = create_section("⚙️ Processing Details")
        processing_grid = QtWidgets.QGridLayout()
        processing_grid.setContentsMargins(0, 4, 0, 0)
        processing_grid.setHorizontalSpacing(12)
        processing_grid.setVerticalSpacing(6)
        
        method_type_label = QtWidgets.QLabel("Redemption Method Type:")
        method_type_label.setObjectName("MutedLabel")
        processing_grid.addWidget(method_type_label, 0, 0)
        processing_grid.addWidget(make_selectable_label(self.position.get("method_type") or "—"), 0, 1)
        
        method_label = QtWidgets.QLabel("Redemption Method:")
        method_label.setObjectName("MutedLabel")
        processing_grid.addWidget(method_label, 1, 0)
        processing_grid.addWidget(make_selectable_label(self.position.get("method_name") or "—"), 1, 1)
        
        type_label = QtWidgets.QLabel("Redemption Type:")
        type_label.setObjectName("MutedLabel")
        processing_grid.addWidget(type_label, 2, 0)
        type_text = "Partial" if self.position.get("more_remaining") else "Full"
        processing_grid.addWidget(make_selectable_label(type_text), 2, 1)
        
        receipt_label = QtWidgets.QLabel("Receipt Date:")
        receipt_label.setObjectName("MutedLabel")
        processing_grid.addWidget(receipt_label, 3, 0)
        receipt_text = format_date(self.position.get("receipt_date")) if self.position.get("receipt_date") else "—"
        processing_grid.addWidget(make_selectable_label(receipt_text), 3, 1)
        
        processed_label = QtWidgets.QLabel("Processed:")
        processed_label.setObjectName("MutedLabel")
        processing_grid.addWidget(processed_label, 4, 0)
        processed_text = "Yes" if self.position.get("processed") else "No"
        processing_grid.addWidget(make_selectable_label(processed_text), 4, 1)
        
        processing_grid.setColumnStretch(1, 1)
        processing_layout.addLayout(processing_grid)
        processing_layout.addStretch(1)
        subsections_layout.addWidget(processing_section, 1)
        
        layout.addWidget(subsections_widget)

        # ========== NOTES SECTION (Full Width Below) ==========
        notes_section, notes_layout = create_section("📝 Notes")
        notes_value = self.position.get("redemption_notes") or ""
        
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

        if self.adjustments:
            adj_section, adj_layout = create_section("🧩 Adjustments & Checkpoints")
            summary = QtWidgets.QLabel(
                f"This realized position has {len(self.adjustments)} adjustment(s)/checkpoint(s) explicitly linked to its redemption."
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

    def _create_adjustments_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        group = QtWidgets.QGroupBox("Adjustments & Checkpoints")
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(8, 10, 8, 8)

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

        adjustments = sorted(
            self.adjustments,
            key=lambda a: (str(a.effective_date), str(a.effective_time or "00:00:00"), int(a.id or 0)),
            reverse=True,
        )
        table.setRowCount(len(adjustments))
        for row_idx, adj in enumerate(adjustments):
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

        group_layout.addWidget(table)
        layout.addWidget(group)
        layout.addStretch(1)
        return widget

    def _open_adjustments_tab(self) -> None:
        if not hasattr(self, "tabs") or self.tabs is None:
            return
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Adjustments":
                self.tabs.setCurrentIndex(i)
                return

    def _open_adjustment_dialog(self, adjustment_id: int | None) -> None:
        if not adjustment_id or not self.facade:
            return
        # Use the redemption's site/user, if present.
        dialog = ViewAdjustmentsDialog(
            self.facade,
            parent=self,
            preselect_adjustment_id=int(adjustment_id),
        )
        dialog.exec()

    def _create_related_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        cost_basis = Decimal(str(self.position.get("cost_basis") or 0))
        redemption_amt = Decimal(str(self.position.get("redemption_amount") or 0))
        unbased_portion = redemption_amt - cost_basis if cost_basis < redemption_amt else Decimal("0.00")

        summary_layout = QtWidgets.QGridLayout()
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(6)
        summary_layout.addWidget(QtWidgets.QLabel("Cost Basis:"), 0, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(cost_basis)), 0, 1)
        if unbased_portion > Decimal("0.01"):
            summary_layout.addWidget(QtWidgets.QLabel("Unbased Portion:"), 1, 0)
            summary_layout.addWidget(QtWidgets.QLabel(format_currency(unbased_portion)), 1, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Total Redemption:"), 2, 0)
        summary_layout.addWidget(QtWidgets.QLabel(format_currency(redemption_amt)), 2, 1)
        summary_layout.setColumnStretch(2, 1)
        layout.addLayout(summary_layout)
        layout.addSpacing(8)

        purchases_group = QtWidgets.QGroupBox("Allocated Purchases (FIFO)")
        purchases_layout = QtWidgets.QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(8, 10, 8, 8)
        if not self.allocations:
            note = QtWidgets.QLabel(
                "This redemption has no purchase basis. This may occur when cashing out freebies, bonuses, "
                "or winnings from partial redemptions."
            )
            note.setWordWrap(True)
            purchases_layout.addWidget(note)
        else:
            self.purchases_table = QtWidgets.QTableWidget(0, 5)
            self.purchases_table.setHorizontalHeaderLabels(
                ["Date/Time", "Amount", "SC Received", "Allocated", "View Purchase"]
            )
            self.purchases_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.purchases_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.purchases_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.purchases_table.setAlternatingRowColors(True)
            header = self.purchases_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.purchases_table.verticalHeader().setVisible(False)
            self.purchases_table.setColumnWidth(0, 150)
            self.purchases_table.setColumnWidth(1, 100)
            self.purchases_table.setColumnWidth(2, 100)
            self.purchases_table.setColumnWidth(3, 100)
            self.purchases_table.setColumnWidth(4, 120)
            purchases_layout.addWidget(self.purchases_table)
            self._populate_purchases_table()
        layout.addWidget(purchases_group, 1)

        sessions_group = QtWidgets.QGroupBox("Linked Game Sessions")
        sessions_layout = QtWidgets.QVBoxLayout(sessions_group)
        sessions_layout.setContentsMargins(8, 10, 8, 8)
        if not self.linked_sessions:
            note = QtWidgets.QLabel("No linked game sessions found.")
            note.setWordWrap(True)
            sessions_layout.addWidget(note)
        else:
            self.sessions_table = QtWidgets.QTableWidget(0, 5)
            self.sessions_table.setHorizontalHeaderLabels(
                ["Session Date/Time", "End Date/Time", "Game", "Realized P/L", "View Session"]
            )
            self.sessions_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.sessions_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.sessions_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.sessions_table.setAlternatingRowColors(True)
            header = self.sessions_table.horizontalHeader()
            header.setStretchLastSection(True)
            header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            self.sessions_table.verticalHeader().setVisible(False)
            self.sessions_table.setColumnWidth(0, 150)
            self.sessions_table.setColumnWidth(1, 140)
            self.sessions_table.setColumnWidth(2, 140)
            self.sessions_table.setColumnWidth(3, 90)
            sessions_layout.addWidget(self.sessions_table)
            self._populate_sessions_table()
        layout.addWidget(sessions_group, 1)
        return widget

    def _populate_purchases_table(self):
        self.purchases_table.setRowCount(len(self.allocations))
        for row_idx, purchase in enumerate(self.allocations):
            date_display = self._format_date(purchase.get("purchase_date")) if purchase.get("purchase_date") else "—"
            time_display = purchase.get("purchase_time", "")[:5] if purchase.get("purchase_time") else "—"
            date_time_display = f"{date_display} {time_display}" if date_display != "—" else time_display
            amount = format_currency(purchase.get("amount"))
            sc_received = f"{float(purchase.get('sc_received') or 0.0):.2f}"
            allocated = format_currency(purchase.get("allocated_amount"))

            values = [date_time_display, amount, sc_received, allocated]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col_idx in (1, 2, 3):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.purchases_table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("👁️ View Purchase")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
            view_btn.clicked.connect(
                lambda _checked=False, pid=purchase.get("purchase_id"): self._open_purchase(pid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.purchases_table.setCellWidget(row_idx, 4, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_sessions_table(self):
        self.sessions_table.setRowCount(len(self.linked_sessions))
        for row_idx, session in enumerate(self.linked_sessions):
            session_date = self._format_date(session.session_date) if session.session_date else "—"
            start_time = (session.session_time or "00:00:00")[:5]
            start_display = f"{session_date} {start_time}" if session_date != "—" else "—"
            end_display = "—"
            if getattr(session, "end_date", None):
                end_time = (getattr(session, "end_time", None) or "00:00:00")[:5]
                end_display = f"{session.end_date} {end_time}"
            game_name = getattr(session, "game_name", None) or getattr(session, "game_type_name", None) or "—"
            net_pl = getattr(session, "net_taxable_pl", None)
            if net_pl is None:
                net_pl = getattr(session, "net_pl", None)
            net_display = self._format_signed_currency(net_pl) if net_pl is not None else "—"

            values = [start_display, end_display, game_name, net_display]
            for col_idx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                self.sessions_table.setItem(row_idx, col_idx, item)

            view_btn = QtWidgets.QPushButton("👁️ View Session")
            view_btn.setObjectName("MiniButton")
            view_btn.setFixedHeight(24)
            view_btn.setFixedWidth(view_btn.sizeHint().width() + 12)
            view_btn.clicked.connect(
                lambda _checked=False, sid=session.id: self._open_session(sid)
            )
            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.sessions_table.setCellWidget(row_idx, 4, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):
        if not self.on_open_purchase:
            QtWidgets.QMessageBox.information(
                self, "Purchases Unavailable", "Purchase view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_purchase(purchase_id))

    def _open_session(self, session_id):
        if not self.on_open_session:
            QtWidgets.QMessageBox.information(
                self, "Sessions Unavailable", "Session view is not available here."
            )
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_session(session_id))

    def _handle_open_redemption(self):
        redemption_id = self.position.get("redemption_id")
        if not redemption_id:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Redemption ID not found.")
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_redemption(redemption_id))

    def _handle_open_daily_sessions(self):
        session_date = self.position.get("session_date")
        if not session_date:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Session date not found.")
            return
        self.accept()
        QtCore.QTimer.singleShot(0, lambda: self.on_open_daily_sessions(session_date))

    def _format_date(self, value):
        if not value:
            return "—"
        if isinstance(value, date):
            return value.strftime("%m/%d/%y")
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%m/%d/%y")
        except Exception:
            return str(value)

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"


class RealizedTab(QtWidgets.QWidget):
    def __init__(self, facade: AppFacade, parent=None, main_window=None):
        super().__init__(parent)
        self.facade = facade
        self.main_window = main_window
        self.db = facade.db
        self.all_transactions = []
        self.filtered_transactions = []
        self.column_filters = {}
        self.date_filter = set()
        self.sort_column = None
        self.sort_reverse = False
        self.active_date_filter = (None, None)
        self.selected_users = set()
        self.selected_sites = set()

        self.columns = [
            "Date",
            "User",
            "Site",
            "Transaction",
            "Cost Basis",
            "Fees",
            "Realized P/L",
            "Notes",
        ]

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Realized")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search realized sessions...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.setMinimumWidth(300)
        header_layout.addWidget(self.search_edit)

        self.search_clear_btn = QtWidgets.QPushButton("Clear")
        header_layout.addWidget(self.search_clear_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        header_layout.addWidget(self.clear_filters_btn)

        layout.addLayout(header_layout)

        info = QtWidgets.QLabel("Realized cash flow from completed redemptions.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        year_start = date(date.today().year, 1, 1)
        self.date_filter_widget = DateFilterWidget(
            default_start=year_start,
            default_end=date.today(),
        )
        self.date_filter_widget.filter_changed.connect(self.apply_date_filter)
        layout.addWidget(self.date_filter_widget)

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

        self.date_notes_btn = QtWidgets.QPushButton("➕ Add Notes")
        self.date_notes_btn.setObjectName("PrimaryButton")
        self.view_position_btn = QtWidgets.QPushButton("👁️ View Position")
        self.view_position_btn.setObjectName("PrimaryButton")
        view_text_width = self.view_position_btn.fontMetrics().horizontalAdvance(self.view_position_btn.text()) + 24

        self.date_notes_wrapper = QtWidgets.QWidget()
        date_notes_layout = QtWidgets.QHBoxLayout(self.date_notes_wrapper)
        date_notes_layout.setContentsMargins(0, 0, 0, 0)
        date_notes_layout.addStretch(1)
        date_notes_layout.addWidget(self.date_notes_btn)

        self.transaction_actions = QtWidgets.QWidget()
        transaction_layout = QtWidgets.QHBoxLayout(self.transaction_actions)
        transaction_layout.setContentsMargins(0, 0, 0, 0)
        transaction_layout.setSpacing(8)
        transaction_layout.addStretch(1)
        transaction_layout.addWidget(self.view_position_btn)

        dynamic_width = max(
            self.date_notes_btn.sizeHint().width(),
            self.view_position_btn.sizeHint().width(),
            view_text_width,
        )
        for btn in (self.date_notes_btn, self.view_position_btn):
            btn.setMinimumWidth(dynamic_width)
        self.dynamic_placeholder = QtWidgets.QWidget()
        self.dynamic_placeholder.setFixedWidth(dynamic_width)
        self.dynamic_placeholder.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.dynamic_container = QtWidgets.QWidget()
        self.dynamic_container.setFixedWidth(dynamic_width)
        self.dynamic_container.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.dynamic_stack = QtWidgets.QStackedLayout(self.dynamic_container)
        self.dynamic_stack.setContentsMargins(0, 0, 0, 0)
        self.dynamic_stack.addWidget(self.dynamic_placeholder)
        self.dynamic_stack.addWidget(self.date_notes_wrapper)
        self.dynamic_stack.addWidget(self.transaction_actions)
        self.dynamic_stack.setCurrentWidget(self.dynamic_placeholder)

        self.expand_btn = QtWidgets.QPushButton("➕ Expand All")
        self.collapse_btn = QtWidgets.QPushButton("➖ Collapse All")
        self.export_btn = QtWidgets.QPushButton("📤 Export CSV")
        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")

        self.actions_container = QtWidgets.QWidget()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.dynamic_container)
        actions_layout.addWidget(self.expand_btn)
        actions_layout.addWidget(self.collapse_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.refresh_btn)
        action_row.addWidget(self.actions_container, 0, QtCore.Qt.AlignRight)
        layout.addLayout(action_row)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(self.columns))
        self.tree.setHeaderLabels(self.columns)
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumSize(0, 0)
        self.tree.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding
        )
        self.tree.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustIgnored)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        header = self.tree.header()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.setStretchLastSection(True)
        self.tree.setColumnWidth(0, 140)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 220)
        self.tree.setColumnWidth(3, 200)
        self.tree.setColumnWidth(4, 110)
        self.tree.setColumnWidth(5, 80)
        self.tree.setColumnWidth(6, 110)
        self.tree.setColumnWidth(7, 140)
        self.header = header
        header.viewport().installEventFilter(self)
        
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

        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._handle_double_click)

        self.search_edit.textChanged.connect(self.refresh_view)
        self.search_clear_btn.clicked.connect(self._clear_search)
        self.clear_filters_btn.clicked.connect(self.clear_all_filters)
        self.date_notes_btn.clicked.connect(self._edit_date_notes)
        self.view_position_btn.clicked.connect(self._view_position)
        self.expand_btn.clicked.connect(self.tree.expandAll)
        self.collapse_btn.clicked.connect(self.tree.collapseAll)
        self.refresh_btn.clicked.connect(self.refresh_view)
        self.export_btn.clicked.connect(self.export_csv)
        self.user_filter_btn.clicked.connect(self._show_user_filter)
        self.site_filter_btn.clicked.connect(self._show_site_filter)

        self.refresh_view()
    
    def _on_selection_changed(self):
        """Update stats bar and action buttons on selection change"""
        grid = SpreadsheetUXController.extract_selection_grid(self.tree)
        stats = SpreadsheetUXController.compute_stats(grid)
        self.stats_bar.update_stats(stats)
        self._update_action_buttons()

    def eventFilter(self, obj, event):
        if getattr(self, "tree", None) is not None and obj is self.tree.header().viewport():
            header = self.tree.header()
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

    def _current_meta(self):
        item = self.tree.currentItem()
        if not item:
            return None
        return item.data(0, QtCore.Qt.UserRole) or {}

    def _update_action_buttons(self):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        if kind == "date":
            self.dynamic_stack.setCurrentWidget(self.date_notes_wrapper)
        elif kind == "transaction":
            self.dynamic_stack.setCurrentWidget(self.transaction_actions)
        else:
            self.dynamic_stack.setCurrentWidget(self.dynamic_placeholder)

    def _handle_double_click(self, *_args):
        meta = self._current_meta() or {}
        kind = meta.get("kind")
        if kind == "date":
            self._edit_date_notes()
        elif kind == "transaction":
            self._view_position()

    def apply_date_filter(self):
        start_date, end_date = self.date_filter_widget.get_date_range()
        if start_date and end_date and start_date > end_date:
            QtWidgets.QMessageBox.warning(self, "Invalid Range", "From date is after To date.")
            return
        self.active_date_filter = (start_date, end_date)
        self.refresh_view()

    def clear_date_filter(self):
        year_start = date(date.today().year, 1, 1)
        self.date_filter_widget.start_date.setText(year_start.strftime("%m/%d/%y"))
        self.date_filter_widget.end_date.setText(date.today().strftime("%m/%d/%y"))
        self.apply_date_filter()

    def clear_all_filters(self):
        self.selected_users = set()
        self.selected_sites = set()
        self.date_filter = set()
        self.column_filters = {}
        self._set_filter_label(self.user_filter_label, self.selected_users)
        self._set_filter_label(self.site_filter_label, self.selected_sites)
        self.search_edit.clear()
        self._clear_selection()
        year_start = date(date.today().year, 1, 1)
        self.date_filter_widget.start_date.setText(year_start.strftime("%m/%d/%y"))
        self.date_filter_widget.end_date.setText(date.today().strftime("%m/%d/%y"))
        self.apply_date_filter()

    def _clear_search(self):
        self.search_edit.clear()
        self._clear_selection()

    def _clear_selection(self):
        self.tree.clearSelection()
        self._update_action_buttons()

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
            transactions = self._filter_transactions(
                self._last_transactions, exclude_col=col_index, include_search=True
            )
            if col_index == 0:
                values = sorted({t["session_date"] for t in transactions})
                dialog = DateTimeFilterDialog(values, self.date_filter, self, show_time=False)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    self.date_filter = dialog.selected_values()
                    self.refresh_view()
            else:
                values = sorted({self._transaction_value_for_column(t, col_index) for t in transactions})
                selected = self.column_filters.get(col_index, set())
                dialog = ColumnFilterDialog(values, selected, self)
                if dialog.exec() == QtWidgets.QDialog.Accepted:
                    selected_values = dialog.selected_values()
                    if selected_values:
                        self.column_filters[col_index] = selected_values
                    else:
                        self.column_filters.pop(col_index, None)
                    self.refresh_view()

    def _format_signed_currency(self, value):
        if value is None:
            return "-"
        val = float(value)
        return f"+${val:.2f}" if val >= 0 else f"${val:.2f}"

    def _format_currency_or_dash(self, value):
        if value is None:
            return "-"
        return format_currency(value)

    def _transaction_value_for_column(self, tx, col_index):
        if col_index == 0:
            return tx["session_date"]
        if col_index == 1:
            return tx["user_name"]
        if col_index == 2:
            return tx["site_name"]
        if col_index == 3:
            return self._transaction_label(tx)
        if col_index == 4:
            return self._format_currency_or_dash(tx["cost_basis"])
        if col_index == 5:
            return self._format_currency_or_dash(tx.get("fees", 0))
        if col_index == 6:
            net_pl = tx["net_pl"]
            fees = tx.get("fees", 0) or 0
            adjusted_net_pl = net_pl - fees
            return self._format_signed_currency(adjusted_net_pl)
        if col_index == 7:
            return tx.get("notes") or ""
        return ""

    def _align_numeric(self, item):
        for col in (4, 5, 6):
            item.setTextAlignment(col, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def _apply_status_color(self, item, value):
        if value is None:
            return
        color = "#2e7d32" if value >= 0 else "#c0392b"
        brush = QtGui.QBrush(QtGui.QColor(color))
        for col in range(item.columnCount()):
            item.setForeground(col, brush)

    def _transaction_label(self, tx):
        redemption_amount = tx.get("redemption_amount") or 0.0
        if redemption_amount == 0:
            return "Total Loss"
        return f"Redemption (${redemption_amount:.2f})"

    def _fetch_transactions(self):
        query = """
            SELECT
                rt.id as tax_session_id,
                rt.redemption_date as session_date,
                rt.redemption_id as redemption_id,
                rt.cost_basis,
                rt.net_pl,
                rt.site_id,
                s.name as site_name,
                rt.user_id,
                u.name as user_name,
                r.amount as redemption_amount,
                r.fees as fees,
                r.is_free_sc,
                r.notes as redemption_notes,
                rt.notes as session_notes
            FROM realized_transactions rt
            JOIN sites s ON rt.site_id = s.id
            JOIN users u ON rt.user_id = u.id
            LEFT JOIN redemptions r ON rt.redemption_id = r.id
        """
        params = []
        conditions = []
        if self.selected_sites:
            placeholders = ",".join("?" * len(self.selected_sites))
            conditions.append(f"s.name IN ({placeholders})")
            params.extend(list(self.selected_sites))
        if self.selected_users:
            placeholders = ",".join("?" * len(self.selected_users))
            conditions.append(f"u.name IN ({placeholders})")
            params.extend(list(self.selected_users))
        start_date, end_date = self.active_date_filter
        if start_date:
            conditions.append("rt.redemption_date >= ?")
            params.append(start_date.isoformat() if isinstance(start_date, date) else start_date)
        if end_date:
            conditions.append("rt.redemption_date <= ?")
            params.append(end_date.isoformat() if isinstance(end_date, date) else end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY rt.redemption_date DESC, s.name ASC, u.name ASC, rt.id ASC"

        rows = self.db.fetch_all(query, tuple(params))
        transactions = []
        for row in rows:
            row = dict(row)
            redemption_notes = row.get("redemption_notes") or ""
            session_notes = row.get("session_notes") or ""
            notes = redemption_notes or session_notes
            redemption_amount = row.get("redemption_amount") or 0.0
            search_blob = " ".join(
                [
                    row["session_date"],
                    row["site_name"],
                    row["user_name"],
                    f"{Decimal(str(row['cost_basis'])):.2f}",
                    f"{Decimal(str(row['net_pl'])):.2f}",
                    f"{Decimal(str(redemption_amount)):.2f}",
                    notes,
                ]
            ).lower()
            transactions.append(
                {
                    "tax_session_id": row["tax_session_id"],
                    "redemption_id": row["redemption_id"],
                    "session_date": row["session_date"],
                    "site_id": row["site_id"],
                    "site_name": row["site_name"],
                    "user_id": row["user_id"],
                    "user_name": row["user_name"],
                    "cost_basis": Decimal(str(row["cost_basis"])),
                    "net_pl": Decimal(str(row["net_pl"])),
                    "fees": Decimal(str(row.get("fees") or 0)),
                    "redemption_amount": Decimal(str(redemption_amount)),
                    "is_free_sc": bool(row.get("is_free_sc") or 0),
                    "notes": notes,
                    "redemption_notes": redemption_notes,
                    "search_blob": search_blob,
                }
            )
        return transactions

    def _filter_transactions(self, transactions, exclude_col=None, include_search=True):
        if self.date_filter and exclude_col != 0:
            transactions = [t for t in transactions if t["session_date"] in self.date_filter]
        for col_index, values in self.column_filters.items():
            if col_index == exclude_col:
                continue
            if values:
                transactions = [
                    t for t in transactions if self._transaction_value_for_column(t, col_index) in values
                ]
        if include_search:
            term = self.search_edit.text().strip().lower()
            if term:
                transactions = [t for t in transactions if term in t["search_blob"]]
        return transactions

    def _group_transactions(self, transactions):
        from collections import defaultdict

        dates = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for tx in transactions:
            dates[tx["session_date"]][tx["user_id"]][tx["site_id"]].append(tx)

        notes_by_date = self._fetch_notes_for_dates(dates.keys())
        data = []
        for session_date in sorted(dates.keys(), reverse=True):
            user_groups = []
            date_site_ids = set()
            total_transactions = 0
            date_cost = Decimal("0.00")
            date_fees = Decimal("0.00")
            date_net = Decimal("0.00")
            notes_count = 0
            users_map = dates[session_date]
            for user_id in sorted(
                users_map.keys(),
                key=lambda uid: list(users_map[uid].values())[0][0]["user_name"].lower(),
            ):
                sites_map = users_map[user_id]
                site_groups = []
                user_cost = Decimal("0.00")
                user_fees = Decimal("0.00")
                user_net = Decimal("0.00")
                user_transactions = 0
                for site_id in sorted(
                    sites_map.keys(),
                    key=lambda sid: sites_map[sid][0]["site_name"].lower(),
                ):
                    txs = sites_map[site_id]
                    total_cost = sum(tx["cost_basis"] for tx in txs)
                    total_fees = sum((tx.get("fees", 0) or 0) for tx in txs)
                    total_net = sum((tx["net_pl"] - (tx.get("fees", 0) or 0)) for tx in txs)
                    transaction_count = len(txs)
                    site_groups.append(
                        {
                            "site_id": site_id,
                            "site_name": txs[0]["site_name"],
                            "total_cost": total_cost,
                            "total_fees": total_fees,
                            "total_net": total_net,
                            "transaction_count": transaction_count,
                            "transactions": txs,
                        }
                    )
                    user_cost += total_cost
                    user_fees += total_fees
                    user_net += total_net
                    user_transactions += transaction_count
                    total_transactions += transaction_count
                    date_site_ids.add(site_id)
                    notes_count += sum(1 for tx in txs if tx.get("notes"))

                user_groups.append(
                    {
                        "user_id": user_id,
                        "user_name": list(sites_map.values())[0][0]["user_name"],
                        "total_cost": user_cost,
                        "total_fees": user_fees,
                        "total_net": user_net,
                        "transaction_count": user_transactions,
                        "site_count": len(site_groups),
                        "sites": site_groups,
                    }
                )
                date_cost += user_cost
                date_fees += user_fees
                date_net += user_net

            date_notes = notes_by_date.get(session_date, "")
            if date_notes:
                notes_count += 1
            data.append(
                {
                    "date": session_date,
                    "date_cost": date_cost,
                    "date_fees": date_fees,
                    "date_net": date_net,
                    "user_count": len(user_groups),
                    "site_count": len(date_site_ids),
                    "transaction_count": total_transactions,
                    "notes_count": notes_count,
                    "notes": date_notes,
                    "users": user_groups,
                }
            )
        return self._sort_data(data)

    def _sort_data(self, data):
        if self.sort_column is None:
            return data
        reverse = self.sort_reverse

        def sort_key(item):
            if self.sort_column == 0:
                return item["date"]
            if self.sort_column == 1:
                return item["user_count"]
            if self.sort_column == 2:
                return item["site_count"]
            if self.sort_column == 3:
                return item["transaction_count"]
            if self.sort_column == 4:
                return item["date_cost"]
            if self.sort_column == 5:
                return item.get("date_fees", 0)
            if self.sort_column == 6:
                return item["date_net"]
            if self.sort_column == 7:
                return item["notes_count"]
            return item["date"]

        return sorted(data, key=sort_key, reverse=reverse)

    def _render_tree(self, data):
        self.tree.clear()
        for day in data:
            date_values = [
                f"📅 {day['date']}",
                f"{day['user_count']} user(s)",
                f"{day['site_count']} site(s)",
                f"{day['transaction_count']} transaction(s)",
                self._format_currency_or_dash(day["date_cost"]),
                self._format_currency_or_dash(day.get("date_fees", 0)),
                self._format_signed_currency(day["date_net"]),
                day.get("notes", ""),
            ]
            date_item = QtWidgets.QTreeWidgetItem(date_values)
            date_item.setData(0, QtCore.Qt.UserRole, {"kind": "date", "date": day["date"]})
            self._align_numeric(date_item)
            self._apply_status_color(date_item, day["date_net"])
            self.tree.addTopLevelItem(date_item)

            for user in day["users"]:
                user_display = f"👤 {user['user_name']}"
                user_values = [
                    "",
                    user_display,
                    f"{user['site_count']} site(s)",
                    f"{user['transaction_count']} transaction(s)",
                    self._format_currency_or_dash(user["total_cost"]),
                    self._format_currency_or_dash(user.get("total_fees", 0)),
                    self._format_signed_currency(user["total_net"]),
                    "",
                ]
                user_item = QtWidgets.QTreeWidgetItem(user_values)
                user_item.setData(
                    0,
                    QtCore.Qt.UserRole,
                    {"kind": "user", "user_id": user["user_id"]},
                )
                self._align_numeric(user_item)
                self._apply_status_color(user_item, user["total_net"])
                date_item.addChild(user_item)

                for site in user["sites"]:
                    site_display = f"⤷ {site['site_name']}"
                    site_values = [
                        "",
                        "",
                        site_display,
                        f"{site['transaction_count']} transaction(s)",
                        self._format_currency_or_dash(site["total_cost"]),
                        self._format_currency_or_dash(site.get("total_fees", 0)),
                        self._format_signed_currency(site["total_net"]),
                        "",
                    ]
                    site_item = QtWidgets.QTreeWidgetItem(site_values)
                    site_item.setData(
                        0,
                        QtCore.Qt.UserRole,
                        {"kind": "site", "site_id": site["site_id"], "user_id": user["user_id"]},
                    )
                    self._align_numeric(site_item)
                    self._apply_status_color(site_item, site["total_net"])
                    user_item.addChild(site_item)

                    for tx in site["transactions"]:
                        transaction_display = f"⤷ {self._transaction_label(tx)}"
                        tx_fees = tx.get("fees", 0) or 0
                        tx_net_pl = tx["net_pl"]
                        adjusted_net_pl = tx_net_pl - tx_fees
                        tx_values = [
                            "",
                            "",
                            "",
                            transaction_display,
                            self._format_currency_or_dash(tx["cost_basis"]),
                            self._format_currency_or_dash(tx_fees),
                            self._format_signed_currency(adjusted_net_pl),
                            tx.get("notes") or "",
                        ]
                        tx_item = QtWidgets.QTreeWidgetItem(tx_values)
                        tx_item.setData(
                            0,
                            QtCore.Qt.UserRole,
                            {
                                "kind": "transaction",
                                "tax_session_id": tx["tax_session_id"],
                                "redemption_id": tx["redemption_id"],
                            },
                        )
                        self._align_numeric(tx_item)
                        self._apply_status_color(tx_item, adjusted_net_pl)
                        site_item.addChild(tx_item)

    def refresh_view(self):
        transactions = self._fetch_transactions()
        self._last_transactions = transactions
        transactions = self._filter_transactions(transactions)
        data = self._group_transactions(transactions)
        self._render_tree(data)
        self._update_action_buttons()
    
    def focus_search(self):
        """Focus the search bar (for Cmd+F/Ctrl+F shortcut - Issue #99)"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_data(self):
        """Standardized refresh method for global refresh system (Issue #9)."""
        self.refresh_view()

    def _fetch_notes_for_dates(self, dates):
        dates = list(dates)
        if not dates:
            return {}
        placeholders = ",".join("?" * len(dates))
        rows = self.db.fetch_all(
            f"""
            SELECT session_date, notes
            FROM realized_daily_notes
            WHERE session_date IN ({placeholders})
            """,
            tuple(dates),
        )
        return {row["session_date"]: (row["notes"] or "") for row in rows}

    def _edit_date_notes(self):
        meta = self._current_meta() or {}
        session_date = meta.get("date")
        if not session_date:
            QtWidgets.QMessageBox.information(self, "Select Date", "Select a date to add notes.")
            return
        
        # Use service layer instead of direct SQL
        current_notes = self.facade.realized_notes_service.get_date_note(session_date) or ""

        dialog = RealizedDateNotesDialog(session_date, current_notes, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        
        new_notes = dialog.notes_text()
        if new_notes:
            self.facade.realized_notes_service.set_date_note(session_date, new_notes)
        else:
            self.facade.realized_notes_service.delete_date_note(session_date)
        self.refresh_view()

    def _view_position(self):
        meta = self._current_meta() or {}
        if meta.get("kind") != "transaction":
            QtWidgets.QMessageBox.information(
                self, "Select Transaction", "Select an individual transaction to view."
            )
            return
        session_id = meta.get("tax_session_id")
        if not session_id:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Transaction ID not found.")
            return
        position = self._fetch_position_details(session_id)
        if not position:
            QtWidgets.QMessageBox.warning(self, "Not Found", "Transaction not found.")
            return
        allocations = self._fetch_redemption_allocations(position["redemption_id"])
        linked_sessions = self._fetch_linked_sessions(position["redemption_id"])
        dialog = RealizedPositionDialog(
            position,
            allocations,
            linked_sessions,
            parent=self,
            on_open_purchase=self._open_purchase,
            on_open_redemption=self._open_redemption,
            on_open_daily_sessions=self._open_daily_sessions,
            on_open_session=self._open_session,
            facade=self.facade,
        )
        dialog.exec()

    def _open_daily_sessions(self, session_date):
        if not self.main_window or not hasattr(self.main_window, "open_daily_sessions_by_date"):
            QtWidgets.QMessageBox.information(
                self, "Daily Sessions Unavailable", "Daily Sessions view is not available here."
            )
            return
        QtCore.QTimer.singleShot(0, lambda: self.main_window.open_daily_sessions_by_date(session_date))

    def _fetch_position_details(self, tax_session_id):
        row = self.db.fetch_one(
            """
            SELECT
                rt.id as tax_session_id,
                rt.redemption_date as session_date,
                rt.cost_basis,
                rt.net_pl,
                rt.redemption_id,
                r.amount as redemption_amount,
                r.redemption_date,
                r.redemption_time,
                r.fees,
                r.more_remaining,
                r.receipt_date,
                r.processed,
                r.notes as redemption_notes,
                s.name as site_name,
                u.name as user_name,
                rm.name as method_name,
                rm.method_type
            FROM realized_transactions rt
            JOIN redemptions r ON rt.redemption_id = r.id
            JOIN sites s ON rt.site_id = s.id
            JOIN users u ON rt.user_id = u.id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE rt.id = ?
            """,
            (tax_session_id,),
        )
        return dict(row) if row else None

    def _fetch_redemption_allocations(self, redemption_id):
        rows = self.db.fetch_all(
            """
            SELECT
                ra.purchase_id,
                ra.allocated_amount,
                p.purchase_date,
                p.purchase_time,
                p.amount,
                p.sc_received,
                p.remaining_amount
            FROM redemption_allocations ra
            JOIN purchases p ON ra.purchase_id = p.id
            WHERE ra.redemption_id = ?
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time,'00:00:00') ASC, p.id ASC
            """,
            (redemption_id,),
        )
        return [dict(row) for row in rows]

    def _fetch_linked_sessions(self, redemption_id):
        sessions = self.facade.get_linked_sessions_for_redemption(redemption_id)
        games = {g.id: g for g in self.facade.list_all_games()}
        game_types = {t.id: t.name for t in self.facade.get_all_game_types()}
        for session in sessions:
            game = games.get(session.game_id)
            session.game_type_name = game_types.get(game.game_type_id, "—") if game else "—"
        return sessions

    def find_and_select_redemption(self, redemption_id):
        def search_tree(item):
            meta = item.data(0, QtCore.Qt.UserRole)
            if meta and meta.get("kind") == "transaction" and meta.get("redemption_id") == redemption_id:
                return item
            for i in range(item.childCount()):
                result = search_tree(item.child(i))
                if result:
                    return result
            return None

        for i in range(self.tree.topLevelItemCount()):
            result = search_tree(self.tree.topLevelItem(i))
            if result:
                parent = result.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(result)
                self.tree.scrollToItem(result, QtWidgets.QAbstractItemView.PositionAtCenter)
                return True
        return False

    def view_realized_by_redemption_id(self, redemption_id: int):
        if redemption_id is None:
            return
        self.clear_date_filter()
        self.refresh_view()
        if self.find_and_select_redemption(redemption_id):
            # After selecting, open the View Position dialog
            QtCore.QTimer.singleShot(100, self._view_position)

    def export_csv(self):
        import csv

        default_name = f"realized_sessions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Realized Sessions",
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)

            def write_item(item):
                row_data = []
                for col in range(len(self.columns)):
                    text = item.text(col)
                    if text.startswith("$") or text.startswith("-$"):
                        text = text.replace("$", "").replace(",", "")
                    row_data.append(text)
                writer.writerow(row_data)
                for idx in range(item.childCount()):
                    write_item(item.child(idx))

            for idx in range(self.tree.topLevelItemCount()):
                write_item(self.tree.topLevelItem(idx))

    def _open_purchase(self, purchase_id: int):
        main_window = self._resolve_main_window()
        if main_window and hasattr(main_window, "open_purchase"):
            main_window.open_purchase(purchase_id)

    def _open_redemption(self, redemption_id: int):
        main_window = self._resolve_main_window()
        if main_window and hasattr(main_window, "open_redemption"):
            main_window.open_redemption(redemption_id)

    def _open_session(self, session_id: int):
        main_window = self._resolve_main_window()
        if main_window and hasattr(main_window, "open_session"):
            main_window.open_session(session_id)

    def _resolve_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "main_window") and parent.main_window is not None:
                return parent.main_window
            if parent.parent() is None and hasattr(parent, "open_purchase"):
                return parent
            parent = parent.parent()
        return None
    
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
