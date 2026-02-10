"""
Unit tests for audit summary generation (Issue #97)

Test Matrix:
- Happy path: Generate summaries for Purchases, Redemptions, Game Sessions
- Edge cases: Missing optional fields, NULL values, empty dicts
- Failure resilience: Invalid JSON, missing required fields should not crash
- Invariants: Summary generation never blocks CRUD operations
"""
import pytest
import json
from datetime import datetime
from services.audit_service import AuditService


class TestAuditSummaryGeneration:
    """Test audit summary data capture for long-term retention"""
    
    def test_purchase_summary_includes_core_fields(self):
        """Happy path: Purchase summary includes amount, user_id, site_id"""
        # Arrange
        new_data = {
            "id": 123,
            "amount": "500.00",
            "purchase_date": "2026-02-09",
            "user_id": 5,
            "site_id": 2,
            "sc_received": "1500.00",
            "starting_sc_balance": "1000.00"
        }
        
        # Act
        summary = AuditService.build_summary("purchases", "CREATE", 123, None, new_data)
        
        # Assert
        assert summary is not None
        summary_dict = json.loads(summary)
        assert summary_dict["entity"] == "purchase"
        assert summary_dict["entity_id"] == 123
        assert summary_dict["crud"] == "CREATE"
        assert summary_dict["fields"]["amount"] == "500.00"
        assert summary_dict["fields"]["user_id"] == 5
        assert summary_dict["fields"]["site_id"] == 2
        # Starting SC is a derived/computed field
        assert "starting_sc" in summary_dict["fields"]
        
    def test_redemption_summary_includes_amount_user_site(self):
        """Happy path: Redemption summary includes amount, user_id, site_id"""
        new_data = {
            "id": 456,
            "amount": "200.00",
            "redemption_date": "2026-02-09",
            "user_id": 3,
            "site_id": 1,
        }
        
        summary = AuditService.build_summary("redemptions", "CREATE", 456, None, new_data)
        
        summary_dict = json.loads(summary)
        assert summary_dict["entity"] == "redemption"
        assert summary_dict["entity_id"] == 456
        assert summary_dict["fields"]["amount"] == "200.00"
        assert summary_dict["fields"]["user_id"] == 3
        assert summary_dict["fields"]["site_id"] == 1
        
    def test_game_session_start_summary(self):
        """Happy path: Game session start includes start datetime, balances, user/site"""
        new_data = {
            "id": 789,
            "session_date": "2026-02-09",
            "session_time": "14:30:00",
            "starting_balance": "2000.00",
            "starting_redeemable": "500.00",
            "user_id": 7,
            "site_id": 3,
            "status": "Active"
        }
        
        summary = AuditService.build_summary("game_sessions", "CREATE", 789, None, new_data)
        
        summary_dict = json.loads(summary)
        assert summary_dict["entity"] == "game_session"
        assert summary_dict["entity_id"] == 789
        assert summary_dict["crud"] == "CREATE"
        # Session start summary
        assert summary_dict["fields"]["start_datetime"] == "2026-02-09 14:30:00"
        assert summary_dict["fields"]["start_sc"] == "2000.00"
        assert summary_dict["fields"]["start_redeemable"] == "500.00"
        assert summary_dict["fields"]["user_id"] == 7
        assert summary_dict["fields"]["site_id"] == 3
        
    def test_game_session_end_summary(self):
        """Happy path: Game session end includes end datetime, ending balances"""
        old_data = {
            "id": 789,
            "status": "Active",
            "ending_balance": None,
            "ending_redeemable": None
        }
        new_data = {
            "id": 789,
            "status": "Ended",
            "end_date": "2026-02-09",
            "end_time": "18:00:00",
            "ending_balance": "2500.00",
            "ending_redeemable": "600.00",
            "user_id": 7,
            "site_id": 3
        }
        
        summary = AuditService.build_summary("game_sessions", "UPDATE", 789, old_data, new_data)
        
        summary_dict = json.loads(summary)
        # End summary
        assert summary_dict["fields"]["end_datetime"] == "2026-02-09 18:00:00"
        assert summary_dict["fields"]["end_sc"] == "2500.00"
        assert summary_dict["fields"]["end_redeemable"] == "600.00"
        
    def test_summary_with_missing_optional_fields(self):
        """Edge case: Missing optional fields still produce valid summary"""
        # Purchase without starting_sc_balance
        new_data = {
            "id": 100,
            "amount": "300.00",
            "user_id": 1,
            "site_id": 1
            # starting_sc_balance is missing
        }
        
        summary = AuditService.build_summary("purchases", "CREATE", 100, None, new_data)
        
        summary_dict = json.loads(summary)
        assert summary_dict["fields"]["amount"] == "300.00"
        # starting_sc might be omitted or null in summary
        assert "starting_sc" not in summary_dict["fields"] or summary_dict["fields"]["starting_sc"] is None
        
    def test_summary_for_unsupported_table_returns_none(self):
        """Edge case: Unsupported tables return None (no crash)"""
        new_data = {"id": 1, "name": "Test"}
        summary = AuditService.build_summary("users", "CREATE", 1, None, new_data)
        # Users table not in summary rules yet
        assert summary is None
        
    def test_summary_with_null_data_does_not_crash(self):
        """Failure resilience: NULL data should not crash"""
        summary = AuditService.build_summary("purchases", "CREATE", 999, None, None)
        # Should return None or minimal summary, not crash
        assert summary is None or isinstance(summary, str)
        
    def test_summary_with_empty_dict_does_not_crash(self):
        """Failure resilience: Empty dict should not crash"""
        summary = AuditService.build_summary("purchases", "CREATE", 999, None, {})
        # Should handle gracefully
        assert summary is None or isinstance(summary, str)


