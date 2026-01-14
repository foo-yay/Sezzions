#!/usr/bin/env python3
"""Clean up orphaned daily_tax_sessions"""
from database import Database

db = Database()
conn = db.get_connection()
c = conn.cursor()

print('ORPHANED DAILY_TAX_SESSIONS CLEANUP')
print('=' * 70)

# Find daily sessions with no matching game sessions
c.execute('''
    SELECT dts.id, dts.session_date, dts.user_id, dts.total_session_pnl,
           (SELECT COUNT(*) FROM game_sessions gs 
            WHERE gs.session_date = dts.session_date 
            AND gs.user_id = dts.user_id) as game_count
    FROM daily_tax_sessions dts
''')

orphans = []
for row in c.fetchall():
    if row['game_count'] == 0:
        orphans.append({
            'id': row['id'],
            'date': row['session_date'],
            'user': row['user_id'],
            'pl': row['total_session_pnl']
        })

if not orphans:
    print('✓ No orphaned daily sessions found!')
    exit(0)

print(f'Found {len(orphans)} orphaned daily_tax_sessions:')
print()
print(f'{"ID":<6} | {"Date":<12} | {"User":<4} | {"P/L":<12}')
print('-' * 45)

total_orphan_pl = 0
for o in orphans:
    print(f'{o["id"]:<6} | {o["date"]:<12} | {o["user"]:<4} | ${o["pl"]:>10,.2f}')
    total_orphan_pl += o["pl"]

print('-' * 45)
print(f'Total orphaned P/L: ${total_orphan_pl:,.2f}')
print()

# Confirm deletion
response = input('Delete these orphaned daily sessions? (yes/no): ').strip().lower()

if response == 'yes':
    ids_to_delete = [o['id'] for o in orphans]
    placeholders = ','.join('?' * len(ids_to_delete))
    c.execute(f'DELETE FROM daily_tax_sessions WHERE id IN ({placeholders})', ids_to_delete)
    deleted = c.rowcount
    conn.commit()
    print()
    print(f'✓ Successfully deleted {deleted} orphaned daily sessions')
    print(f'✓ Cleanup complete!')
    
    # Verify totals match now
    c.execute('SELECT SUM(net_taxable_pl) FROM game_sessions')
    game_total = c.fetchone()[0] or 0
    
    c.execute('SELECT SUM(total_session_pnl) FROM daily_tax_sessions')
    daily_total = c.fetchone()[0] or 0
    
    print()
    print('Verification:')
    print(f'  game_sessions total:       ${game_total:,.2f}')
    print(f'  daily_tax_sessions total:  ${daily_total:,.2f}')
    print(f'  Difference:                ${abs(game_total - daily_total):,.2f}')
    
    if abs(game_total - daily_total) < 0.01:
        print('  ✓ Totals now match!')
else:
    print()
    print('Cleanup cancelled. No changes made.')
    
conn.close()
