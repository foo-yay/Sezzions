from datetime import date, timedelta
from decimal import Decimal

import pytest
from PySide6 import QtCore

from app_facade import AppFacade
from ui.tabs.redemptions_tab import RedemptionsTab


class _MainWindowStub:
    settings = None


@pytest.fixture

def facade(tmp_path):
    app = AppFacade(str(tmp_path / "issue_191_close_marker_labels.db"))
    try:
        yield app
    finally:
        app.db.close()



def _seed_reference_data(facade: AppFacade):
    user = facade.create_user("UI User")
    site = facade.create_site("UI Site", sc_rate=1.0)
    return user, site



def _row_for_redemption(tab: RedemptionsTab, redemption_id: int) -> int:
    for row in range(tab.table.rowCount()):
        item = tab.table.item(row, 0)
        if item is not None and item.data(QtCore.Qt.UserRole) == redemption_id:
            return row
    raise AssertionError(f"redemption row {redemption_id} not found")



def test_zero_basis_close_marker_is_not_labeled_loss(qtbot, facade):
    user, site = _seed_reference_data(facade)
    purchase_date = date.today() - timedelta(days=2)
    session_date = date.today() - timedelta(days=1)

    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, status)
        VALUES
            (?, ?, ?, '10:00:00', 20.00, 20.00, 0.00, 'active')
        """,
        (user.id, site.id, purchase_date.isoformat()),
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (?, ?, NULL, ?, '11:00:00', ?, '12:00:00',
             20.00, 0.14, 0.14, 'completed')
        """,
        (user.id, site.id, session_date.isoformat(), session_date.isoformat()),
    )
    facade.db.commit()

    position = facade.get_unrealized_position(site.id, user.id)
    assert position is not None
    assert position.purchase_basis == Decimal("0.00")

    facade.close_unrealized_position(
        site_id=site.id,
        user_id=user.id,
        current_sc=position.total_sc,
        current_value=position.current_value,
        total_basis=position.purchase_basis,
    )
    redemption = facade.get_all_redemptions()[0]

    tab = RedemptionsTab(facade, main_window=_MainWindowStub())
    qtbot.addWidget(tab)
    tab.show()
    tab.date_filter.set_all_time()
    tab.refresh_data()

    row = _row_for_redemption(tab, redemption.id)
    assert tab.table.item(row, 8).text() == "Closed"
    assert tab.table.item(row, 10).text().startswith("Balance Closed - Net Loss: $0.00")



def test_basis_close_marker_still_shows_loss_label(qtbot, facade):
    user, site = _seed_reference_data(facade)
    purchase_date = date.today() - timedelta(days=2)
    session_date = date.today() - timedelta(days=1)

    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, status)
        VALUES
            (?, ?, ?, '10:00:00', 100.00, 100.00, 100.00, 'active')
        """,
        (user.id, site.id, purchase_date.isoformat()),
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (?, ?, NULL, ?, '11:00:00', ?, '12:00:00',
             100.00, 80.00, 80.00, 'completed')
        """,
        (user.id, site.id, session_date.isoformat(), session_date.isoformat()),
    )
    facade.db.commit()

    position = facade.get_unrealized_position(site.id, user.id)
    assert position is not None
    assert position.purchase_basis == Decimal("100.00")

    facade.close_unrealized_position(
        site_id=site.id,
        user_id=user.id,
        current_sc=position.total_sc,
        current_value=position.current_value,
        total_basis=position.purchase_basis,
    )
    redemption = facade.get_all_redemptions()[0]

    tab = RedemptionsTab(facade, main_window=_MainWindowStub())
    qtbot.addWidget(tab)
    tab.show()
    tab.date_filter.set_all_time()
    tab.refresh_data()

    row = _row_for_redemption(tab, redemption.id)
    assert tab.table.item(row, 8).text() == "Loss"
