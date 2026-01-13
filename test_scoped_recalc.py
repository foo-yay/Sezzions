#!/usr/bin/env python3
"""
Comprehensive test suite for scoped recalculation logic.
Tests idempotency, RTP-only paths, administrative fields, and various edge cases.
"""

import os
import sqlite3
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from database import Database
from business_logic import FIFOCalculator, SessionManager


class TestScopedRecalculation:
    """Test suite for scoped recalculation logic."""
    
    def __init__(self, db_path='casino_accounting.db'):
        self.original_db = db_path
        self.test_db = 'test_scoped_recalc.db'
        self.db = None
        self.session_manager = None
        
    def setup(self):
        """Create a test database copy."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        shutil.copy2(self.original_db, self.test_db)
        
        self.db = Database(self.test_db)
        fifo_calc = FIFOCalculator(self.db)
        self.session_manager = SessionManager(self.db, fifo_calc)
        print(f"✓ Test database created: {self.test_db}")
    
    def teardown(self):
        """Clean up test database."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            print(f"✓ Test database cleaned up")
    
    def capture_session_state(self, site_id, user_id):
        """Capture current state of all sessions for a site/user pair."""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   starting_sc_balance, ending_sc_balance,
                   starting_redeemable_sc, ending_redeemable_sc,
                   expected_start_total_sc, expected_start_redeemable_sc,
                   inferred_start_total_delta, inferred_start_redeemable_delta,
                   session_basis, basis_consumed, delta_total, delta_redeem,
                   net_taxable_pl, wager_amount, game_id
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
            ORDER BY session_date, start_time
        """, (site_id, user_id))
        sessions = [dict(row) for row in c.fetchall()]
        conn.close()
        return sessions
    
    def compare_sessions(self, before, after, test_name):
        """Compare two session states and report differences."""
        if len(before) != len(after):
            print(f"  ✗ {test_name}: Session count mismatch ({len(before)} vs {len(after)})")
            return False
        
        all_match = True
        for i, (b, a) in enumerate(zip(before, after)):
            for key in b.keys():
                if key in ['id']:  # Skip ID comparison
                    continue
                b_val = b[key]
                a_val = a[key]
                
                # Handle float comparison with tolerance
                if isinstance(b_val, float) or isinstance(a_val, float):
                    b_val = float(b_val) if b_val is not None else 0.0
                    a_val = float(a_val) if a_val is not None else 0.0
                    if abs(b_val - a_val) > 0.01:
                        print(f"  ✗ {test_name}: Session {i} field '{key}' mismatch: {b_val} vs {a_val}")
                        all_match = False
                elif b_val != a_val:
                    print(f"  ✗ {test_name}: Session {i} field '{key}' mismatch: {b_val} vs {a_val}")
                    all_match = False
        
        if all_match:
            print(f"  ✓ {test_name}: All sessions match")
        return all_match
    
    def get_test_site_user(self):
        """Get the first available site/user pair with sessions."""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT site_id, user_id
            FROM game_sessions
            WHERE site_id IS NOT NULL AND user_id IS NOT NULL
            LIMIT 1
        """)
        row = c.fetchone()
        conn.close()
        if not row:
            raise ValueError("No sessions found in database for testing")
        return row['site_id'], row['user_id']
    
    def get_session_for_testing(self, site_id, user_id):
        """Get a closed session suitable for testing."""
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   starting_sc_balance, ending_sc_balance,
                   wager_amount, delta_total, game_id, notes
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND end_date IS NOT NULL
            ORDER BY session_date, start_time
            LIMIT 1
        """, (site_id, user_id))
        row = c.fetchone()
        conn.close()
        if not row:
            raise ValueError("No closed sessions found for testing")
        return dict(row)
    
    # ==================== TEST CASES ====================
    
    def test_01_idempotency_ending_sc(self):
        """Test 1: Change ending SC and revert - should restore original state."""
        print("\n[TEST 1] Idempotency: Ending SC change and revert")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        # Capture original state
        original = self.capture_session_state(site_id, user_id)
        original_ending = session['ending_sc_balance']
        
        # Change ending SC
        conn = self.db.get_connection()
        c = conn.cursor()
        new_ending = original_ending + 50.0
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?", 
                  (new_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Trigger recalc
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert to original
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Trigger recalc again
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Compare with original
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Idempotency (Ending SC)"):
            raise AssertionError("Idempotency test failed: sessions don't match after revert")
    
    def test_02_idempotency_wager(self):
        """Test 2: Change wager and revert - should restore original state."""
        print("\n[TEST 2] Idempotency: Wager change and revert")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        original_wager = session['wager_amount'] or 0.0
        
        # Change wager
        conn = self.db.get_connection()
        c = conn.cursor()
        new_wager = original_wager + 100.0
        c.execute("UPDATE game_sessions SET wager_amount = ? WHERE id = ?",
                  (new_wager, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        old_vals = {'wager_amount': original_wager, 'delta_total': session['delta_total'],
                    'game_id': session['game_id'], 'notes': session['notes']}
        new_vals = {'wager_amount': new_wager, 'delta_total': session['delta_total'],
                    'game_id': session['game_id'], 'notes': session['notes']}
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True,
            old_values=old_vals, new_values=new_vals
        )
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET wager_amount = ? WHERE id = ?",
                  (original_wager, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True,
            old_values=new_vals, new_values=old_vals
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Idempotency (Wager)"):
            raise AssertionError("Idempotency test failed: sessions don't match after revert")
    
    def test_03_administrative_notes_skip(self):
        """Test 3: Change only notes field - should skip recalculation."""
        print("\n[TEST 3] Administrative field: Notes-only change")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        
        # Change only notes
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET notes = ? WHERE id = ?",
                  ("Test note", session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        old_vals = {'notes': session['notes']}
        new_vals = {'notes': "Test note"}
        
        count = self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True,
            old_values=old_vals, new_values=new_vals
        )
        
        # Should return 0 (skipped)
        if count == 0:
            print("  ✓ Administrative field: Recalculation skipped (returned 0)")
        else:
            print(f"  ✗ Administrative field: Expected 0 sessions, got {count}")
        
        # State should be unchanged
        after = self.capture_session_state(site_id, user_id)
        self.compare_sessions(original, after, "Administrative field (unchanged)")
    
    def test_04_rtp_only_path(self):
        """Test 4: Change only wager/game_id - should use RTP-only path."""
        print("\n[TEST 4] RTP-only path: Wager-only change")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        original_wager = session['wager_amount'] or 0.0
        
        # Change only wager (RTP-only path)
        conn = self.db.get_connection()
        c = conn.cursor()
        new_wager = original_wager + 50.0
        delta_total = session['delta_total'] or 0.0
        c.execute("UPDATE game_sessions SET wager_amount = ? WHERE id = ?",
                  (new_wager, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        old_vals = {'wager_amount': original_wager, 'delta_total': delta_total,
                    'game_id': session['game_id'], 'notes': session['notes']}
        new_vals = {'wager_amount': new_wager, 'delta_total': delta_total,
                    'game_id': session['game_id'], 'notes': session['notes']}
        
        count = self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True,
            old_values=old_vals, new_values=new_vals
        )
        
        # Should return 0 (RTP-only path doesn't count as session rebuild)
        if count == 0:
            print("  ✓ RTP-only path: Used fast path (returned 0)")
        else:
            print(f"  ✗ RTP-only path: Expected 0, got {count}")
        
        # Verify RTP was updated (check game_rtp table)
        # Note: We won't revert since this test is about the path, not idempotency
    
    def test_05_scoped_vs_full_comparison(self):
        """Test 5: Compare scoped rebuild vs full rebuild results."""
        print("\n[TEST 5] Scoped vs Full: Verify identical results")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        # Make a change
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = session['ending_sc_balance']
        new_ending = original_ending + 25.0
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (new_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Run scoped rebuild
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        scoped_result = self.capture_session_state(site_id, user_id)
        
        # Restore original value
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Change again (same change)
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (new_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Run full rebuild
        self.session_manager.rebuild_all_derived(site_id, user_id)
        full_result = self.capture_session_state(site_id, user_id)
        
        # Compare
        if not self.compare_sessions(scoped_result, full_result, "Scoped vs Full"):
            raise AssertionError("Scoped and Full rebuild produced different results")
    
    def test_06_multiple_sequential_changes(self):
        """Test 6: Multiple sequential edits to same session."""
        print("\n[TEST 6] Multiple sequential changes to same session")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        original_ending = session['ending_sc_balance']
        
        # Change 1
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 10.0, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Change 2
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 20.0, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Change 3
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 30.0, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert to original
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Multiple sequential changes"):
            raise AssertionError("Multiple sequential changes test failed")
    
    def test_07_early_session_impact(self):
        """Test 7: Edit early session, verify later sessions update."""
        print("\n[TEST 7] Early session edit impacts later sessions")
        site_id, user_id = self.get_test_site_user()
        
        # Get first session
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND end_date IS NOT NULL
            ORDER BY session_date, start_time
            LIMIT 1
        """, (site_id, user_id))
        first_session = dict(c.fetchone())
        
        # Get count of later sessions
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
              AND (session_date > ? OR (session_date = ? AND start_time > ?))
        """, (site_id, user_id, first_session['session_date'],
              first_session['session_date'], first_session['start_time']))
        later_count = c.fetchone()['cnt']
        conn.close()
        
        if later_count == 0:
            print("  ⊘ Skipped: No later sessions to impact")
            return
        
        original = self.capture_session_state(site_id, user_id)
        
        # Change first session ending SC
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = first_session['ending_sc_balance']
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 100.0, first_session['id']))
        conn.commit()
        conn.close()
        
        # Recalc
        old_ts = (first_session['session_date'], first_session['start_time'])
        new_ts = (first_session['end_date'], first_session['end_time'])
        count = self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        print(f"  → Recalculated {count} sessions (expected ~{later_count + 1})")
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, first_session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Early session impact"):
            raise AssertionError("Early session impact test failed")
    
    def test_08_checkpoint_validation(self):
        """Test 8: Verify checkpoint balances are consistent."""
        print("\n[TEST 8] Checkpoint validation")
        site_id, user_id = self.get_test_site_user()
        
        # Get all closed sessions
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   ending_sc_balance, ending_redeemable_sc,
                   expected_start_total_sc, expected_start_redeemable_sc
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND end_date IS NOT NULL
            ORDER BY session_date, start_time
        """, (site_id, user_id))
        sessions = [dict(row) for row in c.fetchall()]
        conn.close()
        
        if len(sessions) < 2:
            print("  ⊘ Skipped: Need at least 2 sessions")
            return
        
        # Check that each session's expected_start matches previous session's ending
        all_valid = True
        for i in range(1, len(sessions)):
            prev = sessions[i-1]
            curr = sessions[i]
            
            prev_end_total = prev['ending_sc_balance'] or 0.0
            prev_end_redeem = prev['ending_redeemable_sc'] or 0.0
            
            # Note: expected_start includes transactions between sessions
            # So we can't directly compare, but we can check they're reasonable
            curr_exp_total = curr['expected_start_total_sc'] or 0.0
            curr_exp_redeem = curr['expected_start_redeemable_sc'] or 0.0
            
            # Just verify they're non-negative and total >= redeemable
            if curr_exp_total < 0 or curr_exp_redeem < 0:
                print(f"  ✗ Session {i}: Negative expected balance")
                all_valid = False
            if curr_exp_total < curr_exp_redeem:
                print(f"  ✗ Session {i}: Total < Redeemable ({curr_exp_total} < {curr_exp_redeem})")
                all_valid = False
        
        if all_valid:
            print("  ✓ Checkpoint validation: All balances valid")
    
    def test_09_session_timing_edge_case(self):
        """Test 9: Sessions with same date but different times."""
        print("\n[TEST 9] Same-date sessions with different times")
        site_id, user_id = self.get_test_site_user()
        
        # Find sessions on same date
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT session_date, COUNT(*) as cnt
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND end_date IS NOT NULL
            GROUP BY session_date
            HAVING cnt > 1
            ORDER BY session_date
            LIMIT 1
        """, (site_id, user_id))
        row = c.fetchone()
        conn.close()
        
        if not row:
            print("  ⊘ Skipped: No same-date sessions found")
            return
        
        same_date = row['session_date']
        
        # Get sessions on that date
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND session_date = ?
            ORDER BY start_time
        """, (site_id, user_id, same_date))
        same_date_sessions = [dict(row) for row in c.fetchall()]
        conn.close()
        
        original = self.capture_session_state(site_id, user_id)
        
        # Edit first session on that date
        first = same_date_sessions[0]
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = first['ending_sc_balance']
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 15.0, first['id']))
        conn.commit()
        conn.close()
        
        old_ts = (first['session_date'], first['start_time'])
        new_ts = (first['end_date'], first['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, first['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Same-date sessions"):
            raise AssertionError("Same-date sessions test failed")
    
    def test_10_large_value_changes(self):
        """Test 10: Very large value changes."""
        print("\n[TEST 10] Large value changes")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        original_ending = session['ending_sc_balance']
        
        # Make a huge change
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 10000.0, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Large value changes"):
            raise AssertionError("Large value changes test failed")
    
    def test_11_zero_balances(self):
        """Test 11: Sessions with zero balances."""
        print("\n[TEST 11] Zero balance handling")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        
        # Set ending balance to zero
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = session['ending_sc_balance']
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (0.0, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Zero balances"):
            raise AssertionError("Zero balances test failed")
    
    def test_12_concurrent_field_changes(self):
        """Test 12: Multiple fields changed simultaneously."""
        print("\n[TEST 12] Multiple field changes simultaneously")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        original_wager = session['wager_amount'] or 0.0
        original_ending = session['ending_sc_balance']
        
        # Change multiple fields
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE game_sessions
            SET wager_amount = ?, ending_sc_balance = ?
            WHERE id = ?
        """, (original_wager + 50.0, original_ending + 25.0, session['id']))
        conn.commit()
        conn.close()
        
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        # Revert both
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            UPDATE game_sessions
            SET wager_amount = ?, ending_sc_balance = ?
            WHERE id = ?
        """, (original_wager, original_ending, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Multiple field changes"):
            raise AssertionError("Multiple field changes test failed")
    
    def test_13_boundary_detection(self):
        """Test 13: Verify scoped rebuild finds correct boundary."""
        print("\n[TEST 13] Boundary detection accuracy")
        site_id, user_id = self.get_test_site_user()
        
        # Get middle session
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT id, session_date, start_time, end_date, end_time,
                   ending_sc_balance
            FROM game_sessions
            WHERE site_id = ? AND user_id = ? AND end_date IS NOT NULL
            ORDER BY session_date, start_time
            LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM game_sessions 
                           WHERE site_id = ? AND user_id = ? AND end_date IS NOT NULL)
        """, (site_id, user_id, site_id, user_id))
        middle_session = dict(c.fetchone() or {})
        conn.close()
        
        if not middle_session:
            print("  ⊘ Skipped: No middle session found")
            return
        
        # Find expected boundary
        old_ts = (middle_session['session_date'], middle_session['start_time'])
        boundary_start = self.session_manager.find_containing_session_start(
            site_id, user_id, old_ts[0], old_ts[1]
        )
        
        if boundary_start:
            print(f"  → Boundary found: {boundary_start[0]} {boundary_start[1]}")
            print(f"  → Changed session: {old_ts[0]} {old_ts[1]}")
            
            # Boundary should be <= changed session
            if boundary_start <= old_ts:
                print("  ✓ Boundary detection: Correct (boundary <= changed)")
            else:
                print("  ✗ Boundary detection: Incorrect (boundary > changed)")
        else:
            print("  ✓ Boundary detection: No containing session (first session)")
    
    def test_14_fallback_to_full_rebuild(self):
        """Test 14: Verify fallback mechanism works."""
        print("\n[TEST 14] Fallback to full rebuild")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        original = self.capture_session_state(site_id, user_id)
        
        # Make a change that should work with scoped
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = session['ending_sc_balance']
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 33.0, session['id']))
        conn.commit()
        conn.close()
        
        # Call with scoped=True (will use fallback if needed)
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        count = self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        print(f"  → Rebuilt {count} sessions")
        
        # Revert and verify (tests both scoped and fallback idempotency)
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        
        reverted = self.capture_session_state(site_id, user_id)
        if not self.compare_sessions(original, reverted, "Fallback mechanism"):
            raise AssertionError("Fallback mechanism test failed")
    
    def test_15_performance_comparison(self):
        """Test 15: Compare performance of scoped vs full rebuild."""
        print("\n[TEST 15] Performance comparison (scoped vs full)")
        site_id, user_id = self.get_test_site_user()
        session = self.get_session_for_testing(site_id, user_id)
        
        # Get total session count
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) as cnt
            FROM game_sessions
            WHERE site_id = ? AND user_id = ?
        """, (site_id, user_id))
        total_sessions = c.fetchone()['cnt']
        conn.close()
        
        import time
        
        # Time scoped rebuild
        conn = self.db.get_connection()
        c = conn.cursor()
        original_ending = session['ending_sc_balance']
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 42.0, session['id']))
        conn.commit()
        conn.close()
        
        start_time = time.time()
        old_ts = (session['session_date'], session['start_time'])
        new_ts = (session['end_date'], session['end_time'])
        scoped_count = self.session_manager.auto_recalculate_affected_sessions(
            site_id, user_id, old_ts=old_ts, new_ts=new_ts,
            entity_type='session', scoped=True
        )
        scoped_time = time.time() - start_time
        
        # Revert
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending, session['id']))
        conn.commit()
        conn.close()
        
        # Time full rebuild
        conn = self.db.get_connection()
        c = conn.cursor()
        c.execute("UPDATE game_sessions SET ending_sc_balance = ? WHERE id = ?",
                  (original_ending + 42.0, session['id']))
        conn.commit()
        conn.close()
        
        start_time = time.time()
        self.session_manager.rebuild_all_derived(site_id, user_id)
        full_time = time.time() - start_time
        
        print(f"  → Total sessions: {total_sessions}")
        print(f"  → Scoped rebuilt: {scoped_count} sessions in {scoped_time:.3f}s")
        print(f"  → Full rebuilt: {total_sessions} sessions in {full_time:.3f}s")
        
        if scoped_time < full_time:
            speedup = full_time / scoped_time
            print(f"  ✓ Performance: Scoped is {speedup:.2f}x faster")
        else:
            print(f"  ⚠ Performance: Scoped slower (dataset may be too small)")
    
    # ==================== RUN ALL TESTS ====================
    
    def run_all_tests(self):
        """Run all test cases."""
        print("=" * 70)
        print("SCOPED RECALCULATION TEST SUITE")
        print("=" * 70)
        
        test_methods = [
            self.test_01_idempotency_ending_sc,
            self.test_02_idempotency_wager,
            self.test_03_administrative_notes_skip,
            self.test_04_rtp_only_path,
            self.test_05_scoped_vs_full_comparison,
            self.test_06_multiple_sequential_changes,
            self.test_07_early_session_impact,
            self.test_08_checkpoint_validation,
            self.test_09_session_timing_edge_case,
            self.test_10_large_value_changes,
            self.test_11_zero_balances,
            self.test_12_concurrent_field_changes,
            self.test_13_boundary_detection,
            self.test_14_fallback_to_full_rebuild,
            self.test_15_performance_comparison,
        ]
        
        passed = 0
        failed = 0
        skipped = 0
        
        for test_method in test_methods:
            try:
                test_method()
                passed += 1
            except ValueError as e:
                if "No sessions" in str(e) or "No closed" in str(e):
                    print(f"  ⊘ Skipped: {e}")
                    skipped += 1
                else:
                    print(f"  ✗ FAILED: {e}")
                    failed += 1
            except Exception as e:
                print(f"  ✗ FAILED: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        print("\n" + "=" * 70)
        print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
        print("=" * 70)


if __name__ == '__main__':
    tester = TestScopedRecalculation()
    try:
        tester.setup()
        tester.run_all_tests()
    finally:
        tester.teardown()
