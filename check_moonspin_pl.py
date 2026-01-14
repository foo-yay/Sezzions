#!/usr/bin/env python3
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

# Get Moonspin site ID
c.execute("SELECT id, name FROM sites WHERE name LIKE '%Moonspin%'")
site = c.fetchone()
if not site:
    print("No Moonspin site found")
    exit()

site_id = site['id']
print(f"Moonspin Site ID: {site_id} ({site['name']})")
print("=" * 80)

# Check 2026 date range
year_start = '2026-01-01'
year_end = '2026-12-31'

# 1. Check unrealized basis
c.execute("""
    SELECT SUM(remaining_amount) as unrealized
    FROM purchases
    WHERE site_id = ? AND status = 'active'
      AND purchase_date BETWEEN ? AND ?
""", (site_id, year_start, year_end))
unrealized = c.fetchone()['unrealized'] or 0
print(f"\n1. Unrealized Basis (2026 purchases): ${unrealized:,.2f}")

# 2. Check Redeemed P/L (from tax_sessions via redemptions)
c.execute("""
    SELECT SUM(ts.net_pl) as redeemed_pl
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ? 
      AND r.redemption_date BETWEEN ? AND ?
""", (site_id, year_start, year_end))
redeemed_pl = c.fetchone()['redeemed_pl'] or 0
print(f"\n2. Redeemed P/L (via tax_sessions): ${redeemed_pl:,.2f}")

# 3. Check Session P/L (from game_sessions)
c.execute("""
    SELECT SUM(net_taxable_pl) as session_pl
    FROM game_sessions
    WHERE site_id = ?
      AND session_date BETWEEN ? AND ?
""", (site_id, year_start, year_end))
session_pl = c.fetchone()['session_pl'] or 0
print(f"\n3. Session P/L (from game_sessions): ${session_pl:,.2f}")

print(f"\n{'=' * 80}")
print(f"DISCREPANCY: ${redeemed_pl - session_pl:,.2f}")
print(f"{'=' * 80}")

# 4. Check for tax_sessions without corresponding game_sessions
print("\n4. Checking for orphaned tax_sessions...")
c.execute("""
    SELECT ts.id, ts.session_date, ts.net_pl, r.id as redemption_id, r.redemption_date
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    LEFT JOIN game_sessions gs ON gs.session_date = ts.session_date 
                                AND gs.site_id = r.site_id 
                                AND gs.user_id = r.user_id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN ? AND ?
      AND gs.id IS NULL
""", (site_id, year_start, year_end))

orphaned_tax = c.fetchall()
if orphaned_tax:
    print(f"Found {len(orphaned_tax)} tax_sessions without matching game_sessions:")
    total_orphaned = 0
    for row in orphaned_tax:
        print(f"  Tax Session {row['id']}: {row['session_date']}, P/L ${row['net_pl']:.2f}, Redemption {row['redemption_id']} on {row['redemption_date']}")
        total_orphaned += row['net_pl']
    print(f"  Total orphaned P/L: ${total_orphaned:,.2f}")
else:
    print("No orphaned tax_sessions found")

# 5. Check for game_sessions without tax_sessions
print("\n5. Checking for game_sessions without tax_sessions...")
c.execute("""
    SELECT gs.id, gs.session_date, gs.net_taxable_pl, gs.status
    FROM game_sessions gs
    WHERE gs.site_id = ?
      AND gs.session_date BETWEEN ? AND ?
      AND NOT EXISTS (
          SELECT 1 FROM tax_sessions ts
          WHERE ts.session_date = gs.session_date
            AND ts.redemption_id IN (
                SELECT id FROM redemptions 
                WHERE site_id = gs.site_id AND user_id = gs.user_id
            )
      )
""", (site_id, year_start, year_end))

sessions_without_tax = c.fetchall()
if sessions_without_tax:
    print(f"Found {len(sessions_without_tax)} game_sessions without tax_sessions:")
    total_untaxed = 0
    for row in sessions_without_tax:
        print(f"  Session {row['id']}: {row['session_date']}, P/L ${row['net_taxable_pl']:.2f}, Status: {row['status']}")
        total_untaxed += row['net_taxable_pl']
    print(f"  Total untaxed P/L: ${total_untaxed:,.2f}")
else:
    print("No game_sessions without tax_sessions found")

# 6. Show all tax_sessions for Moonspin in 2026
print("\n6. All tax_sessions for Moonspin in 2026:")
c.execute("""
    SELECT ts.id, ts.session_date, ts.net_pl, ts.redemption_id, r.redemption_date, r.amount
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN ? AND ?
    ORDER BY ts.session_date
""", (site_id, year_start, year_end))

tax_sessions = c.fetchall()
print(f"Total: {len(tax_sessions)} tax sessions")
for row in tax_sessions:
    print(f"  {row['session_date']}: ${row['net_pl']:.2f} (Redemption {row['redemption_id']} on {row['redemption_date']}, amount ${row['amount']:.2f})")

conn.close()
