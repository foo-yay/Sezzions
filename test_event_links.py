"""
Test game_session_event_links rebuild functionality
"""

import os
from database import Database
from business_logic import SessionManager, FIFOCalculator

TEST_DB = 'test_event_links.db'

def setup_test_db():
    """Create test database with sessions, purchases, and redemptions"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    db = Database(TEST_DB)
    conn = db.get_connection()
    c = conn.cursor()
    
    # Create test user, site, card
    c.execute("INSERT INTO users (name, active) VALUES ('TestUser', 1)")
    user_id = c.lastrowid
    
    c.execute("INSERT INTO sites (name, active) VALUES ('TestSite', 1)")
    site_id = c.lastrowid
    
    c.execute("INSERT INTO cards (name, user_id, cashback_rate, active) VALUES ('TestCard', ?, 0, 1)", (user_id,))
    card_id = c.lastrowid
    
    # Use existing or create game type
    c.execute("SELECT name FROM game_types LIMIT 1")
    game_type_row = c.fetchone()
    if game_type_row:
        game_type = game_type_row['name']
    else:
        c.execute("INSERT INTO game_types (name) VALUES ('TestSlots')")
        game_type = 'TestSlots'
    
    # Create 3 closed sessions
    # Session 1: Jan 10, 10:00 - 11:00
    c.execute("""
        INSERT INTO game_sessions 
        (site_id, user_id, game_type, session_date, start_time, end_date, end_time,
         starting_sc_balance, ending_sc_balance, wager_amount, status)
        VALUES (?, ?, ?, '2026-01-10', '10:00:00', '2026-01-10', '11:00:00',
                100.0, 90.0, 50.0, 'Closed')
    """, (site_id, user_id, game_type))
    session1_id = c.lastrowid
    
    # Session 2: Jan 10, 14:00 - 15:00
    c.execute("""
        INSERT INTO game_sessions 
        (site_id, user_id, game_type, session_date, start_time, end_date, end_time,
         starting_sc_balance, ending_sc_balance, wager_amount, status)
        VALUES (?, ?, ?, '2026-01-10', '14:00:00', '2026-01-10', '15:00:00',
                90.0, 80.0, 40.0, 'Closed')
    """, (site_id, user_id, game_type))
    session2_id = c.lastrowid
    
    # Session 3: Jan 11, 10:00 - 11:00
    c.execute("""
        INSERT INTO game_sessions 
        (site_id, user_id, game_type, session_date, start_time, end_date, end_time,
         starting_sc_balance, ending_sc_balance, wager_amount, status)
        VALUES (?, ?, ?, '2026-01-11', '10:00:00', '2026-01-11', '11:00:00',
                80.0, 70.0, 30.0, 'Closed')
    """, (site_id, user_id, game_type))
    session3_id = c.lastrowid
    
    # Create purchases
    # Purchase 1: Jan 10, 09:00 (BEFORE session 1)
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received,
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-10', '09:00:00', 100.0, 100.0, 0.0, 0.0, 100.0)
    """, (user_id, site_id, card_id))
    
    # Purchase 2: Jan 10, 10:30 (DURING session 1)
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received,
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-10', '10:30:00', 50.0, 50.0, 0.0, 0.0, 50.0)
    """, (user_id, site_id, card_id))
    
    # Purchase 3: Jan 10, 12:00 (BEFORE session 2, gap between sessions)
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received,
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-10', '12:00:00', 25.0, 25.0, 0.0, 0.0, 25.0)
    """, (user_id, site_id, card_id))
    
    # Create redemptions
    # Redemption 1: Jan 10, 11:00 (exactly at session 1 end - should be DURING)
    c.execute("""
        INSERT INTO redemptions 
        (site_id, user_id, redemption_date, redemption_time, amount, more_remaining)
        VALUES (?, ?, '2026-01-10', '11:00:00', 90.0, 1)
    """, (site_id, user_id))
    
    # Redemption 2: Jan 10, 15:30 (AFTER session 2)
    c.execute("""
        INSERT INTO redemptions 
        (site_id, user_id, redemption_date, redemption_time, amount, more_remaining)
        VALUES (?, ?, '2026-01-10', '15:30:00', 80.0, 1)
    """, (site_id, user_id))
    
    # Redemption 3: Jan 11, 10:30 (DURING session 3)
    c.execute("""
        INSERT INTO redemptions 
        (site_id, user_id, redemption_date, redemption_time, amount, more_remaining)
        VALUES (?, ?, '2026-01-11', '10:30:00', 70.0, 0)
    """, (site_id, user_id))
    
    conn.commit()
    conn.close()
    
    return db, site_id, user_id, session1_id, session2_id, session3_id


