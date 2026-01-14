#!/usr/bin/env python3
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

# Get Moonspin site ID
c.execute("SELECT id FROM sites WHERE name LIKE '%Moonspin%'")
site_id = c.fetchone()['id']

print("Checking Moonspin tax_sessions for 2026 redemptions...")
print("=" * 80)

# Get all tax_sessions from 2026 redemptions
c.execute("""
    SELECT ts.id, ts.session_date, ts.net_pl, r.redemption_date, r.amount
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN '2026-01-01' AND '2026-12-31'
    ORDER BY r.redemption_date, ts.session_date
""", (site_id,))

tax_sessions = c.fetchall()

sessions_in_2025 = 0
pl_from_2025 = 0
sessions_in_2026 = 0
pl_from_2026 = 0

print(f"\n2026 Redemptions creating tax_sessions:")
print(f"{'Redemption Date':<20} {'Session Date':<15} {'P/L':<12} {'Year'}")
print("-" * 80)

for row in tax_sessions:
    session_year = row['session_date'][:4]
    pl = row['net_pl']
    
    print(f"{row['redemption_date']:<20} {row['session_date']:<15} ${pl:>10.2f} {session_year}")
    
    if session_year == '2025':
        sessions_in_2025 += 1
        pl_from_2025 += pl
    elif session_year == '2026':
        sessions_in_2026 += 1
        pl_from_2026 += pl

print("=" * 80)
print(f"\nSummary:")
print(f"  Tax sessions from 2025 sessions: {sessions_in_2025} sessions, ${pl_from_2025:,.2f} P/L")
print(f"  Tax sessions from 2026 sessions: {sessions_in_2026} sessions, ${pl_from_2026:,.2f} P/L")
print(f"  Total Redeemed P/L (2026 redemptions): ${pl_from_2025 + pl_from_2026:,.2f}")

# Compare to actual 2026 session P/L
c.execute("""
    SELECT SUM(net_taxable_pl) as total
    FROM game_sessions
    WHERE site_id = ?
      AND session_date BETWEEN '2026-01-01' AND '2026-12-31'
""", (site_id,))
session_pl_2026 = c.fetchone()['total'] or 0

print(f"\n  Actual 2026 Session P/L: ${session_pl_2026:,.2f}")
print(f"\n  Expected if all 2026 sessions redeemed: ${session_pl_2026:,.2f}")
print(f"  Actually redeemed from 2026 sessions: ${pl_from_2026:,.2f}")
print(f"  Difference (unredeemed): ${session_pl_2026 - pl_from_2026:,.2f}")

conn.close()
