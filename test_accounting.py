#!/usr/bin/env python3
"""Test accounting identity"""
from database import Database

db = Database()
c = db.get_connection().cursor()

# Get all the numbers
c.execute("SELECT COALESCE(SUM(amount), 0) FROM purchases")
purchases = c.fetchone()[0]

c.execute("SELECT COALESCE(SUM(remaining_amount), 0) FROM purchases WHERE status='active'")
unrealized = c.fetchone()[0]

c.execute("SELECT COALESCE(SUM(amount - COALESCE(fees, 0)), 0) FROM redemptions WHERE is_free_sc = 0")
realized_paid = c.fetchone()[0]

c.execute("SELECT COALESCE(SUM(amount - COALESCE(fees, 0)), 0) FROM redemptions WHERE is_free_sc = 1")
realized_free = c.fetchone()[0]

c.execute("SELECT COALESCE(SUM(net_taxable_pl), 0) FROM game_sessions")
pl = c.fetchone()[0]

consumed = purchases - unrealized

print("=" * 60)
print("ACCOUNTING IDENTITY CHECK")
print("=" * 60)
print(f"Total Purchases:        ${purchases:>12,.2f}")
print(f"Unrealized (basis):     ${unrealized:>12,.2f}")
print(f"Consumed (basis):       ${consumed:>12,.2f}")
print(f"Realized (paid):        ${realized_paid:>12,.2f}")
print(f"Realized (free SC):     ${realized_free:>12,.2f}")
print(f"Realized (total):       ${realized_paid + realized_free:>12,.2f}")
print(f"Session P/L:            ${pl:>12,.2f}")
print()
print("VERIFICATION (excluding free SC):")
print(f"  Unrealized + Realized (paid) = ${unrealized + realized_paid:>12,.2f}")
print(f"  Purchases + P/L              = ${purchases + pl:>12,.2f}")
diff = abs((unrealized + realized_paid) - (purchases + pl))
print(f"  Difference:                    ${diff:>12,.2f}")
print(f"  Match: {diff < 0.01}")
print()
print("EXPLANATION:")
print(f"  Free SC redemptions add ${realized_free:,.2f} that didn't come from purchases")
print(f"  So the full identity is:")
print(f"  Unrealized + Realized = Purchases + P/L + Free SC")
print(f"  ${unrealized + realized_paid + realized_free:,.2f} = ${purchases + pl + realized_free:,.2f}")
