#!/usr/bin/env python3
from database import Database
from datetime import datetime

db = Database()
conn = db.get_connection()
c = conn.cursor()

# Get Stake site ID
c.execute("SELECT id, name FROM sites WHERE name LIKE '%Stake%'")
stake = c.fetchone()
if not stake:
    print("No Stake site found")
    exit()
    
stake_id = stake['id']
print(f"Stake Site ID: {stake_id} ({stake['name']})")

# Get total session P/L for Stake
c.execute('SELECT SUM(net_taxable_pl) FROM game_sessions WHERE site_id = ?', (stake_id,))
total_pl = c.fetchone()[0] or 0

# Get unique days played for Stake
c.execute('SELECT COUNT(DISTINCT session_date) FROM game_sessions WHERE site_id = ?', (stake_id,))
unique_days = c.fetchone()[0] or 0

# Get session count
c.execute('SELECT COUNT(*) FROM game_sessions WHERE site_id = ?', (stake_id,))
session_count = c.fetchone()[0]

# Get total hours played for Stake
c.execute('''
    SELECT SUM(
        CASE 
            WHEN end_date IS NOT NULL AND end_time IS NOT NULL 
            THEN (JULIANDAY(end_date || ' ' || end_time) - JULIANDAY(session_date || ' ' || start_time)) * 24
            ELSE 0
        END
    ) as total_hours
    FROM game_sessions
    WHERE site_id = ?
''', (stake_id,))
total_hours = c.fetchone()[0] or 0

# Get date range for Stake
c.execute('SELECT MIN(session_date), MAX(session_date) FROM game_sessions WHERE site_id = ?', (stake_id,))
min_date, max_date = c.fetchone()

print(f'\nTotal Session P/L (Stake): ${total_pl:,.2f}')
print(f'Total Sessions (Stake): {session_count}')
print(f'Unique Days Played (Stake): {unique_days}')
print(f'Total Hours Played (Stake): {total_hours:.2f}')
print(f'Date Range (Stake): {min_date} to {max_date}')

if unique_days > 0:
    daily_pl = total_pl / unique_days
    print(f'\nDaily P/L: ${daily_pl:,.2f}')

if total_hours > 0:
    hourly_pl = total_pl / total_hours
    print(f'Hourly P/L: ${hourly_pl:,.2f}')

if min_date and max_date:
    start = datetime.strptime(min_date, '%Y-%m-%d')
    end = datetime.strptime(max_date, '%Y-%m-%d')
    days_in_range = (end - start).days + 1
    play_frequency = unique_days / days_in_range
    annual_pl = daily_pl * play_frequency * 365
    print(f'\nDays in Range: {days_in_range}')
    print(f'Play Frequency: {play_frequency:.2%}')
    print(f'Annual P/L (weighted): ${annual_pl:,.2f}')
    print(f'Annual P/L (unweighted - daily * 365): ${daily_pl * 365:,.2f}')

# Check a few sample sessions to see if there are any outliers
print('\n--- Sample Stake Sessions (Top 10 P/L) ---')
c.execute('''
    SELECT session_date, start_time, end_date, end_time, net_taxable_pl,
           CASE 
               WHEN end_date IS NOT NULL AND end_time IS NOT NULL 
               THEN (JULIANDAY(end_date || ' ' || end_time) - JULIANDAY(session_date || ' ' || start_time)) * 24
               ELSE 0
           END as hours
    FROM game_sessions 
    WHERE site_id = ?
    ORDER BY net_taxable_pl DESC
    LIMIT 10
''', (stake_id,))
for row in c.fetchall():
    print(f"{row['session_date']} {row['start_time']} to {row['end_date']} {row['end_time']}: {row['hours']:.2f}h, P/L ${row['net_taxable_pl']:.2f}")

print('\n--- Sample Stake Sessions (Longest Duration) ---')
c.execute('''
    SELECT session_date, start_time, end_date, end_time, net_taxable_pl,
           CASE 
               WHEN end_date IS NOT NULL AND end_time IS NOT NULL 
               THEN (JULIANDAY(end_date || ' ' || end_time) - JULIANDAY(session_date || ' ' || start_time)) * 24
               ELSE 0
           END as hours
    FROM game_sessions 
    WHERE site_id = ?
    ORDER BY hours DESC
    LIMIT 10
''', (stake_id,))
for row in c.fetchall():
    print(f"{row['session_date']} {row['start_time']} to {row['end_date']} {row['end_time']}: {row['hours']:.2f}h, P/L ${row['net_taxable_pl']:.2f}")

conn.close()
