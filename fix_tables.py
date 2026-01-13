#!/usr/bin/env python3
"""Script to fix table columns and button styling"""

import re

# Read the file
with open('qt_app.py', 'r') as f:
    content = f.read()

# 1. Purchase redemptions table - columns already fixed

# 2. Remove Relation column from Purchase Sessions table (line ~1321)
content = re.sub(
    r'self\.sessions_table = QtWidgets\.QTableWidget\(0, 7\)\s+self\.sessions_table\.setHorizontalHeaderLabels\(\s+\["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "Relation", "View"\]',
    'self.sessions_table = QtWidgets.QTableWidget(0, 6)\n            self.sessions_table.setHorizontalHeaderLabels(\n                ["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View"]',
    content
)

# 3. Remove Relation column from Redemption Sessions table (line ~2203)
content = re.sub(
    r'self\.sessions_table = QtWidgets\.QTableWidget\(0, 7\)\s+self\.sessions_table\.setHorizontalHeaderLabels\(\s+\["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "Relation", "View"\]',
    'self.sessions_table = QtWidgets.QTableWidget(0, 6)\n            self.sessions_table.setHorizontalHeaderLabels(\n                ["Session Date", "Start Time", "End Date/Time", "Game Type", "Status", "View"]',
    content
)

# 4. Remove Relation column from GameSession Purchases table
content = re.sub(
    r'self\.purchases_table = QtWidgets\.QTableWidget\(0, 6\)\s+self\.purchases_table\.setHorizontalHeaderLabels\(\s+\["Date", "Time", "Amount", "SC Received", "Relation", "View"\]',
    'self.purchases_table = QtWidgets.QTableWidget(0, 5)\n            self.purchases_table.setHorizontalHeaderLabels(\n                ["Date", "Time", "Amount", "SC Received", "View"]',
    content
)

# 5. Remove Relation column from GameSession Redemptions table
content = re.sub(
    r'self\.redemptions_table = QtWidgets\.QTableWidget\(0, 5\)\s+self\.redemptions_table\.setHorizontalHeaderLabels\(\s+\["Date", "Time", "Amount", "Relation", "View"\]',
    'self.redemptions_table = QtWidgets.QTableWidget(0, 4)\n            self.redemptions_table.setHorizontalHeaderLabels(\n                ["Date", "Time", "Amount", "View"]',
    content
)

# Write back
with open('qt_app.py', 'w') as f:
    f.write(content)

print("Fixed table column headers")
