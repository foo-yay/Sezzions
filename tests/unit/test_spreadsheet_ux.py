"""Unit tests for spreadsheet UX module (Issue #14)."""

import pytest
from decimal import Decimal
from desktop.ui.spreadsheet_ux import SpreadsheetUXController, SelectionStats
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QTableWidgetSelectionRange,
)


class TestNumericParsing:
    """Test numeric value parsing with various formats."""
    
    def test_parse_simple_integer(self):
        assert SpreadsheetUXController.parse_numeric_value("123") == Decimal("123")
    
    def test_parse_simple_decimal(self):
        assert SpreadsheetUXController.parse_numeric_value("123.45") == Decimal("123.45")
    
    def test_parse_negative(self):
        assert SpreadsheetUXController.parse_numeric_value("-123.45") == Decimal("-123.45")
    
    def test_parse_currency_with_dollar_sign(self):
        assert SpreadsheetUXController.parse_numeric_value("$1,234.56") == Decimal("1234.56")
    
    def test_parse_currency_with_commas(self):
        assert SpreadsheetUXController.parse_numeric_value("1,234,567.89") == Decimal("1234567.89")
    
    def test_parse_accounting_negative_parentheses(self):
        assert SpreadsheetUXController.parse_numeric_value("(123.45)") == Decimal("-123.45")
    
    def test_parse_currency_negative_parentheses(self):
        assert SpreadsheetUXController.parse_numeric_value("$(1,234.56)") == Decimal("-1234.56")
    
    def test_parse_percentage(self):
        assert SpreadsheetUXController.parse_numeric_value("100%") == Decimal("100")
        assert SpreadsheetUXController.parse_numeric_value("12.5%") == Decimal("12.5")
    
    def test_parse_whitespace(self):
        assert SpreadsheetUXController.parse_numeric_value("  123.45  ") == Decimal("123.45")
    
    def test_parse_empty_string_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("") is None
    
    def test_parse_whitespace_only_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("   ") is None
    
    def test_parse_na_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("N/A") is None
        assert SpreadsheetUXController.parse_numeric_value("na") is None
        assert SpreadsheetUXController.parse_numeric_value("n/a") is None
    
    def test_parse_dash_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("-") is None
        assert SpreadsheetUXController.parse_numeric_value("—") is None
        assert SpreadsheetUXController.parse_numeric_value("–") is None
    
    def test_parse_text_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("abc") is None
        assert SpreadsheetUXController.parse_numeric_value("User") is None
    
    def test_parse_none_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value(None) is None
    
    def test_parse_mixed_text_and_numbers_returns_none(self):
        assert SpreadsheetUXController.parse_numeric_value("123abc") is None
        assert SpreadsheetUXController.parse_numeric_value("abc123") is None
    
    def test_parse_zero(self):
        assert SpreadsheetUXController.parse_numeric_value("0") == Decimal("0")
        assert SpreadsheetUXController.parse_numeric_value("0.00") == Decimal("0.00")
        assert SpreadsheetUXController.parse_numeric_value("$0.00") == Decimal("0.00")


class TestTSVFormatting:
    """Test TSV (Tab-Separated Values) formatting."""
    
    def test_format_single_row(self):
        grid = [["A", "B", "C"]]
        assert SpreadsheetUXController.format_as_tsv(grid) == "A\tB\tC"
    
    def test_format_multiple_rows(self):
        grid = [
            ["A", "B", "C"],
            ["1", "2", "3"],
            ["X", "Y", "Z"]
        ]
        assert SpreadsheetUXController.format_as_tsv(grid) == "A\tB\tC\n1\t2\t3\nX\tY\tZ"
    
    def test_format_empty_grid(self):
        assert SpreadsheetUXController.format_as_tsv([]) == ""
    
    def test_format_with_empty_cells(self):
        grid = [["A", "", "C"], ["1", "2", ""]]
        assert SpreadsheetUXController.format_as_tsv(grid) == "A\t\tC\n1\t2\t"
    
    def test_format_preserves_spaces_within_cells(self):
        grid = [["Hello World", "Test Value"]]
        assert SpreadsheetUXController.format_as_tsv(grid) == "Hello World\tTest Value"


