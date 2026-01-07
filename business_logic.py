"""
business_logic.py - FIFO calculations and session management
FIXED VERSION - Addresses orphaned redemptions and refactor bugs
"""

import sqlite3
from datetime import datetime

class FreebiesInfo(dict):
    """
    Backwards/forwards compatible return type for detect_freebies().

    - Dict-like access: info["freebies_sc"], info["expected_total_sc"], etc.
    - Tuple unpacking: freebies_sc, freebies_dollar, expected_total = info
    """
    def __iter__(self):
        yield float(self.get("freebies_sc", 0.0))
        yield float(self.get("freebies_dollar", 0.0))
        yield float(self.get("expected_total_sc", 0.0))


class FIFOCalculator:
    """Handles FIFO cost basis calculations for redemptions"""
    
    def __init__(self, db):
        self.db = db
    
    def calculate_cost_basis(self, site_id, redemption_amount, user_id, redemption_date):
        """
        Calculate FIFO cost basis for a redemption
        
        Returns:
            tuple: (cost_basis, allocations) where allocations is list of (purchase_id, allocated_amount)
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get purchases with remaining balance, ordered by FIFO (oldest first)
        c.execute('''
            SELECT id, amount, remaining_amount, sc_received
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0
            ORDER BY purchase_date ASC, purchase_time ASC, id ASC
        ''', (site_id, user_id))
        
        purchases = c.fetchall()
        conn.close()
        
        cost_basis = 0.0
        allocations = []
        remaining = redemption_amount
        
        # Allocate redemption amount across purchases using FIFO
        for purchase in purchases:
            if remaining <= 0:
                break
            
            allocated = min(purchase['remaining_amount'], remaining)
            cost_basis += allocated
            allocations.append((purchase['id'], allocated))
            remaining -= allocated
        
        return cost_basis, allocations
    
    def get_weighted_average_basis_per_sc(self, site_id, user_id, as_of_date=None, as_of_time=None):
        """
        Calculate weighted average basis per SC for a site/user
        
        This is used for session P/L calculation when unlocking SC.
        Unlike FIFO (used for redemptions), this gives average cost across all purchases.
        
        Args:
            site_id: Site ID
            user_id: User ID
            as_of_date: Optional date filter - only include purchases on or before this date
            as_of_time: Optional time filter - for purchases on as_of_date, only include if time <= this
        
        Returns:
            float: Average cost per SC (e.g., $0.75/SC)
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Build query with optional date/time filter
        query = '''
            SELECT amount, sc_received
            FROM purchases
            WHERE site_id = ? AND user_id = ?
        '''
        params = [site_id, user_id]
        
        # Add date/time filtering if provided
        if as_of_date is not None:
            query += '''
              AND (purchase_date < ? OR 
                   (purchase_date = ? AND (purchase_time IS NULL OR purchase_time <= ?)))
            '''
            params.extend([as_of_date, as_of_date, as_of_time or '23:59:59'])
        
        c.execute(query, params)
        purchases = c.fetchall()
        conn.close()
        
        if not purchases:
            return 0.0
        
        # Calculate weighted average
        total_cost = sum(p['amount'] for p in purchases)
        total_sc = sum(p['sc_received'] for p in purchases)
        
        if total_sc == 0:
            return 0.0
        
        return total_cost / total_sc
    
    def apply_allocation(self, allocations):
        """Apply FIFO allocation by updating purchase remaining amounts"""
        if not allocations:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        for purchase_id, allocated in allocations:
            # Update remaining amount, ensuring it never goes below 0 or above original amount
            c.execute('''
                UPDATE purchases 
                SET remaining_amount = MAX(0, MIN(remaining_amount - ?, amount))
                WHERE id = ?
            ''', (allocated, purchase_id))
        
        conn.commit()
        conn.close()
    
    def reverse_cost_basis(self, site_id, user_id, cost_basis_to_restore):
        """
        Restore cost basis to purchases using reverse FIFO (newest first)
        Used when editing/deleting redemptions to unapply cost basis
        """
        if cost_basis_to_restore <= 0:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get purchases in reverse FIFO order (newest first)
        # Only include purchases that have been partially or fully consumed
        c.execute('''
            SELECT id, amount, remaining_amount
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount < amount
            ORDER BY purchase_date DESC, purchase_time DESC, id DESC
        ''', (site_id, user_id))
        
        purchases = c.fetchall()
        remaining_to_restore = cost_basis_to_restore
        
        # Restore to purchases in reverse order
        for purchase in purchases:
            if remaining_to_restore <= 0:
                break
            
            # How much was consumed from this purchase?
            consumed = purchase['amount'] - purchase['remaining_amount']
            
            # Restore up to the consumed amount
            to_restore = min(consumed, remaining_to_restore)
            
            # Update, ensuring remaining doesn't exceed original amount
            c.execute('''
                UPDATE purchases 
                SET remaining_amount = MIN(remaining_amount + ?, amount)
                WHERE id = ?
            ''', (to_restore, purchase['id']))
            
            remaining_to_restore -= to_restore
        
        conn.commit()
        conn.close()