def test_full_link_rebuild():
    """Test full rebuild of game_session_event_links"""
    print("\n=== Test: Full Link Rebuild ===")
    
    db, site_id, user_id, session1_id, session2_id, session3_id = setup_test_db()
    
    sm = SessionManager(db, FIFOCalculator(db))
    
    # Run full rebuild
    sm.rebuild_game_session_event_links_for_pair(site_id, user_id)
    
    # Verify links
    conn = db.get_connection()
    c = conn.cursor()
    
    # Check Session 1 links
    c.execute('''
        SELECT event_type, event_id, relation
        FROM game_session_event_links
        WHERE game_session_id = ?
        ORDER BY event_type, event_id
    ''', (session1_id,))
    session1_links = c.fetchall()
    
    print(f"\nSession 1 (Jan 10, 10:00-11:00) links:")
    for link in session1_links:
        print(f"  {link['event_type']} #{link['event_id']} - {link['relation']}")
    
    # Verify expected links for Session 1
    # - Purchase #1 (09:00) should be BEFORE
    # - Purchase #2 (10:30) should be DURING
    # - Redemption #1 (11:00) should be DURING (inclusive boundary)
    
    purchase_links = [l for l in session1_links if l['event_type'] == 'purchase']
    redemption_links = [l for l in session1_links if l['event_type'] == 'redemption']
    
    assert len(purchase_links) == 2, f"Expected 2 purchase links for session 1, got {len(purchase_links)}"
    assert len(redemption_links) == 1, f"Expected 1 redemption link for session 1, got {len(redemption_links)}"
    
    # Check relations
    before_purchases = [l for l in purchase_links if l['relation'] == 'BEFORE']
    during_purchases = [l for l in purchase_links if l['relation'] == 'DURING']
    
    assert len(before_purchases) == 1, f"Expected 1 BEFORE purchase, got {len(before_purchases)}"
    assert len(during_purchases) == 1, f"Expected 1 DURING purchase, got {len(during_purchases)}"
    assert redemption_links[0]['relation'] == 'DURING', "Redemption at session end should be DURING"
    
    print("\n✓ Session 1 links verified")
    
    # Check Session 2 links
    c.execute('''
        SELECT event_type, event_id, relation
        FROM game_session_event_links
        WHERE game_session_id = ?
        ORDER BY event_type, event_id
    ''', (session2_id,))
    session2_links = c.fetchall()
    
    print(f"\nSession 2 (Jan 10, 14:00-15:00) links:")
    for link in session2_links:
        print(f"  {link['event_type']} #{link['event_id']} - {link['relation']}")
    
    # Verify Session 2
    # - Purchase #3 (12:00) should be BEFORE (gap between sessions)
    # - Redemption #2 (15:30) should be AFTER
    
    purchase_links_s2 = [l for l in session2_links if l['event_type'] == 'purchase']
    redemption_links_s2 = [l for l in session2_links if l['event_type'] == 'redemption']
    
    assert len(purchase_links_s2) == 1, f"Expected 1 purchase link for session 2, got {len(purchase_links_s2)}"
    assert purchase_links_s2[0]['relation'] == 'BEFORE', "Gap purchase should be BEFORE"
    
    assert len(redemption_links_s2) == 1, f"Expected 1 redemption link for session 2, got {len(redemption_links_s2)}"
    assert redemption_links_s2[0]['relation'] == 'AFTER', "Post-session redemption should be AFTER"
    
    print("✓ Session 2 links verified")
    
    conn.close()
    print("\n✓ PASS: Full link rebuild works correctly\n")


def test_helper_query_methods():
    """Test get_links_for_* helper methods"""
    print("\n=== Test: Helper Query Methods ===")
    
    db, site_id, user_id, session1_id, session2_id, session3_id = setup_test_db()
    
    sm = SessionManager(db, FIFOCalculator(db))
    sm.rebuild_game_session_event_links_for_pair(site_id, user_id)
    
    # Get links for purchase #1
    purchase_links = sm.get_links_for_purchase(1)
    print(f"\nPurchase #1 linked to {len(purchase_links)} session(s):")
    for link in purchase_links:
        print(f"  Session #{link['game_session_id']} - {link['relation']}")
    
    assert len(purchase_links) > 0, "Purchase #1 should be linked to at least one session"
    
    # Get links for redemption #2
    redemption_links = sm.get_links_for_redemption(2)
    print(f"\nRedemption #2 linked to {len(redemption_links)} session(s):")
    for link in redemption_links:
        print(f"  Session #{link['game_session_id']} - {link['relation']}")
    
    assert len(redemption_links) > 0, "Redemption #2 should be linked to at least one session"
    
    # Get links for session #1
    session_links = sm.get_links_for_session(session1_id)
    print(f"\nSession #1 has {len(session_links['purchases'])} purchase(s) and {len(session_links['redemptions'])} redemption(s)")
    
    assert len(session_links['purchases']) > 0, "Session #1 should have linked purchases"
    assert len(session_links['redemptions']) > 0, "Session #1 should have linked redemptions"
    
    print("\n✓ PASS: Helper query methods work correctly\n")


def cleanup():
    """Remove test database"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("Test database cleaned up.\n")


if __name__ == "__main__":
    try:
        test_full_link_rebuild()
        test_helper_query_methods()
        
        print("=" * 60)
        print("ALL EVENT LINK TESTS PASSED ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        raise
    finally:
        cleanup()
