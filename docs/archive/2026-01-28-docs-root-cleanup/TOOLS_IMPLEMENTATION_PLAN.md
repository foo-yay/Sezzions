# Tools Implementation Plan - Sezzions OOP Architecture

**Document Version:** 1.3  
**Date:** January 27, 2026 (Updated: January 28, 2026)  
**Status:** Phase 4 complete; Phase 2 complete; Phase 3 UI mostly shipped (follow-ups remaining)

---

## Implementation Status Summary

### ✅ Phase 1: Foundation (COMPLETE)
- ✅ Tools DTOs, enums, schemas: `services/tools/dtos.py`, `services/tools/enums.py`, `services/tools/schemas.py`
- ✅ FK resolution + CSV parsing utilities: `services/tools/fk_resolver.py`, `services/tools/csv_utils.py`
- ✅ Validation framework + entity validators: `services/tools/validators/*`
- ✅ Schema registry covers: purchases, redemptions, game_sessions, users, sites, cards, redemption_methods, redemption_method_types, game_types, games
- ✅ Settings persistence hardening for Tools: JSON-backed UI settings are stable for Tools workflows (flush/fsync; reload-before-partial-write pattern)
- ⏳ Settings storage strategy documentation: still needs a clear “JSON vs DB settings table” ownership list (explicit per-key ownership)

### ✅ Phase 2: CSV Import/Export (FUNCTIONALLY COMPLETE; OPTIONAL POLISH)
- ✅ Backend import/export: `services/tools/csv_import_service.py`, `services/tools/csv_export_service.py`
- ✅ Templates generated from schema definitions
- ✅ UI integrated in Tools tab:
    - Import preview dialog (adds/updates/conflicts/duplicates/errors)
    - Import execute with conflict strategy (skip vs overwrite)
    - Export single entity, Export All (ZIP), Template download (single + ZIP)
- ⏳ Optional polish:
    - Run import/export in a background worker for very large files (avoid UI blocking)
    - Add progress reporting for long exports/imports (if needed)
    - After CSV import: trigger a cross-tab refresh (or provide a one-click “Reload Data” action) so users don’t need to restart

### ✅/⏳ Phase 3: Database Tools (SHIPPED; IMPORTANT FOLLOW-UPS REMAIN)

**Backend (COMPLETE):**
- ✅ Services exist and are tested:
    - `services/tools/backup_service.py`
    - `services/tools/restore_service.py`
    - `services/tools/reset_service.py`
- ✅ Audit logging for database tools operations (backup/restore/reset) via `DatabaseManager.log_audit()`
- ✅ Transaction-safe primitives for bulk operations (e.g., `execute_no_commit`, `executemany_no_commit`) used by restore/reset workflows

**UI (MOSTLY SHIPPED):**
- ✅ Tools tab exposes:
    - Manual backup (directory picker + “Backup Now”)
    - Automatic backup scheduling (enable + cadence + last backup time; periodic checks)
    - Restore UI and Reset UI dialogs with safety confirmations

**Follow-ups (recommended next work):**
- ⏳ Move DB backup/restore/reset execution off the UI thread (use the same worker pattern as recalculation)
    - Requirement: worker must open its own SQLite connection (never share UI thread connection)
    - Show progress and allow cancel where safe (no partial commits)
- ⏳ Implement “Merge Selected” restore (user chooses specific tables/entities to merge)
    - Must define deterministic merge order and FK-safe constraints
    - Must be transaction-atomic (all-or-nothing)
- ⏳ Replace restore UX + lifecycle: support full in-app refresh after restore/reset/import
    - Goal: avoid forcing a full app restart after database-changing operations
    - Likely needs a shared “data changed” signal/event and per-tab reload hooks
- ⏳ Centralize Tools operations behind `AppFacade` (UI should call facade/services, not assemble workflows directly)
- ⏳ Add “backup-before-destructive” prompts in other destructive flows (ties into Phase 5 notifications)

### ✅ Phase 4: Recalculation Engine (6/6 COMPLETE)
**Backend (COMPLETE - 20 tests):**
- ✅ RecalculationService with FIFO + session recalculation
- ✅ Progress callbacks (2 steps per pair)
- ✅ Transaction-safe operations
- ✅ Scoped recalculation support
- ✅ RebuildResult DTO with statistics
- ✅ GameSessionService integration (lazy-loaded)

**UI Integration (6/6 COMPLETE):**
- ✅ Task 1: Transaction API to DatabaseManager (already existed)
- ✅ Task 2: Qt background workers (RecalculationWorker + WorkerSignals)
- ✅ Task 3: Progress dialogs (ProgressDialog hierarchy)
- ✅ Task 4: Tools tab buttons (Recalculate Everything + scoped)
- ✅ Task 5: Post-import recalculation prompts (PostImportPromptDialog)
- ✅ Task 6: End-to-end testing (COMPLETE - all tests passed, zero failures)

**Files Created/Modified:**
- `ui/tools_workers.py` (183 lines) - Background workers
- `ui/tools_dialogs.py` (267 + 50 lines) - Progress/Result/Prompt dialogs
- `ui/tabs/tools_tab.py` (365 + 60 lines) - Recalculation UI
- `ui/main_window.py` (modified) - Tools tab integration
- `services/tools/dtos.py` (modified) - Added affected_user_ids/site_ids
- `services/tools/csv_import_service.py` (modified) - Track affected IDs

**Documentation:**
- `docs/POST_IMPORT_RECALC_IMPLEMENTATION.md` - Implementation details
- `docs/PHASE4_TESTING_GUIDE.md` - Comprehensive test scenarios
- `docs/PHASE4_MANUAL_TEST_CHECKLIST.md` - Manual testing completed (9/9 tests passed)

**Completion Date:** January 28, 2026

### 🔜 Next: Phase 3 UI + Phase 5 Notifications
**Why Phase 3 UI next:**
 - The core backup/restore/reset UI is now available, but there are follow-ups to make it non-blocking, more powerful (selective merge), and refresh-friendly.
 - Notifications become substantially more useful once “backup due” can drive users to the tools.

**After Phase 3 UI:** Phase 5 (Notifications), then Audit Log UI (if desired).

### ✅/⏳ What’s Left (Functional)
- ✅ Tools → Database Tools UI (backup/restore/reset) exists
- ⏳ Tools → Database Tools worker-thread execution + progress/cancel
- ⏳ Tools → Restore “Merge Selected”
- ⏳ Global refresh mechanism after database-changing operations (restore/reset/import)
- ⏳ “Backup-before-destructive-ops” prompting (sessions/redemptions/purchases deletes) once backups are exposed
- ⏳ Notification system (backup due reminders + badge/panel)
- ⏳ Audit logging integration (record CRUD/import/reset/restore events) + viewer/export UI
- ⏳ (Optional) CSV import/export background workers + progress for huge datasets

---

## Executive Summary

This document outlines the comprehensive implementation strategy for migrating and enhancing the Tools/Setup functionality from the legacy `qt_app.py` to the new OOP architecture in `/sezzions`. The plan addresses CSV import/export, data validation, database tools, notifications, audit logging, and UI integration with consideration for future web/mobile deployment.

---

## Table of Contents

