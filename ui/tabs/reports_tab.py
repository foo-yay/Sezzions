"""
Reports tab - Phase 1 (Issue #102) with wireframe layout.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from PySide6 import QtWidgets, QtCore

from app_facade import AppFacade
from services.report_service import ReportFilter
from ui.date_filter_widget import DateFilterWidget


def _card(title: str, value: str = "—", subtitle: str = "") -> QtWidgets.QFrame:
    """Simple KPI card frame."""
    frame = QtWidgets.QFrame()
    frame.setObjectName("KpiCard")
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)

    label_title = QtWidgets.QLabel(title)
    label_title.setObjectName("KpiTitle")
    label_value = QtWidgets.QLabel(value)
    label_value.setObjectName("KpiValue")
    label_sub = QtWidgets.QLabel(subtitle)
    label_sub.setObjectName("KpiSub")

    layout.addWidget(label_title)
    layout.addWidget(label_value)
    if subtitle:
        layout.addWidget(label_sub)
    layout.addStretch(1)

    return frame


def _panel(title: str) -> QtWidgets.QFrame:
    """Generic panel frame for charts/lists/tables."""
    frame = QtWidgets.QFrame()
    frame.setObjectName("Panel")
    frame.setFrameShape(QtWidgets.QFrame.StyledPanel)

    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    header = QtWidgets.QHBoxLayout()
    label = QtWidgets.QLabel(title)
    label.setObjectName("PanelTitle")
    header.addWidget(label)
    header.addStretch(1)
    layout.addLayout(header)

    body = QtWidgets.QFrame()
    body.setObjectName("PanelBody")
    body.setFrameShape(QtWidgets.QFrame.NoFrame)
    layout.addWidget(body)

    return frame


class ReportsTab(QtWidgets.QWidget):
    """Reports tab with KPI snapshot and breakdown tables."""

    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        self.report_service = facade.report_service

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # ----- Left Sidebar -----
        self.nav = QtWidgets.QListWidget()
        self.nav.setObjectName("ReportsNav")
        self.nav.setFixedWidth(220)
        self.nav.addItems([
            "Overview",
            "By User",
            "By Site",
            "Games",
            "Cashback",
            "Time & Flow",
            "Balances",
            "Tax Analysis",
            "Custom Builder",
        ])

        sidebar_layout = QtWidgets.QVBoxLayout()
        sidebar_layout.setSpacing(10)
        sidebar_layout.addWidget(QtWidgets.QLabel("Reports"))
        sidebar_layout.addWidget(self.nav)

        self.btn_save_view = QtWidgets.QPushButton("Save View")
        self.btn_load_view = QtWidgets.QPushButton("Load View")
        sidebar_layout.addWidget(self.btn_save_view)
        sidebar_layout.addWidget(self.btn_load_view)
        sidebar_layout.addStretch(1)

        sidebar_wrap = QtWidgets.QWidget()
        sidebar_wrap.setLayout(sidebar_layout)
        sidebar_wrap.setObjectName("ReportsSidebar")

        root.addWidget(sidebar_wrap)

        # ----- Main Area -----
        main = QtWidgets.QVBoxLayout()
        main.setSpacing(10)

        # Filter bar
        self.filter_bar = QtWidgets.QFrame()
        self.filter_bar.setObjectName("FilterBar")
        self.filter_bar.setFrameShape(QtWidgets.QFrame.StyledPanel)
        filter_grid = QtWidgets.QGridLayout(self.filter_bar)
        filter_grid.setContentsMargins(12, 10, 12, 10)
        filter_grid.setHorizontalSpacing(10)
        filter_grid.setVerticalSpacing(8)

        self.date_filter = DateFilterWidget("Date Range")
        self.date_filter.filter_changed.connect(self.refresh_data)

        self.user_combo = QtWidgets.QComboBox()
        self.user_combo.setObjectName("FilterUser")
        self.user_combo.setMinimumWidth(160)
        self.user_combo.currentIndexChanged.connect(self.refresh_data)

        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setObjectName("FilterSite")
        self.site_combo.setMinimumWidth(160)
        self.site_combo.currentIndexChanged.connect(self.refresh_data)

        self.card_combo = QtWidgets.QComboBox()
        self.card_combo.setObjectName("FilterCard")
        self.card_combo.setMinimumWidth(160)

        self.game_type_combo = QtWidgets.QComboBox()
        self.game_type_combo.setObjectName("FilterGameType")
        self.game_type_combo.setMinimumWidth(160)

        self.game_combo = QtWidgets.QComboBox()
        self.game_combo.setObjectName("FilterGame")
        self.game_combo.setMinimumWidth(160)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search current table…")
        self.search_edit.textChanged.connect(self._apply_search_filter)

        self.btn_7d = QtWidgets.QPushButton("7d")
        self.btn_30d = QtWidgets.QPushButton("30d")
        self.btn_mtd = QtWidgets.QPushButton("MTD")
        self.btn_ytd = QtWidgets.QPushButton("YTD")
        self.btn_all = QtWidgets.QPushButton("All")
        for btn in (self.btn_7d, self.btn_30d, self.btn_mtd, self.btn_ytd, self.btn_all):
            btn.setObjectName("PresetChip")

        self.btn_7d.clicked.connect(lambda: self._set_range_days(7))
        self.btn_30d.clicked.connect(lambda: self._set_range_days(30))
        self.btn_mtd.clicked.connect(self._set_month_to_date)
        self.btn_ytd.clicked.connect(self._set_year_to_date)
        self.btn_all.clicked.connect(self.date_filter.set_all_time)

        self.chk_soft_deleted = QtWidgets.QCheckBox("Include soft-deleted")
        self.chk_anomalies = QtWidgets.QCheckBox("Include anomalies")
        self.chk_soft_deleted.stateChanged.connect(self.refresh_data)

        # Row 0: date + presets + save/load
        filter_grid.addWidget(self.date_filter, 0, 0, 1, 2)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setSpacing(6)
        for btn in (self.btn_7d, self.btn_30d, self.btn_mtd, self.btn_ytd, self.btn_all):
            preset_row.addWidget(btn)
        preset_row.addStretch(1)
        preset_wrap = QtWidgets.QWidget()
        preset_wrap.setLayout(preset_row)
        filter_grid.addWidget(preset_wrap, 0, 2, 1, 2)

        save_row = QtWidgets.QHBoxLayout()
        save_row.addWidget(self.btn_save_view)
        save_row.addWidget(self.btn_load_view)
        save_row.addStretch(1)
        save_wrap = QtWidgets.QWidget()
        save_wrap.setLayout(save_row)
        filter_grid.addWidget(save_wrap, 0, 4, 1, 2)

        # Row 1: user/site/card
        filter_grid.addWidget(QtWidgets.QLabel("User"), 1, 0)
        filter_grid.addWidget(self.user_combo, 1, 1)
        filter_grid.addWidget(QtWidgets.QLabel("Site"), 1, 2)
        filter_grid.addWidget(self.site_combo, 1, 3)
        filter_grid.addWidget(QtWidgets.QLabel("Card"), 1, 4)
        filter_grid.addWidget(self.card_combo, 1, 5)

        # Row 2: game type/game/search
        filter_grid.addWidget(QtWidgets.QLabel("Game Type"), 2, 0)
        filter_grid.addWidget(self.game_type_combo, 2, 1)
        filter_grid.addWidget(QtWidgets.QLabel("Game"), 2, 2)
        filter_grid.addWidget(self.game_combo, 2, 3)
        filter_grid.addWidget(self.search_edit, 2, 4, 1, 2)

        # Row 3: toggles
        toggle_row = QtWidgets.QHBoxLayout()
        toggle_row.addWidget(self.chk_soft_deleted)
        toggle_row.addWidget(self.chk_anomalies)
        toggle_row.addStretch(1)
        toggle_wrap = QtWidgets.QWidget()
        toggle_wrap.setLayout(toggle_row)
        filter_grid.addWidget(toggle_wrap, 3, 0, 1, 6)

        main.addWidget(self.filter_bar)

        # KPI strip
        kpi_wrap = QtWidgets.QFrame()
        kpi_wrap.setObjectName("KpiStrip")
        kpi_wrap.setFrameShape(QtWidgets.QFrame.NoFrame)
        kpi_grid = QtWidgets.QGridLayout(kpi_wrap)
        kpi_grid.setContentsMargins(0, 0, 0, 0)
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)

        self.kpi_labels = {}

        self.kpi_net = self._register_kpi(kpi_grid, 0, 0, "Net P/L (pre-tax)", "session_net_pl")
        self.kpi_net_cb = self._register_kpi(kpi_grid, 0, 1, "Net P/L + Cashback", "session_pl_plus_cashback")
        self.kpi_post = self._register_kpi(kpi_grid, 0, 2, "Net P/L (post-tax)")
        self.kpi_post_cb = self._register_kpi(kpi_grid, 0, 3, "Post-tax + Cashback")

        self.kpi_cashback = self._register_kpi(kpi_grid, 1, 0, "Cashback", "total_cashback")
        self.kpi_fees = self._register_kpi(kpi_grid, 1, 1, "Fees", "total_fees")
        self.kpi_purchased = self._register_kpi(kpi_grid, 1, 2, "Purchased", "total_purchases")
        self.kpi_redeemed = self._register_kpi(kpi_grid, 1, 3, "Redeemed", "total_redemptions")
        self.kpi_outstanding = self._register_kpi(kpi_grid, 1, 4, "Outstanding Balance", "outstanding_balance")
        self.kpi_rtp = self._register_kpi(kpi_grid, 1, 5, "Avg RTP")
        self.kpi_redeem_time = self._register_kpi(kpi_grid, 1, 6, "Avg Redemption Time")

        main.addWidget(kpi_wrap)

        # Stacked section pages
        self.pages = QtWidgets.QStackedWidget()
        self.pages.setObjectName("ReportsPages")

        self.pages.addWidget(self._build_overview_page())
        self.pages.addWidget(self._build_by_user_page())
        self.pages.addWidget(self._build_by_site_page())
        self.pages.addWidget(self._build_games_page())
        self.pages.addWidget(self._build_cashback_page())
        self.pages.addWidget(self._build_time_flow_page())
        self.pages.addWidget(self._build_balances_page())
        self.pages.addWidget(self._build_tax_page())
        self.pages.addWidget(self._build_builder_page())

        main.addWidget(self.pages, 1)

        main_wrap = QtWidgets.QWidget()
        main_wrap.setLayout(main)
        main_wrap.setObjectName("ReportsMain")
        root.addWidget(main_wrap, 1)

        # Wiring nav → pages
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self._load_filter_options()
        self.refresh_data()

    def _register_kpi(self, grid: QtWidgets.QGridLayout, row: int, col: int, title: str, key: Optional[str] = None) -> QtWidgets.QLabel:
        card = _card(title)
        grid.addWidget(card, row, col)
        value_label = card.findChild(QtWidgets.QLabel, "KpiValue")
        if value_label is None:
            value_label = QtWidgets.QLabel("—")
            card.layout().addWidget(value_label)
        if key:
            self.kpi_labels[key] = value_label
        return value_label

    def _format_currency(self, value: Decimal) -> str:
        return f"${value:,.2f}"

    def _set_range_days(self, days: int) -> None:
        today = date.today()
        start = today - timedelta(days=days)
        self.date_filter.start_date.setText(start.strftime("%m/%d/%y"))
        self.date_filter.end_date.setText(today.strftime("%m/%d/%y"))
        self.date_filter.filter_changed.emit()

    def _set_month_to_date(self) -> None:
        today = date.today()
        start = date(today.year, today.month, 1)
        self.date_filter.start_date.setText(start.strftime("%m/%d/%y"))
        self.date_filter.end_date.setText(today.strftime("%m/%d/%y"))
        self.date_filter.filter_changed.emit()

    def _set_year_to_date(self) -> None:
        today = date.today()
        start = date(today.year, 1, 1)
        self.date_filter.start_date.setText(start.strftime("%m/%d/%y"))
        self.date_filter.end_date.setText(today.strftime("%m/%d/%y"))
        self.date_filter.filter_changed.emit()

    def _build_overview_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        trend = _panel("Net P/L Trend (placeholder)")
        trend.layout().addWidget(QtWidgets.QLabel("Trend chart placeholder"))

        composition = _panel("Composition (Users vs Sites vs Games)")
        composition.layout().addWidget(QtWidgets.QLabel("Composition placeholder"))

        drivers = _panel("Top Drivers")
        drivers_tabs = QtWidgets.QTabWidget()

        self.overview_users_table = QtWidgets.QTableWidget(0, 3)
        self.overview_users_table.setHorizontalHeaderLabels(["User", "Net P/L", "Net + Cashback"])
        self.overview_users_table.horizontalHeader().setStretchLastSection(True)

        self.overview_sites_table = QtWidgets.QTableWidget(0, 3)
        self.overview_sites_table.setHorizontalHeaderLabels(["Site", "Net P/L", "Net + Cashback"])
        self.overview_sites_table.horizontalHeader().setStretchLastSection(True)

        self.overview_games_table = QtWidgets.QTableWidget(0, 2)
        self.overview_games_table.setHorizontalHeaderLabels(["Game", "Net P/L"])
        self.overview_games_table.horizontalHeader().setStretchLastSection(True)

        drivers_tabs.addTab(self.overview_users_table, "Top Users")
        drivers_tabs.addTab(self.overview_sites_table, "Top Sites")
        drivers_tabs.addTab(self.overview_games_table, "Top Games")
        drivers.layout().addWidget(drivers_tabs)

        grid.addWidget(trend, 0, 0, 1, 2)
        grid.addWidget(composition, 0, 2, 1, 2)
        grid.addWidget(drivers, 1, 0, 1, 4)

        return widget

    def _build_by_user_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        leaderboard = _panel("User Leaderboard")
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
        leaderboard.layout().addWidget(self.user_table)

        details = _panel("Selected User Details (optional)")
        details.layout().addWidget(QtWidgets.QLabel("Click a user row to populate this panel."))

        grid.addWidget(leaderboard, 0, 0, 1, 3)
        grid.addWidget(details, 0, 3, 1, 1)
        return widget

    def _build_by_site_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        leaderboard = _panel("Site Leaderboard")
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
        leaderboard.layout().addWidget(self.site_table)

        redeem_time = _panel("Redemption Time by Site (placeholder)")
        redeem_time.layout().addWidget(QtWidgets.QLabel("Chart or ranked list goes here."))

        grid.addWidget(leaderboard, 0, 0, 1, 3)
        grid.addWidget(redeem_time, 0, 3, 1, 1)
        return widget

    def _build_games_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        game_types = QtWidgets.QWidget()
        game_types_layout = QtWidgets.QVBoxLayout(game_types)
        game_types_layout.addWidget(_panel("Game Type Leaderboard"))
        game_types_layout.addWidget(QtWidgets.QTableWidget())

        games = QtWidgets.QWidget()
        games_layout = QtWidgets.QVBoxLayout(games)
        games_layout.addWidget(_panel("Game Leaderboard"))
        games_layout.addWidget(QtWidgets.QTableWidget())

        tabs.addTab(game_types, "Game Types")
        tabs.addTab(games, "Games")
        layout.addWidget(tabs)
        return widget

    def _build_cashback_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        for name in ("By Site", "By Card", "By User"):
            page = QtWidgets.QWidget()
            page_layout = QtWidgets.QVBoxLayout(page)
            page_layout.addWidget(_panel(f"Cashback {name}"))
            page_layout.addWidget(QtWidgets.QTableWidget())
            tabs.addTab(page, name)

        layout.addWidget(tabs)
        return widget

    def _build_time_flow_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        redemption_time = QtWidgets.QWidget()
        redemption_layout = QtWidgets.QVBoxLayout(redemption_time)
        redemption_layout.addWidget(_panel("Redemption Time (Avg/Median/P95)"))
        redemption_layout.addWidget(QtWidgets.QTableWidget())

        cadence = QtWidgets.QWidget()
        cadence_layout = QtWidgets.QVBoxLayout(cadence)
        cadence_layout.addWidget(_panel("Cadence (Sessions/Week, Redemptions/Week)"))
        cadence_layout.addWidget(QtWidgets.QLabel("Chart placeholder"))

        tabs.addTab(redemption_time, "Redemption Time")
        tabs.addTab(cadence, "Cadence")
        layout.addWidget(tabs)
        return widget

    def _build_balances_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        tabs = QtWidgets.QTabWidget()
        outstanding = QtWidgets.QWidget()
        outstanding_layout = QtWidgets.QVBoxLayout(outstanding)
        outstanding_layout.addWidget(_panel("Outstanding Balances (by Site/User/Card)"))
        outstanding_layout.addWidget(QtWidgets.QTableWidget())

        aging = QtWidgets.QWidget()
        aging_layout = QtWidgets.QVBoxLayout(aging)
        aging_layout.addWidget(_panel("Aging Buckets (0–7, 8–30, 31–90, 90+)"))
        aging_layout.addWidget(QtWidgets.QTableWidget())

        tabs.addTab(outstanding, "Outstanding")
        tabs.addTab(aging, "Aging")
        layout.addWidget(tabs)
        return widget

    def _build_tax_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        inputs = _panel("Tax Settings (what-if)")
        inputs.layout().addWidget(QtWidgets.QLabel("Filing method, rates, cashback treatment, withholding model…"))
        outputs = _panel("Tax Outputs")
        outputs.layout().addWidget(QtWidgets.QLabel("Post-tax KPIs + sensitivity table…"))

        grid.addWidget(inputs, 0, 0, 1, 2)
        grid.addWidget(outputs, 0, 2, 1, 2)
        return widget

    def _build_builder_page(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_panel("Custom Builder (phase 2)"))
        layout.addWidget(QtWidgets.QLabel("Choose grouping + measures + save report"))
        return widget

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

        self.card_combo.clear()
        self.card_combo.addItem("All", None)
        for card in self.facade.get_all_cards(active_only=False):
            self.card_combo.addItem(card.name, card.id)

        self.game_type_combo.clear()
        self.game_type_combo.addItem("All", None)
        for game_type in self.facade.get_all_game_types(active_only=False):
            self.game_type_combo.addItem(game_type.name, game_type.id)

        self.game_combo.clear()
        self.game_combo.addItem("All", None)
        for game in self.facade.list_all_games(active_only=False):
            self.game_combo.addItem(game.name, game.id)

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
            include_deleted=self.chk_soft_deleted.isChecked(),
        )

    def refresh_data(self) -> None:
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
            self._populate_overview_tables(user_rows, site_rows)
            self._apply_search_filter(self.search_edit.text())
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

    def _populate_overview_tables(self, user_rows, site_rows) -> None:
        self.overview_users_table.setRowCount(0)
        for row in user_rows[:10]:
            self._add_row(self.overview_users_table, [
                row.user_name,
                self._format_currency(row.session_net_pl),
                self._format_currency(row.session_net_pl + row.cashback),
            ])

        self.overview_sites_table.setRowCount(0)
        for row in site_rows[:10]:
            self._add_row(self.overview_sites_table, [
                row.site_name,
                self._format_currency(row.session_net_pl),
                self._format_currency(row.session_net_pl + row.cashback),
            ])

        self.overview_games_table.setRowCount(0)

    def _apply_search_filter(self, text: str) -> None:
        term = (text or "").strip().lower()
        current_index = self.pages.currentIndex()

        if not term:
            self._clear_table_filter(self.user_table)
            self._clear_table_filter(self.site_table)
            self._clear_table_filter(self.overview_users_table)
            self._clear_table_filter(self.overview_sites_table)
            return

        if current_index == 0:
            self._filter_table(self.overview_users_table, term)
            self._filter_table(self.overview_sites_table, term)
        elif current_index == 1:
            self._filter_table(self.user_table, term)
        elif current_index == 2:
            self._filter_table(self.site_table, term)

    def _filter_table(self, table: QtWidgets.QTableWidget, term: str) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            value = item.text().lower() if item else ""
            table.setRowHidden(row, term not in value)

    def _clear_table_filter(self, table: QtWidgets.QTableWidget) -> None:
        for row in range(table.rowCount()):
            table.setRowHidden(row, False)

    def _add_row(self, table: QtWidgets.QTableWidget, values: List[str]) -> None:
        row_idx = table.rowCount()
        table.insertRow(row_idx)
        for col_idx, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            if col_idx > 0:
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row_idx, col_idx, item)
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
