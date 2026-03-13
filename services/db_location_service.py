"""Database location configuration and migration helpers."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


def default_db_path() -> str:
    if getattr(sys, "frozen", False):
        app_support_dir = Path.home() / "Library" / "Application Support" / "Sezzions"
        return str(app_support_dir / "sezzions.db")

    project_root = Path(__file__).resolve().parent.parent
    return str(project_root / "sezzions.db")


def settings_file_path() -> Path:
    if getattr(sys, "frozen", False):
        config_dir = Path.home() / "Library" / "Application Support" / "Sezzions"
        return config_dir / "settings.json"

    project_root = Path(__file__).resolve().parent.parent
    return project_root / "settings.json"


def legacy_runtime_config_path() -> Path:
    if getattr(sys, "frozen", False):
        config_dir = Path.home() / "Library" / "Application Support" / "Sezzions"
        return config_dir / "runtime_config.json"

    project_root = Path(__file__).resolve().parent.parent
    return project_root / "runtime_config.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_persisted_db_path() -> str | None:
    payload = _load_json(settings_file_path())
    raw_path = str(payload.get("db_path", "")).strip()
    if raw_path:
        return raw_path

    legacy_path = str(_load_json(legacy_runtime_config_path()).get("db_path", "")).strip()
    if not legacy_path:
        return None

    persist_db_path(legacy_path)
    return str(Path(legacy_path).expanduser().resolve())


def persist_db_path(db_path: str) -> None:
    path = Path(db_path).expanduser().resolve()
    config_path = settings_file_path()
    payload = _load_json(config_path)
    payload["db_path"] = str(path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def has_persisted_db_path() -> bool:
    return load_persisted_db_path() is not None


def relocate_database(
    source_db_path: str,
    destination_db_path: str,
    *,
    move: bool = False,
    overwrite: bool = False,
) -> str:
    source = Path(source_db_path).expanduser().resolve()
    destination = Path(destination_db_path).expanduser().resolve()

    if source == destination:
        raise ValueError("Source and destination database paths are the same")
    if not source.exists():
        raise FileNotFoundError(f"Source database does not exist: {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination database already exists: {destination}")

    temp_destination = destination.with_suffix(destination.suffix + ".tmp-copy")
    if temp_destination.exists():
        temp_destination.unlink()

    try:
        shutil.copy2(source, temp_destination)
        _verify_sqlite_file(temp_destination)

        if destination.exists():
            destination.unlink()
        os.replace(temp_destination, destination)

        if move:
            source.unlink()
    except Exception:
        if temp_destination.exists():
            try:
                temp_destination.unlink()
            except Exception:
                pass
        if move and destination.exists() and source.exists():
            try:
                destination.unlink()
            except Exception:
                pass
        raise

    return str(destination)


def _verify_sqlite_file(db_file: Path) -> None:
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA schema_version")
    finally:
        conn.close()