class TestAuditSummaryIntegration:
    """Integration tests: summary capture during actual CRUD operations"""
    
    @pytest.fixture
    def db(self, tmp_path):
        """Provide a temporary test database"""
        from repositories.database import DatabaseManager
        db_path = tmp_path / "test_audit_summary.db"
        db = DatabaseManager(str(db_path))
        yield db
        db.close()
    
    @pytest.fixture
    def audit_service(self, db):
        """Provide AuditService with test DB"""
        return AuditService(db)
    
    def test_create_purchase_logs_summary(self, db, audit_service):
        """Integration: Creating a purchase writes summary_data"""
        # Log purchase creation
        new_data = {
            "id": 1,
            "amount": "500.00",
            "user_id": 1,
            "site_id": 1,
            "starting_sc_balance": "1000.00"
        }
        audit_service.log_create("purchases", 1, new_data, auto_commit=True)
        
        # Verify audit entry has summary_data
        audit_log = db.fetch_all("SELECT * FROM audit_log WHERE table_name='purchases' AND record_id=1")
        assert len(audit_log) == 1
        entry = audit_log[0]
        assert entry["summary_data"] is not None
        
        summary = json.loads(entry["summary_data"])
        assert summary["entity"] == "purchase"
        assert summary["fields"]["amount"] == "500.00"
        assert summary["fields"]["user_id"] == 1
        
    def test_summary_persists_when_snapshots_pruned(self, db, audit_service):
        """Invariant: summary_data remains even when old_data/new_data are nulled (undo pruning)"""
        # Create audit entry with full snapshots + summary
        new_data = {"id": 1, "amount": "100.00", "user_id": 1, "site_id": 1}
        audit_service.log_create("purchases", 1, new_data, auto_commit=True)
        
        # Simulate undo pruning: null old_data/new_data but keep summary_data
        db.execute("UPDATE audit_log SET old_data=NULL, new_data=NULL WHERE record_id=1", ())
        
        # Verify summary_data is still present
        audit_log = db.fetch_all("SELECT * FROM audit_log WHERE record_id=1")
        entry = audit_log[0]
        assert entry["old_data"] is None
        assert entry["new_data"] is None
        assert entry["summary_data"] is not None
        
        summary = json.loads(entry["summary_data"])
        assert summary["entity"] == "purchase"
        assert summary["fields"]["amount"] == "100.00"
