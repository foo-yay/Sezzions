"""Base validator for CSV import validation."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..dtos import ValidationError, ValidationSeverity, ValidationContext


class BaseValidator(ABC):
    """Base class for entity validators.
    
    Provides common validation utilities and defines the validation interface.
    Subclasses implement entity-specific business rules.
    """
    
    @abstractmethod
    def validate_record(self, record: Dict[str, Any], context: ValidationContext) -> List[ValidationError]:
        """Validate a single record.
        
        Args:
            record: Dictionary of field values (DB column names as keys)
            context: Validation context with row number, entity type, etc.
        
        Returns:
            List of validation errors (empty if valid)
        """
        pass
    
    @abstractmethod
    def validate_batch(self, records: List[Dict[str, Any]]) -> List[ValidationError]:
        """Cross-record validation (e.g., within-file duplicates).
        
        Args:
            records: List of record dictionaries
        
        Returns:
            List of validation errors across the batch
        """
        pass
    
    # ========================================================================
    # Common validation utilities
    # ========================================================================
    
    def validate_required_field(
        self,
        record: Dict[str, Any],
        field: str,
        row_number: int
    ) -> List[ValidationError]:
        """Check if required field is present and non-empty."""
        errors = []
        value = record.get(field)
        
        if value is None or (isinstance(value, str) and value.strip() == ''):
            errors.append(ValidationError(
                row_number=row_number,
                field=field,
                value=value,
                message='Required field is missing',
                severity=ValidationSeverity.ERROR
            ))
        
        return errors
    
    def validate_positive_number(
        self,
        record: Dict[str, Any],
        field: str,
        row_number: int,
        allow_zero: bool = False
    ) -> List[ValidationError]:
        """Validate that a number field is positive (or >= 0 if allow_zero)."""
        errors = []
        value = record.get(field)
        
        if value is None:
            return errors  # Skip if not provided
        
        try:
            num_value = Decimal(str(value))
            if allow_zero:
                if num_value < 0:
                    errors.append(ValidationError(
                        row_number=row_number,
                        field=field,
                        value=value,
                        message='Must be zero or positive',
                        severity=ValidationSeverity.ERROR
                    ))
            else:
                if num_value <= 0:
                    errors.append(ValidationError(
                        row_number=row_number,
                        field=field,
                        value=value,
                        message='Must be positive',
                        severity=ValidationSeverity.ERROR
                    ))
        except (ValueError, InvalidOperation):
            errors.append(ValidationError(
                row_number=row_number,
                field=field,
                value=value,
                message='Invalid number format',
                severity=ValidationSeverity.ERROR
            ))
        
        return errors
    
    def validate_date_not_future(
        self,
        record: Dict[str, Any],
        field: str,
        row_number: int
    ) -> List[ValidationError]:
        """Validate that a date is not in the future."""
        errors = []
        value = record.get(field)
        
        if value is None:
            return errors  # Skip if not provided
        
        try:
            if isinstance(value, str):
                date_value = datetime.strptime(value, '%Y-%m-%d').date()
            elif isinstance(value, date):
                date_value = value
            else:
                raise ValueError("Invalid date type")
            
            if date_value > date.today():
                errors.append(ValidationError(
                    row_number=row_number,
                    field=field,
                    value=value,
                    message='Date cannot be in the future',
                    severity=ValidationSeverity.ERROR
                ))
        except (ValueError, TypeError):
            errors.append(ValidationError(
                row_number=row_number,
                field=field,
                value=value,
                message='Invalid date format (expected YYYY-MM-DD)',
                severity=ValidationSeverity.ERROR
            ))
        
        return errors
    
    def validate_date_order(
        self,
        record: Dict[str, Any],
        earlier_field: str,
        later_field: str,
        row_number: int,
        message: str = None
    ) -> List[ValidationError]:
        """Validate that one date comes before or equals another."""
        errors = []
        earlier = record.get(earlier_field)
        later = record.get(later_field)
        
        if earlier is None or later is None:
            return errors  # Skip if either not provided
        
        try:
            if isinstance(earlier, str):
                earlier_date = datetime.strptime(earlier, '%Y-%m-%d').date()
            else:
                earlier_date = earlier
            
            if isinstance(later, str):
                later_date = datetime.strptime(later, '%Y-%m-%d').date()
            else:
                later_date = later
            
            if later_date < earlier_date:
                errors.append(ValidationError(
                    row_number=row_number,
                    field=later_field,
                    value=later,
                    message=message or f'{later_field} must be >= {earlier_field}',
                    severity=ValidationSeverity.ERROR
                ))
        except (ValueError, TypeError):
            pass  # Date format errors caught elsewhere
        
        return errors
    
    def validate_time_format(
        self,
        record: Dict[str, Any],
        field: str,
        row_number: int
    ) -> List[ValidationError]:
        """Validate time format (HH:MM or HH:MM:SS)."""
        errors = []
        value = record.get(field)
        
        if value is None or value == '':
            return errors  # Skip if not provided
        
        try:
            # Try HH:MM:SS format
            datetime.strptime(str(value), '%H:%M:%S')
        except ValueError:
            try:
                # Try HH:MM format (will auto-append :00)
                datetime.strptime(str(value), '%H:%M')
            except ValueError:
                errors.append(ValidationError(
                    row_number=row_number,
                    field=field,
                    value=value,
                    message='Invalid time format (expected HH:MM or HH:MM:SS)',
                    severity=ValidationSeverity.ERROR
                ))
        
        return errors
    
    def validate_foreign_key_exists(
        self,
        record: Dict[str, Any],
        field: str,
        row_number: int,
        fk_table: str,
        existing_data: Dict[str, Any]
    ) -> List[ValidationError]:
        """Validate that foreign key ID exists in lookup data."""
        errors = []
        fk_id = record.get(field)
        
        if fk_id is None:
            return errors  # Skip if not provided (may be optional)
        
        # Check if ID exists in cached lookup data
        lookup_key = f"{fk_table}_by_id"
        if lookup_key not in existing_data:
            # No lookup data - cannot validate
            return errors
        
        if fk_id not in existing_data[lookup_key]:
            errors.append(ValidationError(
                row_number=row_number,
                field=field,
                value=fk_id,
                message=f'{fk_table} with ID {fk_id} not found',
                severity=ValidationSeverity.ERROR
            ))
        
        return errors
