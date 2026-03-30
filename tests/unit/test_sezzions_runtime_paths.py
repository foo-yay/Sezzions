from pathlib import Path
import sys

from desktop import sezzions


def test_resolve_db_path_uses_env_override(monkeypatch):
    monkeypatch.setenv("SEZZIONS_DB_PATH", "/tmp/custom-sezzions.db")
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    assert sezzions.resolve_db_path() == "/tmp/custom-sezzions.db"


def test_resolve_db_path_uses_persisted_path_when_no_env(monkeypatch):
    monkeypatch.delenv("SEZZIONS_DB_PATH", raising=False)
    monkeypatch.setattr(sezzions, "load_persisted_db_path", lambda: "/tmp/persisted.db")

    assert sezzions.resolve_db_path() == "/tmp/persisted.db"


def test_resolve_db_path_uses_app_support_when_frozen(monkeypatch, tmp_path):
    monkeypatch.delenv("SEZZIONS_DB_PATH", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sezzions.Path, "home", lambda: tmp_path)

    expected = tmp_path / "Library" / "Application Support" / "Sezzions" / "sezzions.db"
    assert sezzions.resolve_db_path() == str(expected)


def test_ensure_db_parent_exists_creates_directory(tmp_path):
    db_file = tmp_path / "nested" / "dir" / "sezzions.db"

    sezzions.ensure_db_parent_exists(str(db_file))

    assert db_file.parent.exists()
