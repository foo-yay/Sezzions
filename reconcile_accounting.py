#!/usr/bin/env python3
"""Deep dive accounting reconciliation"""
from database import Database

db = Database()
c = db.get_connection().cursor()

print("=" * 70)
print("ACCOUNTING RECONCILIATION")
print("=" * 70)

# 1. Total purchases
c.execute("SELECT SUM(amount) as total, SUM(remaining_amount) as remaining FROM purchases")
p = c.fetchone()
total_purchases = p['total'] or 0
total_unrealized = p['remaining'] or 0
consumed_basis = total_purchases - total_unrealized

print(f"\n1. PURCHASES (Cost Basis)")
print(f"   Total Purchases:      ${total_purchases:>12,.2f}")
print(f"   Unrealized (active):  ${total_unrealized:>12,.2f}")
print(f"   Consumed Basis:       ${consumed_basis:>12,.2f}")

# 2. Check consumed basis via FIFO allocations
c.execute("SELECT SUM(allocated_amount) FROM redemption_allocations")
fifo_allocated = c.fetchone()[0] or 0
print(f"\n2. FIFO ALLOCATIONS")
print(f"   Via redemption_allocations: ${fifo_allocated:>12,.2f}")
print(f"   Difference from consumed:   ${consumed_basis - fifo_allocated:>12,.2f}")

# 3. Redemptions breakdown
c.execute("SELECT SUM(amount - COALESCE(fees, 0)) FROM redemptions WHERE is_free_sc = 0")
paid_redemptions = c.fetchone()[0] or 0
c.execute("SELECT SUM(amount - COALESCE(fees, 0)) FROM redemptions WHERE is_free_sc = 1")
free_redemptions = c.fetchone()[0] or 0

print(f"\n3. REDEMPTIONS (Cash Out)")
print(f"   Paid SC redemptions:  ${paid_redemptions:>12,.2f}")
print(f"   Free SC redemptions:  ${free_redemptions:>12,.2f}")
print(f"   Total Redemptions:    ${paid_redemptions + free_redemptions:>12,.2f}")

# 4. Session P/L
c.execute("SELECT SUM(net_taxable_pl) FROM game_sessions")
session_pl = c.fetchone()[0] or 0

print(f"\n4. GAMEPLAY P/L")
print(f"   Total Session P/L:    ${session_pl:>12,.2f}")

# 5. Check the identity
print(f"\n5. IDENTITY CHECK (excluding free SC)")
print(f"   Consumed + P/L =           ${consumed_basis + session_pl:>12,.2f}")
print(f"   Paid Redemptions =         ${paid_redemptions:>12,.2f}")
print(f"   Difference:                ${(consumed_basis + session_pl) - paid_redemptions:>12,.2f}")

# 6. Check for dormant or other status purchases
c.execute("SELECT status, COUNT(*), SUM(amount), SUM(remaining_amount) FROM purchases GROUP BY status")
print(f"\n6. PURCHASES BY STATUS")
for row in c.fetchall():
    status = row[0] or 'NULL'
    count = row[1]
    amount = row[2] or 0
    remaining = row[3] or 0
    print(f"   {status:10s}: {count:3d} purchases, amount=${amount:>10,.2f}, remaining=${remaining:>10,.2f}")

# 7. Check tax_sessions vs game_sessions
c.execute("SELECT SUM(net_pl) FROM tax_sessions")
tax_pl = c.fetchone()[0] or 0
print(f"\n7. TAX vs GAME P/L")
print(f"   tax_sessions.net_pl:       ${tax_pl:>12,.2f}")
print(f"   game_sessions.net_taxable_pl: ${session_pl:>12,.2f}")
print(f"   Difference:                ${session_pl - tax_pl:>12,.2f}")

# 8. Check if dormant balance is the issue
c.execute("SELECT amount, remaining_amount FROM purchases WHERE status = 'dormant'")
dormant = c.fetchall()
if dormant:
    print(f"\n8. DORMANT PURCHASES")
    for row in dormant:
        print(f"   Amount: ${row[0]:.2f}, Remaining: ${row[1]:.2f}")

# 9. Summary
print(f"\n" + "=" * 70)
print("SUMMARY:")
print("=" * 70)
print(f"The identity should be:")
print(f"  Consumed Basis + P/L = Paid Redemptions")
print(f"  ${consumed_basis:.2f} + ${session_pl:.2f} = ${consumed_basis + session_pl:.2f}")
print(f"  Actual Paid Redemptions: ${paid_redemptions:.2f}")
print(f"  Discrepancy: ${abs((consumed_basis + session_pl) - paid_redemptions):.2f}")
print()
print(f"Possible causes:")
print(f"  1. FIFO allocations out of sync (consumed vs allocated: ${abs(consumed_basis - fifo_allocated):.2f})")
print(f"  2. Dormant balance with non-zero remaining_amount")
print(f"  3. Game sessions not fully reconciled with purchases/redemptions")
print(f"  4. Free SC treated inconsistently")
