"""UI regression test for Realized tab local-day grouping."""

import pytest
from PySide6.QtWidgets import QApplication

from app_facade import AppFacade
from ui.tabs.realized_tab import RealizedTab


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_realized_tab_groups_by_local_day(monkeypatch, tmp_path, qapp):
    monkeypatch.setattr(
        "ui.tabs.realized_tab.get_configured_timezone_name",
        lambda *args, **kwargs: "America/New_York",
    )

    db_path = tmp_path / "test.db"
    facade = AppFacade(str(db_path))
    db = facade.db

    user_id = db.execute("INSERT INTO users (name) VALUES (?)", ("Test User",))
    site_id = db.execute("INSERT INTO sites (name) VALUES (?)", ("Sixty6",))
    redemption_id = db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, site_id, "10.00", "2026-02-15", "02:00:00"),
    )
    db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-02-15", site_id, user_id, redemption_id, "1.00", "10.00", "9.00"),
    )

    tab = RealizedTab(facade)
    transactions = tab._fetch_transactions()

    assert transactions
    assert transactions[0]["session_date"] == "2026-02-14"

    if facade.db._connection is not None:
        facade.db._connection.close()
