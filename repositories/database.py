"""
Database connection and management
"""
from contextlib import contextmanager
import sqlite3
from typing import Optional, List, Dict, Any, Iterator, Sequence


class DatabaseWritesBlockedError(RuntimeError):
    """Raised when a write is attempted while writes are blocked."""


class DatabaseManager:
    """Manages database connections for SQLite (PostgreSQL support coming later)"""
    
    def __init__(self, db_path: str = "sezzions.db"):
        self.db_path = db_path
        self.db_type = "sqlite"
        self._connection = None
        self._change_listeners = []
        self._writes_blocked = False
        self._init_sqlite()
        self._create_tables()

    def set_writes_blocked(self, blocked: bool) -> None:
        """Enable/disable write blocking for this DatabaseManager instance.

        Intended for UI-facing connections: when database maintenance (restore/reset)
        is running in a background worker, we keep the UI responsive but prevent
        user-driven writes from committing against a potentially changing dataset.
        """
        self._writes_blocked = bool(blocked)

    def writes_blocked(self) -> bool:
        return self._writes_blocked

    def _assert_writes_allowed(self, query: str) -> None:
        if not self._writes_blocked:
            return

        q = (query or "").lstrip().upper()
        # Allow typical read-only statements.
        if q.startswith("SELECT") or q.startswith("WITH") or q.startswith("EXPLAIN"):
            return

        raise DatabaseWritesBlockedError(
            "Database maintenance is in progress; writes are temporarily disabled."
        )
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        self._connection = conn
    
    def _create_tables(self):
        """Create initial database schema"""
        cursor = self._connection.cursor()
        
        # Schema version tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        # Sites table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT,
                sc_rate REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        # Cards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                last_four TEXT,
                cashback_rate REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # RedemptionMethods table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS redemption_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                method_type TEXT,
                user_id INTEGER,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        self._migrate_redemption_methods_table()

        # Redemption Method Types table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS redemption_method_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        # GameTypes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        # Games table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                game_type_id INTEGER NOT NULL,
                rtp REAL,
                actual_rtp REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (game_type_id) REFERENCES game_types(id) ON DELETE CASCADE
            )
        ''')
        self._migrate_games_table()
        
        # Purchases table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                sc_received TEXT DEFAULT '0.00',
                starting_sc_balance TEXT DEFAULT '0.00',
                cashback_earned TEXT DEFAULT '0.00',
                cashback_is_manual INTEGER DEFAULT 0,
                purchase_date TEXT NOT NULL,
                purchase_time TEXT,
                card_id INTEGER,
                remaining_amount TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE SET NULL
            )
        ''')

        # Migration: Add new columns if table already exists
        self._migrate_purchases_table()

        # Unrealized positions notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unrealized_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                UNIQUE(site_id, user_id),
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        self._migrate_unrealized_positions_table()
        
        # Redemptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS redemptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                amount TEXT NOT NULL,
                fees TEXT DEFAULT '0.00',
                redemption_date TEXT NOT NULL,
                redemption_time TEXT DEFAULT '00:00:00',
                redemption_method_id INTEGER,
                is_free_sc INTEGER DEFAULT 0,
                receipt_date TEXT,
                processed INTEGER DEFAULT 0,
                more_remaining INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (redemption_method_id) REFERENCES redemption_methods(id) ON DELETE SET NULL
            )
        ''')

        # Migration: Add new columns if table already exists
        self._migrate_redemptions_table()
        
        # Game sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                game_id INTEGER,
                game_type_id INTEGER,
                session_date TEXT NOT NULL,
                session_time TEXT DEFAULT '00:00:00',
                end_date TEXT,
                end_time TEXT,
                starting_balance TEXT DEFAULT '0.00',
                ending_balance TEXT DEFAULT '0.00',
                starting_redeemable TEXT DEFAULT '0.00',
                ending_redeemable TEXT DEFAULT '0.00',
                wager_amount TEXT DEFAULT '0.00',
                rtp REAL,
                purchases_during TEXT DEFAULT '0.00',
                redemptions_during TEXT DEFAULT '0.00',
                expected_start_total TEXT,
                expected_start_redeemable TEXT,
                discoverable_sc TEXT,
                delta_total TEXT,
                delta_redeem TEXT,
                session_basis TEXT,
                basis_consumed TEXT,
                net_taxable_pl TEXT,
                status TEXT DEFAULT 'Active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                FOREIGN KEY (game_type_id) REFERENCES game_types(id) ON DELETE SET NULL
            )
        ''')

        # Game session event links (legacy parity)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_session_event_links (
                id INTEGER PRIMARY KEY,
                game_session_id INTEGER NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL CHECK(event_type IN ('purchase','redemption')),
                event_id INTEGER NOT NULL,
                relation TEXT NOT NULL CHECK(relation IN ('BEFORE','DURING','AFTER','MANUAL')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(game_session_id, event_type, event_id, relation)
            )
        ''')

        # Game RTP aggregates (legacy parity)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_rtp_aggregates (
                game_id INTEGER PRIMARY KEY REFERENCES games(id),
                total_wager REAL DEFAULT 0,
                total_delta REAL DEFAULT 0,
                session_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Add new columns if table already exists
        self._migrate_game_sessions_table()
        self._migrate_game_rtp_aggregates_table()
        self._migrate_daily_sessions_table()
        
        # Redemption allocations table (tracks FIFO purchase consumption)
        # Reference: DATABASE_DESIGN.md §6
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS redemption_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redemption_id INTEGER NOT NULL,
                purchase_id INTEGER NOT NULL,
                allocated_amount TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (redemption_id) REFERENCES redemptions(id) ON DELETE CASCADE,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE
            )
        ''')
        
        # Realized transactions table (tax sessions)
        # Reference: DATABASE_DESIGN.md §7
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realized_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                redemption_date TEXT NOT NULL,
                site_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                redemption_id INTEGER NOT NULL,
                cost_basis TEXT NOT NULL,
                payout TEXT NOT NULL,
                net_pl TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE RESTRICT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
                FOREIGN KEY (redemption_id) REFERENCES redemptions(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS realized_daily_notes (
                session_date TEXT PRIMARY KEY,
                notes TEXT
            )
        ''')

        # Expenses table (legacy parity)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                amount TEXT NOT NULL,
                vendor TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'Other Expenses',
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')

        # Daily sessions table (per-user daily aggregates)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_sessions (
                session_date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                total_other_income REAL DEFAULT 0.0,
                total_session_pnl REAL DEFAULT 0.0,
                net_daily_pnl REAL DEFAULT 0.0,
                status TEXT,
                num_game_sessions INTEGER DEFAULT 0,
                num_other_income_items INTEGER DEFAULT 0,
                PRIMARY KEY (session_date, user_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
            )
        ''')

        # Daily date tax (date-level tax calculated on net of ALL users)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_date_tax (
                session_date TEXT PRIMARY KEY,
                net_daily_pnl REAL DEFAULT 0.0,
                tax_withholding_rate_pct REAL,
                tax_withholding_is_custom INTEGER DEFAULT 0,
                tax_withholding_amount REAL,
                notes TEXT
            )
        ''')

        # Expenses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                expense_time TEXT,
                amount TEXT NOT NULL,
                vendor TEXT NOT NULL,
                description TEXT,
                category TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')

        # One-time migration from legacy daily_tax_sessions -> daily_sessions
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_tax_sessions'"
        )
        if cursor.fetchone():
            cursor.execute('''
                INSERT OR IGNORE INTO daily_sessions
                    (session_date, user_id, total_other_income, total_session_pnl, net_daily_pnl,
                     status, num_game_sessions, num_other_income_items, notes)
                SELECT session_date, user_id, total_other_income, total_session_pnl, net_daily_pnl,
                       status, num_game_sessions, num_other_income_items, notes
                FROM daily_tax_sessions
            ''')
            cursor.execute("DROP TABLE daily_tax_sessions")

        self._migrate_expenses_table()
        
        # Account adjustments table (basis corrections + balance checkpoints)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                effective_date TEXT NOT NULL,
                effective_time TEXT DEFAULT '00:00:00',
                type TEXT NOT NULL CHECK(type IN ('BASIS_USD_CORRECTION', 'BALANCE_CHECKPOINT_CORRECTION')),
                delta_basis_usd TEXT DEFAULT '0.00',
                checkpoint_total_sc TEXT DEFAULT '0.00',
                checkpoint_redeemable_sc TEXT DEFAULT '0.00',
                reason TEXT NOT NULL,
                notes TEXT,
                related_table TEXT,
                related_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                deleted_at TIMESTAMP,
                deleted_reason TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
            )
        ''')
        
        # Audit log table (compliance trail)
        # Reference: DATABASE_DESIGN.md §12
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                details TEXT,
                user_name TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Settings table (key-value store)
        # Reference: DATABASE_DESIGN.md §13
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Create indexes for performance
        # Reference: DATABASE_DESIGN.md - Indexes for Performance
        
        # Purchases indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_remaining ON purchases(remaining_amount)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_site_user ON purchases(site_id, user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date, purchase_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_deleted ON purchases(deleted_at)')
        
        # Redemptions indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_redemptions_site_user ON redemptions(site_id, user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_redemptions_date ON redemptions(redemption_date, redemption_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_redemptions_deleted ON redemptions(deleted_at)')
        
        # Redemption allocations indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_allocations_redemption ON redemption_allocations(redemption_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_allocations_purchase ON redemption_allocations(purchase_id)')
        
        # Realized transactions indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realized_site_user ON realized_transactions(site_id, user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realized_date ON realized_transactions(redemption_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_realized_redemption ON realized_transactions(redemption_id)')
        
        # Game sessions indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_site_user ON game_sessions(site_id, user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_date ON game_sessions(session_date, session_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON game_sessions(deleted_at)')

        # Game session event links indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gsel_session ON game_session_event_links(game_session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gsel_event ON game_session_event_links(event_type, event_id)')
        
        # Account adjustments indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_user_site ON account_adjustments(user_id, site_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_date ON account_adjustments(effective_date, effective_time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_type ON account_adjustments(type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_deleted ON account_adjustments(deleted_at)')
        
        # Audit log indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)')
        
        # Users indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')
        
        # Sites indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sites_active ON sites(is_active)')
        
        # Cards indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cards_active ON cards(is_active)')
        
        self._connection.commit()

        # Data normalization (idempotent): ensure missing times are treated as 00:00:00
        self._normalize_time_fields()
    
    def _migrate_game_sessions_table(self):
        """Add new columns to game_sessions if they don't exist"""
        cursor = self._connection.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(game_sessions)")
        columns_info = cursor.fetchall()
        existing_columns = {row[1] for row in columns_info}

        game_id_col = next((row for row in columns_info if row[1] == "game_id"), None)
        if game_id_col and game_id_col[3] == 1:
            try:
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.execute("ALTER TABLE game_sessions RENAME TO game_sessions_old")
                cursor.execute('''
                    CREATE TABLE game_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        site_id INTEGER NOT NULL,
                        game_id INTEGER,
                        game_type_id INTEGER,
                        session_date TEXT NOT NULL,
                        session_time TEXT DEFAULT '00:00:00',
                        end_date TEXT,
                        end_time TEXT,
                        starting_balance TEXT DEFAULT '0.00',
                        ending_balance TEXT DEFAULT '0.00',
                        starting_redeemable TEXT DEFAULT '0.00',
                        ending_redeemable TEXT DEFAULT '0.00',
                        purchases_during TEXT DEFAULT '0.00',
                        redemptions_during TEXT DEFAULT '0.00',
                        expected_start_total TEXT,
                        expected_start_redeemable TEXT,
                        discoverable_sc TEXT,
                        delta_total TEXT,
                        delta_redeem TEXT,
                        session_basis TEXT,
                        basis_consumed TEXT,
                        net_taxable_pl TEXT,
                        tax_withholding_rate_pct REAL,
                        tax_withholding_is_custom INTEGER DEFAULT 0,
                        tax_withholding_amount TEXT,
                        status TEXT DEFAULT 'Active',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE,
                        FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
                        FOREIGN KEY (game_type_id) REFERENCES game_types(id) ON DELETE SET NULL
                    )
                ''')

                new_columns = [
                    "id",
                    "user_id",
                    "site_id",
                    "game_id",
                    "game_type_id",
                    "session_date",
                    "session_time",
                    "end_date",
                    "end_time",
                    "starting_balance",
                    "ending_balance",
                    "starting_redeemable",
                    "ending_redeemable",
                    "purchases_during",
                    "redemptions_during",
                    "expected_start_total",
                    "expected_start_redeemable",
                    "discoverable_sc",
                    "delta_total",
                    "delta_redeem",
                    "session_basis",
                    "basis_consumed",
                    "net_taxable_pl",
                    "tax_withholding_rate_pct",
                    "tax_withholding_is_custom",
                    "tax_withholding_amount",
                    "status",
                    "notes",
                    "created_at",
                    "updated_at",
                ]
                old_columns = [col for col in new_columns if col in existing_columns]
                cols_csv = ", ".join(old_columns)
                cursor.execute(
                    f"INSERT INTO game_sessions ({cols_csv}) SELECT {cols_csv} FROM game_sessions_old"
                )
                cursor.execute("DROP TABLE game_sessions_old")
                cursor.execute("PRAGMA foreign_keys=ON")
            except Exception:
                cursor.execute("PRAGMA foreign_keys=ON")
                try:
                    cursor.execute("DROP TABLE IF EXISTS game_sessions_old")
                except Exception:
                    pass
        
        # Add missing columns
        migrations = [
            ("game_type_id", "INTEGER REFERENCES game_types(id) ON DELETE SET NULL"),
            ("starting_redeemable", "TEXT DEFAULT '0.00'"),
            ("ending_redeemable", "TEXT DEFAULT '0.00'"),
            ("end_date", "TEXT"),
            ("end_time", "TEXT"),
            ("wager_amount", "TEXT DEFAULT '0.00'"),
            ("rtp", "REAL"),
            ("expected_start_total", "TEXT"),
            ("expected_start_redeemable", "TEXT"),
            ("discoverable_sc", "TEXT"),
            ("delta_total", "TEXT"),
            ("delta_redeem", "TEXT"),
            ("session_basis", "TEXT"),
            ("basis_consumed", "TEXT"),
            ("net_taxable_pl", "TEXT"),
            ("status", "TEXT DEFAULT 'Active'"),
            ("deleted_at", "TIMESTAMP NULL"),
        ]
        
        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE game_sessions ADD COLUMN {column_name} {column_def}")
                except Exception as e:
                    # Column might already exist in some edge cases
                    pass
        
        # Remove old profit_loss column if it exists (renamed to net_taxable_pl)
        if "profit_loss" in existing_columns and "net_taxable_pl" in existing_columns:
            # Can't drop columns in SQLite easily, but net_taxable_pl will be used going forward
            pass

    def _migrate_daily_sessions_table(self):
        """Remove old tax withholding columns from daily_sessions (moved to daily_date_tax)"""
        # Tax columns are now in daily_date_tax table, not daily_sessions
        # This migration is a no-op, keeping for reference
        pass


    def _migrate_games_table(self):
        """Add new columns to games if they don't exist"""
        cursor = self._connection.cursor()
        cursor.execute("PRAGMA table_info(games)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("actual_rtp", "REAL DEFAULT 0"),
        ]
        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE games ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass

    def _migrate_redemptions_table(self):
        """Add new columns to redemptions if they don't exist"""
        cursor = self._connection.cursor()

        cursor.execute("PRAGMA table_info(redemptions)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("fees", "TEXT DEFAULT '0.00'"),
            ("receipt_date", "TEXT"),
            ("processed", "INTEGER DEFAULT 0"),
            ("more_remaining", "INTEGER DEFAULT 0"),
            ("deleted_at", "TIMESTAMP NULL"),
        ]

        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE redemptions ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass

    def _migrate_redemption_methods_table(self):
        """Add new columns to redemption_methods and remove UNIQUE constraint from name"""
        cursor = self._connection.cursor()

        cursor.execute("PRAGMA table_info(redemption_methods)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # Add columns if missing
        migrations = [
            ("method_type", "TEXT"),
            ("user_id", "INTEGER"),
        ]

        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE redemption_methods ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass

        # Check if name has UNIQUE constraint - if so, need to recreate table
        # SQLite doesn't store constraint names in an easily queryable way,
        # so we check the SQL create statement
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='redemption_methods'")
        row = cursor.fetchone()
        if row and 'UNIQUE' in row[0] and 'name' in row[0]:
            # Need to recreate table without UNIQUE constraint on name
            try:
                # Create new table
                cursor.execute('''
                    CREATE TABLE redemption_methods_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        method_type TEXT,
                        user_id INTEGER,
                        is_active INTEGER DEFAULT 1,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                    )
                ''')
                
                # Copy data
                cursor.execute('''
                    INSERT INTO redemption_methods_new 
                    SELECT id, name, method_type, user_id, is_active, notes, created_at, updated_at
                    FROM redemption_methods
                ''')
                
                # Drop old table
                cursor.execute('DROP TABLE redemption_methods')
                
                # Rename new table
                cursor.execute('ALTER TABLE redemption_methods_new RENAME TO redemption_methods')
                
                self._connection.commit()
            except Exception as e:
                # If migration fails, roll back and continue
                self._connection.rollback()
                pass

    def _migrate_game_rtp_aggregates_table(self):
        """Fix foreign key constraint on game_rtp_aggregates to include ON DELETE CASCADE"""
        cursor = self._connection.cursor()
        
        # Check if foreign key has CASCADE
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='game_rtp_aggregates'")
        result = cursor.fetchone()
        
        # If table exists and doesn't have ON DELETE CASCADE, recreate it
        if result and 'ON DELETE CASCADE' not in result[0]:
            try:
                cursor.execute("PRAGMA foreign_keys=OFF")
                
                # Create new table with proper CASCADE
                cursor.execute('''
                    CREATE TABLE game_rtp_aggregates_new (
                        game_id INTEGER PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
                        total_wager REAL DEFAULT 0,
                        total_delta REAL DEFAULT 0,
                        session_count INTEGER DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Copy existing data
                cursor.execute('''
                    INSERT INTO game_rtp_aggregates_new 
                    SELECT game_id, total_wager, total_delta, session_count, last_updated
                    FROM game_rtp_aggregates
                ''')
                
                # Drop old table and rename new one
                cursor.execute('DROP TABLE game_rtp_aggregates')
                cursor.execute('ALTER TABLE game_rtp_aggregates_new RENAME TO game_rtp_aggregates')
                
                self._connection.commit()
                cursor.execute("PRAGMA foreign_keys=ON")
            except Exception as e:
                # If migration fails, rollback and restore foreign keys
                self._connection.rollback()
                cursor.execute("PRAGMA foreign_keys=ON")
                # Don't raise - allow app to continue with old schema

    def _migrate_expenses_table(self):
        """Add new columns to expenses if they don't exist, and remove DEFAULT constraint from category"""
        cursor = self._connection.cursor()
        cursor.execute("PRAGMA table_info(expenses)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("description", "TEXT"),
            ("category", "TEXT"),
            ("user_id", "INTEGER"),
            ("expense_time", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE expenses ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass
        
        # Remove DEFAULT constraint from category column by recreating table
        # Check if category has DEFAULT constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='expenses'")
        result = cursor.fetchone()
        if result and "category TEXT DEFAULT 'Other Expenses'" in result[0]:
            # Recreate table without DEFAULT constraint
            cursor.execute('''
                CREATE TABLE expenses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_date TEXT NOT NULL,
                    expense_time TEXT,
                    amount TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            ''')
            
            # Copy data
            cursor.execute('''
                INSERT INTO expenses_new 
                SELECT id, expense_date, expense_time, amount, vendor, description, 
                       category, user_id, created_at, updated_at
                FROM expenses
            ''')
            
            # Drop old table and rename new one
            cursor.execute('DROP TABLE expenses')
            cursor.execute('ALTER TABLE expenses_new RENAME TO expenses')
            self._connection.commit()

    def _migrate_purchases_table(self):
        """Add new columns to purchases if they don't exist"""
        cursor = self._connection.cursor()

        cursor.execute("PRAGMA table_info(purchases)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("sc_received", "TEXT DEFAULT '0.00'"),
            ("starting_sc_balance", "TEXT DEFAULT '0.00'"),
            ("cashback_earned", "TEXT DEFAULT '0.00'"),
            ("cashback_is_manual", "INTEGER DEFAULT 0"),
            ("deleted_at", "TIMESTAMP NULL"),
            ("status", "TEXT DEFAULT 'active'"),
        ]

        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE purchases ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass

    def _migrate_unrealized_positions_table(self):
        """Add new columns to unrealized_positions if they don't exist"""
        cursor = self._connection.cursor()
        cursor.execute("PRAGMA table_info(unrealized_positions)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("notes", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP"),
        ]
        for column_name, column_def in migrations:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE unrealized_positions ADD COLUMN {column_name} {column_def}")
                except Exception:
                    pass

    def _normalize_time_fields(self):
        """Backfill NULL/blank time strings to '00:00:00' (safe to rerun)."""
        cursor = self._connection.cursor()

        updates = [
            ("UPDATE purchases SET purchase_time='00:00:00' WHERE purchase_time IS NULL OR TRIM(purchase_time) = ''", ()),
            ("UPDATE redemptions SET redemption_time='00:00:00' WHERE redemption_time IS NULL OR TRIM(redemption_time) = ''", ()),
            ("UPDATE game_sessions SET session_time='00:00:00' WHERE session_time IS NULL OR TRIM(session_time) = ''", ()),
            (
                "UPDATE game_sessions SET end_time='00:00:00' WHERE end_date IS NOT NULL AND (end_time IS NULL OR TRIM(end_time) = '')",
                (),
            ),
        ]

        for q, params in updates:
            try:
                cursor.execute(q, params)
            except Exception:
                continue

        try:
            self._connection.commit()
        except Exception:
            pass
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and return one row as dict"""
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return all rows as list of dicts"""
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute_no_commit(self, query: str, params: tuple = ()) -> int:
        """Execute a statement without committing.

        This exists to support atomic bulk operations that manage their own
        transaction boundary (e.g., Tools CSV import, reset, merge/restore).
        """
        self._assert_writes_allowed(query)
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid

    def executemany_no_commit(self, query: str, params_seq: Sequence[tuple]) -> None:
        """Execute many statements without committing."""
        self._assert_writes_allowed(query)
        cursor = self._connection.cursor()
        cursor.executemany(query, params_seq)
    
    def execute(self, query: str, params: tuple = ()) -> int:
        """Execute query and return last insert ID"""
        self._assert_writes_allowed(query)
        cursor = self._connection.cursor()
        cursor.execute(query, params)
        self._connection.commit()
        self._notify_change()
        return cursor.lastrowid

    def add_change_listener(self, callback):
        if callback not in self._change_listeners:
            self._change_listeners.append(callback)

    def remove_change_listener(self, callback):
        if callback in self._change_listeners:
            self._change_listeners.remove(callback)

    def _notify_change(self):
        for callback in list(self._change_listeners):
            try:
                callback()
            except Exception:
                continue

    def notify_change(self):
        """Public hook to signal that underlying DB contents changed.

        Used when changes are made via external connections (e.g., restore/reset workers)
        so UI listeners can refresh.
        """
        self._notify_change()
    
    def begin_transaction(self):
        """Begin transaction"""
        self._connection.execute("BEGIN")
    
    def commit(self):
        """Commit transaction"""
        self._connection.commit()
    
    def rollback(self):
        """Rollback transaction"""
        self._connection.rollback()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Context manager for an explicit DB transaction.

        IMPORTANT: To preserve atomicity, callers should use
        `execute_no_commit`/`executemany_no_commit` inside this context.
        Using `execute()` inside will auto-commit and break atomicity.
        """
        self.begin_transaction()
        try:
            yield
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()
            self._notify_change()
    
    def log_audit(self, action: str, table_name: str, record_id: Optional[int] = None, 
                  details: Optional[str] = None, user_name: Optional[str] = None):
        """
        Log an audit trail entry.
        
        Args:
            action: Action type (BACKUP, RESTORE, RESET, INSERT, UPDATE, DELETE, etc.)
            table_name: Table or entity affected
            record_id: Optional record ID
            details: Optional details text
            user_name: Optional user name (defaults to 'system')
        """
        self._assert_writes_allowed("INSERT")
        cursor = self._connection.cursor()
        cursor.execute(
            'INSERT INTO audit_log (action, table_name, record_id, details, user_name) VALUES (?, ?, ?, ?, ?)',
            (action, table_name, record_id, details, user_name or 'system')
        )
        self._connection.commit()
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
