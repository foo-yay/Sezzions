#!/usr/bin/env python3
"""
Quick test script to verify RTP calculation
"""
import sys
from database import Database
from business_logic import SessionManager, FIFOCalculator

# Initialize
db = Database("casino_accounting.db")
fifo = FIFOCalculator(db)
session_mgr = SessionManager(db, fifo)

# Get site_id and user_id for Legendz/fooyay
conn = db.get_connection()
c = conn.cursor()

c.execute("SELECT id FROM sites WHERE name = 'Legendz'")
site_id = c.fetchone()['id']

c.execute("SELECT id FROM users WHERE name = 'fooyay'")
user_id = c.fetchone()['id']

conn.close()

print(f"Testing RTP calculation for site_id={site_id}, user_id={user_id}")

# Before recalculation
print("\nBefore recalculation:")
conn = db.get_connection()
c = conn.cursor()
c.execute("""
    SELECT id, starting_sc_balance, ending_sc_balance, wager_amount, rtp
    FROM game_sessions
    WHERE id = 180
""")
row = c.fetchone()
print(f"Session 180:")
print(f"  Starting: {row['starting_sc_balance']} SC")
print(f"  Ending: {row['ending_sc_balance']} SC")
print(f"  Wager: {row['wager_amount']} SC")
print(f"  RTP: {row['rtp']}")
print(f"  Expected RTP: {((row['wager_amount'] + (row['ending_sc_balance'] - row['starting_sc_balance'])) / row['wager_amount']) * 100:.2f}%")
conn.close()

# Run recalculation
print(f"\nRunning recalculation for (site={site_id}, user={user_id})...")
result = session_mgr.rebuild_all_derived(site_id, user_id)
print(f"Recalculated {result['sessions_processed']} sessions")

# After recalculation
print("\nAfter recalculation:")
conn = db.get_connection()
c = conn.cursor()
c.execute("""
    SELECT id, starting_sc_balance, ending_sc_balance, wager_amount, rtp
    FROM game_sessions
    WHERE id = 180
""")
row = c.fetchone()
print(f"Session 180:")
print(f"  Starting: {row['starting_sc_balance']} SC")
print(f"  Ending: {row['ending_sc_balance']} SC")
print(f"  Wager: {row['wager_amount']} SC")
print(f"  RTP: {row['rtp']:.2f}%" if row['rtp'] is not None else "  RTP: None")
print(f"  Expected RTP: {((row['wager_amount'] + (row['ending_sc_balance'] - row['starting_sc_balance'])) / row['wager_amount']) * 100:.2f}%")

# Check a few more sessions
print("\nOther sessions with wager_amount:")
c.execute("""
    SELECT id, starting_sc_balance, ending_sc_balance, wager_amount, rtp
    FROM game_sessions
    WHERE wager_amount IS NOT NULL AND status='Closed'
    LIMIT 5
""")
for row in c.fetchall():
    sc_change = row['ending_sc_balance'] - row['starting_sc_balance']
    expected_rtp = ((row['wager_amount'] + sc_change) / row['wager_amount']) * 100
    actual_rtp = row['rtp']
    match = "✓" if actual_rtp and abs(actual_rtp - expected_rtp) < 0.01 else "✗"
    rtp_display = f"{actual_rtp:.2f}%" if actual_rtp is not None else "None"
    print(f"  Session {row['id']}: Wager={row['wager_amount']}, Change={sc_change:+.2f}, RTP={rtp_display}, Expected={expected_rtp:.2f}% {match}")

conn.close()

print("\n✓ Test complete!")
