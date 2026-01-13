#!/usr/bin/env python3
"""Quick test to check if Clear All Logs button exists"""

import sys
from PyQt5 import QtWidgets
from database import Database

# Import the ToolsSetupTab
from qt_app import ToolsSetupTab

app = QtWidgets.QApplication(sys.argv)
db = Database()

# Create the tab
tab = ToolsSetupTab(db, None)

# Find all QPushButton widgets
buttons = tab.findChildren(QtWidgets.QPushButton)

print(f"Total buttons found: {len(buttons)}")
print("\nButton texts containing 'Clear':")
for btn in buttons:
    text = btn.text()
    if "Clear" in text or "clear" in text:
        print(f"  - {text}")

print("\nAll button texts:")
for btn in buttons:
    print(f"  - {btn.text()}")
