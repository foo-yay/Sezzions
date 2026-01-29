import pytest

from repositories.database import DatabaseManager, DatabaseWritesBlockedError


def test_writes_are_blocked_when_enabled():
    db = DatabaseManager(":memory:")

    # Sanity: reads still work
    users_before = db.fetch_all("SELECT * FROM users")
    assert isinstance(users_before, list)

    db.set_writes_blocked(True)

    with pytest.raises(DatabaseWritesBlockedError):
        db.execute("INSERT INTO users (name) VALUES (?)", ("blocked",))

    with pytest.raises(DatabaseWritesBlockedError):
        db.execute_no_commit("UPDATE users SET name = name")


def test_writes_work_again_after_unblocked():
    db = DatabaseManager(":memory:")

    db.set_writes_blocked(True)
    with pytest.raises(DatabaseWritesBlockedError):
        db.execute("INSERT INTO users (name) VALUES (?)", ("blocked",))

    db.set_writes_blocked(False)
    db.execute("INSERT INTO users (name) VALUES (?)", ("ok",))

    row = db.fetch_one("SELECT name FROM users WHERE name = ?", ("ok",))
    assert row is not None
    assert row["name"] == "ok"
