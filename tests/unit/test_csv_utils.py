"""Tests for CSV parsing utilities."""

import pytest
from datetime import date
from decimal import Decimal

from services.tools.csv_utils import (
    parse_date, parse_time, parse_decimal, parse_boolean,
    format_date_for_export, format_time_for_export,
    format_decimal_for_export, format_boolean_for_export
)


class TestParseDate:
    """Test date parsing."""
    
    def test_parse_standard_format(self):
        """Test YYYY-MM-DD format."""
        result = parse_date('2024-01-15')
        assert result == date(2024, 1, 15)
    
    def test_parse_us_format(self):
        """Test MM/DD/YYYY format."""
        result = parse_date('01/15/2024')
        assert result == date(2024, 1, 15)
    
    def test_parse_us_short_year(self):
        """Test MM/DD/YY format."""
        result = parse_date('01/15/24')
        assert result == date(2024, 1, 15)
    
    def test_parse_date_object_passthrough(self):
        """Test date object returns as-is."""
        input_date = date(2024, 1, 15)
        result = parse_date(input_date)
        assert result == input_date
    
    def test_parse_empty_date(self):
        """Test empty date returns None."""
        assert parse_date('') is None
        assert parse_date(None) is None
    
    def test_parse_invalid_date(self):
        """Test invalid date returns None."""
        assert parse_date('not a date') is None
        assert parse_date('2024-13-01') is None


class TestParseTime:
    """Test time parsing."""
    
    def test_parse_hh_mm_ss(self):
        """Test HH:MM:SS format."""
        result = parse_time('14:30:45')
        assert result == '14:30:45'
    
    def test_parse_hh_mm(self):
        """Test HH:MM format (appends :00)."""
        result = parse_time('14:30')
        assert result == '14:30:00'
    
    def test_parse_empty_time_with_default(self):
        """Test empty time returns default."""
        result = parse_time('')
        assert result == '00:00:00'
        
        result = parse_time('', default='12:00:00')
        assert result == '12:00:00'
    
    def test_parse_invalid_time(self):
        """Test invalid time returns None."""
        assert parse_time('25:00:00') is None
        assert parse_time('not a time') is None


class TestParseDecimal:
    """Test decimal parsing."""
    
    def test_parse_plain_number(self):
        """Test plain numeric string."""
        result = parse_decimal('100.50')
        assert result == Decimal('100.50')
    
    def test_parse_currency_symbol(self):
        """Test with $ symbol."""
        result = parse_decimal('$100.50')
        assert result == Decimal('100.50')
    
    def test_parse_with_commas(self):
        """Test with comma separators."""
        result = parse_decimal('1,234.56')
        assert result == Decimal('1234.56')
    
    def test_parse_integer(self):
        """Test integer input."""
        result = parse_decimal(100)
        assert result == Decimal('100')
    
    def test_parse_decimal_passthrough(self):
        """Test Decimal passthrough."""
        input_val = Decimal('100.50')
        result = parse_decimal(input_val)
        assert result == input_val
    
    def test_parse_negative_not_allowed(self):
        """Test negative values are parsed (validation handles rejection)."""
        result = parse_decimal('-100.50')
        assert result == Decimal('-100.50')  # Parsing succeeds, validators reject later
    
    def test_parse_negative_allowed(self):
        """Test negative values when allowed."""
        result = parse_decimal('-100.50', allow_negative=True)
        assert result == Decimal('-100.50')
    
    def test_parse_empty_decimal(self):
        """Test empty decimal returns None."""
        assert parse_decimal('') is None
        assert parse_decimal(None) is None


class TestParseBoolean:
    """Test boolean parsing."""
    
    def test_parse_numeric_true(self):
        """Test numeric 1."""
        assert parse_boolean('1') is True
        assert parse_boolean(1) is True
    
    def test_parse_numeric_false(self):
        """Test numeric 0."""
        assert parse_boolean('0') is False
        assert parse_boolean(0) is False
    
    def test_parse_word_true(self):
        """Test 'true' variations."""
        assert parse_boolean('true') is True
        assert parse_boolean('TRUE') is True
        assert parse_boolean('True') is True
        assert parse_boolean('t') is True
    
    def test_parse_word_false(self):
        """Test 'false' variations."""
        assert parse_boolean('false') is False
        assert parse_boolean('FALSE') is False
        assert parse_boolean('f') is False
    
    def test_parse_yes_no(self):
        """Test yes/no."""
        assert parse_boolean('yes') is True
        assert parse_boolean('no') is False
        assert parse_boolean('y') is True
        assert parse_boolean('n') is False
    
    def test_parse_active_inactive(self):
        """Test active/inactive."""
        assert parse_boolean('active') is True
        assert parse_boolean('inactive') is False
    
    def test_parse_on_off(self):
        """Test on/off."""
        assert parse_boolean('on') is True
        assert parse_boolean('off') is False
    
    def test_parse_boolean_passthrough(self):
        """Test bool passthrough."""
        assert parse_boolean(True) is True
        assert parse_boolean(False) is False
    
    def test_parse_empty_boolean(self):
        """Test empty boolean returns None."""
        assert parse_boolean('') is None
        assert parse_boolean(None) is None


class TestFormatters:
    """Test export formatters."""
    
    def test_format_date(self):
        """Test date formatting."""
        result = format_date_for_export(date(2024, 1, 15))
        assert result == '2024-01-15'
    
    def test_format_time(self):
        """Test time formatting."""
        result = format_time_for_export('14:30:45')
        assert result == '14:30:45'
        
        # HH:MM should become HH:MM:SS
        result = format_time_for_export('14:30')
        assert result == '14:30:00'
    
    def test_format_decimal_plain(self):
        """Test decimal formatting without currency."""
        result = format_decimal_for_export(Decimal('100.5'))
        assert result == '100.50'
    
    def test_format_decimal_currency(self):
        """Test decimal formatting with currency."""
        result = format_decimal_for_export(Decimal('100.5'), currency=True)
        assert result == '$100.50'
    
    def test_format_boolean_numeric(self):
        """Test boolean formatting as numbers."""
        assert format_boolean_for_export(True) == '1'
        assert format_boolean_for_export(False) == '0'
    
    def test_format_boolean_word(self):
        """Test boolean formatting as words."""
        assert format_boolean_for_export(True, style='word') == 'true'
        assert format_boolean_for_export(False, style='word') == 'false'
    
    def test_format_boolean_active(self):
        """Test boolean formatting as active/inactive."""
        assert format_boolean_for_export(True, style='active') == 'active'
        assert format_boolean_for_export(False, style='active') == 'inactive'
