"""
Spreadsheet Stats Bar Widget

A status bar widget that displays selection statistics for spreadsheet-like tables.
Shows: Count, Numeric Count, Sum, Average, Min, Max

Updated automatically when selection changes.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from decimal import Decimal
from typing import Optional

from ui.spreadsheet_ux import SelectionStats


class SpreadsheetStatsBar(QWidget):
    """
    A horizontal status bar that displays selection statistics.
    
    Usage:
        stats_bar = SpreadsheetStatsBar()
        # ... later, when selection changes:
        stats = SpreadsheetUXController.compute_stats(grid)
        stats_bar.update_stats(stats)
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the widget layout and labels."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(16)
        
        # Create labels for each stat
        self._count_label = QLabel()
        self._numeric_count_label = QLabel()
        self._sum_label = QLabel()
        self._avg_label = QLabel()
        self._min_label = QLabel()
        self._max_label = QLabel()
        
        # Add labels to layout
        layout.addWidget(self._count_label)
        layout.addWidget(self._numeric_count_label)
        layout.addWidget(self._sum_label)
        layout.addWidget(self._avg_label)
        layout.addWidget(self._min_label)
        layout.addWidget(self._max_label)
        layout.addStretch()
        
        # Initial state (no selection)
        self.clear_stats()
        
    def update_stats(self, stats: SelectionStats):
        """Update the displayed statistics."""
        self._count_label.setText(f"Count: {stats.count}")
        
        if stats.numeric_count > 0:
            self._numeric_count_label.setText(f"Numeric: {stats.numeric_count}")
            self._numeric_count_label.setVisible(True)
            
            # Format sum/avg/min/max as currency with 2 decimal places
            self._sum_label.setText(f"Sum: ${stats.sum:,.2f}")
            self._sum_label.setVisible(True)
            
            self._avg_label.setText(f"Avg: ${stats.avg:,.2f}")
            self._avg_label.setVisible(True)
            
            self._min_label.setText(f"Min: ${stats.min_val:,.2f}")
            self._min_label.setVisible(True)
            
            self._max_label.setText(f"Max: ${stats.max_val:,.2f}")
            self._max_label.setVisible(True)
        else:
            # No numeric values in selection
            self._numeric_count_label.setVisible(False)
            self._sum_label.setVisible(False)
            self._avg_label.setVisible(False)
            self._min_label.setVisible(False)
            self._max_label.setVisible(False)
            
    def clear_stats(self):
        """Clear all statistics (used when no selection)."""
        self._count_label.setText("Count: 0")
        self._numeric_count_label.setVisible(False)
        self._sum_label.setVisible(False)
        self._avg_label.setVisible(False)
        self._min_label.setVisible(False)
        self._max_label.setVisible(False)
