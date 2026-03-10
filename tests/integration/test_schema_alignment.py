"""
Integration tests for Issue #136 — schema/spec alignment.

Verifies that a fresh DatabaseManager(':memory:') contains all canonical
columns for daily_sessions, game_sessions, and expenses.
These are the columns that existed in real upgraded databases but were
missing from the fresh-schema CREATE TABLE statements.
"""

import pytest

from repositories.database import DatabaseManager


@pytest.fixture
def fresh_db():
    """Fresh in-memory database — no legacy migration paths triggered."""
    db = DatabaseManager(":memory:")
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _columns(db: DatabaseManager, table: str) -> set:
    cursor = db._connection.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Happy-path: canonical columns present in fresh DB
# ---------------------------------------------------------------------------

class TestDailySessionsFreshSchema:
    """daily_sessions must include 'notes' on a fresh DB."""

    def test_notes_column_present(self, fresh_db):
        cols = _columns(fresh_db, "daily_sessions")
        assert "notes" in cols, (
            "daily_sessions.notes missing from fresh schema — "
            "DailySession model and repository both use it"
        )

    def test_core_columns_intact(self, fresh_db):
        """Sanity: core columns must still be present."""
        cols = _columns(fresh_db, "daily_sessions")
        for col in ("session_date", "user_id", "total_other_income",
                    "total_session_pnl", "net_daily_pnl", "status",
                    "num_game_sessions", "num_other_income_items"):
            assert col in cols, f"daily_sessions.{col} unexpectedly missing"


class TestGameSessionsFreshSchema:
    """game_sessions must include all three tax-withholding columns on a fresh DB."""

    REQUIRED_TAX_COLS = (
        "tax_withholding_rate_pct",
        "tax_withholding_is_custom",
        "tax_withholding_amount",
    )

    def test_tax_withholding_columns_present(self, fresh_db):
        cols = _columns(fresh_db, "game_sessions")
        for col in self.REQUIRED_TAX_COLS:
            assert col in cols, (
                f"game_sessions.{col} missing from fresh schema — "
                f"GameSession model declares it"
            )

    def test_wager_and_rtp_intact(self, fresh_db):
        """Regression guard: wager_amount and rtp must not be dropped."""
        cols = _columns(fresh_db, "game_sessions")
        assert "wager_amount" in cols
        assert "rtp" in cols

    def test_core_columns_intact(self, fresh_db):
        cols = _columns(fresh_db, "game_sessions")
        for col in ("id", "user_id", "site_id", "session_date", "notes",
                    "net_taxable_pl", "status"):
            assert col in cols, f"game_sessions.{col} unexpectedly missing"


class TestExpensesFreshSchema:
    """expenses must include expense_entry_time_zone on a fresh DB."""

    def test_expense_entry_time_zone_present(self, fresh_db):
        cols = _columns(fresh_db, "expenses")
        assert "expense_entry_time_zone" in cols, (
            "expenses.expense_entry_time_zone missing from fresh schema — "
            "Expense model declares it"
        )

    def test_core_columns_intact(self, fresh_db):
        cols = _columns(fresh_db, "expenses")
        for col in ("id", "expense_date", "amount", "vendor",
                    "description", "category", "user_id",
                    "expense_time", "created_at", "updated_at"):
            assert col in cols, f"expenses.{col} unexpectedly missing"


class TestSitesFreshSchema:
    """sites must include playthrough_requirement on a fresh DB."""

    def test_playthrough_requirement_present(self, fresh_db):
        cols = _columns(fresh_db, "sites")
        assert "playthrough_requirement" in cols, (
            "sites.playthrough_requirement missing from fresh schema — "
            "Site model/repository now require it"
        )


# ---------------------------------------------------------------------------
# Edge-cases
# ---------------------------------------------------------------------------

class TestDailySessionsMigration:
    """Migration path: verify _migrate_daily_sessions_table adds 'notes' to an existing DB."""

    def test_notes_added_by_migration(self, tmp_path):
        """
        Bootstrap a full DB, then rebuild daily_sessions WITHOUT 'notes',
        then call the migration directly and confirm 'notes' is re-added.
        """
        db = DatabaseManager(str(tmp_path / "migrate_test.db"))
        conn = db._connection

        # Rebuild daily_sessions without the 'notes' column to simulate old schema
        conn.execute("ALTER TABLE daily_sessions RENAME TO daily_sessions_bak")
        conn.execute("""
            CREATE TABLE daily_sessions (
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
        """)
        conn.execute("""
            INSERT INTO daily_sessions
                (session_date, user_id, total_other_income, total_session_pnl,
                 net_daily_pnl, status, num_game_sessions, num_other_income_items)
            SELECT session_date, user_id, total_other_income, total_session_pnl,
                   net_daily_pnl, status, num_game_sessions, num_other_income_items
            FROM daily_sessions_bak
        """)
        conn.execute("DROP TABLE daily_sessions_bak")
        conn.commit()

        # Run the migration
        db._migrate_daily_sessions_table()
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(daily_sessions)")
        cols = {row[1] for row in cursor.fetchall()}
        db.close()

        assert "notes" in cols, "Migration failed to add daily_sessions.notes"


class TestSitesMigration:
    """Migration path: verify sites migration adds playthrough_requirement."""

    def test_playthrough_requirement_added_by_migration(self, tmp_path):
        db = DatabaseManager(str(tmp_path / "migrate_sites_test.db"))
        conn = db._connection

        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE sites RENAME TO sites_bak")
        conn.execute(
            """
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT,
                sc_rate REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sites (id, name, url, sc_rate, is_active, notes, created_at, updated_at)
            SELECT id, name, url, sc_rate, is_active, notes, created_at, updated_at
            FROM sites_bak
            """
        )
        conn.execute("DROP TABLE sites_bak")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        db._migrate_sites_table()
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sites)")
        cols = {row[1] for row in cursor.fetchall()}

        cursor.execute("INSERT INTO sites (name) VALUES (?)", ("Migrated Site",))
        row = conn.execute(
            "SELECT playthrough_requirement FROM sites WHERE name = ?",
            ("Migrated Site",),
        ).fetchone()
        db.close()

        assert "playthrough_requirement" in cols
        assert row is not None
        assert float(row[0]) == pytest.approx(1.0)


