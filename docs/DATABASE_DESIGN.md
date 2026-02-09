# Database Design

## Overview

The Sezzions database schema supports both **SQLite** (desktop) and **PostgreSQL** (web) without code changes. This document defines tables, relationships, indexes, and migration strategy.

---

## Database Manager (`repositories/database.py`)

The DatabaseManager class abstracts database connections:

```python
from typing import Optional, List, Dict, Any
import sqlite3
import os

class DatabaseManager:
    """Manages database connections for SQLite and PostgreSQL"""
    
    def __init__(self, db_path: str = "sezzions.db", db_type: str = "sqlite"):
        self.db_path = db_path
        self.db_type = db_type
        self._connection = None
        
        if db_type == "sqlite":
            self._init_sqlite()
        elif db_type == "postgres":
            self._init_postgres()
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        self._connection = conn
    
    def _init_postgres(self):
        """Initialize PostgreSQL database"""
        import psycopg2
        import psycopg2.extras
        
        self._connection = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        self._connection.set_session(autocommit=False)
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and return one row"""
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return all rows"""
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute query and return last insert ID"""
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        self._connection.commit()
        return cursor.lastrowid
    
    def begin_transaction(self):
        """Begin transaction"""
        if self.db_type == "sqlite":
            self._connection.execute("BEGIN")
    
    def commit(self):
        """Commit transaction"""
        self._connection.commit()
    
    def rollback(self):
        """Rollback transaction"""
        self._connection.rollback()
```

---

## Core Tables

### 1. users

**Purpose:** User accounts (players)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL, UNIQUE | User display name |
| email | TEXT/VARCHAR(255) | NULL | User email |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | User notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Indexes:**
- `idx_users_active` ON (is_active)

**SQLite:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    email TEXT,
    is_active INTEGER DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

**PostgreSQL:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

### 2. sites

**Purpose:** Casino sites (Stake, Fortune Coins, etc.)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL, UNIQUE | Site name |
| url | TEXT/VARCHAR(512) | NULL | Site URL |
| sc_rate | DECIMAL(10,2) | DEFAULT 1.0 | SC:Dollar ratio |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | Site notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Indexes:**
- `idx_sites_active` ON (is_active)

---

### 3. cards

**Purpose:** Payment cards for purchases

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL | Card name (e.g., "Chase Sapphire") |
| user_id | INTEGER | NOT NULL, FK → users(id) | Card owner |
| last_four | TEXT/VARCHAR(4) | NULL | Last 4 digits |
| cashback_rate | DECIMAL(5,2) | DEFAULT 0.0 | Cashback % (0-100) |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | Card notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Indexes:**
- `idx_cards_user` ON (user_id)
- `idx_cards_active` ON (is_active)

**Foreign Keys:**
- user_id REFERENCES users(id) ON DELETE CASCADE

---

### 4. purchases

