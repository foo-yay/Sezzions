"""
Shared QTableView model infrastructure for grid tabs

Provides base classes for QAbstractTableModel-based tabs with:
- Column definitions (label, key, formatter, alignment)
- Proxy model support for filtering/sorting
- Spreadsheet UX integration (selection/copy/stats)
"""
from typing import List, Dict, Any, Callable, Optional
from PySide6 import QtCore, QtGui


class ColumnDefinition:
    """Definition for a single table column"""
    
    def __init__(
        self,
        label: str,
        key: str,
        formatter: Optional[Callable[[Any], str]] = None,
        alignment: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
        width_hint: Optional[int] = None
    ):
        self.label = label
        self.key = key  # Attribute name on model object
        self.formatter = formatter or self._default_formatter
        self.alignment = alignment
        self.width_hint = width_hint
    
    @staticmethod
    def _default_formatter(value: Any) -> str:
        """Default formatter: convert to string, handle None"""
        if value is None:
            return ""
        return str(value)
    
    def format(self, value: Any) -> str:
        """Format a value for display"""
        try:
            return self.formatter(value)
        except Exception:
            return str(value) if value is not None else ""


class BaseTableModel(QtCore.QAbstractTableModel):
    """
    Base QAbstractTableModel for grid tabs
    
    Provides common patterns:
    - Column definitions
    - Row data as list of objects
    - Display/alignment roles
    - UserRole for object ID storage
    """
    
    def __init__(self, columns: List[ColumnDefinition], parent=None):
        super().__init__(parent)
        self.columns = columns
        self._data: List[Any] = []
    
    def set_data(self, data: List[Any]):
        """Replace model data"""
        self.beginResetModel()
        self._data = data
        self.endResetModel()
    
    def get_row_object(self, row: int) -> Optional[Any]:
        """Get the underlying object for a row"""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None
    
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._data)
    
    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.columns)
    
    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._data) or col < 0 or col >= len(self.columns):
            return None
        
        obj = self._data[row]
        column_def = self.columns[col]
        
        if role == QtCore.Qt.DisplayRole:
            # Get value from object attribute
            value = getattr(obj, column_def.key, None)
            return column_def.format(value)
        
        elif role == QtCore.Qt.TextAlignmentRole:
            return column_def.alignment
        
        elif role == QtCore.Qt.UserRole:
            # Store object ID in first column for row identification
            if col == 0 and hasattr(obj, 'id'):
                return obj.id
            return None
        
        return None
    
    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.columns):
                return self.columns[section].label
            elif orientation == QtCore.Qt.Vertical:
                return section + 1
        return None
    
    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        """Base flags: selectable and enabled, no editing"""
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
