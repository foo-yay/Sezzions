"""
Background workers for Tools operations (recalculation, imports, backups)
"""
from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from typing import Optional, List
import traceback
import dataclasses


class WorkerSignals(QObject):
    """Signals for background workers"""
    progress = Signal(int, int, str)  # current, total, message
    finished = Signal(object)  # result object
    error = Signal(str)  # error message
    cancelled = Signal()


class RecalculationWorker(QRunnable):
    """Background worker for recalculation operations
    
    Runs recalculation off the UI thread to keep the interface responsive.
    Emits progress signals for UI updates.
    
    Note: Creates its own database connection to avoid SQLite thread safety issues.
    """
    
    def __init__(
        self,
        db_path: str,
        operation: str = "all",
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        user_ids: Optional[List[int]] = None,
        site_ids: Optional[List[int]] = None
    ):
        super().__init__()
        self.db_path = db_path
        self.operation = operation
        self.user_id = user_id
        self.site_id = site_id
        self.entity_type = entity_type
        self.user_ids = user_ids
        self.site_ids = site_ids
        self.signals = WorkerSignals()
        self._cancelled = False
        
    def cancel(self):
        """Request cancellation of the operation"""
        self._cancelled = True
        
    def _progress_callback(self, current: int, total: int, message: str):
        """Progress callback for recalculation service"""
        if self._cancelled:
            raise InterruptedError("Recalculation cancelled by user")
        self.signals.progress.emit(current, total, message)
        
    @Slot()
    def run(self):
        """Execute the recalculation operation"""
        try:
            # Create database connection in this thread (SQLite thread safety)
            from repositories.database import DatabaseManager
            from services.recalculation_service import RecalculationService
            
            db = DatabaseManager(self.db_path)
            recalc_service = RecalculationService(db)
            
            result = None
            
            if self.operation == "all":
                result = recalc_service.rebuild_all(
                    progress_callback=self._progress_callback
                )
                # Add operation tracking to result
                result = dataclasses.replace(result, operation=self.operation)
            elif self.operation == "pair":
                if self.user_id is None or self.site_id is None:
                    raise ValueError("user_id and site_id required for pair recalculation")
                result = recalc_service.rebuild_for_pair(
                    user_id=self.user_id,
                    site_id=self.site_id,
                    progress_callback=self._progress_callback
                )
                # Add operation tracking to result
                result = dataclasses.replace(result, operation=self.operation)
            elif self.operation == "after_import":
                if self.entity_type is None:
                    raise ValueError("entity_type required for after_import recalculation")
                result = recalc_service.rebuild_after_import(
                    entity_type=self.entity_type,
                    user_ids=self.user_ids or [],
                    site_ids=self.site_ids or [],
                    progress_callback=self._progress_callback
                )
                # Add operation tracking to result
                result = dataclasses.replace(result, operation=self.operation)
            else:
                raise ValueError(f"Unknown operation: {self.operation}")
                
            if self._cancelled:
                self.signals.cancelled.emit()
            else:
                self.signals.finished.emit(result)
                
        except InterruptedError:
            self.signals.cancelled.emit()
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)


class CSVImportWorker(QRunnable):
    """Background worker for CSV import operations"""
    
    def __init__(self, import_service, entity_type: str, file_path: str, **kwargs):
        super().__init__()
        self.import_service = import_service
        self.entity_type = entity_type
        self.file_path = file_path
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = False
        
    def cancel(self):
        """Request cancellation of the operation"""
        self._cancelled = True
        
    @Slot()
    def run(self):
        """Execute the CSV import operation"""
        try:
            # Note: CSV import is typically fast and atomic, so we don't
            # emit granular progress here. If needed, add progress callbacks
            # to CSVImportService similar to RecalculationService.
            
            result = self.import_service.import_from_csv(
                entity_type=self.entity_type,
                file_path=self.file_path,
                **self.kwargs
            )
            
            if self._cancelled:
                self.signals.cancelled.emit()
            else:
                self.signals.finished.emit(result)
                
        except InterruptedError:
            self.signals.cancelled.emit()
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)


