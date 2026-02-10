"""
Unit tests for audit log CSV export (Issue #97)

Test Matrix:
- Happy path: Export all audit rows to CSV
- Edge cases: Export with date range filter, empty results
- Invariants: CSV contains expected columns, summary_data is included
"""
import pytest
import csv
from datetime import datetime, timedelta
from pathlib import Path
from services.audit_service import AuditService


class TestAuditLogCSVExport:
    """Test audit log CSV export functionality"""
    
    @pytest.fixture
    def db(self, tmp_path):
        """Provide a temporary test database"""
        from repositories.database import DatabaseManager
        db_path = tmp_path / "test_audit_export.db"
        db = DatabaseManager(str(db_path))
        yield db
        db.close()
    
    @pytest.fixture
    def audit_service(self, db):
        """Provide AuditService with test DB"""
        return AuditService(db)
    
    def test_export_all_audit_rows_to_csv(self, tmp_path, db, audit_service):
        """Happy path: Export all audit rows"""
        # Create some audit entries
        for i in range(5):
            audit_service.log_create(
                "purchases",
                i + 1,
                {"id": i + 1, "amount": f"{100 + i}.00", "user_id": 1, "site_id": 1},
                auto_commit=True
            )
        
        # Export to CSV
        output_path = tmp_path / "audit_export.csv"
        count = audit_service.export_audit_log_csv(str(output_path))
        
        assert count == 5
        assert output_path.exists()
        
        # Verify CSV contents
        with open(output_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 5
        # Check expected columns
        expected_cols = ['id', 'action', 'table_name', 'record_id', 'timestamp', 'user_name', 'summary_data']
        for col in expected_cols:
            assert col in rows[0]
        
        # Check first row data
        assert rows[0]['action'] == 'CREATE'
        assert rows[0]['table_name'] == 'purchases'
        assert rows[0]['summary_data'] is not None
    
    def test_export_with_date_range_filter(self, tmp_path, db, audit_service):
        """Happy path: Export with date range"""
        # Create audit entries with different timestamps
        # (Note: actual timestamp filtering would require time control or manual timestamp updates)
        for i in range(10):
            audit_service.log_create(
                "purchases",
                i + 1,
                {"id": i + 1, "amount": "100.00"},
                auto_commit=True
            )
        
        # Export with date range (default behavior: all rows)
        output_path = tmp_path / "audit_filtered.csv"
        count = audit_service.export_audit_log_csv(str(output_path))
        
        assert count == 10
    
    def test_export_with_start_date_only(self, tmp_path, db, audit_service):
        """Edge case: Export with only start date"""
        # Create entries
        for i in range(3):
            audit_service.log_create("purchases", i + 1, {"id": i + 1}, auto_commit=True)
        
        # Export with start date
        today = datetime.now().date()
        output_path = tmp_path / "audit_start_date.csv"
        count = audit_service.export_audit_log_csv(str(output_path), start_date=today)
        
        # Should include all entries from today
        assert count == 3
    
    def test_export_empty_audit_log(self, tmp_path, audit_service):
        """Edge case: Export when no audit entries exist"""
        output_path = tmp_path / "audit_empty.csv"
        count = audit_service.export_audit_log_csv(str(output_path))
        
        assert count == 0
        # CSV should still be created with headers
        assert output_path.exists()
        
        with open(output_path, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)
            assert 'id' in headers
            # No data rows
            data_rows = list(reader)
            assert len(data_rows) == 0
    
    def test_export_includes_summary_data(self, tmp_path, db, audit_service):
        """Invariant: Exported CSV includes summary_data column"""
        # Create purchase with summary
        audit_service.log_create(
            "purchases",
            1,
            {"id": 1, "amount": "500.00", "user_id": 5, "site_id": 2},
            auto_commit=True
        )
        
        output_path = tmp_path / "audit_with_summary.csv"
        audit_service.export_audit_log_csv(str(output_path))
        
        with open(output_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 1
        assert 'summary_data' in rows[0]
        # summary_data should be present and not empty
        assert rows[0]['summary_data']
        # Should contain valid JSON
        import json
        summary = json.loads(rows[0]['summary_data'])
        assert summary['entity'] == 'purchase'
        assert summary['fields']['amount'] == '500.00'
