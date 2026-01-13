#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to fix undefined csv_duplicates references"""

with open('qt_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 17687 (index 17686) - remove the csv_duplicates check
# Looking for: "        if csv_duplicates:"
fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Remove the csv_duplicates block (lines 17686-17687)
    if i == 17685 and 'if csv_duplicates:' in line:
        # Skip this line and the next line (the append)
        i += 2
        continue
    
    # Fix line 17760 - remove csv_duplicates from the sum
    if 'len(exact_duplicates) + len(csv_duplicates)' in line:
        line = line.replace('len(exact_duplicates) + len(csv_duplicates)', 'len(exact_duplicates)')
    
    fixed_lines.append(line)
    i += 1

with open('qt_app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

print("✅ Fixed undefined csv_duplicates references")
