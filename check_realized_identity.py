#!/usr/bin/env python3
"""Check accounting identity using Realized profit"""
from database import Database

db = Database()
c = db.get_connection().cursor()

print('CORRECTED ACCOUNTING IDENTITY')
print('=' * 70)

# 1. Purchases
c.execute('SELECT SUM(amount), SUM(remaining_amount) FROM purchases')
p = c.fetchone()
total_purchases = p[0] or 0
unrealized = p[1] or 0
consumed_basis = total_purchases - unrealized

print(f'Total Purchases:      ${total_purchases:>12,.2f}')
print(f'Unrealized (active):  ${unrealized:>12,.2f}')
print(f'Consumed Basis:       ${consumed_basis:>12,.2f}')
print()

# 2. Redemptions (paid only - those with allocations)
c.execute('''
    SELECT r.id, r.amount - COALESCE(r.fees, 0) as net
    FROM redemptions r
    WHERE EXISTS (SELECT 1 FROM redemption_allocations ra WHERE ra.redemption_id = r.id)
''')
paid_redemptions = sum(row['net'] or 0 for row in c.fetchall())

print(f'Paid Redemptions:     ${paid_redemptions:>12,.2f}')

# 3. Realized Profit from tax_sessions
c.execute('SELECT SUM(net_pl) FROM tax_sessions')
realized_profit = c.fetchone()[0] or 0

print(f'Realized Profit:      ${realized_profit:>12,.2f}')
print()

# Check the identity: Consumed = Paid - Profit
calculated_consumed = paid_redemptions - realized_profit
diff1 = consumed_basis - calculated_consumed

print(f'Identity Check #1: Consumed = Paid Redemptions - Profit')
print(f'  Consumed Basis (actual):     ${consumed_basis:>12,.2f}')
print(f'  Paid Red - Profit (calc):    ${calculated_consumed:>12,.2f}')
print(f'  Difference:                  ${diff1:>12,.2f}')
print()

# Alternative: Purchases = (Red - Profit) + Unrealized
calculated_purchases = (paid_redemptions - realized_profit) + unrealized
diff2 = total_purchases - calculated_purchases

print(f'Identity Check #2: Purchases = (Red - Profit) + Unrealized')
print(f'  Purchases (actual):          ${total_purchases:>12,.2f}')
print(f'  (Red-Profit) + Unrealized:   ${calculated_purchases:>12,.2f}')
print(f'  Difference:                  ${diff2:>12,.2f}')
print()

if abs(diff2) < 0.01:
    print('✓ ACCOUNTING IDENTITY VERIFIED!')
else:
    print(f'✗ Discrepancy of ${abs(diff2):,.2f} found')
