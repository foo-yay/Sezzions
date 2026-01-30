"""
Spreadsheet UX Module (Issue #14, Phase 1)

Provides Excel-like usability across all tabs:
- Cell-level selection (multi-cell highlight)
- Copy selection to clipboard as TSV (Tab-Separated Values)
- Selection stats: Count, Numeric Count, Sum, Avg, Min, Max

Widget-agnostic foundation supporting:
- QTableWidget (grid-based tabs)
- QTreeWidget (hierarchical tabs like Daily Sessions / Realized)

Phase 1 is read-only (no editing/paste yet).
"""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from typing import List, Tuple, Optional, Dict, Any
from decimal import Decimal, InvalidOperation
import re


class SelectionStats:
    """Statistics for a selection of cells."""
    
    def __init__(self):
        self.count = 0  # Total cells
        self.numeric_count = 0  # Cells with valid numeric values
        self.sum = Decimal('0')
        self.min_val: Optional[Decimal] = None
        self.max_val: Optional[Decimal] = None
    
    @property
    def avg(self) -> Optional[Decimal]:
        """Average of numeric values."""
        if self.numeric_count == 0:
            return None
        return self.sum / self.numeric_count
    
    def __repr__(self):
        if self.numeric_count == 0:
            return f"Count: {self.count}"
        avg_str = f"{self.avg:.2f}" if self.avg is not None else "N/A"
        return (f"Count: {self.count} | Numeric: {self.numeric_count} | "
                f"Sum: {self.sum:.2f} | Avg: {avg_str} | "
                f"Min: {self.min_val:.2f} | Max: {self.max_val:.2f}")


