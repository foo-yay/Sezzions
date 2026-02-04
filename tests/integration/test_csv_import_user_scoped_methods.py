"""Integration tests for user-scoped FK resolution in CSV imports (Issue #36)."""

import pytest
import tempfile
import csv
import sqlite3
from pathlib import Path

from services.tools.csv_import_service import CSVImportService


@pytest.fixture
def db_conn():
    """Create simple in-memory SQLite connection."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create test tables
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE sites (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE redemption_methods (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            method_type TEXT,
            user_id INTEGER,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE redemptions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            amount TEXT NOT NULL,
            fees TEXT DEFAULT '0.00',
            redemption_date TEXT NOT NULL,
            redemption_time TEXT DEFAULT '00:00:00',
            redemption_method_id INTEGER,
            receipt_date TEXT,
            is_free_sc INTEGER DEFAULT 0,
            processed INTEGER DEFAULT 0,
            notes TEXT,
            more_remaining INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (redemption_method_id) REFERENCES redemption_methods(id)
        )
    """)
    
    # Insert test reference data
    cursor.execute("INSERT INTO users (id, name) VALUES (1, 'fooyay')")
    cursor.execute("INSERT INTO users (id, name) VALUES (2, 'mrs. fooyay')")
    cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'Stake')")
    
    # Insert redemption methods with same name for different users
    cursor.execute("INSERT INTO redemption_methods (id, name, user_id) VALUES (1, 'USAA Checking', 1)")
    cursor.execute("INSERT INTO redemption_methods (id, name, user_id) VALUES (2, 'USAA Checking', 2)")
    cursor.execute("INSERT INTO redemption_methods (id, name, user_id) VALUES (3, 'PayPal', 1)")
    
    conn.commit()
    
    yield conn
    conn.close()


@pytest.fixture
def db(db_conn):
    """Wrap connection in a simple DB manager-like object."""
    class SimpleDB:
        def __init__(self, connection):
            self._connection = connection
        
        def fetch_all(self, query, params=None):
            cursor = self._connection.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()
        
        def fetch_one(self, query, params=None):
            cursor = self._connection.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchone()
        
        def execute(self, query, params=None):
            cursor = self._connection.cursor()
            cursor.execute(query, params or ())
            return cursor.lastrowid
        
        def commit(self):
            self._connection.commit()
        
        def rollback(self):
            self._connection.rollback()
        
        def transaction(self):
            """Simple context manager for transactions."""
            from contextlib import contextmanager
            
            @contextmanager
            def _transaction():
                try:
                    yield self
                    self._connection.commit()
                except Exception:
                    self._connection.rollback()
                    raise
            
            return _transaction()
    
    return SimpleDB(db_conn)


@pytest.fixture
def import_service(db):
    """Create CSV import service."""
    return CSVImportService(db)


@pytest.fixture
def temp_csv():
    """Create temporary CSV file."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
    try:
        temp_path = temp_file.name
    finally:
        temp_file.close()

    yield temp_path
    Path(temp_path).unlink(missing_ok=True)


class TestUserScopedMethodResolution:
    """Test user-scoped FK resolution for redemption methods (Issue #36)."""
    
    def test_import_redemptions_with_duplicate_method_names_across_users(self, import_service, temp_csv):
        """Test importing redemptions where two users have methods with same name."""
        # Create CSV with two redemptions using "USAA Checking" for different users
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Redemption Date', 'Amount', 'Method Name'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'fooyay',
                'Site Name': 'Stake',
                'Redemption Date': '2024-01-15',
                'Amount': '100.00',
                'Method Name': 'USAA Checking'
            })
            writer.writerow({
                'User Name': 'mrs. fooyay',
                'Site Name': 'Stake',
                'Redemption Date': '2024-01-16',
                'Amount': '200.00',
                'Method Name': 'USAA Checking'
            })
        
        # Preview import
        preview = import_service.preview_import(temp_csv, 'redemptions')
        
        # Should not have errors (no ambiguity because each user's method is distinct)
        assert len(preview.invalid_rows) == 0
        assert not preview.has_errors
        assert len(preview.to_add) == 2
        
        # Verify correct method IDs resolved
        redemption_fooyay = [r for r in preview.to_add if r['user_id'] == 1][0]
        redemption_mrs = [r for r in preview.to_add if r['user_id'] == 2][0]
        
        assert redemption_fooyay['redemption_method_id'] == 1  # fooyay's USAA Checking
        assert redemption_mrs['redemption_method_id'] == 2  # mrs. fooyay's USAA Checking
        
        # Execute import
        result = import_service.execute_import(temp_csv, 'redemptions')
        
        assert result.success is True
        assert result.records_added == 2
        assert result.records_updated == 0
    
    def test_import_redemption_method_not_found_for_user(self, import_service, temp_csv, db):
        """Test error when method exists for another user but not for the row's user."""
        # Create CSV where mrs. fooyay tries to use PayPal (which only exists for fooyay)
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Redemption Date', 'Amount', 'Method Name'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'mrs. fooyay',
                'Site Name': 'Stake',
                'Redemption Date': '2024-01-15',
                'Amount': '100.00',
                'Method Name': 'PayPal'
            })
        
        # Preview should detect error
        preview = import_service.preview_import(temp_csv, 'redemptions')
        
        assert len(preview.invalid_rows) > 0
        assert preview.has_errors
        assert len(preview.to_add) == 0
        
        # Error should mention user_id
        error = preview.invalid_rows[0]
        assert 'PayPal' in error.message
        assert 'user_id=2' in error.message
    
    def test_import_redemption_ambiguous_for_same_user(self, import_service, temp_csv, db):
        """Test error when the same user has multiple methods with same normalized name."""
        # Add a second "USAA Checking" for fooyay (same name, creates ambiguity)
        db.execute("INSERT INTO redemption_methods (id, name, user_id) VALUES (4, 'USAA  Checking', 1)")
        db.commit()
        
        # Clear FK cache so it picks up the new duplicate method
        import_service.fk_resolver.clear()
        
        # Create CSV
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Redemption Date', 'Amount', 'Method Name'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'fooyay',
                'Site Name': 'Stake',
                'Redemption Date': '2024-01-15',
                'Amount': '100.00',
                'Method Name': 'USAA Checking'
            })
        
        # Preview should detect ambiguity
        preview = import_service.preview_import(temp_csv, 'redemptions')
        
        assert len(preview.invalid_rows) > 0
        assert preview.has_errors
        
        # Error should mention ambiguity and user_id
        error = preview.invalid_rows[0]
        assert 'ambiguous' in error.message.lower()
        assert 'user_id=1' in error.message
    
    def test_import_redemption_without_method_name(self, import_service, temp_csv):
        """Test importing redemption without method name (optional field)."""
        # Create CSV without Method Name
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Redemption Date', 'Amount'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'fooyay',
                'Site Name': 'Stake',
                'Redemption Date': '2024-01-15',
                'Amount': '100.00'
            })
        
        # Preview should succeed
        preview = import_service.preview_import(temp_csv, 'redemptions')
        
        assert len(preview.invalid_rows) == 0
        assert not preview.has_errors
        assert len(preview.to_add) == 1
        assert preview.to_add[0]['redemption_method_id'] is None
