#!/usr/bin/env python3
"""
Database Schema Validation Script

Compares implemented schema in repositories/database.py against 
specification in docs/PROJECT_SPEC.md
"""

import sqlite3
import sys
import os
from pathlib import Path

# Expected tables from docs/PROJECT_SPEC.md
EXPECTED_TABLES = {
    'schema_version': {
        'columns': ['version', 'applied_at'],
        'purpose': 'Track schema migrations'
    },
    'users': {
        'columns': ['id', 'name', 'email', 'is_active', 'notes', 'created_at', 'updated_at'],
        'purpose': 'User accounts (players)'
    },
    'sites': {
        'columns': ['id', 'name', 'url', 'sc_rate', 'is_active', 'notes', 'created_at', 'updated_at'],
        'purpose': 'Casino sites (Stake, Fortune Coins, etc.)'
    },
    'cards': {
        'columns': ['id', 'name', 'user_id', 'last_four', 'cashback_rate', 'is_active', 'notes', 'created_at', 'updated_at'],
        'purpose': 'Payment cards for purchases'
    },
    'purchases': {
        'columns': ['id', 'purchase_date', 'purchase_time', 'site_id', 'user_id', 'amount', 'sc_received', 'card_id', 'remaining_amount', 'notes', 'created_at', 'updated_at'],
        'purpose': 'SC purchases (adds basis to FIFO pool)'
    },
    'redemptions': {
        'columns': ['id', 'redemption_date', 'redemption_time', 'site_id', 'user_id', 'amount', 'method_id', 'is_free_sc', 'fees', 'notes', 'created_at', 'updated_at'],
        'purpose': 'SC redemptions (consumes basis via FIFO)'
    },
    'redemption_allocations': {
        'columns': ['id', 'redemption_id', 'purchase_id', 'allocated_amount', 'created_at'],
        'purpose': 'Links redemptions to purchases for FIFO basis tracking'
    },
    'realized_transactions': {
        'columns': ['id', 'redemption_date', 'site_id', 'user_id', 'redemption_id', 'cost_basis', 'payout', 'net_pl', 'notes', 'created_at'],
        'purpose': 'Tax sessions (taxable profit/loss events)'
    },
    'game_sessions': {
        'columns': [
            'id', 'session_date', 'session_time', 'end_date', 'end_time',
            'site_id', 'user_id', 'game_id',
            'starting_balance', 'ending_balance', 'starting_redeemable', 'ending_redeemable',
            'purchases_during', 'redemptions_during',
            'expected_start_total', 'expected_start_redeemable', 'discoverable_sc',
            'delta_total', 'delta_redeem', 'session_basis', 'basis_consumed', 'net_taxable_pl',
            'status', 'notes', 'created_at', 'updated_at'
        ],
        'purpose': 'Active game sessions with SC balances'
    },
    'redemption_methods': {
        'columns': ['id', 'name', 'method_type', 'user_id', 'is_active', 'notes', 'created_at'],
        'purpose': 'Payment methods for redemptions'
    },
    'games': {
        'columns': ['id', 'name', 'game_type_id', 'rtp', 'is_active', 'notes', 'created_at'],
        'purpose': 'Game catalog'
    },
    'game_types': {
        'columns': ['id', 'name', 'is_active', 'notes', 'created_at'],
        'purpose': 'Game type categories (Slots, Table Games, etc.)'
    },
    'audit_log': {
        'columns': ['id', 'action', 'table_name', 'record_id', 'details', 'user_name', 'timestamp'],
        'purpose': 'Audit trail for compliance'
    },
    'settings': {
        'columns': ['key', 'value'],
        'purpose': 'Application settings (key-value store)'
    }
}


def get_actual_tables(db_path: str) -> dict:
    """Get actual tables and columns from database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0]: {'columns': []} for row in cursor.fetchall()}
    
    # Get columns for each table
    for table_name in tables.keys():
        cursor.execute(f"PRAGMA table_info({table_name})")
        tables[table_name]['columns'] = [row[1] for row in cursor.fetchall()]
    
    conn.close()
    return tables


def validate_schema(db_path: str) -> tuple[bool, list[str], list[str]]:
    """
    Validate database schema against docs/PROJECT_SPEC.md
    
    Returns:
        (is_valid, missing_tables, missing_columns)
    """
    actual_tables = get_actual_tables(db_path)
    missing_tables = []
    missing_columns = []
    
    print("\n" + "="*80)
    print("DATABASE SCHEMA VALIDATION REPORT")
    print("="*80)
    print(f"\nReference: docs/PROJECT_SPEC.md")
    print(f"Database: {db_path}\n")
    
    # Check each expected table
    for table_name, spec in EXPECTED_TABLES.items():
        if table_name not in actual_tables:
            missing_tables.append(table_name)
            print(f"❌ MISSING TABLE: {table_name}")
            print(f"   Purpose: {spec['purpose']}")
            print(f"   Expected columns: {', '.join(spec['columns'])}\n")
        else:
            # Check columns
            actual_cols = set(actual_tables[table_name]['columns'])
            expected_cols = set(spec['columns'])
            missing_cols = expected_cols - actual_cols
            extra_cols = actual_cols - expected_cols
            
            if missing_cols or extra_cols:
                print(f"⚠️  TABLE: {table_name}")
                if missing_cols:
                    for col in missing_cols:
                        missing_columns.append(f"{table_name}.{col}")
                        print(f"   ❌ Missing column: {col}")
                if extra_cols:
                    for col in extra_cols:
                        print(f"   ⚠️  Extra column: {col} (not in spec)")
                print()
            else:
                print(f"✅ TABLE: {table_name} ({len(actual_cols)} columns)")
    
    # Check for unexpected tables
    unexpected_tables = set(actual_tables.keys()) - set(EXPECTED_TABLES.keys())
    if unexpected_tables:
        print(f"\n⚠️  Unexpected tables (not in spec): {', '.join(unexpected_tables)}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Expected tables: {len(EXPECTED_TABLES)}")
    print(f"Actual tables: {len(actual_tables)}")
    print(f"Missing tables: {len(missing_tables)}")
    print(f"Missing columns: {len(missing_columns)}")
    
    is_valid = len(missing_tables) == 0 and len(missing_columns) == 0
    
    if is_valid:
        print("\n✅ Schema is VALID and matches docs/PROJECT_SPEC.md")
    else:
        print("\n❌ Schema is INVALID - missing components detected")
        print("\nAction Required:")
        if missing_tables:
            print(f"  - Add {len(missing_tables)} missing table(s)")
        if missing_columns:
            print(f"  - Add {len(missing_columns)} missing column(s)")
    
    print("="*80 + "\n")
    
    return is_valid, missing_tables, missing_columns


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    default_db_path = repo_root / "sezzions.db"
    db_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SEZZIONS_DB_PATH", str(default_db_path))
    db_path_obj = Path(db_path)
    
    if not db_path_obj.exists():
        print(f"❌ Database not found: {db_path_obj}")
        print("Run the app once to create the database, or pass a DB path:")
        print("  python3 tools/validate_schema.py /path/to/sezzions.db")
        sys.exit(1)
    
    is_valid, missing_tables, missing_columns = validate_schema(str(db_path_obj))
    
    sys.exit(0 if is_valid else 1)