class SpreadsheetUXController(QObject):
    """
    Shared controller for spreadsheet-like UX across all tabs.
    
    Provides:
    - Cell selection extraction (rectangular grid)
    - TSV formatting for clipboard copy
    - Numeric parsing (handles $1,234.56, negatives, blanks)
    - Selection statistics computation
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    @staticmethod
    def parse_numeric_value(text: str) -> Optional[Decimal]:
        """
        Parse a cell value as Decimal, handling currency formatting.
        
        Examples:
            "$1,234.56" -> Decimal("1234.56")
            "(123.45)" -> Decimal("-123.45")
            "100%" -> Decimal("100")
            "N/A" -> None
            "" -> None
        
        Returns None for non-numeric values or empty strings.
        """
        if not text or not isinstance(text, str):
            return None
        
        # Strip whitespace
        text = text.strip()
        if not text:
            return None
        
        # Handle common non-numeric indicators
        if text.lower() in ('n/a', 'na', '-', '—', '–'):
            return None
        
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$€£¥,\s]', '', text)
        
        # Handle parentheses as negative (accounting format)
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        
        # Handle percentage (strip %, keep numeric value)
        if cleaned.endswith('%'):
            cleaned = cleaned[:-1]
        
        # Try to parse as Decimal
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None
    
    @staticmethod
    def extract_selection_grid(widget, include_headers=False) -> List[List[str]]:
        """
        Extract selected cells as a rectangular grid of strings.
        
        For QTableWidget: returns selected cells in row/column order
        For QTreeWidget: returns selected items as visible "cells"
        
        Args:
            widget: QTableWidget or QTreeWidget
            include_headers: If True, prepend column headers as first row
        
        Returns:
            List of rows, where each row is a list of cell values (strings)
        """
        from PySide6.QtWidgets import QTableWidget, QTreeWidget
        
        if isinstance(widget, QTableWidget):
            return SpreadsheetUXController._extract_table_selection(widget, include_headers)
        elif isinstance(widget, QTreeWidget):
            return SpreadsheetUXController._extract_tree_selection(widget, include_headers)
        else:
            return []
    
    @staticmethod
    def _extract_table_selection(table, include_headers=False) -> List[List[str]]:
        """Extract selection from QTableWidget."""
        selected_ranges = table.selectedRanges()
        if not selected_ranges:
            return []
        
        # Find bounding box of all selected ranges
        min_row = min(r.topRow() for r in selected_ranges)
        max_row = max(r.bottomRow() for r in selected_ranges)
        min_col = min(r.leftColumn() for r in selected_ranges)
        max_col = max(r.rightColumn() for r in selected_ranges)
        
        grid = []
        
        # Add headers if requested
        if include_headers:
            header_row = []
            for col in range(min_col, max_col + 1):
                header_item = table.horizontalHeaderItem(col)
                header_row.append(header_item.text() if header_item else f"Column {col}")
            grid.append(header_row)
        
        # Extract selected cells
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                # Check if this cell is in any selected range
                is_selected = any(
                    r.topRow() <= row <= r.bottomRow() and
                    r.leftColumn() <= col <= r.rightColumn()
                    for r in selected_ranges
                )
                if is_selected:
                    item = table.item(row, col)
                    row_data.append(item.text() if item else "")
                else:
                    row_data.append("")  # Empty for non-selected cells in bounding box
            grid.append(row_data)
        
        return grid
    
    @staticmethod
    def _extract_tree_selection(tree, include_headers=False) -> List[List[str]]:
        """
        Extract selection from QTreeWidget.
        
        Best-effort: treats each selected item as a row, extracts text from all columns.
        """
        selected_items = tree.selectedItems()
        if not selected_items:
            return []
        
        column_count = tree.columnCount()
        grid = []
        
        # Add headers if requested
        if include_headers:
            header_row = []
            for col in range(column_count):
                header_item = tree.headerItem()
                if header_item:
                    header_row.append(header_item.text(col))
                else:
                    header_row.append(f"Column {col}")
            grid.append(header_row)
        
        # Extract selected items
        for item in selected_items:
            row_data = []
            for col in range(column_count):
                row_data.append(item.text(col))
            grid.append(row_data)
        
        return grid
    
    @staticmethod
    def format_as_tsv(grid: List[List[str]]) -> str:
        """
        Format grid as Tab-Separated Values (TSV).
        
        TSV is Excel-friendly: rows separated by newlines, cells by tabs.
        """
        return '\n'.join('\t'.join(row) for row in grid)
    
    @staticmethod
    def compute_stats(grid: List[List[str]]) -> SelectionStats:
        """
        Compute statistics over all cells in grid.
        
        Counts all cells and computes numeric stats (sum/avg/min/max) for valid numbers.
        """
        stats = SelectionStats()
        
        for row in grid:
            for cell in row:
                stats.count += 1
                numeric_val = SpreadsheetUXController.parse_numeric_value(cell)
                if numeric_val is not None:
                    stats.numeric_count += 1
                    stats.sum += numeric_val
                    if stats.min_val is None or numeric_val < stats.min_val:
                        stats.min_val = numeric_val
                    if stats.max_val is None or numeric_val > stats.max_val:
                        stats.max_val = numeric_val
        
        return stats
    
    @staticmethod
    def copy_to_clipboard(grid: List[List[str]]):
        """Copy grid to system clipboard as TSV."""
        tsv = SpreadsheetUXController.format_as_tsv(grid)
        clipboard = QApplication.clipboard()
        clipboard.setText(tsv)
    
    @staticmethod
    def copy_selection(widget, include_headers=False):
        """
        Extract selection from widget and copy to clipboard as TSV.
        
        Convenience method combining extract_selection_grid + copy_to_clipboard.
        """
        grid = SpreadsheetUXController.extract_selection_grid(widget, include_headers)
        if grid:
            SpreadsheetUXController.copy_to_clipboard(grid)
    
    @staticmethod
    def get_selection_stats(widget) -> SelectionStats:
        """
        Compute statistics for current selection in widget.
        
        Returns SelectionStats with count/sum/avg/min/max.
        """
        grid = SpreadsheetUXController.extract_selection_grid(widget, include_headers=False)
        return SpreadsheetUXController.compute_stats(grid)
