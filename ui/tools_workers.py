"""
Background workers for Tools operations (recalculation, imports, backups)
"""
from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from typing import Optional, List
import traceback


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
            elif self.operation == "pair":
                if self.user_id is None or self.site_id is None:
                    raise ValueError("user_id and site_id required for pair recalculation")
                result = recalc_service.rebuild_for_pair(
                    user_id=self.user_id,
                    site_id=self.site_id,
                    progress_callback=self._progress_callback
                )
            elif self.operation == "after_import":
                if self.entity_type is None:
                    raise ValueError("entity_type required for after_import recalculation")
                result = recalc_service.rebuild_after_import(
                    entity_type=self.entity_type,
                    user_ids=self.user_ids or [],
                    site_ids=self.site_ids or [],
                    progress_callback=self._progress_callback
                )
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
    
    Creates its own database connection for SQLite thread safety.
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
        try:
            # Create database connection in this thread (SQLite thread safety)
            from repositories.database import DatabaseManager
            from services.tools.backup_service import BackupService
            
            db = DatabaseManager(self.db_path)
            backup_service = BackupService(db)
            
            result = backup_service.backup_database(
                backup_path=self.backup_path,
                include_audit_log=self.include_audit_log
            )
            
            self.signals.finished.emit(result)
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)


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
