"""
Tests for time_utils module (Issue #90: Time precision and edge case handling).
"""
import pytest
from datetime import time
from tools.time_utils import (
    parse_time_input,
    current_time_with_seconds,
    format_time_display,
    time_to_db_string,
    db_string_to_time,
    is_time_in_session_window,
    is_purchase_after_checkpoint,
)


class TestParseTimeInput:
    """Test time input parsing with various formats."""
    
    def test_parse_hh_mm_format(self):
        """HH:MM input should append :00 for seconds."""
        result = parse_time_input("13:16")
        assert result == time(13, 16, 0)
    
    def test_parse_hh_mm_ss_format(self):
        """HH:MM:SS input should preserve seconds."""
        result = parse_time_input("13:16:45")
        assert result == time(13, 16, 45)
    
    def test_parse_empty_string(self):
        """Empty string should return None."""
        assert parse_time_input("") is None
        assert parse_time_input("   ") is None
    
    def test_parse_none(self):
        """None should return None."""
        assert parse_time_input(None) is None
    
    def test_parse_invalid_format(self):
        """Invalid format should return None."""
        assert parse_time_input("invalid") is None
        assert parse_time_input("25:00") is None
        assert parse_time_input("13") is None
    
    def test_parse_with_whitespace(self):
        """Should strip whitespace."""
        result = parse_time_input("  13:16:45  ")
        assert result == time(13, 16, 45)


class TestCurrentTime:
    """Test current time function."""
    
    def test_current_time_returns_time_object(self):
        """Should return time object with seconds."""
        result = current_time_with_seconds()
        assert isinstance(result, time)
        assert 0 <= result.hour <= 23
        assert 0 <= result.minute <= 59
        assert 0 <= result.second <= 59


class TestFormatTimeDisplay:
    """Test time display formatting."""
    
    def test_format_with_seconds(self):
        """Should format as HH:MM:SS."""
        t = time(13, 16, 45)
        result = format_time_display(t)
        assert result == "13:16:45"
    
    def test_format_without_seconds(self):
        """Should show :00 for zero seconds."""
        t = time(13, 16, 0)
        result = format_time_display(t)
        assert result == "13:16:00"
    
    def test_format_none(self):
        """None should return empty string."""
        assert format_time_display(None) == ""
    
    def test_format_midnight(self):
        """Midnight should format as 00:00:00."""
        t = time(0, 0, 0)
        result = format_time_display(t)
        assert result == "00:00:00"


class TestDatabaseConversions:
    """Test database string conversions."""
    
    def test_time_to_db_string(self):
        """Should convert to HH:MM:SS string."""
        t = time(13, 16, 45)
        result = time_to_db_string(t)
        assert result == "13:16:45"
    
    def test_time_to_db_string_none(self):
        """None should return None."""
        assert time_to_db_string(None) is None
    
    def test_db_string_to_time_with_seconds(self):
        """Should parse HH:MM:SS from database."""
        result = db_string_to_time("13:16:45")
        assert result == time(13, 16, 45)
    
    def test_db_string_to_time_without_seconds(self):
        """Should handle legacy HH:MM format (backward compatibility)."""
        result = db_string_to_time("13:16")
        assert result == time(13, 16, 0)
    
    def test_db_string_to_time_none(self):
        """None/empty should return None."""
        assert db_string_to_time(None) is None
        assert db_string_to_time("") is None
    
    def test_round_trip(self):
        """Round-trip conversion should preserve value."""
        original = time(13, 16, 45)
        db_str = time_to_db_string(original)
        recovered = db_string_to_time(db_str)
        assert recovered == original


