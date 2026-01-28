"""
Unit tests for CSV export utilities.

Tests export formatting and template generation.
"""

import pytest
from datetime import date, time
from decimal import Decimal

from services.tools.csv_export_service import CSVExportService
from services.tools.schemas import get_schema


class SimpleDB:
    """Mock database for testing."""
    
    def __init__(self):
        self.data = {}
        self.row_factory = None
    
    def cursor(self):
        return self
    
    def execute(self, query, params=None):
        # Return empty for FK lookups
        self.results = []
        return self
    
    def fetchall(self):
        return self.results
    
    def fetchone(self):
        return None if not self.results else self.results[0]


class TestCSVExportService:
    """Test CSV export service initialization and basic operations."""
    
    def test_init(self):
        """Test service initialization."""
        db = SimpleDB()
        service = CSVExportService(db)
        
        assert service.db == db
        assert service.fk_resolver is not None
    
    def test_generate_template_headers_only(self, tmp_path):
        """Test template generation without example row."""
        db = SimpleDB()
        service = CSVExportService(db)
        
        output_path = tmp_path / "template.csv"
        result = service.generate_template(
            entity_type='purchases',
            output_path=str(output_path),
            include_example_row=False
        )
        
        assert result.success
        assert result.records_exported == 0
        assert output_path.exists()
        
        # Check headers
        with open(output_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 1
        assert 'Date' in lines[0]
        assert 'Site' in lines[0]
        assert 'Amount' in lines[0]
    
    def test_generate_template_with_example(self, tmp_path):
        """Test template generation with example row."""
        db = SimpleDB()
        service = CSVExportService(db)
        
        output_path = tmp_path / "template.csv"
        result = service.generate_template(
            entity_type='purchases',
            output_path=str(output_path),
            include_example_row=True
        )
        
        assert result.success
        assert result.records_exported == 1
        assert len(result.warnings) > 0
        assert "Template generated" in result.warnings[0]
        
        # Check content
        with open(output_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        assert 'Example' in lines[1]  # Example data in second row
    
    def test_generate_example_row_types(self):
        """Test example row generation produces correct types."""
        db = SimpleDB()
        service = CSVExportService(db)
        
        schema = get_schema('purchases')
        example_row = service._generate_example_row(schema)
        
        # Should have value for each field
        assert len(example_row) == len(schema.fields)
        
        # Check specific examples
        field_names = [f.csv_header for f in schema.fields]
        if 'Date' in field_names:
            date_idx = field_names.index('Date')
            assert '2026' in example_row[date_idx]  # Date format
        
        if 'Amount' in field_names:
            amt_idx = field_names.index('Amount')
            assert '100.00' in example_row[amt_idx]  # Currency format
    
    def test_export_no_records(self, tmp_path):
        """Test export when no records match criteria."""
        db = SimpleDB()
        db.results = []  # No records
        service = CSVExportService(db)
        
        output_path = tmp_path / "export.csv"
        result = service.export_to_csv(
            entity_type='purchases',
            output_path=str(output_path)
        )
        
        assert result.success
        assert result.records_exported == 0
        assert len(result.warnings) > 0
        assert "No records found" in result.warnings[0]
    
    def test_build_export_query_no_filters(self):
        """Test query building without filters."""
        db = SimpleDB()
        service = CSVExportService(db)
        schema = get_schema('purchases')
        
        query, params = service._build_export_query(schema, None, False)
        
        assert "SELECT * FROM purchases" in query
        assert "ORDER BY" in query  # Check that chronological ordering exists
        assert params == []
    
    def test_build_export_query_with_filters(self):
        """Test query building with filters."""
        db = SimpleDB()
        service = CSVExportService(db)
        schema = get_schema('purchases')
        
        query, params = service._build_export_query(
            schema,
            filters={'site_id': 1, 'user_id': 2},
            include_inactive=True
        )
        
        assert "SELECT * FROM purchases" in query
        assert "site_id = ?" in query
        assert "user_id = ?" in query
        assert params == [1, 2]
    
    def test_resolve_fk_for_export_none(self):
        """Test FK resolution with None value."""
        db = SimpleDB()
        service = CSVExportService(db)
        
        result = service._resolve_fk_for_export('sites', None)
        assert result == ""
    
    def test_format_record_handles_none(self):
        """Test record formatting with None values."""
        db = SimpleDB()
        service = CSVExportService(db)
        schema = get_schema('purchases')
        
        # Mock record with None values
        record = {f.db_column: None for f in schema.fields}
        
        formatted = service._format_record_for_export(schema, record)
        
        # Should have empty strings for None values
        assert all(v == "" for v in formatted)
    
    def test_format_record_with_values(self):
        """Test record formatting with actual values."""
        db = SimpleDB()
        service = CSVExportService(db)
        schema = get_schema('purchases')
        
        # Mock record with values
        record = {
            'id': 1,
            'date': '2026-01-27',
            'site_id': 1,
            'user_id': 1,
            'card_id': 1,
            'amount': 100.50,
            'time': '14:30:00',
            'notes': 'Test purchase',
            'is_active': 1
        }
        
        formatted = service._format_record_for_export(schema, record)
        
        # Check specific formats (ID might be empty for auto-generated fields)
        assert len(formatted) == len(schema.fields)
        # Amount should be formatted as currency
        amount_found = any('100.50' in str(f) or '100.5' in str(f) for f in formatted)
        assert amount_found


class TestExportTimestampHelper:
    """Test timestamped export helper function."""
    
    def test_export_with_timestamp_generates_filename(self, tmp_path):
        """Test that export creates timestamped filename."""
        from services.tools.csv_export_service import export_with_timestamp
        
        db = SimpleDB()
        db.results = []  # No records
        service = CSVExportService(db)
        
        result = export_with_timestamp(
            service=service,
            entity_type='purchases',
            output_dir=str(tmp_path)
        )
        
        assert result.success
        assert 'purchases_' in result.file_path
        assert '.csv' in result.file_path
        assert str(tmp_path) in result.file_path