1. [Legacy Feature Analysis](#1-legacy-feature-analysis)
2. [Architecture Strategy](#2-architecture-strategy)
3. [Data Validation Framework](#3-data-validation-framework)
4. [CSV Import/Export System](#4-csv-importexport-system)
5. [Database Tools](#5-database-tools)
6. [Recalculation Engine](#6-recalculation-engine)
7. [Notification System](#7-notification-system)
8. [Audit Logging](#8-audit-logging)
9. [UI Integration](#9-ui-integration)
10. [Implementation Phases](#10-implementation-phases)
11. [Testing Strategy](#11-testing-strategy)
12. [Future Considerations](#12-future-considerations)

---

## 1. Legacy Feature Analysis

### 1.1 Current Tools Tab Structure (qt_app.py)

The legacy implementation provides a collapsible Tools tab within Setup containing:

**CSV Operations:**
- Upload CSV for 10 entity types (Purchases, Sessions, Redemptions, Expenses, Users, Sites, Cards, Redemption Methods, Game Types, Games)
- Download CSV templates (human-editable with examples)
- Export data as CSV (full data backup capability)

**Data Recalculation:**
- Recalculate Everything (full rebuild)
- Recalculate Session Data only
- Recalculate FIFO (Redemptions) only
- Recalculate RTP (planned but not implemented)
- No scoped recalculation by Site/User pair (planned enhancement)

**Database Tools:**
- Backup Settings:
  - Choose backup folder
  - Backup Now button
  - Auto-backup toggle with interval (days)
  - Last backup timestamp display
  - Next backup due date
- Database Reset:
  - Full reset with optional "keep setup data" toggle
  - Confirmation dialog with warning

**Audit Log:**
- View audit log in dialog
- Export audit log to CSV
- Auto-backup audit log (configurable interval)
- Clear old records (retention policy)
- Tracks: timestamp, action, table, record_id, details, user_name

**Notifications:**
- Bell icon with badge count
- Backup due notifications (popup + persistent badge)
- Hourly background check for backup due status
- Dismissible notifications

### 1.2 CSV Import Features

**Current Capabilities:**
- Dynamic schema detection via `PRAGMA table_info`
- Foreign key resolution (e.g., "User Name" → user_id)
- Duplicate detection (exact match vs conflict)
- Within-file duplicate detection
- Validation before commit (all-or-nothing transaction)
- Preview dialog showing adds/conflicts/errors
- Choice: Clear existing data vs append
- Chronological sorting for transactions
- Auto-default calculated fields (remaining_amount, status, etc.)
- Business rule validation (date ranges, fee limits, etc.)
- Post-import recalculation prompts

**Validation Rules:**
- Required fields check
- Foreign key existence check
- Date format parsing (store as YYYY-MM-DD; optionally accept MM/DD/YY and normalize during import)
- Time format parsing (HH:MM or HH:MM:SS)
- Numeric field parsing (currency symbols stripped)
- Boolean parsing (1/0, true/false, yes/no, active/inactive)
- Business logic:
  - Redemption date ≤ receipt date
  - Dates not in future
  - Fees ≤ redemption amount
  - Session end_datetime ≥ start_datetime

**Duplicate Handling:**
- Exact duplicate: identical values on all columns → skip
- Conflict: same unique key, different values → user choice (skip/overwrite)
- CSV duplicates: same key appears twice in uploaded file → flag error

### 1.3 Export Features

**CSV Export Format:**
- Human-readable column names (e.g., "Site Name" not "site_id")
- Foreign keys exported as names (auto-resolved on import)
- Timestamps with default formatting
- Currency with `$` symbol (stripped on import)
- Boolean as 1/0 or active/inactive
- All user-editable fields included
- Calculated fields EXCLUDED (will be recomputed)
- Filename: `{entity}_{timestamp}.csv`

**Template Downloads:**
- Same structure as export but with example rows
- Commented instructions in first row (optional)
- All required fields present
- Foreign key examples show valid names

### 1.4 Parity Findings, Conflicts, and Mitigations (Legacy vs Sezzions)

This section captures the *important behavioral nuances* found in the legacy Tools implementation and the key Sezzions-specific constraints that can create reliability issues if not explicitly designed around.

**CSV import: strict atomicity vs “skip invalid rows” legacy flow**
- Legacy UX can allow the user to proceed by skipping problematic rows.
- Sezzions plan goal (“error-proof”) prefers strict all-or-nothing behavior by default.
- **Mitigation / design decision:** support two explicit modes:
    - **Strict mode (default):** any validation error blocks import.
    - **Permissive mode (explicit opt-in):** user can exclude invalid rows (and optionally warnings) during preview; the *final chosen import set* still commits atomically in one transaction.

**Transaction atomicity vs current Sezzions DB API**
- In Sezzions today, `DatabaseManager.execute()` commits each statement.
- This undermines “single transaction” imports/resets/merges if those operations use `execute()` internally.
- **Mitigation / design decision:** implement a transaction-safe bulk-write path for Tools operations:
    - Add a transaction context manager (e.g., `DatabaseManager.transaction()`), and
    - Add commit-control methods (e.g., `execute_no_commit` / `executemany_no_commit`) or a dedicated bulk repository that uses the underlying connection and commits once.

**Threading & SQLite connection safety**
- Tools work (import/recalc/restore/merge) must run off the UI thread.
- SQLite connections are not safe to share across threads.
- **Mitigation / design decision:** background workers must open their own SQLite connection (same DB file), and long-running write operations should acquire a service-level “exclusive tools operation” lock that temporarily disables UI writes.

**Settings persistence: DB `settings` table exists but JSON is preferred**
- Legacy stored auto-backup/audit settings in the database `settings` table.
- Sezzions already has JSON-backed UI settings (`sezzions/ui/settings.py`) and a DB `settings` table.
- **Mitigation / design decision:**
    - Keep **UI/operational preferences** (backup folder, auto-backup cadence, notification thresholds, UI defaults) in JSON.
    - Use the DB `settings` table only for settings that must *travel with the database file* (explicitly documented per-key).

**Backup/restore parity and reliability**
- Legacy backups use raw file copy; this can be inconsistent if copied while the DB is being written.
- **Mitigation / design decision:** prefer SQLite online backup (`sqlite3.Connection.backup`) for both manual and automatic backups.
- Restore (REPLACE) while the app is running must be treated as an exclusive operation:
    - Pause/disable UI writes, perform restore, then force a full UI refresh and run validation + (optionally) full recalculation.

**Selective restore / “merge selected data”**
- Legacy primarily supports full DB replace.
- New requirement includes restoring selected subsets.
- **Mitigation / design decision:** define restore modes up-front (REPLACE, MERGE_ALL, MERGE_SELECTED) with clear selection semantics (entity/table selection, site/user scope, date range) and deterministic FK-safe import ordering.

---

## 2. Architecture Strategy

### 2.1 Service Layer Design

Create new service classes in `/sezzions/services/`.

Important: Sezzions already has an `AppFacade` and several services (validation, recalculation, reporting, CRUD services). The Tools work should **reuse existing public methods** wherever possible (especially via `AppFacade`) and only add new services for net-new behavior (CSV import orchestration, backup/restore, notifications UI, audit log viewer/export).

```
sezzions/services/
  ├── tools/
  │   ├── __init__.py
  │   ├── csv_service.py         # CSV import/export orchestration
    │   ├── validation_adapters.py # Optional: Tools-specific validation/report formatting that calls existing ValidationService
    │   ├── recalc_adapters.py     # Optional: Tools-specific progress/cancellation wrapper around existing RecalculationService
  │   ├── backup_service.py      # Database backup/restore
  │   └── audit_service.py       # Audit logging
```

**Key Principles:**
- **Separation of Concerns:** Each service handles one domain
- **No UI SQL:** UI code never touches SQL or sqlite cursors
- **Reuse Before Build:** Prefer calling existing `AppFacade` methods and existing services; avoid duplicating validation and recalculation logic
- **DB Access Boundary:** Prefer repositories/services for data access; if bulk operations require SQL for performance/correctness, keep it inside a dedicated service/repository (never scattered across UI)
- **Transaction Safety:** Imports/resets wrap in database transactions (see “All-or-Nothing Imports” below)
- **Event-Driven:** Services emit events for audit logging
- **Testable:** Pure business logic, mockable dependencies

### 2.1.1 Current Sezzions Integration Reality (Recommended)

Sezzions already exposes Tools-relevant capabilities via the app stack:

- **Validation** already exists (Tools should call it, not re-implement it).
- **Recalculate Everything** already exists and is reachable from the UI (Tools tab should call the same operation).
- **Export CSV** already exists in several tabs (Tools tab can provide a centralized “Export” experience by calling those shared helpers or by implementing a single export service used by all tabs).

**Recommendation:** treat `AppFacade` as the public API for Tools UI. New Tools services should be injected into / composed by the facade (or called by it), rather than being called directly from UI widgets.

### 2.1.2 DB Access Strategy (Separation Without Paralysis)

To keep OOP boundaries clean while still supporting complex/bulk operations:

- **UI layer:** no SQL, no sqlite connections, no cursor usage.
- **Service layer:** prefers repositories; orchestrates workflows; owns transactions and progress reporting.
- **Repository layer:** owns SQL.
- **Bulk operations:** if some workflows need non-trivial SQL (CSV merge, scoped rebuild), implement them in a dedicated repository (e.g., `BulkAccountingRepository`) rather than embedding cursor logic throughout multiple services.

This preserves the separation you want (no “direct DB access” from UI/business workflows) without blocking correctness/performance work.

### 2.2 Data Transfer Objects (DTOs)

Create DTOs for structured data passing:

```python
# sezzions/services/tools/dtos.py

@dataclass
class ImportResult:
    """Result of CSV import operation"""
    success: bool
    records_added: int
    records_updated: int
    records_skipped: int
    errors: List[str]
    warnings: List[str]

@dataclass
class ValidationError:
    """Single validation error"""
    row_number: int
    field: str
    value: Any
    message: str

@dataclass
class ImportPreview:
    """Preview before confirming import"""
    to_add: List[Dict]
    to_update: List[Dict]
    exact_duplicates: List[Dict]
    conflicts: List[Dict]
    invalid_rows: List[ValidationError]
    csv_duplicates: List[Dict]
```

### 2.3 Validation Framework

**Strategy:** Pluggable validators per entity type

```python
# sezzions/services/tools/validators/base.py

class BaseValidator(ABC):
    """Base class for entity validators"""
    
    @abstractmethod
    def validate_record(self, record: Dict, context: ValidationContext) -> List[ValidationError]:
        """Validate a single record"""
        pass
    
    @abstractmethod
    def validate_batch(self, records: List[Dict]) -> List[ValidationError]:
        """Cross-record validation (e.g., within-file duplicates)"""
        pass

# sezzions/services/tools/validators/purchase_validator.py

class PurchaseValidator(BaseValidator):
    def validate_record(self, record, context):
        errors = []
        
        # Required fields
        if not record.get('amount'):
            errors.append(ValidationError(context.row_num, 'amount', None, 'Required'))
        
        # Amount validation
        if record.get('amount', 0) <= 0:
            errors.append(ValidationError(context.row_num, 'amount', record['amount'], 'Must be positive'))
        
        # Date validation
        if record.get('purchase_date'):
            if parse_date(record['purchase_date']) > date.today():
                errors.append(ValidationError(context.row_num, 'purchase_date', record['purchase_date'], 'Cannot be in future'))
        
        return errors
```

### 2.4 Foreign Key Resolution Strategy

**Problem:** User uploads CSV with "Steve" but database has two users named Steve.

**Solutions:**

**Option 1: Unique Constraint (RECOMMENDED)**
- Enforce unique constraint on human-readable names (sites.name, users.name, etc.)
- At insert time, reject duplicate names
- CSV import fails with clear error: "User 'Steve' is ambiguous - found 2 matches"
- User must rename one Steve in database (e.g., "Steve (Carolina)", "Steve (Florida)")

**Option 2: Composite Key Resolution**
- CSV includes multiple fields for disambiguation
- Example: `User Name` + `User Email` or `User Name` + `User ID`
- Requires more complex CSV format
- Error-prone for manual editing

**Option 3: ID Override Column**
- CSV has optional `User ID` column
- If present and valid, use it; otherwise resolve by name
- Allows power users to be explicit
- Still fails if name doesn't match ID

**Recommendation:** Option 1 + Option 3, with sensible per-entity uniqueness rules.

#### 2.4.1 Unique Names Policy (Human + CSV Friendly)

We should enforce unique names for setup entities because it’s confusing for humans and makes CSV name-based FK resolution unreliable.

**Strongly recommended unique globally:**
- Users
- Sites
- Redemption Method Types
- Redemption Methods
- Game Types

**Cards and Games:** unique names are still recommended, but there are two workable options:
- **Option A (simplest user experience):** enforce *global* uniqueness for Card names and Game names.
- **Option B (more flexible schema):** enforce *scoped* uniqueness:
    - Cards unique per user (user_id + card_name)
    - Games unique per game type (game_type_id + game_name)

Given your preference (“there shouldn’t be two users named Steve …”), **Option A is acceptable** and keeps CSV templates simpler. If we later discover real-world friction (e.g., many games share a name across types), Option B is the escape hatch.

**CSV behavior:**
- Default: resolve FK by unique name.
- Power-user override: optional `... ID` column, which must match the name if both are provided.

**Migration note:** adding uniqueness constraints to an existing DB requires a preflight check and a clear error path for duplicates.

### 2.5 CSV Schema Definitions

**Location:** `sezzions/services/tools/schemas.py`

```python
@dataclass
class CSVFieldDef:
    """Definition of a CSV column"""
    db_column: str          # Database column name
    csv_header: str         # Human-readable CSV header
    field_type: FieldType   # (TEXT, INTEGER, DECIMAL, DATE, TIME, BOOLEAN, FOREIGN_KEY)
    required: bool
    foreign_key: Optional[ForeignKeyDef] = None
    validator: Optional[Callable] = None
    default_value: Optional[Any] = None
    export_formatter: Optional[Callable] = None

@dataclass
class EntitySchema:
    """Complete schema for an entity's CSV import/export"""
    table_name: str
    display_name: str
    unique_columns: Tuple[str, ...]  # Columns that define uniqueness
    fields: List[CSVFieldDef]
    post_import_hook: Optional[Callable] = None  # e.g., trigger recalculation
    
# Example: Purchase Schema
PURCHASE_SCHEMA = EntitySchema(
    table_name='purchases',
    display_name='Purchases',
    unique_columns=('user_id', 'site_id', 'purchase_date', 'purchase_time'),
    fields=[
        CSVFieldDef('user_id', 'User Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('users', 'id', 'name')),
        CSVFieldDef('site_id', 'Site Name', FieldType.FOREIGN_KEY, required=True,
                    foreign_key=ForeignKeyDef('sites', 'id', 'name')),
        CSVFieldDef('purchase_date', 'Purchase Date', FieldType.DATE, required=True),
        CSVFieldDef('purchase_time', 'Purchase Time', FieldType.TIME, required=False, default_value='00:00:00'),
        CSVFieldDef('amount', 'Amount', FieldType.DECIMAL, required=True,
                    validator=lambda x: x > 0),
        CSVFieldDef('sc_received', 'SC Received', FieldType.DECIMAL, required=True),
        CSVFieldDef('starting_sc_balance', 'Post-Purchase SC', FieldType.DECIMAL, required=False),
        CSVFieldDef('cashback_earned', 'Cashback Earned', FieldType.DECIMAL, required=False, default_value=0),
        CSVFieldDef('card_id', 'Card Name', FieldType.FOREIGN_KEY, required=False,
                    foreign_key=ForeignKeyDef('cards', 'id', 'name')),
        CSVFieldDef('notes', 'Notes', FieldType.TEXT, required=False),
    ],
    # Post-import actions should be orchestrated by the Tools workflow (UI + facade),
    # not by referencing a global service inside the schema module.
    # Example: after importing Purchases/Redemptions/Sessions, prompt the user to run
    # Tools → Recalculate Everything (or auto-run if they opted in).
    post_import_hook=PostImportHook.PROMPT_RECALCULATE_EVERYTHING
)
```

---

## 3. Data Validation Framework

### 3.1 Validation Layers

**Layer 1: Field-Level Validation**
- Data type checks (is it a valid date/number/etc.?)
- Range checks (amount > 0, date not in future)
- Format validation (time HH:MM:SS)

**Layer 2: Record-Level Validation**
- Required fields present
- Foreign key resolution
- Business rules (receipt_date >= redemption_date)

**Layer 3: Batch-Level Validation**
- Within-file duplicate detection
- Cross-record dependencies
- Chronological ordering requirements

**Layer 4: Database-Level Validation**
- Uniqueness constraints
- Referential integrity
- Transaction-level consistency

### 3.2 Validation Context

```python
@dataclass
class ValidationContext:
    """Context for validation operations"""
    row_number: int
    entity_type: str
    existing_data: Dict[str, Any]  # Cache of foreign key lookups
    strict_mode: bool = True       # Fail on warnings vs allow with warning
    date_cutoff: Optional[date] = None  # For chronological checks
```

### 3.3 Business Rule Validators

**Purchases:**
- `amount > 0`
- `sc_received >= 0`
- `starting_sc_balance >= sc_received` (if provided)
- `purchase_date <= today`
- `cashback_earned >= 0`

**Redemptions:**
- `amount > 0`
- `fees >= 0`
- `fees <= amount`
- `redemption_date <= today`
- `receipt_date >= redemption_date` (if both provided)
- `dollar_value = amount - fees`

**Game Sessions:**
- `session_date <= today`
- `ending_sc_balance >= 0`
- `starting_sc_balance >= 0`
- If closed: `end_date >= session_date`
- If closed and same-day: `end_time > start_time`
- `purchases_during >= 0`
- `redemptions_during >= 0`

**Expenses:**
- `amount > 0`
- `expense_date <= today`

### 3.4 Error Severity Levels

```python
class ValidationSeverity(Enum):
    ERROR = "error"      # Block import
    WARNING = "warning"  # Allow with confirmation
    INFO = "info"        # Show but don't block
```

---

## 4. CSV Import/Export System

### 4.0 All-or-Nothing Imports (What this means and why it matters)

“All-or-nothing import transaction” means: either the final, user-approved import set commits successfully, or **none** of it is applied.

This is especially important here because partial imports can leave the database in a misleading state:
- imported purchases without imported sessions/redemptions,
- FIFO allocations/recalculated fields out of sync,
- “half-updated” setup records breaking FK resolution.

**Legacy parity note:** legacy Tools can offer “skip invalid rows and proceed.” That can still be compatible with an atomic commit: the user can choose to *exclude* invalid rows during preview (permissive mode), and the remaining rows are committed in one transaction.

**Recommendation:**
- Preview/validate without writing anything.
- On user confirmation, run the import in a single DB transaction.
- If any write fails, rollback and surface a clear error.

**Implementation constraint to plan for:** if the data layer auto-commits per statement (as Sezzions `DatabaseManager.execute()` currently does), the import will *not* be atomic. Therefore, Tools import needs either:
- a transaction-aware repository layer (preferred), or
- a dedicated import writer that executes batched writes using the underlying connection and commits once.

### 4.0.1 DB Transaction API Checklist (Implementation-Ready)

This section turns the atomicity requirement into concrete implementation tasks so there’s no ambiguity when building Tools.

**Goal:** make it *impossible* for a Tools bulk operation (import/reset/restore/merge-selected) to partially commit due to per-statement auto-commit.

**Current constraint:** `DatabaseManager.execute()` commits on every call.

**Recommended approach (minimal disruption):** keep `execute()` as-is for convenience in normal CRUD, but add explicit transaction-safe primitives for bulk operations.

**A) Add an explicit transaction context manager**

In `sezzions/repositories/database.py` (or a small helper module nearby), add:

```python
from contextlib import contextmanager

@contextmanager
def transaction(self):
        """Run multiple statements atomically.

        NOTE: Only safe if the statements executed inside do not auto-commit.
        Tools bulk operations must use *_no_commit methods or direct-connection bulk writer.
        """
        self.begin_transaction()
        try:
                yield
                self.commit()
                self._notify_change()
        except Exception:
                self.rollback()
                raise
```

**B) Add no-auto-commit execution methods for bulk writers**

Add either (choose one style; do not mix casually):

**Option 1 (explicit new methods):**
```python
def execute_no_commit(self, query: str, params: tuple = ()) -> int:
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid

def executemany_no_commit(self, query: str, params_seq: list[tuple]) -> None:
        cursor = self._connection.cursor()
        cursor.executemany(query, params_seq)
```

**Option 2 (parameterized commit control):**
```python
def execute(self, query: str, params: tuple = (), *, commit: bool = True) -> int:
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        if commit:
                self._connection.commit()
                self._notify_change()
        return cursor.lastrowid
```

**Recommendation:** Option 1 is harder to misuse (Tools code will visibly choose no-commit).

**C) Provide a dedicated bulk writer/repository for Tools**

To keep “no UI SQL” intact while also avoiding scattered raw-SQL calls:

- Create `sezzions/repositories/bulk_tools_repository.py` (or similar), owning:
    - bulk deletes for reset
    - merge-from-backup logic (MERGE_ALL / MERGE_SELECTED)
    - import writes for CSV (insert/update)

This repository should:
- use only parameterized SQL (no string interpolation from user input)
- operate inside `db.transaction()`
- use `*_no_commit` methods (or direct connection cursor) and commit once

**D) Threading rule (must be enforced in code, not just policy)**

Because Tools runs off the UI thread:
- the worker thread should open its own `DatabaseManager` (or raw `sqlite3.connect`) pointing at the same DB file
- never share the UI thread’s SQLite connection across threads

**E) What “atomic” means for each Tools operation**

- **CSV import (any entity):**
    - preview/validation: no writes
    - commit phase: one transaction; rollback on any error
- **Reset DB:**
    - one transaction; rollback if any table clear fails
- **Restore MERGE_ALL / MERGE_SELECTED:**
    - one transaction; rollback if any FK/unique constraint fails
- **Restore REPLACE:**
    - treated as an exclusive operation; after restore, run validation and (optionally) a full rebuild

**F) Tests to add (so this never regresses)**

- Verify `execute()` auto-commits does *not* get used by Tools bulk flows (unit tests can patch/spy on it)
- Failure injection: raise an exception mid-import and assert no rows were inserted
- Failure injection: raise an exception mid-merge-selected and assert no rows were merged

### 4.1 Import Workflow

```
┌─────────────────────┐
│ User uploads CSV    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Parse CSV headers   │
│ Validate structure  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Load foreign key    │
│ lookup tables       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Parse each row      │
│ - Resolve FKs       │
│ - Validate fields   │
│ - Apply defaults    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Detect duplicates   │
│ - Exact matches     │
│ - Conflicts         │
│ - CSV duplicates    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Show preview dialog │
│ - X to add          │
│ - Y conflicts       │
│ - Z errors          │
└──────────┬──────────┘
           │
       User confirms?
           │
     ┌─────┴─────┐
     │ No        │ Yes
     ▼           ▼
  Cancel   ┌──────────────┐
           │ Begin txn    │
           │ Insert/Update│
           │ Commit       │
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │ Audit log    │
           │ entries      │
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │ Trigger post-│
           │ import hook  │
           │ (recalc)     │
           └──────┬───────┘
                  │
                  ▼
           ┌──────────────┐
           │ Show success │
           │ summary      │
           └──────────────┘
```

### 4.2 Import Service Interface

```python
class CSVImportService:
    """Service for CSV import operations"""
    
    def __init__(self, db: DatabaseManager, validation_service: ValidationService):
        self.db = db
        self.validation = validation_service
        self._repos = {}  # Cache of repository instances
    
    def import_csv(
        self,
        entity_type: str,
        file_path: str,
        clear_existing: bool = False,
        strict_mode: bool = True
    ) -> ImportResult:
        """
        Import CSV file for given entity type.
        
        Args:
            entity_type: 'purchases', 'redemptions', etc.
            file_path: Path to CSV file
            clear_existing: If True, delete existing records before import
            strict_mode: If True, fail on warnings; if False, allow with confirmation
        
        Returns:
            ImportResult with counts and errors
        
        Raises:
            ValidationException: If critical errors prevent import
        """
        schema = self._get_schema(entity_type)
        
        # Parse CSV
        rows = self._parse_csv(file_path, schema)
        
        # Load FK lookup tables
        fk_cache = self._load_foreign_key_cache(schema)
        
        # Validate and resolve
        preview = self._validate_and_preview(rows, schema, fk_cache, strict_mode)
        
        # If errors, return early
        if preview.invalid_rows and strict_mode:
            return ImportResult(
                success=False,
                records_added=0,
                records_updated=0,
                records_skipped=len(preview.exact_duplicates),
                errors=[f"Row {e.row_number}: {e.message}" for e in preview.invalid_rows],
                warnings=[]
            )
        
        # User confirms via dialog (handled by UI layer)
        # ...
        
        # Execute import in a single transaction (all-or-nothing)
        result = self._execute_import(entity_type, preview, clear_existing)
        
        # Post-import hook (e.g., recalculate)
        if schema.post_import_hook and result.success:
            schema.post_import_hook()
        
        return result
    
    def _validate_and_preview(self, rows, schema, fk_cache, strict_mode):
        """Validate rows and generate preview"""
        to_add = []
        conflicts = []
        exact_duplicates = []
        invalid_rows = []
        csv_duplicates = []
        
        seen_in_csv = {}
        existing_records = self._load_existing_records(schema)
        
        for row_idx, csv_row in enumerate(rows, start=2):
            # Validate and transform row
            record, errors = self._process_row(csv_row, schema, fk_cache, row_idx)
            
            if errors:
                invalid_rows.extend(errors)
                continue
            
            # Check for CSV duplicates
            unique_key = self._make_unique_key(record, schema.unique_columns)
            if unique_key in seen_in_csv:
                csv_duplicates.append({'row': row_idx, 'record': record})
                continue
            seen_in_csv[unique_key] = row_idx
            
            # Check against existing records
            if unique_key in existing_records:
                if self._is_exact_match(record, existing_records[unique_key]):
                    exact_duplicates.append(record)
                else:
                    conflicts.append({
                        'new': record,
                        'existing': existing_records[unique_key]
                    })

            else:
                to_add.append(record)

        return ImportPreview(
            to_add=to_add,
            to_update=[],  # Conflicts that user chose to overwrite
            exact_duplicates=exact_duplicates,
            conflicts=conflicts,
            invalid_rows=invalid_rows,
            csv_duplicates=csv_duplicates,
        )

```

```python
def _sort_records_chronologically(records, date_field, time_field=''):
    """Sort records by date (and optionally time)"""
    def sort_key(record):
        date_val = record.get(date_field)
        time_val = record.get(time_field, '00:00:00') if time_field else '00:00:00'
        
        # Combine date and time for sorting
        dt_str = f"{date_val} {time_val}"
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.min  # Put invalid dates first to catch errors
    
    return sorted(records, key=sort_key)
```

---

## 5. Database Tools

### 5.1 Backup Service

```python
class BackupService:
    """Service for database backup/restore operations"""
    
    def backup_database(
        self,
        backup_path: str,
        include_audit_log: bool = True
    ) -> BackupResult:
        """
        Create full database backup.
        
        Args:
            backup_path: Destination file path
            include_audit_log: Whether to include audit log table
        
        Returns:
            BackupResult with status and file info
        """
        try:
            # Prefer SQLite online backup API so we do NOT have to close connections.
            # This supports taking consistent backups while the app is running.
            #
            # Example:
            #   src_conn = self.db._connection
            #   dest_conn = sqlite3.connect(backup_path)
            #   src_conn.backup(dest_conn)
            #   if not include_audit_log:
            #       dest_conn.execute("DELETE FROM audit_log")
            #       dest_conn.commit()
            #   dest_conn.close()
            #
            # Fall back to file copy only if necessary (with an explicit warning),
            # since copying an open SQLite file can produce inconsistent backups.
            #
            # Note: if excluding audit log, delete it *after* the backup is created.
            
            # Update last backup timestamp (store in app settings, not in the accounting DB)
            self._update_last_backup_timestamp()
            
            return BackupResult(
                success=True,
                backup_path=backup_path,
                size_bytes=os.path.getsize(backup_path)
            )
        except Exception as e:
            return BackupResult(success=False, error=str(e))
    
    def restore_database(
        self,
        backup_path: str,
        restore_mode: RestoreMode
    ) -> RestoreResult:
        """
        Restore database from backup.
        
        Args:
            backup_path: Source backup file
            restore_mode:
                - REPLACE: full replace
                - MERGE_ALL: merge all tables (skip duplicates)
                - MERGE_SELECTED: merge a user-selected subset (entity/table + site/user/date scope)
        
        Returns:
            RestoreResult with status
        """
        # Validate backup file
        if not self._validate_backup_file(backup_path):
            return RestoreResult(success=False, error="Invalid backup file")
        
        if restore_mode == RestoreMode.REPLACE:
            # Preferred: restore into the existing live DB connection using SQLite online backup.
            # This avoids restarting the app and avoids swapping files under an open connection.
            #
            # Pseudocode:
            #   src = sqlite3.connect(backup_path)
            #   src.backup(self.db._connection)
            #   src.close()
            #
            # After restore: force a full refresh + validation + optional recalculation.
            return RestoreResult(success=True)

        elif restore_mode == RestoreMode.MERGE_ALL:
            # Merge logic: import all tables from backup, skip duplicates
            # This is essentially a CSV import from backup DB
            return self._merge_backup(backup_path)

        elif restore_mode == RestoreMode.MERGE_SELECTED:
            # Merge a subset of data (selection spec supplied by UI):
            # - allow selecting entities/tables
            # - allow scoping transactional entities by site/user and date range
            # - preserve FK integrity by importing in parent-first order
            # - run inside a single transaction (all-or-nothing)
            return self._merge_backup_selected(backup_path, selection_spec=...)
    
    def reset_database(
        self,
        keep_setup_data: bool = False
    ) -> ResetResult:
        """
        Reset database to empty state.
        
        Args:
            keep_setup_data: If True, preserve Users, Sites, Cards, Games, etc.
        
        Returns:
            ResetResult with status
        """
        # Create backup before reset
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"backup_before_reset_{timestamp}.db"
        self.backup_database(backup_path)
        
        # Reset is destructive: always prompt and always offer/perform a backup first.
        # Prefer deleting/truncating tables inside a single transaction.
        # This does not require swapping database files or resetting UI settings.

        # IMPORTANT: the data layer must support running multiple statements under one
        # transaction without auto-committing each statement.
        # Recommended approach: implement this through a dedicated bulk repository that
        # uses the underlying sqlite connection and commits once at the end.

        self.db.begin_transaction()
        try:
            if keep_setup_data:
                tables_to_clear = [
                    'purchases', 'redemptions', 'game_sessions',
                    'daily_sessions', 'expenses', 'audit_log',
                    'realized_transactions', 'redemption_allocations',
                ]
            else:
                rows = self.db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'", ())
                tables_to_clear = [
                    r["name"]
                    for r in rows
                    if ("name" in r.keys()) and r["name"] and r["name"] != "sqlite_sequence"
                ]

            for table in tables_to_clear:
                # Use the underlying connection for transactional bulk deletes
                # (DatabaseManager.execute() may auto-commit).
                self.db._connection.execute(f"DELETE FROM {table}")

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        
        return ResetResult(success=True, backup_path=backup_path)
```

### 5.2 Auto-Backup System

```python
class AutoBackupMonitor(QtCore.QObject):
    """Qt-friendly auto-backup checker.

    This is best modeled as a small UI-side coordinator:
    - uses `QTimer` (no background threads needed for the *check*)
    - reads/writes app settings (JSON)
    - when due, posts a notification that calls into BackupService
    """

    def __init__(self, backup_service: BackupService, settings: Settings, notification_service: NotificationService):
        super().__init__()
        self.backup_service = backup_service
        self.settings = settings
        self.notifications = notification_service
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(60 * 60 * 1000)  # hourly
        self._timer.timeout.connect(self._check_backup_due)

    def start(self):
        if not self.settings.get('auto_backup_enabled', False):
            return

        self._check_backup_due()
        self._timer.start()
    
    def _check_backup_due(self):
        """Check if backup is due and trigger if needed"""
        interval_days = int(self.settings.get('auto_backup_interval_days', 7))
        last_backup_str = self.settings.get('last_backup_date')
        
        if not last_backup_str:
            days_since = None
        else:
            last_backup = datetime.fromisoformat(last_backup_str)
            days_since = (datetime.now() - last_backup).days
        
        is_due = (days_since is None) or (days_since >= interval_days)
        
        if is_due:
            self._trigger_backup_notification(days_since)
    
    def _trigger_backup_notification(self, days_since):
        """Emit notification that backup is due"""
        # This will be shown via notification service
        message = (
            f"No backup has been created yet." if days_since is None
            else f"It's been {days_since} days since your last backup."
        )

        self.notifications.add_notification(
            title="Database Backup Due",
            message=message,
            notification_id="backup_due",
            severity=NotificationSeverity.WARNING,
            action_callback=self._perform_backup
        )
```

---

## 6. Recalculation Engine

### 6.1 Recalculation Service

```python
class RecalculationService:
    """Bulk rebuild operations for derived accounting data.

    In Sezzions, this already exists. Tools should call it through `AppFacade`
    and add background execution + progress UI.
    """

    def rebuild_all(self) -> RebuildResult:
        ...

    def rebuild_fifo_for_pair(self, user_id: int, site_id: int) -> RebuildResult:
        ...


# Tools/UI usage (recommended):
#   result = facade.recalculate_everything(progress_callback=..., cancel_token=...)

```

### 6.2 Background Execution (Non-UI Thread)

Recalculations must not run on the UI thread.

**Recommendation:**
- Use a Qt background worker (e.g., `QThread`/`QRunnable` + `QThreadPool`) to run:
    - full recalculation,
    - scoped recalculation,
    - large CSV imports,
    - DB restore/merge.
- Emit progress signals to a modal progress dialog.
- Provide cancellation where it’s safe (e.g., cancel before commit; cancel between scoped pair batches).

**Important:** cancellation does not mean “partial commit.” If the operation is inside a transaction, cancellation should trigger rollback.

### 6.3 Scoped Recalculation Strategy

**When to use scoped recalc:**
- User edits multiple sessions for one site/user
- User imports CSV data for one site/user
- User corrects data errors for one site/user

**When to use full recalc:**
- After bulk CSV import across multiple site/user pairs
- After database restore/merge
- After fixing systemic data issues
- When data inconsistencies are detected

**Scoped Recalc Scope:**
- Includes ALL purchases, redemptions, sessions for the pair
- Rebuilds FIFO from first purchase forward
- Recalculates all session fields
- Updates redemption tax implications

---

## 7. Notification System

### 7.1 Notification Service

```python
class NotificationSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class Notification:
    """Notification data structure"""
    id: str
    title: str
    message: str
    severity: NotificationSeverity  # INFO, WARNING, ERROR
    timestamp: datetime
    action_callback: Optional[Callable] = None
    dismissible: bool = True
    persistent: bool = False  # If True, survives app restart

class NotificationService:
    """Service for managing notifications"""
    
    def __init__(self, settings: Settings):
        # Settings are JSON-backed in Sezzions (`sezzions/ui/settings.py`).
        # Prefer settings for persistence unless we explicitly want notifications
        # to travel with the database file.
        self.settings = settings
        self._notifications: List[Notification] = []
        self._listeners: List[Callable] = []
        self._load_persistent_notifications()
    
    def add_notification(
        self,
        title: str,
        message: str,
        notification_id: str,
        severity: NotificationSeverity = NotificationSeverity.INFO,
        action_callback: Optional[Callable] = None,
        persistent: bool = False
    ):
        """Add a new notification"""
        # Check if notification already exists
        if any(n.id == notification_id for n in self._notifications):
            return
        
        notification = Notification(
            id=notification_id,
            title=title,
            message=message,
            severity=severity,
            timestamp=datetime.now(),
            action_callback=action_callback,
            persistent=persistent
        )
        
        self._notifications.append(notification)
        
        if persistent:
            self._save_persistent_notification(notification)
        
        self._notify_listeners()
    
    def dismiss_notification(self, notification_id: str):
        """Dismiss a notification"""
        self._notifications = [n for n in self._notifications if n.id != notification_id]
        self._delete_persistent_notification(notification_id)
        self._notify_listeners()
    
    def get_all(self) -> List[Notification]:
        """Get all active notifications"""
        return self._notifications.copy()
    
    def get_count(self) -> int:
        """Get count of active notifications"""
        return len(self._notifications)
    
    def subscribe(self, callback: Callable):
        """Subscribe to notification changes"""
        self._listeners.append(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of change"""
        for listener in self._listeners:
            listener(self._notifications)

    def _load_persistent_notifications(self):
        items = self.settings.get("persistent_notifications", [])
        if not isinstance(items, list):
            return

        for raw in items:
            try:
                self._notifications.append(
                    Notification(
                        id=str(raw["id"]),
                        title=str(raw["title"]),
                        message=str(raw["message"]),
                        severity=NotificationSeverity(str(raw["severity"])),
                        timestamp=datetime.fromisoformat(str(raw["timestamp"])),
                        action_callback=None,
                        dismissible=True,
                        persistent=True,
                    )
                )
            except Exception:
                # Ignore malformed entries
                continue

    def _save_persistent_notification(self, notification: Notification):
        items = self.settings.get("persistent_notifications", [])
        if not isinstance(items, list):
            items = []

        items = [x for x in items if str(x.get("id")) != notification.id]
        items.append(
            {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "severity": notification.severity.value,
                "timestamp": notification.timestamp.isoformat(),
            }
        )
        self.settings.set("persistent_notifications", items)

    def _delete_persistent_notification(self, notification_id: str):
        items = self.settings.get("persistent_notifications", [])
        if not isinstance(items, list):
            return

        items = [x for x in items if str(x.get("id")) != notification_id]
        self.settings.set("persistent_notifications", items)
```

### 7.2 Notification Types

**Backup Due:**
- Triggered by AutoBackupService
- Shown at startup if overdue
- Hourly background check
- Action: Perform backup now
- Persistent until dismissed or backup performed

**Unredeemed Balance:**
- Triggered when balance hasn't been redeemed in X days
- Configurable threshold (e.g., 90 days)
- Action: Navigate to Redemptions tab
- Non-persistent (rechecked daily)

**Pending Redemption:**
- Triggered when redemption has no receipt_date after X days
- Configurable threshold (e.g., 30 days)
- Action: Navigate to specific redemption
- Non-persistent (rechecked daily)

**Data Inconsistency:**
- Triggered by validation checks (future feature)
- Action: Open validation report
- Persistent until resolved

**Import Complete:**
- Shown after CSV import
- Summary of records added/updated/skipped
- Non-persistent (informational only)

### 7.3 UI Integration

**Notification Bell:**
- Top-right corner of main window
- Badge shows count of active notifications
- Click to open notification panel

**Notification Panel:**
- Dropdown or modal dialog
- Lists all notifications with title/message/timestamp
- Action button per notification (if applicable)
- Dismiss button per notification
- "Clear All" button

---

## 8. Audit Logging

### 8.1 Audit Service

```python
class AuditService:
    """Service for audit log management"""
    
    def __init__(self, db: DatabaseManager, settings: Settings | None = None):
        self.db = db
        self.settings = settings
        self._enabled = bool(self.settings.get("audit_enabled", True)) if self.settings else True
    
    def log_action(
        self,
        action: AuditAction,
        table_name: str,
        record_id: Optional[int] = None,
        details: Optional[str] = None,
        user_name: Optional[str] = None
    ):
        """Log an action to audit log"""
        if not self._enabled:
            return
        
        self.db.execute("""
            INSERT INTO audit_log (timestamp, action, table_name, record_id, details, user_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action.value,
            table_name,
            record_id,
            details,
            user_name or "System"
        ))
    
    def get_logs(
        self,
        limit: int = 100,
        action_filter: Optional[AuditAction] = None,
        table_filter: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict]:
        """Retrieve audit logs with filters"""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if action_filter:
            query += " AND action = ?"
            params.append(action_filter.value)
        
        if table_filter:
            query += " AND table_name = ?"
            params.append(table_filter)
        
        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        return self.db.fetch_all(query, tuple(params))
    
    def export_logs(self, output_path: str, start_date: Optional[date] = None, end_date: Optional[date] = None):
        """Export audit logs to CSV"""
        logs = self.get_logs(limit=999999, start_date=start_date, end_date=end_date)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'action', 'table_name', 'record_id', 'details', 'user_name'])
            writer.writeheader()
            writer.writerows(logs)
    
    def clear_old_logs(self, retention_days: int):
        """Delete logs older than retention period"""
        # NOTE: DatabaseManager.execute() returns lastrowid, not affected rows.
        # Use count-before/count-after for reporting.
        before = self.db.fetch_one("SELECT COUNT(*) AS c FROM audit_log", ())
        before_count = int(before["c"]) if before and "c" in before else 0

        self.db.execute(
            """
            DELETE FROM audit_log
            WHERE datetime(timestamp) < datetime('now', '-' || ? || ' days')
            """,
            (retention_days,),
        )
        after = self.db.fetch_one("SELECT COUNT(*) AS c FROM audit_log", ())
        after_count = int(after["c"]) if after and "c" in after else before_count
        return before_count - after_count
```

### 8.2 Audit Actions Enum

```python
class AuditAction(Enum):
    """Types of auditable actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    IMPORT = "import"
    EXPORT = "export"
    RECALCULATE = "recalculate"
    BACKUP = "backup"
    RESTORE = "restore"
    RESET = "reset"
```

### 8.3 What to Audit

**Always Audit:**
- All CREATE/UPDATE/DELETE on transaction tables (purchases, redemptions, game_sessions)
- All CSV imports (with record counts)
- All recalculation operations
- Database backup/restore/reset operations

**Optional Audit:**
- CREATE/UPDATE/DELETE on setup tables (users, sites, cards, etc.)
- View-only operations (exports, report generation)
- Settings changes

**Never Audit:**
- Query operations (SELECT)
- UI interactions
- Session state changes

### 8.4 Audit Log Schema

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,           -- ISO 8601 format
    action TEXT NOT NULL,              -- 'create', 'update', 'delete', etc.
    table_name TEXT,                   -- Which table was affected
    record_id INTEGER,                 -- Which record (if applicable)
    details TEXT,                      -- JSON or plain text with change details
    user_name TEXT,                    -- Who performed the action (future: auth)
    ip_address TEXT                    -- Future: for web version
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name);
```

### 8.5 Audit Log Retention Policy

**Settings:**
- `audit_log_retention_days`: Default 365 days
- `audit_log_auto_backup`: Default True
- `audit_log_backup_interval_days`: Default 30 days

**Auto-Backup:**
- Separate from database backup
- Exports old logs to CSV before deletion
- Triggered at retention threshold

---

## 9. UI Integration

### 9.1 Tools Tab Structure (Desktop)

**Location:** `sezzions/ui/tabs/setup_tab.py` → Sub-tab "Tools"

This plan assumes Tools lives as a Setup sub-tab (legacy parity). Sezzions also has a Tools menu already; the best UX is to support **both**:
- The Tools menu items remain quick-access entry points.
- The Tools tab becomes the “home” for imports/backups/audit/advanced tools.

**Implementation note:** both entry points should call the same underlying facade/service methods.

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ TOOLS                                               │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ▼ CSV Import/Export                                │
│   ┌───────────────────────────────────────────┐   │
│   │ Upload CSV                                 │   │
│   │  [Purchases] [Redemptions] [Sessions]     │   │
│   │  [Expenses] [Users] [Sites] [Cards]       │   │
│   │  [Methods] [Game Types] [Games]           │   │
│   │                                            │   │
│   │ Download Templates                         │   │
│   │  [Purchases] [Redemptions] [Sessions]     │   │
│   │  ... (same as above)                      │   │
│   │                                            │   │
│   │ Export Data as CSV                         │   │
│   │  [Purchases] [Redemptions] [Sessions]     │   │
│   │  ... (same as above)                      │   │
│   └───────────────────────────────────────────┘   │
│                                                     │
│ ▶ Data Recalculation                               │
│                                                     │
│ ▶ Database Tools                                   │
│                                                     │
│ ▶ Audit Log                                        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Collapsible Sections:**
- Each major section can be collapsed to save vertical space
- Persists state in settings

### 9.2 Import Preview Dialog

```python
class ImportPreviewDialog(QDialog):
    """Dialog to preview and confirm CSV import"""
    
    def __init__(self, preview: ImportPreview, entity_type: str, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.entity_type = entity_type
        self.setWindowTitle(f"Import Preview - {entity_type.title()}")
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Summary
        summary_label = QLabel(
            f"<b>Import Summary:</b><br>"
            f"Records to add: {len(self.preview.to_add)}<br>"
            f"Conflicts: {len(self.preview.conflicts)}<br>"
            f"Exact duplicates (skipped): {len(self.preview.exact_duplicates)}<br>"
            f"Errors: {len(self.preview.invalid_rows)}<br>"
            f"CSV duplicates: {len(self.preview.csv_duplicates)}"
        )
        layout.addWidget(summary_label)
        
        # Tabs for details
        tabs = QTabWidget()
        
        # To Add tab
        if self.preview.to_add:
            add_table = self._create_preview_table(self.preview.to_add)
            tabs.addTab(add_table, f"To Add ({len(self.preview.to_add)})")
        
        # Conflicts tab
        if self.preview.conflicts:
            conflicts_widget = self._create_conflicts_widget()
            tabs.addTab(conflicts_widget, f"Conflicts ({len(self.preview.conflicts)})")
        
        # Errors tab
        if self.preview.invalid_rows:
            errors_widget = self._create_errors_widget()
            tabs.addTab(errors_widget, f"Errors ({len(self.preview.invalid_rows)})")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel Import")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        
        if self.preview.invalid_rows:
            # Can't proceed with errors
            proceed_btn = QPushButton("Cannot Proceed (Fix Errors)")
            proceed_btn.setEnabled(False)
        else:
            proceed_btn = QPushButton("Proceed with Import")
            proceed_btn.setObjectName("PrimaryButton")
            proceed_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(proceed_btn)
        layout.addLayout(button_layout)
```

### 9.3 Recalculation Progress Dialog

```python
class RecalculationProgressDialog(QDialog):
    """Dialog to show recalculation progress"""
    
    def __init__(self, recalc_type: str, parent=None):
        super().__init__(parent)
        self.recalc_type = recalc_type
        self.setWindowTitle(f"Recalculating {recalc_type}...")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        
        self.cancel_btn = QPushButton("Cancel")
        # Cancel should request the worker to stop and rollback if applicable.
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)
    
    def update_progress(self, step: str, percent: int):
        """Update progress display"""
        self.status_label.setText(step)
        self.progress_bar.setValue(percent)
        QApplication.processEvents()  # Keep UI responsive
```

### 9.4 Notification Panel

```python
class NotificationPanel(QWidget):
    """Panel to display active notifications"""
    
    def __init__(self, notification_service: NotificationService, parent=None):
        super().__init__(parent)
        self.notification_service = notification_service
        self.setup_ui()
        
        # Subscribe to notification changes
        self.notification_service.subscribe(self.refresh)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("<b>Notifications</b>")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        clear_all_btn = QPushButton("Clear All")
        clear_all_btn.clicked.connect(self.clear_all)
        header_layout.addWidget(clear_all_btn)
        
        layout.addLayout(header_layout)
        
        # Scroll area for notifications
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        
        self.notifications_container = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_container)
        scroll.setWidget(self.notifications_container)
        
        layout.addWidget(scroll)
    
    def refresh(self, notifications: List[Notification]):
        """Refresh notification list"""
        # Clear existing
        while self.notifications_layout.count():
            item = self.notifications_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add each notification
        for notification in notifications:
            notif_widget = self._create_notification_widget(notification)
            self.notifications_layout.addWidget(notif_widget)
        
        if not notifications:
            empty_label = QLabel("No active notifications")
            empty_label.setAlignment(Qt.AlignCenter)
            self.notifications_layout.addWidget(empty_label)
    
    def _create_notification_widget(self, notification: Notification):
        """Create widget for single notification"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # Icon based on severity
        icon_label = QLabel(self._get_severity_icon(notification.severity))
        layout.addWidget(icon_label)
        
        # Content
        content_layout = QVBoxLayout()
        title_label = QLabel(f"<b>{notification.title}</b>")
        content_layout.addWidget(title_label)
        
        message_label = QLabel(notification.message)
        message_label.setWordWrap(True)
        content_layout.addWidget(message_label)
        
        time_label = QLabel(notification.timestamp.strftime("%I:%M %p"))
        time_label.setObjectName("HelperText")
        content_layout.addWidget(time_label)
        
        layout.addLayout(content_layout)
        
        # Action button
        if notification.action_callback:
            action_btn = QPushButton("View")
            action_btn.clicked.connect(notification.action_callback)
            layout.addWidget(action_btn)
        
        # Dismiss button
        if notification.dismissible:
            dismiss_btn = QPushButton("✕")
            dismiss_btn.setFixedSize(24, 24)
            dismiss_btn.clicked.connect(lambda: self.notification_service.dismiss_notification(notification.id))
            layout.addWidget(dismiss_btn)
        
        return widget
```

### 9.5 Menu Bar Integration

**File Menu:**
- Export All Data → Opens dialog to export all tables
- Import Database (Merge) → Opens file picker + “merge-from-db” workflow (conceptually the same as importing CSVs)
- Restore Database (Replace) → Opens file picker + restore dialog (destructive replace; requires explicit confirmation)
- Backup Database → Triggers backup service
- **Refresh All** (existing)

**Tools Menu:**
- Recalculate Everything
- Recalculate Session Data
- Recalculate Redemptions
- Recalculate RTP
- ---
- Data Validation Report (future)
- Database Integrity Check (future)
- ---
- Open Tools Tab

**View Menu:**
- Themes (existing)
- Full Screen (existing)
- ---
- Show Notifications

---

## 10. Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Build core service layer and data structures

**Tasks:**
1. Add Tools UI shell (Setup → Tools tab) but reuse existing menu actions where applicable
2. Implement schema definitions (PURCHASE_SCHEMA, REDEMPTION_SCHEMA, etc.) for CSV import/export only
3. Implement validation *adapters* (formatting + entity-specific CSV validation) that call existing validation services when possible
4. Implement DTOs (ImportResult, ValidationError, etc.)
5. Decide and document settings storage split (UI/tool prefs in JSON; accounting data in DB)
6. Add/plan DB migrations to enforce unique naming constraints (with duplicate preflight checks and a remediation UX)

**Deliverables:**
- `/sezzions/services/tools/` directory with base classes
- Schema definitions for all 10 entity types
- Validator suite with unit tests

### Phase 2: CSV Import/Export (Week 2)
**Goal:** Working CSV import/export for all entity types

**Tasks:**
1. Implement CSVImportService with full validation pipeline
2. Implement CSVExportService with FK name resolution
3. Implement template generation
4. Build ImportPreviewDialog UI
5. Wire up Upload/Download buttons in Tools tab
6. Write integration tests for import/export

**Deliverables:**
- Working CSV import for all 10 entities
- Template downloads for all entities
- Data export for all entities
- Import preview dialog with conflict resolution

### Phase 3: Database Tools (Week 3)
**Goal:** Backup, restore, reset functionality

**Tasks:**
1. Implement BackupService
2. Implement auto-backup scheduling
3. Build backup settings UI in Tools tab
4. Implement database reset with confirmation dialog
5. Implement database restore/merge logic
6. Write tests for backup/restore operations

**Deliverables:**
- Manual and automatic backup working
- Database reset with "keep setup data" option
- Database restore with replace/merge modes

### Phase 4: Recalculation Engine (Week 4)
**Goal:** Comprehensive recalculation system

**Tasks:**
1. Extend the existing recalculation pathway (via `AppFacade`) to support progress callbacks + (optional) scoped runs
2. Move recalculation execution to a background worker (no UI thread work)
3. Build recalculation progress dialog and wire it to the worker’s signals
4. Wire Tools tab recalculation buttons to call the same existing “Recalculate Everything” flow used by the Tools menu
5. Add post-import recalculation prompts/hooks (UI-driven) rather than auto-running silently
6. Add focused tests for the “orchestration” layer (progress + cancellation + error surfacing)

**Deliverables:**
- Recalculate Everything working
- Scoped recalculation by site/user
- Progress dialog with cancellation
- Post-import recalculation prompts

### Phase 5: Notifications (Week 5)
**Goal:** Notification system with backup alerts

**Tasks:**
1. Implement NotificationService
2. Build notification panel UI
3. Implement notification bell with badge
4. Implement auto-backup notifications
5. Add notification persistence (app settings JSON preferred; DB only if we explicitly want settings to travel with the database)
6. Write tests for notification system

**Deliverables:**
- Notification bell in main window
- Notification panel with dismiss/action buttons
- Backup due notifications at startup and hourly checks

### Phase 6: Audit Logging (Week 6)
**Goal:** Complete audit trail for all operations

**Tasks:**
1. Implement AuditService
2. Add audit logging to all CRUD operations (preferably in repositories/services so UI doesn’t need to remember to log)
3. Build audit log viewer dialog
4. Implement audit log export
5. Implement audit log auto-backup
6. Add audit log settings in Tools tab

**Deliverables:**
- All actions logged to audit_log table
- Audit log viewer with filters
- Audit log export to CSV
- Auto-backup of old logs before deletion

### Phase 7: Polish & Testing (Week 7)
**Goal:** Bug fixes, edge cases, user testing

**Tasks:**
1. End-to-end testing of import/export workflows
2. Performance testing with large datasets
3. UI/UX polish (tooltips, help text, etc.)
4. Documentation updates
5. User acceptance testing
6. Bug fixes from testing

**Deliverables:**
- Comprehensive test suite passing
- User documentation for Tools features
- Bug-free import/export workflow

---

## 11. Testing Strategy

### 11.1 Unit Tests

**Validators:**
- Test each field validator in isolation
- Test business rule validators with edge cases
- Test foreign key resolution with ambiguous names

**Services:**
- Mock repositories and test service logic
- Test import preview generation
- Test duplicate detection logic
- Test backup/restore file operations

### 11.2 Integration Tests

**CSV Import:**
- Valid CSV → successful import
- CSV with errors → preview shows errors, import blocked
- CSV with errors in permissive mode → preview allows excluding invalid rows; commit is atomic for remaining rows
- CSV with conflicts → user can choose overwrite/skip
- CSV with duplicates within file → error flagged
- Chronological ordering preserved

**Backup/Restore:**
- Backup uses SQLite online backup API (not raw file copy)
- Restore REPLACE leaves DB in a consistent state (then triggers full UI refresh)
- Restore MERGE_SELECTED preserves FK integrity and does not create orphan rows
- Failure injection: mid-merge exception causes full rollback (no partial writes)

**Recalculation:**
- Full recalculation rebuilds all derived fields correctly
- Scoped recalculation only affects target site/user
- Progress callback invoked at each step

**Audit Logging:**
- All CRUD operations create audit entries
- Audit log export includes all fields
- Old log deletion respects retention policy

### 11.3 End-to-End Tests

**Scenario 1: Bulk Import**
1. User exports existing purchases
2. User edits CSV to add new purchases
3. User imports CSV (preview shows adds vs duplicates)
4. User confirms import
5. System triggers recalculation
6. All derived data correct

**Scenario 2: Database Backup**
1. User sets backup folder
2. User enables auto-backup every 7 days
3. User performs backup now
4. Last backup timestamp updated
5. 7 days later, notification appears at startup
6. User clicks "Backup Now" in notification
7. Backup performed, notification dismissed

**Scenario 3: Data Validation**
1. User imports CSV with errors (future date, negative amount, missing required field)
2. Preview dialog shows error rows with details
3. "Proceed" button disabled
4. User cancels, fixes CSV, re-imports
5. Preview shows all valid
6. Import succeeds

### 11.4 Performance Tests

**Large Dataset Import:**
- 10,000 purchases imported in < 30 seconds
- 50,000 game sessions recalculated in < 60 seconds
- Backup of 100MB database in < 5 seconds

**Memory Usage:**
- Import of 10,000 records uses < 500MB RAM
- Recalculation doesn't cause memory leaks

---

## 12. Future Considerations

### 12.1 Web/Mobile Compatibility

**Design Decisions for Cross-Platform:**

**CSV Import/Export:**
- Service layer is UI-agnostic (can be called from REST API)
- Preview dialog concept translates to web modal/page
- File upload via HTTP multipart form data

**Database Tools:**
- Backup/restore via server-side storage (S3, etc.)
- Auto-backup runs on server, not client
- User downloads backup files via HTTP

**Notifications:**
- Web: Real-time notifications via WebSocket or polling
- Mobile: Push notifications for critical alerts
- Desktop: System tray notifications

**Audit Logging:**
- Add `ip_address` and `user_agent` fields for web version
- Log user authentication events
- Role-based access control for audit log viewing

### 12.2 Additional Notification Types

**Unredeemed Balance Alert:**
- Trigger: Balance > $0 for > X days without redemption
- Configurable threshold (default 90 days)
- Action: Navigate to Redemptions tab with site/user pre-selected

**Pending Redemption Alert:**
- Trigger: Redemption with no receipt_date for > X days
- Configurable threshold (default 30 days)
- Action: Navigate to specific redemption for editing

**Data Inconsistency Alert:**
- Trigger: Validation check finds issues (e.g., basis_consumed > amount)
- Action: Open validation report with details
- Persistent until resolved

**Low Balance Alert (Future):**
- Trigger: Site balance < $X (configurable)
- Suggests user to purchase or withdraw

### 12.3 Advanced Import Features

**Auto-Mapping CSV Columns:**
- AI/ML to detect column intent from headers
- "Site" vs "Site Name" vs "site_name" all map to site_id
- Confidence scoring for ambiguous columns

**Import Wizard:**
- Multi-step wizard for complex imports
- Step 1: Upload file
- Step 2: Map columns (drag-and-drop)
- Step 3: Preview and validate
- Step 4: Confirm and import

**Scheduled Imports:**
- User configures recurring import (daily, weekly)
- System checks folder for new CSV files
- Auto-imports and notifies user of results
- Useful for syncing with external systems

### 12.4 Data Validation Enhancements

**Validation Reports:**
- Periodic integrity checks (daily/weekly)
- Report showing:
  - Orphaned records (FK points to non-existent record)
  - Basis mismatches (basis_consumed > available basis)
  - Negative balances
  - Future-dated records
- Action: Auto-fix or manual review

**Constraint Enforcement:**
- Foreign key constraints in SQLite (enforced in Sezzions via `PRAGMA foreign_keys = ON`; keep enabled)
- Check constraints for business rules
- Trigger-based validation (e.g., prevent redemption > balance)

### 12.5 Audit Log Enhancements

**Change Tracking:**
- Store before/after values in details field (JSON)
- Enable "undo" functionality (future)
- Show diff view in audit log viewer

**Audit Log Search:**
- Full-text search across details field
- Filter by date range, action, table, user
- Export filtered results

**Audit Log Analytics:**
- Dashboard showing action frequency
- User activity trends
- Most-edited records

### 12.6 RTP Calculation

**Scope:**
- Calculate Return to Player percentage per game
- Track theoretical RTP vs actual RTP
- Identify variance and outliers

**Implementation:**
- Add `rtp_theoretical` field to games table
- Calculate `rtp_actual` from session data
- Display RTP report in Reporting tab
- Recalculate RTP after session changes

---

## Appendix A: CSV Schema Reference

### Purchases CSV

| CSV Column | DB Column | Type | Required | FK Table | Validation |
|------------|-----------|------|----------|----------|------------|
| User Name | user_id | FK | Yes | users | Must exist |
| Site Name | site_id | FK | Yes | sites | Must exist |
| Purchase Date | purchase_date | DATE | Yes | - | <= today |
| Purchase Time | purchase_time | TIME | No | - | Default 00:00:00 |
| Amount | amount | DECIMAL | Yes | - | > 0 |
| SC Received | sc_received | DECIMAL | Yes | - | >= 0 |
| Post-Purchase SC | starting_sc_balance | DECIMAL | No | - | >= sc_received |
| Cashback Earned | cashback_earned | DECIMAL | No | - | >= 0 |
| Card Name | card_id | FK | No | cards | Must exist if provided |
| Notes | notes | TEXT | No | - | - |

### Redemptions CSV

| CSV Column | DB Column | Type | Required | FK Table | Validation |
|------------|-----------|------|----------|----------|------------|
| User Name | user_id | FK | Yes | users | Must exist |
| Site Name | site_id | FK | Yes | sites | Must exist |
| Redemption Date | redemption_date | DATE | Yes | - | <= today |
| Redemption Time | redemption_time | TIME | No | - | Default 00:00:00 |
| Amount | amount | DECIMAL | Yes | - | > 0 |
| Fees | fees | DECIMAL | No | - | >= 0, <= amount |
| Method Name | method_id | FK | No | redemption_methods | Must exist if provided |
| Receipt Date | receipt_date | DATE | No | - | >= redemption_date |
| Notes | notes | TEXT | No | - | - |

### Game Sessions CSV

| CSV Column | DB Column | Type | Required | FK Table | Validation |
|------------|-----------|------|----------|----------|------------|
| User Name | user_id | FK | Yes | users | Must exist |
| Site Name | site_id | FK | Yes | sites | Must exist |
| Game Name | game_id | FK | Yes | games | Must exist |
| Session Date | session_date | DATE | Yes | - | <= today |
| Start Time | start_time | TIME | No | - | Default 00:00:00 |
| Starting SC | starting_balance | DECIMAL | Yes | - | >= 0 |
| Ending SC | ending_balance | DECIMAL | No | - | >= 0 |
| Starting Redeemable | starting_redeemable | DECIMAL | No | - | >= 0 |
| Ending Redeemable | ending_redeemable | DECIMAL | No | - | >= 0 |
| Purchases During | purchases_during | DECIMAL | No | - | >= 0 |
| Redemptions During | redemptions_during | DECIMAL | No | - | >= 0 |
| End Date | end_date | DATE | No | - | >= session_date |
| End Time | end_time | TIME | No | - | If same day: > start_time |
| Notes | notes | TEXT | No | - | - |

*(Other entity schemas follow similar pattern)*

---

## Appendix B: Database Schema Updates

### audit_log Table

```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'create', 'update', 'delete', 'import', 'export', 'recalculate', 'backup', 'restore', 'reset'
    table_name TEXT,
    record_id INTEGER,
    details TEXT,  -- JSON with change details
    user_name TEXT,
    ip_address TEXT  -- Optional/future: for web version
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name);
```

### settings Table Additions

Sezzions should keep **UI and operational preferences** out of the accounting database by default, especially to support future Web/Mobile ports.

**Recommendation:** store these in an app settings file (JSON), keyed by database path if needed:
- auto-backup enabled/interval/folder/last-backup
- notification thresholds
- import strict-mode default

If we later decide a setting must “travel with the database” (shared DB file across machines), we can optionally persist that small subset in the DB `settings` table.

---

## Appendix C: Error Messages Reference

### Import Errors

| Error Code | Message Template | User Action |
|------------|------------------|-------------|
| ERR_MISSING_REQUIRED | "Row {row}: Missing required field '{field}'" | Provide value for required field |
| ERR_INVALID_DATE | "Row {row}: Invalid date format for '{field}': '{value}'" | Use YYYY-MM-DD (MM/DD/YY optionally accepted) |
| ERR_INVALID_NUMBER | "Row {row}: Invalid number for '{field}': '{value}'" | Enter valid decimal number |
| ERR_FK_NOT_FOUND | "Row {row}: {fk_type} '{value}' not found" | Create the referenced entity first |
| ERR_FK_AMBIGUOUS | "Row {row}: {fk_type} '{value}' is ambiguous (found {count} matches)" | Use unique name or provide ID |
| ERR_BUSINESS_RULE | "Row {row}: {message}" | Fix data to satisfy business rule |
| ERR_CSV_DUPLICATE | "Row {row}: Duplicate unique key found in CSV" | Remove duplicate row |
| WARN_CONFLICT | "Row {row}: Conflicts with existing record" | Choose to overwrite or skip |

### Backup Errors

| Error Code | Message Template | User Action |
|------------|------------------|-------------|
| ERR_BACKUP_NO_FOLDER | "Backup folder not configured" | Set backup folder in Settings |
| ERR_BACKUP_FOLDER_INVALID | "Backup folder '{path}' does not exist or is not writable" | Choose valid folder |
| ERR_BACKUP_FILE_EXISTS | "Backup file '{filename}' already exists" | Choose different filename or overwrite |
| ERR_BACKUP_FAILED | "Backup failed: {error}" | Check disk space and permissions |
| ERR_RESTORE_INVALID | "Backup file is invalid or corrupt" | Use valid backup file |

---

## Summary

This implementation plan provides a comprehensive roadmap for migrating and enhancing the Tools/Setup functionality in the new OOP architecture. Key design principles:

1. **Service-oriented architecture** separates business logic from UI
2. **Validation framework** is extensible and testable
3. **Foreign key resolution** uses unique names with optional ID override
4. **Import preview** gives users full control before committing
5. **Audit logging** provides complete transparency
6. **Notifications** keep users informed of critical events
7. **Cross-platform design** prepares for future web/mobile deployment

The phased implementation approach allows for incremental delivery of value while maintaining system stability. Each phase builds on the previous, ensuring a solid foundation before adding complexity.

---

**End of Document**