class SessionManager:
    """Manages site sessions and redemption processing"""
    
    def __init__(self, db, fifo_calc):
        self.db = db
        self.fifo_calc = fifo_calc
    
    def rebuild_all_derived(self, site_id=None, user_id=None, from_date=None, from_time='00:00:00',
                             rebuild_fifo=True, rebuild_sessions=True):
        """
        Unified rebuild entrypoint.

        - If site_id and user_id are provided: rebuild only that pair.
        - If not: rebuild all (site_id, user_id) pairs found in purchases/redemptions/sessions.
        """
        conn = self.db.get_connection()
        c = conn.cursor()

        if site_id is not None and user_id is not None:
            pairs = [(site_id, user_id)]
        else:
            c.execute("""
                SELECT DISTINCT site_id, user_id FROM (
                    SELECT site_id, user_id FROM purchases
                    UNION
                    SELECT site_id, user_id FROM redemptions
                    UNION
                    SELECT site_id, user_id FROM game_sessions
                )
                WHERE site_id IS NOT NULL AND user_id IS NOT NULL
                ORDER BY site_id, user_id
            """)
            pairs = [(r[0], r[1]) for r in c.fetchall()]

        conn.close()

        sessions_processed = 0

        for s_id, u_id in pairs:
            if rebuild_fifo:
                self._rebuild_fifo_for_pair(s_id, u_id)

            if rebuild_sessions:
                if from_date is not None:
                    _ = (from_date, from_time)

                session_count, touched_dates = self._rebuild_session_tax_fields_for_pair(s_id, u_id)
                sessions_processed += session_count

                for d in touched_dates:
                    self.update_daily_tax_session(d, u_id)

        return {
            "pairs": pairs,
            "pairs_processed": len(pairs),
            "rebuild_fifo": bool(rebuild_fifo),
            "rebuild_sessions": bool(rebuild_sessions),
            "sessions_processed": sessions_processed,
        }

    def _rebuild_fifo_for_pair(self, site_id, user_id):
        """Rebuild FIFO purchase remaining_amount and tax_sessions for all redemptions in scope."""
        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("""
            UPDATE purchases
            SET remaining_amount = amount
            WHERE site_id = ? AND user_id = ?
        """, (site_id, user_id))

        c.execute("""
            DELETE FROM tax_sessions
            WHERE site_id = ? AND user_id = ?
        """, (site_id, user_id))

        conn.commit()

        c.execute("""
            SELECT id, site_id, amount, redemption_date,
                   COALESCE(redemption_time,'00:00:00') AS rt,
                   user_id,
                   COALESCE(is_free_sc, 0) AS is_free_sc,
                   COALESCE(more_remaining, 0) AS more_remaining
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id))
        redemptions = c.fetchall()
        conn.close()

        for r in redemptions:
            rid = r[0]
            self.process_redemption(
                rid,
                r[1],
                float(r[2] or 0.0),
                r[3],
                r[4],
                r[5],
                int(r[6] or 0),
                int(r[7] or 0),
                is_edit=False,
            )

    def get_last_checkpoint(self, site_id, user_id, as_of_date, as_of_time='00:00:00'):
        """
        Return the most recent balance checkpoint strictly before (as_of_date, as_of_time).
        Priority: closed session end > purchase starting_sc_balance > 0 baseline.
        """
        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("""
            SELECT
                COALESCE(end_date, session_date) AS eff_end_date,
                COALESCE(end_time, '23:59:59') AS eff_end_time,
                ending_sc_balance,
                COALESCE(ending_redeemable_sc, ending_sc_balance) AS ending_redeemable
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (
                    COALESCE(end_date, session_date) < ?
                 OR (COALESCE(end_date, session_date) = ? AND COALESCE(end_time, '23:59:59') < ?)
              )
            ORDER BY eff_end_date DESC, eff_end_time DESC, id DESC
            LIMIT 1
        """, (site_id, user_id, as_of_date, as_of_date, as_of_time))
        row = c.fetchone()
        if row:
            conn.close()
            return (row[0], row[1], float(row[2] or 0.0), float(row[3] or 0.0))

        c.execute("""
            SELECT purchase_date, COALESCE(purchase_time,'00:00:00') AS pt, starting_sc_balance
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND starting_sc_balance > 0
              AND (purchase_date < ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') < ?))
            ORDER BY purchase_date DESC, pt DESC, id DESC
            LIMIT 1
        """, (site_id, user_id, as_of_date, as_of_date, as_of_time))
        row = c.fetchone()
        conn.close()
        if row:
            return (row[0], row[1], float(row[2] or 0.0), 0.0)

        return (None, None, 0.0, 0.0)

    def compute_expected_balances(self, site_id, user_id, as_of_date, as_of_time='00:00:00'):
        """Compute expected (total_sc, redeemable_sc) as of a timestamp."""
        chk_date, chk_time, chk_total, chk_redeemable = self.get_last_checkpoint(site_id, user_id, as_of_date, as_of_time)
        expected_total = chk_total
        expected_redeemable = chk_redeemable

        if chk_date is None:
            chk_date, chk_time = '0001-01-01', '00:00:00'

        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("""
            SELECT COALESCE(sc_received, amount, 0) AS sc
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') >= ?))
              AND (purchase_date < ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') < ?))
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id, chk_date, chk_date, chk_time, as_of_date, as_of_date, as_of_time))
        for r in c.fetchall():
            expected_total += float(r[0] or 0.0)

        c.execute("""
            SELECT amount
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
              AND (redemption_date < ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') < ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id, chk_date, chk_date, chk_time, as_of_date, as_of_date, as_of_time))
        for r in c.fetchall():
            amt = float(r[0] or 0.0)
            expected_total -= amt
            expected_redeemable -= amt

        conn.close()
        expected_total = max(0.0, expected_total)
        expected_redeemable = max(0.0, expected_redeemable)
        return expected_total, expected_redeemable

    def get_or_create_site_session(self, site_id, user_id, purchase_date):
        """Get active site session or create new one"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Look for existing active session
        c.execute('''
            SELECT id FROM site_sessions
            WHERE site_id = ? AND user_id = ? AND status IN ('Active', 'Redeeming')
            ORDER BY start_date DESC LIMIT 1
        ''', (site_id, user_id))
        
        result = c.fetchone()
        
        if result:
            session_id = result['id']
        else:
            # Create new session
            c.execute('''
                INSERT INTO site_sessions (site_id, user_id, start_date, status)
                VALUES (?, ?, ?, 'Active')
            ''', (site_id, user_id, purchase_date))
            session_id = c.lastrowid
            conn.commit()
        
        conn.close()
        return session_id
    
    def add_purchase_to_session(self, session_id, amount):
        """Add purchase amount to site session total"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute(
            'UPDATE site_sessions SET total_buyin = total_buyin + ? WHERE id = ?',
            (amount, session_id)
        )
        
        conn.commit()
        conn.close()
    
    def process_redemption(self, redemption_id, site_id, redemption_amount, redemption_date,
                          redemption_time, user_id, is_free_sc, more_remaining, is_edit=False):
        """
        Process redemption: calculate FIFO, create tax session, update site session
        
        FIXED VERSION: Links redemptions to sessions without overriding processed flags
        
        When more_remaining=False (final redemption), consumes ALL remaining cost basis
        When more_remaining=True, only uses FIFO for the redemption amount
        
        Args:
            redemption_id: ID of the redemption
            site_id: Site ID
            redemption_amount: Amount being redeemed
            redemption_date: Date of redemption
            redemption_time: Time of redemption (HH:MM:SS)
            user_id: User ID
            is_free_sc: Whether this is free SC (no cost basis)
            more_remaining: Whether more balance remains in session
            is_edit: Whether this is an edit (don't update total_redeemed again)
        
        Returns:
            float: Net P/L for this redemption
        """
        # Calculate cost basis using FIFO (skip for free SC)
        if is_free_sc:
            cost_basis = 0.0
            allocations = []
        else:
            if not more_remaining:
                # Final redemption - consume ALL remaining cost basis for this site/user
                # BUT ONLY for purchases on or before this redemption timestamp
                conn = self.db.get_connection()
                c = conn.cursor()
                c.execute('''
                    SELECT SUM(remaining_amount) as total_remaining
                    FROM purchases
                    WHERE site_id = ? AND user_id = ? AND remaining_amount > 0
                      AND (purchase_date < ? OR 
                           (purchase_date = ? AND (purchase_time IS NULL OR purchase_time <= ?)))
                ''', (site_id, user_id, redemption_date, redemption_date, redemption_time))
                result = c.fetchone()
                conn.close()
                
                total_remaining = float(result['total_remaining']) if result and result['total_remaining'] else 0.0
                
                # Use FIFO to consume ALL remaining basis (not just redemption amount)
                cost_basis, allocations = self.fifo_calc.calculate_cost_basis(
                    site_id, total_remaining, user_id, redemption_date
                )
            else:
                # More redemptions expected - just use FIFO for this redemption amount
                cost_basis, allocations = self.fifo_calc.calculate_cost_basis(
                    site_id, redemption_amount, user_id, redemption_date
                )
            
            self.fifo_calc.apply_allocation(allocations)
        
        net_pl = redemption_amount - cost_basis
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Create tax session record
        c.execute('''
            INSERT INTO tax_sessions 
            (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (redemption_date, site_id, redemption_id, cost_basis, redemption_amount, net_pl, user_id))
        
        conn.commit()
        conn.close()
        
        # Get or create the site session for this redemption (skip for free SC)
        session_id = None
        if not is_free_sc:
            session_id = self.get_or_create_site_session(site_id, user_id, redemption_date)
        
        # Reopen connection for remaining updates
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Link the redemption to its session (don't override user's processed flag)
        c.execute('''
            UPDATE redemptions 
            SET site_session_id = ? 
            WHERE id = ?
        ''', (session_id, redemption_id))
        
        # Update site session if not free SC (and not an edit - edit handles totals separately)
        if not is_free_sc and not is_edit:
            # Determine new status based on remaining balance and P/L
            if more_remaining:
                new_status = 'Redeeming'
            else:
                new_status = 'Closed - Profit' if net_pl >= 0 else 'Closed - Loss'
            
            c.execute('''
                UPDATE site_sessions 
                SET total_redeemed = total_redeemed + ?, status = ? 
                WHERE id = ?
            ''', (redemption_amount, new_status, session_id))
        
        conn.commit()
        conn.close()
        
        return net_pl
    
    def close_session_as_loss(self, session_id, loss_date, notes=None):
        """
        Close a site session as total loss
        
        This accounts for the REMAINING balance that was lost (not redeemed).
        
        For example:
          - Bought in: $2000
          - Already redeemed: $1000 (which consumed $1000 of cost basis via FIFO)
          - Remaining balance lost: $1000
        
        We record a $0 redemption for the remaining balance, applying FIFO to get cost basis.
        
        Args:
            session_id: The site session to close
            loss_date: Date of the loss
            notes: Optional notes explaining why the session closed as a loss
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get session details INCLUDING STATUS
        c.execute('''
            SELECT site_id, user_id, total_buyin, total_redeemed, status
            FROM site_sessions 
            WHERE id = ?
        ''', (session_id,))
        session = c.fetchone()
        
        if not session:
            conn.close()
            return
        
        # Check if already closed
        if session['status'].startswith('Closed'):
            conn.close()
            raise ValueError(f"Session already closed with status: {session['status']}")
        
        site_id = session['site_id']
        user_id = session['user_id']  # Get actual user_id from session
        total_buyin = float(session['total_buyin'] or 0.0)
        total_redeemed = float(session['total_redeemed'] or 0.0)
        
        # Calculate remaining balance that was lost
        remaining_balance = total_buyin - total_redeemed
        
        # If nothing remaining, nothing to do
        if remaining_balance <= 0:
            conn.close()
            return
        
        # Create $0 redemption for audit trail (with notes)
        c.execute('''
            INSERT INTO redemptions 
            (site_session_id, site_id, redemption_date, amount, is_free_sc, user_id, notes, processed)
            VALUES (?, ?, ?, 0.0, 0, ?, ?, 1)
        ''', (session_id, site_id, loss_date, user_id, notes))
        
        redemption_id = c.lastrowid
        
        # If notes provided, also add to the site_session
        if notes:
            c.execute('UPDATE site_sessions SET notes = ? WHERE id = ?', (notes, session_id))
        
        conn.commit()
        conn.close()
        
        # Apply FIFO against the remaining balance to get cost basis
        cost_basis, allocations = self.fifo_calc.calculate_cost_basis(
            site_id, remaining_balance, user_id, loss_date
        )
        
        if allocations:
            self.fifo_calc.apply_allocation(allocations)
        
        # Create tax session showing loss of the remaining cost basis
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO tax_sessions 
            (session_date, site_id, redemption_id, cost_basis, payout, net_pl, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (loss_date, site_id, redemption_id, cost_basis, 0.0, -cost_basis, user_id))
        
        # Update session status
        c.execute('UPDATE site_sessions SET status = "Closed - Loss" WHERE id = ?', (session_id,))
        
        conn.commit()
        conn.close()
    
    def delete_redemption(self, redemption_id):
        """
        Delete a redemption and reverse all accounting
        
        This needs to:
        1. Get the cost_basis from tax_sessions to restore FIFO
        2. Update site_session's total_redeemed
        3. Potentially reopen the site_session if it was closed
        4. Delete tax_session and redemption records
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get redemption details
        c.execute('''
            SELECT r.site_session_id, r.site_id, r.amount, r.user_id, r.is_free_sc,
                   ts.cost_basis
            FROM redemptions r
            LEFT JOIN tax_sessions ts ON ts.redemption_id = r.id
            WHERE r.id = ?
        ''', (redemption_id,))
        
        redemption = c.fetchone()
        
        if not redemption:
            conn.close()
            return False
        
        site_session_id = redemption['site_session_id']
        redemption_amount = float(redemption['amount'] or 0.0)
        cost_basis = float(redemption['cost_basis'] or 0.0)
        site_id = redemption['site_id']
        user_id = redemption['user_id']
        is_free_sc = redemption['is_free_sc']
        
        # Delete tax_session and redemption
        c.execute("DELETE FROM tax_sessions WHERE redemption_id = ?", (redemption_id,))
        c.execute("DELETE FROM redemptions WHERE id = ?", (redemption_id,))
        
        # If not free SC and has a site session, reverse the accounting
        if not is_free_sc and site_session_id:
            # Restore FIFO by adding back to purchases in reverse order
            # We need to restore the cost_basis amount back to purchases
            if cost_basis > 0:
                # Get the purchases that were consumed (in FIFO order)
                c.execute('''
                    SELECT id, amount, remaining_amount
                    FROM purchases
                    WHERE site_id = ? AND user_id = ?
                    ORDER BY purchase_date ASC, purchase_time ASC, id ASC
                ''', (site_id, user_id))
                
                purchases = c.fetchall()
                remaining_to_restore = cost_basis
                
                # Restore in FIFO order (same order they were consumed)
                for purchase in purchases:
                    if remaining_to_restore <= 0:
                        break
                    
                    # How much can we restore to this purchase?
                    max_restore = purchase['amount'] - purchase['remaining_amount']
                    restore_amount = min(max_restore, remaining_to_restore)
                    
                    if restore_amount > 0:
                        c.execute('''
                            UPDATE purchases 
                            SET remaining_amount = MIN(remaining_amount + ?, amount)
                            WHERE id = ?
                        ''', (restore_amount, purchase['id']))
                        
                        remaining_to_restore -= restore_amount
            
            # Update site_session
            # Reduce total_redeemed
            c.execute('''
                UPDATE site_sessions 
                SET total_redeemed = total_redeemed - ?
                WHERE id = ?
            ''', (redemption_amount, site_session_id))
            
            # Check if session should be reopened
            c.execute('''
                SELECT total_buyin, total_redeemed, status
                FROM site_sessions
                WHERE id = ?
            ''', (site_session_id,))
            
            session = c.fetchone()
            if session:
                total_buyin = float(session['total_buyin'] or 0.0)
                total_redeemed = float(session['total_redeemed'] or 0.0)
                current_status = session['status']
                
                # Check if any redemptions remain for this session
                c.execute('''
                    SELECT COUNT(*) as count
                    FROM redemptions
                    WHERE site_session_id = ?
                ''', (site_session_id,))
                remaining_redemptions = c.fetchone()['count']
                
                # Determine new status
                if remaining_redemptions == 0:
                    # No redemptions left - back to Active
                    new_status = 'Active'
                elif current_status.startswith('Closed'):
                    # Had redemptions, was closed, now reopen as Redeeming
                    new_status = 'Redeeming'
                else:
                    # Keep current status if still has redemptions and wasn't closed
                    new_status = current_status
                
                # Update status if it changed
                if new_status != current_status:
                    c.execute('''
                        UPDATE site_sessions
                        SET status = ?
                        WHERE id = ?
                    ''', (new_status, site_session_id))
        
        conn.commit()
        conn.close()
        return True
    
    # ========================================================================
    # DAILY SESSION TRACKING METHODS
    # ========================================================================
    
    def get_sc_rate(self, site_id):
        """Get SC to dollar conversion rate for a site"""
        conn = self.db.get_connection()
        c = conn.cursor()
        
        rate = None
        try:
            c.execute('SELECT sc_rate FROM sites WHERE id = ?', (site_id,))
            row = c.fetchone()
            if row and row['sc_rate'] is not None:
                rate = float(row['sc_rate'])
        except sqlite3.OperationalError:
            rate = None

        if rate is None:
            # Fallback: legacy sc_conversion_rates table
            try:
                c.execute('SELECT rate FROM sc_conversion_rates WHERE site_id = ?', (site_id,))
                row = c.fetchone()
                if row and row['rate'] is not None:
                    rate = float(row['rate'])
            except sqlite3.OperationalError:
                rate = None

        if rate is None:
            # Get default rate from settings if available
            try:
                c.execute("SELECT value FROM settings WHERE key = 'default_sc_rate'")
                default_row = c.fetchone()
                rate = float(default_row['value']) if default_row and default_row['value'] is not None else 1.0
            except sqlite3.OperationalError:
                rate = 1.0
        
        conn.close()
        return rate
    


    def detect_freebies(self, site_id, user_id, current_sc_balance, session_date=None, session_time=None):
        """
        Determine expected balances at a timestamp and compute delta vs expected.

        Returns a FreebiesInfo which is both dict-like and tuple-unpackable:
            freebies_sc, freebies_dollar, expected_total_sc = detect_freebies(...)
        """
        if session_date is None:
            # If caller doesn't provide, treat as "now-ish" by using a very late timestamp.
            session_date = '9999-12-31'
        if session_time is None:
            session_time = '23:59:59'

        expected_total, expected_redeemable = self.compute_expected_balances(site_id, user_id, session_date, session_time)
        delta_total = float(current_sc_balance or 0.0) - float(expected_total or 0.0)

        sc_rate = float(self.get_sc_rate(site_id) or 1.0)
        freebies_sc = float(max(0.0, delta_total))
        freebies_dollar = freebies_sc * sc_rate

        return FreebiesInfo({
            "expected_total_sc": float(expected_total or 0.0),
            "expected_redeemable_sc": float(expected_redeemable or 0.0),
            "delta_total_sc": float(delta_total),
            "freebies_sc": freebies_sc,
            "freebies_dollar": float(freebies_dollar),
            "missing_sc": float(max(0.0, -delta_total)),
        })

    def _dt(self, d, t):
        """Parse date+time strings into a datetime for comparisons."""
        if not d:
            return None
        tt = (t or '00:00:00')
        # Some tables store times without seconds; normalize
        if len(tt) == 5:
            tt = tt + ':00'
        return datetime.fromisoformat(f"{d} {tt}")

    def _load_pair_events(self, site_id, user_id):
        """Load purchases and redemptions for (site_id,user_id) into lists of (dt, amount, sc)."""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT purchase_date, COALESCE(purchase_time,'00:00:00') as purchase_time,
                   amount, COALESCE(sc_received,0) as sc_received
            FROM purchases
            WHERE site_id=? AND user_id=?
        """, (site_id, user_id))
        purchases = []
        for r in c.fetchall():
            purchases.append((self._dt(r['purchase_date'], r['purchase_time']), float(r['amount'] or 0), float(r['sc_received'] or 0)))

        c.execute("""
            SELECT redemption_date, COALESCE(redemption_time,'00:00:00') as redemption_time,
                   amount
            FROM redemptions
            WHERE site_id=? AND user_id=?
        """, (site_id, user_id))
        redemptions = []
        for r in c.fetchall():
            redemptions.append((self._dt(r['redemption_date'], r['redemption_time']), float(r['amount'] or 0)))

        conn.close()
        # Sort for stable filtering
        purchases.sort(key=lambda x: (x[0] or datetime.min))
        redemptions.sort(key=lambda x: (x[0] or datetime.min))
        return purchases, redemptions

    def _rebuild_session_tax_fields_for_pair(self, site_id, user_id):
        """
        Recompute derived session fields per spec (v2):
        - expected_start_total_sc / expected_start_redeemable_sc
        - session_basis (cash purchases since last completed session end)
        - basis_consumed (cash basis used in this session)
        - delta_total / delta_redeem
        - inferred_start deltas
        - net_taxable_pl (discoverable + delta_play - basis_consumed)
        - pending basis pool (carry-forward cash basis consumed only on redeemable gains)
        """
        conn = self.db.get_connection()
        c = conn.cursor()

        # Load closed sessions ordered by completion timestamp
        c.execute("""
            SELECT id, session_date, COALESCE(start_time,'00:00:00') as start_time,
                   COALESCE(end_date, session_date) as end_date,
                   COALESCE(end_time,'00:00:00') as end_time,
                   COALESCE(starting_sc_balance,0) as starting_sc_balance,
                   COALESCE(ending_sc_balance,0) as ending_sc_balance,
                   COALESCE(starting_redeemable_sc, COALESCE(starting_sc_balance,0)) as starting_redeemable_sc,
                   COALESCE(ending_redeemable_sc, COALESCE(ending_sc_balance,0)) as ending_redeemable_sc
            FROM game_sessions
            WHERE site_id=? AND user_id=? AND status='Closed'
            ORDER BY end_date ASC, end_time ASC, id ASC
        """, (site_id, user_id))
        sessions = c.fetchall()

        purchases, redemptions = self._load_pair_events(site_id, user_id)

        last_end_total = 0.0
        last_end_redeem = 0.0
        checkpoint_end_dt = None  # None => beginning of history
        pending_basis_pool = 0.0
        sc_rate = float(self.get_sc_rate(site_id) or 1.0)
        touched_dates = set()

        def in_window(dt, start_exclusive, end_inclusive):
            if dt is None:
                return False
            if start_exclusive is not None and dt < start_exclusive:
                return False
            return dt <= end_inclusive

        for s in sessions:
            sid = s['id']
            start_dt = self._dt(s['session_date'], s['start_time'])
            end_dt = self._dt(s['end_date'], s['end_time'])

            # Defensive: if end_dt < start_dt, force end_dt = start_dt
            if end_dt and start_dt and end_dt < start_dt:
                end_dt = start_dt

            # Redemptions between checkpoint end and session start (exclusive cp, inclusive start)
            red_between = sum(amt for (dt, amt) in redemptions if in_window(dt, checkpoint_end_dt, start_dt))

            # Purchases SC received between checkpoint end and session start (for expected start total)
            pur_sc_to_start = sum(sc for (dt, amt, sc) in purchases if in_window(dt, checkpoint_end_dt, start_dt))

            # Purchases cash between checkpoint end and session end (session basis / pool additions)
            pur_cash_to_end = sum(amt for (dt, amt, sc) in purchases if in_window(dt, checkpoint_end_dt, end_dt))

            expected_start_total = (last_end_total - red_between) + pur_sc_to_start
            expected_start_redeem = (last_end_redeem - red_between)
            expected_start_total = max(0.0, expected_start_total)
            expected_start_redeem = max(0.0, expected_start_redeem)

            start_total = float(s['starting_sc_balance'] or 0)
            end_total = float(s['ending_sc_balance'] or 0)
            start_red = float(s['starting_redeemable_sc'] or 0)
            end_red = float(s['ending_redeemable_sc'] or 0)

            delta_total = end_total - start_total
            delta_redeem = end_red - start_red

            inferred_start_total_delta = start_total - expected_start_total
            inferred_start_redeem_delta = start_red - expected_start_redeem

            session_basis = float(pur_cash_to_end or 0)

            # Pending basis pool rolls forward; only redeemable gains consume basis
            pending_basis_pool += session_basis
            if pending_basis_pool < 0:
                pending_basis_pool = 0.0

            discoverable_sc = max(0.0, start_red - expected_start_redeem)
            delta_play_sc = delta_redeem
            locked_start = max(0.0, start_total - start_red)
            locked_end = max(0.0, end_total - end_red)
            locked_processed_sc = max(locked_start - locked_end, 0.0)
            locked_processed_value = locked_processed_sc * sc_rate
            basis_consumed = min(pending_basis_pool, locked_processed_value)
            pending_basis_pool = max(0.0, pending_basis_pool - basis_consumed)

            net_taxable_pl = ((discoverable_sc + delta_play_sc) * sc_rate) - basis_consumed

            # Write derived fields
            c.execute("""
                UPDATE game_sessions
                SET
                    session_basis=?,
                    basis_consumed=?,
                    expected_start_total_sc=?,
                    expected_start_redeemable_sc=?,
                    inferred_start_total_delta=?,
                    inferred_start_redeemable_delta=?,
                    delta_total=?,
                    delta_redeem=?,
                    net_taxable_pl=?,
                    total_taxable=?,
                    sc_change=?,
                    basis_bonus=NULL,
                    gameplay_pnl=NULL
                WHERE id=?
            """, (session_basis, basis_consumed, expected_start_total, expected_start_redeem,
                  inferred_start_total_delta, inferred_start_redeem_delta,
                  delta_total, delta_redeem, net_taxable_pl, net_taxable_pl, delta_total, sid))

            # Advance checkpoint
            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt
            touched_dates.add(s['session_date'])

        conn.commit()
        conn.close()
        return len(sessions), touched_dates

    def start_game_session(self, site_id, user_id, game_type, starting_sc, starting_redeemable_sc=None, 
                          session_date=None, notes=None, start_time=None):
        """
        Start a new game session
        
        Args:
            starting_sc: Total SC balance
            starting_redeemable_sc: SC that has completed playthrough (defaults to starting_sc)
        
        NOTE: Freebies are informational only; tax is computed at session end.
        
        Returns: (session_id, freebies_detected_amount)
        """
        from datetime import datetime
        
        if session_date is None:
            session_date = datetime.now().strftime('%Y-%m-%d')
        
        if start_time is None:
            start_time = datetime.now().strftime('%H:%M:%S')
        
        # Default redeemable to total if not provided (assume fully unlocked)
        if starting_redeemable_sc is None:
            starting_redeemable_sc = starting_sc
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # IMPORTANT: Reactivate any dormant purchases for this site/user
        # When starting a new session, dormant basis becomes active again
        # Get the amount being reactivated for user notification
        c.execute('''
            SELECT COALESCE(SUM(remaining_amount), 0) as reactivated_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND status = 'dormant'
        ''', (site_id, user_id))
        
        reactivated_basis = c.fetchone()['reactivated_basis']
        
        c.execute('''
            UPDATE purchases
            SET status = 'active'
            WHERE site_id = ? AND user_id = ? AND status = 'dormant'
        ''', (site_id, user_id))
        
        reactivated_count = c.rowcount
        conn.commit()
        conn.close()
        
        # Detect freebies (for informational display only)
        # Do this AFTER reactivating dormant purchases so basis calculation is accurate
        # Pass session date/time to filter purchases correctly
        freebies_sc, freebies_dollar, last_balance = self.detect_freebies(
            site_id, user_id, starting_sc, session_date, start_time
        )
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Create game session
        # Note: freebies_detected is kept for reference but not used for tax
        c.execute('''
            INSERT INTO game_sessions 
            (session_date, start_time, site_id, user_id, game_type, 
             starting_sc_balance, starting_redeemable_sc, freebies_detected, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?)
        ''', (session_date, start_time, site_id, user_id, game_type, 
              starting_sc, starting_redeemable_sc, freebies_dollar, notes))
        
        session_id = c.lastrowid
        
        # Do NOT create other_income here anymore
        # Basis bonus calculation on session end handles all freebies/bonuses
        
        conn.commit()
        conn.close()
        
        # Update daily tax session
        self.update_daily_tax_session(session_date, user_id)
        
        return (session_id, freebies_dollar, reactivated_count, reactivated_basis)
    
    def end_game_session(self, session_id, ending_sc, redeemable_sc=None, notes=None, end_date=None, end_time=None):
        """
        End an active game session.

        Spec v1 behavior:
        - Store ending balances and completion timestamp
        - Mark session Closed
        - Recompute derived fields for this site/user pair
        - Return the computed net taxable P/L for this session
        """
        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute('SELECT * FROM game_sessions WHERE id = ?', (session_id,))
        session = c.fetchone()
        if not session:
            conn.close()
            raise ValueError(f"Session {session_id} not found")

        if redeemable_sc is None:
            redeemable_sc = ending_sc

        # Default end_date/time
        if end_date is None:
            end_date = session['session_date']
        if end_time is None:
            end_time = session['end_time'] or datetime.now().strftime('%H:%M:%S')

        c.execute('''
            UPDATE game_sessions
            SET ending_sc_balance = ?,
                ending_redeemable_sc = ?,
                end_date = ?,
                end_time = ?,
                notes = COALESCE(?, notes),
                status = 'Closed',
                processed = 0
            WHERE id = ?
        ''', (float(ending_sc), float(redeemable_sc), end_date, end_time, notes, session_id))

        site_id = session['site_id']
        user_id = session['user_id']

        conn.commit()
        conn.close()

        # Recompute derived fields for this pair (canonical path)
        self.auto_recalculate_affected_sessions(site_id, user_id, end_date, end_time)

        conn2 = self.db.get_connection()
        c2 = conn2.cursor()
        c2.execute('SELECT COALESCE(net_taxable_pl, total_taxable, 0) AS net_taxable_pl FROM game_sessions WHERE id = ?', (session_id,))
        row = c2.fetchone()
        conn2.close()
        return float(row['net_taxable_pl'] or 0.0)

    def auto_recalculate_affected_sessions(self, site_id, user_id, changed_date, changed_time='00:00:00'):
        """
        Canonical recompute path for a site/user pair.

        This is a full recompute to keep basis pool and expected balances consistent.
        """
        if site_id is None or user_id is None:
            return 0

        if changed_date is not None:
            _ = (changed_date, changed_time)

        self._rebuild_fifo_for_pair(site_id, user_id)
        session_count, touched_dates = self._rebuild_session_tax_fields_for_pair(site_id, user_id)
        for d in touched_dates:
            self.update_daily_tax_session(d, user_id)
        return session_count

    def update_daily_tax_session(self, session_date, user_id):
        """
        Recalculate daily tax session totals from game sessions and other income

        Uses total_taxable (net taxable P/L) for accurate tax calculation
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Sum other income for this day
        c.execute('''
            SELECT COALESCE(SUM(amount), 0) as total_other_income,
                   COUNT(*) as num_items
            FROM other_income
            WHERE date = ? AND user_id = ?
        ''', (session_date, user_id))
        
        other_income_row = c.fetchone()
        total_other_income = other_income_row['total_other_income']
        num_other_income = other_income_row['num_items']
        
        # Sum game session total_taxable for this day (net taxable P/L)
        c.execute('''
            SELECT COALESCE(SUM(total_taxable), 0) as total_session_pnl,
                   COUNT(*) as num_sessions
            FROM game_sessions
            WHERE session_date = ? AND user_id = ? AND status = 'Closed'
        ''', (session_date, user_id))
        
        session_row = c.fetchone()
        total_session_pnl = session_row['total_session_pnl']
        num_sessions = session_row['num_sessions']
        
        # Calculate net (Other Income is now only from manual entries)
        net_daily_pnl = total_other_income + total_session_pnl
        status = 'Win' if net_daily_pnl >= 0 else 'Loss'
        
        # If no sessions and no other income, delete the daily tax session
        if num_sessions == 0 and num_other_income == 0:
            c.execute('''
                DELETE FROM daily_tax_sessions
                WHERE session_date = ? AND user_id = ?
            ''', (session_date, user_id))
        else:
            # Insert or update daily tax session
            c.execute('''
                INSERT INTO daily_tax_sessions 
                (session_date, user_id, total_other_income, total_session_pnl, 
                 net_daily_pnl, status, num_game_sessions, num_other_income_items)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_date, user_id) DO UPDATE SET
                    total_other_income = excluded.total_other_income,
                    total_session_pnl = excluded.total_session_pnl,
                    net_daily_pnl = excluded.net_daily_pnl,
                    status = excluded.status,
                    num_game_sessions = excluded.num_game_sessions,
                    num_other_income_items = excluded.num_other_income_items
            ''', (session_date, user_id, total_other_income, total_session_pnl,
                  net_daily_pnl, status, num_sessions, num_other_income))
        
        conn.commit()
        conn.close()
