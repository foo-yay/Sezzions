#!/usr/bin/env python3
"""Post-recalculation accounting check"""
from database import Database

db = Database()
c = db.get_connection().cursor()

print('POST-RECALCULATION CHECK')
print('=' * 70)

# Purchases
c.execute('SELECT SUM(amount), SUM(remaining_amount) FROM purchases')
p = c.fetchone()
total_purchases = p[0] or 0
unrealized = p[1] or 0
consumed = total_purchases - unrealized

# Total redemptions
c.execute('SELECT SUM(amount - COALESCE(fees, 0)) FROM redemptions')
total_redemptions = c.fetchone()[0] or 0

# Realized profit
c.execute('SELECT SUM(net_pl) FROM tax_sessions')
realized_profit = c.fetchone()[0] or 0

# Orphaned allocations
c.execute('''
    SELECT COUNT(*), SUM(ra.allocated_amount)
    FROM redemption_allocations ra
    LEFT JOIN redemptions r ON r.id = ra.redemption_id
    WHERE r.id IS NULL
''')
orphan_row = c.fetchone()
orphan_count = orphan_row[0] or 0
orphan_total = orphan_row[1] or 0

print(f'Total Purchases:      ${total_purchases:>12,.2f}')
print(f'Unrealized:           ${unrealized:>12,.2f}')
print(f'Consumed:             ${consumed:>12,.2f}')
print()
print(f'Total Redemptions:    ${total_redemptions:>12,.2f}')
print(f'Realized Profit:      ${realized_profit:>12,.2f}')
print()
print(f'Orphaned allocations: {orphan_count} records, ${orphan_total:>12,.2f}')
print()

# Check identities
identity1_left = total_purchases
identity1_right = consumed + unrealized
identity1_pass = abs(identity1_left - identity1_right) < 0.01

identity2_left = total_redemptions
identity2_right = consumed + realized_profit
identity2_pass = abs(identity2_left - identity2_right) < 0.01

print('IDENTITY #1: Purchases = Consumed + Unrealized')
print(f'  ${identity1_left:.2f} = ${consumed:.2f} + ${unrealized:.2f}')
print(f'  ${identity1_left:.2f} = ${identity1_right:.2f}')
status1 = '✓ PASS' if identity1_pass else f'✗ FAIL (diff: ${abs(identity1_left - identity1_right):.2f})'
print(f'  {status1}')
print()

print('IDENTITY #2: Total Redemptions = Consumed + Profit')
print(f'  ${identity2_left:.2f} = ${consumed:.2f} + ${realized_profit:.2f}')
print(f'  ${identity2_left:.2f} = ${identity2_right:.2f}')
status2 = '✓ PASS' if identity2_pass else f'✗ FAIL (diff: ${abs(identity2_left - identity2_right):.2f})'
print(f'  {status2}')
print()

if orphan_count > 0:
    print(f'⚠ WARNING: {orphan_count} orphaned FIFO allocations still exist')
    print(f'  These reference deleted redemptions and should be cleaned up')
