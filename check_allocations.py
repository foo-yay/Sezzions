#!/usr/bin/env python3
"""Check FIFO allocations per redemption"""
from database import Database

db = Database()
c = db.get_connection().cursor()

# Group allocations by redemption
c.execute('''
    SELECT r.id, r.redemption_date, r.amount - COALESCE(r.fees, 0) as net_redemption, 
           SUM(ra.allocated_amount) as total_allocated,
           COUNT(ra.id) as num_allocations
    FROM redemptions r
    LEFT JOIN redemption_allocations ra ON ra.redemption_id = r.id
    WHERE r.is_free_sc = 0
    GROUP BY r.id
    ORDER BY r.redemption_date
''')

print('Redemption ID | Date       | Net Redeemed | Allocated | # Allocs | Difference')
print('-' * 85)
total_allocated = 0
total_redeemed = 0
for row in c.fetchall():
    rid = row['id']
    date = row['redemption_date']
    net_red = row['net_redemption'] or 0
    alloc = row['total_allocated'] or 0
    n_alloc = row['num_allocations']
    diff = net_red - alloc
    total_allocated += alloc
    total_redeemed += net_red
    marker = ' <-- OVER' if alloc > net_red else ''
    print(f'{rid:13d} | {date} | ${net_red:>11,.2f} | ${alloc:>10,.2f} | {n_alloc:>8d} | ${diff:>10,.2f}{marker}')

print('-' * 85)
over_alloc = total_allocated - total_redeemed
print(f'TOTALS:        |            | ${total_redeemed:>11,.2f} | ${total_allocated:>10,.2f} |          | ${total_redeemed - total_allocated:>10,.2f}')
print()
print(f'Over-allocation: ${over_alloc:,.2f}')
print()

if abs(over_alloc) > 0.01:
    print("The FIFO allocation system has over-allocated purchases to redemptions.")
    print("This means redemptions are consuming MORE cost basis than actually exists.")
    print()
    print("Recommended fix: Run 'Recalculate Everything' from Tools tab to rebuild FIFO allocations.")
