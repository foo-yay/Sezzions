"""Redemption-specific validation rules."""

from typing import List, Dict, Any
from decimal import Decimal

from .base import BaseValidator
from ..dtos import ValidationError, ValidationSeverity, ValidationContext


class RedemptionValidator(BaseValidator):
    """Validator for Redemption records.
    
    Business rules:
    - amount > 0
    - fees >= 0 and fees <= amount
    - redemption_date <= today
    - receipt_date >= redemption_date (if both provided)
    - user_id and site_id must exist (FKs)
    """
    
    def validate_record(self, record: Dict[str, Any], context: ValidationContext) -> List[ValidationError]:
        """Validate a single redemption record."""
        errors = []
        row = context.row_number
        
        # Required fields
        errors.extend(self.validate_required_field(record, 'user_id', row))
        errors.extend(self.validate_required_field(record, 'site_id', row))
        errors.extend(self.validate_required_field(record, 'redemption_date', row))
        errors.extend(self.validate_required_field(record, 'amount', row))
        
        # Amount must be positive
        errors.extend(self.validate_positive_number(record, 'amount', row, allow_zero=False))
        
        # Fees must be >= 0 if provided
        if record.get('fees') is not None:
            errors.extend(self.validate_positive_number(record, 'fees', row, allow_zero=True))
            
            # Fees must be <= amount
            try:
                fees = Decimal(str(record['fees']))
                amount = Decimal(str(record['amount']))
                
                if fees > amount:
                    errors.append(ValidationError(
                        row_number=row,
                        field='fees',
                        value=record['fees'],
                        message='Fees cannot exceed redemption amount',
                        severity=ValidationSeverity.ERROR
                    ))
            except (ValueError, TypeError):
                pass  # Number format errors caught elsewhere
        
        # Redemption date must not be in future
        errors.extend(self.validate_date_not_future(record, 'redemption_date', row))
        
        # Receipt date must not be in future (if provided)
        if record.get('receipt_date'):
            errors.extend(self.validate_date_not_future(record, 'receipt_date', row))
        
        # Time format validation (if provided)
        if record.get('redemption_time'):
            errors.extend(self.validate_time_format(record, 'redemption_time', row))
        
        # Receipt date must be >= redemption date (if both provided)
        if record.get('receipt_date') and record.get('redemption_date'):
            errors.extend(self.validate_date_order(
                record,
                'redemption_date',
                'receipt_date',
                row,
                'Receipt date must be on or after redemption date'
            ))
        
        # Foreign key validation
        errors.extend(self.validate_foreign_key_exists(
            record, 'user_id', row, 'users', context.existing_data
        ))
        errors.extend(self.validate_foreign_key_exists(
            record, 'site_id', row, 'sites', context.existing_data
        ))
        
        if record.get('redemption_method_id'):
            errors.extend(self.validate_foreign_key_exists(
                record, 'redemption_method_id', row, 'redemption_methods', context.existing_data
            ))
        
        return errors
    
    def validate_batch(self, records: List[Dict[str, Any]]) -> List[ValidationError]:
        """Cross-record validation for redemptions.
        
        Checks for duplicate redemptions (same user, site, date, time).
        """
        errors = []
        seen = {}
        
        for idx, record in enumerate(records, start=2):
            # Create unique key from user_id, site_id, redemption_date, redemption_time
            user_id = record.get('user_id')
            site_id = record.get('site_id')
            redem_date = record.get('redemption_date')
            redem_time = record.get('redemption_time', '00:00:00')
            
            if all([user_id, site_id, redem_date]):
                key = (user_id, site_id, redem_date, redem_time)
                
                if key in seen:
                    errors.append(ValidationError(
                        row_number=idx,
                        field='redemption_date',
                        value=redem_date,
                        message=f'Duplicate redemption found in CSV (row {seen[key]} has same user, site, date, time)',
                        severity=ValidationSeverity.ERROR
                    ))
                else:
                    seen[key] = idx
        
        return errors
