# Phase 3: Database Tools - Implementation Status

## Overview
Phase 3 implements database backup, restore, and reset functionality to support safe data management workflows. All services use SQLite's online backup API for non-blocking operations.

**Status:** ✅ **COMPLETE** - 27/27 tests passing (18 unit + 9 integration)

---

## 1. BackupService

**File:** `services/tools/backup_service.py` (292 lines)

### Features Implemented

#### Core Backup Operations
- **`backup_database()`** - SQLite online backup using `src_conn.backup(dest_conn)`
  - Non-blocking: App continues running during backup
  - Page-by-page copy ensures consistency
  - Optional audit log exclusion
  - File existence check (prevents accidental overwrites)
  
- **`backup_with_timestamp()`** - Auto-generate timestamped filenames
  - Format: `{prefix}_YYYYMMDD_HHMMSS.db`
  - Default prefix: "backup"
  - Returns BackupResult with file path and size

#### Backup Management
- **`list_backups()`** - List all backups in directory
  - Sorted by timestamp (most recent first)
  - Returns: path, filename, timestamp, size_bytes
  - Glob pattern filtering by prefix
  
- **`delete_old_backups()`** - Cleanup old backups
  - Keep N most recent backups
  - Deletes older backups automatically
  - Safe: Skips files that can't be deleted
  
- **`verify_backup()`** - Integrity verification
  - Uses `PRAGMA integrity_check`
  - Returns BackupResult with success/error

### API Example
```python
from services.tools import BackupService, BackupResult

# Create service
service = BackupService(db_connection)

# Timestamped backup
result = service.backup_with_timestamp('backups/')
# Creates: backups/backup_20260127_143052.db

# List backups
backups = service.list_backups('backups/')
for backup in backups:
    print(f"{backup['timestamp']}: {backup['size_bytes']} bytes")

# Cleanup old backups (keep 10 most recent)
deleted = service.delete_old_backups('backups/', keep_count=10)

# Verify integrity
verify_result = service.verify_backup('backups/backup_20260127_143052.db')
```

### Test Coverage
- **Unit Tests:** 9/9 passing
  - Initialization
  - Successful backup
  - File exists error
  - Timestamped backup
  - List backups (empty and populated)
  - Delete old backups
  - Verify backup (valid and not found)

---

## 2. RestoreService

**File:** `services/tools/restore_service.py` (368 lines)

### Features Implemented

#### Restore Modes

**1. REPLACE Mode (Full Replacement)**
- Complete database replacement
- Destructive: Closes current connection, replaces file, reopens
- Use case: Clean slate restore, undo all changes
- **Note:** UI must handle connection closure/reopening

**2. MERGE_ALL Mode (Merge All Tables)**
- Merge all tables from backup into current database
- Uses `INSERT OR IGNORE` to skip duplicates
- Preserves existing data not in backup
- Use case: Combine data from multiple sources

**3. MERGE_SELECTED Mode (Selective Merge)**
- Merge only specified tables
- Same INSERT OR IGNORE strategy
- Requires `tables` parameter
- Use case: Restore specific data (e.g., only purchases)

#### Core Operations
- **`restore_database()`** - Main entry point with mode selection
  - Validates backup file exists
  - Verifies backup integrity before restore
  - Returns RestoreResult with records_restored and tables_affected
  
- **`_verify_backup_integrity()`** - Pre-restore validation
  - PRAGMA integrity_check on backup file
  - Prevents restoring corrupted backups
  
- **`_get_table_list()`** - List all user tables
  - Excludes system tables (sqlite_*)
  - Used for MERGE_ALL mode

### API Example
```python
from services.tools import RestoreService, RestoreMode

service = RestoreService(db_connection)

# Full replacement (destructive)
result = service.restore_database(
    'backups/backup_20260127_143052.db',
    mode=RestoreMode.REPLACE
)

# Merge all tables (non-destructive)
result = service.restore_database(
    'backups/backup_20260127_143052.db',
    mode=RestoreMode.MERGE_ALL
)

# Merge specific tables only
result = service.restore_database(
    'backups/backup_20260127_143052.db',
    mode=RestoreMode.MERGE_SELECTED,
    tables=['purchases', 'redemptions']
)

if result.success:
    print(f"Restored {result.records_restored} records")
    print(f"Tables affected: {', '.join(result.tables_affected)}")
```

### Test Coverage
- **Unit Tests:** 3/3 passing
  - Initialization
  - Backup not found error
  - MERGE_SELECTED requires tables list validation

- **Integration Tests:** 3/3 passing
  - Full replace restore workflow
  - Merge all restore workflow
  - Selective merge restore workflow

---

## 3. ResetService

**File:** `services/tools/reset_service.py` (285 lines)

### Features Implemented

#### Table Classifications

**SETUP_TABLES** (Reference Data):
- `users`
- `sites`
- `cards`
- `redemption_methods`
- `game_types`
- `games`

**TRANSACTION_TABLES** (Transactional Data):
- `purchases`
- `redemptions`
- `game_sessions`
- `daily_sessions`
- `expenses`

#### Core Operations

- **`reset_database()`** - Main reset with options
  - `keep_setup_data=True` - Preserves SETUP_TABLES, clears TRANSACTION_TABLES
  - `keep_setup_data=False` - Clears all tables
  - `keep_audit_log=True` - Excludes audit_log table (optional)
  - Uses PRAGMA foreign_keys OFF/ON for safe deletion
  - Resets autoincrement counters via sqlite_sequence
  
- **`reset_transaction_data_only()`** - Convenience method
  - Equivalent to `reset_database(keep_setup_data=True)`
  - Common use case: Reset transactions but keep users/sites
  
- **`reset_table()`** - Reset single table
  - Deletes all rows from specified table
  - Resets autoincrement counter
  - Returns ResetResult with records_deleted
  
- **`get_table_counts()`** - Current record counts
  - Returns dict: `{table_name: record_count}`
  - Useful for UI display and validation
  
- **`preview_reset()`** - Show what will be deleted
  - Lists tables to be cleared
  - Shows current record counts
  - Total records to be deleted
  - **Does not modify data** - safe preview

---

(Archived status snapshot preserved from root-level doc.)
