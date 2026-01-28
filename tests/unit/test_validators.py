"""Tests for validation framework."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from sezzions.services.tools.validators import (
    PurchaseValidator,
    RedemptionValidator,
    GameSessionValidator,
)
from sezzions.services.tools.dtos import ValidationContext, ValidationSeverity


class TestPurchaseValidator:
    """Tests for PurchaseValidator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = PurchaseValidator()
        self.context = ValidationContext(
            row_number=2,
            entity_type='purchases',
            existing_data={
                'users_by_id': {1: 'Alice', 2: 'Bob'},
                'sites_by_id': {1: 'Site A', 2: 'Site B'},
                'cards_by_id': {1: 'Visa 1234', 2: 'MC 5678'},
            },
            strict_mode=True
        )
    
    def test_valid_purchase(self):
        """Test validation of a valid purchase record."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': '2026-01-15',
            'purchase_time': '14:30:00',
            'amount': '100.00',
            'sc_received': '100.00',
            'starting_sc_balance': '100.00',
            'cashback_earned': '5.00',
            'card_id': 1,
            'notes': 'Test purchase'
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert len(errors) == 0
    
    def test_missing_required_fields(self):
        """Test that missing required fields are caught."""
        record = {
            # Missing user_id, site_id, purchase_date, amount, sc_received
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert len(errors) >= 5
        assert any(e.field == 'user_id' for e in errors)
        assert any(e.field == 'site_id' for e in errors)
        assert any(e.field == 'purchase_date' for e in errors)
        assert any(e.field == 'amount' for e in errors)
        assert any(e.field == 'sc_received' for e in errors)
    
    def test_negative_amount(self):
        """Test that negative amount is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': '2026-01-15',
            'amount': '-100.00',
            'sc_received': '100.00',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'amount' and 'positive' in e.message.lower() for e in errors)
    
    def test_zero_amount(self):
        """Test that zero amount is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': '2026-01-15',
            'amount': '0',
            'sc_received': '0',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'amount' and 'positive' in e.message.lower() for e in errors)
    
    def test_future_date(self):
        """Test that future date is rejected."""
        future_date = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': future_date,
            'amount': '100.00',
            'sc_received': '100.00',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'purchase_date' and 'future' in e.message.lower() for e in errors)
    
    def test_invalid_time_format(self):
        """Test that invalid time format is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': '2026-01-15',
            'purchase_time': '25:99:99',  # Invalid
            'amount': '100.00',
            'sc_received': '100.00',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'purchase_time' and 'time' in e.message.lower() for e in errors)
    
    def test_balance_less_than_received(self):
        """Test that balance < sc_received is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'purchase_date': '2026-01-15',
            'amount': '100.00',
            'sc_received': '100.00',
            'starting_sc_balance': '50.00',  # Less than received
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'starting_sc_balance' for e in errors)
    
    def test_duplicate_in_batch(self):
        """Test that duplicate purchases in same CSV are caught."""
        records = [
            {
                'user_id': 1,
                'site_id': 1,
                'purchase_date': '2026-01-15',
                'purchase_time': '14:30:00',
                'amount': '100.00',
                'sc_received': '100.00',
            },
            {
                'user_id': 1,
                'site_id': 1,
                'purchase_date': '2026-01-15',
                'purchase_time': '14:30:00',  # Duplicate!
                'amount': '200.00',
                'sc_received': '200.00',
            },
        ]
        
        errors = self.validator.validate_batch(records)
        
        assert len(errors) == 1
        assert 'duplicate' in errors[0].message.lower()


class TestRedemptionValidator:
    """Tests for RedemptionValidator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = RedemptionValidator()
        self.context = ValidationContext(
            row_number=2,
            entity_type='redemptions',
            existing_data={
                'users_by_id': {1: 'Alice'},
                'sites_by_id': {1: 'Site A'},
                'redemption_methods_by_id': {1: 'PayPal'},
            },
            strict_mode=True
        )
    
    def test_valid_redemption(self):
        """Test validation of a valid redemption record."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'redemption_date': '2026-01-15',
            'redemption_time': '14:30:00',
            'amount': '100.00',
            'fees': '2.50',
            'redemption_method_id': 1,
            'receipt_date': '2026-01-16',
            'notes': 'Test redemption'
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert len(errors) == 0
    
    def test_fees_exceed_amount(self):
        """Test that fees > amount is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'redemption_date': '2026-01-15',
            'amount': '100.00',
            'fees': '150.00',  # Exceeds amount
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'fees' and 'exceed' in e.message.lower() for e in errors)
    
    def test_receipt_before_redemption(self):
        """Test that receipt_date < redemption_date is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'redemption_date': '2026-01-15',
            'amount': '100.00',
            'receipt_date': '2026-01-10',  # Before redemption
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'receipt_date' for e in errors)


class TestGameSessionValidator:
    """Tests for GameSessionValidator."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.validator = GameSessionValidator()
        self.context = ValidationContext(
            row_number=2,
            entity_type='game_sessions',
            existing_data={
                'users_by_id': {1: 'Alice'},
                'sites_by_id': {1: 'Site A'},
                'games_by_id': {1: 'Slots Game'},
            },
            strict_mode=True
        )
    
    def test_valid_session(self):
        """Test validation of a valid game session record."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'game_id': 1,
            'session_date': '2026-01-15',
            'session_time': '14:00:00',
            'starting_balance': '100.00',
            'ending_balance': '150.00',
            'purchases_during': '50.00',
            'redemptions_during': '0.00',
            'end_date': '2026-01-15',
            'end_time': '15:00:00',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert len(errors) == 0
    
    def test_negative_balance(self):
        """Test that negative balance is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'session_date': '2026-01-15',
            'starting_balance': '-50.00',
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'starting_balance' for e in errors)
    
    def test_end_before_start_same_day(self):
        """Test that end_time before start_time on same day is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'session_date': '2026-01-15',
            'session_time': '15:00:00',
            'starting_balance': '100.00',
            'end_date': '2026-01-15',
            'end_time': '14:00:00',  # Before start time
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'end_time' and 'after' in e.message.lower() for e in errors)
    
    def test_end_date_before_start_date(self):
        """Test that end_date < session_date is rejected."""
        record = {
            'user_id': 1,
            'site_id': 1,
            'session_date': '2026-01-15',
            'starting_balance': '100.00',
            'end_date': '2026-01-10',  # Before start
        }
        
        errors = self.validator.validate_record(record, self.context)
        
        assert any(e.field == 'end_date' for e in errors)


class TestBaseValidatorUtilities:
    """Tests for base validator utility methods."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Use PurchaseValidator as a concrete implementation
        self.validator = PurchaseValidator()
    
    def test_validate_positive_number_zero_allowed(self):
        """Test positive number validation with zero allowed."""
        record = {'amount': '0'}
        errors = self.validator.validate_positive_number(
            record, 'amount', 1, allow_zero=True
        )
        assert len(errors) == 0
    
    def test_validate_positive_number_zero_not_allowed(self):
        """Test positive number validation with zero not allowed."""
        record = {'amount': '0'}
        errors = self.validator.validate_positive_number(
            record, 'amount', 1, allow_zero=False
        )
        assert len(errors) == 1
        assert 'positive' in errors[0].message.lower()
    
    def test_validate_date_format_valid(self):
        """Test date validation with valid format."""
        record = {'test_date': '2026-01-15'}
        errors = self.validator.validate_date_not_future(record, 'test_date', 1)
        assert len(errors) == 0
    
    def test_validate_date_format_invalid(self):
        """Test date validation with invalid format."""
        record = {'test_date': '01/15/2026'}  # Wrong format
        errors = self.validator.validate_date_not_future(record, 'test_date', 1)
        # Should have format error
        assert any('format' in e.message.lower() for e in errors)
    
    def test_validate_time_format_hh_mm(self):
        """Test time format validation with HH:MM."""
        record = {'test_time': '14:30'}
        errors = self.validator.validate_time_format(record, 'test_time', 1)
        assert len(errors) == 0
    
    def test_validate_time_format_hh_mm_ss(self):
        """Test time format validation with HH:MM:SS."""
        record = {'test_time': '14:30:45'}
        errors = self.validator.validate_time_format(record, 'test_time', 1)
        assert len(errors) == 0
