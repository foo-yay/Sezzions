from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app_facade import AppFacade
from ui.settings import Settings
from ui.tabs.game_sessions_tab import GameSessionsTab
from ui.tabs.purchases_tab import PurchasesTab
from ui.tabs.redemptions_tab import RedemptionsTab


class _MainWindowStub:
    def __init__(self, settings: Settings):
        self.settings = settings


@pytest.fixture
def facade():
    app = AppFacade(":memory:")
    yield app
    app.db.close()


@pytest.fixture
def settings(tmp_path):
    return Settings(settings_file=str(tmp_path / "settings.json"))


def _seed_user_site_game(facade: AppFacade):
    user = facade.create_user(name="Issue121 User", email="issue121@example.com")
    site = facade.create_site(name="Issue121 Site", url="https://issue121.example")
    game_type = facade.create_game_type(name="Slots")
    game = facade.create_game(name="Issue121 Game", game_type_id=game_type.id)
    return user, site, game


def test_purchases_basis_remaining_quick_filter_filters_persists_and_clears(qtbot, facade, settings):
    user, site, _game = _seed_user_site_game(facade)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        purchase_time="08:00:00",
    )
    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        purchase_date=date.today(),
        purchase_time="09:00:00",
    )
    # Consume exactly one purchase so only one row has remaining basis > 0
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        redemption_date=date.today(),
        redemption_time="10:00:00",
        processed=True,
        more_remaining=True,
        apply_fifo=True,
    )

    main_window = _MainWindowStub(settings)
    tab = PurchasesTab(facade, main_window=main_window)
    qtbot.addWidget(tab)
    tab.date_filter.set_all_time()
    tab.refresh_data()

    assert tab.table.rowCount() == 2

    tab.basis_remaining_filter_check.setChecked(True)
    assert tab.table.rowCount() == 1

    # Persisted state should restore on a new tab instance
    tab2 = PurchasesTab(facade, main_window=main_window)
    qtbot.addWidget(tab2)
    tab2.date_filter.set_all_time()
    tab2.refresh_data()
    assert tab2.basis_remaining_filter_check.isChecked() is True

    tab2._clear_all_filters()
    assert tab2.basis_remaining_filter_check.isChecked() is False
    assert tab2.table.rowCount() == 2


def test_redemptions_pending_unprocessed_quick_filters_and_persistence(qtbot, facade, settings):
    user, site, _game = _seed_user_site_game(facade)

    # pending + unprocessed
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("10.00"),
        redemption_date=date.today(),
        redemption_time="08:00:00",
        receipt_date=None,
        processed=False,
        more_remaining=True,
        apply_fifo=False,
    )
    # pending + processed
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("20.00"),
        redemption_date=date.today(),
        redemption_time="09:00:00",
        receipt_date=None,
        processed=True,
        more_remaining=True,
        apply_fifo=False,
    )
    # received + unprocessed
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("30.00"),
        redemption_date=date.today(),
        redemption_time="10:00:00",
        receipt_date=date.today(),
        processed=False,
        more_remaining=True,
        apply_fifo=False,
    )

    main_window = _MainWindowStub(settings)
    tab = RedemptionsTab(facade, main_window=main_window)
    qtbot.addWidget(tab)
    tab.date_filter.set_all_time()
    tab.refresh_data()

    assert tab.table.rowCount() == 3

    tab.pending_filter_check.setChecked(True)
    assert tab.table.rowCount() == 2

    tab.unprocessed_filter_check.setChecked(True)
    assert tab.table.rowCount() == 1

    # Persist and restore
    tab2 = RedemptionsTab(facade, main_window=main_window)
    qtbot.addWidget(tab2)
    tab2.date_filter.set_all_time()
    tab2.refresh_data()
    assert tab2.pending_filter_check.isChecked() is True
    assert tab2.unprocessed_filter_check.isChecked() is True

    tab2._clear_all_filters()
    assert tab2.pending_filter_check.isChecked() is False
    assert tab2.unprocessed_filter_check.isChecked() is False
    assert tab2.table.rowCount() == 3


def test_game_sessions_active_only_quick_filter_filters_persists_and_clears(qtbot, facade, settings):
    user1, site1, game = _seed_user_site_game(facade)
    user2 = facade.create_user(name="Issue121 User 2", email="issue121-2@example.com")
    site2 = facade.create_site(name="Issue121 Site 2", url="https://issue121-2.example")

    # Active session
    facade.create_game_session(
        user_id=user1.id,
        site_id=site1.id,
        game_id=game.id,
        session_date=date.today(),
        session_time="08:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        calculate_pl=False,
    )

    # Closed session (different user/site so it can coexist)
    closed = facade.create_game_session(
        user_id=user2.id,
        site_id=site2.id,
        game_id=game.id,
        session_date=date.today(),
        session_time="09:00:00",
        starting_balance=Decimal("50.00"),
        ending_balance=Decimal("60.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("10.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        closed.id,
        status="Closed",
        end_date=date.today(),
        end_time="09:30:00",
        recalculate_pl=False,
    )

    main_window = _MainWindowStub(settings)
    tab = GameSessionsTab(facade, main_window=main_window)
    qtbot.addWidget(tab)
    tab.date_filter.set_all_time()
    tab.apply_filters()

    assert len(tab.filtered_sessions) == 2

    tab.active_only_filter_check.setChecked(True)
    assert len(tab.filtered_sessions) == 1
    assert all(s.status == "Active" for s in tab.filtered_sessions)

    tab2 = GameSessionsTab(facade, main_window=main_window)
    qtbot.addWidget(tab2)
    tab2.date_filter.set_all_time()
    tab2.apply_filters()
    assert tab2.active_only_filter_check.isChecked() is True

    tab2.clear_all_filters()
    assert tab2.active_only_filter_check.isChecked() is False
    assert len(tab2.filtered_sessions) == 2
