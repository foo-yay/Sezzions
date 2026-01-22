"""
Service layer for GameSession business logic - CORRECT P/L CALCULATION

CRITICAL: This implements the correct tax calculation algorithm from business_logic.py.
Do NOT simplify or change this formula without verifying against legacy app.
"""
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import date, datetime
from repositories.game_session_repository import GameSessionRepository
from repositories.site_repository import SiteRepository
from models.game_session import GameSession
from services.fifo_service import FIFOService


class GameSessionService:
    """Business logic for game sessions with proper tax calculations"""
    
    def __init__(self, session_repo: GameSessionRepository, 
                 site_repo: Optional[SiteRepository] = None,
                 fifo_service: Optional[FIFOService] = None,
                 purchase_repo=None,
                 redemption_repo=None):
        self.session_repo = session_repo
        self.site_repo = site_repo
        self.fifo_service = fifo_service
        self.purchase_repo = purchase_repo
        self.redemption_repo = redemption_repo
    
    def create_session(
        self,
        user_id: int,
        site_id: int,
        game_id: Optional[int],
        session_date: date,
        starting_balance: Decimal = Decimal("0.00"),
        ending_balance: Decimal = Decimal("0.00"),
        starting_redeemable: Decimal = Decimal("0.00"),
        ending_redeemable: Decimal = Decimal("0.00"),
        purchases_during: Decimal = Decimal("0.00"),
        redemptions_during: Decimal = Decimal("0.00"),
        session_time: str = "00:00:00",
        notes: str = "",
        calculate_pl: bool = True
    ) -> GameSession:
        """
        Create a new game session
        
        Args:
            calculate_pl: If True, calculate P/L based on previous session
        """
        active = self.session_repo.get_active_session(user_id, site_id)
        if active is not None:
            raise ValueError("An active session already exists for this User/Site.")

        # Create session model
        session = GameSession(
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
            session_time=session_time,
            notes=notes
        )
        
        # Save to database
        created = self.session_repo.create(session)

        # Calculate P/L if requested (recompute chain per legacy algorithm)
        if calculate_pl:
            self._recalculate_closed_sessions_for_pair(user_id, site_id)
            return self.session_repo.get_by_id(created.id)

        return created
    
    def update_session(
        self,
        session_id: int,
        starting_balance: Optional[Decimal] = None,
        ending_balance: Optional[Decimal] = None,
        starting_redeemable: Optional[Decimal] = None,
        ending_redeemable: Optional[Decimal] = None,
        purchases_during: Optional[Decimal] = None,
        redemptions_during: Optional[Decimal] = None,
        session_time: Optional[str] = None,
        notes: Optional[str] = None,
        recalculate_pl: bool = True,
        **kwargs
    ) -> GameSession:
        """
        Update an existing session
        
        Args:
            recalculate_pl: If True, recalculate P/L after updates
        """
        session = self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Update fields if provided
        if starting_balance is not None:
            session.starting_balance = starting_balance
        if ending_balance is not None:
            session.ending_balance = ending_balance
        if starting_redeemable is not None:
            session.starting_redeemable = starting_redeemable
        if ending_redeemable is not None:
            session.ending_redeemable = ending_redeemable
        if purchases_during is not None:
            session.purchases_during = purchases_during
        if redemptions_during is not None:
            session.redemptions_during = redemptions_during
        if session_time is not None:
            session.session_time = session_time
        if notes is not None:
            session.notes = notes
        
        # Handle other kwargs (for compatibility)
        for key, value in kwargs.items():
            if hasattr(session, key) and value is not None:
                setattr(session, key, value)

        target_status = getattr(session, "status", None)
        if target_status == "Active":
            active = self.session_repo.get_active_session(session.user_id, session.site_id)
            if active is not None and active.id != session.id:
                raise ValueError("An active session already exists for this User/Site.")

        updated = self.session_repo.update(session)

        # Recalculate P/L if requested
        if recalculate_pl:
            self._recalculate_closed_sessions_for_pair(session.user_id, session.site_id)
            refreshed = self.session_repo.get_by_id(session_id)
            return refreshed if refreshed else updated

        return updated
    
    def delete_session(self, session_id: int) -> None:
        """Delete a session"""
        self.session_repo.delete(session_id)
    
    def get_session(self, session_id: int) -> Optional[GameSession]:
        """Get session by ID"""
        return self.session_repo.get_by_id(session_id)
    
    def list_user_sessions(self, user_id: int) -> List[GameSession]:
        """List all sessions for a user"""
        return self.session_repo.get_by_user(user_id)
    
    def list_site_sessions(self, site_id: int) -> List[GameSession]:
        """List all sessions for a site"""
        return self.session_repo.get_by_site(site_id)
    
    def list_sessions(
        self,
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[GameSession]:
        """List sessions with optional filters"""
        # Get sessions based on user/site filters
        if user_id and site_id:
            sessions = self.session_repo.get_by_user_and_site(user_id, site_id)
        elif user_id:
            sessions = self.session_repo.get_by_user(user_id)
        elif site_id:
            sessions = self.session_repo.get_by_site(site_id)
        else:
            sessions = self.session_repo.get_all()
        
        # Apply status filter in memory if specified
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        return sessions

    def get_active_session(self, user_id: int, site_id: int) -> Optional[GameSession]:
        """Get active session for a user/site, if any"""
        return self.session_repo.get_active_session(user_id, site_id)

    def compute_expected_balances(
        self,
        user_id: int,
        site_id: int,
        session_date: date,
        session_time: str
    ) -> Tuple[Decimal, Decimal]:
        """Compute expected starting total/redeemable balances for a session"""
        expected_total = Decimal("0.00")
        expected_redeemable = Decimal("0.00")

        def to_dt(d, t):
            time_str = t or "00:00:00"
            if len(time_str) == 5:
                time_str = f"{time_str}:00"
            return datetime.combine(d, datetime.strptime(time_str, "%H:%M:%S").time())

        cutoff = to_dt(session_date, session_time)
        checkpoint_dt = None

        # Use last closed session as checkpoint when available (legacy behavior)
        sessions = self.session_repo.get_by_user_and_site(user_id, site_id)
        for sess in sessions:
            if sess.status != "Closed":
                continue
            sess_end_date = sess.end_date or sess.session_date
            sess_end_time = sess.end_time or sess.session_time
            sess_dt = to_dt(sess_end_date, sess_end_time)
            if sess_dt < cutoff and (checkpoint_dt is None or sess_dt > checkpoint_dt):
                checkpoint_dt = sess_dt
                expected_total = Decimal(str(sess.ending_balance))
                expected_redeemable = Decimal(str(sess.ending_redeemable))

        # Fall back to last purchase starting balance checkpoint
        if checkpoint_dt is None and self.purchase_repo is not None:
            purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
            for p in purchases:
                if p.starting_sc_balance is None:
                    continue
                if Decimal(str(p.starting_sc_balance)) <= 0:
                    continue
                p_dt = to_dt(p.purchase_date, p.purchase_time)
                if p_dt < cutoff and (checkpoint_dt is None or p_dt > checkpoint_dt):
                    checkpoint_dt = p_dt
                    expected_total = Decimal(str(p.starting_sc_balance))
                    expected_redeemable = Decimal(str(p.starting_sc_balance))

        # Apply purchases/redemptions after checkpoint up to cutoff
        if self.purchase_repo is not None:
            purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
            for p in purchases:
                p_dt = to_dt(p.purchase_date, p.purchase_time)
                if p_dt <= cutoff and (checkpoint_dt is None or p_dt > checkpoint_dt):
                    sc_amount = Decimal(str(p.sc_received))
                    expected_total += sc_amount

        if self.redemption_repo is not None:
            redemptions = self.redemption_repo.get_by_user_and_site(user_id, site_id)
            for r in redemptions:
                r_dt = to_dt(r.redemption_date, r.redemption_time)
                if r_dt <= cutoff and (checkpoint_dt is None or r_dt > checkpoint_dt):
                    amount = Decimal(str(r.amount))
                    expected_total -= amount
                    expected_redeemable -= amount

        expected_total = max(Decimal("0.00"), expected_total)
        expected_redeemable = max(Decimal("0.00"), expected_redeemable)
        return expected_total, expected_redeemable
    
    def _calculate_session_pl(self, session: GameSession, user_id: int, site_id: int) -> None:
        """
        Calculate net taxable P/L for session using CORRECT algorithm from business_logic.py
        
        Formula: net_taxable_pl = ((discoverable_sc + delta_play_sc) * sc_rate) - basis_consumed
        
        Where:
        - discoverable_sc = max(0, starting_redeemable - expected_start_redeemable)
        - delta_play_sc = ending_redeemable - starting_redeemable
        - basis_consumed = based on locked SC processing
        """
        self._recalculate_closed_sessions_for_pair(user_id, site_id)

    def _to_dt(self, d: date, t: Optional[str]) -> Optional[datetime]:
        if not d:
            return None
        time_str = t or "00:00:00"
        if len(time_str) == 5:
            time_str = f"{time_str}:00"
        return datetime.combine(d, datetime.strptime(time_str, "%H:%M:%S").time())

    def _load_pair_events(self, user_id: int, site_id: int):
        purchases = []
        redemptions = []

        if self.purchase_repo is not None:
            for p in self.purchase_repo.get_by_user_and_site(user_id, site_id):
                dt = self._to_dt(p.purchase_date, p.purchase_time)
                cash_amt = Decimal(str(p.amount))
                sc_amt = Decimal(str(p.sc_received))
                purchases.append((dt, cash_amt, sc_amt))

        if self.redemption_repo is not None:
            for r in self.redemption_repo.get_by_user_and_site(user_id, site_id):
                dt = self._to_dt(r.redemption_date, r.redemption_time)
                amt = Decimal(str(r.amount))
                redemptions.append((dt, amt))

        purchases.sort(key=lambda x: (x[0] or datetime.min))
        redemptions.sort(key=lambda x: (x[0] or datetime.min))
        return purchases, redemptions

    def _recalculate_closed_sessions_for_pair(self, user_id: int, site_id: int) -> None:
        sessions = self.session_repo.get_chronological(user_id, site_id)
        purchases, redemptions = self._load_pair_events(user_id, site_id)

        last_end_total = Decimal("0.00")
        last_end_redeem = Decimal("0.00")
        checkpoint_end_dt = None
        pending_basis_pool = Decimal("0.00")

        sc_rate = Decimal("1.00")
        if self.site_repo:
            site = self.site_repo.get_by_id(site_id)
            if site:
                sc_rate = Decimal(str(getattr(site, "sc_rate", "1.0")))

        def in_window(dt, start_exclusive, end_inclusive):
            if dt is None:
                return False
            if start_exclusive is not None and dt < start_exclusive:
                return False
            return dt <= end_inclusive

        for sess in sessions:
            if sess.status != "Closed":
                continue

            start_dt = self._to_dt(sess.session_date, sess.session_time)
            end_dt = self._to_dt(sess.end_date or sess.session_date, sess.end_time or sess.session_time)
            if end_dt is None:
                end_dt = start_dt

            red_between = sum(
                (amt for (dt, amt) in redemptions if in_window(dt, checkpoint_end_dt, start_dt)),
                Decimal("0.00"),
            )
            pur_sc_to_start = sum(
                (sc for (dt, amt, sc) in purchases if in_window(dt, checkpoint_end_dt, start_dt)),
                Decimal("0.00"),
            )
            pur_cash_to_end = sum(
                (amt for (dt, amt, sc) in purchases if in_window(dt, checkpoint_end_dt, end_dt)),
                Decimal("0.00"),
            )

            expected_start_total = (last_end_total - red_between) + pur_sc_to_start
            expected_start_redeem = (last_end_redeem - red_between)
            expected_start_total = max(Decimal("0.00"), expected_start_total)
            expected_start_redeem = max(Decimal("0.00"), expected_start_redeem)

            start_total = Decimal(str(sess.starting_balance))
            end_total = Decimal(str(sess.ending_balance))
            start_red = Decimal(str(sess.starting_redeemable))
            end_red = Decimal(str(sess.ending_redeemable))

            delta_total = end_total - start_total
            delta_redeem = end_red - start_red

            session_basis = pur_cash_to_end

            pending_basis_pool += session_basis
            if pending_basis_pool < 0:
                pending_basis_pool = Decimal("0.00")

            discoverable_sc = max(Decimal("0.00"), start_red - expected_start_redeem)
            locked_start = max(Decimal("0.00"), start_total - start_red)
            locked_end = max(Decimal("0.00"), end_total - end_red)
            locked_processed_sc = max(Decimal("0.00"), locked_start - locked_end)
            locked_processed_value = locked_processed_sc * sc_rate
            basis_consumed = min(pending_basis_pool, locked_processed_value)
            pending_basis_pool = max(Decimal("0.00"), pending_basis_pool - basis_consumed)

            net_taxable_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed

            sess.expected_start_total = expected_start_total
            sess.expected_start_redeemable = expected_start_redeem
            sess.discoverable_sc = discoverable_sc
            sess.delta_total = delta_total
            sess.delta_redeem = delta_redeem
            sess.session_basis = session_basis
            sess.basis_consumed = basis_consumed
            sess.net_taxable_pl = net_taxable_pl

            self.session_repo.update(sess)

            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt
    
    def recalculate_all_sessions(self, user_id: Optional[int] = None, site_id: Optional[int] = None) -> int:
        """
        Recalculate P/L for all sessions (or filtered by user/site)
        
        IMPORTANT: Sessions must be processed in chronological order
        because each session's expected_start depends on the previous session's ending.
        
        Returns count of sessions updated
        """
        if not user_id or not site_id:
            # For now, require both user_id and site_id for correct calculation
            raise ValueError("recalculate_all_sessions requires both user_id and site_id")
        
        sessions = self.session_repo.get_chronological(user_id, site_id)
        count = 0
        
        for session in sessions:
            old_pl = session.net_taxable_pl
            self._calculate_session_pl(session, user_id, site_id)
            
            if session.net_taxable_pl != old_pl:
                self.session_repo.update(session)
                count += 1
        
        return count

    def recalculate_closed_sessions_for_pair(self, user_id: int, site_id: int) -> None:
        """Recalculate derived fields for closed sessions for one (user_id, site_id) pair."""
        self._recalculate_closed_sessions_for_pair(user_id, site_id)

