"""Reports tab for structured desktop reporting inside Setup."""
from collections import OrderedDict
from datetime import date
from decimal import Decimal
import csv

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from desktop.ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from desktop.ui.spreadsheet_ux import SpreadsheetUXController
from desktop.ui.table_header_filters import TableHeaderFilter


class ReportsTab(QtWidgets.QWidget):
    """Setup sub-tab for running and viewing reports."""

    def __init__(self, app_facade, parent=None):
        super().__init__(parent)
        self.facade = app_facade
        self._current_report_rows = []
        self._current_report_columns = []
        self._current_report_status_text = ""
        self._current_report_footer_note = ""
        self._current_report_kind = ""
        self._current_explanation_details = {}
        self._report_configs = OrderedDict(
            {
                "bridge_reconciliation_summary": {
                    "name": "Bridge / Reconciliation Summary",
                    "description": "User/site basis roll-forward plus the gap between economic P/L and session taxable P/L.",
                    "runner": self._run_bridge_reconciliation_summary,
                },
                "session_pl_summary": {
                    "name": "Session P/L Summary",
                    "description": "High-level win/loss totals and session performance across all recorded sessions.",
                    "runner": self._run_session_pl_summary,
                },
            }
        )
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("ToolsTabBackground")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Reports")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search report rows...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self._filter_rows)
        header_layout.addWidget(self.search_edit)

        self.clear_search_btn = QtWidgets.QPushButton("Clear")
        self.clear_search_btn.clicked.connect(self._clear_search)
        header_layout.addWidget(self.clear_search_btn)

        self.clear_filters_btn = QtWidgets.QPushButton("Clear All Filters")
        self.clear_filters_btn.clicked.connect(self._clear_all_filters)
        header_layout.addWidget(self.clear_filters_btn)

        layout.addLayout(header_layout)

        intro = QtWidgets.QLabel(
            "Run built-in reports here. Green means the basis roll-forward closes mathematically. Bridge Gap is informational only."
        )
        intro.setStyleSheet("color: #666; font-style: italic;")
        intro.setWordWrap(True)
        
        content_section = QtWidgets.QFrame()
        content_section.setObjectName("SectionBackground")
        content_layout = QtWidgets.QVBoxLayout(content_section)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(10)
        content_layout.addWidget(intro)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(QtWidgets.QLabel("Report"))

        self.report_selector = QtWidgets.QComboBox()
        for report_key, config in self._report_configs.items():
            self.report_selector.addItem(config["name"], report_key)
        self.report_selector.currentIndexChanged.connect(self._sync_report_metadata)
        toolbar.addWidget(self.report_selector, 1)

        self.run_button = QtWidgets.QPushButton("Run Report")
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.clicked.connect(self.run_selected_report)
        toolbar.addWidget(self.run_button)

        toolbar.addStretch()

        self.export_btn = QtWidgets.QPushButton("📤 Export CSV")
        self.export_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(self.export_btn)

        self.refresh_btn = QtWidgets.QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.run_selected_report)
        toolbar.addWidget(self.refresh_btn)

        content_layout.addLayout(toolbar)

        self.report_description = QtWidgets.QLabel()
        self.report_description.setStyleSheet("color: #666; font-style: italic;")
        self.report_description.setWordWrap(True)
        content_layout.addWidget(self.report_description)

        self.report_title = QtWidgets.QLabel("Report Output")
        self.report_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        content_layout.addWidget(self.report_title)

        self.report_status = QtWidgets.QLabel("Select a report and click Run Report.")
        self.report_status.setStyleSheet("color: #666;")
        self.report_status.setWordWrap(True)
        content_layout.addWidget(self.report_status)

        self.results_table = QtWidgets.QTableWidget()
        self.results_table.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        self.results_table.setSelectionBehavior(QtWidgets.QTableWidget.SelectItems)
        self.results_table.setSelectionMode(QtWidgets.QTableWidget.ExtendedSelection)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.results_table.itemDoubleClicked.connect(self._handle_item_double_clicked)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        content_layout.addWidget(self.results_table, 1)

        self.empty_state = QtWidgets.QLabel("No report results yet.")
        self.empty_state.setStyleSheet("color: #666;")
        self.empty_state.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.empty_state)

        self.stats_bar = SpreadsheetStatsBar()
        content_layout.addWidget(self.stats_bar)

        totals_layout = QtWidgets.QHBoxLayout()
        self.totals_label = QtWidgets.QLabel()
        self.totals_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        totals_layout.addWidget(self.totals_label)
        totals_layout.addStretch()
        content_layout.addLayout(totals_layout)

        self.report_notes_label = QtWidgets.QLabel()
        self.report_notes_label.setStyleSheet("color: #666;")
        self.report_notes_label.setWordWrap(True)
        content_layout.addWidget(self.report_notes_label)

        layout.addWidget(content_section, 1)

        self.table_filter = None
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Copy, self.results_table)
        copy_shortcut.activated.connect(self._copy_selection)

        self._sync_report_metadata()
        self._render_report([], ["Metric", "Value"], "Select a report and click Run Report.")

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def refresh_data(self):
        if self.results_table.rowCount() > 0 or self._current_report_rows:
            self.run_selected_report()

    def run_selected_report(self):
        report_key = self.report_selector.currentData()
        config = self._report_configs.get(report_key)
        if not config:
            self._render_report([], ["Metric", "Value"], "No report is configured for the current selection.")
            return

        report = config["runner"]()
        self.report_title.setText(config["name"])
        self._current_report_footer_note = report.get("footer_note", "")
        self._render_report(
            report["rows"],
            report["columns"],
            report.get("status", f"Showing the latest {config['name'].lower()} output."),
        )

    def _sync_report_metadata(self):
        report_key = self.report_selector.currentData()
        config = self._report_configs.get(report_key)
        self.report_description.setText(config["description"] if config else "")

    def _run_session_pl_summary(self):
        self._current_report_kind = "session_pl_summary"
        self._current_explanation_details = {}
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
            "footer_note": "Session P/L Summary is descriptive only. It does not determine whether basis accounting closes cleanly.",
        }

    def _run_bridge_reconciliation_summary(self):
        self._current_report_kind = "bridge_reconciliation_summary"
        report = self.facade.get_bridge_reconciliation_report()
        rows = []
        self._current_explanation_details = {}

        for site_row in report["site_rows"]:
            basis_ok = abs(site_row["basis_delta"]) < Decimal("0.005")
            self._current_explanation_details[(site_row["site_name"], site_row["user_name"])] = site_row.get(
                "bridge_gap_detail",
                site_row["bridge_gap_explanation"],
            )
            rows.append(
                [
                    "Checks Out" if basis_ok else "Needs Review",
                    site_row["site_name"],
                    site_row["user_name"],
                    self._format_currency(site_row["total_purchases"]),
                    self._format_currency(site_row["redeemed_basis"]),
                    self._format_currency(site_row["open_basis"]),
                    self._format_currency(site_row["basis_delta"]),
                    self._format_currency(site_row["realized_pl"]),
                    self._format_currency(site_row["economic_pl"]),
                    self._format_currency(site_row["session_pl"]),
                    self._format_currency(site_row["bridge_gap"]),
                    site_row["bridge_gap_explanation"],
                ]
            )

        return {
            "columns": [
                "Status",
                "Site",
                "User",
                "Purchases",
                "Redeemed Basis",
                "Open Basis",
                "Basis Delta",
                "Realized P/L",
                "Economic P/L",
                "Session P/L",
                "Current Gap",
                "Explanation",
            ],
            "rows": rows,
            "status": "Green status means Purchases = Redeemed Basis + Open Basis for that user/site row. Current Gap is the actionable present-state gap after suppressing older close-marker residue that was reactivated by later play for that same user/site pair. Explanation amounts sum to Current Gap. Double-click an Explanation cell for the full narrative.",
            "footer_note": "Basis Delta values of $0.00 and -$0.00 mean the same thing. Negative zero is rounding noise and is normalized to $0.00 in this view.",
        }

    def _render_report(self, rows, columns, status_text):
        self._current_report_columns = list(columns)
        self._current_report_rows = [list(row) for row in rows]
        self._current_report_status_text = status_text
        self._refresh_visible_rows()

    def _refresh_visible_rows(self):
        self._populate_table(self._visible_rows())

    def _populate_table(self, rows):
        previous_filters = dict(self.table_filter.column_filters) if self.table_filter is not None else {}
        previous_sort_column = self.table_filter.sort_column if self.table_filter is not None else None
        previous_sort_order = self.table_filter.sort_order if self.table_filter is not None else Qt.AscendingOrder

        sorting_was_enabled = self.results_table.isSortingEnabled()
        self.results_table.setSortingEnabled(False)
        self.results_table.setUpdatesEnabled(False)
        self.results_table.blockSignals(True)
        try:
            self.results_table.clearContents()
            columns = self._current_report_columns or ["Metric", "Value"]
            self.results_table.setColumnCount(len(columns))
            self.results_table.setHorizontalHeaderLabels(columns)
            self.results_table.setRowCount(len(rows))

            for row_idx, row_values in enumerate(rows):
                for col_idx, value in enumerate(row_values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    if self._is_numeric_column(col_idx):
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.results_table.setItem(row_idx, col_idx, item)
                self._decorate_row(row_idx)
        finally:
            self.results_table.blockSignals(False)
            self.results_table.setUpdatesEnabled(True)

        if previous_sort_column is not None and previous_sort_column < self.results_table.columnCount():
            self.table_filter.sort_by_column(previous_sort_column, previous_sort_order)
        else:
            self.results_table.setSortingEnabled(sorting_was_enabled)
            header = self.results_table.horizontalHeader()
            if header is not None:
                header.setSortIndicatorShown(False)

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        self.table_filter = TableHeaderFilter(self.results_table, refresh_callback=self._refresh_visible_rows)
        self.table_filter.column_filters = {
            col: values for col, values in previous_filters.items() if col < self.results_table.columnCount()
        }
        self.table_filter.apply_filters()

        self._attach_explanation_details(rows)

        self.results_table.setVisible(bool(rows))
        self.empty_state.setVisible(not rows)
        self.report_status.setText(self._current_report_status_text)
        self.report_notes_label.setText(self._current_report_footer_note)
        self._update_footer(rows)

    def _filter_rows(self, _text):
        self._refresh_visible_rows()

    def _visible_rows(self):
        search_text = self.search_edit.text().strip().lower()
        if not search_text:
            return [list(row) for row in self._current_report_rows]

        return [
            list(row)
            for row in self._current_report_rows
            if any(search_text in str(value).lower() for value in row)
        ]

    def _clear_search(self):
        self.search_edit.clear()
        self.results_table.clearSelection()
        self._on_selection_changed()
        self._refresh_visible_rows()

    def _clear_all_filters(self):
        self.search_edit.clear()
        self.results_table.clearSelection()
        self._on_selection_changed()
        if self.table_filter is not None:
            self.table_filter.clear_all_filters()
        self._refresh_visible_rows()

    def _decorate_row(self, row_idx):
        if "Status" in self._current_report_columns:
            status_col = self._current_report_columns.index("Status")
            status_item = self.results_table.item(row_idx, status_col)
            if status_item is not None:
                if status_item.text() == "Checks Out":
                    status_item.setForeground(QtGui.QColor("#138a36"))
                else:
                    status_item.setForeground(QtGui.QColor("#b42318"))

        if "Basis Delta" in self._current_report_columns:
            delta_col = self._current_report_columns.index("Basis Delta")
            delta_item = self.results_table.item(row_idx, delta_col)
            if delta_item is not None:
                if delta_item.text() == "$0.00":
                    delta_item.setForeground(QtGui.QColor("#138a36"))
                else:
                    delta_item.setForeground(QtGui.QColor("#b42318"))

    def _update_footer(self, rows):
        if not rows:
            self.totals_label.setText("")
            self.stats_bar.clear_stats()
            return

        if "Status" in self._current_report_columns and "Basis Delta" in self._current_report_columns:
            status_col = self._current_report_columns.index("Status")
            basis_col = self._current_report_columns.index("Basis Delta")
            checks_out = sum(1 for row in rows if row[status_col] == "Checks Out")
            needs_review = sum(1 for row in rows if row[status_col] != "Checks Out")
            self.totals_label.setText(
                f"Rows: {len(rows)} | Checks Out: {checks_out} | Needs Review: {needs_review} | Basis Delta Total: {self._sum_currency_column(rows, basis_col)}"
            )
            return

        self.totals_label.setText(f"Rows: {len(rows)}")

    def _sum_currency_column(self, rows, col_idx):
        total = Decimal("0.00")
        for row in rows:
            total += self._parse_currency(row[col_idx])
        return self._format_currency(total)

    def _on_selection_changed(self):
        if self.results_table.selectionModel().hasSelection():
            grid = SpreadsheetUXController.extract_selection_grid(self.results_table)
            stats = SpreadsheetUXController.compute_stats(grid)
            self.stats_bar.update_stats(stats)
            return

        self.stats_bar.clear_stats()

    def _copy_selection(self):
        grid = SpreadsheetUXController.extract_selection_grid(self.results_table)
        SpreadsheetUXController.copy_to_clipboard(grid)

    def _copy_with_headers(self):
        grid = SpreadsheetUXController.extract_selection_grid(self.results_table, include_headers=True)
        SpreadsheetUXController.copy_to_clipboard(grid)

    def _show_context_menu(self, position):
        if not self.results_table.selectionModel().hasSelection():
            return

        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("Copy")
        copy_action.setShortcut(QtGui.QKeySequence.Copy)
        copy_action.triggered.connect(self._copy_selection)

        copy_headers_action = menu.addAction("Copy With Headers")
        copy_headers_action.triggered.connect(self._copy_with_headers)

        menu.exec(self.results_table.viewport().mapToGlobal(position))

    def _attach_explanation_details(self, rows):
        if self._current_report_kind != "bridge_reconciliation_summary":
            return
        if (
            "Explanation" not in self._current_report_columns
            or "Site" not in self._current_report_columns
            or "User" not in self._current_report_columns
        ):
            return

        explanation_col = self._current_report_columns.index("Explanation")
        site_col = self._current_report_columns.index("Site")
        user_col = self._current_report_columns.index("User")
        for row_idx, row_values in enumerate(rows):
            explanation_item = self.results_table.item(row_idx, explanation_col)
            if explanation_item is None:
                continue
            site_name = str(row_values[site_col])
            user_name = str(row_values[user_col])
            detail = self._current_explanation_details.get((site_name, user_name), explanation_item.text())
            explanation_item.setData(Qt.UserRole, detail)
            explanation_item.setToolTip("Double-click to view the full audit trail")

    def _handle_item_double_clicked(self, item):
        if self._current_report_kind != "bridge_reconciliation_summary":
            return
        if (
            "Explanation" not in self._current_report_columns
            or "Site" not in self._current_report_columns
            or "User" not in self._current_report_columns
        ):
            return

        explanation_col = self._current_report_columns.index("Explanation")
        if item.column() != explanation_col:
            return

        site_col = self._current_report_columns.index("Site")
        user_col = self._current_report_columns.index("User")
        site_item = self.results_table.item(item.row(), site_col)
        user_item = self.results_table.item(item.row(), user_col)
        if site_item is None or user_item is None:
            return

        site_name = site_item.text()
        user_name = user_item.text()
        detail = item.data(Qt.UserRole) or item.text()
        self._show_explanation_dialog(site_name, user_name, item.text(), detail)

    def _show_explanation_dialog(self, site_name, user_name, summary, detail):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"{site_name} / {user_name} Bridge Gap Audit")
        dialog.resize(760, 420)

        layout = QtWidgets.QVBoxLayout(dialog)

        summary_label = QtWidgets.QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(summary_label)

        detail_view = QtWidgets.QTextEdit(dialog)
        detail_view.setReadOnly(True)
        detail_view.setPlainText(detail)
        layout.addWidget(detail_view, 1)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close, parent=dialog)
        button_box.rejected.connect(dialog.reject)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        dialog.exec()

    def _export_csv(self):
        if self.results_table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Export", "No data to export")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Report",
            f"report_{date.today().isoformat()}.csv",
            "CSV Files (*.csv)",
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                headers = [
                    self.results_table.horizontalHeaderItem(column).text()
                    for column in range(self.results_table.columnCount())
                ]
                writer.writerow(headers)
                for row in range(self.results_table.rowCount()):
                    if self.results_table.isRowHidden(row):
                        continue
                    writer.writerow(
                        [
                            self.results_table.item(row, column).text()
                            if self.results_table.item(row, column)
                            else ""
                            for column in range(self.results_table.columnCount())
                        ]
                    )
            QtWidgets.QMessageBox.information(self, "Export Complete", f"Exported report to:\n{filename}")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to export:\n{exc}")

    def _is_numeric_column(self, col_idx):
        if not self._current_report_columns:
            return False
        column_name = self._current_report_columns[col_idx]
        return column_name not in {"Metric", "Status", "Site", "User", "Explanation"}

    @staticmethod
    def _format_currency(value):
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if abs(amount) < Decimal("0.005"):
            amount = Decimal("0.00")
        return f"${amount:,.2f}"

    @staticmethod
    def _parse_currency(value):
        text = str(value).replace("$", "").replace(",", "")
        if not text:
            return Decimal("0.00")
        return Decimal(text)
