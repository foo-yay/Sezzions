#!/usr/bin/env python3
from database import Database
db = Database()
c = db.get_connection().cursor()

print('P/L Comparison:')
print('=' * 70)

# game_sessions
c.execute('SELECT COUNT(*), SUM(net_taxable_pl) FROM game_sessions')
row = c.fetchone()
game_sessions_count = row[0]
game_sessions_total = row[1] or 0

print(f'game_sessions:')
print(f'  {game_sessions_count} sessions')
print(f'  Total P/L: ${game_sessions_total:,.2f}')
print()

# daily_tax_sessions
c.execute('SELECT COUNT(*), SUM(net_taxable_pl) FROM daily_tax_sessions')
row = c.fetchone()
daily_count = row[0]
daily_total = row[1] or 0

print(f'daily_tax_sessions:')
print(f'  {daily_count} daily aggregates')
print(f'  Total P/L: ${daily_total:,.2f}')
print()

diff = game_sessions_total - daily_total
print(f'Difference: ${diff:,.2f}')

if abs(diff) > 0.01:
    print()
    print('❌ These should match - daily sessions should aggregate game sessions')
else:
    print()
    print('✅ Match!')
