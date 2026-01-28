"""
Integration tests for CSV export functionality.

Tests full export workflow including:
- Export from actual database
- FK resolution (ID → name)
- Roundtrip (export → import)
- Template generation
"""

import pytest
import sqlite3
import csv
from pathlib import Path
from decimal import Decimal

from services.tools.csv_export_service import CSVExportService, export_with_timestamp
from services.tools.csv_import_service import CSVImportService
from services.tools.schemas import get_schema


class SimpleDB:
    """Wrapper for sqlite3 connection with Row factory."""
    
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_test_schema()
    
    def cursor(self):
        return self.conn.cursor()
    
    def execute(self, query, params=None):
        """Execute a query and return cursor."""
        cursor = self.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    
    def commit(self):
        self.conn.commit()
    
    def rollback(self):
        self.conn.rollback()
    
    def close(self):
        self.conn.close()
    
    def _create_test_schema(self):
        """Create minimal test schema."""
        cursor = self.cursor()
        
        # Reference tables
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Transaction table
        cursor.execute("""
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_date TEXT NOT NULL,
                site_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                card_id INTEGER,
                amount REAL NOT NULL,
                sc_received REAL NOT NULL,
                starting_sc_balance REAL,
                cashback_earned REAL DEFAULT 0.00,
                purchase_time TEXT NOT NULL,
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (card_id) REFERENCES cards(id)
            )
        """)
        
        # Insert reference data
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Test User')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'Test Site')")
        cursor.execute("INSERT INTO cards (id, name) VALUES (1, 'Test Card')")
        
        self.commit()


@pytest.fixture
def test_db():
    """Create test database with schema."""
    db = SimpleDB()
    yield db
    db.close()


@pytest.fixture
def export_service(test_db):
    """Create export service with test database."""
    return CSVExportService(test_db)


@pytest.fixture
def import_service(test_db):
    """Create import service with test database."""
    return CSVImportService(test_db)


