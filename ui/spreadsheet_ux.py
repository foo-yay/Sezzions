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
        For QTableView: returns selected model indexes in row/column order
        For QTreeWidget: returns selected items as visible "cells"
        
        Args:
            widget: QTableWidget, QTableView, or QTreeWidget
            include_headers: If True, prepend column headers as first row
        
        Returns:
            List of rows, where each row is a list of cell values (strings)
        """
        from PySide6.QtWidgets import QTableWidget, QTreeWidget, QTableView
        
        if isinstance(widget, QTableWidget):
            return SpreadsheetUXController._extract_table_selection(widget, include_headers)
        elif isinstance(widget, QTableView):
            return SpreadsheetUXController._extract_tableview_selection(widget, include_headers)
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
        
        visible_rows = [
            row for row in range(min_row, max_row + 1)
            if not table.isRowHidden(row)
        ]
        visible_cols = [
            col for col in range(min_col, max_col + 1)
            if not table.isColumnHidden(col)
        ]

        if not visible_rows or not visible_cols:
            return []

        grid = []
        
        # Add headers if requested
        if include_headers:
            header_row = []
            for col in visible_cols:
                header_item = table.horizontalHeaderItem(col)
                header_row.append(header_item.text() if header_item else f"Column {col}")
            grid.append(header_row)
        
        # Extract selected cells
        for row in visible_rows:
            row_data = []
            for col in visible_cols:
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
    def _extract_tableview_selection(view, include_headers=False) -> List[List[str]]:
        """
        Extract selection from QTableView with model/proxy.
        
        QTableView uses a selection model and item model. Selected indexes
        may map through a QSortFilterProxyModel to source model indexes.
        """
        from PySide6.QtCore import Qt
        
        selection_model = view.selectionModel()
        if not selection_model:
            return []
        
        selected_indexes = selection_model.selectedIndexes()
        if not selected_indexes:
            return []

        visible_indexes = [
            idx for idx in selected_indexes
            if not view.isRowHidden(idx.row()) and not view.isColumnHidden(idx.column())
        ]
        if not visible_indexes:
            return []
        
        # Find bounding box of selection
        min_row = min(idx.row() for idx in visible_indexes)
        max_row = max(idx.row() for idx in visible_indexes)
        min_col = min(idx.column() for idx in visible_indexes)
        max_col = max(idx.column() for idx in visible_indexes)
        
        # Build map of (row, col) -> data
        cell_map = {}
        for idx in visible_indexes:
            cell_map[(idx.row(), idx.column())] = idx.data(Qt.DisplayRole) or ""
        
        grid = []
        
        # Add headers if requested
        if include_headers:
            header_row = []
            model = view.model()
            visible_cols = [
                col for col in range(min_col, max_col + 1)
                if not view.isColumnHidden(col)
            ]
            if not visible_cols:
                return []

            for col in visible_cols:
                header_data = model.headerData(col, Qt.Horizontal, Qt.DisplayRole)
                header_row.append(str(header_data) if header_data else f"Column {col}")
            grid.append(header_row)
        
        # Extract selected cells in rectangular grid
        visible_rows = [
            row for row in range(min_row, max_row + 1)
            if not view.isRowHidden(row)
        ]
        visible_cols = [
            col for col in range(min_col, max_col + 1)
            if not view.isColumnHidden(col)
        ]
        if not visible_rows or not visible_cols:
            return []

        for row in visible_rows:
            row_data = []
            for col in visible_cols:
                if (row, col) in cell_map:
                    row_data.append(str(cell_map[(row, col)]))
                else:
                    row_data.append("")  # Empty for non-selected cells in bounding box
            grid.append(row_data)
        
        return grid
    
    @staticmethod
    def _extract_tree_selection(tree, include_headers=False) -> List[List[str]]:
        """
        Extract selection from QTreeWidget.
        
        Note: QTreeWidget doesn't support true cell-level selection like QTableWidget.
        When an item is selected, all columns are selected. We use currentColumn() 
        to detect single-cell clicks, but multi-selection will select entire rows.
        """
        selection_model = tree.selectionModel()
        if not selection_model:
            return []
        
        selected_items = tree.selectedItems()
        if not selected_items:
            return []
        
        # Check if this is a single-cell selection by using currentColumn
        current_col = tree.currentColumn()
        current_item = tree.currentItem()
        
        # If we have exactly one selected item and it's the current item,
        # and currentColumn is valid, treat as single-cell selection
        if (len(selected_items) == 1 and 
            selected_items[0] == current_item and 
            current_col >= 0):
            # Single cell selection
            grid = []
            if include_headers:
                header_item = tree.headerItem()
                if header_item:
                    grid.append([header_item.text(current_col)])
                else:
                    grid.append([f"Column {current_col}"])
            grid.append([current_item.text(current_col)])
            return grid
        
        # Multi-item selection or range selection - extract all columns
        # Find all selected columns from indexes
        selected_indexes = selection_model.selectedIndexes()
        if not selected_indexes:
            return []
        
        # Build map of (item, col) -> data
        cell_map = {}
        for index in selected_indexes:
            item = tree.itemFromIndex(index)
            if item and item in selected_items:
                cell_map[(item, index.column())] = item.text(index.column())
        
        if not cell_map:
            return []
        
        # Find column range
        all_cols = set(col for _, col in cell_map.keys())
        min_col = min(all_cols)
        max_col = max(all_cols)
        
        column_count = tree.columnCount()
        grid = []
        
        # Add headers if requested
        if include_headers:
            header_row = []
            for col in range(min_col, max_col + 1):
                header_item = tree.headerItem()
                if header_item:
                    header_row.append(header_item.text(col))
                else:
                    header_row.append(f"Column {col}")
            grid.append(header_row)
        
        # Extract selected items in order they appear in tree
        items_with_index = []
        for item in selected_items:
            index = tree.indexFromItem(item)
            if index.isValid():
                items_with_index.append((index.row(), item))
        items_with_index.sort(key=lambda x: x[0])
        
        # Extract data for each row
        for _, item in items_with_index:
            row_data = []
            for col in range(min_col, max_col + 1):
                if (item, col) in cell_map:
                    row_data.append(cell_map[(item, col)])
                else:
                    row_data.append("")  # Empty for non-selected cells in bounding box
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
