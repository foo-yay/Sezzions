"""Reports Tab - structured desktop reports rendered inside Setup."""
from collections import OrderedDict
from decimal import Decimal

from PySide6 import QtWidgets
from PySide6.QtCore import Qt


class ReportsTab(QtWidgets.QWidget):
    """Setup sub-tab for running and viewing desktop reports."""

    def __init__(self, app_facade, parent=None):
        super().__init__(parent)
        self.facade = app_facade
        self._report_configs = OrderedDict({
            "bridge_reconciliation_summary": {
                "name": "Bridge / Reconciliation Summary",
                "description": "Site-level basis roll-forward plus the gap between economic P/L and session taxable P/L.",
                "runner": self._run_bridge_reconciliation_summary,
            },
            "session_pl_summary": {
                "name": "Session P/L Summary",
                "description": "High-level win/loss totals and session performance across all recorded sessions.",
                "runner": self._run_session_pl_summary,
            },
        })
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("ReportsTabBackground")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Reports")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setFixedWidth(0)
        self.search_edit.setMaximumWidth(0)
        header_layout.addWidget(self.search_edit)

        dummy_clear = QtWidgets.QPushButton("Clear")
        dummy_clear.setFixedWidth(0)
        dummy_clear.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear)

        dummy_clear_filters = QtWidgets.QPushButton("Clear All Filters")
        dummy_clear_filters.setFixedWidth(0)
        dummy_clear_filters.setMaximumWidth(0)
        header_layout.addWidget(dummy_clear_filters)

        layout.addLayout(header_layout)

        controls_card = QtWidgets.QWidget()
        controls_card.setObjectName("SectionBackground")
        controls_layout = QtWidgets.QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)

        intro = QtWidgets.QLabel(
            "Run built-in reports here. The selector is designed to hold additional reports without changing the tab layout."
        )
        intro.setObjectName("HelperText")
        intro.setWordWrap(True)
        controls_layout.addWidget(intro)

        selector_row = QtWidgets.QHBoxLayout()
        selector_row.addWidget(QtWidgets.QLabel("Report"))

        self.report_selector = QtWidgets.QComboBox()
        for report_key, config in self._report_configs.items():
            self.report_selector.addItem(config["name"], report_key)
        self.report_selector.currentIndexChanged.connect(self._sync_report_metadata)
        selector_row.addWidget(self.report_selector, 1)

        self.run_button = QtWidgets.QPushButton("Run Report")
        self.run_button.clicked.connect(self.run_selected_report)
        selector_row.addWidget(self.run_button)
        controls_layout.addLayout(selector_row)

        self.report_description = QtWidgets.QLabel()
        self.report_description.setObjectName("HelperText")
        self.report_description.setWordWrap(True)
        controls_layout.addWidget(self.report_description)

        layout.addWidget(controls_card)

        results_card = QtWidgets.QWidget()
        results_card.setObjectName("SectionBackground")
        results_layout = QtWidgets.QVBoxLayout(results_card)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(10)

        self.report_title = QtWidgets.QLabel("Report Output")
        self.report_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        results_layout.addWidget(self.report_title)

        self.report_status = QtWidgets.QLabel("Select a report and click Run Report.")
        self.report_status.setObjectName("HelperText")
        self.report_status.setWordWrap(True)
        results_layout.addWidget(self.report_status)

        self.results_table = QtWidgets.QTableWidget(0, 2)
        self.results_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.results_table.setSelectionMode(QtWidgets.QTableWidget.NoSelection)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        results_layout.addWidget(self.results_table, 1)

        self.empty_state = QtWidgets.QLabel("No report results yet.")
        self.empty_state.setObjectName("HelperText")
        self.empty_state.setAlignment(Qt.AlignCenter)
        results_layout.addWidget(self.empty_state)

        layout.addWidget(results_card, 1)

        self._sync_report_metadata()
        self._render_report([], ["Metric", "Value"], "Select a report and click Run Report.")

    def focus_search(self):
        """Match Setup sub-tab shortcut routing by focusing the report selector."""
        self.report_selector.setFocus()

    def refresh_data(self):
        """Refresh the visible report output when the Setup tab is refreshed."""
        if self.results_table.rowCount() > 0:
            self.run_selected_report()

    def run_selected_report(self):
        """Run the currently selected report and display the output below."""
        report_key = self.report_selector.currentData()
        config = self._report_configs.get(report_key)
        if not config:
            self._render_report([], ["Metric", "Value"], "No report is configured for the current selection.")
            return

        report = config["runner"]()
        self.report_title.setText(config["name"])
        self._render_report(
            report["rows"],
            report["columns"],
            report.get("status", f"Showing the latest {config['name'].lower()} output."),
        )

    def _sync_report_metadata(self):
        report_key = self.report_selector.currentData()
        config = self._report_configs.get(report_key)
        if not config:
            self.report_description.setText("")
            return

        self.report_description.setText(config["description"])

    def _run_session_pl_summary(self):
        report = self.facade.get_session_pl_report()
        return {
            "columns": ["Metric", "Value"],
            "rows": [
                ["Total Sessions", str(report["total_sessions"])],
                ["Total P/L", self._format_currency(report["total_pl"])],
                ["Average P/L", self._format_currency(report["average_pl"])],
                ["Winning Sessions", str(report["winning_sessions"])],
                ["Losing Sessions", str(report["losing_sessions"])],
                ["Win Rate", f"{report['win_rate']:.1f}%"],
                ["Best Session", self._format_currency(report["best_session"])],
                ["Worst Session", self._format_currency(report["worst_session"])],
            ],
        }

    def _run_bridge_reconciliation_summary(self):
        report = self.facade.get_bridge_reconciliation_report()
        rows = []

        for site_row in report["site_rows"]:
            rows.append([
                site_row["site_name"],
                self._format_currency(site_row["total_purchases"]),
                self._format_currency(site_row["redeemed_basis"]),
                self._format_currency(site_row["open_basis"]),
                self._format_currency(site_row["basis_delta"]),
                self._format_currency(site_row["realized_pl"]),
                self._format_currency(site_row["economic_pl"]),
                self._format_currency(site_row["session_pl"]),
                self._format_currency(site_row["bridge_gap"]),
            ])

        totals = report["totals"]
        rows.append([
            "All Sites",
            self._format_currency(totals["total_purchases"]),
            self._format_currency(totals["redeemed_basis"]),
            self._format_currency(totals["open_basis"]),
            self._format_currency(totals["basis_delta"]),
            self._format_currency(totals["realized_pl"]),
            self._format_currency(totals["economic_pl"]),
            self._format_currency(totals["session_pl"]),
            self._format_currency(totals["bridge_gap"]),
        ])

        return {
            "columns": [
                "Site",
                "Purchases",
                "Redeemed Basis",
                "Open Basis",
                "Basis Delta",
                "Realized P/L",
                "Economic P/L",
                "Session P/L",
                "Bridge Gap",
            ],
            "rows": rows,
            "status": "Basis Delta should normally stay near $0.00. Bridge Gap shows the difference between economic P/L and session taxable P/L.",
        }

    def _render_report(self, rows, columns, status_text):
        self.results_table.clear()
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(rows))

        for row_idx, row_values in enumerate(rows):
            for col_idx, value in enumerate(row_values):
                self.results_table.setItem(row_idx, col_idx, QtWidgets.QTableWidgetItem(value))

        self.results_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.results_table.setVisible(bool(rows))
        self.empty_state.setVisible(not rows)
        self.report_status.setText(status_text)

    @staticmethod
    def _format_currency(value):
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        return f"${amount:,.2f}"