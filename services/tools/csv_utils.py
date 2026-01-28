"""CSV parsing utilities for Tools import/export."""

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def parse_date(value: Any) -> Optional[date]:
    """Parse date from various formats to YYYY-MM-DD date object.
    
    Supports:
    - YYYY-MM-DD (standard)
    - MM/DD/YYYY or MM/DD/YY (US format)
    - date objects (passthrough)
    
    Args:
        value: Date value to parse
    
    Returns:
        date object or None if parsing fails
    """
    if value is None or value == '':
        return None
    
    if isinstance(value, date):
        return value
    
    if isinstance(value, datetime):
        return value.date()
    
    value_str = str(value).strip()
    
    # Try YYYY-MM-DD format first (standard)
    try:
        return datetime.strptime(value_str, '%Y-%m-%d').date()
    except ValueError:
        pass
    
    # Try MM/DD/YYYY format
    try:
        return datetime.strptime(value_str, '%m/%d/%Y').date()
    except ValueError:
        pass
    
    # Try MM/DD/YY format
    try:
        return datetime.strptime(value_str, '%m/%d/%y').date()
    except ValueError:
        pass
    
    return None


def parse_time(value: Any, default: str = '00:00:00') -> Optional[str]:
    """Parse time to HH:MM:SS format.
    
    Supports:
    - HH:MM:SS
    - HH:MM (appends :00)
    - Empty/None returns default
    
    Args:
        value: Time value to parse
        default: Default time if value is empty
    
    Returns:
        Time string in HH:MM:SS format or None if invalid
    """
    if value is None or value == '':
        return default
    
    value_str = str(value).strip()
    
    # Try HH:MM:SS format
    try:
        parsed = datetime.strptime(value_str, '%H:%M:%S')
        return parsed.strftime('%H:%M:%S')
    except ValueError:
        pass
    
    # Try HH:MM format (append :00)
    try:
        parsed = datetime.strptime(value_str, '%H:%M')
        return parsed.strftime('%H:%M:00')
    except ValueError:
        pass
    
    return None


def parse_decimal(value: Any, allow_negative: bool = False) -> Optional[Decimal]:
    """Parse decimal number from string, stripping currency symbols.
    
    Supports:
    - Plain numbers: "100", "100.50"
    - Currency: "$100.50", "100.50 USD"
    - Commas: "1,000.50"
    
    Args:
        value: Numeric value to parse
        allow_negative: Whether to allow negative values
    
    Returns:
        Decimal object or None if parsing fails
    """
    if value is None or value == '':
        return None
    
    # Already a Decimal
    if isinstance(value, Decimal):
        return value
    
    # Numeric types
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    
    # String parsing
    value_str = str(value).strip()
    
    # Remove common currency symbols and separators
    cleaned = value_str.replace('$', '').replace('USD', '').replace('€', '').replace('£', '')
    cleaned = cleaned.replace(',', '').strip()
    
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_boolean(value: Any) -> Optional[bool]:
    """Parse boolean from various formats.
    
    Supports:
    - 1/0
    - true/false (case insensitive)
    - yes/no (case insensitive)
    - active/inactive (case insensitive)
    - on/off (case insensitive)
    
    Args:
        value: Boolean value to parse
    
    Returns:
        bool or None if parsing fails
    """
    if value is None or value == '':
        return None
    
    if isinstance(value, bool):
        return value
    
    # Numeric values
    if isinstance(value, (int, float)):
        return value != 0
    
    # String parsing
    value_str = str(value).strip().lower()
    
    true_values = {'1', 'true', 't', 'yes', 'y', 'active', 'on'}
    false_values = {'0', 'false', 'f', 'no', 'n', 'inactive', 'off'}
    
    if value_str in true_values:
        return True
    if value_str in false_values:
        return False
    
    return None


def format_date_for_export(value: Any) -> str:
    """Format date for CSV export (YYYY-MM-DD)."""
    if value is None:
        return ''
    
    if isinstance(value, str):
        # Already a string, assume it's formatted
        return value
    
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    
    return str(value)


def format_time_for_export(value: Any) -> str:
    """Format time for CSV export (HH:MM:SS)."""
    if value is None:
        return ''
    
    if isinstance(value, str):
        # Ensure HH:MM:SS format
        parsed = parse_time(value)
        return parsed if parsed else value
    
    return str(value)


def format_decimal_for_export(value: Any, currency: bool = False) -> str:
    """Format decimal for CSV export.
    
    Args:
        value: Decimal value to format
        currency: Whether to add $ prefix
    
    Returns:
        Formatted string
    """
    if value is None:
        return ''
    
    try:
        decimal_value = Decimal(str(value))
        formatted = f"{decimal_value:.2f}"
        
        if currency:
            return f"${formatted}"
        return formatted
    except (InvalidOperation, ValueError):
        return str(value)


def format_boolean_for_export(value: Any, style: str = 'numeric') -> str:
    """Format boolean for CSV export.
    
    Args:
        value: Boolean value to format
        style: 'numeric' (1/0), 'word' (true/false), or 'active' (active/inactive)
    
    Returns:
        Formatted string
    """
    if value is None:
        return ''
    
    # Convert to boolean
    if isinstance(value, str):
        bool_value = parse_boolean(value)
    elif isinstance(value, (int, float)):
        bool_value = value != 0
    else:
        bool_value = bool(value)
    
    if bool_value is None:
        return ''
    
    if style == 'numeric':
        return '1' if bool_value else '0'
    elif style == 'word':
        return 'true' if bool_value else 'false'
    elif style == 'active':
        return 'active' if bool_value else 'inactive'
    else:
        return '1' if bool_value else '0'
