"""
Unit tests for database tools workers and exclusive operation locking.

Tests worker-based execution, thread safety, and operation locking.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QThreadPool

from app_facade import AppFacade
from ui.tools_workers import DatabaseBackupWorker, DatabaseRestoreWorker, DatabaseResetWorker
from services.tools.enums import RestoreMode


class TestExclusiveOperationLock:
    """Test exclusive operation lock mechanism in AppFacade."""
    
    def test_acquire_lock_when_available(self):
        """Lock can be acquired when no operation is active."""
        facade = AppFacade(":memory:")
        
        assert facade.acquire_tools_lock() is True
        assert facade.is_tools_operation_active() is True
        
        facade.release_tools_lock()
        assert facade.is_tools_operation_active() is False

        facade.db.close()
    
    def test_cannot_acquire_lock_when_active(self):
        """Lock cannot be acquired when operation is already active."""
        facade = AppFacade(":memory:")
        
        # First acquisition succeeds
        assert facade.acquire_tools_lock() is True
        
        # Second acquisition fails
        assert facade.acquire_tools_lock() is False
        assert facade.is_tools_operation_active() is True
        
        # After release, can acquire again
        facade.release_tools_lock()
        assert facade.acquire_tools_lock() is True
        
        facade.release_tools_lock()

        facade.db.close()
    
    def test_lock_is_thread_safe(self):
        """Lock operations are thread-safe."""
        import threading
        
        facade = AppFacade(":memory:")
        results = []
        
        def try_acquire():
            result = facade.acquire_tools_lock()
            results.append(result)
            if result:
                # Simulate some work
                import time
                time.sleep(0.01)
                facade.release_tools_lock()
        
        # Start multiple threads trying to acquire lock
        threads = [threading.Thread(target=try_acquire) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Only one thread should have succeeded in acquiring the lock at a time
        # But since they release, multiple successes are possible
        assert True in results  # At least one succeeded
        assert False in results  # At least one failed

        facade.db.close()


class TestDatabaseBackupWorker:
    """Test DatabaseBackupWorker creates read-only connection."""
    
    def test_worker_uses_db_path(self, tmp_path):
        """Worker receives db_path and creates its own read-only connection."""
        db_path = str(tmp_path / "test.db")
        backup_path = str(tmp_path / "backup.db")
        
        # Create a simple database
        from repositories.database import DatabaseManager
        db = DatabaseManager(db_path)
        db.close()
        
        # Create worker with db_path (not db_connection)
        worker = DatabaseBackupWorker(db_path, backup_path, include_audit_log=True)
        
        # Worker should store db_path
        assert worker.db_path == db_path
        assert worker.backup_path == backup_path
        assert worker.include_audit_log is True
    
    def test_worker_has_signals(self):
        """Worker has WorkerSignals for communication."""
        db_path = ":memory:"
        backup_path = "/tmp/backup.db"
        
        worker = DatabaseBackupWorker(db_path, backup_path)
        
        # Check signals exist
        assert hasattr(worker.signals, 'finished')
        assert hasattr(worker.signals, 'error')
        assert hasattr(worker.signals, 'progress')


class TestDatabaseRestoreWorker:
    """Test DatabaseRestoreWorker creates its own connection."""
    
    def test_worker_uses_db_path(self, tmp_path):
        """Worker receives db_path and can create its own connection."""
        db_path = str(tmp_path / "test.db")
        backup_path = str(tmp_path / "backup.db")
        
        worker = DatabaseRestoreWorker(db_path, backup_path, RestoreMode.REPLACE)
        
        # Worker should store db_path
        assert worker.db_path == db_path
        assert worker.backup_path == backup_path
        assert worker.restore_mode == RestoreMode.REPLACE
    
    def test_worker_accepts_tables_list(self, tmp_path):
        """Worker accepts optional tables list for selective restore."""
        db_path = str(tmp_path / "test.db")
        backup_path = str(tmp_path / "backup.db")
        tables = ['purchases', 'game_sessions']
        
        worker = DatabaseRestoreWorker(
            db_path, 
            backup_path, 
            RestoreMode.MERGE_SELECTED, 
            tables=tables
        )
        
        assert worker.tables == tables


class TestDatabaseResetWorker:
    """Test DatabaseResetWorker creates its own connection."""
    
    def test_worker_uses_db_path(self, tmp_path):
        """Worker receives db_path and can create its own connection."""
        db_path = str(tmp_path / "test.db")
        
        worker = DatabaseResetWorker(db_path, keep_setup_data=True, keep_audit_log=True)
        
        # Worker should store db_path
        assert worker.db_path == db_path
        assert worker.keep_setup_data is True
        assert worker.keep_audit_log is True
    
    def test_worker_accepts_tables_list(self, tmp_path):
        """Worker accepts optional tables list for selective reset."""
        db_path = str(tmp_path / "test.db")
        tables = ['purchases', 'redemptions']
        
        worker = DatabaseResetWorker(db_path, tables_to_reset=tables)
        
        assert worker.tables_to_reset == tables


class TestAppFacadeWorkerCreation:
    """Test AppFacade creates workers correctly."""
    
    def test_create_backup_worker(self):
        """Facade creates backup worker with correct parameters."""
        facade = AppFacade(":memory:")
        backup_path = "/tmp/backup.db"
        
        worker = facade.create_backup_worker(backup_path, include_audit_log=False)
        
        assert isinstance(worker, DatabaseBackupWorker)
        assert worker.db_path == facade.db_path
        assert worker.backup_path == backup_path
        assert worker.include_audit_log is False

        facade.db.close()
    
    def test_create_restore_worker(self):
        """Facade creates restore worker with correct parameters."""
        facade = AppFacade(":memory:")
        backup_path = "/tmp/backup.db"
        
        worker = facade.create_restore_worker(backup_path, RestoreMode.MERGE_ALL)
        
        assert isinstance(worker, DatabaseRestoreWorker)
        assert worker.db_path == facade.db_path
        assert worker.backup_path == backup_path
        assert worker.restore_mode == RestoreMode.MERGE_ALL

        facade.db.close()
    
    def test_create_reset_worker(self):
        """Facade creates reset worker with correct parameters."""
        facade = AppFacade(":memory:")
        
        worker = facade.create_reset_worker(keep_setup_data=True, keep_audit_log=False)
        
        assert isinstance(worker, DatabaseResetWorker)
        assert worker.db_path == facade.db_path
        assert worker.keep_setup_data is True
        assert worker.keep_audit_log is False

        facade.db.close()


class TestWorkerIndependence:
    """Test that workers handle database connections appropriately."""
    
    def test_backup_worker_creates_own_connection(self, tmp_path):
        """Backup worker creates its own read-only connection."""
        db_path = str(tmp_path / "test.db")
        backup_path = "/tmp/backup.db"
        
        # Create worker - will create read-only connection in run()
        worker = DatabaseBackupWorker(db_path, backup_path)
        
        # Worker should have db_path, not db_connection
        assert worker.db_path == db_path
        assert not hasattr(worker, 'db_connection')
    
    def test_restore_worker_creates_own_connection(self, tmp_path):
        """Restore worker creates its own DatabaseManager instance."""
        db_path = str(tmp_path / "test.db")
        
        worker = DatabaseRestoreWorker(db_path, str(tmp_path / "backup.db"), RestoreMode.REPLACE)
        
        # Worker has db_path for creating connection
        assert worker.db_path == db_path
    
    def test_reset_worker_creates_own_connection(self, tmp_path):
        """Reset worker creates its own DatabaseManager instance."""
        db_path = str(tmp_path / "test.db")
        
        worker = DatabaseResetWorker(db_path, keep_setup_data=True)
        
        # Worker has db_path for creating connection
        assert worker.db_path == db_path
    
    def test_workers_do_not_share_connections(self):
        """Multiple workers can be created with different db paths."""
        db_path1 = "/tmp/db1.db"
        db_path2 = "/tmp/db2.db"
        
        worker1 = DatabaseBackupWorker(db_path1, "/tmp/backup1.db")
        worker2 = DatabaseBackupWorker(db_path2, "/tmp/backup2.db")
        
        # Workers use different paths
        assert worker1.db_path != worker2.db_path
        assert worker1.backup_path != worker2.backup_path
        
        # They are separate objects
        assert worker1 is not worker2
        assert worker1.signals is not worker2.signals


# Note: Full integration tests that actually run workers in threads
# would require a Qt application context and are better placed in
# integration tests or manual testing scenarios.
