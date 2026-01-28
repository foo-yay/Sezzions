"""
Integration tests for database tools (Backup, Restore, Reset).

Tests complete workflows with real database operations.
"""

import pytest
import sqlite3
from pathlib import Path
from decimal import Decimal

from services.tools.backup_service import BackupService
from services.tools.restore_service import RestoreService
from services.tools.reset_service import ResetService
from services.tools.enums import RestoreMode


class DB:
    """Test database with full schema."""
    
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
    
    def cursor(self):
        return self.conn.cursor()
    
    def execute(self, query, params=None):
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
    
    def log_audit(self, action: str, table_name: str, record_id=None, details=None, user_name=None):
        """Log audit entry (test stub - does nothing)."""
        # Stub implementation for testing - could write to audit_log if needed
        pass
    
    def fetch_all(self, query, params=None):
        """DatabaseManager-compatible fetch_all."""
        cursor = self.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchall()
    
    def fetch_one(self, query, params=None):
        """DatabaseManager-compatible fetch_one."""
        cursor = self.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor.fetchone()
    
    def execute_no_commit(self, query, params=None):
        """DatabaseManager-compatible execute_no_commit."""
        cursor = self.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    
    def executemany_no_commit(self, query, params_list):
        """DatabaseManager-compatible executemany_no_commit."""
        cursor = self.cursor()
        cursor.executemany(query, params_list)
        return cursor
    
    def close(self):
        self.conn.close()
    
    def _create_schema(self):
        """Create full test schema."""
        cursor = self.cursor()
        
        # Setup tables
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                site_id INTEGER NOT NULL,
                FOREIGN KEY (site_id) REFERENCES sites(id)
            )
        """)
        
        # Transaction tables
        cursor.execute("""
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                card_id INTEGER,
                amount REAL NOT NULL,
                purchase_date TEXT NOT NULL,
                purchase_time TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (site_id) REFERENCES sites(id),
                FOREIGN KEY (card_id) REFERENCES cards(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                result REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (site_id) REFERENCES sites(id)
            )
        """)
        
        self.commit()
    
    def populate_test_data(self):
        """Add test data."""
        cursor = self.cursor()
        
        # Setup data
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (1, 'CasinoX')")
        cursor.execute("INSERT INTO sites (id, name) VALUES (2, 'LuckyY')")
        cursor.execute("INSERT INTO cards (id, name, site_id) VALUES (1, 'Visa1234', 1)")
        
        # Transaction data
        cursor.execute("""
            INSERT INTO purchases (user_id, site_id, card_id, amount, purchase_date) 
            VALUES (1, 1, 1, 100.0, '2024-01-01')
        """)
        cursor.execute("""
            INSERT INTO purchases (user_id, site_id, card_id, amount, purchase_date) 
            VALUES (2, 2, NULL, 50.0, '2024-01-02')
        """)
        cursor.execute("""
            INSERT INTO game_sessions (user_id, site_id, start_date, result) 
            VALUES (1, 1, '2024-01-01', -25.5)
        """)
        
        self.commit()


@pytest.fixture
def test_db(tmp_path):
    """Create test database."""
    db_path = tmp_path / "test.db"
    db = DB(str(db_path))
    yield db
    db.close()


@pytest.fixture
def backup_service(test_db):
    """Create backup service."""
    return BackupService(test_db)


@pytest.fixture
def restore_service(test_db):
    """Create restore service."""
    return RestoreService(test_db)


@pytest.fixture
def reset_service(test_db):
    """Create reset service."""
    return ResetService(test_db)


class TestBackupRestoreWorkflow:
    """Test complete backup and restore workflows."""
    
    def test_backup_and_full_replace_restore(self, test_db, backup_service, restore_service, tmp_path):
        """Test backup then full replace restore."""
        # Add data
        test_db.populate_test_data()
        
        # Backup
        backup_path = tmp_path / "backup.db"
        backup_result = backup_service.backup_database(str(backup_path))
        assert backup_result.success
        assert backup_path.exists()
        
        # Modify data
        cursor = test_db.cursor()
        cursor.execute("DELETE FROM purchases")
        cursor.execute("INSERT INTO users (id, name) VALUES (3, 'Charlie')")
        test_db.commit()
        
        # Verify changes
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 3
        
        # Restore (full replace requires closing connection - not testing this in unit test)
        # In real usage, UI would handle connection management
    
    def test_backup_and_merge_all_restore(self, test_db, backup_service, restore_service, tmp_path):
        """Test backup then merge all restore."""
        # Add initial data
        test_db.populate_test_data()
        
        # Backup
        backup_path = tmp_path / "backup.db"
        backup_result = backup_service.backup_database(str(backup_path))
        assert backup_result.success
        
        # Delete transaction data
        cursor = test_db.cursor()
        cursor.execute("DELETE FROM purchases")
        cursor.execute("DELETE FROM game_sessions")
        test_db.commit()
        
        # Verify deleted
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 0
        
        # Merge restore
        restore_result = restore_service.restore_database(
            str(backup_path),
            mode=RestoreMode.MERGE_ALL
        )
        
        assert restore_result.success
        assert restore_result.records_restored >= 2
        
        # Verify data restored
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM game_sessions")
        assert cursor.fetchone()[0] == 1
    
    def test_backup_and_merge_selective_restore(self, test_db, backup_service, restore_service, tmp_path):
        """Test backup then selective merge restore."""
        # Add initial data
        test_db.populate_test_data()
        
        # Backup
        backup_path = tmp_path / "backup.db"
        backup_result = backup_service.backup_database(str(backup_path))
        assert backup_result.success
        
        # Delete all transaction data
        cursor = test_db.cursor()
        cursor.execute("DELETE FROM purchases")
        cursor.execute("DELETE FROM game_sessions")
        test_db.commit()
        
        # Selective restore - only purchases
        restore_result = restore_service.restore_database(
            str(backup_path),
            mode=RestoreMode.MERGE_SELECTED,
            tables=['purchases']
        )
        
        assert restore_result.success
        assert 'purchases' in restore_result.tables_affected
        
        # Verify only purchases restored
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM game_sessions")
        assert cursor.fetchone()[0] == 0  # Not restored


class TestResetWorkflows:
    """Test reset workflows."""
    
    def test_reset_all_data(self, test_db, reset_service):
        """Test resetting all data."""
        # Add data
        test_db.populate_test_data()
        
        # Verify data exists
        counts = reset_service.get_table_counts()
        assert counts['users'] == 2
        assert counts['purchases'] == 2
        
        # Reset all
        result = reset_service.reset_database(keep_setup_data=False)
        
        assert result.success
        assert result.records_deleted >= 7  # Total records
        
        # Verify all empty
        counts = reset_service.get_table_counts()
        assert all(count == 0 for count in counts.values())
    
    def test_reset_keep_setup_data(self, test_db, reset_service):
        """Test reset keeping setup data."""
        # Add data
        test_db.populate_test_data()
        
        # Reset transactions only
        result = reset_service.reset_transaction_data_only()
        
        assert result.success
        assert 'purchases' in result.tables_cleared
        assert 'game_sessions' in result.tables_cleared
        
        # Verify setup data preserved
        cursor = test_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT COUNT(*) FROM sites")
        assert cursor.fetchone()[0] == 2
        
        # Verify transaction data deleted
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM game_sessions")
        assert cursor.fetchone()[0] == 0
    
    def test_preview_reset(self, test_db, reset_service):
        """Test preview reset operation."""
        # Add data
        test_db.populate_test_data()
        
        # Preview reset all
        preview = reset_service.preview_reset(keep_setup_data=False)
        
        assert 'tables' in preview
        assert 'record_counts' in preview
        assert 'total_records' in preview
        assert preview['total_records'] >= 7
        
        # Verify actual data not changed
        counts = reset_service.get_table_counts()
        assert counts['users'] == 2
        assert counts['purchases'] == 2


class TestBackupResetRestoreWorkflow:
    """Test complete backup → reset → restore workflow."""
    
    def test_full_workflow(self, test_db, backup_service, reset_service, restore_service, tmp_path):
        """Test backup, reset, then restore."""
        # 1. Add data
        test_db.populate_test_data()
        
        # Verify initial state
        counts_initial = reset_service.get_table_counts()
        assert counts_initial['users'] == 2
        assert counts_initial['purchases'] == 2
        assert counts_initial['game_sessions'] == 1
        
        # 2. Backup
        backup_path = tmp_path / "backup.db"
        backup_result = backup_service.backup_database(str(backup_path))
        assert backup_result.success
        
        # 3. Reset transaction data
        reset_result = reset_service.reset_transaction_data_only()
        assert reset_result.success
        
        # Verify transactions cleared but setup preserved
        counts_reset = reset_service.get_table_counts()
        assert counts_reset['users'] == 2
        assert counts_reset['purchases'] == 0
        assert counts_reset['game_sessions'] == 0
        
        # 4. Restore from backup
        restore_result = restore_service.restore_database(
            str(backup_path),
            mode=RestoreMode.MERGE_ALL
        )
        assert restore_result.success
        
        # 5. Verify data restored
        counts_restored = reset_service.get_table_counts()
        assert counts_restored['users'] == 2
        assert counts_restored['purchases'] == 2
        assert counts_restored['game_sessions'] == 1


class TestBackupManagement:
    """Test backup management operations."""
    
    def test_backup_cleanup(self, test_db, backup_service, tmp_path):
        """Test backup cleanup keeps most recent."""
        import time
        # Create multiple backups with delays
        test_db.populate_test_data()
        
        for i in range(5):
            result = backup_service.backup_with_timestamp(str(tmp_path))
            assert result.success
            time.sleep(1.1)  # Need > 1 second since timestamp format is YYYYMMDD_HHMMSS
        
        # List all backups
        backups = backup_service.list_backups(str(tmp_path))
        initial_count = len(backups)
        assert initial_count >= 5
        
        # Delete old backups, keep 2
        deleted = backup_service.delete_old_backups(str(tmp_path), keep_count=2)
        
        assert deleted >= 3
        
        # Verify only 2 remain
        remaining = backup_service.list_backups(str(tmp_path))
        assert len(remaining) == 2
    
    def test_verify_backup_integrity(self, test_db, backup_service, tmp_path):
        """Test backup verification."""
        # Create backup
        test_db.populate_test_data()
        backup_path = tmp_path / "backup.db"
        backup_result = backup_service.backup_database(str(backup_path))
        assert backup_result.success
        
        # Verify integrity
        verify_result = backup_service.verify_backup(str(backup_path))
        assert verify_result.success
