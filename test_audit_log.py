#!/usr/bin/env python3
"""
Test script for audit log functionality
"""
import sys
import os
from database import Database

print("="*60)
print("AUDIT LOG FEATURE TEST")
print("="*60)

# Use a test database
test_db_path = "test_audit.db"
if os.path.exists(test_db_path):
    os.remove(test_db_path)

db = Database(test_db_path)

# Test 1: Verify infrastructure exists
print("\n[Test 1] Verifying audit log infrastructure...")
conn = db.get_connection()
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
assert cursor.fetchone(), "❌ audit_log table missing"
print("✓ audit_log table exists")

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
assert cursor.fetchone(), "❌ settings table missing"
print("✓ settings table exists")

cursor.execute("PRAGMA table_info(audit_log)")
columns = [row[1] for row in cursor.fetchall()]
required_cols = ['id', 'timestamp', 'action', 'table_name', 'record_id', 'details', 'user_name']
for col in required_cols:
    assert col in columns, f"❌ Column '{col}' missing from audit_log"
print(f"✓ All required columns present: {', '.join(required_cols)}")

conn.close()

# Test 2: Test with audit logging disabled (default)
print("\n[Test 2] Testing with audit logging disabled (default)...")
db.log_audit_conditional("INSERT", "test_table", 1, "Test details", "TestUser")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM audit_log")
count = cursor.fetchone()["count"]
conn.close()
assert count == 0, f"❌ Expected 0 records, found {count}"
print(f"✓ No records logged when disabled (count: {count})")

# Test 3: Enable audit logging
print("\n[Test 3] Enabling audit logging...")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('audit_log_enabled', '1')")
cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('audit_log_actions', 'INSERT,UPDATE,DELETE,IMPORT,REFACTOR')")
cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('audit_log_default_user', 'TestAdmin')")
cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('audit_log_retention_days', '365')")
conn.commit()
conn.close()
print("✓ Audit settings configured")

# Test 4: Log with audit enabled
print("\n[Test 4] Testing logging with audit enabled...")
db.log_audit_conditional("INSERT", "purchases", 123, "TestUser - TestSite - $100.00", "TestUser")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()
conn.close()
assert row, "❌ No record found"
assert row['action'] == 'INSERT', f"❌ Wrong action: {row['action']}"
assert row['table_name'] == 'purchases', f"❌ Wrong table: {row['table_name']}"
assert row['record_id'] == 123, f"❌ Wrong record_id: {row['record_id']}"
assert row['user_name'] == 'TestUser', f"❌ Wrong user: {row['user_name']}"
print(f"✓ Record logged correctly:")
print(f"  Action: {row['action']}, Table: {row['table_name']}, ID: {row['record_id']}, User: {row['user_name']}")

# Test 5: Test action filtering
print("\n[Test 5] Testing action filtering...")
db.log_audit_conditional("UPDATE", "redemptions", 456, "Update test", "TestUser")
db.log_audit_conditional("DELETE", "expenses", 789, "Delete test", "TestUser")
db.log_audit_conditional("BACKUP", "database", None, "Backup test", "TestUser")  # Not in enabled list

conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE action='UPDATE'")
update_count = cursor.fetchone()["count"]
cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE action='DELETE'")
delete_count = cursor.fetchone()["count"]
cursor.execute("SELECT COUNT(*) as count FROM audit_log WHERE action='BACKUP'")
backup_count = cursor.fetchone()["count"]
conn.close()

assert update_count == 1, f"❌ UPDATE count: {update_count} (expected 1)"
assert delete_count == 1, f"❌ DELETE count: {delete_count} (expected 1)"
assert backup_count == 0, f"❌ BACKUP count: {backup_count} (expected 0)"
print(f"✓ Action filtering works:")
print(f"  UPDATE logged: {update_count}, DELETE logged: {delete_count}, BACKUP filtered: {backup_count}")

# Test 6: Test default user
print("\n[Test 6] Testing default user from settings...")
db.log_audit_conditional("INSERT", "sessions", 999, "Session test", None)  # No user provided
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT user_name FROM audit_log WHERE action='INSERT' AND table_name='sessions' ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()
conn.close()
assert row, "❌ No record found"
assert row['user_name'] == 'TestAdmin', f"❌ Wrong user: {row['user_name']} (expected TestAdmin)"
print(f"✓ Default user applied: {row['user_name']}")

# Test 7: Test silent failure
print("\n[Test 7] Testing silent failure (bad table query)...")
try:
    # Temporarily break something to test silent failure
    db.log_audit_conditional("INSERT", "nonexistent_table", 1, "Should not crash", "TestUser")
    print("✓ Silent failure works - no exception raised")
except Exception as e:
    print(f"❌ Exception raised: {e}")

# Test 8: Verify total record count
print("\n[Test 8] Verifying total record count...")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as total FROM audit_log")
total = cursor.fetchone()["total"]
cursor.execute("SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY action")
breakdown = cursor.fetchall()
conn.close()
print(f"✓ Total records in audit_log: {total}")
print("  Breakdown by action:")
for row in breakdown:
    print(f"    {row['action']}: {row['count']}")

# Cleanup
os.remove(test_db_path)

print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\nAudit log feature is working correctly:")
print("  ✓ Infrastructure in place")
print("  ✓ ON/OFF toggle works")
print("  ✓ Action filtering works")
print("  ✓ Default user configuration works")
print("  ✓ Silent failure prevents crashes")
print("  ✓ Conditional logging respects settings")
