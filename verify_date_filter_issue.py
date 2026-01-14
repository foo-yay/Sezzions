#!/usr/bin/env python3
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

# Get Moonspin site ID
c.execute("SELECT id FROM sites WHERE name LIKE '%Moonspin%'")
site_id = c.fetchone()['id']

print("Checking if 2026 redemptions are pulling in 2025 session P/L...")
print("=" * 80)

# Check Redeemed P/L for 2026 (redemption_date filter)
c.execute("""
    SELECT 
        ts.session_date,
        ts.net_pl,
        r.redemption_date,
        r.id as redemption_id
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN '2026-01-01' AND '2026-12-31'
    ORDER BY ts.session_date
""", (site_id,))

tax_sessions = c.fetchall()

pl_2025 = 0
pl_2026 = 0

print("\n2026 Redemptions - Tax Sessions Breakdown:")
print(f"{'Session Date':<15} {'Session Year':<12} {'P/L':<12} {'Redemption Date'}")
print("-" * 80)

for row in tax_sessions:
    year = row['session_date'][:4]
    if year == '2025':
        pl_2025 += row['net_pl']
    else:
        pl_2026 += row['net_pl']
    print(f"{row['session_date']:<15} {year:<12} ${row['net_pl']:>10.2f} {row['redemption_date']}")

print("=" * 80)
print(f"\nRedeemed P/L from 2025 sessions: ${pl_2025:,.2f}")
print(f"Redeemed P/L from 2026 sessions: ${pl_2026:,.2f}")
print(f"Total Redeemed P/L (2026 redemptions): ${pl_2025 + pl_2026:,.2f}")

# Check Session P/L for 2026 (session_date filter)
c.execute("""
    SELECT SUM(net_taxable_pl) as total
    FROM game_sessions
    WHERE site_id = ?
      AND session_date BETWEEN '2026-01-01' AND '2026-12-31'
""", (site_id,))
session_pl_2026 = c.fetchone()['total'] or 0

print(f"\nSession P/L (2026 sessions only): ${session_pl_2026:,.2f}")
print(f"\nDISCREPANCY: ${(pl_2025 + pl_2026) - session_pl_2026:,.2f}")

# Now check with expanded date range (2025-2026)
c.execute("""
    SELECT SUM(net_taxable_pl) as total
    FROM game_sessions
    WHERE site_id = ?
      AND session_date BETWEEN '2025-01-01' AND '2026-12-31'
""", (site_id,))
session_pl_all = c.fetchone()['total'] or 0

c.execute("""
    SELECT SUM(ts.net_pl) as total
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN '2025-01-01' AND '2026-12-31'
""", (site_id,))
redeemed_pl_all = c.fetchone()['total'] or 0

print(f"\n{'=' * 80}")
print(f"With expanded date range (2025-2026):")
print(f"  Session P/L: ${session_pl_all:,.2f}")
print(f"  Redeemed P/L: ${redeemed_pl_all:,.2f}")
print(f"  Difference: ${redeemed_pl_all - session_pl_all:,.2f}")

conn.close()