**Purpose:** SC purchases (adds basis to FIFO pool)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| purchase_date | DATE | NOT NULL | Purchase date |
| purchase_time | TIME | DEFAULT '00:00:00' | Purchase time |
| site_id | INTEGER | NOT NULL, FK → sites(id) | Casino site |
| user_id | INTEGER | NOT NULL, FK → users(id) | Purchaser |
| amount | DECIMAL(10,2) | NOT NULL | USD spent |
| sc_received | DECIMAL(10,2) | NOT NULL | SC received |
| card_id | INTEGER | NULL, FK → cards(id) | Payment card |
| remaining_amount | DECIMAL(10,2) | NOT NULL | Unconsumed basis (FIFO) |
| notes | TEXT | NULL | Purchase notes |
| deleted_at | TIMESTAMP | NULL | Soft delete timestamp (Issue #92) |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Computed Fields:**
- consumed = amount - remaining_amount

**Indexes:**
- `idx_purchases_site_user` ON (site_id, user_id)
- `idx_purchases_date` ON (purchase_date, purchase_time)
- `idx_purchases_remaining` ON (remaining_amount) WHERE remaining_amount > 0
- `idx_purchases_deleted` ON (deleted_at) – for soft delete queries (Issue #92)

**Foreign Keys:**
- site_id REFERENCES sites(id) ON DELETE RESTRICT
- user_id REFERENCES users(id) ON DELETE RESTRICT

**Soft Delete Behavior (Issue #92):**
- **delete():** Sets `deleted_at = CURRENT_TIMESTAMP` instead of DELETE. Record remains in database.
- **restore():** Clears `deleted_at` to NULL, making record visible again.
- **All queries:** Automatically filter `WHERE deleted_at IS NULL` to exclude soft-deleted records.
- **FIFO:** `get_available_for_fifo()` excludes soft-deleted purchases to maintain accurate basis tracking.
- card_id REFERENCES cards(id) ON DELETE SET NULL

**Business Rules:**
- Cannot edit amount/site/user if consumed > 0
- remaining_amount must be >= 0 and <= amount

---

### 5. redemptions

**Purpose:** SC redemptions (consumes basis via FIFO)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| redemption_date | DATE | NOT NULL | Redemption date |
| redemption_time | TIME | DEFAULT '00:00:00' | Redemption time |
| site_id | INTEGER | NOT NULL, FK → sites(id) | Casino site |
| user_id | INTEGER | NOT NULL, FK → users(id) | Redeemer |
| amount | DECIMAL(10,2) | NOT NULL | USD redeemed |
| method_id | INTEGER | NULL, FK → redemption_methods(id) | Payment method |
| is_free_sc | BOOLEAN/INTEGER | DEFAULT 0 | Discoverable SC redemption |
| fees | DECIMAL(10,2) | DEFAULT 0.0 | Redemption fees |
| notes | TEXT | NULL | Redemption notes |
| deleted_at | TIMESTAMP | NULL | Soft delete timestamp (Issue #92) |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Indexes:**
- `idx_redemptions_site_user` ON (site_id, user_id)
- `idx_redemptions_date` ON (redemption_date, redemption_time)
- `idx_redemptions_deleted` ON (deleted_at) – for soft delete queries (Issue #92)

**Foreign Keys:**
- site_id REFERENCES sites(id) ON DELETE RESTRICT
- user_id REFERENCES users(id) ON DELETE RESTRICT
- method_id REFERENCES redemption_methods(id) ON DELETE SET NULL

**Soft Delete Behavior (Issue #92):**
- **delete():** Sets `deleted_at = CURRENT_TIMESTAMP`.
- **restore():** Clears `deleted_at`.
- **All queries:** Filter `WHERE deleted_at IS NULL`.

---

### 6. redemption_allocations

**Purpose:** Links redemptions to purchases for FIFO basis tracking

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| redemption_id | INTEGER | NOT NULL, FK → redemptions(id) | Redemption |
| purchase_id | INTEGER | NOT NULL, FK → purchases(id) | Purchase |
| allocated_amount | DECIMAL(10,2) | NOT NULL | Basis allocated |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Indexes:**
- `idx_allocations_redemption` ON (redemption_id)
- `idx_allocations_purchase` ON (purchase_id)

**Foreign Keys:**
- redemption_id REFERENCES redemptions(id) ON DELETE CASCADE
- purchase_id REFERENCES purchases(id) ON DELETE RESTRICT

**Business Rules:**
- Sum of allocated_amount per redemption must equal redemption.amount
- Cannot allocate more than purchase.remaining_amount

---

### 7. realized_transactions

**Purpose:** Tax sessions (taxable profit/loss events)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| redemption_date | DATE | NOT NULL | Tax event date |
| site_id | INTEGER | NOT NULL, FK → sites(id) | Casino site |
| user_id | INTEGER | NOT NULL, FK → users(id) | Taxpayer |
| redemption_id | INTEGER | NOT NULL, FK → redemptions(id) | Associated redemption |
| cost_basis | DECIMAL(10,2) | NOT NULL | Total basis consumed |
| payout | DECIMAL(10,2) | NOT NULL | Total payout (after fees) |
| net_pl | DECIMAL(10,2) | NOT NULL | Taxable profit/loss |
| notes | TEXT | NULL | Transaction notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Computed Fields:**
- net_pl = payout - cost_basis

**Indexes:**
- `idx_realized_site_user` ON (site_id, user_id)
- `idx_realized_date` ON (redemption_date)
- `idx_realized_redemption` ON (redemption_id)

**Foreign Keys:**
- site_id REFERENCES sites(id) ON DELETE RESTRICT
- user_id REFERENCES users(id) ON DELETE RESTRICT
- redemption_id REFERENCES redemptions(id) ON DELETE CASCADE

---

### 8. game_sessions

**Purpose:** Active game sessions with SC balances

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| session_date | DATE | NOT NULL | Session date |
| session_time | TIME | DEFAULT '00:00:00' | Session start time |
| site_id | INTEGER | NOT NULL, FK → sites(id) | Casino site |
| user_id | INTEGER | NOT NULL, FK → users(id) | Player |
| game_id | INTEGER | NULL, FK → games(id) | Game played |
| starting_balance | DECIMAL(10,2) | DEFAULT 0.0 | Starting total SC |
| ending_balance | DECIMAL(10,2) | NULL | Ending total SC |
| starting_redeemable | DECIMAL(10,2) | DEFAULT 0.0 | Starting redeemable SC |
| ending_redeemable | DECIMAL(10,2) | NULL | Ending redeemable SC |
| basis_consumed | DECIMAL(10,2) | DEFAULT 0.0 | Basis consumed |
| net_taxable_pl | DECIMAL(10,2) | DEFAULT 0.0 | Net taxable P/L |
| is_closed | BOOLEAN/INTEGER | DEFAULT 0 | Session closed flag |
| notes | TEXT | NULL | Session notes |
| deleted_at | TIMESTAMP | NULL | Soft delete timestamp (Issue #92) |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | NULL | Last update timestamp |

**Computed Fields:**
- delta_play = ending_balance - starting_balance
- delta_redeemable = ending_redeemable - starting_redeemable

**Indexes:**
- `idx_sessions_site_user` ON (site_id, user_id)
- `idx_sessions_date` ON (session_date, session_time)
- `idx_sessions_open` ON (is_closed) WHERE is_closed = 0
- `idx_sessions_deleted` ON (deleted_at) – for soft delete queries (Issue #92)

**Foreign Keys:**
- site_id REFERENCES sites(id) ON DELETE RESTRICT
- user_id REFERENCES users(id) ON DELETE RESTRICT
- game_id REFERENCES games(id) ON DELETE SET NULL

**Soft Delete Behavior (Issue #92):**
- **delete():** Sets `deleted_at = CURRENT_TIMESTAMP`.
- **restore():** Clears `deleted_at`.
- **All queries:** Filter `WHERE deleted_at IS NULL`.

---

### 9. redemption_methods

**Purpose:** Payment methods for redemptions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL, UNIQUE | Method name |
| method_type | TEXT/VARCHAR(50) | NULL | Type (bank, crypto, etc.) |
| user_id | INTEGER | NULL, FK → users(id) | Method owner |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | Method notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

---

### 10. games

**Purpose:** Game catalog

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL, UNIQUE | Game name |
| game_type_id | INTEGER | NULL, FK → game_types(id) | Game type |
| rtp | DECIMAL(5,2) | NULL | Return to player % |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | Game notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

---

### 11. game_types

**Purpose:** Game type categories (Slots, Table Games, etc.)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| name | TEXT/VARCHAR(255) | NOT NULL, UNIQUE | Type name |
| is_active | BOOLEAN/INTEGER | DEFAULT 1 | Soft delete flag |
| notes | TEXT | NULL | Type notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

---

## Audit & Settings Tables

### 12. audit_log

**Purpose:** Audit trail for compliance and undo/redo support (Issue #92)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER/SERIAL | PRIMARY KEY | Auto-increment ID |
| action | TEXT/VARCHAR(50) | NOT NULL | Action type (CREATE, UPDATE, DELETE, RESTORE, UNDO, REDO) |
| table_name | TEXT/VARCHAR(100) | NOT NULL | Table affected |
| record_id | INTEGER | NULL | Record ID affected |
| old_data | TEXT | NULL | JSON snapshot of record before change (for UPDATE/DELETE/RESTORE) |
| new_data | TEXT | NULL | JSON snapshot of record after change (for CREATE/UPDATE/RESTORE) |
| group_id | TEXT | NULL | UUID linking related operations (e.g., batch updates) |
| details | TEXT | NULL | Additional details |
| user_name | TEXT/VARCHAR(255) | NULL | User who performed action |
| timestamp | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Action timestamp |

**Indexes:**
- `idx_audit_table` ON (table_name)
- `idx_audit_timestamp` ON (timestamp)
- `idx_audit_group` ON (group_id) – for retrieving operation groups

**Notes:**
- **Soft Delete Pattern:** Records are NOT deleted; instead, `deleted_at` timestamp is set. `restore()` clears `deleted_at`.
- **JSON Snapshots:** `old_data` and `new_data` store complete record state as JSON TEXT, enabling atomic rollback via `UndoRedoService`.
- **group_id:** UUID linking related audit entries (e.g., multi-table cascading deletes, bulk imports). Used by undo/redo to atomically reverse operation groups.
- **Undo/Redo:** Persistent stacks stored in `settings` table. Service layer uses audit log to reverse/replay operations.

---

### 13. settings

**Purpose:** Application settings (key-value store)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| key | TEXT/VARCHAR(100) | PRIMARY KEY | Setting key |
| value | TEXT | NULL | Setting value (JSON or string) |

**Example Settings:**
- `audit_log_enabled`: "1" or "0"
- `audit_log_actions`: "INSERT,UPDATE,DELETE,IMPORT"
- `audit_log_default_user`: "system"

---

## Database-Agnostic Queries

### Handle AUTO_INCREMENT vs SERIAL

**SQLite:**
```python
query = "INSERT INTO users (name) VALUES (?)"
cursor.execute(query, (name,))
user_id = cursor.lastrowid
```

**PostgreSQL:**
```python
query = "INSERT INTO users (name) VALUES (%s) RETURNING id"
cursor.execute(query, (name,))
user_id = cursor.fetchone()[0]
```

**Abstracted:**
```python
def insert_returning_id(self, query, params):
    if self.db_type == "sqlite":
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid
    elif self.db_type == "postgres":
        query += " RETURNING id"
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]
```

---

### Handle Placeholders (? vs %s)

**SQLite:** Uses `?` for placeholders  
**PostgreSQL:** Uses `%s` for placeholders

**Solution:** Convert queries at runtime:
```python
def _convert_placeholders(self, query):
    if self.db_type == "postgres":
        return query.replace("?", "%s")
    return query
```

---

### Handle BOOLEAN vs INTEGER

**SQLite:** No native BOOLEAN type (use INTEGER: 0/1)  
**PostgreSQL:** Native BOOLEAN type (TRUE/FALSE)

**Solution:** Use INTEGER in queries, convert in repository:
```python
def _to_bool(self, value):
    return bool(value) if value is not None else False

def _from_bool(self, value):
    return 1 if value else 0
```

---

## Migration Strategy

### Using Alembic (Recommended with SQLAlchemy)

1. **Initialize Alembic:**
```bash
cd ./
alembic init migrations
```

2. **Configure `alembic.ini`:**
```ini
sqlalchemy.url = sqlite:///sezzions.db
```

3. **Create Migration:**
```bash
alembic revision -m "Create initial tables"
```

4. **Apply Migration:**
```bash
alembic upgrade head
```

5. **Rollback Migration:**
```bash
alembic downgrade -1
```

---

### Manual Migrations (Without SQLAlchemy)

Create `migrations/` folder with numbered SQL files:

```
migrations/
├── 001_create_users.sql
├── 002_create_sites.sql
├── 003_create_cards.sql
└── ...
```

**Migration Manager:**
```python
class MigrationManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_schema_version(self):
        try:
            result = self.db.fetch_one("SELECT MAX(version) as v FROM schema_version")
            return result['v'] if result and result['v'] else 0
        except:
            return 0
    
    def apply_migrations(self):
        current_version = self.get_schema_version()
        migration_files = sorted(os.listdir("migrations"))
        
        for filename in migration_files:
            version = int(filename.split("_")[0])
            if version > current_version:
                with open(f"migrations/{filename}") as f:
                    sql = f.read()
                self.db.execute(sql)
                self.db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
```

---

## Indexes for Performance

### Critical Indexes:

1. **purchases.remaining_amount** - FIFO queries filter by remaining > 0
2. **purchases/redemptions date+time** - Chronological ordering
3. **site_id+user_id** - Most queries filter by pair
4. **redemption_allocations foreign keys** - Join performance

**Create Indexes:**
```sql
-- SQLite
CREATE INDEX idx_purchases_remaining ON purchases(remaining_amount) WHERE remaining_amount > 0;
CREATE INDEX idx_purchases_site_user_date ON purchases(site_id, user_id, purchase_date, purchase_time);
CREATE INDEX idx_redemptions_site_user_date ON redemptions(site_id, user_id, redemption_date, redemption_time);

-- PostgreSQL (similar, adjust WHERE clause)
CREATE INDEX idx_purchases_remaining ON purchases(remaining_amount) WHERE remaining_amount > 0;
```

---

## Transaction Management

### Pattern for Multi-Table Operations:

```python
def create_redemption_with_allocation(redemption_data, allocation_data):
    try:
        db.begin_transaction()
        
        # Insert redemption
        redemption_id = redemption_repo.create(redemption_data)
        
        # Insert realized transaction
        tax_session_repo.create(tax_session_data)
        
        # Insert allocations
        for allocation in allocation_data:
            allocation['redemption_id'] = redemption_id
            allocation_repo.create(allocation)
        
        # Update purchase remaining amounts
        for allocation in allocation_data:
            purchase_repo.update_remaining_amount(
                allocation['purchase_id'],
                allocation['new_remaining']
            )
        
        db.commit()
        return redemption_id
        
    except Exception as e:
        db.rollback()
        raise e
```

---

## Next Steps

1. Create DatabaseManager class in `repositories/database.py`
2. Create migration files or Alembic setup
3. Run initial migration to create tables
4. Read **[ARCHITECTURE.md](ARCHITECTURE.md)** to implement repositories
5. Read **[ACCOUNTING_LOGIC.md](ACCOUNTING_LOGIC.md)** for FIFO service

---

**Last Updated:** January 16, 2026