class TestSelectionStats:
    """Test selection statistics computation."""
    
    def test_stats_all_numeric(self):
        grid = [
            ["100", "200", "300"],
            ["50", "150", "250"]
        ]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.count == 6
        assert stats.numeric_count == 6
        assert stats.sum == Decimal("1050")
        assert stats.avg == Decimal("175")
        assert stats.min_val == Decimal("50")
        assert stats.max_val == Decimal("300")
    
    def test_stats_mixed_numeric_and_text(self):
        grid = [
            ["User A", "$100.00", "N/A"],
            ["User B", "$200.50", "Active"]
        ]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.count == 6
        assert stats.numeric_count == 2
        assert stats.sum == Decimal("300.50")
        assert stats.avg == Decimal("150.25")
        assert stats.min_val == Decimal("100.00")
        assert stats.max_val == Decimal("200.50")
    
    def test_stats_no_numeric_values(self):
        grid = [
            ["User A", "Active", "Notes"],
            ["User B", "Inactive", "More notes"]
        ]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.count == 6
        assert stats.numeric_count == 0
        assert stats.sum == Decimal("0")
        assert stats.avg is None
        assert stats.min_val is None
        assert stats.max_val is None
    
    def test_stats_empty_grid(self):
        stats = SpreadsheetUXController.compute_stats([])
        
        assert stats.count == 0
        assert stats.numeric_count == 0
        assert stats.sum == Decimal("0")
        assert stats.avg is None
    
    def test_stats_handles_currency_formatting(self):
        grid = [["$1,234.56", "$(500.00)", "$750.00"]]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.numeric_count == 3
        assert stats.sum == Decimal("1484.56")
        assert stats.min_val == Decimal("-500.00")
        assert stats.max_val == Decimal("1234.56")
    
    def test_stats_handles_empty_cells(self):
        grid = [
            ["100", "", "300"],
            ["", "200", ""]
        ]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.count == 6
        assert stats.numeric_count == 3
        assert stats.sum == Decimal("600")
        assert stats.avg == Decimal("200")
    
    def test_stats_repr_with_numeric_values(self):
        grid = [["100", "200", "300"]]
        stats = SpreadsheetUXController.compute_stats(grid)
        repr_str = repr(stats)
        
        assert "Count: 3" in repr_str
        assert "Numeric: 3" in repr_str
        assert "Sum: 600.00" in repr_str
        assert "Avg: 200.00" in repr_str
        assert "Min: 100.00" in repr_str
        assert "Max: 300.00" in repr_str
    
    def test_stats_repr_without_numeric_values(self):
        grid = [["A", "B", "C"]]
        stats = SpreadsheetUXController.compute_stats(grid)
        repr_str = repr(stats)
        
        assert repr_str == "Count: 3"
    
    def test_stats_single_value(self):
        grid = [["$42.00"]]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.count == 1
        assert stats.numeric_count == 1
        assert stats.sum == Decimal("42.00")
        assert stats.avg == Decimal("42.00")
        assert stats.min_val == Decimal("42.00")
        assert stats.max_val == Decimal("42.00")
    
    def test_stats_negative_values(self):
        grid = [["-100", "-50", "200"]]
        stats = SpreadsheetUXController.compute_stats(grid)
        
        assert stats.sum == Decimal("50")
        # Check average with tolerance for Decimal precision
        assert abs(stats.avg - Decimal("16.67")) < Decimal("0.01")
        assert stats.min_val == Decimal("-100")
        assert stats.max_val == Decimal("200")


class TestTableSelectionExtraction:
    def test_hidden_rows_in_range_selection_are_ignored(self):
        app = QApplication.instance() or QApplication([])
        _ = app  # Keep reference for test lifetime

        table = QTableWidget(3, 1)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)

        table.setItem(0, 0, QTableWidgetItem("8.99"))
        table.setItem(1, 0, QTableWidgetItem("17.99"))
        table.setItem(2, 0, QTableWidgetItem("17.99"))

        table.setRowHidden(1, True)

        # Simulate shift-click style range selection spanning a hidden row.
        table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 2, 0), True)

        grid = SpreadsheetUXController.extract_selection_grid(table)
        stats = SpreadsheetUXController.compute_stats(grid)

        assert stats.numeric_count == 2
        assert stats.sum == Decimal("26.98")
