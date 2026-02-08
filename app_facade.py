"""
AppFacade - Unified interface for Qt application to access OOP backend services

This facade provides a single entry point for the Qt UI to interact with
all backend services while maintaining backward compatibility during migration.
"""
from decimal import Decimal
from datetime import date, datetime
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
from repositories.notification_repository import NotificationRepository

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
        )
        
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
        self.notification_repo = NotificationRepository()
        self.notification_service = NotificationService(self.notification_repo)
        self.notification_rules_service = NotificationRulesService(
            self.notification_service,
            None,  # Will be set from MainWindow
            self.db
        )
        
        # Repair Mode service (Issue #55)
        # Will be wired to MainWindow settings after construction
        self.repair_mode_service = None

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

    def _find_containing_session_start(
        self,
        site_id: int,
        user_id: int,
        session_date: date,
        session_time: Optional[str],
    ) -> Optional[Tuple[date, str]]:
        ts_time = self._normalize_time(session_time)
        date_str = session_date.isoformat() if hasattr(session_date, "isoformat") else str(session_date)

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
        return start_date, row["start_time"]

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
        return session_date, self._normalize_time(session_time)

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
            # Normal mode: rebuild immediately
            self.recalculation_service.rebuild_fifo_for_pair_from(
                user_id,
                site_id,
                boundary_date.isoformat(),
                boundary_time
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
                    sc_rate: float = 1.0, notes: Optional[str] = None) -> Site:
        """Create new site."""
        return self.site_service.create_site(
            name=name,
            url=url,
            sc_rate=sc_rate,
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
        """Create new purchase with atomic transaction."""
        with self.db.transaction():
            purchase = self.purchase_service.create_purchase(
                user_id=user_id,
                site_id=site_id,
                amount=amount,
                sc_received=sc_received,
                starting_sc_balance=starting_sc_balance,
                cashback_earned=cashback_earned,
                purchase_date=purchase_date,
                card_id=card_id,
                purchase_time=purchase_time,
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
        """Update purchase and trigger scoped rebuild when needed with atomic transaction.

        Legacy parity:
        - Allow editing consumed purchases, but protect amount/date unless a full rebuild is performed.
        - Allow site/user change only if explicitly forced (clears derived allocations via rebuild).
        """
        with self.db.transaction():
            old_purchase = self.purchase_repo.get_by_id(purchase_id)
            if not old_purchase:
                raise ValueError(f"Purchase {purchase_id} not found")

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
        fifo_result = self.recalculation_service.rebuild_fifo_all()
        pairs = self.recalculation_service.iter_pairs()
        sessions_recalculated = 0
        for user_id, site_id in pairs:
            try:
                self.game_session_service.recalculate_closed_sessions_for_pair(user_id, site_id)
                sessions_recalculated += 1
            except Exception:
                # Keep going; individual pairs may lack sessions or have data issues.
                continue

        # Rebuild explicit event links (legacy parity)
        try:
            self.game_session_event_link_service.rebuild_links_all()
        except Exception:
            pass

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
        """Get the start datetime of the basis period for a purchase.
        
        A basis period is bounded by FULL redemptions (more_remaining=0).
        Returns (date, time) of the most recent FULL redemption before the purchase,
        or None if no such redemption exists (meaning this purchase is in the first period).
        
        Args:
            user_id: User ID
            site_id: Site ID
            purchase_date: Date of the purchase
            purchase_time: Time of the purchase (optional, defaults to '00:00:00')
            
        Returns:
            (date, time) tuple of the most recent FULL redemption, or None
        """
        redemptions = self.redemption_repo.get_by_user_and_site(user_id, site_id)
        
        # Normalize purchase time for comparison
        p_time = purchase_time or "00:00:00"
        
        # Find the most recent FULL redemption (more_remaining=0) before this purchase
        latest_full = None
        latest_datetime = None
        
        for r in redemptions:
            # Skip if not a full redemption
            if r.more_remaining != 0:
                continue
                
            r_time = r.redemption_time or "00:00:00"
            
            # Check if this redemption is before the purchase
            if r.redemption_date < purchase_date or \
               (r.redemption_date == purchase_date and r_time < p_time):
                # Compare with current latest
                if latest_datetime is None or \
                   r.redemption_date > latest_datetime[0] or \
                   (r.redemption_date == latest_datetime[0] and r_time > latest_datetime[1]):
                    latest_full = r
                    latest_datetime = (r.redemption_date, r_time)
        
        return latest_datetime
    
    def get_basis_period_purchases(
        self,
        user_id: int,
        site_id: int,
        purchase_date: date,
        purchase_time: Optional[str] = None,
        exclude_purchase_id: Optional[int] = None
    ) -> List[Purchase]:
        """Get all purchases in the same basis period as the given purchase.
        
        Returns ALL purchases (past, current, and future) ordered by (date, time, id)
        that fall within the basis period defined by FULL redemptions (more_remaining=0).
        Partial redemptions do NOT start a new basis period.
        
        Args:
            user_id: User ID
            site_id: Site ID
            purchase_date: Date of the reference purchase
            purchase_time: Time of the reference purchase (optional)
            exclude_purchase_id: Purchase ID to exclude (useful when editing)
            
        Returns:
            List of purchases in the basis period, ordered by (date, time, id)
        """
        # Get the basis period start
        period_start = self.get_basis_period_start_for_purchase(
            user_id, site_id, purchase_date, purchase_time
        )
        
        # Get all purchases for this user+site
        all_purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
        
        # Filter to purchases in the basis period
        p_time = purchase_time or "00:00:00"
        result = []
        
        for p in all_purchases:
            # Skip excluded purchase
            if exclude_purchase_id and p.id == exclude_purchase_id:
                continue
                
            p_purchase_time = p.purchase_time or "00:00:00"
            
            # Check if purchase is after period start (or no start = first period)
            if period_start:
                start_date, start_time = period_start
                if p.purchase_date < start_date or \
                   (p.purchase_date == start_date and p_purchase_time <= start_time):
                    continue
            
            # Include ALL purchases in the basis period (past, current, and future)
            # This gives a complete view of the entire basis period when viewing any purchase in it
            result.append(p)
        
        # Sort by (date, time, id)
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
        """Create new redemption with optional FIFO processing, using atomic transaction."""
        with self.db.transaction():
            redemption = self.redemption_service.create_redemption(
                user_id=user_id,
                site_id=site_id,
                amount=amount,
                fees=fees,
                redemption_date=redemption_date,
                apply_fifo=apply_fifo,
                redemption_method_id=redemption_method_id,
                redemption_time=redemption_time,
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
        """Update redemption and fully reprocess FIFO/realized/session cascades (legacy parity)."""
        old_redemption = self.redemption_repo.get_by_id(redemption_id)
        if not old_redemption:
            raise ValueError(f"Redemption {redemption_id} not found")

        updated = Redemption(
            id=old_redemption.id,
            user_id=kwargs.get("user_id", old_redemption.user_id),
            site_id=kwargs.get("site_id", old_redemption.site_id),
            amount=kwargs.get("amount", old_redemption.amount),
            fees=kwargs.get("fees", old_redemption.fees),
            redemption_date=kwargs.get("redemption_date", old_redemption.redemption_date),
            redemption_time=kwargs.get("redemption_time", old_redemption.redemption_time),
            redemption_method_id=kwargs.get("redemption_method_id", old_redemption.redemption_method_id),
            receipt_date=kwargs.get("receipt_date", old_redemption.receipt_date),
            processed=kwargs.get("processed", old_redemption.processed),
            more_remaining=kwargs.get("more_remaining", old_redemption.more_remaining),
            is_free_sc=kwargs.get("is_free_sc", old_redemption.is_free_sc),
            notes=kwargs.get("notes", old_redemption.notes),
        )
        updated.__post_init__()
        self.redemption_repo.update(updated)

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
                                 exclude_purchase_id: Optional[int] = None) -> Tuple[Decimal, Decimal]:
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
            exclude_purchase_id=exclude_purchase_id
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
        """Create new game session with automatic P/L calculation."""
        session = self.game_session_service.create_session(
            user_id=user_id,
            site_id=site_id,
            game_id=game_id,
            game_type_id=game_type_id,
            session_date=session_date,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            starting_redeemable=starting_redeemable,
            ending_redeemable=ending_redeemable,
            purchases_during=purchases_during,
            redemptions_during=redemptions_during,
            session_time=session_time or "00:00:00",
            notes=notes or "",
            calculate_pl=calculate_pl
        )
        boundary_date, boundary_time = self._containing_boundary(
            site_id,
            user_id,
            session.session_date,
            session.session_time,
        )
        self.game_session_event_link_service.rebuild_links_for_pair_from(
            site_id,
            user_id,
            boundary_date.isoformat(),
            boundary_time,
        )
        return session
    
    def update_game_session(self, session_id: int, recalculate_pl: bool = True, 
                           **kwargs) -> GameSession:
        """Update game session with optional P/L recalculation."""
        old_session = self.game_session_repo.get_by_id(session_id)
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
                self.game_session_event_link_service.rebuild_links_for_pair_from(
                    new_pair[1],
                    new_pair[0],
                    boundary_date.isoformat(),
                    boundary_time,
                )
            else:
                old_date, old_time = self._containing_boundary(
                    old_pair[1],
                    old_pair[0],
                    old_session.session_date,
                    old_session.session_time,
                )
                self.game_session_event_link_service.rebuild_links_for_pair_from(
                    old_pair[1],
                    old_pair[0],
                    old_date.isoformat(),
                    old_time,
                )
                new_date, new_time = self._containing_boundary(
                    new_pair[1],
                    new_pair[0],
                    updated.session_date,
                    updated.session_time,
                )
                self.game_session_event_link_service.rebuild_links_for_pair_from(
                    new_pair[1],
                    new_pair[0],
                    new_date.isoformat(),
                    new_time,
                )
        else:
            boundary_date, boundary_time = self._containing_boundary(
                updated.site_id,
                updated.user_id,
                updated.session_date,
                updated.session_time,
            )
            self.game_session_event_link_service.rebuild_links_for_pair_from(
                updated.site_id,
                updated.user_id,
                boundary_date.isoformat(),
                boundary_time,
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
            self.game_session_event_link_service.rebuild_links_for_pair_from(
                session.site_id,
                session.user_id,
                boundary_date.isoformat(),
                boundary_time,
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
        
        # Rebuild once per affected pair
        for site_id, user_id in affected_pairs:
            date, time = earliest_dates[(site_id, user_id)]
            boundary_date, boundary_time = self._containing_boundary(site_id, user_id, date, time)
            self.game_session_event_link_service.rebuild_links_for_pair_from(
                site_id, user_id, boundary_date.isoformat(), boundary_time
            )

    def recalculate_game_rtp(self, game_id: int) -> None:
        """Recalculate RTP aggregates for a game (full rebuild)."""
        self.game_session_service.recalculate_game_rtp_full(game_id)

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
        if events.get("purchases") or events.get("redemptions"):
            return events
        session = self.game_session_repo.get_by_id(session_id)
        if session:
            self.game_session_event_link_service.rebuild_links_for_pair(session.site_id, session.user_id)
            return self.game_session_event_link_service.get_events_for_session(session_id)
        return events

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
    
    def validate_all_data(self, user_id: Optional[int] = None,
                         site_id: Optional[int] = None) -> Dict[str, Any]:
        """Run comprehensive data validation checks."""
        return self.validation_service.validate_all(user_id, site_id)
    
    def validate_fifo_allocations(self, user_id: Optional[int] = None,
                                 site_id: Optional[int] = None) -> Dict[str, Any]:
        """Validate FIFO allocation integrity."""
        return self.validation_service.validate_fifo_allocations(user_id, site_id)
    
    def get_data_summary(self) -> Dict[str, int]:
        """Get counts of all records in system."""
        return self.validation_service.get_data_summary()
    
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
    
    def get_unrealized_position(self, site_id: int, user_id: int) -> Optional[UnrealizedPosition]:
        """Get specific unrealized position for a site/user pair."""
        return self.unrealized_position_repo.get_position_by_site_user(site_id, user_id)

    def update_unrealized_notes(self, site_id: int, user_id: int, notes: str) -> None:
        self.unrealized_position_repo.update_notes(site_id, user_id, notes)

    def get_unrealized_open_purchases(self, site_id: int, user_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT id, purchase_date, purchase_time, amount, sc_received, remaining_amount
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0.001
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
        """
        return self.db.fetch_all(query, (site_id, user_id))

    def get_unrealized_sessions(self, site_id: int, user_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT gs.id, gs.session_date, gs.session_time, gs.end_date, gs.end_time,
                   gs.ending_balance, gs.ending_redeemable, gs.status,
                   g.name as game_name
            FROM game_sessions gs
            LEFT JOIN games g ON gs.game_id = g.id
            WHERE gs.site_id = ? AND gs.user_id = ?
            ORDER BY gs.session_date DESC, gs.session_time DESC, gs.id DESC
        """
        return self.db.fetch_all(query, (site_id, user_id))

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

        # When closing position: cost basis is abandoned (total loss)
        # current_value is irrelevant since we're not redeeming
        net_loss = total_basis
        notes = (
            f"Balance Closed - Net Loss: ${net_loss:.2f} "
            f"(${current_sc:.2f} SC marked dormant)"
        )

        now = datetime.now()
        # Create $0 redemption as Full (more_remaining=False) to consume all basis
        redemption = self.redemption_service.create_redemption(
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
