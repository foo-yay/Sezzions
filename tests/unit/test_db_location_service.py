from pathlib import Path

import pytest

from services import db_location_service


def _make_sqlite_file(db_path: Path) -> None:
    import sqlite3

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample(name) VALUES ('alpha')")
        conn.commit()
    finally:
        conn.close()


def _row_count(db_path: Path) -> int:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM sample").fetchone()[0]
    finally:
        conn.close()


def test_persist_and_load_db_path(tmp_path, monkeypatch):
    config_file = tmp_path / "runtime_config.json"
    monkeypatch.setattr(db_location_service, "db_location_config_path", lambda: config_file)

    db_location_service.persist_db_path(str(tmp_path / "a" / "sezzions.db"))

    loaded = db_location_service.load_persisted_db_path()
    assert loaded == str((tmp_path / "a" / "sezzions.db").resolve())


def test_relocate_database_copy_and_switch_preserves_source(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "new" / "dest.db"
    _make_sqlite_file(source)

    out = db_location_service.relocate_database(str(source), str(destination), move=False)

    assert out == str(destination.resolve())
    assert source.exists()
    assert destination.exists()
    assert _row_count(source) == 1
    assert _row_count(destination) == 1


def test_relocate_database_raises_when_destination_exists_without_overwrite(tmp_path):
    source = tmp_path / "source.db"
    destination = tmp_path / "dest.db"
    _make_sqlite_file(source)
    _make_sqlite_file(destination)

    with pytest.raises(FileExistsError):
        db_location_service.relocate_database(str(source), str(destination), move=False, overwrite=False)


def test_relocate_database_copy_failure_keeps_source_unchanged(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    destination = tmp_path / "dest" / "dest.db"
    _make_sqlite_file(source)

    def _boom(*args, **kwargs):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(db_location_service.shutil, "copy2", _boom)

    with pytest.raises(OSError, match="simulated copy failure"):
        db_location_service.relocate_database(str(source), str(destination), move=False, overwrite=False)

    assert source.exists()
    assert _row_count(source) == 1
    assert not destination.exists()
