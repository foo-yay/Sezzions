"""
Test FIFO timestamp fix - verify that redemptions cannot allocate from future purchases
"""

import os
import shutil
from database import Database
from business_logic import FIFOCalculator

# Use test database
TEST_DB = 'test_fifo_timestamp.db'

def setup_test_db():
    """Create fresh test database with test data"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    db = Database(TEST_DB)
    conn = db.get_connection()
    c = conn.cursor()
    
    # Insert test user and site
    c.execute("INSERT INTO users (name, active) VALUES ('TestUser', 1)")
    user_id = c.lastrowid
    
    c.execute("INSERT INTO sites (name, active) VALUES ('TestSite', 1)")
    site_id = c.lastrowid
    
    c.execute("INSERT INTO cards (name, user_id, cashback_rate, active) VALUES ('TestCard', ?, 0, 1)", (user_id,))
    card_id = c.lastrowid
    
    # Insert purchases with SPECIFIC times on same day
    # Purchase 1: 2026-01-13 08:00:00 - $100
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received, 
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-13', '08:00:00', 100.0, 100.0, 0.0, 0.0, 100.0)
    """, (user_id, site_id, card_id))
    
    # Purchase 2: 2026-01-13 14:00:00 - $50
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received, 
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-13', '14:00:00', 50.0, 50.0, 0.0, 0.0, 50.0)
    """, (user_id, site_id, card_id))
    
    conn.commit()
    conn.close()
    
    return db, site_id, user_id


def test_redemption_cannot_allocate_from_future_purchase():
    """Test that a 12:00 redemption cannot allocate from 14:00 purchase"""
    print("\n=== Test: Redemption at 12:00 cannot allocate from 14:00 purchase ===")
    
    db, site_id, user_id = setup_test_db()
    fifo = FIFOCalculator(db)
    
    # Redemption at 2026-01-13 12:00:00 for $120
    # Should ONLY allocate from 08:00 purchase ($100), NOT from 14:00 purchase ($50)
    cost_basis, allocations = fifo.calculate_cost_basis(
        site_id=site_id,
        redemption_amount=120.0,
        user_id=user_id,
        redemption_date='2026-01-13',
        redemption_time='12:00:00'
    )
    
    print(f"Redemption: $120 at 12:00:00")
    print(f"Available purchases:")
    print(f"  - $100 at 08:00:00 (should be allocated)")
    print(f"  - $50 at 14:00:00 (should NOT be allocated - future)")
    print(f"\nResult:")
    print(f"  Cost basis allocated: ${cost_basis:.2f}")
    print(f"  Number of allocations: {len(allocations)}")
    
    # Verify: cost_basis should be $100 (only from 08:00 purchase)
    assert cost_basis == 100.0, f"Expected $100 cost basis, got ${cost_basis:.2f}"
    
    # Verify: only 1 allocation (from 08:00 purchase)
    assert len(allocations) == 1, f"Expected 1 allocation, got {len(allocations)}"
    
    print(f"\n✓ PASS: Redemption correctly allocated only ${cost_basis:.2f} from 08:00 purchase")
    print(f"✓ PASS: Future purchase at 14:00 was correctly excluded\n")


def test_redemption_can_allocate_from_same_time():
    """Test that a redemption at 14:00 CAN allocate from purchase at 14:00 (inclusive)"""
    print("\n=== Test: Redemption at 14:00 CAN allocate from 14:00 purchase (inclusive) ===")
    
    db, site_id, user_id = setup_test_db()
    fifo = FIFOCalculator(db)
    
    # Redemption at 2026-01-13 14:00:00 for $120
    # Should allocate from BOTH purchases (08:00 $100 + 14:00 $50)
    cost_basis, allocations = fifo.calculate_cost_basis(
        site_id=site_id,
        redemption_amount=120.0,
        user_id=user_id,
        redemption_date='2026-01-13',
        redemption_time='14:00:00'
    )
    
    print(f"Redemption: $120 at 14:00:00")
    print(f"Available purchases:")
    print(f"  - $100 at 08:00:00 (should be allocated)")
    print(f"  - $50 at 14:00:00 (should be allocated - same time, inclusive)")
    print(f"\nResult:")
    print(f"  Cost basis allocated: ${cost_basis:.2f}")
    print(f"  Number of allocations: {len(allocations)}")
    
    # Verify: cost_basis should be $120 (full redemption amount from both)
    assert cost_basis == 120.0, f"Expected $120 cost basis, got ${cost_basis:.2f}"
    
    # Verify: 2 allocations
    assert len(allocations) == 2, f"Expected 2 allocations, got {len(allocations)}"
    
    print(f"\n✓ PASS: Redemption correctly allocated ${cost_basis:.2f} from both purchases")
    print(f"✓ PASS: Same-time purchase was correctly included (boundary inclusive)\n")


def test_null_purchase_time_treated_as_midnight():
    """Test that NULL purchase_time is treated as 00:00:00"""
    print("\n=== Test: NULL purchase_time treated as 00:00:00 ===")
    
    db, site_id, user_id = setup_test_db()
    conn = db.get_connection()
    c = conn.cursor()
    
    c.execute("SELECT id FROM cards LIMIT 1")
    card_id = c.fetchone()['id']
    
    # Add purchase with NULL time (should be treated as 00:00:00)
    c.execute("""
        INSERT INTO purchases 
        (user_id, site_id, card_id, purchase_date, purchase_time, amount, sc_received, 
         starting_sc_balance, cashback_earned, remaining_amount)
        VALUES (?, ?, ?, '2026-01-14', NULL, 75.0, 75.0, 0.0, 0.0, 75.0)
    """, (user_id, site_id, card_id))
    conn.commit()
    conn.close()
    
    fifo = FIFOCalculator(db)
    
    # Redemption at 2026-01-14 01:00:00
    # Should include the NULL-time purchase (treated as 00:00:00, which is < 01:00:00)
    cost_basis, allocations = fifo.calculate_cost_basis(
        site_id=site_id,
        redemption_amount=75.0,
        user_id=user_id,
        redemption_date='2026-01-14',
        redemption_time='01:00:00'
    )
    
    print(f"Redemption: $75 at 2026-01-14 01:00:00")
    print(f"Purchase: $75 at 2026-01-14 (NULL time, treated as 00:00:00)")
    print(f"\nResult:")
    print(f"  Cost basis allocated: ${cost_basis:.2f}")
    
    # Should have allocated the NULL-time purchase
    assert cost_basis == 75.0, f"Expected $75 cost basis, got ${cost_basis:.2f}"
    
    print(f"\n✓ PASS: NULL purchase_time correctly treated as 00:00:00")
    print(f"✓ PASS: Purchase was included in FIFO allocation\n")


def cleanup():
    """Remove test database"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    print("Test database cleaned up.\n")


if __name__ == "__main__":
    try:
        test_redemption_cannot_allocate_from_future_purchase()
        test_redemption_can_allocate_from_same_time()
        test_null_purchase_time_treated_as_midnight()
        
        print("=" * 60)
        print("ALL FIFO TIMESTAMP TESTS PASSED ✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        raise
    finally:
        cleanup()
