"""Integration tests for database tools audit logging."""

import pytest
from pathlib import Path

from repositories.database import DatabaseManager
from services.tools import BackupService, RestoreService, ResetService, RestoreMode


@pytest.fixture
def test_db(tmp_path):
    """Create integration test database."""
    db_path = tmp_path / "test.db"
    db = DatabaseManager(str(db_path))
    yield db
    db.close()


@pytest.fixture
def backup_service(test_db):
    return BackupService(test_db)


@pytest.fixture
def restore_service(test_db):
    return RestoreService(test_db)


@pytest.fixture
def reset_service(test_db):
    return ResetService(test_db)


class TestBackupAuditLogging:
    """Test audit logging for backup operations."""
    
    def test_backup_creates_audit_log(self, test_db, backup_service, tmp_path):
        """Test that backup operation logs to audit_log table."""
        backup_path = tmp_path / "test_backup.db"
        
        # Perform backup
        result = backup_service.backup_database(str(backup_path))
        assert result.success
        
        # Check audit log
        cursor = test_db._connection.cursor()
        cursor.execute("""
            SELECT action, table_name, details, user_name 
            FROM audit_log 
            WHERE action = 'BACKUP'
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        audit_entry = cursor.fetchone()
        
        assert audit_entry is not None
        assert audit_entry['action'] == 'BACKUP'
        assert audit_entry['table_name'] == 'database'
        assert 'test_backup.db' in audit_entry['details']
        assert 'bytes' in audit_entry['details']
        assert audit_entry['user_name'] == 'system'
    
    def test_timestamped_backup_creates_audit_log(self, test_db, backup_service, tmp_path):
        """Test that timestamped backup logs correctly."""
        result = backup_service.backup_with_timestamp(str(tmp_path))
        assert result.success
        
        # Check audit log
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE action = 'BACKUP'")
        count = cursor.fetchone()['count']
        
        assert count == 1


class TestRestoreAuditLogging:
    """Test audit logging for restore operations."""
    
    def test_restore_replace_creates_audit_log(self, test_db, backup_service, restore_service, tmp_path):
        """Test that full replace restore logs to audit_log."""
        # Create backup
        backup_path = tmp_path / "backup_replace.db"
        backup_service.backup_database(str(backup_path))
        
        # Clear audit log
        cursor = test_db._connection.cursor()
        cursor.execute("DELETE FROM audit_log")
        test_db._connection.commit()
        
        # Perform restore
        result = restore_service.restore_database(str(backup_path), mode=RestoreMode.REPLACE)
        assert result.success
        
        # Check audit log
        cursor.execute("""
            SELECT action, table_name, details 
            FROM audit_log 
            WHERE action = 'RESTORE_REPLACE'
        """)
        audit_entry = cursor.fetchone()
        
        assert audit_entry is not None
        assert audit_entry['action'] == 'RESTORE_REPLACE'
        assert audit_entry['table_name'] == 'database'
        assert 'backup_replace.db' in audit_entry['details']
    
    def test_restore_merge_creates_audit_logs(self, test_db, backup_service, restore_service, tmp_path):
        """Test that merge restore logs for each table merged."""
        # Add some data
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO users (name) VALUES ('User1')")
        cursor.execute("INSERT INTO sites (name) VALUES ('Site1')")
        test_db._connection.commit()
        
        # Create backup
        backup_path = tmp_path / "backup_merge.db"
        backup_service.backup_database(str(backup_path))
        
        # Clear data and audit log
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM sites")
        cursor.execute("DELETE FROM audit_log")
        test_db._connection.commit()
        
        # Perform merge restore
        result = restore_service.restore_database(str(backup_path), mode=RestoreMode.MERGE_ALL)
        assert result.success
        
        # Check audit logs
        cursor.execute("""
            SELECT action, table_name, details 
            FROM audit_log 
            WHERE action = 'RESTORE_MERGE'
            ORDER BY table_name
        """)
        audit_entries = cursor.fetchall()
        
        # Should have entries for tables with data
        assert len(audit_entries) >= 2
        table_names = [entry['table_name'] for entry in audit_entries]
        assert 'users' in table_names
        assert 'sites' in table_names
        
        # Check details contain record counts
        for entry in audit_entries:
            assert 'record(s)' in entry['details']
            assert 'from backup' in entry['details']


class TestResetAuditLogging:
    """Test audit logging for reset operations."""
    
    def test_reset_full_creates_audit_log(self, test_db, reset_service):
        """Test that full reset logs to audit_log."""
        # Add some data
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO users (name) VALUES ('User1')")
        cursor.execute("INSERT INTO sites (name) VALUES ('Site1')")
        test_db._connection.commit()
        
        # Clear audit log
        cursor.execute("DELETE FROM audit_log")
        test_db._connection.commit()
        
        # Perform full reset
        result = reset_service.reset_database(keep_setup_data=False)
        assert result.success
        
        # Check audit log
        cursor.execute("""
            SELECT action, table_name, details 
            FROM audit_log 
            WHERE action = 'RESET_FULL'
        """)
        audit_entry = cursor.fetchone()
        
        assert audit_entry is not None
        assert audit_entry['action'] == 'RESET_FULL'
        assert audit_entry['table_name'] == 'database'
        assert 'table(s)' in audit_entry['details']
        assert 'Total records:' in audit_entry['details']
    
    def test_reset_partial_creates_audit_log(self, test_db, reset_service):
        """Test that partial reset (keep setup data) logs correctly."""
        # Add some data
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO users (name) VALUES ('User1')")
        cursor.execute("INSERT INTO sites (name) VALUES ('Site1')")
        test_db._connection.commit()
        
        # Clear audit log
        cursor.execute("DELETE FROM audit_log")
        test_db._connection.commit()
        
        # Perform partial reset
        result = reset_service.reset_database(keep_setup_data=True)
        assert result.success
        
        # Check audit log
        cursor.execute("""
            SELECT action, table_name, details 
            FROM audit_log 
            WHERE action = 'RESET_PARTIAL'
        """)
        audit_entry = cursor.fetchone()
        
        assert audit_entry is not None
        assert audit_entry['action'] == 'RESET_PARTIAL'
        assert audit_entry['table_name'] == 'database'
        assert 'Reset' in audit_entry['details']
    
    def test_reset_transaction_data_logs_as_partial(self, test_db, reset_service):
        """Test that reset_transaction_data_only() logs as RESET_PARTIAL."""
        # Add transaction data
        cursor = test_db._connection.cursor()
        cursor.execute("INSERT INTO users (name) VALUES ('User1')")
        cursor.execute("INSERT INTO sites (name) VALUES ('Site1')")
        cursor.execute("""
            INSERT INTO purchases (user_id, site_id, amount, purchase_date, remaining_amount)
            VALUES (1, 1, 100.0, '2024-01-01', 100.0)
        """)
        test_db._connection.commit()
        
        # Clear audit log
        cursor.execute("DELETE FROM audit_log")
        test_db._connection.commit()
        
        # Reset transaction data only
        result = reset_service.reset_transaction_data_only()
        assert result.success
        
        # Check audit log
        cursor.execute("SELECT action FROM audit_log WHERE action = 'RESET_PARTIAL'")
        audit_entry = cursor.fetchone()
        
        assert audit_entry is not None


class TestAuditLogPreservation:
    """Test that audit log itself can be preserved during operations."""
    
    def test_reset_preserves_audit_log_when_requested(self, test_db, reset_service):
        """Test that reset can preserve audit_log table."""
        # Add audit entry
        test_db.log_audit('TEST', 'test_table', details='Test entry')
        
        # Get audit log count
        cursor = test_db._connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM audit_log")
        count_before = cursor.fetchone()['count']
        assert count_before >= 1
        
        # Reset with audit log preservation
        result = reset_service.reset_database(keep_setup_data=False, keep_audit_log=True)
        assert result.success
        
        # Check audit log still has entries
        cursor.execute("SELECT COUNT(*) as count FROM audit_log")
        count_after = cursor.fetchone()['count']
        assert count_after >= count_before  # At least the original entry + reset entry
    
    def test_backup_can_exclude_audit_log(self, test_db, backup_service, tmp_path):
        """Test that backup can exclude audit_log."""
        # Add audit entry
        test_db.log_audit('TEST', 'test_table', details='Test entry')
        
        # Backup without audit log
        backup_path = tmp_path / "backup_no_audit.db"
        result = backup_service.backup_database(str(backup_path), include_audit_log=False)
        assert result.success
        
        # Check backup doesn't have pre-existing audit entries
        backup_conn = DatabaseManager(str(backup_path))
        cursor = backup_conn._connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE action = 'TEST'")
        count = cursor.fetchone()['count']
        backup_conn.close()
        
        assert count == 0  # TEST entry was excluded


class TestAuditLogTimestamps:
    """Test audit log timestamp functionality."""
    
    def test_audit_entries_have_timestamps(self, test_db):
        """Test that audit log entries get automatic timestamps."""
        test_db.log_audit('TEST_ACTION', 'test_table', details='Test')
        
        cursor = test_db._connection.cursor()
        cursor.execute("""
            SELECT timestamp 
            FROM audit_log 
            WHERE action = 'TEST_ACTION'
        """)
        entry = cursor.fetchone()
        
        assert entry is not None
        assert entry['timestamp'] is not None
        assert len(str(entry['timestamp'])) > 0
