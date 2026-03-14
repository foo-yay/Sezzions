from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from PySide6 import QtCore

from app_facade import AppFacade
from ui.settings import Settings
from ui.tabs.redemptions_tab import RedemptionsTab


class _MainWindowStub:
    def __init__(self, settings: Settings):
        self.settings = settings

    def refresh_all_tabs(self):
        pass


@pytest.fixture
def facade(tmp_path):
    app = AppFacade(str(tmp_path / "issue_187_ui.db"))
    yield app
    app.db.close()


@pytest.fixture
def settings(tmp_path):
    return Settings(settings_file=str(tmp_path / "settings.json"))


def _row_for_redemption(tab: RedemptionsTab, redemption_id: int) -> int:
    for row in range(tab.table.rowCount()):
        item = tab.table.item(row, 0)
        if item is not None and item.data(QtCore.Qt.UserRole) == redemption_id:
            return row
    raise AssertionError(f"redemption row {redemption_id} not found")


def _select_row(tab: RedemptionsTab, row: int) -> None:
    tab.table.clearSelection()
    tab.table.selectRow(row)
    tab._on_selection_changed()


def test_cancel_button_hidden_for_received_and_edit_hidden_for_pending_cancel(qtbot, facade, settings):
    user = facade.create_user("UI User")
    site = facade.create_site("UI Site", sc_rate=1.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("100.00"),
    )

    pending = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("10.00"),
        redemption_date=date.today() - timedelta(days=3),
        redemption_time="08:00:00",
        receipt_date=None,
        processed=False,
        more_remaining=True,
        apply_fifo=False,
    )
    received = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("20.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="09:00:00",
        receipt_date=date.today() - timedelta(days=1),
        processed=False,
        more_remaining=True,
        apply_fifo=False,
    )

    active_session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        calculate_pl=False,
    )
    queued = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("15.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="10:30:00",
        receipt_date=None,
        processed=False,
        more_remaining=True,
        apply_fifo=True,
    )
    facade.cancel_redemption(queued.id, reason="queue it")
    assert facade.get_redemption(queued.id).status == "PENDING_CANCEL"
    assert active_session.status == "Active"

    tab = RedemptionsTab(facade, main_window=_MainWindowStub(settings))
    qtbot.addWidget(tab)
    tab.show()
    tab.date_filter.set_all_time()
    tab.refresh_data()

    pending_row = _row_for_redemption(tab, pending.id)
    _select_row(tab, pending_row)
    assert tab.cancel_btn.isHidden() is False
    assert tab.edit_btn.isHidden() is False

    received_row = _row_for_redemption(tab, received.id)
    _select_row(tab, received_row)
    assert tab.cancel_btn.isHidden() is True
    assert tab.uncancel_btn.isHidden() is True

    queued_row = _row_for_redemption(tab, queued.id)
    _select_row(tab, queued_row)
    assert tab.cancel_btn.isHidden() is True
    assert tab.edit_btn.isHidden() is True
    assert tab.uncancel_btn.isHidden() is True

    tab.table.clearSelection()
    tab._on_selection_changed()
    assert tab.cancel_btn.isHidden() is True
    assert tab.uncancel_btn.isHidden() is True