class TestSessionWindowBoundaries:
    """Test session window boundary logic (Issue #90 edge cases)."""
    
    def test_event_during_session(self):
        """Event in middle of session → DURING."""
        event = time(13, 16, 30)
        start = time(13, 16, 0)
        end = time(13, 17, 0)
        assert is_time_in_session_window(event, start, end) is True
    
    def test_event_before_session(self):
        """Event before start → NOT during."""
        event = time(13, 15, 59)
        start = time(13, 16, 0)
        end = time(13, 17, 0)
        assert is_time_in_session_window(event, start, end) is False
    
    def test_event_after_session(self):
        """Event after end → NOT during."""
        event = time(13, 17, 1)
        start = time(13, 16, 0)
        end = time(13, 17, 0)
        assert is_time_in_session_window(event, start, end) is False
    
    def test_event_exactly_at_start(self):
        """Event exactly at start → DURING (inclusive start)."""
        event = time(13, 16, 0)
        start = time(13, 16, 0)
        end = time(13, 17, 0)
        assert is_time_in_session_window(event, start, end) is True
    
    def test_event_exactly_at_end(self):
        """Event exactly at end → AFTER (exclusive end)."""
        event = time(13, 17, 0)
        start = time(13, 16, 0)
        end = time(13, 17, 0)
        assert is_time_in_session_window(event, start, end) is False
    
    def test_zero_duration_session(self):
        """Zero-duration session → naturally empty window."""
        event = time(13, 16, 0)
        start = time(13, 16, 0)
        end = time(13, 16, 0)
        # start <= event < end → 13:16:00 <= 13:16:00 < 13:16:00 → False
        assert is_time_in_session_window(event, start, end) is False
    
    def test_session_with_seconds_precision(self):
        """Seconds precision affects window boundaries."""
        # Purchase at 13:16:05
        event = time(13, 16, 5)
        # Session 13:16:00 to 13:16:45
        start = time(13, 16, 0)
        end = time(13, 16, 45)
        assert is_time_in_session_window(event, start, end) is True
        
        # Purchase at 13:16:45 (exactly at end)
        event_at_end = time(13, 16, 45)
        assert is_time_in_session_window(event_at_end, start, end) is False


class TestCheckpointBoundaries:
    """Test checkpoint boundary logic for basis window."""
    
    def test_purchase_after_checkpoint(self):
        """Purchase after checkpoint → included in basis."""
        purchase = time(12, 43, 0)
        checkpoint = time(12, 42, 0)
        assert is_purchase_after_checkpoint(purchase, checkpoint) is True
    
    def test_purchase_before_checkpoint(self):
        """Purchase before checkpoint → NOT included."""
        purchase = time(12, 41, 0)
        checkpoint = time(12, 42, 0)
        assert is_purchase_after_checkpoint(purchase, checkpoint) is False
    
    def test_purchase_exactly_at_checkpoint(self):
        """Purchase exactly at checkpoint → BEFORE (exclusive)."""
        purchase = time(12, 42, 0)
        checkpoint = time(12, 42, 0)
        assert is_purchase_after_checkpoint(purchase, checkpoint) is False
    
    def test_purchase_with_seconds_after_checkpoint(self):
        """Seconds precision affects checkpoint boundary."""
        purchase = time(12, 42, 5)
        checkpoint = time(12, 42, 0)
        assert is_purchase_after_checkpoint(purchase, checkpoint) is True


class TestRealWorldScenarios:
    """Test scenarios from Session 145 and 147 (Issue #88/#90)."""
    
    def test_session_147_scenario(self):
        """
        Session 147: Start 13:16:00, End 13:16:45
        Purchase 1: 13:16:05 → DURING
        Purchase 2: 13:16:30 → DURING
        
        Before fix: times showed 13:16:00 (precision loss)
        After fix: seconds preserved, both purchases DURING
        """
        start = time(13, 16, 0)
        end = time(13, 16, 45)
        
        purchase1 = time(13, 16, 5)
        purchase2 = time(13, 16, 30)
        
        assert is_time_in_session_window(purchase1, start, end) is True
        assert is_time_in_session_window(purchase2, start, end) is True
    
    def test_session_145_basis_window(self):
        """
        Session 145: Checkpoint 12:42:00, Session starts after
        Purchase 1: 12:42:00 (BEFORE checkpoint) → NOT in basis
        Purchase 2: 12:43:00 (DURING session) → in basis
        """
        checkpoint = time(12, 42, 0)
        
        purchase_at_checkpoint = time(12, 42, 0)
        purchase_after = time(12, 43, 0)
        
        # Checkpoint is exclusive
        assert is_purchase_after_checkpoint(purchase_at_checkpoint, checkpoint) is False
        assert is_purchase_after_checkpoint(purchase_after, checkpoint) is True
