"""
Repository for querying unrealized positions (open positions with SC remaining)
"""
from typing import List, Optional
from decimal import Decimal
from datetime import date, datetime

from models.unrealized_position import UnrealizedPosition


class UnrealizedPositionRepository:
    """Repository for querying unrealized positions"""
    
    def __init__(self, db):
        self.db = db
    
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

        notes_map = self._get_notes_map()
        
        # Get all site/user combinations with any purchase, session, or redemption activity
        # (not limited to only purchases with remaining_amount > 0)
        query = """
            SELECT DISTINCT
                site_id,
                user_id
            FROM (
                SELECT site_id, user_id FROM purchases WHERE (status IS NULL OR status = 'active')
                UNION
                SELECT site_id, user_id FROM game_sessions
                UNION
                SELECT site_id, user_id FROM redemptions
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
            site_name = names['site_name']
            user_name = names['user_name']
            
            # Get remaining basis and start date
            basis_query = """
                SELECT 
                    MIN(purchase_date) as start_date,
                    COALESCE(SUM(remaining_amount), 0) as remaining_basis
                FROM purchases
                WHERE site_id = ? AND user_id = ?
                  AND (status IS NULL OR status = 'active')
                  AND remaining_amount > 0.001
            """
            
            basis_data = self.db.fetch_one(basis_query, (site_id, user_id))
            remaining_basis = Decimal(str(basis_data['remaining_basis'] or 0)) if basis_data else Decimal("0.00")
            position_start_date = basis_data['start_date'] if basis_data and basis_data['start_date'] else None
            
            # If no purchases with remaining basis, use earliest purchase date
            if not position_start_date:
                earliest_purchase_query = """
                    SELECT MIN(purchase_date) as start_date
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                """
                earliest = self.db.fetch_one(earliest_purchase_query, (site_id, user_id))
                position_start_date = earliest['start_date'] if earliest and earliest['start_date'] else None
            
            # If still no start date, skip (no purchase activity)
            if not position_start_date:
                continue
            
            # Get current SC balance - estimate from last session + transactions since
            session_query = """
                SELECT ending_redeemable, ending_balance, session_date, session_time, end_date, end_time
                FROM game_sessions
                WHERE site_id = ? AND user_id = ?
                  AND ending_balance IS NOT NULL
                ORDER BY session_date DESC, session_time DESC
                LIMIT 1
            """
            
            last_session = self.db.fetch_one(session_query, (site_id, user_id))
            
            if last_session:
                # Baseline: last session ending balances
                # Use ending_balance for total SC baseline (represents all SC, not just redeemable)
                baseline_total = Decimal(str(last_session['ending_balance'] or 0))
                baseline_redeemable = Decimal(str(last_session['ending_redeemable'] or 0))
                session_end_date = last_session['end_date'] or last_session['session_date']
                session_end_time = last_session['end_time'] or last_session['session_time']
                session_end_dt = self._to_dt(session_end_date, session_end_time)
                
                # Get purchases after this session
                purchases_after_query = """
                    SELECT COALESCE(SUM(sc_received), 0) as total_sc
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                      AND (
                          purchase_date > ? 
                          OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') > ?)
                      )
                """
                purchases_after = self.db.fetch_one(
                    purchases_after_query,
                    (site_id, user_id, session_end_date, session_end_date, session_end_time or '00:00:00')
                )
                purchases_since = Decimal(str(purchases_after['total_sc'] or 0))
                
                # Get redemptions after this session
                redemptions_after_query = """
                    SELECT COALESCE(SUM(amount), 0) as total_redeemed
                    FROM redemptions
                    WHERE site_id = ? AND user_id = ?
                      AND (
                          redemption_date > ?
                          OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') > ?)
                      )
                """
                redemptions_after = self.db.fetch_one(
                    redemptions_after_query,
                    (site_id, user_id, session_end_date, session_end_date, session_end_time or '00:00:00')
                )
                redemptions_since = Decimal(str(redemptions_after['total_redeemed'] or 0))
                
                # Estimated current balances (purchases add to both, redemptions reduce both)
                estimated_total_sc = baseline_total + purchases_since - redemptions_since
                
                # Use total SC for value/P&L calculations.
                # Redeemable SC: only show if session is part of current position (session end >= position start)
                # Otherwise show 0 (position predates this session, e.g., fully closed then repurchased)
                total_sc = estimated_total_sc
                position_start_dt = self._to_dt(position_start_date, '00:00:00')
                
                if session_end_dt and position_start_dt and session_end_dt >= position_start_dt:
                    # Session is part of current open position
                    redeemable_sc = baseline_redeemable
                else:
                    # Session predates current position's basis (old closed position)
                    redeemable_sc = Decimal("0.00")
                
                # Determine last activity date (most recent of session end, purchase, redemption)
                last_activity_candidates = [(session_end_date, session_end_time or '00:00:00')]
                
                if purchases_since > 0:
                    last_purchase_query = """
                        SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                        FROM purchases
                        WHERE site_id = ? AND user_id = ?
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
                        ORDER BY redemption_date DESC, COALESCE(redemption_time,'00:00:00') DESC, id DESC
                        LIMIT 1
                    """
                    last_redemption = self.db.fetch_one(last_redemption_query, (site_id, user_id))
                    if last_redemption:
                        last_activity_candidates.append((last_redemption['redemption_date'], last_redemption['redemption_time']))
                
                # Find most recent activity
                last_activity_dts = [self._to_dt(d, t) for d, t in last_activity_candidates if d]
                last_activity_dt = max(last_activity_dts) if last_activity_dts else session_end_dt
                last_activity = last_activity_dt.date() if last_activity_dt else session_end_date
                
            else:
                # No sessions yet - sum all purchases (both total and redeemable are same)
                purchase_sum_query = """
                    SELECT COALESCE(SUM(sc_received), 0) as total_sc
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                """
                purchase_data = self.db.fetch_one(purchase_sum_query, (site_id, user_id))
                total_sc = Decimal(str(purchase_data['total_sc'] or 0))
                # No sessions means we have no tracked redeemable split; show 0 as last-known.
                redeemable_sc = Decimal("0.00")
                
                last_purchase_query = """
                    SELECT purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                      AND (status IS NULL OR status = 'active')
                    ORDER BY purchase_date DESC, COALESCE(purchase_time,'00:00:00') DESC, id DESC
                    LIMIT 1
                """
                last_purchase = self.db.fetch_one(last_purchase_query, (site_id, user_id))
                last_activity = last_purchase['purchase_date'] if last_purchase else None
                last_activity_time = last_purchase['purchase_time'] if last_purchase else None
                last_activity_dt = self._to_dt(last_activity, last_activity_time) if last_activity else None

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

    def _get_close_balance_dt(self, site_id: int, user_id: int):
        query = """
            SELECT redemption_date, COALESCE(redemption_time,'00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND CAST(amount AS REAL) = 0
              AND notes LIKE 'Balance Closed%'
            ORDER BY redemption_date DESC, COALESCE(redemption_time,'00:00:00') DESC, id DESC
            LIMIT 1
        """
        row = self.db.fetch_one(query, (site_id, user_id))
        if not row:
            return None
        return self._to_dt(row['redemption_date'], row['redemption_time'])
    
    def get_position_by_site_user(self, site_id: int, user_id: int) -> Optional[UnrealizedPosition]:
        """Get specific position for a site/user pair"""
        all_positions = self.get_all_positions()
        for pos in all_positions:
            if pos.site_id == site_id and pos.user_id == user_id:
                return pos
        return None
