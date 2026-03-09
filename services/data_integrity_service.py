"""Data integrity validation service.

Detects common data integrity violations that can occur during:
- Partial CSV imports (incomplete dataset)
- CSV imports without recalculation
- Manual data edits
- Database corruption
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from repositories.database import DatabaseManager


class ViolationType(Enum):
    """Types of data integrity violations."""
    PURCHASE_INVALID_REMAINING = "purchase_invalid_remaining"
    ORPHANED_FK = "orphaned_fk"
    NULL_REQUIRED_FIELD = "null_required_field"
    DATE_INCONSISTENCY = "date_inconsistency"
    NEGATIVE_AMOUNT = "negative_amount"


@dataclass
class IntegrityViolation:
    """Represents a data integrity violation."""
    violation_type: ViolationType
    table: str
    record_id: Optional[int]
    field: Optional[str]
    message: str
    severity: str  # 'error' or 'warning'
    
    def __str__(self) -> str:
        """Human-readable violation description."""
        if self.record_id:
            return f"{self.table} #{self.record_id}: {self.message}"
        return f"{self.table}: {self.message}"


@dataclass
class IntegrityCheckResult:
    """Result of integrity check."""
    violations: List[IntegrityViolation]
    total_violations: int
    has_errors: bool
    has_warnings: bool
    
    @property
    def is_clean(self) -> bool:
        """Whether database has no integrity issues."""
        return self.total_violations == 0
    
    def violations_by_type(self, violation_type: ViolationType) -> List[IntegrityViolation]:
        """Get violations of a specific type."""
        return [v for v in self.violations if v.violation_type == violation_type]
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        if self.is_clean:
            return "Database integrity check passed. No issues found."
        
        lines = ["Data integrity issues detected:"]
        
        # Group by type
        by_type = {}
        for v in self.violations:
            key = v.violation_type
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(v)
        
        for vtype, violations in by_type.items():
            lines.append(f"  - {vtype.value}: {len(violations)} issue(s)")
        
        return "\n".join(lines)


class DataIntegrityService:
    """Service for validating database integrity."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def check_integrity(self, quick: bool = False) -> IntegrityCheckResult:
        """Run integrity checks on database.
        
        Args:
            quick: If True, run only fast checks and stop at first violation
        
        Returns:
            IntegrityCheckResult with all detected violations
        """
        violations = []
        
        # Check 1: Purchases with invalid remaining_amount
        violations.extend(self._check_purchase_remaining_amounts())
        if quick and violations:
            return self._build_result(violations)
        
        # Check 2: Purchases with negative amounts
        violations.extend(self._check_negative_amounts())
        if quick and violations:
            return self._build_result(violations)
        
        # Check 3: Orphaned foreign keys (if not quick mode)
        if not quick:
            violations.extend(self._check_orphaned_fks())
        
        return self._build_result(violations)
    
    def _check_purchase_remaining_amounts(self) -> List[IntegrityViolation]:
        """Check for purchases where remaining_amount > amount."""
        violations = []
        
        query = """
            SELECT id, purchase_date, amount, remaining_amount
            FROM purchases
            WHERE CAST(remaining_amount AS REAL) > CAST(amount AS REAL)
        """
        
        rows = self.db.fetch_all(query)
        
        for row in rows:
            violations.append(IntegrityViolation(
                violation_type=ViolationType.PURCHASE_INVALID_REMAINING,
                table='purchases',
                record_id=row['id'],
                field='remaining_amount',
                message=f"Remaining amount ({row['remaining_amount']}) exceeds purchase amount ({row['amount']}) on {row['purchase_date']}",
                severity='error'
            ))
        
        return violations
    
    def _check_negative_amounts(self) -> List[IntegrityViolation]:
        """Check for purchases with negative amounts."""
        violations = []
        
        query = """
            SELECT id, purchase_date, amount
            FROM purchases
            WHERE amount < 0
        """
        
        rows = self.db.fetch_all(query)
        
        for row in rows:
            violations.append(IntegrityViolation(
                violation_type=ViolationType.NEGATIVE_AMOUNT,
                table='purchases',
                record_id=row['id'],
                field='amount',
                message=f"Negative purchase amount ({row['amount']}) on {row['purchase_date']}",
                severity='error'
            ))
        
        return violations
    
    def _check_orphaned_fks(self) -> List[IntegrityViolation]:
        """Check for orphaned foreign key references."""
        violations = []
        
        # Check purchases -> users
        query = """
            SELECT p.id, p.purchase_date, p.user_id
            FROM purchases p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE u.id IS NULL
        """
        rows = self.db.fetch_all(query)
        for row in rows:
            violations.append(IntegrityViolation(
                violation_type=ViolationType.ORPHANED_FK,
                table='purchases',
                record_id=row['id'],
                field='user_id',
                message=f"References non-existent user_id={row['user_id']} on {row['purchase_date']}",
                severity='error'
            ))
        
        # Check purchases -> sites
        query = """
            SELECT p.id, p.purchase_date, p.site_id
            FROM purchases p
            LEFT JOIN sites s ON p.site_id = s.id
            WHERE s.id IS NULL
        """
        rows = self.db.fetch_all(query)
        for row in rows:
            violations.append(IntegrityViolation(
                violation_type=ViolationType.ORPHANED_FK,
                table='purchases',
                record_id=row['id'],
                field='site_id',
                message=f"References non-existent site_id={row['site_id']} on {row['purchase_date']}",
                severity='error'
            ))
        
        return violations
    
    def _build_result(self, violations: List[IntegrityViolation]) -> IntegrityCheckResult:
        """Build IntegrityCheckResult from violations list."""
        has_errors = any(v.severity == 'error' for v in violations)
        has_warnings = any(v.severity == 'warning' for v in violations)
        
        return IntegrityCheckResult(
            violations=violations,
            total_violations=len(violations),
            has_errors=has_errors,
            has_warnings=has_warnings
        )
    
    def fix_purchase_remaining_amounts(self) -> int:
        """Fix purchases where remaining_amount > amount by capping at amount.
        
        Returns:
            Number of records fixed
        """
        query = """
            UPDATE purchases 
            SET remaining_amount = amount 
            WHERE CAST(remaining_amount AS REAL) > CAST(amount AS REAL)
        """
        
        self.db.execute(query)
        self.db.commit()
        
        # Return count of fixed records
        return self.db.cursor().rowcount
