"""Regression: tabs should start with the correct default date filter presets."""

from datetime import date

import pytest

from app_facade import AppFacade
from ui.tabs.purchases_tab import PurchasesTab
from ui.tabs.redemptions_tab import RedemptionsTab
from ui.tabs.game_sessions_tab import GameSessionsTab
from ui.tabs.daily_sessions_tab import DailySessionsTab
from ui.tabs.unrealized_tab import UnrealizedTab
from ui.tabs.realized_tab import RealizedTab
from ui.tabs.expenses_tab import ExpensesTab


@pytest.fixture
def app_facade():
    facade = AppFacade(":memory:")
    yield facade
    facade.db.close()


def _assert_date_filter_widget(widget, expected_start: date, expected_end: date):
    assert widget.start_date.text() == expected_start.strftime("%m/%d/%y")
    assert widget.end_date.text() == expected_end.strftime("%m/%d/%y")


@pytest.mark.parametrize(
    "tab_factory,attr_name,expected_start_factory",
    [
        (lambda facade: PurchasesTab(facade), "date_filter", lambda today: date(today.year, 1, 1)),
        (lambda facade: RedemptionsTab(facade), "date_filter", lambda today: date(today.year, 1, 1)),
        (lambda facade: GameSessionsTab(facade), "date_filter", lambda today: date(today.year, 1, 1)),
        (lambda facade: DailySessionsTab(facade), "date_filter_widget", lambda today: date(today.year, 1, 1)),
        (lambda facade: RealizedTab(facade), "date_filter_widget", lambda today: date(today.year, 1, 1)),
        (lambda facade: ExpensesTab(facade), "date_filter", lambda today: date(today.year, 1, 1)),
        (lambda facade: UnrealizedTab(facade), "date_filter", lambda _today: date(2000, 1, 1)),
    ],
)
def test_tab_date_filter_defaults(qtbot, app_facade, tab_factory, attr_name, expected_start_factory):
    tab = tab_factory(app_facade)
    qtbot.addWidget(tab)

    today = date.today()
    expected_start = expected_start_factory(today)
    expected_end = today

    widget = getattr(tab, attr_name)
    _assert_date_filter_widget(widget, expected_start, expected_end)
