#!/usr/bin/env python3
"""Find discrepancy between game_sessions and daily_tax_sessions"""
from database import Database

db = Database()
c = db.get_connection().cursor()

print('INVESTIGATING P/L DISCREPANCY')
print('=' * 70)

# Get totals
c.execute('SELECT SUM(net_taxable_pl) FROM game_sessions')
game_total = c.fetchone()[0] or 0

c.execute('SELECT SUM(total_session_pnl) FROM daily_tax_sessions')
daily_total = c.fetchone()[0] or 0

print(f'game_sessions total:       ${game_total:,.2f}')
print(f'daily_tax_sessions total:  ${daily_total:,.2f}')
print(f'Difference:                ${daily_total - game_total:,.2f}')
print()

# Check 1: Sum game_sessions by date and compare to daily_tax_sessions
print('=' * 70)
print('Comparing by Date:')
print('=' * 70)
print(f'{"Date":<12} | {"User":<4} | {"Game Total":<12} | {"Daily Total":<12} | {"Diff":<10}')
print('-' * 70)

c.execute('''
    SELECT 
        gs.session_date,
        gs.user_id,
        SUM(gs.net_taxable_pl) as game_total
    FROM game_sessions gs
    GROUP BY gs.session_date, gs.user_id
    ORDER BY gs.session_date, gs.user_id
''')

game_by_date = {(row['session_date'], row['user_id']): row['game_total'] for row in c.fetchall()}

c.execute('''
    SELECT session_date, user_id, total_session_pnl
    FROM daily_tax_sessions
    ORDER BY session_date, user_id
''')

daily_by_date = {}
for row in c.fetchall():
    key = (row['session_date'], row['user_id'])
    daily_by_date[key] = row['total_session_pnl']

# Find all unique date+user combinations
all_keys = set(game_by_date.keys()) | set(daily_by_date.keys())

mismatches = []
for date, user in sorted(all_keys):
    game_val = game_by_date.get((date, user), 0)
    daily_val = daily_by_date.get((date, user), 0)
    diff = daily_val - game_val
    
    if abs(diff) > 0.01:
        mismatches.append((date, user, game_val, daily_val, diff))
        print(f'{date:<12} | {user:<4} | ${game_val:>10,.2f} | ${daily_val:>10,.2f} | ${diff:>8,.2f}')

if not mismatches:
    print('All dates match!')
else:
    print('-' * 70)
    print(f'Total mismatches: {len(mismatches)}')
    print(f'Sum of differences: ${sum(m[4] for m in mismatches):,.2f}')
    print()
    
    # Check if daily sessions have other_income
    print('=' * 70)
    print('Checking for Other Income in daily_tax_sessions:')
    print('=' * 70)
    c.execute('SELECT COUNT(*), SUM(total_other_income) FROM daily_tax_sessions WHERE total_other_income > 0')
    row = c.fetchone()
    other_count = row[0]
    other_total = row[1] or 0
    
    if other_count > 0:
        print(f'{other_count} daily sessions have other_income totaling ${other_total:,.2f}')
        print()
        c.execute('SELECT session_date, user_id, total_other_income, total_session_pnl FROM daily_tax_sessions WHERE total_other_income > 0')
        print(f'{"Date":<12} | {"User":<4} | {"Other Income":<12} | {"Session P/L":<12}')
        print('-' * 60)
        for row in c.fetchall():
            print(f'{row[0]:<12} | {row[1]:<4} | ${row[2]:>10,.2f} | ${row[3]:>10,.2f}')
    else:
        print('No other_income found in daily_tax_sessions')
