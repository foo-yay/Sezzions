"""
Tests for RealizedNotesService - Daily session notes CRUD
"""
import pytest
from services.realized_notes_service import RealizedNotesService
from repositories.database import DatabaseManager


@pytest.fixture
def db():
    """Create test database"""
    db = DatabaseManager(":memory:")
    yield db
    db.close()


@pytest.fixture
def service(db):
    """Create service instance"""
    return RealizedNotesService(db)


def test_get_date_note_nonexistent(service):
    """Test getting a note that doesn't exist returns None"""
    result = service.get_date_note("2024-01-15")
    assert result is None


def test_set_and_get_date_note(service):
    """Test setting and retrieving a note"""
    service.set_date_note("2024-01-15", "Test note")
    result = service.get_date_note("2024-01-15")
    assert result == "Test note"


def test_update_existing_note(service):
    """Test updating an existing note"""
    service.set_date_note("2024-01-15", "Original note")
    service.set_date_note("2024-01-15", "Updated note")
    result = service.get_date_note("2024-01-15")
    assert result == "Updated note"


def test_set_empty_note_deletes(service):
    """Test that setting an empty note deletes the entry"""
    service.set_date_note("2024-01-15", "Test note")
    service.set_date_note("2024-01-15", "")
    result = service.get_date_note("2024-01-15")
    assert result is None


def test_set_whitespace_only_note_deletes(service):
    """Test that setting whitespace-only note deletes the entry"""
    service.set_date_note("2024-01-15", "Test note")
    service.set_date_note("2024-01-15", "   ")
    result = service.get_date_note("2024-01-15")
    assert result is None


def test_delete_date_note(service):
    """Test deleting a note"""
    service.set_date_note("2024-01-15", "Test note")
    service.delete_date_note("2024-01-15")
    result = service.get_date_note("2024-01-15")
    assert result is None


def test_delete_nonexistent_note(service):
    """Test deleting a note that doesn't exist (should not raise error)"""
    service.delete_date_note("2024-01-15")
    # Should complete without error


def test_multiple_dates(service):
    """Test managing notes for multiple dates"""
    service.set_date_note("2024-01-15", "Note for Jan 15")
    service.set_date_note("2024-01-16", "Note for Jan 16")
    service.set_date_note("2024-01-17", "Note for Jan 17")
    
    assert service.get_date_note("2024-01-15") == "Note for Jan 15"
    assert service.get_date_note("2024-01-16") == "Note for Jan 16"
    assert service.get_date_note("2024-01-17") == "Note for Jan 17"
    
    service.delete_date_note("2024-01-16")
    assert service.get_date_note("2024-01-15") == "Note for Jan 15"
    assert service.get_date_note("2024-01-16") is None
    assert service.get_date_note("2024-01-17") == "Note for Jan 17"


def test_note_trimming(service):
    """Test that notes are trimmed when saved"""
    service.set_date_note("2024-01-15", "  Test note with spaces  ")
    result = service.get_date_note("2024-01-15")
    assert result == "Test note with spaces"
