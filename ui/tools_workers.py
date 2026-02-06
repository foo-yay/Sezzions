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
        site_ids: Optional[List[int]] = None,
        settings_dict: Optional[dict] = None
    ):
        super().__init__()
        self.db_path = db_path
        self.operation = operation
        self.user_id = user_id
        self.site_id = site_id
        self.entity_type = entity_type
        self.user_ids = user_ids
        self.site_ids = site_ids
        self.settings_dict = settings_dict or {}
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
        db = None
        try:
            # Create database connection in this thread (SQLite thread safety)
            from repositories.database import DatabaseManager
            from services.recalculation_service import RebuildResult, RecalculationService
            from services.tax_withholding_service import TaxWithholdingService
            from repositories.adjustment_repository import AdjustmentRepository
            from repositories.game_session_event_link_repository import GameSessionEventLinkRepository
            from repositories.game_session_repository import GameSessionRepository
            from repositories.purchase_repository import PurchaseRepository
            from repositories.redemption_repository import RedemptionRepository
            from repositories.site_repository import SiteRepository
            from services.adjustment_service import AdjustmentService
            from services.fifo_service import FIFOService
            from services.game_session_event_link_service import GameSessionEventLinkService
            from services.game_session_service import GameSessionService
            
            db = DatabaseManager(self.db_path)
            
            # Create tax withholding service with settings from UI thread
            tax_service = TaxWithholdingService(db, settings=self.settings_dict)

            # Adjustments/checkpoints must be wired so rebuilds include basis adjustments (FIFO)
            # and checkpoints (expected balances within session recalculation).
            adjustment_repo = AdjustmentRepository(db)
            adjustment_service = AdjustmentService(adjustment_repo)

            # Session/event services for rebuild completeness
            purchase_repo = PurchaseRepository(db)
            redemption_repo = RedemptionRepository(db)
            session_repo = GameSessionRepository(db)
            site_repo = SiteRepository(db)
            fifo_service = FIFOService(purchase_repo)

            game_session_service = GameSessionService(
                session_repo,
                site_repo=site_repo,
                fifo_service=fifo_service,
                purchase_repo=purchase_repo,
                redemption_repo=redemption_repo,
                tax_withholding_service=tax_service,
                adjustment_service=adjustment_service,
            )

            recalc_service = RecalculationService(
                db,
                game_session_service=game_session_service,
                tax_withholding_service=tax_service,
                adjustment_service=adjustment_service,
            )

            link_repo = GameSessionEventLinkRepository(db)
            link_service = GameSessionEventLinkService(
                link_repo,
                session_repo,
                purchase_repo,
                redemption_repo,
                db,
            )
            
            result = None
            
            if self.operation == "all":
                result = recalc_service.rebuild_all(
                    progress_callback=self._progress_callback
                )
                # Keep linking coherent with derived rebuilds
                link_service.rebuild_links_all()
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
                link_service.rebuild_links_for_pair(self.site_id, self.user_id)
                # Add operation tracking to result
                result = dataclasses.replace(result, operation=self.operation)
            elif self.operation == "user":
                if self.user_id is None:
                    raise ValueError("user_id required for user recalculation")
                pairs = [(u, s) for (u, s) in recalc_service.iter_pairs() if u == self.user_id]
                total_pairs = len(pairs)
                aggregate = None
                for idx, (user_id, site_id) in enumerate(pairs, 1):
                    if self._cancelled:
                        raise InterruptedError("Recalculation cancelled by user")
                    self._progress_callback(idx, max(1, total_pairs), f"Rebuilding pair {idx}/{total_pairs}")
                    pair_result = recalc_service.rebuild_for_pair(user_id=user_id, site_id=site_id)
                    link_service.rebuild_links_for_pair(site_id, user_id)
                    if aggregate is None:
                        aggregate = pair_result
                    else:
                        aggregate = dataclasses.replace(
                            aggregate,
                            pairs_processed=aggregate.pairs_processed + pair_result.pairs_processed,
                            redemptions_processed=aggregate.redemptions_processed + pair_result.redemptions_processed,
                            allocations_written=aggregate.allocations_written + pair_result.allocations_written,
                            purchases_updated=aggregate.purchases_updated + pair_result.purchases_updated,
                            game_sessions_processed=aggregate.game_sessions_processed + pair_result.game_sessions_processed,
                        )
                result = aggregate or RebuildResult(
                    pairs_processed=0,
                    redemptions_processed=0,
                    allocations_written=0,
                    purchases_updated=0,
                    game_sessions_processed=0,
                )
                result = dataclasses.replace(result, operation=self.operation)
            elif self.operation == "site":
                if self.site_id is None:
                    raise ValueError("site_id required for site recalculation")
                pairs = [(u, s) for (u, s) in recalc_service.iter_pairs() if s == self.site_id]
                total_pairs = len(pairs)
                aggregate = None
                for idx, (user_id, site_id) in enumerate(pairs, 1):
                    if self._cancelled:
                        raise InterruptedError("Recalculation cancelled by user")
                    self._progress_callback(idx, max(1, total_pairs), f"Rebuilding pair {idx}/{total_pairs}")
                    pair_result = recalc_service.rebuild_for_pair(user_id=user_id, site_id=site_id)
                    link_service.rebuild_links_for_pair(site_id, user_id)
                    if aggregate is None:
                        aggregate = pair_result
                    else:
                        aggregate = dataclasses.replace(
                            aggregate,
                            pairs_processed=aggregate.pairs_processed + pair_result.pairs_processed,
                            redemptions_processed=aggregate.redemptions_processed + pair_result.redemptions_processed,
                            allocations_written=aggregate.allocations_written + pair_result.allocations_written,
                            purchases_updated=aggregate.purchases_updated + pair_result.purchases_updated,
                            game_sessions_processed=aggregate.game_sessions_processed + pair_result.game_sessions_processed,
                        )
                result = aggregate or RebuildResult(
                    pairs_processed=0,
                    redemptions_processed=0,
                    allocations_written=0,
                    purchases_updated=0,
                    game_sessions_processed=0,
                )
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
                # Keep linking coherent for affected pairs
                affected_pairs = []
                for user_id, site_id in recalc_service.iter_pairs():
                    if self.user_ids and user_id not in self.user_ids:
                        continue
                    if self.site_ids and site_id not in self.site_ids:
                        continue
                    affected_pairs.append((user_id, site_id))
                for user_id, site_id in affected_pairs:
                    link_service.rebuild_links_for_pair(site_id, user_id)
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
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass


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
