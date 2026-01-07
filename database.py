"""
database.py - Database and migration management
"""
import sqlite3

class Database:
    def __init__(self, db_path="casino_accounting.db"):
        self.db_path = db_path
        self.init_database()
        self.migrate_database()
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def close(self):
        """Close database (no-op since we use connection pooling)"""
        # Connections are closed after each operation, nothing to do here
        pass
    
    def log_audit(self, action, table_name, record_id=None, details=None, user_name=None):
        """Log an audit event"""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO audit_log (action, table_name, record_id, details, user_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (action, table_name, record_id, details, user_name))
        conn.commit()
        conn.close()
    
    def get_schema_version(self, conn):
        """Get current schema version"""
        c = conn.cursor()
        try:
            c.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            result = c.fetchone()
            return result['version'] if result else 0
        except sqlite3.OperationalError:
            return 0
    
    def set_schema_version(self, conn, version):
        """Set schema version"""
        c = conn.cursor()
        c.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)", (version,))
    
    def migrate_database(self):
        """Run database migrations"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Create schema version table
        c.execute('''CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY, 
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        
        current_version = self.get_schema_version(conn)
        # ensure_derived_session_columns: these columns may be missing in older DBs even if schema_version advanced
        def ensure_derived_session_columns():
            def _add_col(table, coldef):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
                except sqlite3.OperationalError:
                    pass
            _add_col("game_sessions", "session_basis REAL")
            _add_col("game_sessions", "basis_consumed REAL")
            _add_col("game_sessions", "expected_start_total_sc REAL")
            _add_col("game_sessions", "expected_start_redeemable_sc REAL")
            _add_col("game_sessions", "inferred_start_total_delta REAL")
            _add_col("game_sessions", "inferred_start_redeemable_delta REAL")
            _add_col("game_sessions", "delta_total REAL")
            _add_col("game_sessions", "delta_redeem REAL")
            _add_col("game_sessions", "net_taxable_pl REAL")
        ensure_derived_session_columns()
        # ensure core columns that may be missing in older DBs
        def ensure_core_columns():
            def _add_col(table, coldef):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
                except sqlite3.OperationalError:
                    pass
            _add_col("sites", "sc_rate REAL DEFAULT 1.0")
            _add_col("cards", "last_four TEXT")
            _add_col("purchases", "notes TEXT")
            _add_col("purchases", "processed INTEGER DEFAULT 0")
            _add_col("purchases", "status TEXT DEFAULT 'active'")
            _add_col("redemptions", "more_remaining INTEGER DEFAULT 0")
            _add_col("redemptions", "notes TEXT")
            _add_col("game_sessions", "total_taxable REAL")
            _add_col("game_sessions", "sc_change REAL")
            _add_col("game_sessions", "dollar_value REAL")
            _add_col("game_sessions", "basis_bonus REAL")
            _add_col("game_sessions", "gameplay_pnl REAL")
            _add_col("game_sessions", "game_name TEXT")
            _add_col("game_sessions", "wager_amount REAL")
            _add_col("game_sessions", "rtp REAL")
        ensure_core_columns()
        try:
            c.execute("UPDATE sites SET sc_rate = 1.0 WHERE sc_rate IS NULL")
        except sqlite3.OperationalError:
            pass
        conn.commit()

        
        # Migration 1: Add user_id to cards
        if current_version < 1:
            try:
                c.execute("SELECT user_id FROM cards LIMIT 1")
            except sqlite3.OperationalError:
                # Get default user or use 1
                c.execute("SELECT id FROM users WHERE active = 1 LIMIT 1")
                default_user = c.fetchone()
                default_user_id = default_user['id'] if default_user else 1
                
                c.execute("ALTER TABLE cards ADD COLUMN user_id INTEGER")
                c.execute("UPDATE cards SET user_id = ?", (default_user_id,))
            
            self.set_schema_version(conn, 1)
            conn.commit()
        
        # Migration 2: Add starting_sc_balance to purchases
        if current_version < 2:
            try:
                c.execute("SELECT starting_sc_balance FROM purchases LIMIT 1")
            except sqlite3.OperationalError:
                c.execute("ALTER TABLE purchases ADD COLUMN starting_sc_balance REAL DEFAULT 0.0")
            
            self.set_schema_version(conn, 2)
            conn.commit()
        
        # Migration 3: Add processed flag and notes fields
        if current_version < 3:
            # Add processed flag to redemptions
            try:
                c.execute("SELECT processed FROM redemptions LIMIT 1")
            except sqlite3.OperationalError:
                c.execute("ALTER TABLE redemptions ADD COLUMN processed INTEGER DEFAULT 0")
            
            # Add notes to purchases
            try:
                c.execute("SELECT notes FROM purchases LIMIT 1")
            except sqlite3.OperationalError:
                c.execute("ALTER TABLE purchases ADD COLUMN notes TEXT")
            
            # Add notes to redemptions
            try:
                c.execute("SELECT notes FROM redemptions LIMIT 1")
            except sqlite3.OperationalError:
                c.execute("ALTER TABLE redemptions ADD COLUMN notes TEXT")
            
            # Add notes to site_sessions
            try:
                c.execute("SELECT notes FROM site_sessions LIMIT 1")
            except sqlite3.OperationalError:
                c.execute("ALTER TABLE site_sessions ADD COLUMN notes TEXT")
            
            self.set_schema_version(conn, 3)
            conn.commit()

        # Migration 4: Add derived session accounting columns to game_sessions
        if current_version < 4:
            # Add columns if missing (safe/idempotent)
            def _add_col(table, coldef):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
                except sqlite3.OperationalError:
                    pass  # column likely exists

            _add_col("game_sessions", "session_basis REAL")
            _add_col("game_sessions", "basis_consumed REAL")
            _add_col("game_sessions", "expected_start_total_sc REAL")
            _add_col("game_sessions", "expected_start_redeemable_sc REAL")
            _add_col("game_sessions", "inferred_start_total_delta REAL")
            _add_col("game_sessions", "inferred_start_redeemable_delta REAL")
            _add_col("game_sessions", "delta_total REAL")
            _add_col("game_sessions", "delta_redeem REAL")
            _add_col("game_sessions", "net_taxable_pl REAL")

            self.set_schema_version(conn, 4)
            conn.commit()

        # Migration 5: Add missing core columns used by the app
        if current_version < 5:
            def _add_col(table, coldef):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
                except sqlite3.OperationalError:
                    pass

            _add_col("sites", "sc_rate REAL DEFAULT 1.0")
            _add_col("cards", "last_four TEXT")

            _add_col("purchases", "notes TEXT")
            _add_col("purchases", "processed INTEGER DEFAULT 0")
            _add_col("purchases", "status TEXT DEFAULT 'active'")

            _add_col("redemptions", "more_remaining INTEGER DEFAULT 0")
            _add_col("redemptions", "notes TEXT")

            _add_col("game_sessions", "start_time TEXT DEFAULT '00:00:00'")
            _add_col("game_sessions", "end_date DATE")
            _add_col("game_sessions", "end_time TEXT")
            _add_col("game_sessions", "freebies_detected REAL")
            _add_col("game_sessions", "status TEXT DEFAULT 'Active'")
            _add_col("game_sessions", "notes TEXT")
            _add_col("game_sessions", "processed INTEGER DEFAULT 0")
            _add_col("game_sessions", "total_taxable REAL")
            _add_col("game_sessions", "sc_change REAL")
            _add_col("game_sessions", "dollar_value REAL")
            _add_col("game_sessions", "basis_bonus REAL")
            _add_col("game_sessions", "gameplay_pnl REAL")

            _add_col("daily_tax_sessions", "total_other_income REAL DEFAULT 0.0")
            _add_col("daily_tax_sessions", "total_session_pnl REAL DEFAULT 0.0")
            _add_col("daily_tax_sessions", "net_daily_pnl REAL DEFAULT 0.0")
            _add_col("daily_tax_sessions", "status TEXT")
            _add_col("daily_tax_sessions", "num_game_sessions INTEGER DEFAULT 0")
            _add_col("daily_tax_sessions", "num_other_income_items INTEGER DEFAULT 0")
            _add_col("daily_tax_sessions", "notes TEXT")

            _add_col("other_income", "notes TEXT")

            try:
                c.execute("UPDATE sites SET sc_rate = 1.0 WHERE sc_rate IS NULL")
            except sqlite3.OperationalError:
                pass

            self.set_schema_version(conn, 5)
            conn.commit()

        # Migration 6: Add games tables and session fields
        if current_version < 6:
            c.execute('''CREATE TABLE IF NOT EXISTS game_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1)''')
            c.execute('''CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                game_type_id INTEGER,
                rtp REAL,
                notes TEXT,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (game_type_id) REFERENCES game_types(id))''')

            def _add_col(table, coldef):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
                except sqlite3.OperationalError:
                    pass

            _add_col("game_sessions", "game_name TEXT")
            _add_col("game_sessions", "wager_amount REAL")
            _add_col("game_sessions", "rtp REAL")

            c.execute("SELECT COUNT(*) as cnt FROM game_types")
            if c.fetchone()["cnt"] == 0:
                for name in ("Slots", "Table Games", "Poker", "Other"):
                    c.execute("INSERT OR IGNORE INTO game_types (name, active) VALUES (?, 1)", (name,))

            self.set_schema_version(conn, 6)
            conn.commit()
        
        conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1)''')
        
        # Sites table
        c.execute('''CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sc_rate REAL DEFAULT 1.0,
            active INTEGER DEFAULT 1)''')
        
        # Cards table
        c.execute('''CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_four TEXT,
            cashback_rate REAL DEFAULT 0.0,
            user_id INTEGER,
            active INTEGER DEFAULT 1)''')
        
        # Redemption methods table
        c.execute('''CREATE TABLE IF NOT EXISTS redemption_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            method_type TEXT,
            user_id INTEGER,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id))''')

        # Game types table
        c.execute('''CREATE TABLE IF NOT EXISTS game_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1)''')

        # Games table
        c.execute('''CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            game_type_id INTEGER,
            rtp REAL,
            notes TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (game_type_id) REFERENCES game_types(id))''')

        # Seed default game types if empty
        c.execute("SELECT COUNT(*) as cnt FROM game_types")
        if c.fetchone()["cnt"] == 0:
            for name in ("Slots", "Table Games", "Poker", "Other"):
                c.execute("INSERT OR IGNORE INTO game_types (name, active) VALUES (?, 1)", (name,))
        
        # Purchases table
        c.execute('''CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_date DATE NOT NULL,
            purchase_time TEXT DEFAULT '00:00:00',
            site_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            sc_received REAL NOT NULL,
            starting_sc_balance REAL DEFAULT 0.0,
            card_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            remaining_amount REAL NOT NULL,
            notes TEXT,
            processed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (card_id) REFERENCES cards(id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Site sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS site_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            start_date DATE NOT NULL,
            status TEXT DEFAULT 'Active',
            total_buyin REAL DEFAULT 0.0,
            total_redeemed REAL DEFAULT 0.0,
            notes TEXT,
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Redemptions table
        c.execute('''CREATE TABLE IF NOT EXISTS redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_session_id INTEGER,
            site_id INTEGER NOT NULL,
            redemption_date DATE NOT NULL,
            redemption_time TEXT DEFAULT '00:00:00',
            amount REAL NOT NULL,
            receipt_date DATE,
            redemption_method_id INTEGER,
            processed INTEGER DEFAULT 0,
            is_free_sc INTEGER DEFAULT 0,
            more_remaining INTEGER DEFAULT 0,
            user_id INTEGER NOT NULL,
            notes TEXT,
            FOREIGN KEY (site_session_id) REFERENCES site_sessions(id),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (redemption_method_id) REFERENCES redemption_methods(id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Tax sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS tax_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE NOT NULL,
            site_id INTEGER NOT NULL,
            redemption_id INTEGER NOT NULL,
            cost_basis REAL NOT NULL,
            payout REAL NOT NULL,
            net_pl REAL NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (redemption_id) REFERENCES redemptions(id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')

        # Game sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date DATE NOT NULL,
            start_time TEXT DEFAULT '00:00:00',
            end_date DATE,
            end_time TEXT,
            site_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            game_type TEXT,
            game_name TEXT,
            wager_amount REAL,
            rtp REAL,
            starting_sc_balance REAL DEFAULT 0.0,
            ending_sc_balance REAL,
            starting_redeemable_sc REAL,
            ending_redeemable_sc REAL,
            freebies_detected REAL,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            processed INTEGER DEFAULT 0,
            session_basis REAL,
            basis_consumed REAL,
            expected_start_total_sc REAL,
            expected_start_redeemable_sc REAL,
            inferred_start_total_delta REAL,
            inferred_start_redeemable_delta REAL,
            delta_total REAL,
            delta_redeem REAL,
            net_taxable_pl REAL,
            total_taxable REAL,
            sc_change REAL,
            dollar_value REAL,
            basis_bonus REAL,
            gameplay_pnl REAL,
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')

        # Other income table
        c.execute('''CREATE TABLE IF NOT EXISTS other_income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            user_id INTEGER,
            game_session_id INTEGER,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (game_session_id) REFERENCES game_sessions(id))''')

        # Daily tax sessions table
        c.execute('''CREATE TABLE IF NOT EXISTS daily_tax_sessions (
            session_date DATE NOT NULL,
            user_id INTEGER NOT NULL,
            total_other_income REAL DEFAULT 0.0,
            total_session_pnl REAL DEFAULT 0.0,
            net_daily_pnl REAL DEFAULT 0.0,
            status TEXT,
            num_game_sessions INTEGER DEFAULT 0,
            num_other_income_items INTEGER DEFAULT 0,
            notes TEXT,
            PRIMARY KEY (session_date, user_id),
            FOREIGN KEY (user_id) REFERENCES users(id))''')

        # Settings table
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT)''')

        # Legacy SC conversion rates table (optional fallback)
        c.execute('''CREATE TABLE IF NOT EXISTS sc_conversion_rates (
            site_id INTEGER PRIMARY KEY,
            rate REAL NOT NULL,
            FOREIGN KEY (site_id) REFERENCES sites(id))''')
        
        # Expenses table
        c.execute('''CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date DATE NOT NULL,
            amount REAL NOT NULL,
            vendor TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'Other Expenses',
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id))''')
        
        # Audit log table
        c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            details TEXT,
            user_name TEXT)''')
        
        # Ensure default user exists
        c.execute("SELECT COUNT(*) as count FROM users")
        if c.fetchone()['count'] == 0:
            c.execute("INSERT INTO users (name) VALUES (?)", ("Default User",))
        
        # Migration: Add user_id to redemption_methods if it doesn't exist
        c.execute("PRAGMA table_info(redemption_methods)")
        columns = [col[1] for col in c.fetchall()]
        if 'user_id' not in columns:
            c.execute("ALTER TABLE redemption_methods ADD COLUMN user_id INTEGER")
        
        # Migration: Add purchase_time to purchases if it doesn't exist
        c.execute("PRAGMA table_info(purchases)")
        columns = [col[1] for col in c.fetchall()]
        if 'purchase_time' not in columns:
            c.execute("ALTER TABLE purchases ADD COLUMN purchase_time TEXT DEFAULT '00:00:00'")
        
        # Migration: Add redemption_time to redemptions if it doesn't exist
        c.execute("PRAGMA table_info(redemptions)")
        columns = [col[1] for col in c.fetchall()]
        if 'redemption_time' not in columns:
            c.execute("ALTER TABLE redemptions ADD COLUMN redemption_time TEXT DEFAULT '00:00:00'")
        
        # Migration: Add ending_redeemable_sc to game_sessions if it doesn't exist
        c.execute("PRAGMA table_info(game_sessions)")
        columns = [col[1] for col in c.fetchall()]
        if 'ending_redeemable_sc' not in columns:
            c.execute("ALTER TABLE game_sessions ADD COLUMN ending_redeemable_sc REAL")
            # For existing closed sessions, set redeemable = total (assume fully played through)
            c.execute("UPDATE game_sessions SET ending_redeemable_sc = ending_sc_balance WHERE status = 'Closed' AND ending_sc_balance IS NOT NULL")
        
        # Migration: Add starting_redeemable_sc to game_sessions if it doesn't exist
        c.execute("PRAGMA table_info(game_sessions)")
        columns = [col[1] for col in c.fetchall()]
        if 'starting_redeemable_sc' not in columns:
            c.execute("ALTER TABLE game_sessions ADD COLUMN starting_redeemable_sc REAL")
            # For existing sessions, set starting_redeemable = starting_total (assume fully unlocked)
            c.execute("UPDATE game_sessions SET starting_redeemable_sc = starting_sc_balance WHERE starting_sc_balance IS NOT NULL")
        
        # Migration: Add status to purchases for dormant tracking
        c.execute("PRAGMA table_info(purchases)")
        columns = [col[1] for col in c.fetchall()]
        if 'status' not in columns:
            c.execute("ALTER TABLE purchases ADD COLUMN status TEXT DEFAULT 'active'")
            # All existing purchases default to 'active'
        
        conn.commit()
        conn.close()
