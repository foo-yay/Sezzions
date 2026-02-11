"""
Reports tab - Phase 1 (Issue #102)
"""
from decimal import Decimal
from typing import Optional, List
from PySide6 import QtWidgets, QtCore

from app_facade import AppFacade
from services.report_service import ReportFilter
from ui.date_filter_widget import DateFilterWidget


class ReportsTab(QtWidgets.QWidget):
    """Reports tab with KPI snapshot and breakdown tables."""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.report_service = facade.report_service

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Reports")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Filter bar
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setSpacing(12)

        self.date_filter = DateFilterWidget("Date Range")
        self.date_filter.filter_changed.connect(self.refresh_data)
        filter_row.addWidget(self.date_filter)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setMinimumWidth(180)
        self.user_combo.currentIndexChanged.connect(self.refresh_data)
        filter_row.addWidget(self._labeled_widget("User", self.user_combo))

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setMinimumWidth(180)
        self.site_combo.currentIndexChanged.connect(self.refresh_data)
        filter_row.addWidget(self._labeled_widget("Site", self.site_combo))

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # KPI snapshot strip
        self.kpi_grid = QtWidgets.QGridLayout()
        self.kpi_grid.setHorizontalSpacing(16)
        self.kpi_grid.setVerticalSpacing(8)
        layout.addLayout(self.kpi_grid)

        self.kpi_labels = {}
        self._add_kpi("Session Net P/L", 0, 0, "session_net_pl")
        self._add_kpi("Cashback", 0, 1, "total_cashback")
        self._add_kpi("Net P/L + Cashback", 0, 2, "session_pl_plus_cashback")
        self._add_kpi("Purchases", 1, 0, "total_purchases")
        self._add_kpi("Redemptions", 1, 1, "total_redemptions")
        self._add_kpi("Fees", 1, 2, "total_fees")
        self._add_kpi("Outstanding Balance", 1, 3, "outstanding_balance")

        # Tables
        self.user_table = QtWidgets.QTableWidget(0, 9)
        self.user_table.setHorizontalHeaderLabels([
            "User",
            "Session Net P/L",
            "Cashback",
            "Net P/L + Cashback",
            "Purchases",
            "Redemptions",
            "Fees",
            "# Sessions",
            "Outstanding",
        ])
        self.user_table.horizontalHeader().setStretchLastSection(True)

        self.site_table = QtWidgets.QTableWidget(0, 9)
        self.site_table.setHorizontalHeaderLabels([
            "Site",
            "Session Net P/L",
            "Cashback",
            "Net P/L + Cashback",
            "Purchases",
            "Redemptions",
            "Fees",
            "# Sessions",
            "Outstanding",
        ])
        self.site_table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self._section_card("By User", self.user_table))
        layout.addWidget(self._section_card("By Site", self.site_table))

        self._load_filter_options()
        self.refresh_data()

    def _labeled_widget(self, label: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title = QtWidgets.QLabel(label)
        title.setStyleSheet("color: #666;")
        layout.addWidget(title)
        layout.addWidget(widget)
        return container

    def _section_card(self, title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        card = QtWidgets.QFrame()
        card.setObjectName("ReportSectionCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)
        header = QtWidgets.QLabel(title)
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        card_layout.addWidget(header)
        card_layout.addWidget(widget)
        return card

    def _add_kpi(self, label: str, row: int, col: int, key: str) -> None:
        label_widget = QtWidgets.QLabel(label)
        value_widget = QtWidgets.QLabel("$0.00")
        value_widget.setStyleSheet("font-weight: bold;")
        self.kpi_grid.addWidget(label_widget, row * 2, col)
        self.kpi_grid.addWidget(value_widget, row * 2 + 1, col)
        self.kpi_labels[key] = value_widget

    def _format_currency(self, value: Decimal) -> str:
        return f"${value:,.2f}"

    def _load_filter_options(self) -> None:
        self.user_combo.blockSignals(True)
        self.site_combo.blockSignals(True)

        self.user_combo.clear()
        self.user_combo.addItem("All", None)
        for user in self.facade.get_all_users(active_only=False):
            self.user_combo.addItem(user.name, user.id)

        self.site_combo.clear()
        self.site_combo.addItem("All", None)
        for site in self.facade.get_all_sites(active_only=False):
            self.site_combo.addItem(site.name, site.id)

        self.user_combo.blockSignals(False)
        self.site_combo.blockSignals(False)

    def _build_filter(self) -> ReportFilter:
        start_date, end_date = self.date_filter.get_date_range()
        user_id = self.user_combo.currentData()
        site_id = self.site_combo.currentData()

        return ReportFilter(
            start_date=start_date,
            end_date=end_date,
            user_ids=[user_id] if user_id else None,
            site_ids=[site_id] if site_id else None,
            include_deleted=False,
        )

    def refresh_data(self):
        """Refresh the snapshot KPIs and breakdown tables."""
        try:
            report_filter = self._build_filter()

            snapshot = self.report_service.get_kpi_snapshot(report_filter)
            self.kpi_labels["session_net_pl"].setText(self._format_currency(snapshot.session_net_pl))
            self.kpi_labels["total_cashback"].setText(self._format_currency(snapshot.total_cashback))
            self.kpi_labels["session_pl_plus_cashback"].setText(self._format_currency(snapshot.session_pl_plus_cashback))
            self.kpi_labels["total_purchases"].setText(self._format_currency(snapshot.total_purchases))
            self.kpi_labels["total_redemptions"].setText(self._format_currency(snapshot.total_redemptions))
            self.kpi_labels["total_fees"].setText(self._format_currency(snapshot.total_fees))
            self.kpi_labels["outstanding_balance"].setText(self._format_currency(snapshot.outstanding_balance))

            user_rows = self.report_service.get_user_breakdown(report_filter)
            site_rows = self.report_service.get_site_breakdown(report_filter)

            self._populate_user_table(user_rows)
            self._populate_site_table(site_rows)
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Reports", f"Failed to load reports:\n{exc}")

    def _populate_user_table(self, rows) -> None:
        self.user_table.setRowCount(0)
        for row in rows:
            self._add_row(self.user_table, [
                row.user_name,
                self._format_currency(row.session_net_pl),
                self._format_currency(row.cashback),
                self._format_currency(row.session_net_pl + row.cashback),
                self._format_currency(row.purchases),
                self._format_currency(row.redemptions),
                self._format_currency(row.fees),
                str(row.session_count),
                self._format_currency(row.outstanding_balance),
            ])

    def _populate_site_table(self, rows) -> None:
        self.site_table.setRowCount(0)
        for row in rows:
            self._add_row(self.site_table, [
                row.site_name,
                self._format_currency(row.session_net_pl),
                self._format_currency(row.cashback),
                self._format_currency(row.session_net_pl + row.cashback),
                self._format_currency(row.purchases),
                self._format_currency(row.redemptions),
                self._format_currency(row.fees),
                str(row.session_count),
                self._format_currency(row.outstanding_balance),
            ])

    def _add_row(self, table: QtWidgets.QTableWidget, values: List[str]) -> None:
        row_idx = table.rowCount()
        table.insertRow(row_idx)
        for col_idx, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            if col_idx > 0:
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row_idx, col_idx, item)
