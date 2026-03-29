import sqlite3
from pathlib import Path

from services.hosted.sqlite_migration_inventory_service import SQLiteMigrationInventoryService


def test_inspect_database_returns_counts_and_names(tmp_path: Path) -> None:
    db_path = tmp_path / "seed.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO schema_version (version) VALUES (1)")
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, is_active INTEGER DEFAULT 1)"
        )
        connection.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, name TEXT NOT NULL, is_active INTEGER DEFAULT 1)"
        )
        connection.execute("CREATE TABLE purchases (id INTEGER PRIMARY KEY, amount TEXT NOT NULL)")
        connection.execute("INSERT INTO users (name, is_active) VALUES ('Elliot', 1)")
        connection.execute("INSERT INTO sites (name, is_active) VALUES ('Stake', 1)")
        connection.execute("INSERT INTO purchases (amount) VALUES ('100.00')")
        connection.commit()
    finally:
        connection.close()

    inventory = SQLiteMigrationInventoryService().inspect_database(str(db_path))

    table_counts = {table.table_name: table.row_count for table in inventory.tables}
    assert inventory.db_path == str(db_path)
    assert inventory.schema_version_count == 1
    assert inventory.active_user_names == ["Elliot"]
    assert inventory.site_names == ["Stake"]
    assert table_counts["users"] == 1
    assert table_counts["sites"] == 1
    assert table_counts["purchases"] == 1


def test_inspect_database_raises_for_missing_file(tmp_path: Path) -> None:
    missing_db = tmp_path / "missing.db"

    service = SQLiteMigrationInventoryService()

    try:
        service.inspect_database(str(missing_db))
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        assert True
