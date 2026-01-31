"""
RealizedNotesService - Service for managing daily session notes

This service provides business layer methods for CRUD operations on
realized_daily_notes table. UI should use this service instead of direct SQL.
"""
from typing import Optional
from repositories.database import DatabaseManager


class RealizedNotesService:
    """Service for managing daily session notes"""

    def __init__(self, db: DatabaseManager):
        """
        Initialize service with database manager.

        Args:
            db: DatabaseManager instance for SQL operations
        """
        self.db = db

    def get_date_note(self, session_date: str) -> Optional[str]:
        """
        Get the note for a specific session date.

        Args:
            session_date: Date string (ISO format: YYYY-MM-DD)

        Returns:
            Note text if exists, None otherwise
        """
        row = self.db.fetch_one(
            "SELECT notes FROM realized_daily_notes WHERE session_date = ?",
            (session_date,),
        )
        return row["notes"] if row else None

    def set_date_note(self, session_date: str, notes: str) -> None:
        """
        Set or update the note for a specific session date.

        Args:
            session_date: Date string (ISO format: YYYY-MM-DD)
            notes: Note text to save (non-empty)
        """
        if not notes or not notes.strip():
            # If notes are empty, delete the entry instead
            self.delete_date_note(session_date)
            return

        self.db.execute(
            "INSERT OR REPLACE INTO realized_daily_notes (session_date, notes) VALUES (?, ?)",
            (session_date, notes.strip()),
        )

    def delete_date_note(self, session_date: str) -> None:
        """
        Delete the note for a specific session date.

        Args:
            session_date: Date string (ISO format: YYYY-MM-DD)
        """
        self.db.execute(
            "DELETE FROM realized_daily_notes WHERE session_date = ?",
            (session_date,),
        )
