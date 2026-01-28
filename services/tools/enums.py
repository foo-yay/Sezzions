"""Enums for Tools services."""

from enum import Enum


class FieldType(Enum):
    """Data types for CSV fields."""
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    TIME = "time"
    BOOLEAN = "boolean"
    FOREIGN_KEY = "foreign_key"


class RestoreMode(Enum):
    """Database restore modes."""
    REPLACE = "replace"           # Full replace (destructive)
    MERGE_ALL = "merge_all"       # Merge all tables (skip duplicates)
    MERGE_SELECTED = "merge_selected"  # Merge selected subset


class PostImportHook(Enum):
    """Actions to take after CSV import."""
    NONE = "none"
    PROMPT_RECALCULATE_EVERYTHING = "prompt_recalculate_everything"
    PROMPT_RECALCULATE_SCOPED = "prompt_recalculate_scoped"
    AUTO_RECALCULATE = "auto_recalculate"


class AuditAction(Enum):
    """Types of auditable actions."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    IMPORT = "import"
    EXPORT = "export"
    RECALCULATE = "recalculate"
    BACKUP = "backup"
    RESTORE = "restore"
    RESET = "reset"
