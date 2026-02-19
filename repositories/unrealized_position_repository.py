"""
Repository for querying unrealized positions (open positions with SC remaining)
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime

from tools.timezone_utils import get_configured_timezone_name, utc_date_time_to_local

from models.unrealized_position import UnrealizedPosition


class UnrealizedPositionRepository:
    """Repository for querying unrealized positions"""
    
    def __init__(self, db):
        self.db = db

    def _get_profit_only_position_start(self, site_id: int, user_id: int, tz_name: str) -> tuple[Optional[date], Optional[datetime]]:
        """Best-effort start date for profit-only positions (remaining basis == 0).

        When FIFO has consumed all basis, the "oldest purchase with remaining basis" is undefined.
        In practice, users want to see the purchase(s) that most recently contributed basis to the
        current on-site balance.

        We approximate this by finding the most recent non-free-SC redemption with FIFO allocations
        and returning the latest purchase datetime among its allocated purchases.
        """
        query = """
            SELECT p.purchase_date,
                   COALESCE(p.purchase_time, '00:00:00') as purchase_time
            FROM redemptions r
            JOIN redemption_allocations ra ON ra.redemption_id = r.id
            JOIN purchases p ON p.id = ra.purchase_id
            WHERE r.site_id = ? AND r.user_id = ?
              AND r.deleted_at IS NULL
                            AND r.canceled_at IS NULL
              AND r.is_free_sc = 0
              AND CAST(ra.allocated_amount AS REAL) > 0
              AND p.deleted_at IS NULL
              AND (p.status IS NULL OR p.status = 'active')
              AND r.id = (
                  SELECT r2.id
                  FROM redemptions r2
                  WHERE r2.site_id = ? AND r2.user_id = ?
                    AND r2.deleted_at IS NULL
                                        AND r2.canceled_at IS NULL
                    AND r2.is_free_sc = 0
                    AND EXISTS (
                        SELECT 1 FROM redemption_allocations ra2
                        WHERE ra2.redemption_id = r2.id
                          AND CAST(ra2.allocated_amount AS REAL) > 0
                    )
                  ORDER BY r2.redemption_date DESC,
                           COALESCE(r2.redemption_time, '00:00:00') DESC,
                           r2.id DESC
                  LIMIT 1
              )
            ORDER BY p.purchase_date DESC,
                     COALESCE(p.purchase_time, '00:00:00') DESC,
                     p.id DESC
            LIMIT 1
        """
        row = self.db.fetch_one(query, (site_id, user_id, site_id, user_id))
        if not row or not row.get("purchase_date"):
            return None, None
        start_dt_utc = self._to_dt(row["purchase_date"], row["purchase_time"])
        start_date_local = self._to_local_date(row["purchase_date"], row["purchase_time"], tz_name)
        return start_date_local, start_dt_utc
    
    def get_all_positions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[UnrealizedPosition]:
        """
        Get all unrealized positions (site/user with SC remaining on site).
        
        Positions are shown when estimated total SC > threshold, even if remaining basis is $0
        (allows for partial redemptions that consumed all basis but left profit-only SC).
        
        Excludes positions with explicit "Balance Closed" marker.
        """
        if not self.db:
            return []
        
        positions = []
        tz_name = get_configured_timezone_name()

        notes_map = self._get_notes_map()
        
        # Get all site/user combinations with any purchase, session, or redemption activity
        # (not limited to only purchases with remaining_amount > 0)
        query = """
            SELECT DISTINCT
                site_id,
                user_id
            FROM (
                SELECT site_id, user_id FROM purchases WHERE deleted_at IS NULL AND (status IS NULL OR status = 'active')
                UNION
                SELECT site_id, user_id FROM game_sessions WHERE deleted_at IS NULL
                UNION
                SELECT site_id, user_id FROM redemptions WHERE deleted_at IS NULL AND canceled_at IS NULL
            ) combined
        """
        
        candidate_pairs = self.db.fetch_all(query)
        
        # For each candidate, compute remaining basis and estimated SC
        for pair in candidate_pairs:
            site_id = pair['site_id']
            user_id = pair['user_id']
            
            # Get site and user names
            site_user_query = """
                SELECT s.name as site_name, u.name as user_name
                FROM sites s, users u
                WHERE s.id = ? AND u.id = ?
            """
            names = self.db.fetch_one(site_user_query, (site_id, user_id))
            if not names:
                continue
            
            site_name = names['site_name']
            user_name = names['user_name']
            
            # Get remaining basis and start date (local date for filtering/display)
            basis_query = """
                SELECT COALESCE(SUM(remaining_amount), 0) as remaining_basis
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND deleted_at IS NULL
                  AND (status IS NULL OR status = 'active')
                  AND remaining_amount > 0.001
            """

            basis_data = self.db.fetch_one(basis_query, (site_id, user_id))
            remaining_basis = Decimal(str(basis_data['remaining_basis'] or 0)) if basis_data else Decimal("0.00")
            position_start_date = None
            position_start_dt_utc = None

            if remaining_basis > Decimal("0.001"):
                earliest_remaining_query = """
                    SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND deleted_at IS NULL
                      AND (status IS NULL OR status = 'active')
                      AND remaining_amount > 0.001
                    ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
                    LIMIT 1
                """
                earliest_remaining = self.db.fetch_one(earliest_remaining_query, (site_id, user_id))
                if earliest_remaining and earliest_remaining.get("purchase_date"):
                    position_start_dt_utc = self._to_dt(
                        earliest_remaining["purchase_date"],
                        earliest_remaining["purchase_time"],
                    )
                    position_start_date = self._to_local_date(
                        earliest_remaining["purchase_date"],
                        earliest_remaining["purchase_time"],
                        tz_name,
                    )

            if not position_start_date:
                if remaining_basis <= Decimal("0.001"):
                    profit_only_start, profit_only_dt = self._get_profit_only_position_start(
                        site_id,
                        user_id,
                        tz_name,
                    )
                    if profit_only_start:
                        position_start_date = profit_only_start
                        position_start_dt_utc = profit_only_dt

            if not position_start_date:
                earliest_purchase_query = """
                    SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND deleted_at IS NULL
                      AND (status IS NULL OR status = 'active')
                    ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
                    LIMIT 1
                """
                earliest = self.db.fetch_one(earliest_purchase_query, (site_id, user_id))
                if earliest and earliest.get("purchase_date"):
                    position_start_dt_utc = self._to_dt(earliest["purchase_date"], earliest["purchase_time"])
                    position_start_date = self._to_local_date(
                        earliest["purchase_date"],
                        earliest["purchase_time"],
                        tz_name,
                    )
            
            # If still no start date, skip (no purchase activity)
            if not position_start_date:
                continue
            
            # Find the most recent checkpoint among:
            # 1) Purchase snapshots (starting_sc_balance)
            # 2) Session starts (starting_balance + starting_redeemable)
            # 3) Session ends (ending_balance + ending_redeemable, Closed only)
            checkpoint = self._get_latest_checkpoint(site_id, user_id)
            
            if not checkpoint:
                # No checkpoints available - fallback to sum of purchases
                purchase_sum_query = """
                    SELECT COALESCE(SUM(sc_received), 0) as total_sc
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                        AND deleted_at IS NULL
                      AND (status IS NULL OR status = 'active')
                """
                purchase_data = self.db.fetch_one(purchase_sum_query, (site_id, user_id))
                total_sc = Decimal(str(purchase_data['total_sc'] or 0))
                redeemable_sc = Decimal("0.00")
                
                last_purchase_query = """
                    SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                                            AND deleted_at IS NULL
                      AND (status IS NULL OR status = 'active')
                    ORDER BY purchase_date DESC, COALESCE(purchase_time,'00:00:00') DESC, id DESC
                    LIMIT 1
                """
                last_purchase = self.db.fetch_one(last_purchase_query, (site_id, user_id))
                last_activity = last_purchase['purchase_date'] if last_purchase else None
                last_activity_time = last_purchase['purchase_time'] if last_purchase else None
                last_activity_dt = self._to_dt(last_activity, last_activity_time) if last_activity else None
                last_activity = self._to_local_date_from_dt(last_activity_dt, tz_name) if last_activity_dt else None
            else:
                # Use checkpoint + deltas
                checkpoint_dt = checkpoint['checkpoint_dt']
                checkpoint_date = checkpoint_dt.date()
                checkpoint_time = checkpoint_dt.strftime("%H:%M:%S")
                baseline_total = checkpoint['total_sc']
                baseline_redeemable = checkpoint['redeemable_sc']
                checkpoint_purchase_id = checkpoint.get('checkpoint_purchase_id')  # None if not a purchase checkpoint
                
                # Get purchases after checkpoint (exclude checkpoint purchase if it's the checkpoint source)
                if checkpoint_purchase_id is not None:
                    purchases_after_query = """
                        SELECT COALESCE(SUM(sc_received), 0) as total_sc
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
                          AND deleted_at IS NULL
                          AND (status IS NULL OR status = 'active')
                          AND id != ?
                          AND (
                              purchase_date > ? 
                              OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') > ?)
                          )
                    """
                    purchases_after = self.db.fetch_one(
                        purchases_after_query,
                        (site_id, user_id, checkpoint_purchase_id, checkpoint_date, checkpoint_date, checkpoint_time)
                    )
                else:
                    purchases_after_query = """
                        SELECT COALESCE(SUM(sc_received), 0) as total_sc
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
                          AND deleted_at IS NULL
                          AND (status IS NULL OR status = 'active')
                          AND (
                              purchase_date > ? 
                              OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') > ?)
                          )
                    """
                    purchases_after = self.db.fetch_one(
                        purchases_after_query,
                        (site_id, user_id, checkpoint_date, checkpoint_date, checkpoint_time)
                    )
                purchases_since = Decimal(str(purchases_after['total_sc'] or 0))
                
                # Get redemptions after checkpoint (all redemptions affect total SC)
                redemptions_after_query = """
                    SELECT COALESCE(SUM(amount), 0) as total_redeemed
                    FROM redemptions
                    WHERE site_id = ? AND user_id = ?
                      AND deleted_at IS NULL
                                            AND canceled_at IS NULL
                      AND (
                          redemption_date > ?
                          OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') > ?)
                      )
                """
                redemptions_after = self.db.fetch_one(
                    redemptions_after_query,
                    (site_id, user_id, checkpoint_date, checkpoint_date, checkpoint_time)
                )
                redemptions_since = Decimal(str(redemptions_after['total_redeemed'] or 0))
                
                # Get redeemable redemptions after checkpoint (only non-free-SC redemptions affect redeemable balance)
                redeemable_redemptions_after_query = """
                    SELECT COALESCE(SUM(amount), 0) as redeemable_redeemed
                    FROM redemptions
                    WHERE site_id = ? AND user_id = ?
                      AND deleted_at IS NULL
                                            AND canceled_at IS NULL
                      AND is_free_sc = 0
                      AND (
                          redemption_date > ?
                          OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') > ?)
                      )
                """
                redeemable_redemptions_after = self.db.fetch_one(
                    redeemable_redemptions_after_query,
                    (site_id, user_id, checkpoint_date, checkpoint_date, checkpoint_time)
                )
                redeemable_redemptions_since = Decimal(str(redeemable_redemptions_after['redeemable_redeemed'] or 0))
                
                # Compute estimated SC
                # baseline_total from purchase checkpoint is starting_sc_balance (POST-purchase balance)
                # The checkpoint purchase is excluded from purchases_since (id != ?) to avoid double-counting
                total_sc = baseline_total + purchases_since - redemptions_since
                
                # Redeemable: use checkpoint redeemable minus redemptions if checkpoint is within current position
                position_start_dt = position_start_dt_utc
                if checkpoint_dt and position_start_dt and checkpoint_dt >= position_start_dt:
                    redeemable_sc = baseline_redeemable - redeemable_redemptions_since
                else:
                    redeemable_sc = Decimal("0.00")
                
                # Determine last activity
                last_activity_candidates = [(checkpoint_date, checkpoint_time)]
                
                if purchases_since > 0:
                    last_purchase_query = """
                        SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
                                                    AND deleted_at IS NULL
                          AND (status IS NULL OR status = 'active')
                        ORDER BY purchase_date DESC, COALESCE(purchase_time,'00:00:00') DESC, id DESC
                        LIMIT 1
                    """
                    last_purchase = self.db.fetch_one(last_purchase_query, (site_id, user_id))
                    if last_purchase:
                        last_activity_candidates.append((last_purchase['purchase_date'], last_purchase['purchase_time']))
                
                if redemptions_since > 0:
                    last_redemption_query = """
                        SELECT redemption_date, COALESCE(redemption_time, '00:00:00') as redemption_time
                        FROM redemptions
                        WHERE site_id = ? AND user_id = ?
                          AND deleted_at IS NULL
                                                    AND canceled_at IS NULL
                        ORDER BY redemption_date DESC, COALESCE(redemption_time,'00:00:00') DESC, id DESC
                        LIMIT 1
                    """
                    last_redemption = self.db.fetch_one(last_redemption_query, (site_id, user_id))
                    if last_redemption:
                        last_activity_candidates.append((last_redemption['redemption_date'], last_redemption['redemption_time']))
                
                last_activity_dts = [self._to_dt(d, t) for d, t in last_activity_candidates if d]
                last_activity_dt = max(last_activity_dts) if last_activity_dts else checkpoint_dt
                if last_activity_dt:
                    last_activity = self._to_local_date_from_dt(last_activity_dt, tz_name)
                else:
                    last_activity = self._to_local_date(checkpoint_date, checkpoint_time, tz_name)

            close_balance_dt = self._get_close_balance_dt(site_id, user_id)
            if close_balance_dt and last_activity_dt and close_balance_dt >= last_activity_dt:
                continue
            
            # Get SC rate (default 1:1)
            site_query = "SELECT sc_rate FROM sites WHERE id = ?"
            site_data = self.db.fetch_one(site_query, (site_id,))
            sc_rate = Decimal(str(site_data['sc_rate'] if site_data and site_data['sc_rate'] else 1.0))
            
            # Calculate current value and unrealized P/L from total SC (not redeemable)
            current_value = total_sc * sc_rate
            unrealized_pl = current_value - remaining_basis
            
            # Skip if total SC is below threshold (effectively zero)
            # This allows positions with remaining_basis=0 but total_sc>0 to still appear
            sc_threshold = Decimal("0.01")
            if total_sc < sc_threshold:
                continue
            
            position = UnrealizedPosition(
                site_id=site_id,
                user_id=user_id,
                site_name=site_name,
                user_name=user_name,
                start_date=position_start_date,
                purchase_basis=remaining_basis,
                total_sc=total_sc,
                redeemable_sc=redeemable_sc,
                current_value=current_value,
                unrealized_pl=unrealized_pl,
                last_activity=last_activity,
                notes=notes_map.get((site_id, user_id), "")
            )
            
            positions.append(position)
        
        # Apply date filter to start_date
        if start_date:
            positions = [p for p in positions if p.start_date >= start_date]
        if end_date:
            positions = [p for p in positions if p.start_date <= end_date]
        
        return positions

    def update_notes(self, site_id: int, user_id: int, notes: str) -> None:
        existing = self.db.fetch_one(
            "SELECT id FROM unrealized_positions WHERE site_id = ? AND user_id = ?",
            (site_id, user_id),
        )
        if existing:
            self.db.execute(
                "UPDATE unrealized_positions SET notes = ?, updated_at = CURRENT_TIMESTAMP WHERE site_id = ? AND user_id = ?",
                (notes, site_id, user_id),
            )
        else:
            self.db.execute(
                "INSERT INTO unrealized_positions (site_id, user_id, notes) VALUES (?, ?, ?)",
                (site_id, user_id, notes),
            )

    def _get_notes_map(self):
        rows = self.db.fetch_all(
            "SELECT site_id, user_id, notes FROM unrealized_positions"
        )
        notes_map = {}
        for row in rows:
            notes_map[(row['site_id'], row['user_id'])] = row['notes'] or ""
        return notes_map

    def _to_dt(self, date_value, time_value):
        if not date_value:
            return None
        date_str = date_value if isinstance(date_value, str) else str(date_value)
        time_str = time_value if time_value else "00:00:00"
        if len(time_str) == 5:
            time_str = f"{time_str}:00"
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    def _to_local_date(self, date_value, time_value, tz_name: str) -> Optional[date]:
        if not date_value:
            return None
        time_str = time_value if time_value else "00:00:00"
        local_date, _local_time = utc_date_time_to_local(date_value, time_str, tz_name)
        return local_date

    def _to_local_date_from_dt(self, dt_value: Optional[datetime], tz_name: str) -> Optional[date]:
        if dt_value is None:
            return None
        return self._to_local_date(dt_value.date().isoformat(), dt_value.strftime("%H:%M:%S"), tz_name)

    def _get_close_balance_dt(self, site_id: int, user_id: int):
        """
        Get the datetime of position closure, which can be either:
        1. Explicit "Balance Closed" marker (amount=0, notes like "Balance Closed%")
        2. FULL redemption (more_remaining=0, meaning no balance remains on site)
        
        Returns the most recent of these two closure types.
        """
        # Check for explicit "Balance Closed" marker
        balance_closed_query = """
            SELECT redemption_date, COALESCE(redemption_time,'00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
                            AND deleted_at IS NULL
                            AND canceled_at IS NULL
              AND CAST(amount AS REAL) = 0
              AND notes LIKE 'Balance Closed%'
            ORDER BY redemption_date DESC, COALESCE(redemption_time,'00:00:00') DESC, id DESC
            LIMIT 1
        """
        balance_closed = self.db.fetch_one(balance_closed_query, (site_id, user_id))
        
        # Check for FULL redemption (more_remaining=0, explicitly not NULL)
        full_redemption_query = """
            SELECT redemption_date, COALESCE(redemption_time,'00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
                            AND deleted_at IS NULL
                            AND canceled_at IS NULL
              AND more_remaining IS NOT NULL
              AND more_remaining = 0
            ORDER BY redemption_date DESC, COALESCE(redemption_time,'00:00:00') DESC, id DESC
            LIMIT 1
        """
        full_redemption = self.db.fetch_one(full_redemption_query, (site_id, user_id))
        
        # Return the most recent closure event
        candidates = []
        if balance_closed:
            candidates.append(self._to_dt(balance_closed['redemption_date'], balance_closed['redemption_time']))
        if full_redemption:
            candidates.append(self._to_dt(full_redemption['redemption_date'], full_redemption['redemption_time']))
        
        return max(candidates) if candidates else None
    
    def get_position_by_site_user(self, site_id: int, user_id: int) -> Optional[UnrealizedPosition]:
        """Get specific position for a site/user pair"""
        all_positions = self.get_all_positions()
        for pos in all_positions:
            if pos.site_id == site_id and pos.user_id == user_id:
                return pos
        return None

    def get_related_anchor_date(
        self,
        site_id: int,
        user_id: int,
        position_start_date: date,
        purchase_basis: Decimal,
    ) -> date:
        """Anchor date for Unrealized "View Position" -> Related tab.

        When a position still has remaining purchase basis, the position start date is meaningful
        and keeps Related scoped to the active basis period.

        When a position has *zero* remaining purchase basis (profit-only / bonus-only SC),
        the position start date falls back to earliest-ever purchase and becomes too broad.
        In that case we anchor Related to the latest *non-adjustment* checkpoint (purchase/session),
        falling back to the latest checkpoint (including balance corrections) if needed.
        """
        try:
            basis = Decimal(str(purchase_basis or 0))
        except Exception:
            basis = Decimal("0")

        if basis > Decimal("0.001"):
            return position_start_date

        non_adjustment_checkpoint = self._get_latest_checkpoint(
            site_id,
            user_id,
            include_balance_checkpoints=False,
        )
        if non_adjustment_checkpoint and non_adjustment_checkpoint.get("checkpoint_dt"):
            return non_adjustment_checkpoint["checkpoint_dt"].date()

        any_checkpoint = self._get_latest_checkpoint(
            site_id,
            user_id,
            include_balance_checkpoints=True,
        )
        if any_checkpoint and any_checkpoint.get("checkpoint_dt"):
            return any_checkpoint["checkpoint_dt"].date()

        return position_start_date
    
    def _get_latest_checkpoint(
        self,
        site_id: int,
        user_id: int,
        *,
        include_balance_checkpoints: bool = True,
    ):
        """
        Find the most recent checkpoint among:
        0) Balance checkpoints (account_adjustments: BALANCE_CHECKPOINT_CORRECTION)
        1) Purchase snapshots (starting_sc_balance > 0)
        2) Session starts (starting_balance, both Active and Closed)
        3) Session ends (ending_balance, Closed only)
        
        Returns dict with: {checkpoint_dt, total_sc, redeemable_sc, checkpoint_purchase_id}
        or None if no checkpoints exist.
        """
        checkpoints = []

        if include_balance_checkpoints:
            # 0) Explicit balance checkpoints (highest trust; can occur outside sessions)
            checkpoint_adjustment_query = """
                SELECT
                    effective_date,
                    COALESCE(effective_time, '00:00:00') as effective_time,
                    checkpoint_total_sc,
                    checkpoint_redeemable_sc
                FROM account_adjustments
                WHERE site_id = ? AND user_id = ?
                  AND deleted_at IS NULL
                  AND type = 'BALANCE_CHECKPOINT_CORRECTION'
                ORDER BY effective_date DESC, COALESCE(effective_time,'00:00:00') DESC, id DESC
                LIMIT 1
            """
            balance_checkpoint = self.db.fetch_one(checkpoint_adjustment_query, (site_id, user_id))
            if balance_checkpoint:
                dt = self._to_dt(balance_checkpoint['effective_date'], balance_checkpoint['effective_time'])
                if dt:
                    checkpoints.append({
                        'checkpoint_dt': dt,
                        'total_sc': Decimal(str(balance_checkpoint['checkpoint_total_sc'] or 0)),
                        'redeemable_sc': Decimal(str(balance_checkpoint['checkpoint_redeemable_sc'] or 0)),
                        'checkpoint_purchase_id': None,
                        'priority': 3,
                    })
        
        # 1) Purchase snapshots
        purchase_snapshot_query = """
            SELECT 
                id as purchase_id,
                purchase_date, 
                COALESCE(purchase_time, '00:00:00') as purchase_time,
                starting_sc_balance,
                COALESCE(starting_redeemable_balance, 0.0) as starting_redeemable_balance
            FROM purchases
            WHERE site_id = ? AND user_id = ?
                            AND deleted_at IS NULL
              AND (status IS NULL OR status = 'active')
              AND starting_sc_balance > 0.001
            ORDER BY purchase_date DESC, COALESCE(purchase_time,'00:00:00') DESC, id DESC
            LIMIT 1
        """
        purchase_snap = self.db.fetch_one(purchase_snapshot_query, (site_id, user_id))
        if purchase_snap:
            dt = self._to_dt(purchase_snap['purchase_date'], purchase_snap['purchase_time'])
            if dt:
                checkpoints.append({
                    'checkpoint_dt': dt,
                    'total_sc': Decimal(str(purchase_snap['starting_sc_balance'])),
                    'redeemable_sc': Decimal(str(purchase_snap['starting_redeemable_balance'] or 0)),
                    'checkpoint_purchase_id': purchase_snap['purchase_id'],
                    'priority': 0,
                })
        
        # 2) Session starts (Active or Closed)
        session_start_query = """
            SELECT 
                session_date,
                COALESCE(session_time, '00:00:00') as session_time,
                starting_balance,
                starting_redeemable
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND deleted_at IS NULL
            ORDER BY session_date DESC, COALESCE(session_time,'00:00:00') DESC, id DESC
            LIMIT 1
        """
        session_start = self.db.fetch_one(session_start_query, (site_id, user_id))
        if session_start:
            dt = self._to_dt(session_start['session_date'], session_start['session_time'])
            if dt:
                checkpoints.append({
                    'checkpoint_dt': dt,
                    'total_sc': Decimal(str(session_start['starting_balance'] or 0)),
                    'redeemable_sc': Decimal(str(session_start['starting_redeemable'] or 0)),
                    'checkpoint_purchase_id': None,
                    'priority': 1,
                })
        
        # 3) Session ends (Closed only)
        session_end_query = """
            SELECT 
                COALESCE(end_date, session_date) as end_date,
                COALESCE(end_time, session_time, '00:00:00') as end_time,
                ending_balance,
                ending_redeemable
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
                            AND deleted_at IS NULL
              AND ending_balance IS NOT NULL
              AND LOWER(COALESCE(status, '')) != 'active'
            ORDER BY COALESCE(end_date, session_date) DESC,
                     COALESCE(end_time, session_time, '00:00:00') DESC,
                     id DESC
            LIMIT 1
        """
        session_end = self.db.fetch_one(session_end_query, (site_id, user_id))
        if session_end:
            dt = self._to_dt(session_end['end_date'], session_end['end_time'])
            if dt:
                checkpoints.append({
                    'checkpoint_dt': dt,
                    'total_sc': Decimal(str(session_end['ending_balance'] or 0)),
                    'redeemable_sc': Decimal(str(session_end['ending_redeemable'] or 0)),
                    'checkpoint_purchase_id': None,
                    'priority': 2,
                })
        
        # Return the newest checkpoint
        if not checkpoints:
            return None
        # Prefer the most recent datetime; if equal, prefer higher priority.
        return max(checkpoints, key=lambda c: (c['checkpoint_dt'], c.get('priority', 0)))
