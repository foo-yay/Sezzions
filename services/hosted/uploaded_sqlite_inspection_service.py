"""Read-only inspection of uploaded SQLite files for hosted migration planning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from services.hosted.sqlite_migration_inventory_service import (
    SQLiteMigrationInventory,
    SQLiteMigrationInventoryService,
)


@dataclass(frozen=True)
class HostedUploadedSQLiteInspectionSummary:
    status: str
    detail: str
    uploaded_filename: str
    inventory: SQLiteMigrationInventory | None

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "detail": self.detail,
            "uploaded_filename": self.uploaded_filename,
            "inventory": self.inventory.to_dict() if self.inventory else None,
        }


class HostedUploadedSQLiteInspectionService:
    def __init__(self, *, inventory_service: SQLiteMigrationInventoryService | None = None) -> None:
        self.inventory_service = inventory_service or SQLiteMigrationInventoryService()

    def inspect_upload(self, *, filename: str, fileobj) -> HostedUploadedSQLiteInspectionSummary:
        uploaded_filename = (filename or "uploaded.sqlite").strip() or "uploaded.sqlite"

        with NamedTemporaryFile(prefix="sezzions-upload-", suffix=".db", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            while True:
                chunk = fileobj.read(1024 * 1024)
                if not chunk:
                    break
                temp_file.write(chunk)

        try:
            if temp_path.stat().st_size == 0:
                raise ValueError("Uploaded SQLite file is empty.")

            try:
                inventory = self.inventory_service.inspect_database(str(temp_path))
            except ValueError:
                raise
            except Exception as exc:
                message = str(exc).lower()
                if "file is not a database" in message or "database disk image is malformed" in message:
                    raise ValueError("Uploaded file is not a readable SQLite database.") from exc
                raise ValueError("Uploaded SQLite inspection failed.") from exc

            return HostedUploadedSQLiteInspectionSummary(
                status="ready",
                detail="Uploaded SQLite inventory is ready.",
                uploaded_filename=uploaded_filename,
                inventory=inventory,
            )
        finally:
            temp_path.unlink(missing_ok=True)