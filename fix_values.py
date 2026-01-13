#!/usr/bin/env python3
"""Script to fix button styling and remove relation from data population"""

# Read the file
with open('qt_app.py', 'r') as f:
    lines = f.readlines()

# Track changes
changes_made = []

for i, line in enumerate(lines):
    # Fix Purchase Sessions table - remove relation from values list
    if i > 0 and 'values = [session_date, start_time, end_display, game_type, status, relation]' in line:
        if i > 50 and i < 1500:  # Purchase dialog range
            lines[i-1] = ''  # Remove the relation = ... line
            lines[i] = '            values = [session_date, start_time, end_display, game_type, status]\n'
            changes_made.append(f"Fixed Purchase sessions values at line {i+1}")
    
    # Fix Redemption Sessions table - remove relation from values list  
    if 'values = [session_date, start_time, end_display, game_type, status, relation]' in line:
        if i > 1500 and i < 2400:  # Redemption dialog range
            lines[i-1] = ''  # Remove the relation = ... line
            lines[i] = '            values = [session_date, start_time, end_display, game_type, status]\n'
            changes_made.append(f"Fixed Redemption sessions values at line {i+1}")
    
    # Fix GameSession Purchases table - remove relation from values list
    if 'values = [date_display, time_display, amount, sc_received, relation]' in line:
        if i > 4000:  # GameSession dialog range
            lines[i-1] = ''  # Remove the relation = ... line
            lines[i] = '            values = [date_display, time_display, amount, sc_received]\n'
            changes_made.append(f"Fixed GameSession purchases values at line {i+1}")
    
    # Fix GameSession Redemptions table - remove relation from values list
    if 'values = [date_display, time_display, amount, relation]' in line:
        if i > 4000:  # GameSession dialog range
            lines[i-1] = ''  # Remove the relation = ... line
            lines[i] = '            values = [date_display, time_display, amount]\n'
            changes_made.append(f"Fixed GameSession redemptions values at line {i+1}")

# Write back
with open('qt_app.py', 'w') as f:
    f.writelines(lines)

for change in changes_made:
    print(change)
print(f"\nTotal changes: {len(changes_made)}")
