#!/usr/bin/env python3
"""Pre-migration verification - capture baseline metrics"""
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

print("=" * 80)
print("PRE-MIGRATION VERIFICATION - tax_sessions")
print("=" * 80)

# Count records
c.execute("SELECT COUNT(*) as total FROM tax_sessions")
total_records = c.fetchone()['total']
print(f"\n1. Total records: {total_records}")

# Sum of net_pl
c.execute("SELECT SUM(net_pl) as total_pl FROM tax_sessions")
total_pl = c.fetchone()['total_pl'] or 0
print(f"2. Total net_pl: ${total_pl:,.2f}")

# Check for NULL session_dates
c.execute("SELECT COUNT(*) as nulls FROM tax_sessions WHERE session_date IS NULL")
null_dates = c.fetchone()['nulls']
print(f"3. NULL session_dates: {null_dates}")

# Verify all redemption_ids exist
c.execute("""
    SELECT COUNT(*) as orphans 
    FROM tax_sessions ts
    LEFT JOIN redemptions r ON r.id = ts.redemption_id
    WHERE r.id IS NULL
""")
orphans = c.fetchone()['orphans']
print(f"4. Orphaned redemption_ids: {orphans}")

# First 5 records
print(f"\n5. First 5 records:")
c.execute("SELECT * FROM tax_sessions ORDER BY id LIMIT 5")
for row in c.fetchall():
    print(f"   ID {row['id']}: {row['session_date']}, redemption={row['redemption_id']}, pl=${row['net_pl']:.2f}")

print("\n" + "=" * 80)
print("BASELINE CAPTURED - Save these numbers!")
print("=" * 80)

conn.close()
