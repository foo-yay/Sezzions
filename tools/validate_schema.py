#!/usr/bin/env python3
"""
Database Schema Validation Script

Validates a SQLite database against the authoritative schema DDL embedded in
docs/PROJECT_SPEC.md (Appendix A).
"""

import sqlite3
import sys
import os
from pathlib import Path
from urllib.parse import quote


def _extract_schema_sql_from_project_spec(spec_path: Path) -> str:
    """Extract the Appendix A ```sql fenced block from PROJECT_SPEC.md."""
    text = spec_path.read_text(encoding="utf-8")
    appendix_marker = "Appendix A) SQLite Schema"
    marker_index = text.find(appendix_marker)
    if marker_index == -1:
        raise ValueError(f"Could not find '{appendix_marker}' in {spec_path}")

    after_marker = text[marker_index:]
    fence_start = after_marker.find("```sql")
    if fence_start == -1:
        raise ValueError(f"Could not find a ```sql block after '{appendix_marker}' in {spec_path}")

    fence_start += len("```sql")
    fence_end = after_marker.find("```", fence_start)
    if fence_end == -1:
        raise ValueError(f"Unterminated ```sql block in {spec_path}")

    schema_sql = after_marker[fence_start:fence_end].strip()
    if not schema_sql:
        raise ValueError(f"Empty schema SQL block in {spec_path}")
    return schema_sql + "\n"


def _introspect_tables_and_columns(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [row[0] for row in cursor.fetchall()]

    tables: dict[str, dict[str, list[str]]] = {}
    for table_name in table_names:
        if table_name.startswith("sqlite_"):
            continue
        cursor.execute(f"PRAGMA table_info({table_name})")
        tables[table_name] = {"columns": [row[1] for row in cursor.fetchall()]}

    return tables


def _introspect_indexes(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {row[0] for row in cursor.fetchall() if row[0]}

def _get_expected_schema_from_project_spec(spec_path: Path) -> tuple[dict, set[str]]:
    schema_sql = _extract_schema_sql_from_project_spec(spec_path)
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        expected_tables = _introspect_tables_and_columns(conn)
        expected_indexes = _introspect_indexes(conn)
        return expected_tables, expected_indexes
    finally:
        conn.close()


def _get_actual_schema(db_path: str) -> tuple[dict, set[str]]:
    db_abs_posix = Path(db_path).expanduser().resolve().as_posix()
    db_uri = f"file:{quote(db_abs_posix, safe='/')}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(db_uri, uri=True)
    except sqlite3.OperationalError:
        db_uri = f"file:{quote(db_abs_posix, safe='/')}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
    try:
        actual_tables = _introspect_tables_and_columns(conn)
        actual_indexes = _introspect_indexes(conn)
        return actual_tables, actual_indexes
    finally:
        conn.close()


def validate_schema(db_path: str) -> tuple[bool, list[str], list[str]]:
    """
    Validate database schema against docs/PROJECT_SPEC.md
    
    Returns:
        (is_valid, missing_tables, missing_columns)
    """
    repo_root = Path(__file__).resolve().parents[1]
    spec_path = repo_root / "docs" / "PROJECT_SPEC.md"
    expected_tables, expected_indexes = _get_expected_schema_from_project_spec(spec_path)
    actual_tables, actual_indexes = _get_actual_schema(db_path)
    missing_tables = []
    missing_columns = []
    
    print("\n" + "="*80)
    print("DATABASE SCHEMA VALIDATION REPORT")
    print("="*80)
    print(f"\nReference: {spec_path.relative_to(repo_root)} (Appendix A)")
    print(f"Database: {db_path}\n")
    
    # Check each expected table
    for table_name, spec in sorted(expected_tables.items()):
        if table_name not in actual_tables:
            missing_tables.append(table_name)
            print(f"❌ MISSING TABLE: {table_name}")
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
    unexpected_tables = set(actual_tables.keys()) - set(expected_tables.keys())
    if unexpected_tables:
        print(f"\n⚠️  Unexpected tables (not in spec): {', '.join(unexpected_tables)}")

    missing_indexes = sorted(expected_indexes - actual_indexes)
    if missing_indexes:
        print(f"\n⚠️  Missing indexes (present in spec, not in DB): {', '.join(missing_indexes)}")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Expected tables: {len(expected_tables)}")
    print(f"Actual tables: {len(actual_tables)}")
    print(f"Missing tables: {len(missing_tables)}")
    print(f"Missing columns: {len(missing_columns)}")
    print(f"Missing indexes: {len(missing_indexes)}")
    
    is_valid = len(missing_tables) == 0 and len(missing_columns) == 0 and len(missing_indexes) == 0
    
    if is_valid:
        print("\n✅ Schema is VALID and matches docs/PROJECT_SPEC.md Appendix A")
    else:
        print("\n❌ Schema is INVALID - missing components detected")
        print("\nAction Required:")
        if missing_tables:
            print(f"  - Add {len(missing_tables)} missing table(s)")
        if missing_columns:
            print(f"  - Add {len(missing_columns)} missing column(s)")
        if missing_indexes:
            print(f"  - Add {len(missing_indexes)} missing index(es)")
    
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
