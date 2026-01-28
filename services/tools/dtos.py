"""Data Transfer Objects for Tools operations."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ValidationSeverity(Enum):
    """Severity levels for validation errors."""
    ERROR = "error"      # Block import
    WARNING = "warning"  # Allow with confirmation
    INFO = "info"        # Show but don't block


@dataclass
@dataclass
class ValidationError:
    """Single validation error from CSV import."""
    row_number: int
    field: str
    value: Any
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    
    def __str__(self):
        return f"Row {self.row_number}, {self.field}: {self.message}"


@dataclass
class ImportPreview:
    """Preview of CSV import before user confirmation."""
    to_add: List[Dict[str, Any]] = None
    to_update: List[Dict[str, Any]] = None
    exact_duplicates: List[Dict[str, Any]] = None
    conflicts: List[Dict[str, Any]] = None
    invalid_rows: List[ValidationError] = None
    csv_duplicates: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize empty lists for None values."""
        if self.to_add is None:
            self.to_add = []
        if self.to_update is None:
            self.to_update = []
        if self.exact_duplicates is None:
            self.exact_duplicates = []
        if self.conflicts is None:
            self.conflicts = []
        if self.invalid_rows is None:
            self.invalid_rows = []
        if self.csv_duplicates is None:
            self.csv_duplicates = []
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any blocking errors."""
        return any(err.severity == ValidationSeverity.ERROR for err in self.invalid_rows)
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(err.severity == ValidationSeverity.WARNING for err in self.invalid_rows)


@dataclass
class ImportResult:
    """Result of CSV import operation."""
    success: bool
    records_added: int
    records_updated: int
    records_skipped: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    entity_type: Optional[str] = None
    affected_user_ids: List[int] = field(default_factory=list)
    affected_site_ids: List[int] = field(default_factory=list)
    
    @property
    def total_processed(self) -> int:
        """Total records processed (added + updated)."""
        return self.records_added + self.records_updated


@dataclass
class ExportResult:
    """Result of CSV export operation."""
    success: bool
    records_exported: int
    file_path: str
    error: Optional[str] = None


@dataclass
class ExportResult:
    """Result of a CSV export operation."""
    success: bool
    records_exported: int = 0
    file_path: str = ""
    errors: List[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        """Initialize empty lists if None."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


@dataclass
class BackupResult:
    """Result of database backup operation."""
    success: bool
    backup_path: Optional[str] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None


@dataclass
class RestoreResult:
    """Result of database restore operation."""
    success: bool
    records_restored: Optional[int] = None
    tables_affected: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ResetResult:
    """Result of database reset operation."""
    success: bool
    backup_path: Optional[str] = None
    tables_cleared: List[str] = field(default_factory=list)
    records_deleted: int = 0
    error: Optional[str] = None


@dataclass
class ValidationContext:
    """Context for validation operations."""
    row_number: int
    entity_type: str
    existing_data: Dict[str, Any]  # Cache of foreign key lookups
    strict_mode: bool = True       # Fail on warnings vs allow with warning
    date_cutoff: Optional[str] = None  # For chronological checks (YYYY-MM-DD)