class TestExportIntegration:
    """Integration tests for CSV export."""
    
    def test_export_with_fk_resolution(self, test_db, export_service, tmp_path):
        """Test export with foreign key ID → name resolution."""
        # Insert test purchase
        cursor = test_db.cursor()
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, card_id, amount, sc_received, purchase_time, notes)
            VALUES ('2026-01-27', 1, 1, 1, 100.50, 100.50, '14:30:00', 'Test purchase')
        """)
        test_db.commit()
        
        # Export
        output_path = tmp_path / "export.csv"
        result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path)
        )
        
        assert result.success
        assert result.records_exported == 1
        
        # Verify CSV content
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        # Check FK names (not IDs)
        assert rows[0]['Site Name'] == 'Test Site'
        assert rows[0]['User Name'] == 'Test User'
        assert rows[0]['Card Name'] == 'Test Card'
        assert rows[0]['Amount'] == '100.50'
        assert rows[0]['Purchase Date'] == '2026-01-27'
    
    def test_export_import_roundtrip(self, test_db, export_service, import_service, tmp_path):
        """Test export → import roundtrip maintains data integrity."""
        # Insert test purchase
        cursor = test_db.cursor()
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, card_id, amount, sc_received, purchase_time, notes)
            VALUES ('2026-01-27', 1, 1, 1, 150.00, 150.00, '15:45:00', 'Roundtrip test')
        """)
        test_db.commit()
        
        # Export
        export_path = tmp_path / "export.csv"
        export_result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(export_path)
        )
        
        assert export_result.success
        
        # Delete original record
        cursor.execute("DELETE FROM purchases")
        test_db.commit()
        
        # Import back
        import_result = import_service.execute_import(
            entity_type='purchases',
            csv_path=str(export_path)
        )
        
        assert import_result.success
        assert import_result.records_added == 1
        
        # Verify data matches
        cursor.execute("SELECT * FROM purchases")
        imported = cursor.fetchone()
        
        assert imported['amount'] == 150.00
        assert imported['purchase_date'] == '2026-01-27'
        assert imported['purchase_time'] == '15:45:00'
        assert imported['notes'] == 'Roundtrip test'
    
    def test_export_multiple_records(self, test_db, export_service, tmp_path):
        """Test exporting multiple records."""
        # Insert multiple purchases
        cursor = test_db.cursor()
        for i in range(5):
            cursor.execute("""
                INSERT INTO purchases (purchase_date, site_id, user_id, card_id, amount, sc_received, purchase_time)
                VALUES (?, 1, 1, 1, ?, ?, '12:00:00')
            """, (f'2026-01-{20+i:02d}', 100.00 * (i + 1), 100.00 * (i + 1)))
        test_db.commit()
        
        # Export
        output_path = tmp_path / "export.csv"
        result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path)
        )
        
        assert result.success
        assert result.records_exported == 5
        
        # Verify CSV has 5 rows
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 6  # 1 header + 5 data rows
    
    def test_export_with_filters(self, test_db, export_service, tmp_path):
        """Test export with filters."""
        # Insert purchases for different sites
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO sites (id, name) VALUES (2, 'Site Two')")
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, amount, sc_received, purchase_time)
            VALUES ('2026-01-27', 1, 1, 100.00, 100.00, '12:00:00')
        """)
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, amount, sc_received, purchase_time)
            VALUES ('2026-01-27', 2, 1, 200.00, 200.00, '13:00:00')
        """)
        test_db.commit()
        
        # Export only site 1
        output_path = tmp_path / "export.csv"
        result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path),
            filters={'site_id': 1}
        )
        
        assert result.success
        assert result.records_exported == 1
        
        # Verify only site 1 exported
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]['Site Name'] == 'Test Site'
        assert rows[0]['Amount'] == '100.00'
    
    def test_template_generation(self, export_service, tmp_path):
        """Test CSV template generation."""
        output_path = tmp_path / "template.csv"
        result = export_service.generate_template(
            entity_type='purchases',
            output_path=str(output_path),
            include_example_row=True
        )
        
        assert result.success
        assert result.records_exported == 1
        assert len(result.warnings) > 0
        
        # Verify template structure
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        assert len(rows) == 2  # Header + example
        assert 'Purchase Date' in rows[0]
        assert 'Site Name' in rows[0]
        assert 'Amount' in rows[0]
    
    def test_export_with_timestamp_filename(self, test_db, export_service, tmp_path):
        """Test timestamped export creates unique filename."""
        # Insert test data
        cursor = test_db.cursor()
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, amount, sc_received, purchase_time)
            VALUES ('2026-01-27', 1, 1, 100.00, 100.00, '12:00:00')
        """)
        test_db.commit()
        
        # Export with timestamp
        result = export_with_timestamp(
            service=export_service,
            entity_type='purchases',
            output_dir=str(tmp_path)
        )
        
        assert result.success
        assert result.records_exported == 1
        assert 'purchases_' in result.file_path
        assert result.file_path.endswith('.csv')
        
        # Verify file exists
        assert Path(result.file_path).exists()
    
    def test_export_empty_database(self, export_service, tmp_path):
        """Test export from empty table."""
        output_path = tmp_path / "empty.csv"
        result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path)
        )
        
        assert result.success
        assert result.records_exported == 0
        assert len(result.warnings) > 0
        assert "No records found" in result.warnings[0]
    
    def test_export_with_null_fks(self, test_db, export_service, tmp_path):
        """Test export with NULL foreign keys."""
        # Insert purchase with NULL card_id
        cursor = test_db.cursor()
        cursor.execute("""
            INSERT INTO purchases (purchase_date, site_id, user_id, card_id, amount, sc_received, purchase_time)
            VALUES ('2026-01-27', 1, 1, NULL, 100.00, 100.00, '12:00:00')
        """)
        test_db.commit()
        
        # Export
        output_path = tmp_path / "export.csv"
        result = export_service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path)
        )
        
        assert result.success
        assert result.records_exported == 1
        
        # Verify NULL FK becomes empty string
        with open(output_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        assert rows[0]['Card Name'] == ''  # NULL → empty string
        assert rows[0]['Site Name'] == 'Test Site'  # Non-NULL FK
