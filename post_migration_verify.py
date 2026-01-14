#!/usr/bin/env python3
"""Post-migration verification for tax_sessions → realized_transactions refactor"""
import sqlite3

db_path = "casino_accounting.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("\nPOST-MIGRATION VERIFICATION - realized_transactions")
print("=" * 60)

# 1. Verify old table is gone
try:
    c.execute("SELECT COUNT(*) FROM tax_sessions")
    print("❌ FAILED: tax_sessions table still exists!")
except sqlite3.OperationalError:
    print("✅ 1. Old table (tax_sessions) successfully removed")

# 2. Verify new table exists with correct columns
try:
    c.execute("PRAGMA table_info(realized_transactions)")
    columns = [row['name'] for row in c.fetchall()]
    expected_cols = ['id', 'redemption_date', 'site_id', 'redemption_id', 'cost_basis', 'payout', 'net_pl', 'user_id', 'notes']
    
    if 'session_date' in columns:
        print("❌ FAILED: Old column name 'session_date' still exists!")
    elif 'redemption_date' not in columns:
        print("❌ FAILED: New column name 'redemption_date' not found!")
    else:
        print(f"✅ 2. New table (realized_transactions) exists with correct schema")
        print(f"   Columns: {', '.join(columns)}")
except Exception as e:
    print(f"❌ FAILED: Could not verify new table schema: {e}")

# 3. Verify record count matches baseline
c.execute("SELECT COUNT(*) as cnt FROM realized_transactions")
count = c.fetchone()['cnt']
expected_count = 38  # From pre-migration
if count == expected_count:
    print(f"✅ 3. Record count matches baseline: {count}")
else:
    print(f"❌ FAILED: Record count mismatch! Expected {expected_count}, got {count}")

# 4. Verify total net_pl matches baseline
c.execute("SELECT SUM(net_pl) as total FROM realized_transactions")
total = c.fetchone()['total']
expected_total = 7313.85  # From pre-migration
if abs(total - expected_total) < 0.01:
    print(f"✅ 4. Total net_pl matches baseline: ${total:.2f}")
else:
    print(f"❌ FAILED: Total net_pl mismatch! Expected ${expected_total:.2f}, got ${total:.2f}")

# 5. Verify no NULL dates
c.execute("SELECT COUNT(*) as cnt FROM realized_transactions WHERE redemption_date IS NULL")
null_count = c.fetchone()['cnt']
if null_count == 0:
    print(f"✅ 5. No NULL redemption_dates: {null_count}")
else:
    print(f"❌ FAILED: Found {null_count} NULL redemption_dates!")

# 6. Verify no orphaned redemption_ids
c.execute("""
    SELECT COUNT(*) as cnt 
    FROM realized_transactions rt
    LEFT JOIN redemptions r ON rt.redemption_id = r.id
    WHERE r.id IS NULL
""")
orphan_count = c.fetchone()['cnt']
if orphan_count == 0:
    print(f"✅ 6. No orphaned redemption_ids: {orphan_count}")
else:
    print(f"❌ FAILED: Found {orphan_count} orphaned redemption_ids!")

# 7. Sample a few records
c.execute("""
    SELECT id, redemption_date, redemption_id, net_pl
    FROM realized_transactions
    ORDER BY id
    LIMIT 5
""")
print("\n✅ 7. Sample records from realized_transactions:")
for row in c.fetchall():
    print(f"   ID {row['id']}: {row['redemption_date']}, redemption={row['redemption_id']}, pl=${row['net_pl']:.2f}")

# 8. Verify schema version
c.execute("SELECT MAX(version) as version FROM schema_version")
version = c.fetchone()['version']
if version >= 15:
    print(f"\n✅ 8. Schema version updated to: {version}")
else:
    print(f"\n❌ FAILED: Schema version not updated! Still at: {version}")

conn.close()

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
