"""
Data change event system for unified cross-tab refresh.

Defines the payload for database change notifications and provides
a centralized event coordinator for debounced refresh.
"""
from dataclasses import dataclass
from typing import Optional, List, Literal
from datetime import datetime


@dataclass
class DataChangeEvent:
    """
    Payload for database change notifications.
    
    Attributes:
        operation: Type of operation that changed the data
        scope: Affected scope (default "all" means refresh everything)
        affected_tables: Optional list of specific tables changed
        timestamp: When the change occurred
        maintenance_phase: Optional maintenance lifecycle indicator
    """
    operation: str
    scope: str = "all"
    affected_tables: Optional[List[str]] = None
    timestamp: Optional[datetime] = None
    maintenance_phase: Optional[Literal["start", "end"]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# Common operation types (for consistency)
class OperationType:
    """Standard operation type constants"""
    CSV_IMPORT = "csv_import"
    RESTORE_REPLACE = "restore_replace"
    RESTORE_MERGE_ALL = "restore_merge_all"
    RESTORE_MERGE_SELECTED = "restore_merge_selected"
    RESET_FULL = "reset_full"
    RESET_PARTIAL = "reset_partial"
    RECALCULATE_ALL = "recalculate_all"
    RECALCULATE_SCOPED = "recalculate_scoped"
    MANUAL_EDIT = "manual_edit"
