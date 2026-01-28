"""Unit tests for DatabaseManager transaction helpers."""

import pytest


def test_transaction_commits_on_success(test_db):
    test_db.execute("CREATE TABLE t_txn (id INTEGER PRIMARY KEY, v TEXT)")

    with test_db.transaction():
        test_db.execute_no_commit("INSERT INTO t_txn (id, v) VALUES (?, ?)", (1, "ok"))

    row = test_db.fetch_one("SELECT COUNT(*) AS c FROM t_txn")
    assert row["c"] == 1


def test_transaction_rolls_back_on_error(test_db):
    test_db.execute("CREATE TABLE t_txn2 (id INTEGER PRIMARY KEY, v TEXT)")

    with pytest.raises(RuntimeError):
        with test_db.transaction():
            test_db.execute_no_commit(
                "INSERT INTO t_txn2 (id, v) VALUES (?, ?)",
                (1, "will_rollback"),
            )
            raise RuntimeError("boom")

    row = test_db.fetch_one("SELECT COUNT(*) AS c FROM t_txn2")
    assert row["c"] == 0
