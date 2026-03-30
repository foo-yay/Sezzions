"""
Unit tests for SpreadsheetStatsBar widget.
"""

import pytest
from PySide6.QtWidgets import QApplication
from decimal import Decimal

from desktop.ui.spreadsheet_stats_bar import SpreadsheetStatsBar
from desktop.ui.spreadsheet_ux import SelectionStats


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestSpreadsheetStatsBar:
    """Test cases for SpreadsheetStatsBar widget."""
    
    def test_init_shows_zero_count(self, qapp):
        """Initial state should show Count: 0."""
        bar = SpreadsheetStatsBar()
        assert "Count: 0" in bar._count_label.text()
        
    def test_init_hides_numeric_stats(self, qapp):
        """Initial state should hide numeric stats labels."""
        bar = SpreadsheetStatsBar()
        assert not bar._numeric_count_label.isVisible()
        assert not bar._sum_label.isVisible()
        assert not bar._avg_label.isVisible()
        assert not bar._min_label.isVisible()
        assert not bar._max_label.isVisible()
        
    def test_update_stats_with_numeric_values(self, qapp):
        """Updating with numeric stats should show all labels."""
        bar = SpreadsheetStatsBar()
        bar.show()  # Need to show widget for child widgets to be visible
        stats = SelectionStats()
        stats.count = 5
        stats.numeric_count = 3
        stats.sum = Decimal("150.00")  # avg will be 50.00 (computed)
        stats.min_val = Decimal("10.00")
        stats.max_val = Decimal("90.00")
        bar.update_stats(stats)
        
        assert "Count: 5" in bar._count_label.text()
        assert "Numeric: 3" in bar._numeric_count_label.text()
        assert "Sum: 150.00" in bar._sum_label.text()
        assert "Avg: 50.00" in bar._avg_label.text()  # 150/3 = 50
        assert "Min: 10.00" in bar._min_label.text()
        assert "Max: 90.00" in bar._max_label.text()
        
        assert bar._numeric_count_label.isVisible()
        assert bar._sum_label.isVisible()
        assert bar._avg_label.isVisible()
        assert bar._min_label.isVisible()
        assert bar._max_label.isVisible()
        
    def test_update_stats_without_numeric_values(self, qapp):
        """Updating with no numeric values should hide numeric stats."""
        bar = SpreadsheetStatsBar()
        stats = SelectionStats()
        stats.count = 5
        stats.numeric_count = 0
        # avg is computed, so don't set it
        bar.update_stats(stats)
        
        assert "Count: 5" in bar._count_label.text()
        assert not bar._numeric_count_label.isVisible()
        assert not bar._sum_label.isVisible()
        assert not bar._avg_label.isVisible()
        assert not bar._min_label.isVisible()
        assert not bar._max_label.isVisible()
        
    def test_clear_stats(self, qapp):
        """clear_stats() should reset to initial state."""
        bar = SpreadsheetStatsBar()
        
        # Set some stats first
        stats = SelectionStats()
        stats.count = 3
        stats.numeric_count = 3
        stats.sum = Decimal("99")  # avg will be 33
        stats.min_val = Decimal("10")
        stats.max_val = Decimal("50")
        bar.update_stats(stats)
        
        # Now clear
        bar.clear_stats()
        
        assert "Count: 0" in bar._count_label.text()
        assert not bar._numeric_count_label.isVisible()
        assert not bar._sum_label.isVisible()
        assert not bar._avg_label.isVisible()
        assert not bar._min_label.isVisible()
        assert not bar._max_label.isVisible()
        
    def test_currency_formatting_with_commas(self, qapp):
        """Large numbers should be formatted with commas."""
        bar = SpreadsheetStatsBar()
        stats = SelectionStats()
        stats.count = 3
        stats.numeric_count = 3
        stats.sum = Decimal("12345.66")  # avg will be 4115.22
        stats.min_val = Decimal("1000.00")
        stats.max_val = Decimal("10000.00")
        bar.update_stats(stats)
        
        assert "Sum: 12,345.66" in bar._sum_label.text()
        assert "Avg: 4,115.22" in bar._avg_label.text()
        assert "Min: 1,000.00" in bar._min_label.text()
        assert "Max: 10,000.00" in bar._max_label.text()
        
    def test_negative_values(self, qapp):
        """Negative values should display with minus sign."""
        bar = SpreadsheetStatsBar()
        stats = SelectionStats()
        stats.count = 2
        stats.numeric_count = 2
        stats.sum = Decimal("-50.00")  # avg will be -25.00
        stats.min_val = Decimal("-40.00")
        stats.max_val = Decimal("-10.00")
        bar.update_stats(stats)
        
        assert "Sum: -50.00" in bar._sum_label.text()
        assert "Avg: -25.00" in bar._avg_label.text()
        assert "Min: -40.00" in bar._min_label.text()
        assert "Max: -10.00" in bar._max_label.text()
