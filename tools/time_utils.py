"""
Time Utilities for Sezzions
Provides standardized time parsing and formatting with seconds precision.
Implements boundary rules for Issue #90.
"""
from datetime import datetime, time as time_type
from typing import Optional


# Display format with seconds precision
TIME_DISPLAY_FORMAT = "%H:%M:%S"


def parse_time_input(time_str: str) -> Optional[time_type]:
    """
    Parse time input string into time object with seconds precision.
    
    Rules (Issue #90):
    - Empty/None/blank → None (caller decides default)
    - "HH:MM" → HH:MM:00
    - "HH:MM:SS" → HH:MM:SS (preserved)
    - Invalid format → None
    
    Args:
        time_str: Time string from user input
        
    Returns:
        time object with seconds precision, or None if invalid/empty
        
    Examples:
        >>> parse_time_input("13:16")
        time(13, 16, 0)
        >>> parse_time_input("13:16:45")
        time(13, 16, 45)
        >>> parse_time_input("")
        None
    """
    if not time_str or not time_str.strip():
        return None
    
    time_str = time_str.strip()
    
    # Try HH:MM:SS format first
    try:
        dt = datetime.strptime(time_str, "%H:%M:%S")
        return dt.time()
    except ValueError:
        pass
    
    # Try HH:MM format (append :00)
    try:
        dt = datetime.strptime(time_str, "%H:%M")
        return dt.time()  # Will have seconds=0
    except ValueError:
        pass
    
    # Invalid format
    return None


def current_time_with_seconds() -> time_type:
    """
    Get current time with seconds precision.
    Used for blank time inputs.
    
    Returns:
        Current time with HH:MM:SS precision
    """
    return datetime.now().time()


def format_time_display(t: Optional[time_type]) -> str:
    """
    Format time object for display with seconds precision.
    
    Args:
        t: time object or None
        
    Returns:
        "HH:MM:SS" string, or empty string if None
        
    Examples:
        >>> format_time_display(time(13, 16, 45))
        "13:16:45"
        >>> format_time_display(None)
        ""
    """
    if t is None:
        return ""
    return t.strftime(TIME_DISPLAY_FORMAT)


def time_to_db_string(t: Optional[time_type]) -> Optional[str]:
    """
    Convert time object to database string format (HH:MM:SS).
    
    Args:
        t: time object or None
        
    Returns:
        "HH:MM:SS" string for database storage, or None
    """
    if t is None:
        return None
    return t.strftime("%H:%M:%S")


def db_string_to_time(s: Optional[str]) -> Optional[time_type]:
    """
    Parse database time string to time object.
    Handles both HH:MM and HH:MM:SS formats for backward compatibility.
    
    Args:
        s: Time string from database
        
    Returns:
        time object or None
    """
    if not s:
        return None
    return parse_time_input(s)


def is_time_in_session_window(
    event_time: time_type,
    session_start: time_type,
    session_end: time_type
) -> bool:
    """
    Check if event time falls within session window.
    
    Boundary rules (Issue #90):
    - Session start: INCLUSIVE (>=)
    - Session end: EXCLUSIVE (<)
    - Event exactly at start → DURING (included)
    - Event exactly at end → AFTER (excluded)
    - Zero-duration sessions → naturally empty window
    
    Args:
        event_time: Time of purchase/redemption/checkpoint
        session_start: Session start_time
        session_end: Session end_time
        
    Returns:
        True if event is DURING session (start <= event < end)
        
    Examples:
        >>> is_time_in_session_window(
        ...     time(13, 16, 0), time(13, 16, 0), time(13, 17, 0))
        True  # At start → DURING
        >>> is_time_in_session_window(
        ...     time(13, 17, 0), time(13, 16, 0), time(13, 17, 0))
        False  # At end → AFTER
        >>> is_time_in_session_window(
        ...     time(13, 16, 30), time(13, 16, 0), time(13, 16, 0))
        False  # Zero-duration session → nothing DURING
    """
    return session_start <= event_time < session_end


def is_purchase_after_checkpoint(
    purchase_time: time_type,
    checkpoint_time: time_type
) -> bool:
    """
    Check if purchase is after checkpoint (for basis window).
    
    Boundary rule:
    - Checkpoint: EXCLUSIVE (>)
    - Purchase exactly at checkpoint → BEFORE (excluded from basis)
    
    Args:
        purchase_time: Time of purchase
        checkpoint_time: Last checkpoint before session
        
    Returns:
        True if purchase is after checkpoint (purchase > checkpoint)
        
    Examples:
        >>> is_purchase_after_checkpoint(time(12, 43, 0), time(12, 42, 0))
        True
        >>> is_purchase_after_checkpoint(time(12, 42, 0), time(12, 42, 0))
        False  # Exact match → BEFORE
    """
    return purchase_time > checkpoint_time
