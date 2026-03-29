"""Inventory the current SQLite database before hosted migration/import."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sqlite3
from typing import Dict, List


@dataclass(frozen=True)
class TableInventory:
    table_name: str
    row_count: int


@dataclass(frozen=True)
class SQLiteMigrationInventory:
    db_path: str
    db_size_bytes: int
    schema_version_count: int
    tables: List[TableInventory]
    active_user_names: List[str]
    site_names: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "db_path": self.db_path,
            "db_size_bytes": self.db_size_bytes,
            "schema_version_count": self.schema_version_count,
            "tables": [asdict(table) for table in self.tables],
            "active_user_names": self.active_user_names,
            "site_names": self.site_names,
        }


class SQLiteMigrationInventoryService:
    """Read-only inspection used to plan SQLite to hosted migration work."""

    TRACKED_TABLES = (
        "users",
        "sites",
        "cards",
        "redemption_methods",
        "game_types",
        "games",
        "purchases",
        "redemptions",
        "game_sessions",
        "expenses",
        "account_adjustments",
        "realized_transactions",
        "unrealized_positions",
    )

    def inspect_database(self, db_path: str) -> SQLiteMigrationInventory:
        path = Path(db_path)
        if not path.exists():
            raise FileNotFoundError(f"SQLite database not found: {db_path}")

        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            tables = [
                TableInventory(table_name=table_name, row_count=self._count_rows(connection, table_name))
                for table_name in self._existing_tables(connection)
            ]
            active_user_names = self._read_name_list(
                connection,
                "SELECT name FROM users WHERE is_active = 1 ORDER BY name",
            )
            site_names = self._read_name_list(
                connection,
                "SELECT name FROM sites WHERE is_active = 1 ORDER BY name",
            )
            schema_version_count = self._count_rows(connection, "schema_version") if self._table_exists(connection, "schema_version") else 0
            return SQLiteMigrationInventory(
                db_path=str(path),
                db_size_bytes=path.stat().st_size,
                schema_version_count=schema_version_count,
                tables=tables,
                active_user_names=active_user_names,
                site_names=site_names,
            )
        finally:
            connection.close()

    def _existing_tables(self, connection: sqlite3.Connection) -> List[str]:
        return [
            table_name
            for table_name in self.TRACKED_TABLES
            if self._table_exists(connection, table_name)
        ]

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
        row = connection.execute(f"SELECT COUNT(*) AS row_count FROM {table_name}").fetchone()
        return int(row["row_count"]) if row else 0

    @staticmethod
    def _read_name_list(connection: sqlite3.Connection, query: str) -> List[str]:
        try:
            return [str(row["name"]) for row in connection.execute(query).fetchall()]
        except sqlite3.OperationalError:
            return []
