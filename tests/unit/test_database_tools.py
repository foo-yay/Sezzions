"""
Unit tests for database tools (Backup, Restore, Reset services).

Tests basic functionality without complex integration.
"""

import pytest
import sqlite3
import time
from pathlib import Path

from services.tools.backup_service import BackupService
from services.tools.restore_service import RestoreService
from services.tools.reset_service import ResetService
from services.tools.enums import RestoreMode


class SimpleDB:
    """Test database wrapper."""
    
    def __init__(self, db_path=':memory:'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_test_schema()
    
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
        """Log audit entry (test stub)."""
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
    
    def _create_test_schema(self):
        """Create minimal test schema."""
        cursor = self.cursor()
        
        # Setup table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """)
        
        # Transaction table
        cursor.execute("""
            CREATE TABLE purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        self.commit()


@pytest.fixture
def test_db():
    """Create test database."""
    db = SimpleDB()
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


class TestBackupService:
    """Test backup service functionality."""
    
    def test_init(self, test_db):
        """Test service initialization."""
        service = BackupService(test_db)
        assert service.db == test_db
    
    def test_backup_success(self, test_db, backup_service, tmp_path):
        """Test successful backup."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        test_db.commit()
        
        # Backup
        backup_path = tmp_path / "backup.db"
        result = backup_service.backup_database(str(backup_path))
        
        assert result.success
        assert result.backup_path == str(backup_path)
        assert result.size_bytes > 0
        assert backup_path.exists()
    
    def test_backup_file_exists_error(self, backup_service, tmp_path):
        """Test backup fails if file already exists."""
        backup_path = tmp_path / "backup.db"
        backup_path.touch()  # Create empty file
        
        result = backup_service.backup_database(str(backup_path))
        
        assert not result.success
        assert "already exists" in result.error
    
    def test_backup_with_timestamp(self, test_db, backup_service, tmp_path):
        """Test timestamped backup."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Bob')")
        test_db.commit()
        
        result = backup_service.backup_with_timestamp(str(tmp_path))
        
        assert result.success
        assert "backup_" in result.backup_path
        assert result.backup_path.endswith('.db')
        assert Path(result.backup_path).exists()
    
    def test_list_backups_empty(self, backup_service, tmp_path):
        """Test listing backups when none exist."""
        backups = backup_service.list_backups(str(tmp_path))
        assert backups == []
    
    def test_list_backups(self, test_db, backup_service, tmp_path):
        """Test listing multiple backups."""
        # Create multiple backups with delay to ensure different timestamps
        for i in range(3):
            cursor = test_db.cursor()
            cursor.execute(f"INSERT INTO users (id, name) VALUES ({i}, 'User{i}')")
            test_db.commit()
            backup_service.backup_with_timestamp(str(tmp_path))
            time.sleep(1.1)  # Ensure different timestamps
        
        backups = backup_service.list_backups(str(tmp_path))
        
        assert len(backups) >= 3
        assert all('timestamp' in b for b in backups)
        assert all('size_bytes' in b for b in backups)
    
    def test_delete_old_backups(self, test_db, backup_service, tmp_path):
        """Test deleting old backups."""
        # Create 5 backups with delays
        for i in range(5):
            cursor = test_db.cursor()
            cursor.execute(f"INSERT INTO users (id, name) VALUES ({i+10}, 'User{i}')")
            test_db.commit()
            backup_service.backup_with_timestamp(str(tmp_path))
            time.sleep(1.1)  # Ensure different timestamps
        
        # Keep only 2 most recent
        deleted = backup_service.delete_old_backups(str(tmp_path), keep_count=2)
        
        assert deleted == 3
        remaining = backup_service.list_backups(str(tmp_path))
        assert len(remaining) == 2
    
    def test_verify_backup_valid(self, test_db, backup_service, tmp_path):
        """Test verify valid backup."""
        # Create backup
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Charlie')")
        test_db.commit()
        
        backup_path = tmp_path / "backup.db"
        backup_service.backup_database(str(backup_path))
        
        # Verify
        result = backup_service.verify_backup(str(backup_path))
        
        assert result.success
    
    def test_verify_backup_not_found(self, backup_service, tmp_path):
        """Test verify non-existent backup."""
        result = backup_service.verify_backup(str(tmp_path / "nonexistent.db"))
        
        assert not result.success
        assert "not found" in result.error


class TestRestoreService:
    """Test restore service functionality."""
    
    def test_init(self, test_db):
        """Test service initialization."""
        service = RestoreService(test_db)
        assert service.db == test_db
    
    def test_restore_backup_not_found(self, restore_service):
        """Test restore fails with non-existent backup."""
        result = restore_service.restore_database('nonexistent.db')
        
        assert not result.success
        assert "not found" in result.error
    
    def test_merge_selective_no_tables(self, restore_service, tmp_path):
        """Test MERGE_SELECTIVE mode requires tables list."""
        # Create dummy backup
        backup_path = tmp_path / "backup.db"
        backup_path.touch()
        
        result = restore_service.restore_database(
            str(backup_path),
            mode=RestoreMode.MERGE_SELECTED
        )
        
        assert not result.success
        assert "requires tables list" in result.error


class TestResetService:
    """Test reset service functionality."""
    
    def test_init(self, test_db):
        """Test service initialization."""
        service = ResetService(test_db)
        assert service.db == test_db
    
    def test_reset_table_counts(self, test_db, reset_service):
        """Test getting table counts."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        test_db.commit()
        
        counts = reset_service.get_table_counts()
        
        assert 'users' in counts
        assert counts['users'] == 2
        assert 'purchases' in counts
        assert counts['purchases'] == 0
    
    def test_reset_single_table(self, test_db, reset_service):
        """Test resetting a single table."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')")
        test_db.commit()
        
        # Reset
        result = reset_service.reset_table('users')
        
        assert result.success
        assert result.records_deleted == 2
        assert 'users' in result.tables_cleared
        
        # Verify empty
        cursor.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 0
    
    def test_reset_all_data(self, test_db, reset_service):
        """Test resetting all data."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO purchases (user_id, amount, date) VALUES (1, 100.0, '2024-01-01')")
        test_db.commit()
        
        # Reset all
        result = reset_service.reset_database(keep_setup_data=False)
        
        assert result.success
        assert result.records_deleted >= 2
        assert 'users' in result.tables_cleared
        assert 'purchases' in result.tables_cleared
        
        # Verify all empty
        counts = reset_service.get_table_counts()
        assert all(count == 0 for count in counts.values())
    
    def test_preview_reset(self, test_db, reset_service):
        """Test preview reset operation."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO purchases (user_id, amount, date) VALUES (1, 50.0, '2024-01-01')")
        test_db.commit()
        
        # Preview
        preview = reset_service.preview_reset(keep_setup_data=False)
        
        assert 'tables' in preview
        assert 'record_counts' in preview
        assert 'total_records' in preview
        assert preview['total_records'] >= 2
        assert 'users' in preview['tables']
        assert 'purchases' in preview['tables']
    
    def test_reset_transaction_data_only(self, test_db, reset_service):
        """Test resetting only transaction data."""
        # Add test data
        cursor = test_db.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
        cursor.execute("INSERT INTO purchases (user_id, amount, date) VALUES (1, 75.0, '2024-01-01')")
        test_db.commit()
        
        # Reset transactions only
        result = reset_service.reset_transaction_data_only()
        
        assert result.success
        
        # Verify users preserved, purchases deleted
        cursor.execute("SELECT COUNT(*) FROM users")
        assert cursor.fetchone()[0] == 1
        
        cursor.execute("SELECT COUNT(*) FROM purchases")
        assert cursor.fetchone()[0] == 0
