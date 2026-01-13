#!/usr/bin/env python3
"""Test script to check if session event links are working"""

from database import Database
from business_logic import FIFOCalculator, SessionManager

db = Database()
fifo = FIFOCalculator(db)
session_mgr = SessionManager(db, fifo)

# Get sessions that have redemption links
conn = db.get_connection()
c = conn.cursor()
c.execute("""
    SELECT DISTINCT gs.id, gs.session_date, gs.start_time 
    FROM game_sessions gs
    JOIN game_session_event_links gsel ON gs.id = gsel.game_session_id
    WHERE gsel.event_type = 'redemption'
    ORDER BY gs.id DESC 
    LIMIT 5
""")
sessions = c.fetchall()
conn.close()

print("Testing session event links (sessions with redemptions)...")
print("=" * 60)

for session in sessions:
    session_id = session['id']
    print(f"\nSession ID: {session_id} ({session['session_date']} {session['start_time']})")
    
    links = session_mgr.get_links_for_session(session_id)
    
    purchases = links.get('purchases', [])
    redemptions = links.get('redemptions', [])
    
    print(f"  Purchases: {len(purchases)}")
    for p in purchases:
        print(f"    - ID {p['id']}: {p['purchase_date']} {p['purchase_time']} - ${p['amount']:.2f} - {p['relation']}")
    
    print(f"  Redemptions: {len(redemptions)}")
    for r in redemptions:
        print(f"    - ID {r['id']}: {r['redemption_date']} {r['redemption_time']} - ${r['amount']:.2f} - {r['relation']}")

print("\n" + "=" * 60)
