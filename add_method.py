#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script to add _clear_all_audit_logs method to qt_app.py"""

# Read the file
with open('qt_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and insert the method after _clear_old_audit_records
search_str = """    def _clear_old_audit_records(self):
        \"\"\"Delete audit log records older than retention setting\"\"\"
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get retention setting
            cursor.execute("SELECT value FROM settings WHERE key = 'audit_log_retention_days'")
            result = cursor.fetchone()
            retention_days = int(result["value"]) if result else 365
            
            # Delete old records
            cursor.execute(\"\"\"
                DELETE FROM audit_log
                WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
            \"\"\", (retention_days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "Records Cleared",
                f"Deleted {deleted_count} audit log record(s) older than {retention_days} days."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear old audit records:\\n{str(e)}"
            )"""

new_method = """    def _clear_all_audit_logs(self):
        \"\"\"Delete ALL audit log records after confirmation\"\"\"
        reply = QtWidgets.QMessageBox.question(
            self,
            "⚠️ Clear All Audit Logs",
            "Are you sure you want to delete ALL audit log records?\\n\\n"
            "⚠️ WARNING: This action cannot be undone!\\n\\n"
            "This will permanently erase the entire audit log history.\\n\\n"
            "Consider exporting the log first if you need to keep a record.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Count records before deletion
            cursor.execute("SELECT COUNT(*) as count FROM audit_log")
            result = cursor.fetchone()
            total_count = result["count"] if result else 0
            
            # Delete all records
            cursor.execute("DELETE FROM audit_log")
            conn.commit()
            conn.close()
            
            QtWidgets.QMessageBox.information(
                self,
                "All Records Cleared",
                f"Successfully deleted all {total_count} audit log record(s)."
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Clear Error",
                f"Failed to clear all audit records:\\n{str(e)}"
            )"""

if search_str in content:
    # Insert the new method right after the old one
    insert_pos = content.find(search_str) + len(search_str)
    content = content[:insert_pos] + "\n\n" + new_method + content[insert_pos:]
    
    with open('qt_app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Successfully added _clear_all_audit_logs method")
else:
    print("❌ Could not find _clear_old_audit_records method")
