"""
Common input parsing utilities for UI components.
Centralized date and time parsing functions used across dialogs and forms.
"""
from datetime import date, datetime
from typing import Optional


def parse_date_input(value: str) -> Optional[date]:
    """
    Parse date from various user input formats.
    
    Supported formats:
    - MM/DD/YY or MM/DD/YYYY
    - YYYY-MM-DD
    - MM-DD-YY or MM-DD-YYYY
    - MM/DD (assumes current year)
    - MM-DD (assumes current year)
    
    Args:
        value: Date string from user input
        
    Returns:
        Parsed date object or None if parsing fails
    """
    value = value.strip()
    if not value:
        return None
    
    # Handle partial dates (MM/DD or MM-DD) by adding current year
    if "/" in value:
        parts = value.split("/")
        if len(parts) == 2:
            value = f"{parts[0]}/{parts[1]}/{date.today().year}"
    if "-" in value:
        parts = value.split("-")
        if len(parts) == 2:
            value = f"{date.today().year}-{parts[0]}-{parts[1]}"
    
    # Try various date formats
    formats = [
        "%Y-%m-%d",     # 2026-01-26
        "%m/%d/%Y",     # 01/26/2026
        "%m-%d-%Y",     # 01-26-2026
        "%m/%d/%y",     # 01/26/26
        "%m-%d-%y",     # 01-26-26
        "%Y/%m/%d",     # 2026/01/26
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    
    return None


def parse_time_input(value: str) -> Optional[str]:
    """
    Parse time from various user input formats.
    
    Supported formats:
    - HH:MM or HH:MM:SS (24-hour)
    - H:MM AM/PM or HH:MM AM/PM (12-hour with AM/PM)
    
    Args:
        value: Time string from user input
        
    Returns:
        Time in HH:MM:SS format or None if parsing fails
    """
    value = value.strip()
    if not value:
        return None
    
    formats = [
        "%H:%M:%S",      # 14:30:00
        "%H:%M",         # 14:30
        "%I:%M%p",       # 02:30PM
        "%I:%M %p",      # 02:30 PM
    ]
    
    for fmt in formats:
        try:
            parsed_time = datetime.strptime(value, fmt)
            return parsed_time.strftime("%H:%M:%S")
        except ValueError:
            continue
    
    return None


def format_date_for_display(value) -> str:
    """
    Format a date for display in the UI (MM/DD/YY format).
    
    Args:
        value: Date object, datetime object, or date string
        
    Returns:
        Formatted date string or "—" if invalid
    """
    if not value:
        return "—"
    
    if isinstance(value, date):
        return value.strftime("%m/%d/%y")
    
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%y")
    
    # Try parsing if it's a string
    if isinstance(value, str):
        parsed = parse_date_input(value)
        if parsed:
            return parsed.strftime("%m/%d/%y")
    
    return "—"


def format_time_for_display(value: str) -> str:
    """
    Format a time for display in the UI (HH:MM format).
    
    Args:
        value: Time string (any format)
        
    Returns:
        Formatted time string (HH:MM) or "—" if invalid
    """
    if not value:
        return "—"
    
    # If already HH:MM:SS, just trim to HH:MM
    if len(value) >= 5:
        return value[:5]
    
    return "—"
