"""Purchase-specific validation rules."""

from typing import List, Dict, Any
from decimal import Decimal

from .base import BaseValidator
from ..dtos import ValidationError, ValidationSeverity, ValidationContext


class PurchaseValidator(BaseValidator):
    """Validator for Purchase records.
    
    Business rules:
    - amount > 0
    - sc_received >= 0
    - starting_sc_balance >= sc_received (if provided)
    - purchase_date <= today
    - cashback_earned >= 0 (if provided)
    - user_id and site_id must exist (FKs)
    """
    
    def validate_record(self, record: Dict[str, Any], context: ValidationContext) -> List[ValidationError]:
        """Validate a single purchase record."""
        errors = []
        row = context.row_number
        
        # Required fields
        errors.extend(self.validate_required_field(record, 'user_id', row))
        errors.extend(self.validate_required_field(record, 'site_id', row))
        errors.extend(self.validate_required_field(record, 'purchase_date', row))
        errors.extend(self.validate_required_field(record, 'amount', row))
        errors.extend(self.validate_required_field(record, 'sc_received', row))
        
        # Amount must be non-negative (zero is allowed for $0 basis purchases)
        errors.extend(self.validate_positive_number(record, 'amount', row, allow_zero=True))
        
        # SC received must be >= 0
        errors.extend(self.validate_positive_number(record, 'sc_received', row, allow_zero=True))
        
        # Cashback must be >= 0 if provided
        if record.get('cashback_earned') is not None:
            errors.extend(self.validate_positive_number(record, 'cashback_earned', row, allow_zero=True))
        
        # Purchase date must not be in future
        errors.extend(self.validate_date_not_future(record, 'purchase_date', row))
        
        # Time format validation (if provided)
        if record.get('purchase_time'):
            errors.extend(self.validate_time_format(record, 'purchase_time', row))
        
        # Starting SC balance must be >= sc_received (if provided)
        if record.get('starting_sc_balance') is not None and record.get('sc_received') is not None:
            try:
                balance = Decimal(str(record['starting_sc_balance']))
                received = Decimal(str(record['sc_received']))
                
                if balance < received:
                    errors.append(ValidationError(
                        row_number=row,
                        field='starting_sc_balance',
                        value=record['starting_sc_balance'],
                        message='Post-purchase balance cannot be less than SC received',
                        severity=ValidationSeverity.ERROR
                    ))
            except (ValueError, TypeError):
                pass  # Number format errors caught elsewhere
        
        # Foreign key validation
        errors.extend(self.validate_foreign_key_exists(
            record, 'user_id', row, 'users', context.existing_data
        ))
        errors.extend(self.validate_foreign_key_exists(
            record, 'site_id', row, 'sites', context.existing_data
        ))
        
        if record.get('card_id'):
            errors.extend(self.validate_foreign_key_exists(
                record, 'card_id', row, 'cards', context.existing_data
            ))
        
        return errors
    
    def validate_batch(self, records: List[Dict[str, Any]]) -> List[ValidationError]:
        """Cross-record validation for purchases.
        
        Checks for duplicate purchases (same user, site, date, time).
        """
        errors = []
        seen = {}
        
        for idx, record in enumerate(records, start=2):
            # Create unique key from user_id, site_id, purchase_date, purchase_time
            user_id = record.get('user_id')
            site_id = record.get('site_id')
            purch_date = record.get('purchase_date')
            purch_time = record.get('purchase_time', '00:00:00')
            
            if all([user_id, site_id, purch_date]):
                key = (user_id, site_id, purch_date, purch_time)
                
                if key in seen:
                    errors.append(ValidationError(
                        row_number=idx,
                        field='purchase_date',
                        value=purch_date,
                        message=f'Duplicate purchase found in CSV (row {seen[key]} has same user, site, date, time)',
                        severity=ValidationSeverity.ERROR
                    ))
                else:
                    seen[key] = idx
        
        return errors
