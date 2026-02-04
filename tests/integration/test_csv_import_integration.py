"""Integration tests for CSV Import Service."""

import pytest
import tempfile
import csv
import sqlite3
from pathlib import Path
from datetime import date
from decimal import Decimal

from services.tools.csv_import_service import CSVImportService
from services.tools.dtos import ValidationSeverity


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
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE purchases (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            purchase_date TEXT NOT NULL,
            purchase_time TEXT,
            amount REAL NOT NULL,
            sc_received REAL NOT NULL,
            remaining_amount REAL,
            card_id INTEGER,
            cashback_earned REAL,
            starting_sc_balance REAL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (card_id) REFERENCES cards(id)
        )
    """)
    
    # Insert test reference data
    cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
    cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'CasinoA')")
    cursor.execute("INSERT INTO sites (id, name) VALUES (2, 'CasinoB')")
    cursor.execute("INSERT INTO cards (id, name, user_id) VALUES (1, 'Visa 1234', 1)")
    
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


class TestCSVImportWorkflow:
    """Test complete CSV import workflows."""
    
    def test_valid_purchase_import(self, import_service, temp_csv):
        """Test importing valid purchase CSV."""
        # Create CSV
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received', 'Card Name', 'Notes'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '$100.00',
                'SC Received': '100',
                'Card Name': 'Visa 1234',
                'Notes': 'First purchase'
            })
        
        # Preview import
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert len(preview.to_add) == 1
        assert len(preview.invalid_rows) == 0
        assert not preview.has_errors
        
        # Verify parsed values
        record = preview.to_add[0]
        assert record['user_id'] == 1
        assert record['site_id'] == 1
        assert record['purchase_date'] == date(2024, 1, 15)
        assert record['purchase_time'] == '10:30:00'
        assert record['amount'] == Decimal('100.00')
        assert record['sc_received'] == Decimal('100')
        assert record['card_id'] == 1
        
        # Execute import
        result = import_service.execute_import(temp_csv, 'purchases')
        
        assert result.success is True
        assert result.records_added == 1
        assert result.records_updated == 0
        assert result.records_skipped == 0
    
    def test_import_with_validation_errors(self, import_service, temp_csv):
        """Test import blocked by validation errors."""
        # Create CSV with invalid data
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '-100.00',  # Invalid: negative
                'SC Received': '100'
            })
        
        # Preview should detect error
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert len(preview.to_add) == 0
        assert len(preview.invalid_rows) > 0
        assert preview.has_errors
        
        # Verify error details
        error = preview.invalid_rows[0]
        assert error.severity == ValidationSeverity.ERROR
        assert error.field == 'amount'  # Check field name instead of message text
        assert 'positive' in error.message.lower()
        
        # Execute should fail
        result = import_service.execute_import(temp_csv, 'purchases')
        
        assert result.success is False
        assert result.records_added == 0
    
    def test_import_exact_duplicates(self, import_service, temp_csv, db):
        """Test import with exact duplicates (should skip)."""
        # Insert existing record
        db.execute("""
            INSERT INTO purchases 
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, cashback_earned)
            VALUES (1, 1, '2024-01-15', '10:30:00', 100.00, 100.00, 100.00, 0.00)
        """)
        db.commit()
        
        # Create CSV with same record
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '100.00',
                'SC Received': '100.00'
            })
        
        # Preview should detect exact duplicate
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert len(preview.to_add) == 0
        assert len(preview.exact_duplicates) == 1
        assert not preview.has_errors
        
        # Execute should skip
        result = import_service.execute_import(temp_csv, 'purchases')
        
        assert result.success is True
        assert result.records_added == 0
        assert result.records_skipped == 1
    
    def test_import_conflicts_skip_mode(self, import_service, temp_csv, db):
        """Test import with conflicts in skip mode."""
        # Insert existing record with different amount
        db.execute("""
            INSERT INTO purchases 
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received)
            VALUES (1, 1, '2024-01-15', '10:30:00', 100.00, 100.00)
        """)
        db.commit()
        
        # Create CSV with conflicting data (same unique key, different amount)
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '150.00',  # Different amount
                'SC Received': '150.00'
            })
        
        # Preview should detect conflict
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert len(preview.to_add) == 0
        assert len(preview.conflicts) == 1
        
        # Execute with skip_conflicts
        result = import_service.execute_import(
            temp_csv, 'purchases', skip_conflicts=True
        )
        
        assert result.success is True
        assert result.records_added == 0
        assert result.records_skipped == 1
    
    def test_import_conflicts_overwrite_mode(self, import_service, temp_csv, db):
        """Test import with conflicts in overwrite mode."""
        # Insert existing record
        db.execute("""
            INSERT INTO purchases 
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received)
            VALUES (1, 1, '2024-01-15', '10:30:00', 100.00, 100.00)
        """)
        db.commit()
        
        # Create CSV with conflicting data
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '150.00',
                'SC Received': '150.00'
            })
        
        # Execute with overwrite_conflicts
        result = import_service.execute_import(
            temp_csv, 'purchases', overwrite_conflicts=True
        )
        
        assert result.success is True
        assert result.records_added == 0
        assert result.records_updated == 1
        assert result.records_skipped == 0
        
        # Verify record was updated
        updated = db.fetch_one(
            "SELECT * FROM purchases WHERE user_id = 1 AND purchase_date = '2024-01-15'"
        )
        assert updated['amount'] == 150.00
    
    def test_import_csv_duplicates_detection(self, import_service, temp_csv):
        """Test detection of duplicates within CSV file."""
        # Create CSV with duplicate rows
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            # Same record twice
            for _ in range(2):
                writer.writerow({
                    'User Name': 'Alice',
                    'Site Name': 'CasinoA',
                    'Purchase Date': '2024-01-15',
                    'Purchase Time': '10:30',
                    'Amount': '100.00',
                    'SC Received': '100.00'
                })
        
        # Preview should detect CSV duplicate
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert len(preview.csv_duplicates) > 0
        assert preview.has_errors
    
    def test_import_missing_required_field(self, import_service, temp_csv):
        """Test import with missing required field."""
        # Create CSV missing required field
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Amount'
                # Missing 'SC Received' (required)
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Amount': '100.00'
            })
        
        # Preview should fail on missing column
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert preview.has_errors
        assert any('required' in err.message.lower() for err in preview.invalid_rows)
    
    def test_import_invalid_foreign_key(self, import_service, temp_csv):
        """Test import with invalid foreign key."""
        # Create CSV with non-existent user
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            writer.writerow({
                'User Name': 'NonExistentUser',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:30',
                'Amount': '100.00',
                'SC Received': '100.00'
            })
        
        # Preview should detect FK error
        preview = import_service.preview_import(temp_csv, 'purchases')
        
        assert preview.has_errors
        assert any('not found' in err.message.lower() for err in preview.invalid_rows)
    
    def test_import_chronological_sorting(self, import_service, temp_csv, db):
        """Test that transaction records are sorted chronologically."""
        # Create CSV with out-of-order dates
        with open(temp_csv, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'User Name', 'Site Name', 'Purchase Date', 'Purchase Time',
                'Amount', 'SC Received'
            ])
            writer.writeheader()
            # Write in reverse chronological order
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-20',
                'Purchase Time': '15:00',
                'Amount': '100.00',
                'SC Received': '100.00'
            })
            writer.writerow({
                'User Name': 'Alice',
                'Site Name': 'CasinoA',
                'Purchase Date': '2024-01-15',
                'Purchase Time': '10:00',
                'Amount': '50.00',
                'SC Received': '50.00'
            })
        
        # Execute import
        result = import_service.execute_import(temp_csv, 'purchases')
        
        assert result.success is True
        assert result.records_added == 2
        
        # Verify chronological order in DB
        purchases = db.fetch_all("SELECT * FROM purchases ORDER BY id")
        assert purchases[0]['purchase_date'] == '2024-01-15'
        assert purchases[1]['purchase_date'] == '2024-01-20'
