"""
AppFacade - Unified interface for Qt application to access OOP backend services

This facade provides a single entry point for the Qt UI to interact with
all backend services while maintaining backward compatibility during migration.
"""
from decimal import Decimal
from datetime import date
from typing import Optional, List, Dict, Any, Tuple

from repositories.database import DatabaseManager
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
        
        # Initialize services
        self.user_service = UserService(self.user_repo)
        self.site_service = SiteService(self.site_repo)
        self.card_service = CardService(self.card_repo)
        self.game_type_service = GameTypeService(self.game_type_repo)
        self.game_service = GameService(self.game_repo)
        self.redemption_method_service = RedemptionMethodService(self.redemption_method_repo)
        self.redemption_method_type_service = RedemptionMethodTypeService(self.redemption_method_type_repo)
        
        self.fifo_service = FIFOService(self.purchase_repo)
        self.purchase_service = PurchaseService(self.purchase_repo)
        self.redemption_service = RedemptionService(
            self.redemption_repo,
            self.fifo_service,
            db_manager=self.db  # Needed for redemption_allocations table
        )
        self.game_session_service = GameSessionService(
            self.game_session_repo,
            site_repo=self.site_repo,  # Needed for SC rate in P/L calculation
            fifo_service=self.fifo_service,  # May be needed in future
            purchase_repo=self.purchase_repo,
            redemption_repo=self.redemption_repo
        )
        
        self.report_service = ReportService(self.db)
        self.validation_service = ValidationService(self.db)
        self.report_service = ReportService(self.db)
        self.daily_sessions_service = DailySessionsService(self.db, self.daily_session_repo)

        # Bulk rebuild / recalculation orchestration (legacy parity)
        self.recalculation_service = RecalculationService(self.db)
        self.game_session_event_link_service = GameSessionEventLinkService(
            self.game_session_event_link_repo,
            self.game_session_repo,
            self.purchase_repo,
            self.redemption_repo,
            self.db,
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
        self.redemption_method_service.method_repo.delete(method_id)

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
        self.redemption_method_type_service.type_repo.delete(type_id)
    
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
        self.game_type_service.type_repo.delete(type_id)

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
        self.game_service.game_repo.delete(game_id)
    
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
        """Create new purchase."""
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
        self.game_session_event_link_service.rebuild_links_for_pair(site_id, user_id)
        return purchase
    
    def update_purchase(self, purchase_id: int, force_site_user_change: bool = False, **kwargs) -> Purchase:
        """Update purchase and trigger scoped rebuild when needed.

        Legacy parity:
        - Allow editing consumed purchases, but protect amount/date unless a full rebuild is performed.
        - Allow site/user change only if explicitly forced (clears derived allocations via rebuild).
        """
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
            impacted_pairs = {(old_purchase.user_id, old_purchase.site_id), (updated.user_id, updated.site_id)}
            for user_id, site_id in impacted_pairs:
                self.recalculation_service.rebuild_fifo_for_pair(user_id, site_id)
                # Session P/L depends on purchase/redemption chronology.
                self.game_session_service.recalculate_closed_sessions_for_pair(user_id, site_id)
                self.game_session_event_link_service.rebuild_links_for_pair(site_id, user_id)

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

        return {
            "fifo": fifo_result,
            "pairs": len(pairs),
            "session_pairs_recalculated": sessions_recalculated,
        }
    
    def delete_purchase(self, purchase_id: int) -> None:
        """Delete purchase (prevents if consumed)."""
        purchase = self.purchase_repo.get_by_id(purchase_id)
        self.purchase_service.delete_purchase(purchase_id)
        if purchase:
            self.game_session_event_link_service.rebuild_links_for_pair(purchase.site_id, purchase.user_id)
    
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
        """Create new redemption with optional FIFO processing."""
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
        self.game_session_event_link_service.rebuild_links_for_pair(site_id, user_id)
        return redemption
    
    def update_redemption(self, redemption_id: int, **kwargs) -> Redemption:
        """Update redemption (with FIFO allocation protection)."""
        old_redemption = self.redemption_repo.get_by_id(redemption_id)
        updated = self.redemption_service.update_redemption(redemption_id, **kwargs)
        impacted_pairs = set()
        if old_redemption:
            impacted_pairs.add((old_redemption.user_id, old_redemption.site_id))
        impacted_pairs.add((updated.user_id, updated.site_id))
        for user_id, site_id in impacted_pairs:
            self.game_session_event_link_service.rebuild_links_for_pair(site_id, user_id)
        return updated
    
    def delete_redemption(self, redemption_id: int) -> None:
        """Delete redemption (reverses FIFO if allocated)."""
        redemption = self.redemption_repo.get_by_id(redemption_id)
        self.redemption_service.delete_redemption(redemption_id)
        if redemption:
            self.game_session_event_link_service.rebuild_links_for_pair(redemption.site_id, redemption.user_id)
    
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
                                 session_date: date, session_time: str) -> Tuple[Decimal, Decimal]:
        """Compute expected starting balances for a new session."""
        return self.game_session_service.compute_expected_balances(
            user_id=user_id,
            site_id=site_id,
            session_date=session_date,
            session_time=session_time
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
                           calculate_pl: bool = True) -> GameSession:
        """Create new game session with automatic P/L calculation."""
        session = self.game_session_service.create_session(
            user_id=user_id,
            site_id=site_id,
            game_id=game_id,
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
        self.game_session_event_link_service.rebuild_links_for_pair(site_id, user_id)
        return session
    
    def update_game_session(self, session_id: int, recalculate_pl: bool = True, 
                           **kwargs) -> GameSession:
        """Update game session with optional P/L recalculation."""
        updated = self.game_session_service.update_session(
            session_id, 
            recalculate_pl=recalculate_pl, 
            **kwargs
        )
        self.game_session_event_link_service.rebuild_links_for_pair(updated.site_id, updated.user_id)
        return updated
    
    def delete_game_session(self, session_id: int) -> None:
        """Delete game session."""
        session = self.game_session_repo.get_by_id(session_id)
        self.game_session_service.delete_session(session_id)
        if session:
            self.game_session_event_link_service.rebuild_links_for_pair(session.site_id, session.user_id)

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
        """Get counts of all records in system."""
        return self.validation_service.get_data_summary()
