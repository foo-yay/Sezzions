import io
import sqlite3
from pathlib import Path

import pytest

from services.hosted.uploaded_sqlite_inspection_service import (
    HostedUploadedSQLiteInspectionService,
)


def _build_sqlite_bytes(tmp_path: Path) -> bytes:
    db_path = tmp_path / "upload.db"
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
        connection.execute("INSERT INTO users (name, is_active) VALUES ('Elliot', 1)")
        connection.execute("INSERT INTO sites (name, is_active) VALUES ('Stake', 1)")
        connection.commit()
    finally:
        connection.close()
    return db_path.read_bytes()


def test_inspect_upload_returns_inventory_and_cleans_up_temp_file(tmp_path: Path) -> None:
    sqlite_bytes = _build_sqlite_bytes(tmp_path)
    seen_paths: list[str] = []

    class TrackingInventoryService:
        def inspect_database(self, db_path: str):
            seen_paths.append(db_path)
            from services.hosted.sqlite_migration_inventory_service import SQLiteMigrationInventoryService

            return SQLiteMigrationInventoryService().inspect_database(db_path)

    summary = HostedUploadedSQLiteInspectionService(
        inventory_service=TrackingInventoryService()
    ).inspect_upload(filename="sezzions.db", fileobj=io.BytesIO(sqlite_bytes))

    assert summary.status == "ready"
    assert summary.uploaded_filename == "sezzions.db"
    assert summary.inventory is not None
    assert summary.inventory.active_user_names == ["Elliot"]
    assert seen_paths
    assert Path(seen_paths[0]).exists() is False


def test_inspect_upload_rejects_empty_upload() -> None:
    service = HostedUploadedSQLiteInspectionService()

    with pytest.raises(ValueError, match="Uploaded SQLite file is empty"):
        service.inspect_upload(filename="empty.db", fileobj=io.BytesIO(b""))


def test_inspect_upload_raises_safe_error_for_invalid_sqlite_bytes() -> None:
    service = HostedUploadedSQLiteInspectionService()

    with pytest.raises(ValueError, match="Uploaded file is not a readable SQLite database"):
        service.inspect_upload(filename="bad.db", fileobj=io.BytesIO(b"not-a-sqlite-db"))


def test_inspect_upload_cleans_up_temp_file_when_inspection_fails(tmp_path: Path) -> None:
    sqlite_bytes = _build_sqlite_bytes(tmp_path)
    seen_paths: list[str] = []

    class ExplodingInventoryService:
        def inspect_database(self, db_path: str):
            seen_paths.append(db_path)
            raise RuntimeError("boom")

    service = HostedUploadedSQLiteInspectionService(
        inventory_service=ExplodingInventoryService()
    )

    with pytest.raises(ValueError, match="Uploaded SQLite inspection failed"):
        service.inspect_upload(filename="sezzions.db", fileobj=io.BytesIO(sqlite_bytes))

    assert seen_paths
    assert Path(seen_paths[0]).exists() is False