class TestGameSessionsMigration:
    """Migration path: verify ALTER TABLE adds tax_withholding columns to existing DB."""

    REQUIRED_TAX_COLS = (
        "tax_withholding_rate_pct",
        "tax_withholding_is_custom",
        "tax_withholding_amount",
    )

    def test_tax_withholding_added_by_migration(self, tmp_path):
        """
        Bootstrap a full DB, drop tax_withholding columns by rebuilding
        game_sessions, then run the migration and confirm columns are re-added.
        """
        db = DatabaseManager(str(tmp_path / "migrate_gs_test.db"))
        conn = db._connection

        # Rebuild game_sessions WITHOUT tax_withholding columns
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE game_sessions RENAME TO game_sessions_bak")
        conn.execute("""
            CREATE TABLE game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                game_id INTEGER,
                game_type_id INTEGER,
                session_date TEXT NOT NULL,
                session_time TEXT DEFAULT '00:00:00',
                start_entry_time_zone TEXT,
                end_date TEXT,
                end_time TEXT,
                end_entry_time_zone TEXT,
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
                updated_at TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT INTO game_sessions
                (id, user_id, site_id, game_id, game_type_id, session_date,
                 session_time, start_entry_time_zone, end_date, end_time,
                 end_entry_time_zone, starting_balance, ending_balance,
                 starting_redeemable, ending_redeemable, wager_amount, rtp,
                 purchases_during, redemptions_during, expected_start_total,
                 expected_start_redeemable, discoverable_sc, delta_total,
                 delta_redeem, session_basis, basis_consumed, net_taxable_pl,
                 status, notes, created_at, updated_at)
            SELECT id, user_id, site_id, game_id, game_type_id, session_date,
                   session_time, start_entry_time_zone, end_date, end_time,
                   end_entry_time_zone, starting_balance, ending_balance,
                   starting_redeemable, ending_redeemable, wager_amount, rtp,
                   purchases_during, redemptions_during, expected_start_total,
                   expected_start_redeemable, discoverable_sc, delta_total,
                   delta_redeem, session_basis, basis_consumed, net_taxable_pl,
                   status, notes, created_at, updated_at
            FROM game_sessions_bak
        """)
        conn.execute("DROP TABLE game_sessions_bak")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        # Confirm columns are gone before migration
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(game_sessions)")
        pre_cols = {row[1] for row in cursor.fetchall()}
        for col in self.REQUIRED_TAX_COLS:
            assert col not in pre_cols, f"{col} should not be present before migration"

        # Run the migration (pass existing_columns from fresh state)
        db._migrate_game_sessions_table()
        conn.commit()

        cursor.execute("PRAGMA table_info(game_sessions)")
        post_cols = {row[1] for row in cursor.fetchall()}
        db.close()

        for col in self.REQUIRED_TAX_COLS:
            assert col in post_cols, (
                f"Migration failed to add game_sessions.{col}"
            )


# ---------------------------------------------------------------------------
# Failure injection
# ---------------------------------------------------------------------------

class TestExpensesRebuildPreservesTimezone:
    """The expenses migration rebuild must not lose expense_entry_time_zone data."""

    def test_timezone_data_preserved_through_rebuild(self, tmp_path):
        """
        If expenses table has old DEFAULT 'Other Expenses' constraint,
        the rebuild (expenses_new) must preserve expense_entry_time_zone.
        """
        db = DatabaseManager(str(tmp_path / "expenses_tz_test.db"))
        conn = db._connection

        # Rebuild expenses to mimic the old DEFAULT 'Other Expenses' schema
        # with a known timezone value
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE expenses RENAME TO expenses_legacy_bak")
        conn.execute("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                expense_time TEXT,
                amount TEXT NOT NULL,
                vendor TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'Other Expenses',
                user_id INTEGER,
                expense_entry_time_zone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            INSERT INTO expenses (expense_date, amount, vendor, expense_entry_time_zone)
            VALUES ('2024-01-01', '10.00', 'Test Vendor', 'America/New_York')
        """)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        # Run the migration — should rebuild without stripping timezone
        db._migrate_expenses_table()
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("SELECT expense_entry_time_zone FROM expenses WHERE id = 1")
        row = cursor.fetchone()
        db.close()

        assert row is not None, "Expense row lost during rebuild"
        assert row[0] == "America/New_York", (
            f"expense_entry_time_zone data lost during rebuild; got {row[0]!r}"
        )

    def test_expense_entry_time_zone_in_rebuilt_schema(self, tmp_path):
        """Rebuilt expenses table must still have expense_entry_time_zone column."""
        db = DatabaseManager(str(tmp_path / "expenses_tz_schema_test.db"))
        conn = db._connection

        # Force the rebuild path by putting the old DEFAULT back
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("ALTER TABLE expenses RENAME TO expenses_old_bak")
        conn.execute("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                expense_time TEXT,
                amount TEXT NOT NULL,
                vendor TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'Other Expenses',
                user_id INTEGER,
                expense_entry_time_zone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()

        db._migrate_expenses_table()
        conn.commit()

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(expenses)")
        cols = {row[1] for row in cursor.fetchall()}
        db.close()

        assert "expense_entry_time_zone" in cols, (
            "expenses.expense_entry_time_zone lost after migration rebuild"
        )
