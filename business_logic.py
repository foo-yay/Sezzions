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
    
    def calculate_cost_basis(self, site_id, redemption_amount, user_id, redemption_date, redemption_time='23:59:59'):
        """
        Calculate FIFO cost basis for a redemption
        
        Args:
            redemption_time: Time of redemption (defaults to end-of-day for backwards compatibility)
                           Ensures FIFO only allocates from purchases on or before redemption timestamp
        
        Returns:
            tuple: (cost_basis, allocations) where allocations is list of (purchase_id, allocated_amount)
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Treat NULL redemption_time as '00:00:00' for consistency
        if not redemption_time:
            redemption_time = '00:00:00'
        
        # Get purchases with remaining balance, ordered by FIFO (oldest first)
        # Only include purchases on or before the redemption timestamp
        c.execute('''
            SELECT id, amount, remaining_amount, sc_received
            FROM purchases
            WHERE site_id = ? AND user_id = ? AND remaining_amount > 0
              AND (purchase_date < ? OR 
                   (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') <= ?))
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
        ''', (site_id, user_id, redemption_date, redemption_date, redemption_time))
        
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
    
    # Administrative fields that don't affect financial calculations
    # Changes to these fields alone should NOT trigger recalculation
    ADMINISTRATIVE_FIELDS = {
        'session': {'notes'},
        'purchase': {'notes'},
        'redemption': {'notes', 'redemption_method_id', 'receipt_date', 'processed'}
    }
    
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
                
                # Rebuild game session event links after session tax fields
                self.rebuild_game_session_event_links_for_pair(s_id, u_id)

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

        c.execute("""
            DELETE FROM redemption_allocations
            WHERE redemption_id IN (
                SELECT id FROM redemptions WHERE site_id = ? AND user_id = ?
            )
        """, (site_id, user_id))

        # Reset site_sessions totals to 0 before reprocessing redemptions
        # This prevents double-counting when rebuild is called multiple times
        c.execute("""
            UPDATE site_sessions
            SET total_buyin = 0.0, total_redeemed = 0.0, status = 'Active'
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

    def _rebuild_fifo_for_pair_from(self, site_id, user_id, from_date, from_time):
        """
        Scoped FIFO rebuild: undo + replay redemptions >= from_dt only.
        
        Steps:
        1. Query suffix redemptions >= from_dt
        2. Validate free SC (non-free redemptions MUST have allocations)
        3. Undo allocations (restore purchases.remaining_amount)
        4. Delete allocations and tax_sessions for suffix
        5. Replay suffix redemptions chronologically
        6. Update site_session aggregates
        
        Raises exception if missing allocations detected (triggers fallback to full).
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Normalize time
        from_time = from_time or '00:00:00'
        if len(from_time) == 5:
            from_time += ':00'
        
        # Step 1: Identify suffix redemptions >= from_dt
        c.execute("""
            SELECT id, site_id, user_id, amount, redemption_date, redemption_time,
                   COALESCE(is_free_sc, 0) as is_free_sc,
                   COALESCE(more_remaining, 0) AS more_remaining
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR 
                   (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id, from_date, from_date, from_time))
        
        suffix_redemptions = c.fetchall()
        
        if not suffix_redemptions:
            conn.close()
            return  # Nothing to rebuild
        
        # Step 2: Validate free SC allocations BEFORE undo
        suffix_ids = [r['id'] for r in suffix_redemptions]
        
        for r in suffix_redemptions:
            is_free = r['is_free_sc']
            redemption_amount = r['amount'] or 0
            
            if is_free == 0:  # Non-free redemption
                # REQUIRE allocations that sum to amount
                c.execute("""
                    SELECT COALESCE(SUM(allocated_amount), 0) as total_allocated
                    FROM redemption_allocations
                    WHERE redemption_id = ?
                """, (r['id'],))
                row = c.fetchone()
                allocated = row['total_allocated'] if row else 0
                
                if abs(allocated - redemption_amount) > 0.01:  # Allow small floating point error
                    conn.close()
                    raise Exception(
                        f"Missing/incomplete allocations for non-free redemption {r['id']}: "
                        f"expected {redemption_amount}, found {allocated}. Fallback to full rebuild."
                    )
        
        # Step 3: Undo allocations - restore purchases.remaining_amount
        # For each allocation, add back to purchase
        c.execute("""
            SELECT purchase_id, allocated_amount
            FROM redemption_allocations
            WHERE redemption_id IN ({})
        """.format(','.join('?' * len(suffix_ids))), suffix_ids)
        
        allocations_to_undo = c.fetchall()
        
        for alloc in allocations_to_undo:
            purchase_id = alloc['purchase_id']
            allocated_amt = alloc['allocated_amount']
            
            # Restore, ensuring we don't exceed original amount
            c.execute("""
                UPDATE purchases
                SET remaining_amount = MIN(amount, remaining_amount + ?)
                WHERE id = ?
            """, (allocated_amt, purchase_id))
        
        # Step 4: Delete allocations and tax_sessions for suffix
        c.execute("""
            DELETE FROM redemption_allocations
            WHERE redemption_id IN ({})
        """.format(','.join('?' * len(suffix_ids))), suffix_ids)
        
        c.execute("""
            DELETE FROM tax_sessions
            WHERE redemption_id IN ({})
        """.format(','.join('?' * len(suffix_ids))), suffix_ids)
        
        conn.commit()
        
        # Step 5: Replay suffix redemptions chronologically
        for r in suffix_redemptions:
            self.process_redemption(
                r['id'],
                r['site_id'],
                float(r['amount'] or 0.0),
                r['redemption_date'],
                r['redemption_time'],
                r['user_id'],
                int(r['is_free_sc']),
                int(r['more_remaining']),
                is_edit=True,  # Don't create duplicate records
            )
        
        # Step 6: Update site_session aggregates for affected site_sessions
        # Get distinct site_session_ids from suffix redemptions
        c.execute("""
            SELECT DISTINCT site_session_id
            FROM redemptions
            WHERE id IN ({}) AND site_session_id IS NOT NULL
        """.format(','.join('?' * len(suffix_ids))), suffix_ids)
        
        affected_site_sessions = [row['site_session_id'] for row in c.fetchall()]
        
        if affected_site_sessions:
            for site_session_id in affected_site_sessions:
                # Recompute total_redeemed from authoritative data
                c.execute("""
                    UPDATE site_sessions
                    SET total_redeemed = (
                        SELECT COALESCE(SUM(amount), 0)
                        FROM redemptions
                        WHERE site_session_id = ?
                    )
                    WHERE id = ?
                """, (site_session_id, site_session_id))
        
        conn.commit()
        conn.close()

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
              AND (purchase_date < ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') <= ?))
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id, chk_date, chk_date, chk_time, as_of_date, as_of_date, as_of_time))
        for r in c.fetchall():
            expected_total += float(r[0] or 0.0)

        c.execute("""
            SELECT amount
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
              AND (redemption_date < ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') <= ?))
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
                    site_id, total_remaining, user_id, redemption_date, redemption_time
                )
            else:
                # More redemptions expected - just use FIFO for this redemption amount
                cost_basis, allocations = self.fifo_calc.calculate_cost_basis(
                    site_id, redemption_amount, user_id, redemption_date, redemption_time
                )
            
            self.fifo_calc.apply_allocation(allocations)
        
        net_pl = redemption_amount - cost_basis
        
        conn = self.db.get_connection()
        c = conn.cursor()

        c.execute("DELETE FROM redemption_allocations WHERE redemption_id = ?", (redemption_id,))
        if allocations:
            c.executemany(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                [(redemption_id, purchase_id, allocated) for purchase_id, allocated in allocations],
            )

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
        # Loss date has no specific time, use end-of-day default
        cost_basis, allocations = self.fifo_calc.calculate_cost_basis(
            site_id, remaining_balance, user_id, loss_date, '23:59:59'
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
        c.execute("DELETE FROM redemption_allocations WHERE redemption_id = ?", (redemption_id,))
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

    def _rebuild_session_tax_fields_for_pair(self, site_id, user_id, old_session_values=None):
        """
        Recompute derived session fields per spec (v2):
        - expected_start_total_sc / expected_start_redeemable_sc
        - session_basis (cash purchases since last completed session end)
        - basis_consumed (cash basis used in this session)
        - delta_total / delta_redeem
        - inferred_start deltas
        - net_taxable_pl (discoverable + delta_play - basis_consumed)
        - pending basis pool (carry-forward cash basis consumed only on redeemable gains)
        
        old_session_values: Optional dict with {'session_id', 'wager_amount', 'delta_total', 'game_id'}
                           for accurate RTP delta calculation when editing a session.
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
                   COALESCE(ending_redeemable_sc, COALESCE(ending_sc_balance,0)) as ending_redeemable_sc,
                   wager_amount, game_id, delta_total
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

            # Defensive: if end_dt < start_dt or equal, fix it and log warning
            if end_dt and start_dt:
                if end_dt < start_dt:
                    print(f"WARNING: Session {sid} ends before it starts! Fixing: {s['session_date']} {s['start_time']} -> {s['end_date']} {s['end_time']}")
                    end_dt = start_dt
                elif end_dt == start_dt:
                    print(f"WARNING: Session {sid} starts and ends at the same time! Adding 1 second: {s['session_date']} {s['start_time']}")
                    # Add 1 second to end time
                    from datetime import timedelta
                    end_dt = end_dt + timedelta(seconds=1)

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

            # Calculate RTP (Return to Player) if wager_amount is provided
            # RTP = (wager + net_change) / wager * 100
            # Example: Wager 1000 SC, lose 100 SC -> (1000 - 100) / 1000 = 90%
            wager = s['wager_amount']
            if wager and float(wager) > 0:
                rtp = ((float(wager) + delta_total) / float(wager)) * 100
            else:
                rtp = None

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
                    rtp=?,
                    basis_bonus=NULL,
                    gameplay_pnl=NULL
                WHERE id=?
            """, (session_basis, basis_consumed, expected_start_total, expected_start_redeem,
                  inferred_start_total_delta, inferred_start_redeem_delta,
                  delta_total, delta_redeem, net_taxable_pl, net_taxable_pl, delta_total, rtp, sid))

            # Update game RTP aggregates ONLY if this is the session being edited
            # (has old_session_values). Don't re-process unchanged sessions during rebuild.
            if old_session_values and old_session_values.get('session_id') == sid:
                if 'game_id' in s.keys() and s['game_id'] and wager:
                    # Use provided old values for accurate delta calculation
                    old_wager = old_session_values.get('wager_amount', 0.0)
                    old_delta_total = old_session_values.get('delta_total', 0.0)
                    
                    # Calculate deltas
                    wager_delta = float(wager) - float(old_wager or 0.0)
                    delta_total_delta = delta_total - float(old_delta_total or 0.0)
                    
                    # Determine if this is a new session (had no wager before, now has wager)
                    is_new_session = (old_wager is None or float(old_wager or 0.0) == 0.0) and float(wager) > 0.0
                    
                    # Update game RTP incrementally (pass existing connection to avoid lock)
                    self.update_game_rtp_incremental(s['game_id'], wager_delta, delta_total_delta, is_new_session, conn)

            # Advance checkpoint
            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt
            touched_dates.add(s['session_date'])

        conn.commit()
        conn.close()
        return len(sessions), touched_dates

    def _rebuild_session_tax_fields_for_pair_from(self, site_id, user_id, from_date, from_time, old_session_values=None):
        """
        Scoped session rebuild: recompute sessions >= from_dt only.
        
        Steps:
        1. Get checkpoint state from last session before from_dt
        2. Query suffix sessions >= from_dt (use end_dt for filtering)
        3. Capture old wager/delta/game_id for RTP change detection
        4. Clear redemption->session links for suffix
        5. Process suffix sessions (compute expected_balance chain)
        6. Detect RTP changes and update incrementally
        
        Returns: (session_count, touched_dates)
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Normalize time
        from_time = from_time or '00:00:00'
        if len(from_time) == 5:
            from_time += ':00'
        
        # Step 1: Get checkpoint state
        try:
            checkpoint = self._get_session_checkpoint(site_id, user_id, from_date, from_time)
            last_end_total = checkpoint['ending_balance']
            last_end_redeem = checkpoint.get('locked_sc', 0)  # May need adjustment based on schema
            
            # If no prior checkpoint, use None to indicate "beginning of history"
            # This must match full rebuild's initial checkpoint_end_dt = None
            if checkpoint.get('checkpoint_id') is None:
                checkpoint_end_dt = None
            else:
                # Query the actual end datetime of the checkpoint session
                c.execute("""
                    SELECT end_date, end_time
                    FROM game_sessions
                    WHERE id = ?
                """, (checkpoint['checkpoint_id'],))
                ckpt_row = c.fetchone()
                if ckpt_row:
                    checkpoint_end_dt = self._dt(ckpt_row['end_date'], ckpt_row['end_time'])
                else:
                    checkpoint_end_dt = None
        except Exception as e:
            # Checkpoint validation failed - fallback to full rebuild
            conn.close()
            raise Exception(f"Checkpoint validation failed: {e}. Fallback to full rebuild required.")
        
        # Step 2: Query suffix sessions where end_dt >= from_dt (inclusive)
        # We need to recompute any session that could be affected
        c.execute("""
            SELECT id, session_date, COALESCE(start_time,'00:00:00') as start_time,
                   COALESCE(end_date, session_date) as end_date,
                   COALESCE(end_time,'00:00:00') as end_time,
                   COALESCE(starting_sc_balance,0) as starting_sc_balance,
                   COALESCE(ending_sc_balance,0) as ending_sc_balance,
                   COALESCE(starting_redeemable_sc, COALESCE(starting_sc_balance,0)) as starting_redeemable_sc,
                   COALESCE(ending_redeemable_sc, COALESCE(ending_sc_balance,0)) as ending_redeemable_sc,
                   wager_amount, game_id, delta_total
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (COALESCE(end_date, session_date) > ? 
                   OR (COALESCE(end_date, session_date) = ? AND COALESCE(end_time,'00:00:00') >= ?))
            ORDER BY session_date ASC, COALESCE(start_time,'00:00:00') ASC, id ASC
        """, (site_id, user_id, from_date, from_date, from_time))
        
        sessions = c.fetchall()
        
        if not sessions:
            conn.close()
            return 0, set()
        
        # Step 3: Capture old state for RTP change detection
        old_rtp_state = {}  # {session_id: (wager, delta_total, game_id)}
        for s in sessions:
            old_rtp_state[s['id']] = (
                s['wager_amount'] or 0,
                s['delta_total'] or 0,
                s['game_id']
            )
        
        # Step 4: Clear redemption->session links for suffix sessions
        suffix_session_ids = [s['id'] for s in sessions]
        c.execute("""
            UPDATE redemptions
            SET site_session_id = NULL
            WHERE site_session_id IN ({})
        """.format(','.join('?' * len(suffix_session_ids))), suffix_session_ids)
        
        conn.commit()
        
        # Step 5: Process suffix sessions (similar to full rebuild logic)
        touched_dates = set()
        pending_basis = 0.0
        
        for s in sessions:
            sid = s['id']
            session_date = s['session_date']
            start_time = s['start_time']
            end_date = s['end_date']
            end_time = s['end_time']
            
            start_total = float(s['starting_sc_balance'] or 0.0)
            end_total = float(s['ending_sc_balance'] or 0.0)
            start_red = float(s['starting_redeemable_sc'] or 0.0)
            end_red = float(s['ending_redeemable_sc'] or 0.0)
            wager = s['wager_amount']
            game_id = s['game_id']
            
            # Compute expected balances from checkpoint + interim transactions
            expected_total, expected_redeem = self._compute_expected_for_session(
                site_id, user_id, session_date, start_time,
                last_end_total, last_end_redeem, checkpoint_end_dt, c
            )
            
            # Compute delta_total and delta_redeem
            delta_total = end_total - start_total
            delta_redeem = end_red - start_red
            
            # Compute discoverable freebies and locked SC processing (match full rebuild)
            discoverable_sc = max(0.0, start_red - expected_redeem) if expected_redeem is not None else 0.0
            delta_play_sc = delta_redeem
            locked_start = max(0.0, start_total - start_red)
            locked_end = max(0.0, end_total - end_red)
            locked_processed_sc = max(locked_start - locked_end, 0.0)
            
            # Use 1:1 SC to dollar rate
            sc_rate = 1.0
            locked_processed_value = locked_processed_sc * sc_rate
            
            # Compute inferred starting deltas
            inferred_start_delta_total = (start_total - expected_total) if expected_total is not None else 0.0
            inferred_start_delta_redeem = (start_red - expected_redeem) if expected_redeem is not None else 0.0
            
            # Compute session basis (cash purchases since last checkpoint)
            session_basis = self._compute_session_basis(site_id, user_id, checkpoint_end_dt, end_date, end_time, c)
            pending_basis += session_basis
            
            # Consume basis against locked processed value
            basis_consumed = min(pending_basis, locked_processed_value)
            pending_basis = max(0.0, pending_basis - basis_consumed)
            
            # Net taxable = (discoverable + delta_play) * rate - basis_consumed
            net_taxable_pl = ((discoverable_sc + delta_play_sc) * sc_rate) - basis_consumed
            
            # Calculate end_dt for checkpoint advancement (must match full rebuild format)
            end_dt = self._dt(end_date, end_time)
            
            # Note: We don't check for redemptions at session end in scoped rebuild
            # because the FIFO rebuild already processed all redemptions correctly
            
            # Update session with computed fields (match full rebuild columns)
            c.execute("""
                UPDATE game_sessions
                SET expected_start_total_sc = ?,
                    expected_start_redeemable_sc = ?,
                    inferred_start_total_delta = ?,
                    inferred_start_redeemable_delta = ?,
                    session_basis = ?,
                    basis_consumed = ?,
                    delta_total = ?,
                    delta_redeem = ?,
                    net_taxable_pl = ?
                WHERE id = ?
            """, (expected_total, expected_redeem,
                  inferred_start_delta_total, inferred_start_delta_redeem,
                  session_basis, basis_consumed,
                  delta_total, delta_redeem,
                  net_taxable_pl, sid))
            
            # Step 6: RTP change detection and incremental update
            old_wager, old_delta, old_game = old_rtp_state.get(sid, (0, 0, None))
            
            # Check if wager or delta changed
            current_wager = wager or 0
            current_delta = delta_total
            current_game = game_id
            
            if (current_wager != old_wager or current_delta != old_delta or current_game != old_game):
                # RTP changed - update incrementally
                
                # If game changed, remove from old and add to new
                if old_game != current_game:
                    if old_game:
                        self.update_game_rtp_incremental(old_game, -old_wager, -old_delta, False, conn)
                    if current_game:
                        self.update_game_rtp_incremental(current_game, current_wager, current_delta, False, conn)
                else:
                    # Same game - use deltas
                    if current_game:
                        wager_delta = current_wager - old_wager
                        delta_delta = current_delta - old_delta
                        
                        # Check if this is the originally edited session
                        is_new_session = False
                        if old_session_values and old_session_values.get('session_id') == sid:
                            # Use old_session_values for accurate delta if this is edited session
                            old_wager_from_edit = old_session_values.get('wager_amount', 0) or 0
                            old_delta_from_edit = old_session_values.get('delta_total', 0) or 0
                            wager_delta = current_wager - old_wager_from_edit
                            delta_delta = current_delta - old_delta_from_edit
                            is_new_session = (old_wager_from_edit == 0 and current_wager > 0)
                        
                        if wager_delta != 0 or delta_delta != 0:
                            self.update_game_rtp_incremental(current_game, wager_delta, delta_delta, is_new_session, conn)
            
            # Advance checkpoint to this session's end datetime (must match full rebuild)
            last_end_total = end_total
            last_end_redeem = end_red
            checkpoint_end_dt = end_dt
            touched_dates.add(session_date)
        
        conn.commit()
        conn.close()
        return len(sessions), touched_dates
    
    def _compute_expected_for_session(self, site_id, user_id, session_date, start_time, 
                                      last_end_total, last_end_redeem, checkpoint_end_dt, cursor):
        """Helper to compute expected balances from checkpoint + interim transactions."""
        # Query purchases/redemptions between checkpoint and session start
        start_dt = self._dt(session_date, start_time)
        
        # If checkpoint_end_dt is None, use a very early date to include all history
        if checkpoint_end_dt is None:
            checkpoint_end_dt = '1900-01-01 00:00:00'
        
        cursor.execute("""
            SELECT COALESCE(SUM(sc_received), 0) as total_sc
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') > ?))
              AND (purchase_date < ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') <= ?))
        """, (site_id, user_id, checkpoint_end_dt, checkpoint_end_dt, '00:00:00', session_date, session_date, start_time))
        
        row = cursor.fetchone()
        purchases_sc = row['total_sc'] if row else 0
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_redeemed
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') > ?))
              AND (redemption_date < ? OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') <= ?))
        """, (site_id, user_id, checkpoint_end_dt, checkpoint_end_dt, '00:00:00', session_date, session_date, start_time))
        
        row = cursor.fetchone()
        redemptions_sc = row['total_redeemed'] if row else 0
        
        expected_total = last_end_total + purchases_sc - redemptions_sc
        expected_redeem = last_end_redeem - redemptions_sc  # Redeemable DOES NOT include purchases
        
        return expected_total, expected_redeem
    
    def _compute_session_basis(self, site_id, user_id, checkpoint_end_dt, end_date, end_time, cursor):
        """Helper to compute cash basis (purchases) for a session window."""
        # If checkpoint_end_dt is None, use a very early date to include all history
        if checkpoint_end_dt is None:
            checkpoint_end_dt = '1900-01-01 00:00:00'
        
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_basis
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') > ?))
              AND (purchase_date < ? OR (purchase_date = ? AND COALESCE(purchase_time,'00:00:00') <= ?))
        """, (site_id, user_id, checkpoint_end_dt, checkpoint_end_dt, '00:00:00', end_date, end_date, end_time))
        
        row = cursor.fetchone()
        return row['total_basis'] if row else 0

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
        
        # Rebuild event links for this session
        self.rebuild_game_session_event_links_for_pair(site_id, user_id)
        
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

    def find_containing_session_start(self, site_id, user_id, d, t):
        """
        Find the start timestamp of the session (open or closed) that contains timestamp (d, t).
        
        A session contains ts if:
        - start_dt <= ts
        - AND (end_date IS NULL OR ts <= end_dt)
        
        Returns: (start_date, start_time) tuple or None if no containing session found
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Normalize time
        ts_time = t or '00:00:00'
        if len(ts_time) == 5:
            ts_time += ':00'
        
        cursor.execute("""
            SELECT session_date, COALESCE(start_time,'00:00:00') as start_time
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (session_date < ? OR (session_date = ? AND COALESCE(start_time,'00:00:00') <= ?))
              AND (end_date IS NULL 
                   OR ? < end_date 
                   OR (? = end_date AND ? <= COALESCE(end_time,'23:59:59')))
            ORDER BY session_date DESC, COALESCE(start_time,'00:00:00') DESC
            LIMIT 1
        """, (site_id, user_id, d, d, ts_time, d, d, ts_time))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return (row['session_date'], row['start_time'])
        return None

    def _get_session_checkpoint(self, site_id, user_id, boundary_date, boundary_time):
        """
        Get checkpoint state from last closed session before boundary.
        
        Returns dict with:
        - ending_balance, locked_sc: State to seed suffix rebuild
        - checkpoint_id: ID of the checkpoint session
        
        Raises CheckpointValidationError if checkpoint is invalid.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, end_date, end_time, ending_sc_balance, ending_redeemable_sc
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND status = 'Closed'
              AND (session_date < ? OR (session_date = ? AND COALESCE(start_time,'00:00:00') < ?))
            ORDER BY 
              COALESCE(end_date, session_date) DESC,
              COALESCE(end_time, '00:00:00') DESC
            LIMIT 1
        """, (site_id, user_id, boundary_date, boundary_date, boundary_time))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            # No prior session - start from zero
            return {'ending_balance': 0, 'locked_sc': 0, 'checkpoint_id': None}
        
        ending_balance = row['ending_sc_balance']
        locked_sc = row['ending_redeemable_sc']
        
        # Validate checkpoint
        if ending_balance is None or locked_sc is None:
            raise Exception(f"Checkpoint validation failed: NULL values (session_id={row['id']})")
        
        if ending_balance < 0 or locked_sc < 0:
            raise Exception(f"Checkpoint validation failed: negative values (session_id={row['id']})")
        
        return {
            'ending_balance': ending_balance,
            'locked_sc': locked_sc,
            'checkpoint_id': row['id']
        }

    def auto_recalculate_affected_sessions(self, site_id, user_id, changed_date=None, changed_time='00:00:00', 
                                           old_session_values=None, old_ts=None, new_ts=None, scoped=True,
                                           entity_type=None, old_values=None, new_values=None):
        """
        Orchestrator for scoped vs full rebuild.
        
        Supports both legacy calls and new scoped API:
        - Legacy: auto_recalculate(site, user, changed_date, changed_time, old_session_values)
        - New: auto_recalculate(site, user, old_ts=(d,t), new_ts=(d,t), scoped=True, ...)
        
        Args:
            site_id, user_id: Pair to recompute
            changed_date, changed_time: Legacy params (mapped to new_ts)
            old_session_values: Legacy RTP dict (for session edits)
            old_ts, new_ts: New params - tuples of (date, time) for old/new timestamps
            scoped: If True, attempt scoped rebuild; if False, force full rebuild
            entity_type: 'session', 'purchase', 'redemption' (for skip logic)
            old_values, new_values: Full old/new record dicts (for field-specific skip)
        
        Execution order:
        1. Skip logic (notes-only, redemption_method_id-only)
        2. RTP-only logic (wager/game_id changes)
        3. Compute boundary T from containing sessions
        4. Try scoped rebuild (with fallback to full on errors)
        5. Update daily tax summaries
        
        Returns: session_count processed
        """
        if site_id is None or user_id is None:
            return 0
        
        # Backward compatibility: map changed_date/changed_time to new_ts
        if changed_date is not None and new_ts is None:
            new_ts = (changed_date, changed_time or '00:00:00')
        
        # Step 1: Skip logic - administrative-only changes don't affect accounting
        if old_values and new_values:
            changed_fields = {k for k in old_values if old_values.get(k) != new_values.get(k)}
            
            # Get administrative fields for this entity type
            admin_fields_for_type = self.ADMINISTRATIVE_FIELDS.get(entity_type, set())
            
            # If only administrative fields changed, skip recalculation
            if changed_fields and changed_fields <= admin_fields_for_type:
                print(f"[Scoped Recompute] Skipping: only administrative fields changed for {entity_type}: {changed_fields}")
                return 0
        
        # Step 2: RTP-only logic (wager/game_id changes for sessions)
        if old_values and new_values and entity_type == 'session':
            rtp_only_fields = {'wager_amount', 'game_id'}
            changed_fields = {k for k in old_values if old_values.get(k) != new_values.get(k)}
            
            if changed_fields and changed_fields <= rtp_only_fields:
                # Only RTP changed - update incrementally and return
                print(f"[Scoped Recompute] RTP-only change detected for session {old_values.get('id')}")
                session_id = old_values.get('id') or new_values.get('id')
                self._update_session_rtp_only(session_id, old_values, new_values)
                return 0
        
        # Step 3: Determine if we should attempt scoped rebuild
        if not scoped:
            print(f"[Scoped Recompute] Full rebuild requested (scoped=False)")
            # Force full rebuild
            self._rebuild_fifo_for_pair(site_id, user_id)
            session_count, touched_dates = self._rebuild_session_tax_fields_for_pair(site_id, user_id, old_session_values)
            for d in touched_dates:
                self.update_daily_tax_session(d, user_id)
            # Rebuild game session event links (full)
            self.rebuild_game_session_event_links_for_pair(site_id, user_id)
            return session_count
        
        # Step 4: Compute boundary T for scoped rebuild
        try:
            boundaries = []
            
            # Consider old_ts
            if old_ts and len(old_ts) == 2:
                old_date, old_time = old_ts
                containing = self.find_containing_session_start(site_id, user_id, old_date, old_time)
                boundaries.append(containing if containing else old_ts)
            
            # Consider new_ts
            if new_ts and len(new_ts) == 2:
                new_date, new_time = new_ts
                containing = self.find_containing_session_start(site_id, user_id, new_date, new_time)
                boundaries.append(containing if containing else new_ts)
            
            if not boundaries:
                # No timestamps provided - fallback to full
                print(f"[Scoped Recompute] No timestamps provided, using full rebuild")
                raise Exception("No timestamps for boundary computation")
            
            # T = earliest boundary
            T_date, T_time = min(boundaries, key=lambda x: (x[0], x[1]))
            
            print(f"[Scoped Recompute] Boundary T = {T_date} {T_time}")
            
            # Step 5: Execute scoped rebuild
            print(f"[Scoped Recompute] Starting scoped FIFO rebuild from {T_date} {T_time}")
            self._rebuild_fifo_for_pair_from(site_id, user_id, T_date, T_time)
            
            print(f"[Scoped Recompute] Starting scoped session rebuild from {T_date} {T_time}")
            session_count, touched_dates = self._rebuild_session_tax_fields_for_pair_from(
                site_id, user_id, T_date, T_time, old_session_values
            )
            
            print(f"[Scoped Recompute] Scoped rebuild complete: {session_count} sessions, {len(touched_dates)} dates")
            
            # Update daily tax summaries
            for d in touched_dates:
                self.update_daily_tax_session(d, user_id)
            
            # Rebuild game session event links (scoped)
            print(f"[Scoped Recompute] Starting scoped link rebuild from {T_date} {T_time}")
            self.rebuild_game_session_event_links_for_pair_from(site_id, user_id, T_date, T_time)
            
            return session_count
            
        except Exception as e:
            # Fallback to full rebuild on any error
            print(f"[Scoped Recompute] Fallback to FULL rebuild: {e}")
            import traceback
            traceback.print_exc()
            
            self._rebuild_fifo_for_pair(site_id, user_id)
            session_count, touched_dates = self._rebuild_session_tax_fields_for_pair(site_id, user_id, old_session_values)
            for d in touched_dates:
                self.update_daily_tax_session(d, user_id)
            # Rebuild game session event links (full)
            self.rebuild_game_session_event_links_for_pair(site_id, user_id)
            
            print(f"[Scoped Recompute] Full rebuild complete: {session_count} sessions")
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

    def update_game_rtp_incremental(self, game_id, wager_delta, delta_total_delta, new_session=False, conn=None):
        """
        Apply delta to game RTP aggregates and recalculate RTP (O(1) operation).
        Called after session close/edit without full DB traversal.
        
        Args:
            game_id: ID of the game to update
            wager_delta: Change in total wager (positive or negative)
            delta_total_delta: Change in total delta (SC change delta)
            new_session: If True, increment session_count by 1
            conn: Optional existing database connection (if None, creates new one)
        """
        close_conn = False
        if conn is None:
            conn = self.db.get_connection()
            close_conn = True
        
        c = conn.cursor()
        
        try:
            # Load or initialize aggregates
            c.execute('''SELECT * FROM game_rtp_aggregates WHERE game_id = ?''', (game_id,))
            agg_row = c.fetchone()
            
            if agg_row is None:
                # First session for this game - initialize aggregates
                total_wager = max(0, wager_delta)
                total_delta = delta_total_delta
                session_count = 1 if new_session else 0
                
                c.execute('''
                    INSERT INTO game_rtp_aggregates (game_id, total_wager, total_delta, session_count)
                    VALUES (?, ?, ?, ?)
                ''', (game_id, total_wager, total_delta, session_count))
            else:
                # Update existing aggregates
                total_wager = agg_row['total_wager'] + wager_delta
                total_delta = agg_row['total_delta'] + delta_total_delta
                session_count = agg_row['session_count'] + (1 if new_session else 0)
                
                # Ensure totals don't go negative (safety check)
                total_wager = max(0, total_wager)
                
                c.execute('''
                    UPDATE game_rtp_aggregates
                    SET total_wager = ?, total_delta = ?, session_count = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE game_id = ?
                ''', (total_wager, total_delta, session_count, game_id))
            
            # Recalculate RTP from aggregates
            self._recalculate_game_rtp_from_aggregates(game_id, conn)
            
            if close_conn:
                conn.commit()
        except Exception as e:
            print(f"Error updating game RTP incrementally: {e}")
            import traceback
            traceback.print_exc()
            if close_conn:
                conn.rollback()
        finally:
            if close_conn:
                conn.close()

    def _update_session_rtp_only(self, session_id, old_values, new_values, conn=None):
        """
        Update RTP aggregates for a session whose ONLY wager/game_id changed.
        Does NOT trigger FIFO or session chain recomputation.
        
        Args:
            session_id: ID of the session
            old_values: Dict with old wager_amount, delta_total, game_id
            new_values: Dict with new wager_amount, delta_total, game_id
            conn: Optional database connection (reuse to prevent locks)
        """
        own_conn = conn is None
        if own_conn:
            conn = self.db.get_connection()
        
        try:
            # Use the passed-in values directly (don't re-query database)
            new_wager = new_values.get('wager_amount', 0) or 0
            new_delta = new_values.get('delta_total', 0) or 0
            new_game_id = new_values.get('game_id')
            
            old_wager = old_values.get('wager_amount', 0) or 0
            old_delta = old_values.get('delta_total', 0) or 0
            old_game_id = old_values.get('game_id')
            
            print(f"[RTP Update] Session {session_id}:")
            print(f"  Old: wager={old_wager}, delta={old_delta}, game_id={old_game_id}")
            print(f"  New: wager={new_wager}, delta={new_delta}, game_id={new_game_id}")
            
            # Handle game_id change (remove from old, add to new)
            if old_game_id != new_game_id:
                print(f"  Game changed: {old_game_id} -> {new_game_id}")
                if old_game_id:
                    # Remove from old game
                    self.update_game_rtp_incremental(
                        old_game_id, -old_wager, -old_delta, False, conn
                    )
                if new_game_id:
                    # Add to new game
                    self.update_game_rtp_incremental(
                        new_game_id, new_wager, new_delta, False, conn
                    )
            else:
                # Same game - apply deltas
                if new_game_id:
                    wager_delta = new_wager - old_wager
                    delta_delta = new_delta - old_delta
                    print(f"  Deltas: wager_delta={wager_delta}, delta_delta={delta_delta}")
                    if wager_delta != 0 or delta_delta != 0:
                        self.update_game_rtp_incremental(
                            new_game_id, wager_delta, delta_delta, False, conn
                        )
            
            if own_conn:
                conn.commit()
        except Exception as e:
            print(f"Error in _update_session_rtp_only: {e}")
            if own_conn:
                conn.rollback()
        finally:
            if own_conn:
                conn.close()

    def recalculate_game_rtp_full(self, game_id):
        """
        Full RTP recalculation via SQL aggregation (O(N) via GROUP BY).
        User-triggered via "Recalculate RTP" button. Traverses all game_sessions for the game.
        
        Args:
            game_id: ID of the game to recalculate
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        try:
            # Delete existing aggregates for this game
            c.execute('''DELETE FROM game_rtp_aggregates WHERE game_id = ?''', (game_id,))
            
            # Query all game_sessions for this game with status='Closed'
            c.execute('''
                SELECT 
                    SUM(COALESCE(wager_amount, 0)) as total_wager,
                    SUM(COALESCE(delta_total, 0)) as total_delta,
                    COUNT(*) as session_count
                FROM game_sessions
                WHERE game_id = ? AND status = 'Closed'
            ''', (game_id,))
            
            result = c.fetchone()
            total_wager = float(result['total_wager']) if result['total_wager'] else 0.0
            total_delta = float(result['total_delta']) if result['total_delta'] else 0.0
            session_count = int(result['session_count']) if result['session_count'] else 0
            
            # Insert aggregates
            if session_count > 0 or total_wager > 0:
                c.execute('''
                    INSERT INTO game_rtp_aggregates (game_id, total_wager, total_delta, session_count)
                    VALUES (?, ?, ?, ?)
                ''', (game_id, total_wager, total_delta, session_count))
            
            # Recalculate RTP
            self._recalculate_game_rtp_from_aggregates(game_id, conn)
            
            conn.commit()
        except Exception as e:
            print(f"Error recalculating game RTP fully: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _recalculate_game_rtp_from_aggregates(self, game_id, conn=None):
        """
        Internal: Load aggregates and compute actual_rtp.
        Updates both game_rtp_aggregates and games.actual_rtp.
        
        Formula: RTP = ((total_wager + total_delta) / total_wager) * 100
        
        Args:
            game_id: ID of the game
            conn: Optional existing database connection (if None, creates new one)
        """
        close_conn = False
        if conn is None:
            conn = self.db.get_connection()
            close_conn = True
        
        try:
            c = conn.cursor()
            
            # Load aggregates
            c.execute('''SELECT * FROM game_rtp_aggregates WHERE game_id = ?''', (game_id,))
            agg_row = c.fetchone()
            
            if agg_row is None:
                # No aggregates - set RTP to 0
                actual_rtp = 0.0
            else:
                total_wager = float(agg_row['total_wager'])
                total_delta = float(agg_row['total_delta'])
                
                # Calculate RTP: ((wager + delta) / wager) * 100
                if total_wager > 0:
                    actual_rtp = ((total_wager + total_delta) / total_wager) * 100.0
                else:
                    actual_rtp = 0.0
            
            # Update games.actual_rtp
            c.execute('''UPDATE games SET actual_rtp = ? WHERE id = ?''', (actual_rtp, game_id))
            if close_conn:
                conn.commit()
        except Exception as e:
            print(f"Error recalculating RTP from aggregates: {e}")
            import traceback
            traceback.print_exc()
            if close_conn:
                conn.rollback()
        finally:
            if close_conn:
                conn.close()

    def remove_session_from_game_rtp(self, game_id, wager_amount, delta_total):
        """
        Remove a session's contribution from game RTP aggregates.
        Called when a session is deleted.
        
        Args:
            game_id: ID of the game
            wager_amount: Wager amount of the deleted session
            delta_total: delta_total of the deleted session
        """
        if not game_id or not wager_amount:
            return
        
        conn = self.db.get_connection()
        c = conn.cursor()
        
        try:
            # Load aggregates
            c.execute('''SELECT * FROM game_rtp_aggregates WHERE game_id = ?''', (game_id,))
            agg_row = c.fetchone()
            
            if agg_row is None:
                # No aggregates - nothing to remove
                return
            
            # Apply negative deltas
            wager_delta = -float(wager_amount or 0.0)
            delta_total_delta = -float(delta_total or 0.0)
            
            new_wager = max(0, agg_row['total_wager'] + wager_delta)
            new_delta = agg_row['total_delta'] + delta_total_delta
            new_session_count = max(0, agg_row['session_count'] - 1)
            
            c.execute('''
                UPDATE game_rtp_aggregates
                SET total_wager = ?, total_delta = ?, session_count = ?, last_updated = CURRENT_TIMESTAMP
                WHERE game_id = ?
            ''', (new_wager, new_delta, new_session_count, game_id))
            
            # Recalculate RTP
            self._recalculate_game_rtp_from_aggregates(game_id, conn)
            
            conn.commit()
        except Exception as e:
            print(f"Error removing session from game RTP: {e}")
            conn.rollback()
        finally:
            conn.close()

    # ========== Game Session Event Linking ==========
    
    def _ensure_unique_session_start(self, site_id, user_id, session_date, start_time, conn):
        """
        Ensure session start time is unique for the (site_id, user_id) pair.
        If conflict exists, increment start_time by 1 second until unique.
        
        Returns:
            tuple: (final_date, final_time) that is guaranteed unique
        """
        # Treat NULL time as '00:00:00'
        if not start_time:
            start_time = '00:00:00'
        
        c = conn.cursor()
        current_date = session_date
        current_time = start_time
        
        while True:
            # Check if this datetime already exists
            c.execute('''
                SELECT id FROM game_sessions
                WHERE site_id = ? AND user_id = ? 
                  AND session_date = ? 
                  AND COALESCE(start_time, '00:00:00') = ?
            ''', (site_id, user_id, current_date, current_time))
            
            if not c.fetchone():
                # No conflict, this datetime is unique
                return current_date, current_time
            
            # Increment by 1 second
            from datetime import datetime, timedelta
            dt = datetime.strptime(f"{current_date} {current_time}", "%Y-%m-%d %H:%M:%S")
            dt += timedelta(seconds=1)
            current_date = dt.strftime("%Y-%m-%d")
            current_time = dt.strftime("%H:%M:%S")
    
    def rebuild_game_session_event_links_for_pair(self, site_id, user_id):
        """
        Full rebuild of game_session_event_links for a site/user pair.
        Links purchases and redemptions to sessions based on timestamp windows.
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Clear existing links for this pair
        c.execute('''
            DELETE FROM game_session_event_links
            WHERE game_session_id IN (
                SELECT id FROM game_sessions WHERE site_id = ? AND user_id = ?
            )
        ''', (site_id, user_id))
        
        # Load all sessions (Active and Closed) in chronological order
        # Active sessions use session_date + start_time as their effective end for linking purposes
        c.execute('''
            SELECT id, session_date, 
                   COALESCE(start_time, '00:00:00') as start_time,
                   end_date, COALESCE(end_time, '23:59:59') as end_time,
                   status
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
            ORDER BY 
                COALESCE(end_date, session_date) ASC, 
                COALESCE(end_time, start_time, '00:00:00') ASC, 
                id ASC
        ''', (site_id, user_id))
        
        sessions = c.fetchall()
        
        if not sessions:
            conn.commit()
            conn.close()
            return
        
        # Load all purchases and redemptions for this pair
        c.execute('''
            SELECT id, purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND purchase_date IS NOT NULL
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
        ''', (site_id, user_id))
        purchases = c.fetchall()
        
        c.execute('''
            SELECT id, redemption_date, COALESCE(redemption_time, '00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND redemption_date IS NOT NULL
            ORDER BY redemption_date ASC, COALESCE(redemption_time, '00:00:00') ASC, id ASC
        ''', (site_id, user_id))
        redemptions = c.fetchall()
        
        links_to_insert = []
        
        # Process each session
        for i, session in enumerate(sessions):
            session_id = session['id']
            start_dt = self._dt(session['session_date'], session['start_time'])
            
            # For Active sessions, end_dt is not yet known - treat as "now" for linking purposes
            if session['status'] == 'Active' or session['end_date'] is None:
                end_dt = None  # Active session has no end yet
            else:
                end_dt = self._dt(session['end_date'], session['end_time'])
            
            # Determine prev_end_dt and next_start_dt for gap windows
            prev_end_dt = None
            if i > 0:
                prev_session = sessions[i - 1]
                if prev_session['end_date']:
                    prev_end_dt = self._dt(prev_session['end_date'], prev_session['end_time'])
            
            next_start_dt = None
            if i < len(sessions) - 1:
                next_session = sessions[i + 1]
                next_start_dt = self._dt(next_session['session_date'], next_session['start_time'])
            
            # Link purchases
            for p in purchases:
                p_dt = self._dt(p['purchase_date'], p['purchase_time'])
                
                # DURING: >= start_dt AND <= end_dt (only for closed sessions)
                if end_dt and start_dt <= p_dt <= end_dt:
                    links_to_insert.append((session_id, 'purchase', p['id'], 'DURING'))
                # BEFORE: > prev_end_dt AND < start_dt (exclusive both ends)
                elif prev_end_dt is None or (prev_end_dt < p_dt < start_dt):
                    if prev_end_dt is None and p_dt < start_dt:
                        # All purchases before first session
                        links_to_insert.append((session_id, 'purchase', p['id'], 'BEFORE'))
                    elif prev_end_dt is not None and prev_end_dt < p_dt < start_dt:
                        # Purchases in gap
                        links_to_insert.append((session_id, 'purchase', p['id'], 'BEFORE'))
            
            # Link redemptions (only for closed sessions)
            if end_dt:
                for r in redemptions:
                    r_dt = self._dt(r['redemption_date'], r['redemption_time'])
                    
                    # DURING: >= start_dt AND <= end_dt
                    if start_dt <= r_dt <= end_dt:
                        links_to_insert.append((session_id, 'redemption', r['id'], 'DURING'))
                    # AFTER: > end_dt AND < next_start_dt (exclusive both ends)
                    elif next_start_dt is None or (end_dt < r_dt < next_start_dt):
                        if next_start_dt is None and r_dt > end_dt:
                            # All redemptions after last session
                            links_to_insert.append((session_id, 'redemption', r['id'], 'AFTER'))
                        elif next_start_dt is not None and end_dt < r_dt < next_start_dt:
                            # Redemptions in gap
                            links_to_insert.append((session_id, 'redemption', r['id'], 'AFTER'))
        
        # Insert all links
        if links_to_insert:
            c.executemany('''
                INSERT OR IGNORE INTO game_session_event_links 
                (game_session_id, event_type, event_id, relation)
                VALUES (?, ?, ?, ?)
            ''', links_to_insert)
        
        conn.commit()
        conn.close()
    
    def rebuild_game_session_event_links_for_pair_from(self, site_id, user_id, from_date, from_time='00:00:00'):
        """
        Scoped rebuild of game_session_event_links starting from a boundary date/time.
        Only rebuilds links for sessions whose end_dt >= boundary.
        
        This mirrors the scoped session rebuild pattern for performance.
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        boundary_dt = self._dt(from_date, from_time or '00:00:00')
        
        # Find sessions to rebuild (suffix sessions with effective_end >= boundary)
        # Active sessions use session_date + start_time as their effective end
        c.execute('''
            SELECT id, session_date, 
                   COALESCE(start_time, '00:00:00') as start_time,
                   end_date, COALESCE(end_time, '23:59:59') as end_time,
                   status
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (
                  (status = 'Closed' AND end_date IS NOT NULL 
                   AND (end_date > ? OR (end_date = ? AND COALESCE(end_time, '00:00:00') >= ?)))
                  OR
                  (status = 'Active' 
                   AND (session_date > ? OR (session_date = ? AND COALESCE(start_time, '00:00:00') >= ?)))
              )
            ORDER BY 
                COALESCE(end_date, session_date) ASC, 
                COALESCE(end_time, start_time, '00:00:00') ASC, 
                id ASC
        ''', (site_id, user_id, from_date, from_date, from_time, from_date, from_date, from_time))
        
        suffix_sessions = c.fetchall()
        
        if not suffix_sessions:
            conn.commit()
            conn.close()
            return
        
        suffix_session_ids = [s['id'] for s in suffix_sessions]
        
        # Delete existing links for suffix sessions only
        placeholders = ','.join('?' * len(suffix_session_ids))
        c.execute(f'''
            DELETE FROM game_session_event_links
            WHERE game_session_id IN ({placeholders})
        ''', suffix_session_ids)
        
        # Find checkpoint session (last session before boundary)
        checkpoint_session = self._get_session_checkpoint(site_id, user_id, from_date, from_time)
        
        prev_end_dt = None
        if checkpoint_session:
            prev_end_dt = self._dt(
                checkpoint_session['end_date'],
                checkpoint_session['end_time'] if checkpoint_session['end_time'] else '23:59:59'
            )
        
        # Load purchases/redemptions that might link to suffix sessions
        # Need to include events from prev_end_dt onwards (or all if no checkpoint)
        if prev_end_dt:
            prev_date = prev_end_dt[:10]  # Extract date portion
            prev_time = prev_end_dt[11:]  # Extract time portion
        else:
            prev_date = '1900-01-01'
            prev_time = '00:00:00'
        
        c.execute('''
            SELECT id, purchase_date, COALESCE(purchase_time, '00:00:00') as purchase_time
            FROM purchases
            WHERE site_id = ? AND user_id = ?
              AND purchase_date IS NOT NULL
              AND (purchase_date > ? OR (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') > ?))
            ORDER BY purchase_date ASC, COALESCE(purchase_time, '00:00:00') ASC, id ASC
        ''', (site_id, user_id, prev_date, prev_date, prev_time))
        purchases = c.fetchall()
        
        c.execute('''
            SELECT id, redemption_date, COALESCE(redemption_time, '00:00:00') as redemption_time
            FROM redemptions
            WHERE site_id = ? AND user_id = ?
              AND redemption_date IS NOT NULL
              AND (redemption_date > ? OR (redemption_date = ? AND COALESCE(redemption_time, '00:00:00') > ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time, '00:00:00') ASC, id ASC
        ''', (site_id, user_id, prev_date, prev_date, prev_time))
        redemptions = c.fetchall()
        
        links_to_insert = []
        
        # Process suffix sessions
        for i, session in enumerate(suffix_sessions):
            session_id = session['id']
            start_dt = self._dt(session['session_date'], session['start_time'])
            
            # For Active sessions, end_dt is not yet known
            if session['status'] == 'Active' or session['end_date'] is None:
                end_dt = None
            else:
                end_dt = self._dt(session['end_date'], session['end_time'])
            
            # For first suffix session, prev is checkpoint (if exists)
            if i == 0:
                current_prev_end_dt = prev_end_dt
            else:
                prev_session = suffix_sessions[i - 1]
                if prev_session['end_date']:
                    current_prev_end_dt = self._dt(prev_session['end_date'], prev_session['end_time'])
                else:
                    current_prev_end_dt = None
            
            # Next session (within suffix)
            next_start_dt = None
            if i < len(suffix_sessions) - 1:
                next_session = suffix_sessions[i + 1]
                next_start_dt = self._dt(next_session['session_date'], next_session['start_time'])
            
            # Link purchases
            for p in purchases:
                p_dt = self._dt(p['purchase_date'], p['purchase_time'])
                
                if end_dt and start_dt <= p_dt <= end_dt:
                    links_to_insert.append((session_id, 'purchase', p['id'], 'DURING'))
                elif current_prev_end_dt is None or (current_prev_end_dt < p_dt < start_dt):
                    if current_prev_end_dt is None and p_dt < start_dt:
                        links_to_insert.append((session_id, 'purchase', p['id'], 'BEFORE'))
                    elif current_prev_end_dt is not None and current_prev_end_dt < p_dt < start_dt:
                        links_to_insert.append((session_id, 'purchase', p['id'], 'BEFORE'))
            
            # Link redemptions (only for closed sessions)
            if end_dt:
                for r in redemptions:
                    r_dt = self._dt(r['redemption_date'], r['redemption_time'])
                
                if start_dt <= r_dt <= end_dt:
                    links_to_insert.append((session_id, 'redemption', r['id'], 'DURING'))
                elif next_start_dt is None or (end_dt < r_dt < next_start_dt):
                    if next_start_dt is None and r_dt > end_dt:
                        links_to_insert.append((session_id, 'redemption', r['id'], 'AFTER'))
                    elif next_start_dt is not None and end_dt < r_dt < next_start_dt:
                        links_to_insert.append((session_id, 'redemption', r['id'], 'AFTER'))
        
        # Insert all links
        if links_to_insert:
            c.executemany('''
                INSERT OR IGNORE INTO game_session_event_links 
                (game_session_id, event_type, event_id, relation)
                VALUES (?, ?, ?, ?)
            ''', links_to_insert)
        
        conn.commit()
        conn.close()
    
    def get_links_for_purchase(self, purchase_id):
        """
        Get all game sessions linked to a purchase.
        
        Returns:
            list of dicts with keys: game_session_id, relation, session_date, start_time, end_date, end_time
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT gsel.game_session_id, gsel.relation,
                   gs.session_date, gs.start_time, gs.end_date, gs.end_time,
                   gs.status, gs.game_type
            FROM game_session_event_links gsel
            JOIN game_sessions gs ON gs.id = gsel.game_session_id
            WHERE gsel.event_type = 'purchase' AND gsel.event_id = ?
            ORDER BY gs.end_date ASC, COALESCE(gs.end_time, '00:00:00') ASC, gs.id ASC
        ''', (purchase_id,))
        
        results = c.fetchall()
        conn.close()
        return results
    
    def get_links_for_redemption(self, redemption_id):
        """
        Get all game sessions linked to a redemption.
        
        Returns:
            list of dicts with keys: game_session_id, relation, session_date, start_time, end_date, end_time
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT gsel.game_session_id, gsel.relation,
                   gs.session_date, gs.start_time, gs.end_date, gs.end_time,
                   gs.status, gs.game_type
            FROM game_session_event_links gsel
            JOIN game_sessions gs ON gs.id = gsel.game_session_id
            WHERE gsel.event_type = 'redemption' AND gsel.event_id = ?
            ORDER BY gs.end_date ASC, COALESCE(gs.end_time, '00:00:00') ASC, gs.id ASC
        ''', (redemption_id,))
        
        results = c.fetchall()
        conn.close()
        return results
    
    def get_links_for_session(self, session_id):
        """
        Get all purchases and redemptions linked to a session.
        
        Returns:
            dict with keys 'purchases' and 'redemptions', each a list of dicts
        """
        conn = self.db.get_connection()
        c = conn.cursor()
        
        # Get linked purchases
        c.execute('''
            SELECT gsel.relation, p.id, p.purchase_date, p.purchase_time,
                   p.amount, p.sc_received
            FROM game_session_event_links gsel
            JOIN purchases p ON p.id = gsel.event_id
            WHERE gsel.game_session_id = ? AND gsel.event_type = 'purchase'
            ORDER BY p.purchase_date ASC, COALESCE(p.purchase_time, '00:00:00') ASC, p.id ASC
        ''', (session_id,))
        purchases = c.fetchall()
        
        # Get linked redemptions
        c.execute('''
            SELECT gsel.relation, r.id, r.redemption_date, r.redemption_time, r.amount
            FROM game_session_event_links gsel
            JOIN redemptions r ON r.id = gsel.event_id
            WHERE gsel.game_session_id = ? AND gsel.event_type = 'redemption'
            ORDER BY r.redemption_date ASC, COALESCE(r.redemption_time, '00:00:00') ASC, r.id ASC
        ''', (session_id,))
        redemptions = c.fetchall()
        
        conn.close()
        
        return {
            'purchases': purchases,
            'redemptions': redemptions
        }


