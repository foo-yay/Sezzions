#!/usr/bin/env python3
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

# Get Moonspin site ID
c.execute("SELECT id FROM sites WHERE name LIKE '%Moonspin%'")
site_id = c.fetchone()['id']

print("Moonspin Session Analysis")
print("=" * 80)

# Get ALL 2025 and 2026 sessions
c.execute("""
    SELECT id, session_date, net_taxable_pl, status
    FROM game_sessions
    WHERE site_id = ?
      AND session_date >= '2025-01-01'
    ORDER BY session_date
""", (site_id,))

all_sessions = c.fetchall()

# Get all tax_sessions linked to 2026 redemptions
c.execute("""
    SELECT DISTINCT ts.session_date
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN '2026-01-01' AND '2026-12-31'
""", (site_id,))

taxed_dates = set(row['session_date'] for row in c.fetchall())

print("\nAll Sessions (2025-2026):")
print(f"{'Date':<15} {'ID':<8} {'P/L':<12} {'Status':<10} {'Taxed?'}")
print("-" * 80)

total_2025 = 0
total_2026 = 0
taxed_2025 = 0
taxed_2026 = 0
untaxed_2025 = 0
untaxed_2026 = 0

for row in all_sessions:
    year = row['session_date'][:4]
    is_taxed = row['session_date'] in taxed_dates
    taxed_str = "YES" if is_taxed else "NO"
    
    print(f"{row['session_date']:<15} {row['id']:<8} ${row['net_taxable_pl']:>10.2f} {row['status']:<10} {taxed_str}")
    
    if year == '2025':
        total_2025 += row['net_taxable_pl']
        if is_taxed:
            taxed_2025 += row['net_taxable_pl']
        else:
            untaxed_2025 += row['net_taxable_pl']
    else:
        total_2026 += row['net_taxable_pl']
        if is_taxed:
            taxed_2026 += row['net_taxable_pl']
        else:
            untaxed_2026 += row['net_taxable_pl']

print("=" * 80)
print(f"\n2025 Sessions:")
print(f"  Total P/L: ${total_2025:,.2f}")
print(f"  Taxed (linked to redemptions): ${taxed_2025:,.2f}")
print(f"  Untaxed (not linked): ${untaxed_2025:,.2f}")

print(f"\n2026 Sessions:")
print(f"  Total P/L: ${total_2026:,.2f}")
print(f"  Taxed (linked to redemptions): ${taxed_2026:,.2f}")
print(f"  Untaxed (not linked): ${untaxed_2026:,.2f}")

# Now show what tax_sessions were actually created
print(f"\n{'=' * 80}")
print("\nTax Sessions from 2026 Redemptions:")
c.execute("""
    SELECT ts.id, ts.session_date, ts.net_pl, r.redemption_date, r.id as redemption_id
    FROM tax_sessions ts
    JOIN redemptions r ON ts.redemption_id = r.id
    WHERE r.site_id = ?
      AND r.redemption_date BETWEEN '2026-01-01' AND '2026-12-31'
    ORDER BY ts.session_date
""", (site_id,))

tax_sessions = c.fetchall()
for row in tax_sessions:
    print(f"  {row['session_date']}: ${row['net_pl']:.2f} (Redemption {row['redemption_id']} on {row['redemption_date']})")

conn.close()
