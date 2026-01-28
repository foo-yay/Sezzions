"""Unit tests for BulkToolsRepository with failure injection."""

import pytest
import sqlite3
from repositories.bulk_tools_repository import BulkToolsRepository


def test_bulk_import_commits_on_success(test_db):
    """Test that bulk import commits all records atomically."""
    test_db.execute("CREATE TABLE t_import (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
    
    repo = BulkToolsRepository(test_db)
    
    records = [
        {'name': 'Alice', 'value': 100},
        {'name': 'Bob', 'value': 200},
        {'name': 'Charlie', 'value': 300},
    ]
    
    result = repo.bulk_import_records('t_import', records)
    
    assert result.success is True
    assert result.records_inserted == 3
    assert result.records_updated == 0
    
    # Verify all records are in DB
    rows = test_db.fetch_all("SELECT name, value FROM t_import ORDER BY name", ())
    assert len(rows) == 3
    assert rows[0]['name'] == 'Alice'
    assert rows[1]['name'] == 'Bob'
    assert rows[2]['name'] == 'Charlie'


def test_bulk_import_rolls_back_on_error(test_db):
    """Test that bulk import rolls back ALL records if any insert fails."""
    test_db.execute("CREATE TABLE t_import2 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, value INTEGER)")
    
    # Pre-insert a conflicting record
    test_db.execute("INSERT INTO t_import2 (name, value) VALUES (?, ?)", ('Bob', 999))
    
    repo = BulkToolsRepository(test_db)
    
    records = [
        {'name': 'Alice', 'value': 100},
        {'name': 'Bob', 'value': 200},  # This will conflict
        {'name': 'Charlie', 'value': 300},
    ]
    
    result = repo.bulk_import_records('t_import2', records)
    
    # Should fail and rollback
    assert result.success is False
    assert result.records_inserted == 0
    assert result.error is not None
    
    # Verify NO new records were inserted (only the original Bob remains)
    rows = test_db.fetch_all("SELECT name FROM t_import2 ORDER BY name", ())
    assert len(rows) == 1
    assert rows[0]['name'] == 'Bob'


def test_bulk_import_update_on_conflict(test_db):
    """Test bulk import with update_on_conflict mode."""
    test_db.execute("CREATE TABLE t_update (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
    
    # Pre-insert records
    test_db.execute("INSERT INTO t_update (name, value) VALUES (?, ?)", ('Alice', 100))
    test_db.execute("INSERT INTO t_update (name, value) VALUES (?, ?)", ('Bob', 200))
    
    repo = BulkToolsRepository(test_db)
    
    records = [
        {'name': 'Alice', 'value': 111},  # Update
        {'name': 'Bob', 'value': 222},    # Update
        {'name': 'Charlie', 'value': 333}, # Insert
    ]
    
    result = repo.bulk_import_records(
        't_update',
        records,
        update_on_conflict=True,
        unique_columns=('name',)
    )
    
    assert result.success is True
    assert result.records_inserted == 1  # Charlie
    assert result.records_updated == 2   # Alice, Bob
    
    # Verify updates
    alice = test_db.fetch_one("SELECT value FROM t_update WHERE name = ?", ('Alice',))
    assert alice['value'] == 111
    
    bob = test_db.fetch_one("SELECT value FROM t_update WHERE name = ?", ('Bob',))
    assert bob['value'] == 222
    
    charlie = test_db.fetch_one("SELECT value FROM t_update WHERE name = ?", ('Charlie',))
    assert charlie['value'] == 333


def test_bulk_delete_tables_commits_atomically(test_db):
    """Test that bulk delete clears tables atomically."""
    test_db.execute("CREATE TABLE t_delete1 (id INTEGER PRIMARY KEY, name TEXT)")
    test_db.execute("CREATE TABLE t_delete2 (id INTEGER PRIMARY KEY, value INTEGER)")
    
    # Insert data
    test_db.execute("INSERT INTO t_delete1 (name) VALUES (?)", ('Alice',))
    test_db.execute("INSERT INTO t_delete1 (name) VALUES (?)", ('Bob',))
    test_db.execute("INSERT INTO t_delete2 (value) VALUES (?)", (100,))
    test_db.execute("INSERT INTO t_delete2 (value) VALUES (?)", (200,))
    
    repo = BulkToolsRepository(test_db)
    
    result = repo.bulk_delete_tables(['t_delete1', 't_delete2'])
    
    assert result.success is True
    assert result.records_deleted == 4
    assert set(result.tables_cleared) == {'t_delete1', 't_delete2'}
    
    # Verify tables are empty
    count1 = test_db.fetch_one("SELECT COUNT(*) as c FROM t_delete1", ())
    count2 = test_db.fetch_one("SELECT COUNT(*) as c FROM t_delete2", ())
    assert count1['c'] == 0
    assert count2['c'] == 0


def test_bulk_delete_keeps_setup_data(test_db):
    """Test that bulk delete respects keep_setup_data flag."""
    # Use the existing purchases table (transactional) and create a mock setup table
    test_db.execute("CREATE TABLE t_setup_mock (id INTEGER PRIMARY KEY, name TEXT)")
    
    # Create required FK records first
    test_db.execute("INSERT INTO users (name) VALUES (?)", ('TestUser',))
    test_db.execute("INSERT INTO sites (name, sc_rate) VALUES (?, ?)", ('TestSite', 1.0))
    
    # Insert data into the real purchases table
    test_db.execute("INSERT INTO purchases (user_id, site_id, amount, sc_received, purchase_date, purchase_time, remaining_amount) VALUES (1, 1, '100.00', '0.00', '2026-01-01', '12:00:00', '100.00')")
    test_db.execute("INSERT INTO t_setup_mock (name) VALUES (?)", ('Alice',))
    
    repo = BulkToolsRepository(test_db)
    
    # Request to clear both tables but keep setup data
    result = repo.bulk_delete_tables(['purchases', 't_setup_mock'], keep_setup_data=True)
    
    assert result.success is True
    assert 'purchases' in result.tables_cleared
    assert 't_setup_mock' not in result.tables_cleared  # Should be skipped
    
    # Verify purchases cleared but setup table remains
    purchases_count = test_db.fetch_one("SELECT COUNT(*) as c FROM purchases", ())
    setup_count = test_db.fetch_one("SELECT COUNT(*) as c FROM t_setup_mock", ())
    
    assert purchases_count['c'] == 0
    assert setup_count['c'] == 1


def test_bulk_merge_from_backup(test_db, tmp_path):
    """Test merging records from a backup database."""
    # Create backup database
    backup_path = tmp_path / "backup.db"
    backup_conn = sqlite3.connect(str(backup_path))
    backup_conn.execute("CREATE TABLE t_merge (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
    backup_conn.execute("INSERT INTO t_merge (name, value) VALUES (?, ?)", ('Alice', 100))
    backup_conn.execute("INSERT INTO t_merge (name, value) VALUES (?, ?)", ('Bob', 200))
    backup_conn.commit()
    backup_conn.close()
    
    # Create same table in test DB
    test_db.execute("CREATE TABLE t_merge (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)")
    
    repo = BulkToolsRepository(test_db)
    
    result = repo.bulk_merge_from_backup(str(backup_path), ['t_merge'])
    
    assert result.success is True
    assert result.records_merged == 2
    assert 't_merge' in result.tables_affected
    
    # Verify records merged
    rows = test_db.fetch_all("SELECT name FROM t_merge ORDER BY name", ())
    assert len(rows) == 2
    assert rows[0]['name'] == 'Alice'
    assert rows[1]['name'] == 'Bob'


def test_bulk_merge_skips_duplicates(test_db, tmp_path):
    """Test that merge skips duplicate records when requested."""
    # Create backup database
    backup_path = tmp_path / "backup_dup.db"
    backup_conn = sqlite3.connect(str(backup_path))
    backup_conn.execute("CREATE TABLE t_merge2 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, value INTEGER)")
    backup_conn.execute("INSERT INTO t_merge2 (name, value) VALUES (?, ?)", ('Alice', 100))
    backup_conn.execute("INSERT INTO t_merge2 (name, value) VALUES (?, ?)", ('Bob', 200))
    backup_conn.commit()
    backup_conn.close()
    
    # Create same table in test DB with one existing record
    test_db.execute("CREATE TABLE t_merge2 (id INTEGER PRIMARY KEY, name TEXT UNIQUE, value INTEGER)")
    test_db.execute("INSERT INTO t_merge2 (name, value) VALUES (?, ?)", ('Alice', 999))
    
    repo = BulkToolsRepository(test_db)
    
    result = repo.bulk_merge_from_backup(str(backup_path), ['t_merge2'], skip_duplicates=True)
    
    assert result.success is True
    assert result.records_merged == 1  # Only Bob (Alice skipped)
    
    # Verify Alice kept original value, Bob merged
    alice = test_db.fetch_one("SELECT value FROM t_merge2 WHERE name = ?", ('Alice',))
    bob = test_db.fetch_one("SELECT value FROM t_merge2 WHERE name = ?", ('Bob',))
    
    assert alice['value'] == 999  # Original value
    assert bob['value'] == 200    # Merged value


def test_failure_injection_mid_import_rolls_back(test_db):
    """CRITICAL TEST: Failure mid-import must rollback ALL records (no partial writes)."""
    test_db.execute("CREATE TABLE t_fail (id INTEGER PRIMARY KEY, name TEXT UNIQUE, value INTEGER)")
    
    repo = BulkToolsRepository(test_db)
    
    # Records with a duplicate that will fail on the 3rd insert
    records = [
        {'name': 'Alice', 'value': 100},
        {'name': 'Bob', 'value': 200},
        {'name': 'Alice', 'value': 300},  # Duplicate name - will fail
        {'name': 'Charlie', 'value': 400},
    ]
    
    result = repo.bulk_import_records('t_fail', records)
    
    # Should fail
    assert result.success is False
    assert result.error is not None
    
    # CRITICAL: Verify NO records were inserted (full rollback)
    rows = test_db.fetch_all("SELECT * FROM t_fail", ())
    assert len(rows) == 0, "Transaction rollback failed - partial records were committed!"


def test_failure_injection_mid_delete_rolls_back(test_db):
    """CRITICAL TEST: Failure mid-delete must rollback ALL deletes."""
    # This test is more conceptual since DELETE FROM rarely fails,
    # but we can simulate by using a nonexistent table in the list
    test_db.execute("CREATE TABLE t_del_ok (id INTEGER PRIMARY KEY, value INTEGER)")
    test_db.execute("INSERT INTO t_del_ok (value) VALUES (100)")
    test_db.execute("INSERT INTO t_del_ok (value) VALUES (200)")
    
    repo = BulkToolsRepository(test_db)
    
    # Include a nonexistent table to trigger failure
    result = repo.bulk_delete_tables(['t_del_ok', 'nonexistent_table'])
    
    # Should fail
    assert result.success is False
    
    # CRITICAL: Verify first table was NOT cleared (rollback)
    rows = test_db.fetch_all("SELECT * FROM t_del_ok", ())
    assert len(rows) == 2, "Transaction rollback failed - table was cleared despite error!"
