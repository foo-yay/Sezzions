"""
AppFacade - Unified interface for Qt application to access OOP backend services

This facade provides a single entry point for the Qt UI to interact with
all backend services while maintaining backward compatibility during migration.
"""
from dataclasses import asdict
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
import threading

from repositories.database import DatabaseManager
from services.data_change_event import DataChangeEvent, OperationType
from repositories.user_repository import UserRepository
from repositories.site_repository import SiteRepository
from repositories.card_repository import CardRepository
from repositories.game_type_repository import GameTypeRepository
from repositories.game_repository import GameRepository
from repositories.redemption_method_repository import RedemptionMethodRepository
from repositories.redemption_method_type_repository import RedemptionMethodTypeRepository
from repositories.purchase_repository import PurchaseRepository
from repositories.redemption_repository import RedemptionRepository
from repositories.game_session_repository import GameSessionRepository
from repositories.unrealized_position_repository import UnrealizedPositionRepository
from repositories.realized_transaction_repository import RealizedTransactionRepository
from repositories.daily_session_repository import DailySessionRepository
from repositories.game_session_event_link_repository import GameSessionEventLinkRepository
from repositories.expense_repository import ExpenseRepository
from repositories.adjustment_repository import AdjustmentRepository

from services.user_service import UserService
from services.site_service import SiteService
from services.card_service import CardService
from services.game_type_service import GameTypeService
from services.game_service import GameService
from services.redemption_method_service import RedemptionMethodService
from services.redemption_method_type_service import RedemptionMethodTypeService
from services.purchase_service import PurchaseService
from services.redemption_service import RedemptionService
from services.fifo_service import FIFOService
from services.game_session_service import GameSessionService
from services.report_service import ReportService
from services.daily_sessions_service import DailySessionsService
from services.validation_service import ValidationService
from services.recalculation_service import RecalculationService
from services.game_session_event_link_service import GameSessionEventLinkService
from services.expense_service import ExpenseService
from services.realized_notes_service import RealizedNotesService
from services.tools.csv_import_service import CSVImportService
from services.tools.csv_export_service import CSVExportService
from services.tax_withholding_service import TaxWithholdingService
from services.notification_service import NotificationService
from services.notification_rules_service import NotificationRulesService
from services.adjustment_service import AdjustmentService
from services.repair_mode_service import RepairModeService
from services.timestamp_service import TimestampService
from services.audit_service import AuditService
from services.undo_redo_service import UndoRedoService
from services.update_service import UpdateService, UpdateAsset, DEFAULT_UPDATE_MANIFEST_URL
from services.db_location_service import settings_file_path
from repositories.notification_repository import NotificationRepository
import __init__ as sezzions_package

from models.user import User
from models.site import Site
from models.card import Card
from models.game_type import GameType
from models.game import Game
from models.redemption_method import RedemptionMethod
from models.redemption_method_type import RedemptionMethodType
from models.purchase import Purchase
from models.redemption import Redemption
from models.game_session import GameSession
from models.unrealized_position import UnrealizedPosition
from models.realized_transaction import RealizedTransaction
from models.expense import Expense
from models.adjustment import Adjustment


