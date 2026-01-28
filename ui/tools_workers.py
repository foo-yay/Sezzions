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


class BackupWorker(QRunnable):
    """Background worker for database backup operations"""
    
    def __init__(self, backup_service, backup_path: Optional[str] = None):
        super().__init__()
        self.backup_service = backup_service
        self.backup_path = backup_path
        self.signals = WorkerSignals()
        
    @Slot()
    def run(self):
        """Execute the backup operation"""
        try:
            result = self.backup_service.backup_database(backup_path=self.backup_path)
            self.signals.finished.emit(result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)


class RestoreWorker(QRunnable):
    """Background worker for database restore operations"""
    
    def __init__(self, restore_service, backup_path: str, restore_mode: str = "REPLACE"):
        super().__init__()
        self.restore_service = restore_service
        self.backup_path = backup_path
        self.restore_mode = restore_mode
        self.signals = WorkerSignals()
        
    @Slot()
    def run(self):
        """Execute the restore operation"""
        try:
            result = self.restore_service.restore_database(
                backup_path=self.backup_path,
                restore_mode=self.restore_mode
            )
            self.signals.finished.emit(result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)
