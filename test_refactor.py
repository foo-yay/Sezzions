#!/usr/bin/env python3
"""Test key workflows after tax_sessions → realized_transactions refactor"""
import sqlite3
from database import Database
from business_logic import FIFOCalculator, SessionManager

db_path = "casino_accounting.db"

print("\nTESTING KEY WORKFLOWS")
print("=" * 60)

# Test 1: Database initialization and migration
print("\n1. Testing database initialization...")
try:
    db = Database(db_path)
    conn = db.get_connection()
    c = conn.cursor()
    
    # Check schema version
    c.execute("SELECT MAX(version) as version FROM schema_version")
    version = c.fetchone()['version']
    print(f"   ✅ Schema version: {version}")
    
    # Check realized_transactions table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realized_transactions'")
    if c.fetchone():
        print(f"   ✅ realized_transactions table exists")
    else:
        print(f"   ❌ realized_transactions table NOT found!")
        
    # Check tax_sessions does NOT exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tax_sessions'")
    if not c.fetchone():
        print(f"   ✅ tax_sessions table removed")
    else:
        print(f"   ❌ tax_sessions table still exists!")
        
    conn.close()
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: FIFO Calculator can access realized_transactions
print("\n2. Testing FIFO Calculator...")
try:
    fifo = FIFOCalculator(db)
    conn = db.get_connection()
    c = conn.cursor()
    
    # Get a redemption to test
    c.execute("""
        SELECT id, site_id, user_id, amount, redemption_date 
        FROM redemptions 
        WHERE id IN (SELECT redemption_id FROM realized_transactions LIMIT 1)
    """)
    redemption = c.fetchone()
    
    if redemption:
        r_id = redemption['id']
        # Check if we can read realized_transactions
        c.execute("SELECT * FROM realized_transactions WHERE redemption_id = ?", (r_id,))
        rt_row = c.fetchone()
        
        if rt_row:
            print(f"   ✅ Can read realized_transactions for redemption {r_id}")
            print(f"      Date: {rt_row['redemption_date']}, P/L: ${rt_row['net_pl']:.2f}")
        else:
            print(f"   ❌ No realized_transactions record for redemption {r_id}")
    else:
        print(f"   ⚠️  No redemptions to test")
        
    conn.close()
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Session Manager can rebuild
print("\n3. Testing Session Manager rebuild...")
try:
    sm = SessionManager(db, fifo)
    
    # Get a site/user pair
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT site_id, user_id FROM realized_transactions LIMIT 1")
    pair = c.fetchone()
    conn.close()
    
    if pair:
        site_id = pair['site_id']
        user_id = pair['user_id']
        
        # Try rebuilding
        sm.rebuild_all_derived(site_id, user_id)
        print(f"   ✅ Rebuilt derived data for site {site_id}, user {user_id}")
        
        # Verify realized_transactions still has data
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM realized_transactions WHERE site_id = ? AND user_id = ?", 
                  (site_id, user_id))
        count = c.fetchone()['cnt']
        conn.close()
        
        if count > 0:
            print(f"   ✅ realized_transactions has {count} records after rebuild")
        else:
            print(f"   ❌ realized_transactions empty after rebuild!")
    else:
        print(f"   ⚠️  No realized_transactions to test")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 4: Query all realized_transactions
print("\n4. Testing realized_transactions queries...")
try:
    conn = db.get_connection()
    c = conn.cursor()
    
    # Count total records
    c.execute("SELECT COUNT(*) as cnt, SUM(net_pl) as total_pl FROM realized_transactions")
    stats = c.fetchone()
    print(f"   ✅ Total records: {stats['cnt']}, Total P/L: ${stats['total_pl']:.2f}")
    
    # Test date filtering with redemption_date
    c.execute("""
        SELECT COUNT(*) as cnt, SUM(net_pl) as total_pl 
        FROM realized_transactions 
        WHERE redemption_date >= '2026-01-01'
    """)
    stats_2026 = c.fetchone()
    print(f"   ✅ 2026 records: {stats_2026['cnt']}, 2026 P/L: ${stats_2026['total_pl']:.2f}")
    
    # Test JOIN with redemptions
    c.execute("""
        SELECT COUNT(*) as cnt 
        FROM realized_transactions rt
        JOIN redemptions r ON rt.redemption_id = r.id
    """)
    join_count = c.fetchone()['cnt']
    print(f"   ✅ JOINed with redemptions: {join_count} records")
    
    conn.close()
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 5: Verify no session_date references remain
print("\n5. Testing for old column names...")
try:
    conn = db.get_connection()
    c = conn.cursor()
    
    # Check realized_transactions schema
    c.execute("PRAGMA table_info(realized_transactions)")
    columns = [row['name'] for row in c.fetchall()]
    
    if 'session_date' in columns:
        print(f"   ❌ Old column 'session_date' still exists!")
    else:
        print(f"   ✅ No 'session_date' column found")
        
    if 'redemption_date' in columns:
        print(f"   ✅ New column 'redemption_date' exists")
    else:
        print(f"   ❌ New column 'redemption_date' NOT found!")
        
    conn.close()
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("WORKFLOW TESTING COMPLETE")
print("=" * 60)
