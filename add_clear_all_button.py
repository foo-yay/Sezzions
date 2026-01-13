#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to add Clear All Logs button to qt_app.py"""

# Read the file
with open('qt_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the button section
old_section = """        # Action buttons
        audit_buttons_row = QtWidgets.QHBoxLayout()
        audit_buttons_row.setSpacing(10)

        save_audit_btn = QtWidgets.QPushButton("💾 Save Settings")
        save_audit_btn.setObjectName("PrimaryButton")
        save_audit_btn.setMaximumWidth(150)
        save_audit_btn.clicked.connect(self._save_audit_settings)
        audit_buttons_row.addWidget(save_audit_btn)

        view_log_btn = QtWidgets.QPushButton("👁 View Log")
        view_log_btn.setMaximumWidth(150)
        view_log_btn.clicked.connect(self._view_audit_log)
        audit_buttons_row.addWidget(view_log_btn)

        export_log_btn = QtWidgets.QPushButton("📤 Export Log")
        export_log_btn.setMaximumWidth(150)
        export_log_btn.clicked.connect(self._export_audit_log)
        audit_buttons_row.addWidget(export_log_btn)

        clear_log_btn = QtWidgets.QPushButton("🗑 Clear Old Records")
        clear_log_btn.setMaximumWidth(180)
        clear_log_btn.clicked.connect(self._clear_old_audit_records)
        audit_buttons_row.addWidget(clear_log_btn)

        audit_buttons_row.addStretch()
        audit_layout.addLayout(audit_buttons_row)"""

new_section = """        # Action buttons - Row 1 (Primary actions)
        audit_buttons_row1 = QtWidgets.QHBoxLayout()
        audit_buttons_row1.setSpacing(10)

        save_audit_btn = QtWidgets.QPushButton("💾 Save Settings")
        save_audit_btn.setObjectName("PrimaryButton")
        save_audit_btn.setMaximumWidth(150)
        save_audit_btn.clicked.connect(self._save_audit_settings)
        audit_buttons_row1.addWidget(save_audit_btn)

        view_log_btn = QtWidgets.QPushButton("👁 View Log")
        view_log_btn.setMaximumWidth(150)
        view_log_btn.clicked.connect(self._view_audit_log)
        audit_buttons_row1.addWidget(view_log_btn)

        export_log_btn = QtWidgets.QPushButton("📤 Export Log")
        export_log_btn.setMaximumWidth(150)
        export_log_btn.clicked.connect(self._export_audit_log)
        audit_buttons_row1.addWidget(export_log_btn)

        audit_buttons_row1.addStretch()
        audit_layout.addLayout(audit_buttons_row1)

        # Action buttons - Row 2 (Destructive actions)
        audit_buttons_row2 = QtWidgets.QHBoxLayout()
        audit_buttons_row2.setSpacing(10)

        clear_log_btn = QtWidgets.QPushButton("🗑 Clear Old Records")
        clear_log_btn.setMaximumWidth(180)
        clear_log_btn.clicked.connect(self._clear_old_audit_records)
        audit_buttons_row2.addWidget(clear_log_btn)

        clear_all_log_btn = QtWidgets.QPushButton("⚠️ Clear All Logs")
        clear_all_log_btn.setMaximumWidth(150)
        clear_all_log_btn.setObjectName("WarningButton")
        clear_all_log_btn.setStyleSheet(\"\"\"
            QPushButton#WarningButton {
                background-color: #d32f2f !important;
                color: white !important;
                border: 1px solid #b71c1c !important;
                font-weight: bold;
            }
            QPushButton#WarningButton:hover {
                background-color: #b71c1c !important;
            }
        \"\"\")
        clear_all_log_btn.clicked.connect(self._clear_all_audit_logs)
        audit_buttons_row2.addWidget(clear_all_log_btn)

        audit_buttons_row2.addStretch()
        audit_layout.addLayout(audit_buttons_row2)"""

if old_section in content:
    content = content.replace(old_section, new_section)
    with open('qt_app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Successfully added Clear All Logs button to qt_app.py")
    print("📝 Backup saved as qt_app.py.backup")
    print("🔄 Restart the application to see the changes")
else:
    print("❌ Could not find the section to replace")
    print("The file may have already been updated or the format is different")
