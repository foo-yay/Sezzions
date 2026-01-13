#!/usr/bin/env python3
"""Script to fix button styling using GridLayout pattern"""

import re

# Read the file
with open('qt_app.py', 'r') as f:
    content = f.read()

# Pattern for Purchase Sessions table (was column 6, now 5)
old_pattern_1 = r'''            view_container = QtWidgets\.QWidget\(\)
            view_container\.setSizePolicy\(
                QtWidgets\.QSizePolicy\.Expanding, QtWidgets\.QSizePolicy\.Expanding
            \)
            view_layout = QtWidgets\.QGridLayout\(view_container\)
            view_layout\.setContentsMargins\(6, 4, 6, 4\)
            view_layout\.addWidget\(view_btn, 0, 0, QtCore\.Qt\.AlignCenter\)
            self\.sessions_table\.setCellWidget\(row_idx, 6, view_container\)
            self\.sessions_table\.setRowHeight\(
                row_idx,
                max\(self\.sessions_table\.rowHeight\(row_idx\), view_btn\.sizeHint\(\)\.height\(\) \+ 16\),
            \)

    def _populate_redemptions_table\(self\):'''

new_pattern_1 = '''            view_container = QtWidgets.QWidget()
            view_container.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            view_layout = QtWidgets.QGridLayout(view_container)
            view_layout.setContentsMargins(6, 4, 6, 4)
            view_layout.addWidget(view_btn, 0, 0, QtCore.Qt.AlignCenter)
            self.sessions_table.setCellWidget(row_idx, 5, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self):'''

content = content.replace(old_pattern_1, new_pattern_1)
print("Fixed Purchase Sessions button column")

# Pattern for Redemption Sessions table (was column 6, now 5)
old_pattern_2 = r'''self\.sessions_table\.setCellWidget\(row_idx, 6, view_container\)

    def _open_purchase\(self, purchase_id\):'''

new_pattern_2 = '''self.sessions_table.setCellWidget(row_idx, 5, view_container)
            self.sessions_table.setRowHeight(
                row_idx,
                max(self.sessions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _open_purchase(self, purchase_id):'''

content = re.sub(old_pattern_2, new_pattern_2, content)
print("Fixed Redemption Sessions button column")

# Pattern for GameSession Purchases table (was column 5, now 4)
old_pattern_3 = r'''self\.purchases_table\.setCellWidget\(row_idx, 5, view_container\)
            self\.purchases_table\.setRowHeight\(
                row_idx,
                max\(self\.purchases_table\.rowHeight\(row_idx\), view_btn\.sizeHint\(\)\.height\(\) \+ 16\),
            \)

    def _populate_redemptions_table\(self\):'''

new_pattern_3 = '''self.purchases_table.setCellWidget(row_idx, 4, view_container)
            self.purchases_table.setRowHeight(
                row_idx,
                max(self.purchases_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )

    def _populate_redemptions_table(self):'''

content = content.replace(old_pattern_3, new_pattern_3)
print("Fixed GameSession Purchases button column")

# Pattern for GameSession Redemptions table (was column 4, now 3)
old_pattern_4 = r'''self\.redemptions_table\.setCellWidget\(row_idx, 4, view_container\)'''
new_pattern_4 = '''self.redemptions_table.setCellWidget(row_idx, 3, view_container)
            self.redemptions_table.setRowHeight(
                row_idx,
                max(self.redemptions_table.rowHeight(row_idx), view_btn.sizeHint().height() + 16),
            )'''

content = re.sub(old_pattern_4, new_pattern_4, content)
print("Fixed GameSession Redemptions button column")

# Write back
with open('qt_app.py', 'w') as f:
    f.write(content)

print("\nAll button columns and row heights fixed")
