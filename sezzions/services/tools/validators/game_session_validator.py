"""Game session-specific validation rules."""

from typing import List, Dict, Any
from datetime import datetime

from .base import BaseValidator
from ..dtos import ValidationError, ValidationSeverity, ValidationContext


class GameSessionValidator(BaseValidator):
    """Validator for Game Session records.
    
    Business rules:
    - session_date <= today
    - starting_balance >= 0
    - ending_balance >= 0 (if provided)
    - purchases_during >= 0 (if provided)
    - redemptions_during >= 0 (if provided)
    - end_date >= session_date (if provided)
    - If same day: end_time > start_time
    - user_id, site_id must exist (FKs)
    """
    
    def validate_record(self, record: Dict[str, Any], context: ValidationContext) -> List[ValidationError]:
        """Validate a single game session record."""
        errors = []
        row = context.row_number
        
        # Required fields
        errors.extend(self.validate_required_field(record, 'user_id', row))
        errors.extend(self.validate_required_field(record, 'site_id', row))
        errors.extend(self.validate_required_field(record, 'session_date', row))
        errors.extend(self.validate_required_field(record, 'starting_balance', row))
        
        # Starting balance must be >= 0
        errors.extend(self.validate_positive_number(record, 'starting_balance', row, allow_zero=True))
        
        # Ending balance must be >= 0 (if provided)
        if record.get('ending_balance') is not None:
            errors.extend(self.validate_positive_number(record, 'ending_balance', row, allow_zero=True))
        
        # Purchases during must be >= 0 (if provided)
        if record.get('purchases_during') is not None:
            errors.extend(self.validate_positive_number(record, 'purchases_during', row, allow_zero=True))
        
        # Redemptions during must be >= 0 (if provided)
        if record.get('redemptions_during') is not None:
            errors.extend(self.validate_positive_number(record, 'redemptions_during', row, allow_zero=True))
        
        # Session date must not be in future
        errors.extend(self.validate_date_not_future(record, 'session_date', row))
        
        # End date must not be in future (if provided)
        if record.get('end_date'):
            errors.extend(self.validate_date_not_future(record, 'end_date', row))
        
        # Time format validation
        if record.get('session_time'):
            errors.extend(self.validate_time_format(record, 'session_time', row))
        if record.get('end_time'):
            errors.extend(self.validate_time_format(record, 'end_time', row))
        
        # End date must be >= session date (if provided)
        if record.get('end_date') and record.get('session_date'):
            errors.extend(self.validate_date_order(
                record,
                'session_date',
                'end_date',
                row,
                'End date must be on or after session date'
            ))
        
        # If same day, end_time must be > start_time
        if (record.get('end_date') and record.get('session_date') and 
            record.get('end_time') and record.get('session_time')):
            try:
                session_date_str = record['session_date']
                end_date_str = record['end_date']
                
                if session_date_str == end_date_str:
                    # Same day - check times
                    session_time = datetime.strptime(record['session_time'], '%H:%M:%S').time()
                    end_time = datetime.strptime(record['end_time'], '%H:%M:%S').time()
                    
                    if end_time <= session_time:
                        errors.append(ValidationError(
                            row_number=row,
                            field='end_time',
                            value=record['end_time'],
                            message='End time must be after start time on same day',
                            severity=ValidationSeverity.ERROR
                        ))
            except (ValueError, TypeError):
                pass  # Date/time format errors caught elsewhere
        
        # Foreign key validation
        errors.extend(self.validate_foreign_key_exists(
            record, 'user_id', row, 'users', context.existing_data
        ))
        errors.extend(self.validate_foreign_key_exists(
            record, 'site_id', row, 'sites', context.existing_data
        ))
        
        if record.get('game_id'):
            errors.extend(self.validate_foreign_key_exists(
                record, 'game_id', row, 'games', context.existing_data
            ))
        
        return errors
    
    def validate_batch(self, records: List[Dict[str, Any]]) -> List[ValidationError]:
        """Cross-record validation for game sessions.
        
        Checks for duplicate sessions (same user, site, date, time).
        """
        errors = []
        seen = {}
        
        for idx, record in enumerate(records, start=2):
            # Create unique key from user_id, site_id, session_date, session_time
            user_id = record.get('user_id')
            site_id = record.get('site_id')
            sess_date = record.get('session_date')
            sess_time = record.get('session_time', '00:00:00')
            
            if all([user_id, site_id, sess_date]):
                key = (user_id, site_id, sess_date, sess_time)
                
                if key in seen:
                    errors.append(ValidationError(
                        row_number=idx,
                        field='session_date',
                        value=sess_date,
                        message=f'Duplicate session found in CSV (row {seen[key]} has same user, site, date, time)',
                        severity=ValidationSeverity.ERROR
                    ))
                else:
                    seen[key] = idx
        
        return errors
