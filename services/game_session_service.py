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
                 redemption_repo=None,
                 tax_withholding_service=None,
                 adjustment_service=None):
        self.session_repo = session_repo
        self.site_repo = site_repo
        self.fifo_service = fifo_service
        self.purchase_repo = purchase_repo
        self.redemption_repo = redemption_repo
        self.tax_withholding_service = tax_withholding_service
        self.adjustment_service = adjustment_service
    
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
        wager_amount: Decimal = Decimal("0.00"),
        rtp: Optional[float] = None,
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

        # IMPORTANT: Reactivate any dormant purchases for this site/user
        # When starting a new session, dormant SC becomes active again (matches legacy behavior)
        self.session_repo.db.execute(
            """
            UPDATE purchases
            SET status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE site_id = ? AND user_id = ? AND status = 'dormant'
            """,
            (site_id, user_id),
        )

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
            wager_amount=wager_amount,
            rtp=rtp,
            session_time=session_time,
            notes=notes
        )
        
        # Save to database
        created = self.session_repo.create(session)

        # Calculate P/L if requested (recompute chain per legacy algorithm)
        if calculate_pl:
            self._recalculate_closed_sessions_for_pair_from(
                user_id,
                site_id,
                session_date,
                session_time,
            )
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
        wager_amount: Optional[Decimal] = None,
        rtp: Optional[float] = None,
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

        old_session_date = session.session_date
        old_session_time = session.session_time
        old_user_id = session.user_id
        old_site_id = session.site_id
        old_status = session.status
        old_game_id = session.game_id
        old_wager = session.wager_amount
        old_delta_total = session.delta_total
        old_end_date = session.end_date  # Capture for tax recalculation
        
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
        if wager_amount is not None:
            session.wager_amount = wager_amount
        if rtp is not None:
            session.rtp = rtp
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
            start_date, start_time = self._earliest_boundary_with_containing(
                session.site_id,
                session.user_id,
                old_session_date,
                old_session_time,
                session.session_date,
                session.session_time,
            )

            self._recalculate_closed_sessions_for_pair_from(
                session.user_id,
                session.site_id,
                start_date,
                start_time,
            )

            if old_user_id != session.user_id or old_site_id != session.site_id:
                old_start_date, old_start_time = self._containing_boundary(
                    old_site_id,
                    old_user_id,
                    old_session_date,
                    old_session_time,
                )
                self._recalculate_closed_sessions_for_pair_from(
                    old_user_id,
                    old_site_id,
                    old_start_date,
                    old_start_time,
                )
            
            # Sync daily_sessions and recalculate tax when:
            # 1. Closing a session for the first time
            # 2. Editing an already-closed session (P/L may have changed)
            if target_status == "Closed":
                # Use end_date for tax accounting (when session closed), not session_date (when started)
                accounting_date = session.end_date or session.session_date
                self._sync_daily_sessions_for_pair(session.user_id, session.site_id, accounting_date)
                
                # Also sync old date if the session moved to a different end_date
                old_end_date = old_end_date if old_end_date else old_session_date
                if old_status == "Closed" and old_end_date != accounting_date:
                    self._sync_daily_sessions_for_pair(old_user_id, old_site_id, old_end_date)
                
                # Recalculate tax for affected dates (if tax withholding is enabled)
                if hasattr(self, 'tax_withholding_service'):
                    try:
                        tax_service = self.tax_withholding_service
                        config = tax_service.get_config()
                        if config.enabled:
                            # Recalculate tax for current date
                            date_str = accounting_date.isoformat() if hasattr(accounting_date, 'isoformat') else str(accounting_date)
                            tax_service.apply_to_date(session_date=date_str)
                            
                            # If session moved to different date, recalculate old date too
                            if old_status == "Closed" and old_end_date != accounting_date:
                                old_date_str = old_end_date.isoformat() if hasattr(old_end_date, 'isoformat') else str(old_end_date)
                                tax_service.apply_to_date(session_date=old_date_str)
                    except Exception:
                        pass  # Don't fail the update if tax calculation fails
            
            refreshed = self.session_repo.get_by_id(session_id)
            if refreshed:
                self._sync_game_rtp(
                    old_status,
                    old_game_id,
                    old_wager,
                    old_delta_total,
                    refreshed,
                )
                return refreshed
            return updated

        return updated
    
    def delete_session(self, session_id: int) -> None:
        """Delete a session"""
        session = self.session_repo.get_by_id(session_id)
        if session:
            self._remove_session_from_game_rtp(session)
        self.session_repo.delete(session_id)
    
    def delete_sessions_bulk(self, session_ids: List[int]) -> None:
        """Delete multiple sessions efficiently in a single transaction"""
        if not session_ids:
            return
        
        # Fetch all sessions first
        sessions = [self.session_repo.get_by_id(sid) for sid in session_ids]
        
        # Remove from RTP aggregates
        for session in sessions:
            if session:
                self._remove_session_from_game_rtp(session)
        
        # Delete all sessions in one transaction
        conn = self.session_repo.db._connection
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(session_ids))
        cursor.execute(f"DELETE FROM game_sessions WHERE id IN ({placeholders})", session_ids)
        conn.commit()
    
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
        session_time: str,
        exclude_purchase_id: Optional[int] = None
    ) -> Tuple[Decimal, Decimal]:
        """Compute expected starting total/redeemable balances for a session
        
        Args:
            exclude_purchase_id: Optional purchase ID to exclude from the calculation.
                Used when editing a purchase to avoid including it in its own expected balance.
        """
        expected_total = Decimal("0.00")
        expected_redeemable = Decimal("0.00")

        def to_dt(d, t):
            time_str = t or "00:00:00"
            if len(time_str) == 5:
                time_str = f"{time_str}:00"
            return datetime.combine(d, datetime.strptime(time_str, "%H:%M:%S").time())

        cutoff = to_dt(session_date, session_time)
        checkpoint_dt = None

        # Priority 1: Balance checkpoint adjustments (explicit anchors)
        if self.adjustment_service is not None:
            latest_checkpoint = self.adjustment_service.get_latest_checkpoint_before(
                user_id, site_id, session_date, session_time
            )
            if latest_checkpoint:
                checkpoint_dt = to_dt(
                    latest_checkpoint.effective_date,
                    latest_checkpoint.effective_time
                )
                expected_total = latest_checkpoint.checkpoint_total_sc
                expected_redeemable = latest_checkpoint.checkpoint_redeemable_sc

        # Priority 2: Last closed session as checkpoint (legacy behavior, only if no adjustment checkpoint)
        if checkpoint_dt is None:
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
        # NOTE: starting_sc_balance is the POST-purchase balance (what user sees on site after purchase)
        # We use the purchase BEFORE this as the checkpoint, not the purchase itself
        if checkpoint_dt is None and self.purchase_repo is not None:
            purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
            for p in purchases:
                p_dt = to_dt(p.purchase_date, p.purchase_time)
                # Only use purchases that are BEFORE the cutoff as checkpoints
                # Don't use starting_sc_balance as a checkpoint - it causes double-counting
                if p_dt < cutoff:
                    pass  # Purchases will be added in the next section

        # Apply purchases/redemptions after checkpoint up to cutoff
        if self.purchase_repo is not None:
            purchases = self.purchase_repo.get_by_user_and_site(user_id, site_id)
            for p in purchases:
                # Skip the excluded purchase if specified
                if exclude_purchase_id is not None and p.id == exclude_purchase_id:
                    continue
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

            sess.rtp = self._compute_session_rtp(sess.wager_amount, delta_total)

            sess.expected_start_total = expected_start_total
            sess.expected_start_redeemable = expected_start_redeem
            sess.discoverable_sc = discoverable_sc
            sess.delta_total = delta_total
            sess.delta_redeem = delta_redeem
            sess.session_basis = session_basis
            sess.basis_consumed = basis_consumed
            sess.net_taxable_pl = net_taxable_pl

            if self.tax_withholding_service is not None:
                self.tax_withholding_service.apply_to_session_model(sess)

            self.session_repo.update(sess)

            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt

    def _normalize_time(self, value: Optional[str], default: str = "00:00:00") -> str:
        if not value:
            return default
        value = value.strip()
        if len(value) == 5:
            return f"{value}:00"
        return value

    def _find_containing_session_start(
        self,
        site_id: int,
        user_id: int,
        session_date: date,
        session_time: Optional[str],
    ) -> Optional[Tuple[date, str]]:
        if not hasattr(self.session_repo, "db"):
            return None
        ts_time = self._normalize_time(session_time)
        date_str = session_date.isoformat() if hasattr(session_date, "isoformat") else str(session_date)
        row = self.session_repo.db.fetch_one(
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
        old_date: date,
        old_time: Optional[str],
        new_date: date,
        new_time: Optional[str],
    ) -> Tuple[date, str]:
        old_boundary = self._containing_boundary(site_id, user_id, old_date, old_time)
        new_boundary = self._containing_boundary(site_id, user_id, new_date, new_time)
        if self._to_dt(new_boundary[0], new_boundary[1]) < self._to_dt(old_boundary[0], old_boundary[1]):
            return new_boundary
        return old_boundary

    def _recalculate_closed_sessions_for_pair_from(
        self,
        user_id: int,
        site_id: int,
        from_date,
        from_time: str = "00:00:00",
    ) -> None:
        sessions = self.session_repo.get_chronological(user_id, site_id)
        purchases, redemptions = self._load_pair_events(user_id, site_id)

        boundary_dt = self._to_dt(from_date, from_time)
        if boundary_dt is None:
            self._recalculate_closed_sessions_for_pair(user_id, site_id)
            return

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

            if start_dt is not None and start_dt < boundary_dt:
                last_end_total = Decimal(str(sess.ending_balance or 0))
                last_end_redeem = Decimal(str(sess.ending_redeemable or 0))
                session_basis = Decimal(str(sess.session_basis or 0))
                basis_consumed = Decimal(str(sess.basis_consumed or 0))
                pending_basis_pool += session_basis
                if pending_basis_pool < 0:
                    pending_basis_pool = Decimal("0.00")
                pending_basis_pool = max(Decimal("0.00"), pending_basis_pool - basis_consumed)
                checkpoint_end_dt = end_dt
                continue

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

            sess.rtp = self._compute_session_rtp(sess.wager_amount, delta_total)

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
        
        # After recalculating sessions, sync daily_sessions and tax for ALL affected dates
        self._sync_tax_for_affected_dates(user_id, site_id, from_date)
    
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

    def calculate_session_pl(self, session: GameSession) -> Decimal:
        """Return simple P/L based on total in/out (legacy helper for tests)."""
        return session.calculated_pl

    def recalculate_closed_sessions_for_pair(self, user_id: int, site_id: int) -> None:
        """Recalculate derived fields for closed sessions for one (user_id, site_id) pair."""
        self._recalculate_closed_sessions_for_pair(user_id, site_id)

    def recalculate_closed_sessions_for_pair_from(
        self,
        user_id: int,
        site_id: int,
        from_date,
        from_time: str = "00:00:00",
    ) -> None:
        """Recalculate derived fields for closed sessions from a boundary date/time."""
        self._recalculate_closed_sessions_for_pair_from(user_id, site_id, from_date, from_time)

    def _compute_session_rtp(self, wager_amount: Decimal, delta_total: Decimal) -> Optional[float]:
        if wager_amount is None:
            return None
        try:
            wager_val = Decimal(str(wager_amount))
        except Exception:
            return None
        if wager_val <= 0:
            return None
        try:
            delta_val = Decimal(str(delta_total))
        except Exception:
            delta_val = Decimal("0.00")
        return float(((wager_val + delta_val) / wager_val) * Decimal("100"))

    def _sync_game_rtp(
        self,
        old_status: Optional[str],
        old_game_id: Optional[int],
        old_wager: Optional[Decimal],
        old_delta_total: Optional[Decimal],
        refreshed: GameSession,
    ) -> None:
        new_status = refreshed.status
        if new_status != "Closed":
            return

        new_game_id = refreshed.game_id
        new_wager = refreshed.wager_amount
        new_delta_total = refreshed.delta_total

        if old_status != "Closed" and new_game_id:
            self.update_game_rtp_incremental(
                new_game_id,
                float(new_wager or 0),
                float(new_delta_total or 0),
                new_session=True,
            )
            return

        if new_status == "Closed":
            self._update_session_rtp_only(
                old_game_id,
                old_wager,
                old_delta_total,
                new_game_id,
                new_wager,
                new_delta_total,
            )

    def _update_session_rtp_only(
        self,
        old_game_id: Optional[int],
        old_wager: Optional[Decimal],
        old_delta_total: Optional[Decimal],
        new_game_id: Optional[int],
        new_wager: Optional[Decimal],
        new_delta_total: Optional[Decimal],
    ) -> None:
        if old_game_id is None and new_game_id is None:
            return

        old_wager_val = float(old_wager or 0)
        old_delta_val = float(old_delta_total or 0)
        new_wager_val = float(new_wager or 0)
        new_delta_val = float(new_delta_total or 0)

        if old_game_id != new_game_id:
            if old_game_id:
                self.update_game_rtp_incremental(old_game_id, -old_wager_val, -old_delta_val, new_session=False)
            if new_game_id:
                self.update_game_rtp_incremental(new_game_id, new_wager_val, new_delta_val, new_session=False)
        else:
            if new_game_id:
                wager_delta = new_wager_val - old_wager_val
                delta_delta = new_delta_val - old_delta_val
                if wager_delta or delta_delta:
                    self.update_game_rtp_incremental(new_game_id, wager_delta, delta_delta, new_session=False)

    def _sync_daily_sessions_for_pair(self, user_id: int, site_id: int, session_date: date) -> None:
        """Synchronize daily_sessions entry for a specific date+user when session is closed.
        
        Uses INSERT OR REPLACE to handle both new and existing rows.
        Notes are stored in daily_date_tax table (not here).
        Tax data is now stored in daily_date_tax table (see TaxWithholdingService).
        """
        # Check if daily_sessions table exists first (for tests/old DBs)
        cursor = self.session_repo.db._connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_sessions'")
        if not cursor.fetchone():
            return  # Table doesn't exist, skip sync
        
        self.session_repo.db.execute(
            """
            INSERT OR REPLACE INTO daily_sessions (
                session_date, 
                user_id, 
                net_daily_pnl, 
                num_game_sessions
            )
            SELECT 
                gs.end_date,
                gs.user_id,
                SUM(COALESCE(gs.net_taxable_pl, 0)) as net_daily_pnl,
                COUNT(*) as num_game_sessions
            FROM game_sessions gs
            WHERE gs.status = 'Closed' 
              AND gs.end_date IS NOT NULL
              AND gs.user_id = ? 
              AND gs.end_date = ?
            GROUP BY gs.end_date, gs.user_id
            """,
            (user_id, session_date)
        )
    
    def _sync_tax_for_affected_dates(self, user_id: int, site_id: int, from_date) -> None:
        """Sync daily_sessions and recalculate tax for all dates from boundary onwards.
        
        Called after cascade recalculations (e.g., after purchase/redemption edits)
        to ensure tax withholding reflects updated session P/L.
        """
        # Get all distinct end_dates for this user/site from boundary onwards
        boundary_str = from_date.isoformat() if hasattr(from_date, 'isoformat') else str(from_date)
        
        rows = self.session_repo.db.fetch_all(
            """
            SELECT DISTINCT end_date
            FROM game_sessions
            WHERE user_id = ?
              AND site_id = ?
              AND status = 'Closed'
              AND end_date IS NOT NULL
              AND end_date >= ?
            """,
            (user_id, site_id, boundary_str)
        )
        
        # Sync daily_sessions and recalculate tax for each affected date
        for row in rows:
            end_date = row["end_date"]
            self._sync_daily_sessions_for_pair(user_id, site_id, end_date)
            
            # Recalculate tax if enabled
            if hasattr(self, 'tax_withholding_service'):
                try:
                    tax_service = self.tax_withholding_service
                    config = tax_service.get_config()
                    if config.enabled:
                        tax_service.apply_to_date(session_date=end_date)
                except Exception:
                    pass  # Don't fail cascade if tax calc fails

    def update_game_rtp_incremental(
        self,
        game_id: int,
        wager_delta: float,
        delta_total_delta: float,
        new_session: bool = False,
        conn=None,
    ) -> None:
        if not game_id:
            return
        close_conn = False
        if conn is None:
            conn = self.session_repo.db._connection
            close_conn = True
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM game_rtp_aggregates WHERE game_id = ?", (game_id,))
        agg_row = cursor.fetchone()

        if agg_row is None:
            total_wager = max(0.0, float(wager_delta))
            total_delta = float(delta_total_delta)
            session_count = 1 if new_session else 0
            cursor.execute(
                """
                INSERT INTO game_rtp_aggregates (game_id, total_wager, total_delta, session_count)
                VALUES (?, ?, ?, ?)
                """,
                (game_id, total_wager, total_delta, session_count),
            )
        else:
            total_wager = float(agg_row["total_wager"]) + float(wager_delta)
            total_delta = float(agg_row["total_delta"]) + float(delta_total_delta)
            session_count = int(agg_row["session_count"]) + (1 if new_session else 0)
            total_wager = max(0.0, total_wager)
            cursor.execute(
                """
                UPDATE game_rtp_aggregates
                SET total_wager = ?, total_delta = ?, session_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE game_id = ?
                """,
                (total_wager, total_delta, session_count, game_id),
            )

        self._recalculate_game_rtp_from_aggregates(game_id, conn)
        if close_conn:
            conn.commit()

    def _recalculate_game_rtp_from_aggregates(self, game_id: int, conn=None) -> None:
        close_conn = False
        if conn is None:
            conn = self.session_repo.db._connection
            close_conn = True
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM game_rtp_aggregates WHERE game_id = ?", (game_id,))
        agg_row = cursor.fetchone()
        if agg_row is None:
            actual_rtp = 0.0
        else:
            total_wager = float(agg_row["total_wager"])
            total_delta = float(agg_row["total_delta"])
            actual_rtp = ((total_wager + total_delta) / total_wager) * 100.0 if total_wager > 0 else 0.0
        cursor.execute("UPDATE games SET actual_rtp = ? WHERE id = ?", (actual_rtp, game_id))
        if close_conn:
            conn.commit()

    def recalculate_game_rtp_full(self, game_id: int) -> None:
        conn = self.session_repo.db._connection
        cursor = conn.cursor()
        cursor.execute("DELETE FROM game_rtp_aggregates WHERE game_id = ?", (game_id,))
        cursor.execute(
            """
            SELECT SUM(COALESCE(wager_amount, 0)) as total_wager,
                   SUM(COALESCE(delta_total, 0)) as total_delta,
                   COUNT(*) as session_count
            FROM game_sessions
            WHERE game_id = ? AND status = 'Closed'
            """,
            (game_id,),
        )
        row = cursor.fetchone()
        total_wager = float(row["total_wager"] or 0)
        total_delta = float(row["total_delta"] or 0)
        session_count = int(row["session_count"] or 0)
        if session_count > 0 or total_wager > 0:
            cursor.execute(
                """
                INSERT INTO game_rtp_aggregates (game_id, total_wager, total_delta, session_count)
                VALUES (?, ?, ?, ?)
                """,
                (game_id, total_wager, total_delta, session_count),
            )
        self._recalculate_game_rtp_from_aggregates(game_id, conn)
        conn.commit()

    def _remove_session_from_game_rtp(self, session: GameSession) -> None:
        if not session or session.status != "Closed" or not session.game_id:
            return
        wager_val = float(session.wager_amount or 0)
        delta_val = float(session.delta_total or 0)
        conn = self.session_repo.db._connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM game_rtp_aggregates WHERE game_id = ?", (session.game_id,))
        agg_row = cursor.fetchone()
        if agg_row is None:
            return
        total_wager = max(0.0, float(agg_row["total_wager"]) - wager_val)
        total_delta = float(agg_row["total_delta"]) - delta_val
        session_count = max(0, int(agg_row["session_count"]) - 1)
        cursor.execute(
            """
            UPDATE game_rtp_aggregates
            SET total_wager = ?, total_delta = ?, session_count = ?, last_updated = CURRENT_TIMESTAMP
            WHERE game_id = ?
            """,
            (total_wager, total_delta, session_count, session.game_id),
        )
        self._recalculate_game_rtp_from_aggregates(session.game_id, conn)
        conn.commit()

    def get_deletion_impact(self, session_id: int) -> str:
        """
        Check if deleting a session would affect subsequent redemptions.

        This method replaces direct UI cursor access to check deletion impact.

        Args:
            session_id: ID of game session to check

        Returns:
            Formatted impact message string, or empty string if no impact
        """
        try:
            session = self.session_repo.get_by_id(session_id)
            if not session or session.status != "Closed":
                return ""

            # Get redemptions after this session
            cursor = self.session_repo.db._connection.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count, SUM(amount) as total
                FROM redemptions
                WHERE site_id = ? AND user_id = ?
                  AND (redemption_date > ? 
                       OR (redemption_date = ? AND redemption_time > ?))
                """,
                (session.site_id, session.user_id, 
                 session.end_date, session.end_date, session.end_time)
            )
            result = cursor.fetchone()

            if result and result["count"] > 0:
                count = result["count"]
                total = Decimal(str(result["total"] or 0))
                ending_balance = Decimal(str(session.ending_balance or 0))

                # Calculate what expected balance would be without this session
                # Import here to avoid circular import
                from app_facade import AppFacade
                
                # Note: This is not ideal but matches current UI pattern
                # In a proper refactor, we'd pass a compute service or extract this logic
                # For now, we replicate the minimal logic needed
                from repositories.database import DatabaseManager
                db = self.session_repo.db
                prev_row = db.fetch_one(
                    """
                    SELECT ending_balance
                    FROM game_sessions
                    WHERE site_id = ? AND user_id = ?
                      AND (session_date < ? OR (session_date = ? AND COALESCE(session_time,'00:00:00') < ?))
                      AND status = 'Closed'
                    ORDER BY session_date DESC, COALESCE(session_time,'00:00:00') DESC
                    LIMIT 1
                    """,
                    (session.site_id, session.user_id, session.session_date, 
                     session.session_date, session.session_time or '00:00:00')
                )
                expected_total = Decimal(str(prev_row["ending_balance"])) if prev_row else Decimal("0")

                # Get site and user names for the message
                site_name = "Unknown"
                user_name = "Unknown"
                if self.site_repo:
                    site = self.site_repo.get_by_id(session.site_id)
                    if site:
                        site_name = site.name
                
                user_row = db.fetch_one("SELECT name FROM users WHERE id = ?", (session.user_id,))
                if user_row:
                    user_name = user_row["name"]

                msg = f"Session: {site_name} / {user_name}\n"
                msg += f"Session ended with {float(ending_balance):,.2f} SC\n"
                msg += f"Found {count} redemption(s) after this session totaling ${float(total):,.2f}\n\n"
                msg += f"If you delete this session:\n"
                msg += f"• Expected balance drops to {float(expected_total):,.2f} SC\n"
                msg += f"• Redemptions may temporarily exceed expected balance\n"
                msg += f"• You won't be able to edit redemptions until you fix the gap"

                return msg
            return ""
        except Exception as e:
            print(f"Error checking game session deletion impact: {e}")
            return ""