class AppFacade:
    """
    Central facade for accessing all backend services.
    
    Provides a unified interface for the Qt UI while maintaining clean
    separation between presentation and business logic layers.
    """
    
    def __init__(self, db_path: str = "sezzions.db"):
        """
        Initialize facade with all services.
        
        Args:
            db_path: Path to SQLite database file
        """
        # Initialize database manager
        self.db = DatabaseManager(db_path)
        self.db_path = db_path  # Store db_path for workers
        
        # Exclusive tools operation lock (prevents concurrent destructive operations)
        self._tools_lock = threading.Lock()
        self._tools_operation_active = False
        
        # Data change event system for unified refresh
        self._data_change_listeners: List[Callable[[DataChangeEvent], None]] = []
        self._maintenance_mode = False
        
        # Initialize repositories
        self.user_repo = UserRepository(self.db)
        self.site_repo = SiteRepository(self.db)
        self.card_repo = CardRepository(self.db)
        self.game_type_repo = GameTypeRepository(self.db)
        self.game_repo = GameRepository(self.db)
        self.redemption_method_repo = RedemptionMethodRepository(self.db)
        self.redemption_method_type_repo = RedemptionMethodTypeRepository(self.db)
        self.purchase_repo = PurchaseRepository(self.db)
        self.redemption_repo = RedemptionRepository(self.db)
        self.game_session_repo = GameSessionRepository(self.db)
        self.unrealized_position_repo = UnrealizedPositionRepository(self.db)
        self.realized_transaction_repo = RealizedTransactionRepository(self.db)
        self.daily_session_repo = DailySessionRepository(self.db)
        self.game_session_event_link_repo = GameSessionEventLinkRepository(self.db)
        self.expense_repo = ExpenseRepository(self.db)
        
        # Initialize services
        self.user_service = UserService(self.user_repo)
        self.site_service = SiteService(self.site_repo)
        self.card_service = CardService(self.card_repo)
        self.game_type_service = GameTypeService(self.game_type_repo)
        self.game_service = GameService(self.game_repo)
        self.redemption_method_service = RedemptionMethodService(self.redemption_method_repo)
        self.redemption_method_type_service = RedemptionMethodTypeService(self.redemption_method_type_repo)
        
        self.fifo_service = FIFOService(self.purchase_repo)
        self.purchase_service = PurchaseService(self.purchase_repo, card_repo=self.card_repo)
        self.redemption_service = RedemptionService(
            self.redemption_repo,
            self.fifo_service,
            db_manager=self.db  # Needed for redemption_allocations table
        )
        # Tax withholding estimates (Issue #29)
        self.tax_withholding_service = TaxWithholdingService(self.db, settings=None)  # wired from MainWindow

        # Adjustments service (must be before game_session_service)
        self.adjustment_repo = AdjustmentRepository(self.db)
        self.adjustment_service = AdjustmentService(self.adjustment_repo)

        self.game_session_service = GameSessionService(
            self.game_session_repo,
            site_repo=self.site_repo,  # Needed for SC rate in P/L calculation
            fifo_service=self.fifo_service,  # May be needed in future
            purchase_repo=self.purchase_repo,
            redemption_repo=self.redemption_repo,
            tax_withholding_service=self.tax_withholding_service,
            adjustment_service=self.adjustment_service,
            redemption_service=self.redemption_service,  # Issue #148 — PENDING_CANCEL processing
        )
        
        # Inject game_session_service into purchase_service for redeemable balance computation
        self.purchase_service.game_session_service = self.game_session_service
        
        self.report_service = ReportService(self.db)
        self.validation_service = ValidationService(self.db)
        self.report_service = ReportService(self.db)
        self.daily_sessions_service = DailySessionsService(self.db, self.daily_session_repo)
        self.expense_service = ExpenseService(self.expense_repo)
        self.realized_notes_service = RealizedNotesService(self.db)

        # Bulk rebuild / recalculation orchestration (legacy parity)
        # Pass game_session_service so RecalculationService can recalculate both FIFO + sessions
        self.recalculation_service = RecalculationService(
            self.db,
            game_session_service=self.game_session_service,
            tax_withholding_service=self.tax_withholding_service,
            adjustment_service=self.adjustment_service
        )
        self.game_session_event_link_service = GameSessionEventLinkService(
            self.game_session_event_link_repo,
            self.game_session_repo,
            self.purchase_repo,
            self.redemption_repo,
            self.db,
        )
        
        # Tools services (CSV import/export, backup/restore)
        self.csv_import_service = CSVImportService(self.db)
        self.csv_export_service = CSVExportService(self.db)
        
        # Notification services
        notification_settings_path = str(settings_file_path())
        self.notification_repo = NotificationRepository(settings_file=notification_settings_path)
        self.notification_service = NotificationService(self.notification_repo)
        self.notification_rules_service = NotificationRulesService(
            self.notification_service,
            None,  # Will be set from MainWindow
            self.db
        )

        app_version = getattr(sezzions_package, "__version__", "0.1.0")
        self.update_service = UpdateService(
            current_version=app_version,
            manifest_url=DEFAULT_UPDATE_MANIFEST_URL,
        )
        
        # Repair Mode service (Issue #55)
        # Will be wired to MainWindow settings after construction
        self.repair_mode_service = None
        
        # Timestamp uniqueness enforcement
        self.timestamp_service = TimestampService(self.db)
        
        # Audit and Undo/Redo services (Issue #92)
        self.audit_service = AuditService(self.db)
        self.undo_redo_service = UndoRedoService(
            self.db, 
            self.audit_service,
            post_operation_callback=self._handle_undo_redo_recalculation,
            repositories={
                'purchases': self.purchase_repo,
                'redemptions': self.redemption_repo,
                'game_sessions': self.game_session_repo,
                'account_adjustments': self.adjustment_repo,
            }
        )
        
        # Wire audit_service and undo_redo_service into existing services
        self.purchase_service.audit_service = self.audit_service
        self.purchase_service.undo_redo_service = self.undo_redo_service
        self.redemption_service.audit_service = self.audit_service
        self.redemption_service.undo_redo_service = self.undo_redo_service
        self.game_session_service.audit_service = self.audit_service
        self.game_session_service.undo_redo_service = self.undo_redo_service
        self.adjustment_service.audit_service = self.audit_service
        self.adjustment_service.undo_redo_service = self.undo_redo_service

    @staticmethod
    def _normalize_time(value: Optional[str]) -> str:
        if not value:
            return "00:00:00"
        value = value.strip()
        if len(value) == 5:
            return f"{value}:00"
        return value

    @classmethod
    def _to_dt(cls, date_value: date, time_value: Optional[str]) -> datetime:
        time_str = cls._normalize_time(time_value)
        return datetime.combine(date_value, datetime.strptime(time_str, "%H:%M:%S").time())

    @classmethod
    def _earliest_boundary(
        cls,
        first_date: date,
        first_time: Optional[str],
        second_date: date,
        second_time: Optional[str],
    ) -> Tuple[date, str]:
        first_dt = cls._to_dt(first_date, first_time)
        second_dt = cls._to_dt(second_date, second_time)
        if second_dt < first_dt:
            return second_date, cls._normalize_time(second_time)
        return first_date, cls._normalize_time(first_time)

    def get_full_redemption_window_for_timestamp(
        self,
        user_id: int,
        site_id: int,
        anchor_date: date,
        anchor_time: str = "23:59:59",
    ) -> tuple[Optional[tuple[date, str]], Optional[tuple[date, str]]]:
        """Return (prev_full_redemption, next_full_redemption) around a timestamp.

        A "full redemption" is defined as a redemption with more_remaining == False.
        Either side may be None if no full redemption exists in that direction.

        Notes:
        - Uses strict comparisons: prev < anchor, next > anchor.
        - Times are normalized to HH:MM:SS.
        """
        try:
            anchor_dt = self._to_dt(anchor_date, anchor_time or "23:59:59")
            redemptions = self.redemption_repo.get_by_user_and_site(int(user_id), int(site_id))
        except Exception:
            return None, None

        prev_item: Optional[tuple[datetime, date, str]] = None
        next_item: Optional[tuple[datetime, date, str]] = None

        for r in redemptions:
            try:
                if bool(getattr(r, "more_remaining", False)):
                    continue
                r_time = self._normalize_time(getattr(r, "redemption_time", None))
                r_dt = self._to_dt(r.redemption_date, r_time)
            except Exception:
                continue

            if r_dt < anchor_dt:
                if prev_item is None or r_dt > prev_item[0]:
                    prev_item = (r_dt, r.redemption_date, r_time)
            elif r_dt > anchor_dt:
                if next_item is None or r_dt < next_item[0]:
                    next_item = (r_dt, r.redemption_date, r_time)

        prev_out = (prev_item[1], prev_item[2]) if prev_item else None
        next_out = (next_item[1], next_item[2]) if next_item else None
        return prev_out, next_out

    def get_full_redemption_datetimes_for_user_site(
        self,
        user_id: int,
        site_id: int,
    ) -> list[datetime]:
        """Return sorted datetimes for full redemptions for a user/site."""
        try:
            redemptions = self.redemption_repo.get_by_user_and_site(int(user_id), int(site_id))
        except Exception:
            return []

        out: list[datetime] = []
        for r in redemptions:
            try:
                if bool(getattr(r, "more_remaining", False)):
                    continue
                r_time = self._normalize_time(getattr(r, "redemption_time", None))
                out.append(self._to_dt(r.redemption_date, r_time))
            except Exception:
                continue

        out.sort()
        return out

    def _find_containing_session_start(
        self,
        site_id: int,
        user_id: int,
        session_date: date,
        session_time: Optional[str],
    ) -> Optional[Tuple[date, str]]:
        from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc, utc_date_time_to_local

        ts_time = self._normalize_time(session_time)
        tz_name = get_configured_timezone_name()
        date_str, ts_time = local_date_time_to_utc(session_date, ts_time, tz_name)

        row = self.db.fetch_one(
            """
            SELECT session_date, COALESCE(session_time,'00:00:00') as start_time
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (session_date < ? OR (session_date = ? AND COALESCE(session_time,'00:00:00') <= ?))
              AND (end_date IS NULL
                   OR ? < end_date
                   OR (? = end_date AND ? <= COALESCE(end_time,'23:59:59')))
            ORDER BY session_date DESC, COALESCE(session_time,'00:00:00') DESC
            LIMIT 1
            """,
            (site_id, user_id, date_str, date_str, ts_time, date_str, date_str, ts_time),
        )
        if not row:
            return None
        start_date = row["session_date"]
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        start_date, start_time = utc_date_time_to_local(start_date, row["start_time"], tz_name)
        return start_date, start_time

    def _containing_boundary(
        self,
        site_id: int,
        user_id: int,
        session_date: date,
        session_time: Optional[str],
    ) -> Tuple[date, str]:
        containing = self._find_containing_session_start(
            site_id,
            user_id,
            session_date,
            session_time,
        )
        if containing:
            return containing

        # Issue #152: the event is not DURING any session.  It may fall in the
        # AFTER gap of the most-recently-closed session (i.e. the session whose
        # end_time is at or before the event timestamp).  If that is the case,
        # use that session's START as the boundary so the scoped rebuild pulls
        # in the prior session and can (re-)create its AFTER link while also
        # preserving any BEFORE-purchase links for that session.
        #
        # Without this, create_redemption would pass a boundary = raw event
        # time, the just-ended session would NOT appear in the suffix window,
        # and the AFTER redemption link would never be created.
        from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc, utc_date_time_to_local
        tz_name = get_configured_timezone_name()
        ts_time = self._normalize_time(session_time)
        utc_date, utc_time = local_date_time_to_utc(session_date, ts_time, tz_name)

        row = self.db.fetch_one(
            """
            SELECT session_date, COALESCE(session_time,'00:00:00') as start_time
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND status = 'Closed'
              AND (end_date < ?
                   OR (end_date = ? AND COALESCE(end_time,'23:59:59') <= ?))
            ORDER BY COALESCE(end_date, session_date) DESC,
                     COALESCE(end_time, '00:00:00') DESC
            LIMIT 1
            """,
            (site_id, user_id, utc_date, utc_date, utc_time),
        )
        if row:
            start_date = row["session_date"]
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            start_date, start_time = utc_date_time_to_local(start_date, row["start_time"], tz_name)
            return start_date, start_time

        return session_date, ts_time

    def _earliest_boundary_with_containing(
        self,
        site_id: int,
        user_id: int,
        first_date: date,
        first_time: Optional[str],
        second_date: date,
        second_time: Optional[str],
    ) -> Tuple[date, str]:
        first = self._containing_boundary(site_id, user_id, first_date, first_time)
        second = self._containing_boundary(site_id, user_id, second_date, second_time)
        return self._earliest_boundary(first[0], first[1], second[0], second[1])
    
    def _rebuild_or_mark_stale(
        self,
        user_id: int,
        site_id: int,
        boundary_date: date,
        boundary_time: str,
        reason: Optional[str] = None
    ) -> None:
        """
        Either rebuild derived data immediately, or mark the pair as stale (Repair Mode).
        
        When Repair Mode is OFF: performs full rebuild (FIFO + sessions + links).
        When Repair Mode is ON: marks the pair stale for explicit rebuild later.
        
        Args:
            user_id: User ID
            site_id: Site ID
            boundary_date: Earliest date to rebuild from
            boundary_time: Earliest time to rebuild from
            reason: Optional reason for stale marking (e.g., "purchase edit")
        """
        if self.repair_mode_service and self.repair_mode_service.is_enabled():
            # Repair Mode: mark stale instead of rebuilding
            self.repair_mode_service.mark_pair_stale(
                user_id=user_id,
                site_id=site_id,
                from_date=boundary_date.isoformat(),
                from_time=boundary_time,
                reason=reason
            )
        else:
            # Normal mode: rebuild immediately.
            # The boundary comes from _containing_boundary which returns LOCAL time,
            # but the FIFO and link rebuild services query raw DB columns stored as UTC.
            # Convert to UTC so the suffix/checkpoint SQL comparisons are consistent.
            # (Issue #152: mixing LOCAL boundary against UTC-stored end_time causes
            # incorrect suffix inclusion and silent BEFORE link deletion.)
            from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc as _l2u
            _tz = get_configured_timezone_name()
            _utc_date, _utc_time = _l2u(boundary_date, boundary_time, _tz)
            self.recalculation_service.rebuild_fifo_for_pair_from(
                user_id,
                site_id,
                _utc_date,
                _utc_time
            )
            # Session links / closed-session fields are more sensitive to nested
            # lifecycle edits (undo/delete/queued cancel). Rebuild them for the
            # whole pair after FIFO is corrected to avoid suffix drift.
            self.game_session_event_link_service.rebuild_links_for_pair(
                site_id,
                user_id,
            )
            self.game_session_service.recalculate_closed_sessions_for_pair(
                user_id,
                site_id,
            )
    
    def _handle_undo_redo_recalculation(self, operation: str, audit_entries: List[Dict]) -> None:
        """
        Callback for undo/redo operations to trigger recalculations (Issue #92).
        
        After undo/redo modifies purchases, redemptions, or game_sessions,
        we need to trigger the same recalculation logic that normal CRUD operations use.
        
        Args:
            operation: 'undo' or 'redo'
            audit_entries: List of audit log entries that were reversed/replayed
        """
        import json
        from datetime import datetime

        def _parse_json(value):
            if not value:
                return None
            try:
                return json.loads(value) if isinstance(value, str) else value
            except (json.JSONDecodeError, TypeError):
                return None
        
        # Group affected records by (user_id, site_id)
        affected_pairs = {}  # (user_id, site_id) -> earliest (date, time)
        affected_redemptions = set()
        
        for entry in audit_entries:
            table_name = entry.get('table_name')
            
            # Only recalculate for tables that affect accounting
            if table_name not in ('purchases', 'redemptions', 'game_sessions', 'account_adjustments'):
                continue
            
            # Parse the data to get user_id, site_id, date, time
            # For UPDATE: use old_data (what it was before undo) or new_data (what it became after undo)
            # For CREATE/DELETE: use whatever data is available
            data_json = entry.get('old_data') or entry.get('new_data')
            if not data_json:
                continue
            
            data = _parse_json(data_json)
            if data is None:
                continue
            
            user_id = data.get('user_id')
            site_id = data.get('site_id')
            
            if not user_id or not site_id:
                continue

            if table_name == 'redemptions' and entry.get('record_id') is not None:
                old_snapshot = _parse_json(entry.get('old_data')) or {}
                new_snapshot = _parse_json(entry.get('new_data')) or {}
                statuses = {
                    old_snapshot.get('status'),
                    new_snapshot.get('status'),
                }
                if statuses & {'CANCELED', 'PENDING_CANCEL'}:
                    affected_redemptions.add(int(entry['record_id']))
            
            # Get date/time based on table
            if table_name == 'purchases':
                date_str = data.get('purchase_date')
                time_str = data.get('purchase_time', '00:00:00')
            elif table_name == 'redemptions':
                date_str = data.get('redemption_date')
                time_str = data.get('redemption_time', '00:00:00')
            elif table_name == 'game_sessions':
                date_str = data.get('session_date')
                time_str = data.get('session_time', '00:00:00')
            elif table_name == 'account_adjustments':
                date_str = data.get('effective_date')
                time_str = data.get('effective_time', '00:00:00')
            else:
                continue
            
            if not date_str:
                continue
            
            # Parse date
            try:
                if isinstance(date_str, str):
                    record_date = datetime.fromisoformat(date_str).date()
                else:
                    record_date = date_str
            except (ValueError, AttributeError):
                continue
            
            # Track earliest date/time per pair
            pair = (user_id, site_id)
            time_normalized = self._normalize_time(time_str)
            
            if pair not in affected_pairs:
                affected_pairs[pair] = (record_date, time_normalized)
            else:
                current_date, current_time = affected_pairs[pair]
                if (record_date, time_normalized) < (current_date, current_time):
                    affected_pairs[pair] = (record_date, time_normalized)
        
        for redemption_id in sorted(affected_redemptions):
            redemption = self.redemption_repo.get_by_id(redemption_id)
            if redemption is None:
                continue
            has_active = (
                self.game_session_service.get_active_session(redemption.user_id, redemption.site_id)
                is not None
            )
            self.redemption_service.reconcile_post_undo_redo(redemption_id, has_active)

        # Trigger recalculation for each affected pair
        for (user_id, site_id), (boundary_date, boundary_time) in affected_pairs.items():
            # Use containing boundary logic to find actual rebuild point
            boundary_date, boundary_time = self._containing_boundary(
                site_id, user_id, boundary_date, boundary_time
            )
            
            # Trigger rebuild or mark stale
            self._rebuild_or_mark_stale(
                user_id=user_id,
                site_id=site_id,
                boundary_date=boundary_date,
                boundary_time=boundary_time,
                reason=f"{operation} operation"
            )
    
    # ==========================================================================
    # User Operations
    # ==========================================================================
    
    def get_all_users(self, active_only: bool = False) -> List[User]:
        """Get all users, optionally filtered by active status."""
        users = self.user_service.list_all_users()
        if active_only:
            return [u for u in users if u.is_active]
        return users
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.user_service.get_user(user_id)
    
    def get_user_by_name(self, name: str) -> Optional[User]:
        """Get user by name."""
        users = [u for u in self.user_service.list_all_users() if u.name == name]
        return users[0] if users else None
    
    def create_user(self, name: str, email: Optional[str] = None, 
                    notes: Optional[str] = None) -> User:
        """Create new user."""
        return self.user_service.create_user(name=name, email=email, notes=notes)
    
    def update_user(self, user_id: int, **kwargs) -> User:
        """Update user."""
        return self.user_service.update_user(user_id, **kwargs)
    
    def delete_user(self, user_id: int) -> None:
        """Delete user."""
        self.user_service.delete_user(user_id)
    
    # ==========================================================================
    # Site Operations
    # ==========================================================================
    
    def get_all_sites(self, active_only: bool = False) -> List[Site]:
        """Get all sites, optionally filtered by active status."""
        sites = self.site_service.list_all_sites()
        if active_only:
            return [s for s in sites if s.is_active]
        return sites
    
    def get_site(self, site_id: int) -> Optional[Site]:
        """Get site by ID."""
        return self.site_service.get_site(site_id)
    
    def get_site_by_name(self, name: str) -> Optional[Site]:
        """Get site by name."""
        sites = [s for s in self.site_service.list_all_sites() if s.name == name]
        return sites[0] if sites else None
    
    def create_site(self, name: str, url: Optional[str] = None,
                    sc_rate: float = 1.0, playthrough_requirement: float = 1.0,
                    notes: Optional[str] = None) -> Site:
        """Create new site."""
        return self.site_service.create_site(
            name=name,
            url=url,
            sc_rate=sc_rate,
            playthrough_requirement=playthrough_requirement,
            notes=notes
        )
    
    def update_site(self, site_id: int, **kwargs) -> Site:
        """Update site."""
        return self.site_service.update_site(site_id, **kwargs)
    
    def delete_site(self, site_id: int) -> None:
        """Delete site."""
        self.site_service.delete_site(site_id)
    
    # ==========================================================================
    # Card Operations
    # ==========================================================================
    
    def get_all_cards(self, active_only: bool = False, user_id: Optional[int] = None) -> List[Card]:
        """Get all cards, optionally filtered by active status and user."""
        if user_id:
            cards = self.card_service.list_user_cards(user_id)
        else:
            cards = self.card_service.list_all_cards()
        
        if active_only:
            return [c for c in cards if c.is_active]
        return cards

    def get_all_redemption_methods(self, active_only: bool = False) -> List[RedemptionMethod]:
        """Get all redemption methods, optionally filtered by active status."""
        if active_only:
            return self.redemption_method_service.list_active_methods()
        return self.redemption_method_service.list_all_methods()

    def get_redemption_method(self, method_id: int) -> Optional[RedemptionMethod]:
        """Get redemption method by ID."""
        return self.redemption_method_service.get_method(method_id)

    def create_redemption_method(self, name: str, method_type: Optional[str] = None,
                                 user_id: Optional[int] = None, notes: Optional[str] = None) -> RedemptionMethod:
        """Create redemption method."""
        return self.redemption_method_service.create_method(
            name=name,
            method_type=method_type,
            user_id=user_id,
            notes=notes
        )

    def update_redemption_method(self, method_id: int, **kwargs) -> RedemptionMethod:
        """Update redemption method."""
        return self.redemption_method_service.update_method(method_id, **kwargs)

    def delete_redemption_method(self, method_id: int) -> None:
        """Delete redemption method."""
        self.redemption_method_service.delete_method(method_id)

    def get_all_redemption_method_types(self, active_only: bool = False) -> List[RedemptionMethodType]:
        """Get all redemption method types, optionally filtered by active status."""
        if active_only:
            return self.redemption_method_type_service.list_active_types()
        return self.redemption_method_type_service.list_all_types()

    def get_redemption_method_type(self, type_id: int) -> Optional[RedemptionMethodType]:
        """Get redemption method type by ID."""
        return self.redemption_method_type_service.get_type(type_id)

    def create_redemption_method_type(self, name: str, notes: Optional[str] = None) -> RedemptionMethodType:
        """Create redemption method type."""
        return self.redemption_method_type_service.create_type(name=name, notes=notes)

    def update_redemption_method_type(self, type_id: int, **kwargs) -> RedemptionMethodType:
        """Update redemption method type."""
        return self.redemption_method_type_service.update_type(type_id, **kwargs)

    def delete_redemption_method_type(self, type_id: int) -> None:
        """Delete redemption method type."""
        self.redemption_method_type_service.delete_type(type_id)
    
    def get_card(self, card_id: int) -> Optional[Card]:
        """Get card by ID."""
        return self.card_service.get_card(card_id)
    
    def get_card_by_name(self, name: str) -> Optional[Card]:
        """Get card by name."""
        cards = [c for c in self.card_service.list_all_cards() if c.name == name]
        return cards[0] if cards else None
    
    def create_card(self, user_id: int, name: str, last_four: Optional[str] = None,
                    cashback_rate: float = 0.0, notes: Optional[str] = None) -> Card:
        """Create new card."""
        return self.card_service.create_card(
            user_id=user_id,
            name=name,
            last_four=last_four,
            cashback_rate=cashback_rate,
            notes=notes
        )
    
    def update_card(self, card_id: int, **kwargs) -> Card:
        """Update card."""
        return self.card_service.update_card(card_id, **kwargs)
    
    def delete_card(self, card_id: int) -> None:
        """Delete card."""
        self.card_service.delete_card(card_id)
    
    # ==========================================================================
    # Game Operations
    # ==========================================================================
    
    def list_all_games(self, game_type_id: Optional[int] = None, active_only: bool = False) -> List[Game]:
        """Get all games, optionally filtered by game type and active status."""
        if active_only:
            return self.game_service.list_active_games(game_type_id)
        return self.game_service.list_all_games(game_type_id)

    def get_all_game_types(self, active_only: bool = False) -> List[GameType]:
        """Get all game types, optionally filtered by active status."""
        types = self.game_type_service.list_all_types()
        if active_only:
            return [t for t in types if t.is_active]
        return types

    def get_game_type(self, type_id: int) -> Optional[GameType]:
        """Get game type by ID."""
        return self.game_type_service.get_type(type_id)

    def create_game_type(self, name: str, notes: Optional[str] = None) -> GameType:
        """Create new game type."""
        return self.game_type_service.create_type(name=name, notes=notes)

    def update_game_type(self, type_id: int, **kwargs) -> GameType:
        """Update game type."""
        return self.game_type_service.update_type(type_id, **kwargs)

    def delete_game_type(self, type_id: int) -> None:
        """Delete game type."""
        self.game_type_service.delete_type(type_id)

    def get_game(self, game_id: int) -> Optional[Game]:
        """Get game by ID."""
        return self.game_service.get_game(game_id)

    def create_game(self, name: str, game_type_id: int,
                    rtp: Optional[float] = None, notes: Optional[str] = None) -> Game:
        """Create new game."""
        return self.game_service.create_game(
            name=name,
            game_type_id=game_type_id,
            rtp=rtp,
            notes=notes
        )

    def update_game(self, game_id: int, **kwargs) -> Game:
        """Update game."""
        return self.game_service.update_game(game_id, **kwargs)

    def delete_game(self, game_id: int) -> None:
        """Delete game."""
        self.game_service.delete_game(game_id)
    
    # ==========================================================================
    # Purchase Operations
    # ==========================================================================
    
    def get_all_purchases(self, user_id: Optional[int] = None, 
                         site_id: Optional[int] = None,
                         start_date: Optional[date] = None,
                         end_date: Optional[date] = None) -> List[Purchase]:
        """Get all purchases, optionally filtered by user, site, and date range."""
        return self.purchase_service.list_purchases(
            user_id=user_id, 
            site_id=site_id,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_purchase(self, purchase_id: int) -> Optional[Purchase]:
        """Get purchase by ID."""
        return self.purchase_service.get_purchase(purchase_id)
    
    def create_purchase(self, user_id: int, site_id: int, amount: Decimal,
                       purchase_date: date,
                       sc_received: Decimal = Decimal("0.00"),
                       starting_sc_balance: Decimal = Decimal("0.00"),
                       cashback_earned: Decimal = Decimal("0.00"),
                       card_id: Optional[int] = None,
                       purchase_time: Optional[str] = None,
                       notes: Optional[str] = None) -> Purchase:
        """
        Create new purchase with atomic transaction and timestamp uniqueness.
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        with self.db.transaction():
            # Ensure timestamp uniqueness (silently auto-increment if needed)
            time_str = self._normalize_time(purchase_time)
            adjusted_date_str, adjusted_time_str, was_adjusted = self.timestamp_service.ensure_unique_timestamp(
                user_id=user_id,
                site_id=site_id,
                date_val=purchase_date,
                time_str=time_str,
                event_type="purchase"
            )
            
            # Convert string date back to date object if needed
            if isinstance(adjusted_date_str, str):
                from datetime import datetime as dt_module
                adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
            else:
                adjusted_date = adjusted_date_str
            
            purchase = self.purchase_service.create_purchase(
                user_id=user_id,
                site_id=site_id,
                amount=amount,
                sc_received=sc_received,
                starting_sc_balance=starting_sc_balance,
                cashback_earned=cashback_earned,
                purchase_date=adjusted_date,
                card_id=card_id,
                purchase_time=adjusted_time_str,
                notes=notes
            )
            boundary_date, boundary_time = self._containing_boundary(
                site_id,
                user_id,
                purchase.purchase_date,
                purchase.purchase_time,
            )
            self._rebuild_or_mark_stale(
                user_id,
                site_id,
                boundary_date,
                boundary_time,
                reason="purchase create"
            )
            return purchase
    
    def update_purchase(self, purchase_id: int, force_site_user_change: bool = False, **kwargs) -> Purchase:
        """
        Update purchase and trigger scoped rebuild when needed with atomic transaction.

        Legacy parity:
        - Allow editing consumed purchases, but protect amount/date unless a full rebuild is performed.
        - Allow site/user change only if explicitly forced (clears derived allocations via rebuild).
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        with self.db.transaction():
            old_purchase = self.purchase_repo.get_by_id(purchase_id)
            if not old_purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            
            # Ensure timestamp uniqueness if date/time is being changed
            was_adjusted = False
            if "purchase_date" in kwargs or "purchase_time" in kwargs:
                new_date = kwargs.get("purchase_date", old_purchase.purchase_date)
                new_time = kwargs.get("purchase_time", old_purchase.purchase_time)
                new_time_str = self._normalize_time(new_time)
                
                adjusted_date_str, adjusted_time_str, was_adjusted = self.timestamp_service.ensure_unique_timestamp(
                    user_id=old_purchase.user_id,
                    site_id=old_purchase.site_id,
                    date_val=new_date,
                    time_str=new_time_str,
                    exclude_id=purchase_id,
                    event_type="purchase"
                )
                
                # Convert string date back to date object
                if isinstance(adjusted_date_str, str):
                    from datetime import datetime as dt_module
                    adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
                else:
                    adjusted_date = adjusted_date_str
                
                kwargs["purchase_date"] = adjusted_date
                kwargs["purchase_time"] = adjusted_time_str

            updated = self.purchase_service.update_purchase(
                purchase_id,
                force_site_user_change=force_site_user_change,
                **kwargs,
            )

            # Determine whether this edit can affect derived data.
            # Notes-only edits should not trigger expensive rebuilds.
            derived_fields = {
                "user_id",
                "site_id",
                "amount",
                "purchase_date",
                "purchase_time",
                "sc_received",
                "starting_sc_balance",
                "cashback_earned",
                "card_id",
            }

            changed = False
            for field in derived_fields:
                if field in kwargs and getattr(old_purchase, field) != getattr(updated, field):
                    changed = True
                    break

            if changed:
                old_pair = (old_purchase.user_id, old_purchase.site_id)
                new_pair = (updated.user_id, updated.site_id)

                if old_pair == new_pair:
                    boundary_date, boundary_time = self._earliest_boundary_with_containing(
                        old_pair[1],
                        old_pair[0],
                        old_purchase.purchase_date,
                        old_purchase.purchase_time,
                        updated.purchase_date,
                        updated.purchase_time,
                    )
                    user_id, site_id = old_pair
                    self._rebuild_or_mark_stale(
                        user_id,
                        site_id,
                        boundary_date,
                        boundary_time,
                        reason="purchase edit"
                    )
                else:
                    # Cross-pair move: mark both pairs stale
                    old_date, old_time = self._containing_boundary(
                        old_pair[1],
                        old_pair[0],
                        old_purchase.purchase_date,
                        old_purchase.purchase_time,
                    )
                    self._rebuild_or_mark_stale(
                        old_pair[0],
                        old_pair[1],
                        old_date,
                        old_time,
                        reason="purchase moved (old pair)"
                    )

                    new_date, new_time = self._containing_boundary(
                        new_pair[1],
                        new_pair[0],
                        updated.purchase_date,
                        updated.purchase_time,
                    )
                    self._rebuild_or_mark_stale(
                        new_pair[0],
                        new_pair[1],
                        new_date,
                        new_time,
                        reason="purchase moved (new pair)"
                    )

            return updated

    def recalculate_everything(self) -> Dict[str, Any]:
        """Full legacy-style rebuild: FIFO allocations + realized + session P/L."""
        fifo_result = self.recalculation_service.rebuild_all()
        pairs = self.recalculation_service.iter_pairs()
        sessions_recalculated = 0

        # Rebuild explicit event links (legacy parity)
        try:
            self.game_session_event_link_service.rebuild_links_all()
        except Exception:
            pass

        for user_id, site_id in pairs:
            try:
                self.game_session_service.recalculate_closed_sessions_for_pair(user_id, site_id)
                sessions_recalculated += 1
            except Exception:
                # Keep going; individual pairs may lack sessions or have data issues.
                continue

        # Recalculate game RTP aggregates for all games
        games_recalculated = 0
        try:
            games = self.game_repo.get_all()
            for game in games:
                try:
                    self.game_session_service.recalculate_game_rtp_full(game.id)
                    games_recalculated += 1
                except Exception:
                    continue
        except Exception:
            pass

        return {
            "fifo": fifo_result,
            "pairs": len(pairs),
            "session_pairs_recalculated": sessions_recalculated,
            "games_rtp_recalculated": games_recalculated,
        }
    
    def get_basis_period_start_for_purchase(
        self, 
        user_id: int, 
        site_id: int, 
        purchase_date: date,
        purchase_time: Optional[str] = None
    ) -> Optional[tuple[date, str]]:
        """Get the start datetime of the purchase's basis period.

        Basis periods are bounded by the nearest "anchor" events before the purchase.
        Anchors include:
        - balance checkpoints (account_adjustments)
        - full redemptions (redemptions with more_remaining == False)

        Returns the later of (latest checkpoint <= purchase) and (latest full redemption < purchase).
        """
        try:
            anchor_time = purchase_time or "23:59:59"
            start_cp, _end_cp = self.adjustment_service.get_checkpoint_window_for_timestamp(
                user_id=int(user_id),
                site_id=int(site_id),
                anchor_date=purchase_date,
                anchor_time=anchor_time,
            )

            prev_full, _next_full = self.get_full_redemption_window_for_timestamp(
                user_id=int(user_id),
                site_id=int(site_id),
                anchor_date=purchase_date,
                anchor_time=anchor_time,
            )

            best: Optional[tuple[datetime, date, str]] = None

            if start_cp:
                cp_time = self._normalize_time(getattr(start_cp, "effective_time", None))
                cp_dt = self._to_dt(start_cp.effective_date, cp_time)
                best = (cp_dt, start_cp.effective_date, cp_time)

            if prev_full:
                red_date, red_time = prev_full
                red_dt = self._to_dt(red_date, red_time)
                if best is None or red_dt > best[0]:
                    best = (red_dt, red_date, red_time)

            if best is None:
                return None
            return (best[1], best[2])
        except Exception:
            return None
    
    def get_basis_period_purchases(
        self,
        user_id: int,
        site_id: int,
        purchase_date: date,
        purchase_time: Optional[str] = None,
        exclude_purchase_id: Optional[int] = None
    ) -> List[Purchase]:
        """Get purchases in the same basis period as a purchase.

        Basis periods are bounded by the nearest anchors around the reference timestamp.
        Anchors include:
        - balance checkpoints (account_adjustments)
        - full redemptions (redemptions with more_remaining == False)

        Bounds:
        - start boundary: later of (latest checkpoint <= anchor) and (latest full redemption < anchor)
        - end boundary:   earlier of (next checkpoint > anchor) and (next full redemption > anchor)

        When no end boundary exists, the list is capped at the anchor timestamp.
        """
        anchor_time = purchase_time or "23:59:59"

        prev_full, next_full = self.get_full_redemption_window_for_timestamp(
            user_id=int(user_id),
            site_id=int(site_id),
            anchor_date=purchase_date,
            anchor_time=anchor_time,
        )

        # Determine checkpoint window bounds.
        start_cp = None
        end_cp = None
        try:
            start_cp, end_cp = self.adjustment_service.get_checkpoint_window_for_timestamp(
                user_id=int(user_id),
                site_id=int(site_id),
                anchor_date=purchase_date,
                anchor_time=anchor_time,
            )
        except Exception:
            start_cp = None
            end_cp = None

        # Build start boundary (inclusive) from the later of checkpoint/redemption.
        start_dt: Optional[datetime] = None
        if start_cp is not None:
            try:
                cp_time = self._normalize_time(getattr(start_cp, "effective_time", None))
                start_dt = self._to_dt(start_cp.effective_date, cp_time)
            except Exception:
                start_dt = None
        if prev_full is not None:
            try:
                red_dt = self._to_dt(prev_full[0], prev_full[1])
                if start_dt is None or red_dt > start_dt:
                    start_dt = red_dt
            except Exception:
                pass

        # Build end boundary (exclusive) from the earlier of checkpoint/redemption.
        end_dt: Optional[datetime] = None
        if end_cp is not None:
            try:
                cp_time = self._normalize_time(getattr(end_cp, "effective_time", None))
                end_dt = self._to_dt(end_cp.effective_date, cp_time)
            except Exception:
                end_dt = None
        if next_full is not None:
            try:
                red_dt = self._to_dt(next_full[0], next_full[1])
                if end_dt is None or red_dt < end_dt:
                    end_dt = red_dt
            except Exception:
                pass

        # When there is no next anchor, cap at the reference purchase timestamp
        # so the "Related" view doesn’t include all future purchases.
        anchor_dt = self._to_dt(purchase_date, anchor_time)
        end_is_anchor = end_dt is None
        if end_dt is None:
            end_dt = anchor_dt

        # Get all purchases for this user+site.
        all_purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
        result: list[Purchase] = []
        for p in all_purchases:
            if exclude_purchase_id and p.id == exclude_purchase_id:
                continue

            p_time = p.purchase_time or "00:00:00"
            try:
                p_dt = self._to_dt(p.purchase_date, p_time)
            except Exception:
                continue

            # Apply start bound: p >= start
            if start_dt is not None and p_dt < start_dt:
                continue

            # Apply end bound.
            # - With an end anchor: p < end (exclusive)
            # - With no end anchor: p <= anchor (inclusive)
            if end_is_anchor:
                if p_dt > end_dt:
                    continue
            else:
                if p_dt >= end_dt:
                    continue

            result.append(p)

        result.sort(key=lambda x: (x.purchase_date, x.purchase_time or "00:00:00", x.id))
        return result
    
    def compute_purchase_total_extra(
        self,
        purchase_id: int,
        entered_post_purchase_sc: Decimal,
        entered_sc_received: Decimal
    ) -> Decimal:
        """Compute the total_extra for a purchase given entered values.
        
        total_extra = actual_pre - expected_pre
        where:
          actual_pre = entered_post_purchase_sc - entered_sc_received
          expected_pre = from compute_expected_balances()
          
        Args:
            purchase_id: Purchase ID
            entered_post_purchase_sc: The post-purchase SC balance entered by user
            entered_sc_received: The SC received amount entered by user
            
        Returns:
            The total extra SC (quantized to 0.01)
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        purchase = self.purchase_repo.get_by_id(purchase_id)
        if not purchase:
            return Decimal("0.00")
        
        # Compute expected balances
        balances = self.report_service.compute_expected_balances(
            user_id=purchase.user_id,
            site_id=purchase.site_id
        )
        
        # Find expected_pre for this purchase
        expected_pre = Decimal("0.00")
        for item in balances:
            if item["event_type"] == "purchase" and item["purchase_id"] == purchase_id:
                expected_pre = item.get("expected_pre", Decimal("0.00"))
                break
        
        # Compute actual_pre from entered values
        actual_pre = entered_post_purchase_sc - entered_sc_received
        
        # Compute total_extra and quantize to 0.01
        total_extra = (actual_pre - expected_pre).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return total_extra

    def delete_purchase(self, purchase_id: int) -> None:
        """Delete purchase (prevents if consumed) with atomic transaction."""
        with self.db.transaction():
            purchase = self.purchase_repo.get_by_id(purchase_id)
            self.purchase_service.delete_purchase(purchase_id)
            if purchase:
                boundary_date, boundary_time = self._containing_boundary(
                    purchase.site_id,
                    purchase.user_id,
                    purchase.purchase_date,
                    purchase.purchase_time,
                )
                self._rebuild_or_mark_stale(
                    purchase.user_id,
                    purchase.site_id,
                    boundary_date,
                    boundary_time,
                    reason="purchase delete"
                )
    
    def get_available_purchases_for_fifo(self, user_id: int, site_id: int) -> List[Purchase]:
        """Get purchases available for FIFO allocation."""
        return self.purchase_service.get_available_for_allocation(user_id, site_id)
    
    # ==========================================================================
    # Redemption Operations
    # ==========================================================================
    
    def get_all_redemptions(self, user_id: Optional[int] = None,
                           site_id: Optional[int] = None,
                           start_date: Optional[date] = None,
                           end_date: Optional[date] = None) -> List[Redemption]:
        """Get all redemptions, optionally filtered."""
        return self.redemption_service.list_redemptions(
            user_id=user_id, 
            site_id=site_id,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_redemption(self, redemption_id: int) -> Optional[Redemption]:
        """Get redemption by ID."""
        return self.redemption_service.get_redemption(redemption_id)
    
    def create_redemption(self, user_id: int, site_id: int, amount: Decimal,
                         redemption_date: date, apply_fifo: bool = True,
                         redemption_method_id: Optional[int] = None,
                         redemption_time: Optional[str] = None,
                         receipt_date: Optional[date] = None,
                         processed: bool = False,
                         more_remaining: bool = False,
                         notes: Optional[str] = None,
                         fees: Decimal = Decimal("0.00")) -> Redemption:
        """
        Create new redemption with optional FIFO processing, using atomic transaction.
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        with self.db.transaction():
            # Ensure timestamp uniqueness
            time_str = self._normalize_time(redemption_time)
            adjusted_date_str, adjusted_time_str, was_adjusted = self.timestamp_service.ensure_unique_timestamp(
                user_id=user_id,
                site_id=site_id,
                date_val=redemption_date,
                time_str=time_str,
                event_type="redemption"
            )
            
            # Convert string date back to date object
            if isinstance(adjusted_date_str, str):
                from datetime import datetime as dt_module
                adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
            else:
                adjusted_date = adjusted_date_str
            
            redemption = self.redemption_service.create_redemption(
                user_id=user_id,
                site_id=site_id,
                amount=amount,
                fees=fees,
                redemption_date=adjusted_date,
                apply_fifo=apply_fifo,
                redemption_method_id=redemption_method_id,
                redemption_time=adjusted_time_str,
                receipt_date=receipt_date,
                processed=processed,
                more_remaining=more_remaining,
                notes=notes
            )
            boundary_date, boundary_time = self._containing_boundary(
                site_id,
                user_id,
                redemption.redemption_date,
                redemption.redemption_time,
            )
            if apply_fifo:
                self._rebuild_or_mark_stale(

                    user_id,

                    site_id,

                    boundary_date,

                    boundary_time,

                    reason="data edit"

                )
            return redemption

    def update_redemption_reprocess(self, redemption_id: int, **kwargs) -> Redemption:
        """
        Update redemption and fully reprocess FIFO/realized/session cascades (legacy parity).
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        old_redemption = self.redemption_repo.get_by_id(redemption_id)
        if not old_redemption:
            raise ValueError(f"Redemption {redemption_id} not found")
        if getattr(old_redemption, 'status', 'PENDING') != 'PENDING':
            raise ValueError("Only PENDING redemptions can be edited through accounting reprocess.")
        old_data = asdict(old_redemption)

        # Ensure timestamp uniqueness if date/time is being changed
        was_adjusted = False
        if "redemption_date" in kwargs or "redemption_time" in kwargs:
            new_date = kwargs.get("redemption_date", old_redemption.redemption_date)
            new_time = kwargs.get("redemption_time", old_redemption.redemption_time)
            new_time_str = self._normalize_time(new_time)
            
            adjusted_date_str, adjusted_time_str, was_adjusted = self.timestamp_service.ensure_unique_timestamp(
                user_id=old_redemption.user_id,
                site_id=old_redemption.site_id,
                date_val=new_date,
                time_str=new_time_str,
                exclude_id=redemption_id,
                event_type="redemption"
            )
            
            # Convert string date back to date object
            if isinstance(adjusted_date_str, str):
                from datetime import datetime as dt_module
                adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
            else:
                adjusted_date = adjusted_date_str
            
            kwargs["redemption_date"] = adjusted_date
            kwargs["redemption_time"] = adjusted_time_str

        updated = Redemption(
            id=old_redemption.id,
            user_id=kwargs.get("user_id", old_redemption.user_id),
            site_id=kwargs.get("site_id", old_redemption.site_id),
            amount=kwargs.get("amount", old_redemption.amount),
            fees=kwargs.get("fees", old_redemption.fees),
            redemption_date=kwargs.get("redemption_date", old_redemption.redemption_date),
            redemption_time=kwargs.get("redemption_time", old_redemption.redemption_time),
            redemption_entry_time_zone=kwargs.get("redemption_entry_time_zone", old_redemption.redemption_entry_time_zone),
            redemption_method_id=kwargs.get("redemption_method_id", old_redemption.redemption_method_id),
            receipt_date=kwargs.get("receipt_date", old_redemption.receipt_date),
            processed=kwargs.get("processed", old_redemption.processed),
            more_remaining=kwargs.get("more_remaining", old_redemption.more_remaining),
            is_free_sc=kwargs.get("is_free_sc", old_redemption.is_free_sc),
            notes=kwargs.get("notes", old_redemption.notes),
            cost_basis=old_redemption.cost_basis,
            taxable_profit=old_redemption.taxable_profit,
            status=old_redemption.status,
            canceled_at=old_redemption.canceled_at,
            cancel_reason=old_redemption.cancel_reason,
        )
        updated.__post_init__()

        group_id = self.audit_service.generate_group_id() if hasattr(self, "audit_service") else None
        with self.db.transaction():
            self.redemption_repo.update(updated)
            if group_id and hasattr(self, "audit_service"):
                self.audit_service.log_update(
                    "redemptions",
                    updated.id,
                    old_data,
                    asdict(updated),
                    group_id=group_id,
                    auto_commit=False,
                )

        if group_id and hasattr(self, "undo_redo_service"):
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=f"Reprocess redemption #{updated.id}",
                timestamp=datetime.now().isoformat(),
            )

        old_pair = (old_redemption.user_id, old_redemption.site_id)
        new_pair = (updated.user_id, updated.site_id)

        if old_pair == new_pair:
            boundary_date, boundary_time = self._earliest_boundary_with_containing(
                old_pair[1],
                old_pair[0],
                old_redemption.redemption_date,
                old_redemption.redemption_time,
                updated.redemption_date,
                updated.redemption_time,
            )
            self._rebuild_or_mark_stale(

                old_pair[0],

                old_pair[1],

                boundary_date,

                boundary_time,

                reason="data edit"

            )
        else:
            old_date, old_time = self._containing_boundary(
                old_pair[1],
                old_pair[0],
                old_redemption.redemption_date,
                old_redemption.redemption_time,
            )
            self._rebuild_or_mark_stale(

                old_pair[0],

                old_pair[1],

                old_date,

                old_time,

                reason="data edit"

            )

            new_date, new_time = self._containing_boundary(
                new_pair[1],
                new_pair[0],
                updated.redemption_date,
                updated.redemption_time,
            )
            self._rebuild_or_mark_stale(

                new_pair[0],

                new_pair[1],

                new_date,

                new_time,

                reason="data edit"

            )

        return self.redemption_repo.get_by_id(redemption_id)
    
    def update_redemption(self, redemption_id: int, **kwargs) -> Redemption:
        """Update redemption (with FIFO allocation protection)."""
        old_redemption = self.redemption_repo.get_by_id(redemption_id)
        updated = self.redemption_service.update_redemption(redemption_id, **kwargs)
        if old_redemption:
            derived_fields = {
                "user_id",
                "site_id",
                "amount",
                "redemption_date",
                "redemption_time",
                "is_free_sc",
                "notes",
            }
            changed = False
            for field in derived_fields:
                if field in kwargs and getattr(old_redemption, field) != getattr(updated, field):
                    changed = True
                    break
            if changed:
                old_pair = (old_redemption.user_id, old_redemption.site_id)
                new_pair = (updated.user_id, updated.site_id)

                if old_pair == new_pair:
                    boundary_date, boundary_time = self._earliest_boundary_with_containing(
                        old_pair[1],
                        old_pair[0],
                        old_redemption.redemption_date,
                        old_redemption.redemption_time,
                        updated.redemption_date,
                        updated.redemption_time,
                    )
                    self._rebuild_or_mark_stale(

                        old_pair[0],

                        old_pair[1],

                        boundary_date,

                        boundary_time,

                        reason="data edit"

                    )
                else:
                    old_date, old_time = self._containing_boundary(
                        old_pair[1],
                        old_pair[0],
                        old_redemption.redemption_date,
                        old_redemption.redemption_time,
                    )
                    self._rebuild_or_mark_stale(

                        old_pair[0],

                        old_pair[1],

                        old_date,

                        old_time,

                        reason="data edit"

                    )

                    new_date, new_time = self._containing_boundary(
                        new_pair[1],
                        new_pair[0],
                        updated.redemption_date,
                        updated.redemption_time,
                    )
                    self._rebuild_or_mark_stale(

                        new_pair[0],

                        new_pair[1],

                        new_date,

                        new_time,

                        reason="data edit"

                    )
            else:
                self.game_session_event_link_service.rebuild_links_for_pair(
                    updated.site_id,
                    updated.user_id,
                )
        else:
            self.game_session_event_link_service.rebuild_links_for_pair(
                updated.site_id,
                updated.user_id,
            )
        return updated

    def bulk_update_redemption_metadata(
        self,
        redemption_ids: List[int],
        *,
        receipt_date: Optional[date] = ...,  # type: ignore[assignment]
        processed: Optional[bool] = ...,     # type: ignore[assignment]
    ) -> int:
        """Update receipt_date and/or processed flag for multiple redemptions in one transaction.

        This is a pure metadata update — no FIFO rebuild, no session recalculation,
        no game_session_event_link rebuild.  Only receipt_date and processed fields
        are allowed.

        Args:
            redemption_ids: List of redemption IDs to update.
            receipt_date: If provided (including None), sets receipt_date for all rows.
                          Pass the sentinel Ellipsis (default) to leave the field unchanged.
            processed: If provided (True/False), sets processed for all rows.
                       Pass the sentinel Ellipsis (default) to leave the field unchanged.

        Returns:
            Number of rows updated.
        """
        _UNSET = ...  # sentinel

        if not redemption_ids:
            return 0

        # Guard (Issue #148): exclude CANCELED (and PENDING_CANCEL) rows from bulk
        # metadata updates — receipt_date must not be set on a canceled redemption.
        eligible_ids = []
        for rid in redemption_ids:
            r = self.redemption_repo.get_by_id(rid)
            if r is not None and getattr(r, 'status', 'PENDING') == 'PENDING':
                eligible_ids.append(rid)
        redemption_ids = eligible_ids

        if not redemption_ids:
            return 0

        set_receipt = receipt_date is not _UNSET
        set_processed = processed is not _UNSET

        if not set_receipt and not set_processed:
            return 0

        # Build human-readable description for the undo stack
        n = len(redemption_ids)
        noun = "redemption" if n == 1 else "redemptions"
        if set_receipt and set_processed:
            _description = f"Bulk update {n} {noun} (receipt date + processed)"
        elif set_receipt:
            if receipt_date is None:
                _description = f"Bulk clear receipt date for {n} {noun}"
            else:
                _description = f"Bulk mark {n} {noun} received"
        else:
            _description = f"Bulk mark {n} {noun} processed"

        # Snapshot old state for each record BEFORE the SQL update.
        # Skip IDs that no longer exist so we only audit rows we actually touch.
        old_snapshots: Dict[int, Dict[str, Any]] = {}
        for rid in redemption_ids:
            r = self.redemption_repo.get_by_id(rid)
            if r is not None:
                old_snapshots[rid] = asdict(r)

        # Generate one group_id shared across all rows in this bulk op
        group_id = self.audit_service.generate_group_id() if hasattr(self, "audit_service") else None

        with self.db.transaction():
            placeholders = ",".join("?" * len(redemption_ids))

            if set_receipt and set_processed:
                receipt_val = receipt_date.isoformat() if receipt_date is not None else None
                processed_val = 1 if processed else 0
                query = (
                    f"UPDATE redemptions SET receipt_date = ?, processed = ?, "
                    f"updated_at = CURRENT_TIMESTAMP "
                    f"WHERE id IN ({placeholders}) AND deleted_at IS NULL"
                )
                params = [receipt_val, processed_val, *redemption_ids]
            elif set_receipt:
                receipt_val = receipt_date.isoformat() if receipt_date is not None else None
                query = (
                    f"UPDATE redemptions SET receipt_date = ?, "
                    f"updated_at = CURRENT_TIMESTAMP "
                    f"WHERE id IN ({placeholders}) AND deleted_at IS NULL"
                )
                params = [receipt_val, *redemption_ids]
            else:
                processed_val = 1 if processed else 0
                query = (
                    f"UPDATE redemptions SET processed = ?, "
                    f"updated_at = CURRENT_TIMESTAMP "
                    f"WHERE id IN ({placeholders}) AND deleted_at IS NULL"
                )
                params = [processed_val, *redemption_ids]

            self.db.execute(query, tuple(params))

            # Log one audit UPDATE entry per affected row (all share the same group_id)
            if group_id and hasattr(self, "audit_service"):
                for rid, old_data in old_snapshots.items():
                    new_data = dict(old_data)
                    if set_receipt:
                        new_data["receipt_date"] = receipt_date
                    if set_processed:
                        new_data["processed"] = processed
                    self.audit_service.log_update(
                        "redemptions",
                        rid,
                        old_data,
                        new_data,
                        group_id=group_id,
                        auto_commit=False,
                    )

        # Push one undoable operation onto the undo stack (covers all rows)
        if group_id and hasattr(self, "undo_redo_service"):
            self.undo_redo_service.push_operation(
                group_id=group_id,
                description=_description,
                timestamp=datetime.now().isoformat(),
            )

        # Dismiss pending-receipt notifications for any rows that now have a receipt_date
        if set_receipt and receipt_date is not None:
            if hasattr(self, "notification_rules_service"):
                for rid in redemption_ids:
                    self.notification_rules_service.on_redemption_received(rid)

        return len(redemption_ids)

    def delete_redemption(self, redemption_id: int) -> None:
        """Delete redemption (reverses FIFO if allocated)."""
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if redemption and redemption.amount == 0 and (redemption.notes or "").startswith("Balance Closed"):
            self.db.execute(
                """
                UPDATE purchases
                SET status = 'active', updated_at = CURRENT_TIMESTAMP
                WHERE site_id = ? AND user_id = ? AND remaining_amount > 0
                  AND status = 'dormant'
                """,
                (redemption.site_id, redemption.user_id),
            )
        self.redemption_service.delete_redemption(redemption_id)
        if redemption:
            boundary_date, boundary_time = self._containing_boundary(
                redemption.site_id,
                redemption.user_id,
                redemption.redemption_date,
                redemption.redemption_time,
            )
            self._rebuild_or_mark_stale(

                redemption.user_id,

                redemption.site_id,

                boundary_date,

                boundary_time,

                reason="redemption delete"

            )
    
    def delete_redemptions_bulk(self, redemption_ids: List[int]) -> None:
        """Delete multiple redemptions efficiently in a batch.
        
        Args:
            redemption_ids: List of redemption IDs to delete
        """
        if not redemption_ids:
            return
        
        # Collect affected pairs for recalculation
        affected_pairs = set()
        redemptions_data = []
        
        for redemption_id in redemption_ids:
            redemption = self.redemption_repo.get_by_id(redemption_id)
            if redemption:
                redemptions_data.append(redemption)
                affected_pairs.add((redemption.user_id, redemption.site_id))
        
        # Delete all redemptions in bulk
        self.redemption_service.delete_redemptions_bulk(redemption_ids)
        
        # Recalculate once per affected pair
        for user_id, site_id in affected_pairs:
            # Find earliest boundary date among deleted redemptions for this pair
            pair_redemptions = [r for r in redemptions_data if r.user_id == user_id and r.site_id == site_id]
            if pair_redemptions:
                earliest = min(pair_redemptions, key=lambda r: (r.redemption_date, r.redemption_time))
                boundary_date, boundary_time = self._containing_boundary(
                    site_id, user_id, earliest.redemption_date, earliest.redemption_time
                )
                self.recalculation_service.rebuild_fifo_for_pair_from(
                    user_id, site_id, boundary_date.isoformat(), boundary_time
                )
                self.game_session_service.recalculate_closed_sessions_for_pair_from(
                    user_id, site_id, boundary_date, boundary_time
                )
                self.game_session_event_link_service.rebuild_links_for_pair_from(
                    site_id,
                    user_id,
                    boundary_date.isoformat(),
                    boundary_time,
                )

    def cancel_redemption(
        self,
        redemption_id: int,
        reason: str = "",
    ) -> 'Redemption':
        """Cancel a pending redemption, reversing its FIFO allocation.

        If there is an active session for the same user/site, shows confirmation and
        defers the cancellation to PENDING_CANCEL until the session closes.

        Raises:
            ValueError: if the redemption cannot be canceled.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")

        has_active = (
            self.game_session_service.get_active_session(
                redemption.user_id, redemption.site_id
            )
            is not None
        )

        canceled = self.redemption_service.cancel_redemption(
            redemption_id,
            reason=reason,
            has_active_session=has_active,
            notification_service=self.notification_rules_service,
        )

        # Rebuild after both immediate cancels and queued PENDING_CANCEL transitions.
        # FIFO rebuilds preserve PENDING_CANCEL rows, while links/session totals
        # must stop counting them immediately.
        boundary_date, boundary_time = self._containing_boundary(
            redemption.site_id,
            redemption.user_id,
            redemption.redemption_date,
            redemption.redemption_time,
        )
        self._rebuild_or_mark_stale(
            redemption.user_id,
            redemption.site_id,
            boundary_date,
            boundary_time,
            reason="redemption cancel",
        )

        return canceled

    def uncancel_redemption(
        self,
        redemption_id: int,
    ) -> 'Redemption':
        """Uncancel a previously canceled redemption, re-applying FIFO.

        Raises:
            ValueError: if the redemption is not in CANCELED status.
        """
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if not redemption:
            raise ValueError(f"Redemption {redemption_id} not found")

        uncanceled = self.redemption_service.uncancel_redemption(
            redemption_id,
            restore_fifo=False,
        )

        # Trigger FIFO + session recalculation from the original redemption timestamp
        boundary_date, boundary_time = self._containing_boundary(
            redemption.site_id,
            redemption.user_id,
            redemption.redemption_date,
            redemption.redemption_time,
        )
        self._rebuild_or_mark_stale(
            redemption.user_id,
            redemption.site_id,
            boundary_date,
            boundary_time,
            reason="redemption uncancel",
        )

        refreshed = self.redemption_repo.get_by_id(redemption_id)
        return refreshed or uncanceled

    # ==========================================================================
    # Game Session Operations
    # ==========================================================================
    
    def get_all_game_sessions(self, user_id: Optional[int] = None,
                             site_id: Optional[int] = None,
                             status: Optional[str] = None) -> List[GameSession]:
        """Get all game sessions, optionally filtered by user, site, and/or status."""
        return self.game_session_service.list_sessions(user_id=user_id, site_id=site_id, status=status)

    # ==========================================================================
    # Daily Sessions Operations
    # ==========================================================================

    def get_daily_sessions_rows(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        selected_users: Optional[List[str]] = None,
        selected_sites: Optional[List[str]] = None,
    ) -> List[Dict]:
        return self.daily_sessions_service.fetch_sessions(
            selected_users=selected_users or [],
            selected_sites=selected_sites or [],
            active_date_filter=(start_date, end_date),
        )

    def get_daily_note_for_date(self, session_date: str) -> str:
        return self.daily_sessions_service.get_note_for_date(session_date)

    def set_daily_note_for_date(self, session_date: str, user_ids: List[int], notes: str) -> None:
        self.daily_sessions_service.set_notes_for_date(session_date, user_ids, notes)

    def get_active_game_session(self, user_id: int, site_id: int) -> Optional[GameSession]:
        """Get active game session for a user/site, if any."""
        return self.game_session_service.get_active_session(user_id, site_id)

    def compute_expected_balances(self, user_id: int, site_id: int,
                                 session_date: date, session_time: str,
                                 exclude_purchase_id: Optional[int] = None,
                                 entry_time_zone: Optional[str] = None) -> Tuple[Decimal, Decimal]:
        """Compute expected starting balances for a new session.
        
        Args:
            exclude_purchase_id: Optional purchase ID to exclude from the calculation.
                Used when editing a purchase to avoid including it in its own expected balance.
        """
        return self.game_session_service.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=session_date,
            session_time=session_time,
            exclude_purchase_id=exclude_purchase_id,
            entry_time_zone=entry_time_zone,
        )
    
    def get_game_session(self, session_id: int) -> Optional[GameSession]:
        """Get game session by ID."""
        return self.game_session_service.get_session(session_id)
    
    def create_game_session(self, user_id: int, site_id: int, game_id: Optional[int],
                           session_date: date, 
                           starting_balance: Decimal,
                           ending_balance: Decimal,
                           starting_redeemable: Decimal = Decimal("0"),
                           ending_redeemable: Decimal = Decimal("0"),
                           purchases_during: Decimal = Decimal("0"),
                           redemptions_during: Decimal = Decimal("0"),
                           session_time: Optional[str] = None,
                           notes: Optional[str] = None,
                           calculate_pl: bool = True,
                           game_type_id: Optional[int] = None) -> GameSession:
        """
        Create new game session with automatic P/L calculation and timestamp uniqueness.
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        # Ensure start timestamp uniqueness
        time_str = self._normalize_time(session_time)
        adjusted_date_str, adjusted_time_str, was_adjusted = self.timestamp_service.ensure_unique_timestamp(
            user_id=user_id,
            site_id=site_id,
            date_val=session_date,
            time_str=time_str,
            event_type="session_start"
        )
        
        # Convert string date back to date object
        if isinstance(adjusted_date_str, str):
            from datetime import datetime as dt_module
            adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
        else:
            adjusted_date = adjusted_date_str
        
        session = self.game_session_service.create_session(
            user_id=user_id,
            site_id=site_id,
            game_id=game_id,
            game_type_id=game_type_id,
            session_date=adjusted_date,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            starting_redeemable=starting_redeemable,
            ending_redeemable=ending_redeemable,
            purchases_during=purchases_during,
            redemptions_during=redemptions_during,
            session_time=adjusted_time_str,
            notes=notes or "",
            calculate_pl=calculate_pl
        )
        boundary_date, boundary_time = self._containing_boundary(
            site_id,
            user_id,
            session.session_date,
            session.session_time,
        )
        # Full recalculation: FIFO + Event Links + Session P/L
        self._rebuild_or_mark_stale(
            user_id,
            site_id,
            boundary_date,
            boundary_time,
            reason="session create"
        )
        return session
    
    def update_game_session(self, session_id: int, recalculate_pl: bool = True, 
                           **kwargs) -> GameSession:
        """
        Update game session with optional P/L recalculation and timestamp uniqueness.
        
        Note: Timestamps are automatically adjusted if conflicts exist (auto-incremented by 1s).
        """
        old_session = self.game_session_repo.get_by_id(session_id)
        
        # Ensure timestamp uniqueness for session_time (start)
        start_adjusted = False
        if "session_time" in kwargs or "session_date" in kwargs:
            new_date = kwargs.get("session_date", old_session.session_date if old_session else None)
            new_time = kwargs.get("session_time", old_session.session_time if old_session else None)
            if new_date and new_time:
                new_time_str = self._normalize_time(new_time)
                adjusted_date_str, adjusted_time_str, start_adjusted = self.timestamp_service.ensure_unique_timestamp(
                    user_id=old_session.user_id,
                    site_id=old_session.site_id,
                    date_val=new_date,
                    time_str=new_time_str,
                    exclude_id=session_id,
                    event_type="session_start"
                )
                # Convert string date back to date object
                if isinstance(adjusted_date_str, str):
                    from datetime import datetime as dt_module
                    adjusted_date = dt_module.strptime(adjusted_date_str, "%Y-%m-%d").date()
                else:
                    adjusted_date = adjusted_date_str
                kwargs["session_date"] = adjusted_date
                kwargs["session_time"] = adjusted_time_str
        
        # Ensure timestamp uniqueness for end_time
        end_adjusted = False
        if "end_time" in kwargs or "end_date" in kwargs:
            new_end_date = kwargs.get("end_date", old_session.end_date if old_session else None)
            new_end_time = kwargs.get("end_time", old_session.end_time if old_session else None)
            if new_end_date and new_end_time:
                new_end_time_str = self._normalize_time(new_end_time)
                adjusted_end_date_str, adjusted_end_time_str, end_adjusted = self.timestamp_service.ensure_unique_timestamp(
                    user_id=old_session.user_id,
                    site_id=old_session.site_id,
                    date_val=new_end_date,
                    time_str=new_end_time_str,
                    exclude_id=session_id,
                    event_type="session_end"
                )
                # Convert string date back to date object
                if isinstance(adjusted_end_date_str, str):
                    from datetime import datetime as dt_module
                    adjusted_end_date = dt_module.strptime(adjusted_end_date_str, "%Y-%m-%d").date()
                else:
                    adjusted_end_date = adjusted_end_date_str
                kwargs["end_date"] = adjusted_end_date
                kwargs["end_time"] = adjusted_end_time_str
        
        updated = self.game_session_service.update_session(
            session_id, 
            recalculate_pl=recalculate_pl, 
            **kwargs
        )
        if old_session:
            old_pair = (old_session.user_id, old_session.site_id)
            new_pair = (updated.user_id, updated.site_id)
            if old_pair == new_pair:
                boundary_date, boundary_time = self._earliest_boundary_with_containing(
                    old_pair[1],
                    old_pair[0],
                    old_session.session_date,
                    old_session.session_time,
                    updated.session_date,
                    updated.session_time,
                )
                # Full recalculation: FIFO + Event Links + Session P/L
                self._rebuild_or_mark_stale(
                    new_pair[0],
                    new_pair[1],
                    boundary_date,
                    boundary_time,
                    reason="session update"
                )
            else:
                old_date, old_time = self._containing_boundary(
                    old_pair[1],
                    old_pair[0],
                    old_session.session_date,
                    old_session.session_time,
                )
                # Full recalculation for old pair: FIFO + Event Links + Session P/L
                self._rebuild_or_mark_stale(
                    old_pair[0],
                    old_pair[1],
                    old_date,
                    old_time,
                    reason="session update (old pair)"
                )
                new_date, new_time = self._containing_boundary(
                    new_pair[1],
                    new_pair[0],
                    updated.session_date,
                    updated.session_time,
                )
                # Full recalculation for new pair: FIFO + Event Links + Session P/L
                self._rebuild_or_mark_stale(
                    new_pair[0],
                    new_pair[1],
                    new_date,
                    new_time,
                    reason="session update (new pair)"
                )
        else:
            boundary_date, boundary_time = self._containing_boundary(
                updated.site_id,
                updated.user_id,
                updated.session_date,
                updated.session_time,
            )
            # Full recalculation: FIFO + Event Links + Session P/L
            self._rebuild_or_mark_stale(
                updated.user_id,
                updated.site_id,
                boundary_date,
                boundary_time,
                reason="session update"
            )
        return updated
    
    def delete_game_session(self, session_id: int) -> None:
        """Delete game session."""
        session = self.game_session_repo.get_by_id(session_id)
        self.game_session_service.delete_session(session_id)
        if session:
            boundary_date, boundary_time = self._containing_boundary(
                session.site_id,
                session.user_id,
                session.session_date,
                session.session_time,
            )
            # Full recalculation: FIFO + Event Links + Session P/L
            self._rebuild_or_mark_stale(
                session.user_id,
                session.site_id,
                boundary_date,
                boundary_time
            )

    def delete_game_sessions_bulk(self, session_ids: List[int]) -> None:
        """Delete multiple game sessions efficiently."""
        if not session_ids:
            return
        
        # Fetch all sessions first to track affected pairs
        sessions = [self.game_session_repo.get_by_id(sid) for sid in session_ids if sid]
        
        # Group by (site, user) for rebuild
        affected_pairs = set()
        earliest_dates = {}
        for session in sessions:
            if session:
                pair = (session.site_id, session.user_id)
                affected_pairs.add(pair)
                current = earliest_dates.get(pair)
                if current is None or (session.session_date, session.session_time) < current:
                    earliest_dates[pair] = (session.session_date, session.session_time)
        
        # Bulk delete
        self.game_session_service.delete_sessions_bulk(session_ids)
        
        # Full recalculation once per affected pair: FIFO + Event Links + Session P/L
        for site_id, user_id in affected_pairs:
            date, time = earliest_dates[(site_id, user_id)]
            boundary_date, boundary_time = self._containing_boundary(site_id, user_id, date, time)
            self._rebuild_or_mark_stale(user_id, site_id, boundary_date, boundary_time)

    def recalculate_game_rtp(self, game_id: int) -> None:
        """Recalculate RTP aggregates for a game (full rebuild)."""
        self.game_session_service.recalculate_game_rtp_full(game_id)

    def get_game_filtered_stats(
        self,
        game_id: int,
        user_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Get game stats constrained by optional user/date filters."""
        return self.game_session_service.get_game_filtered_stats(
            game_id=game_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )

    def get_linked_sessions_for_purchase(self, purchase_id: int):
        sessions = self.game_session_event_link_service.get_sessions_for_purchase(purchase_id)
        if sessions:
            return sessions
        purchase = self.purchase_repo.get_by_id(purchase_id)
        if purchase:
            self.game_session_event_link_service.rebuild_links_for_pair(purchase.site_id, purchase.user_id)
            return self.game_session_event_link_service.get_sessions_for_purchase(purchase_id)
        return sessions

    def get_linked_sessions_for_redemption(self, redemption_id: int):
        sessions = self.game_session_event_link_service.get_sessions_for_redemption(redemption_id)
        if sessions:
            return sessions
        redemption = self.redemption_repo.get_by_id(redemption_id)
        if redemption:
            self.game_session_event_link_service.rebuild_links_for_pair(redemption.site_id, redemption.user_id)
            return self.game_session_event_link_service.get_sessions_for_redemption(redemption_id)
        return sessions

    def get_linked_events_for_session(self, session_id: int):
        events = self.game_session_event_link_service.get_events_for_session(session_id)
        # Fast-return only when purchases are already populated.
        # Do NOT short-circuit on a lone redemption link: a AFTER redemption can exist
        # while the BEFORE purchase link is silently absent (Issue #152, Bug B).
        if events.get("purchases"):
            return events
        session = self.game_session_repo.get_by_id(session_id)
        if session:
            self.game_session_event_link_service.rebuild_links_for_pair(session.site_id, session.user_id)
            return self.game_session_event_link_service.get_events_for_session(session_id)
        return events

    def link_purchase_to_session(self, purchase_id: int, session_id: int, relation: str = "MANUAL") -> None:
        """Create an explicit link between a purchase and a session.
        
        Args:
            purchase_id: ID of the purchase to link
            session_id: ID of the session to link to
            relation: Link relation type (default: MANUAL for explicit user action)
        """
        conn = self.db._connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO game_session_event_links
                (game_session_id, event_type, event_id, relation)
            VALUES (?, 'purchase', ?, ?)
            """,
            (session_id, purchase_id, relation),
        )
        conn.commit()

    def get_redemptions_allocated_to_purchase(self, purchase_id: int):
        rows = self.db.fetch_all(
            """
            SELECT r.*, rm.name as method_name, rm.method_type as method_type
            FROM redemption_allocations ra
            JOIN redemptions r ON r.id = ra.redemption_id
            LEFT JOIN redemption_methods rm ON r.redemption_method_id = rm.id
            WHERE ra.purchase_id = ?
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time, '00:00:00') ASC, r.id ASC
            """,
            (purchase_id,),
        )
        return [self.redemption_repo._row_to_model(row) for row in rows]
    
    def recalculate_all_sessions(self, user_id: Optional[int] = None,
                                site_id: Optional[int] = None) -> int:
        """Recalculate P/L for all sessions."""
        return self.game_session_service.recalculate_all_sessions(
            user_id=user_id, 
            site_id=site_id
        )
    
    # ==========================================================================
    # Reporting Operations
    # ==========================================================================
    
    def get_user_summary(self, user_id: int, site_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of user's activity across purchases, redemptions, and sessions."""
        return self.report_service.get_user_summary(user_id, site_id)
    
    def get_site_summary(self, site_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get summary of site's activity."""
        return self.report_service.get_site_summary(site_id, user_id)
    
    def get_tax_report(self, user_id: int, site_id: int, 
                      start_date: Optional[date] = None,
                      end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get tax report with FIFO cost basis calculations."""
        return self.report_service.get_tax_report(user_id, site_id, start_date, end_date)
    
    def get_session_pl_report(self, user_id: Optional[int] = None,
                             site_id: Optional[int] = None,
                             start_date: Optional[date] = None,
                             end_date: Optional[date] = None) -> Dict[str, Any]:
        """Get session profit/loss analytics."""
        return self.report_service.get_session_profit_loss_report(
            user_id, site_id, start_date, end_date
        )
    
    # ==========================================================================
    # Validation Operations
    # ==========================================================================
    
    def validate_fifo_allocations(self, user_id: Optional[int] = None,
                                 site_id: Optional[int] = None) -> Dict[str, Any]:
        """Validate FIFO allocation integrity."""
        return self.validation_service.validate_fifo_allocations(user_id, site_id)
    
    def get_data_summary(self) -> Dict[str, int]:
        """Get counts of all records in system."""
        return self.validation_service.get_data_summary()

    # ==========================================================================
    # App Update Checks / Downloads (Issue #171)
    # ==========================================================================

    def check_for_app_updates(self, manifest_url: Optional[str] = None) -> Dict[str, Any]:
        if manifest_url:
            self.update_service.manifest_url = manifest_url
        return asdict(self.update_service.check_for_updates())

    def download_app_update(
        self,
        asset: Dict[str, Any],
        destination_dir: str,
    ) -> str:
        update_asset = UpdateAsset(
            platform=str(asset["platform"]),
            url=str(asset["url"]),
            sha256=str(asset["sha256"]),
            name=asset.get("name"),
            size=int(asset["size"]) if asset.get("size") is not None else None,
        )
        return self.update_service.download_and_verify(update_asset, destination_dir)
    
    # ==========================================================================
    # Unrealized Positions (Open Positions)
    # ==========================================================================
    
    def get_unrealized_positions(self, start_date: Optional[date] = None,
                                end_date: Optional[date] = None) -> List[UnrealizedPosition]:
        """
        Get all unrealized positions (sites with remaining purchase basis).
        Shows current SC balances and unrealized P/L (NOT taxable until closed).
        """
        return self.unrealized_position_repo.get_all_positions(start_date, end_date)

    def get_adjusted_site_user_pairs(self, include_deleted: bool = False) -> set[tuple[int, int]]:
        """Return (site_id, user_id) pairs that have adjustments/checkpoints.

        Used for quick-glance UI indicators ("Adjusted" badges) without running
        per-row queries.
        """
        query = """
            SELECT DISTINCT site_id, user_id
            FROM account_adjustments
        """
        params: tuple = ()
        if not include_deleted:
            query += " WHERE deleted_at IS NULL"
        rows = self.db.fetch_all(query, params)
        return {(int(r["site_id"]), int(r["user_id"])) for r in rows}
    
    def get_unrealized_position(self, site_id: int, user_id: int) -> Optional[UnrealizedPosition]:
        """Get specific unrealized position for a site/user pair."""
        return self.unrealized_position_repo.get_position_by_site_user(site_id, user_id)

    def get_low_balance_close_prompt_data(
        self,
        site_id: int,
        user_id: int,
        ending_total_sc: Decimal,
    ) -> Optional[Dict[str, Any]]:
        """Return close-prompt context for low-value ended sessions.

        Prompts are based on dollar-equivalent value, not raw SC, so sites with
        different `sc_rate` values use the same $1.00 threshold.
        """
        site = self.get_site(site_id)
        user = self.get_user(user_id)
        if not site or not user:
            return None

        current_sc = Decimal(str(ending_total_sc or 0))
        sc_rate = Decimal(str(getattr(site, "sc_rate", 1.0) or 1.0))
        current_value = current_sc * sc_rate
        close_threshold = Decimal("1.00")
        if current_value >= close_threshold:
            return None

        basis_row = self.db.fetch_one(
            """
            SELECT COALESCE(SUM(remaining_amount), 0) AS remaining_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND deleted_at IS NULL
              AND (status IS NULL OR status = 'active')
            """,
            (site_id, user_id),
        )
        total_basis = Decimal("0.00")
        if basis_row:
            total_basis = Decimal(str(basis_row["remaining_basis"] or 0))

        return {
            "site_id": site_id,
            "user_id": user_id,
            "site_name": site.name,
            "user_name": user.name,
            "current_sc": current_sc,
            "current_value": current_value,
            "total_basis": total_basis,
            "close_threshold": close_threshold,
        }

    def update_unrealized_notes(self, site_id: int, user_id: int, notes: str) -> None:
        self.unrealized_position_repo.update_notes(site_id, user_id, notes)

    def get_unrealized_open_purchases(
        self,
        site_id: int,
        user_id: int,
        start_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Purchases to show in the Unrealized "View Position" dialog.

        Historically this returned only purchases with remaining basis. In practice, users
        expect to see the purchase(s) that led to the current position, even if remaining
        basis is now $0. We therefore scope to the position timeframe when available.
        """
        query = """
            SELECT id, purchase_date, purchase_time, amount, sc_received, remaining_amount,
               purchase_entry_time_zone
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND deleted_at IS NULL
              AND (status IS NULL OR status = 'active')
              AND (? IS NULL OR (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') >= ?)))
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
        """
        if start_date:
            from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc
            tz_name = get_configured_timezone_name()
            start_date_utc, start_time_utc = local_date_time_to_utc(start_date, "00:00:00", tz_name)
            return self.db.fetch_all(
                query,
                (site_id, user_id, start_date_utc, start_date_utc, start_date_utc, start_time_utc),
            )
        return self.db.fetch_all(query, (site_id, user_id, None, None, None, None))

    def get_unrealized_related_purchases(
        self,
        site_id: int,
        user_id: int,
        purchase_basis: Decimal,
        start_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Purchases to show in the Unrealized "View Position" dialog -> Related tab.

        - For normal positions (purchase basis > 0): show purchases within the related window.
        - For profit-only positions (purchase basis == 0): show purchases that contributed via FIFO
          allocations (even if their remaining_amount is now $0).
        """
        if purchase_basis > Decimal("0.001"):
            return self.get_unrealized_open_purchases(site_id, user_id, start_date=start_date)

        # Profit-only: prefer FIFO-attributed purchases linked to redemptions in the related window.
        allocations_since_query = """
            SELECT DISTINCT
                p.id, p.purchase_date, p.purchase_time, p.amount, p.sc_received, p.remaining_amount,
                p.purchase_entry_time_zone
            FROM redemptions r
            JOIN redemption_allocations ra ON ra.redemption_id = r.id
            JOIN purchases p ON p.id = ra.purchase_id
            WHERE r.site_id = ? AND r.user_id = ?
              AND r.deleted_at IS NULL
              AND r.is_free_sc = 0
              AND CAST(ra.allocated_amount AS REAL) > 0
              AND p.deleted_at IS NULL
              AND (p.status IS NULL OR p.status = 'active')
              AND (? IS NULL OR (r.redemption_date > ? OR (r.redemption_date = ? AND COALESCE(r.redemption_time, '00:00:00') >= ?)))
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time,'00:00:00') ASC, p.id ASC
        """
        if start_date:
            from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc
            tz_name = get_configured_timezone_name()
            start_date_utc, start_time_utc = local_date_time_to_utc(start_date, "00:00:00", tz_name)
            purchases = self.db.fetch_all(
                allocations_since_query,
                (site_id, user_id, start_date_utc, start_date_utc, start_date_utc, start_time_utc),
            )
        else:
            purchases = self.db.fetch_all(
                allocations_since_query, (site_id, user_id, None, None, None, None)
            )
        if purchases:
            return purchases

        # Fallback: the most recent redemption with allocations (useful when the related window
        # starts after the basis was consumed).
        latest_redemption_query = """
            SELECT r.id
            FROM redemptions r
            WHERE r.site_id = ? AND r.user_id = ?
              AND r.deleted_at IS NULL
              AND r.is_free_sc = 0
              AND EXISTS (
                SELECT 1 FROM redemption_allocations ra
                WHERE ra.redemption_id = r.id
                  AND CAST(ra.allocated_amount AS REAL) > 0
              )
            ORDER BY r.redemption_date DESC,
                     COALESCE(r.redemption_time, '00:00:00') DESC,
                     r.id DESC
            LIMIT 1
        """
        row = self.db.fetch_one(latest_redemption_query, (site_id, user_id))
        if row and row.get("id"):
            redemption_id = row["id"]
            latest_allocations_query = """
                SELECT DISTINCT
                    p.id, p.purchase_date, p.purchase_time, p.amount, p.sc_received, p.remaining_amount,
                    p.purchase_entry_time_zone
                FROM redemption_allocations ra
                JOIN purchases p ON p.id = ra.purchase_id
                WHERE ra.redemption_id = ?
                  AND CAST(ra.allocated_amount AS REAL) > 0
                  AND p.deleted_at IS NULL
                  AND (p.status IS NULL OR p.status = 'active')
                ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time,'00:00:00') ASC, p.id ASC
            """
            purchases = self.db.fetch_all(latest_allocations_query, (redemption_id,))
            if purchases:
                return purchases

        # Last resort: just show purchases in the related window.
        return self.get_unrealized_open_purchases(site_id, user_id, start_date=start_date)

    def get_unrealized_related_anchor_date(
        self,
        site_id: int,
        user_id: int,
        position_start_date: date,
        purchase_basis: Decimal,
    ) -> date:
        """Compute the anchor date for Unrealized "View Position" -> Related tab."""
        return self.unrealized_position_repo.get_related_anchor_date(
            site_id=site_id,
            user_id=user_id,
            position_start_date=position_start_date,
            purchase_basis=purchase_basis,
        )

    def get_unrealized_sessions(
        self,
        site_id: int,
        user_id: int,
        start_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """Sessions to show in the Unrealized "View Position" dialog."""
        query = """
            SELECT gs.id, gs.session_date, gs.session_time, gs.end_date, gs.end_time,
                   gs.start_entry_time_zone, gs.end_entry_time_zone,
                   gs.ending_balance, gs.ending_redeemable, gs.status,
                   g.name as game_name
            FROM game_sessions gs
            LEFT JOIN games g ON gs.game_id = g.id
            WHERE gs.site_id = ? AND gs.user_id = ?
              AND gs.deleted_at IS NULL
              AND (? IS NULL OR (COALESCE(gs.end_date, gs.session_date) > ? OR (COALESCE(gs.end_date, gs.session_date) = ? AND COALESCE(gs.end_time, gs.session_time, '00:00:00') >= ?)))
            ORDER BY COALESCE(gs.end_date, gs.session_date) DESC,
                     COALESCE(gs.end_time, gs.session_time, '00:00:00') DESC,
                     gs.id DESC
        """
        if start_date:
            from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc
            tz_name = get_configured_timezone_name()
            start_date_utc, start_time_utc = local_date_time_to_utc(start_date, "00:00:00", tz_name)
            return self.db.fetch_all(
                query,
                (site_id, user_id, start_date_utc, start_date_utc, start_date_utc, start_time_utc),
            )
        return self.db.fetch_all(query, (site_id, user_id, None, None, None, None))

    def close_unrealized_position(
        self,
        site_id: int,
        user_id: int,
        current_sc: Decimal,
        current_value: Decimal,
        total_basis: Decimal,
    ) -> Dict[str, Decimal]:
        active_session = self.game_session_repo.get_active_session(user_id, site_id)
        if active_session:
            raise ValueError("Cannot close balance while a session is active for this site/user.")

        now = datetime.now()
        basis = Decimal(str(total_basis or 0))
        net_loss = basis
        notes = (
            f"Balance Closed - Net Loss: ${net_loss:.2f} "
            f"(${current_sc:.2f} SC marked dormant)"
        )

        if basis <= Decimal("0.00"):
            self.redemption_service.create_redemption(
                user_id=user_id,
                site_id=site_id,
                amount=Decimal("0.00"),
                redemption_date=date.today(),
                redemption_time=now.strftime("%H:%M:%S"),
                processed=True,
                more_remaining=True,
                notes=notes,
                apply_fifo=False,
            )
        else:
            self.redemption_service.create_redemption(
                user_id=user_id,
                site_id=site_id,
                amount=Decimal("0.00"),
                redemption_date=date.today(),
                redemption_time=now.strftime("%H:%M:%S"),
                processed=True,
                more_remaining=False,  # Full redemption - consume all basis
                notes=notes,
                apply_fifo=True,  # Apply FIFO to consume basis
            )

            # Mark purchases as dormant (FIFO already set remaining_amount to 0)
            self.db.execute(
                """
                UPDATE purchases
                SET status = 'dormant', updated_at = CURRENT_TIMESTAMP
                WHERE site_id = ? AND user_id = ? AND remaining_amount = 0
                  AND (status IS NULL OR status = 'active')
                """,
                (site_id, user_id),
            )

        return {
            "net_loss": net_loss,
            "current_sc": current_sc,
            "current_value": current_value,
        }
    
    # ==========================================================================
    # Realized Transactions (Completed Redemptions Cash Flow)
    # ==========================================================================
    
    def get_realized_transactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        site_ids: Optional[List[int]] = None,
        user_ids: Optional[List[int]] = None
    ) -> List[RealizedTransaction]:
        """
        Get all realized transactions (completed redemption cash flow).
        Shows cost_basis (money in), payout (money out), net_pl (cash flow).
        
        NOTE: This is CASH FLOW, not taxable P/L. Taxable P/L is in game_sessions.
        """
        return self.realized_transaction_repo.get_all(
            start_date, end_date, site_ids, user_ids
        )
    
    def get_realized_transaction_by_redemption(self, redemption_id: int) -> Optional[RealizedTransaction]:
        """Get realized transaction for a specific redemption."""
        return self.realized_transaction_repo.get_by_redemption(redemption_id)

    def update_realized_notes(self, redemption_id: int, notes: str) -> None:
        """Update notes for a realized transaction by redemption ID."""
        self.realized_transaction_repo.update_notes(redemption_id, notes)

    # ==========================================================================
    # Expenses
    # ==========================================================================

    def get_expenses(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Expense]:
        return self.expense_service.list_expenses(start_date=start_date, end_date=end_date)

    def get_expense(self, expense_id: int) -> Optional[Expense]:
        return self.expense_service.get_expense(expense_id)

    def create_expense(
        self,
        expense_date: date,
        amount: Decimal,
        vendor: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
        expense_time: Optional[str] = None,
    ) -> Expense:
        return self.expense_service.create_expense(
            expense_date=expense_date,
            amount=amount,
            vendor=vendor,
            description=description,
            category=category,
            user_id=user_id,
            expense_time=expense_time,
        )

    def update_expense(self, expense_id: int, **kwargs) -> Expense:
        return self.expense_service.update_expense(expense_id, **kwargs)

    def delete_expense(self, expense_id: int) -> None:
        self.expense_service.delete_expense(expense_id)
    
    def get_data_summary(self) -> Dict[str, int]:
        """Get counts of all records in system."""
        return self.validation_service.get_data_summary()
    
    # ==========================================================================
    # Database Tools - Exclusive Operations (Backup/Restore/Reset)
    # ==========================================================================
    
    def acquire_tools_lock(self) -> bool:
        """
        Attempt to acquire exclusive tools operation lock.
        
        Returns:
            True if lock acquired, False if another operation is active
        """
        with self._tools_lock:
            if self._tools_operation_active:
                return False
            self._tools_operation_active = True

            # Put the UI-facing DB connection into read-only mode while tools run.
            # Tools workers create their own DB connections, so this only blocks UI writes.
            try:
                if hasattr(self, "db") and hasattr(self.db, "set_writes_blocked"):
                    self.db.set_writes_blocked(True)
            except Exception:
                pass
            return True
    
    def release_tools_lock(self) -> None:
        """Release exclusive tools operation lock."""
        with self._tools_lock:
            self._tools_operation_active = False

            # Re-enable UI writes.
            try:
                if hasattr(self, "db") and hasattr(self.db, "set_writes_blocked"):
                    self.db.set_writes_blocked(False)
            except Exception:
                pass
    
    def is_tools_operation_active(self) -> bool:
        """Check if a tools operation is currently running."""
        with self._tools_lock:
            return self._tools_operation_active
    
    # ==========================================================================
    # Data Change Event System (Issue #9: Global Refresh)
    # ==========================================================================
    
    def add_data_change_listener(self, listener: Callable[[DataChangeEvent], None]) -> None:
        """
        Register a listener for data change events.
        
        Listeners are called when database-changing operations complete.
        Used by MainWindow to trigger debounced UI refresh.
        
        Args:
            listener: Callback function that receives DataChangeEvent
        """
        if listener not in self._data_change_listeners:
            self._data_change_listeners.append(listener)
    
    def remove_data_change_listener(self, listener: Callable[[DataChangeEvent], None]) -> None:
        """Remove a data change listener."""
        if listener in self._data_change_listeners:
            self._data_change_listeners.remove(listener)
    
    def emit_data_changed(self, event: DataChangeEvent) -> None:
        """
        Emit a data change event to all listeners.
        
        Called by tools operations, import, and recalculation after successful completion.
        UI listeners should debounce and refresh appropriately.
        
        Args:
            event: DataChangeEvent with operation type and scope
        """
        # Also notify the legacy DatabaseManager listener system for compatibility
        if hasattr(self.db, "notify_change"):
            try:
                self.db.notify_change()
            except Exception:
                pass
        
        # Notify all registered listeners
        for listener in list(self._data_change_listeners):
            try:
                listener(event)
            except Exception:
                # Don't let one broken listener crash the emit
                continue
    
    def is_maintenance_mode(self) -> bool:
        """
        Check if the app is in maintenance mode.
        
        During maintenance (restore/reset), user writes are blocked and
        manual refresh should be prevented.
        """
        return self._maintenance_mode
    
    def set_maintenance_mode(self, enabled: bool) -> None:
        """
        Enable/disable maintenance mode.
        
        Should be called by tools operations at start/end of destructive operations.
        When enabled, writes are blocked via set_writes_blocked.
        """
        self._maintenance_mode = enabled
        if hasattr(self.db, "set_writes_blocked"):
            self.db.set_writes_blocked(enabled)
        
        # Emit maintenance phase events
        if enabled:
            self.emit_data_changed(DataChangeEvent(
                operation="maintenance",
                maintenance_phase="start"
            ))
        else:
            self.emit_data_changed(DataChangeEvent(
                operation="maintenance",
                maintenance_phase="end"
            ))
    
    # ==========================================================================
    # Tools Workers (Backup/Restore/Reset)
    # ==========================================================================
    
    def create_backup_worker(self, backup_path: str, include_audit_log: bool = True):
        """
        Create a backup worker for background execution.
        
        Note: Backup worker creates a read-only connection for thread safety.
        
        Args:
            backup_path: Destination file path for backup
            include_audit_log: Whether to include audit_log table
        
        Returns:
            DatabaseBackupWorker instance ready to be started
        
        Example:
            if facade.acquire_tools_lock():
                worker = facade.create_backup_worker(backup_path)
                worker.signals.finished.connect(lambda: facade.release_tools_lock())
                QThreadPool.globalInstance().start(worker)
        """
        from ui.tools_workers import DatabaseBackupWorker
        return DatabaseBackupWorker(self.db_path, backup_path, include_audit_log)
    
    def create_restore_worker(self, backup_path: str, restore_mode, tables: Optional[List[str]] = None):
        """
        Create a restore worker for background execution.
        
        Worker creates its own DB connection for thread safety.
        
        Args:
            backup_path: Path to backup file
            restore_mode: RestoreMode enum value
            tables: List of tables to restore (for MERGE_SELECTED mode)
        
        Returns:
            DatabaseRestoreWorker instance ready to be started
        
        Example:
            if facade.acquire_tools_lock():
                from services.tools.enums import RestoreMode
                worker = facade.create_restore_worker(backup_path, RestoreMode.REPLACE)
                worker.signals.finished.connect(lambda: facade.release_tools_lock())
                QThreadPool.globalInstance().start(worker)
        """
        from ui.tools_workers import DatabaseRestoreWorker
        return DatabaseRestoreWorker(self.db_path, backup_path, restore_mode, tables)
    
    def create_reset_worker(self, keep_setup_data: bool = False, keep_audit_log: bool = False, 
                           tables_to_reset: Optional[List[str]] = None):
        """
        Create a reset worker for background execution.
        
        Worker creates its own DB connection for thread safety.
        
        Args:
            keep_setup_data: If True, preserve reference/setup tables
            keep_audit_log: If True, preserve audit_log table
            tables_to_reset: Specific tables to reset
        
        Returns:
            DatabaseResetWorker instance ready to be started
        
        Example:
            if facade.acquire_tools_lock():
                worker = facade.create_reset_worker(keep_setup_data=True)
                worker.signals.finished.connect(lambda: facade.release_tools_lock())
                QThreadPool.globalInstance().start(worker)
        """
        from ui.tools_workers import DatabaseResetWorker
        return DatabaseResetWorker(self.db_path, keep_setup_data, keep_audit_log, tables_to_reset)