class DatabaseBackupWorker(QRunnable):
    """Background worker for database backup operations
    
    Note: Creates a new read-only connection to the database for thread safety.
    SQLite allows multiple readers, so this won't block the main app.
    """
    
    def __init__(self, db_path: str, backup_path: str, include_audit_log: bool = True):
        super().__init__()
        self.db_path = db_path
        self.backup_path = backup_path
        self.include_audit_log = include_audit_log
        self.signals = WorkerSignals()
        
    @Slot()
    def run(self):
        """Execute the backup operation"""
        import sqlite3
        from pathlib import Path
        from services.tools.dtos import BackupResult
        
        src_conn = None
        dest_conn = None
        
        try:
            # Open source database with its own connection in this thread.
            # This avoids cross-thread SQLite connection usage.
            src_path = Path(self.db_path).resolve()
            src_conn = sqlite3.connect(str(src_path), timeout=30.0)
            
            # Ensure backup directory exists
            backup_path_obj = Path(self.backup_path)
            backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Create destination database
            dest_conn = sqlite3.connect(self.backup_path, timeout=30.0)
            
            # Perform the backup using SQLite's online backup API
            src_conn.backup(dest_conn)
            
            # Optionally exclude audit log
            if not self.include_audit_log:
                dest_cursor = dest_conn.cursor()
                dest_cursor.execute("DELETE FROM audit_log WHERE 1=1")
                dest_conn.commit()
            
            dest_conn.close()
            src_conn.close()
            
            # Get backup file size
            backup_size = backup_path_obj.stat().st_size
            
            # Return success result
            result = BackupResult(
                success=True,
                backup_path=self.backup_path,
                size_bytes=backup_size
            )
            
            self.signals.finished.emit(result)
            
        except Exception as e:
            # Clean up connections
            if dest_conn:
                try:
                    dest_conn.close()
                except:
                    pass
            if src_conn:
                try:
                    src_conn.close()
                except:
                    pass
            
            # Clean up failed backup file
            backup_file = Path(self.backup_path)
            if backup_file.exists():
                try:
                    backup_file.unlink()
                except:
                    pass
            
            error_msg = f"Backup failed: {str(e)}"
            result = BackupResult(success=False, error=error_msg)
            self.signals.finished.emit(result)


class DatabaseRestoreWorker(QRunnable):
    """Background worker for database restore operations
    
    Creates its own database connection for SQLite thread safety.
    """
    
    def __init__(self, db_path: str, backup_path: str, restore_mode, tables: Optional[List[str]] = None):
        super().__init__()
        self.db_path = db_path
        self.backup_path = backup_path
        self.restore_mode = restore_mode
        self.tables = tables
        self.signals = WorkerSignals()
        
    @Slot()
    def run(self):
        """Execute the restore operation"""
        db = None
        try:
            # Create database connection in this thread (SQLite thread safety)
            from repositories.database import DatabaseManager
            from services.tools.restore_service import RestoreService
            
            db = DatabaseManager(self.db_path)
            restore_service = RestoreService(db)
            
            result = restore_service.restore_database(
                backup_path=self.backup_path,
                mode=self.restore_mode,
                tables=self.tables
            )
            
            self.signals.finished.emit(result)
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)
        finally:
            # Close database connection
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


class DatabaseResetWorker(QRunnable):
    """Background worker for database reset operations
    
    Creates its own database connection for SQLite thread safety.
    """
    
    def __init__(self, db_path: str, keep_setup_data: bool = False, keep_audit_log: bool = False, tables_to_reset: Optional[List[str]] = None):
        super().__init__()
        self.db_path = db_path
        self.keep_setup_data = keep_setup_data
        self.keep_audit_log = keep_audit_log
        self.tables_to_reset = tables_to_reset
        self.signals = WorkerSignals()
        
    @Slot()
    def run(self):
        """Execute the reset operation"""
        db = None
        try:
            # Create database connection in this thread (SQLite thread safety)
            from repositories.database import DatabaseManager
            from services.tools.reset_service import ResetService
            
            db = DatabaseManager(self.db_path)
            reset_service = ResetService(db)
            
            result = reset_service.reset_database(
                keep_setup_data=self.keep_setup_data,
                keep_audit_log=self.keep_audit_log,
                tables_to_reset=self.tables_to_reset
            )
            
            self.signals.finished.emit(result)
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)
        finally:
            # Close database connection
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
