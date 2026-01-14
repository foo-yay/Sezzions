#!/usr/bin/env python3
"""Clean up orphaned FIFO allocations"""
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

print('ORPHANED FIFO ALLOCATION CLEANUP')
print('=' * 70)

# Find orphaned allocations
c.execute('''
    SELECT ra.id, ra.redemption_id, ra.purchase_id, ra.allocated_amount
    FROM redemption_allocations ra
    LEFT JOIN redemptions r ON r.id = ra.redemption_id
    WHERE r.id IS NULL
    ORDER BY ra.id
''')
orphans = c.fetchall()

if not orphans:
    print('✓ No orphaned allocations found. Database is clean!')
    exit(0)

print(f'Found {len(orphans)} orphaned allocations:')
print()
print('Alloc ID | Redemption ID | Purchase ID | Amount')
print('-' * 60)
total = 0
for row in orphans:
    alloc_id = row['id']
    red_id = row['redemption_id']
    purch_id = row['purchase_id']
    amount = row['allocated_amount']
    total += amount
    print(f'{alloc_id:8d} | {red_id:13d} | {purch_id:11d} | ${amount:>10,.2f}')

print('-' * 60)
print(f'Total: ${total:,.2f}')
print()

# Confirm deletion
response = input('Delete these orphaned allocations? (yes/no): ').strip().lower()

if response == 'yes':
    c.execute('''
        DELETE FROM redemption_allocations
        WHERE id IN (
            SELECT ra.id
            FROM redemption_allocations ra
            LEFT JOIN redemptions r ON r.id = ra.redemption_id
            WHERE r.id IS NULL
        )
    ''')
    deleted = c.rowcount
    conn.commit()
    print()
    print(f'✓ Successfully deleted {deleted} orphaned allocations')
    print(f'✓ Database cleanup complete!')
else:
    print()
    print('Cleanup cancelled. No changes made.')
    
conn.close()
