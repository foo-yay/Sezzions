import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.tabs.redemptions_tab import RedemptionsTab


@dataclass(frozen=True)
class _FakeRedemption:
    id: int
    redemption_date: date
    redemption_time: str | None
    amount: Decimal
    more_remaining: bool
    receipt_date: date | None
    processed: bool
    notes: str | None

    user_name: str
    site_name: str
    method_name: str

    @property
    def datetime_str(self) -> str:
        # Matches the app’s string-based sorting expectation.
        t = (self.redemption_time or "00:00:00")
        return f"{self.redemption_date.isoformat()} {t}"


class _FakeFacade:
    def __init__(self, redemptions):
        self._redemptions = list(redemptions)

    def get_all_redemptions(self, start_date=None, end_date=None):
        return list(self._redemptions)


def _table_row_snapshot(tab: RedemptionsTab):
    def _col(header_text: str) -> int:
        for col in range(tab.table.columnCount()):
            header_item = tab.table.horizontalHeaderItem(col)
            if header_item and header_item.text() == header_text:
                return col
        raise AssertionError(f"Missing expected column header: {header_text}")

    id_col = _col("Date/Time")
    site_col = _col("Site")
    amount_col = _col("Amount")

    rows = []
    for row in range(tab.table.rowCount()):
        id_item = tab.table.item(row, id_col)
        amount_item = tab.table.item(row, amount_col)
        site_item = tab.table.item(row, site_col)
        if id_item is None:
            continue
        rows.append(
            (
                id_item.data(Qt.UserRole),
                site_item.text() if site_item else "",
                amount_item.text() if amount_item else "",
            )
        )
    return rows


def test_redemptions_tab_repopulate_under_active_sort_keeps_rows_consistent():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    redemptions = [
        _FakeRedemption(
            id=1,
            redemption_date=date(2026, 2, 1),
            redemption_time="10:00:00",
            amount=Decimal("169.00"),
            more_remaining=False,
            receipt_date=None,
            processed=False,
            notes="one",
            user_name="Elliot",
            site_name="Crown Coins",
            method_name="ACH",
        ),
        _FakeRedemption(
            id=2,
            redemption_date=date(2026, 2, 1),
            redemption_time="11:00:00",
            amount=Decimal("260.00"),
            more_remaining=False,
            receipt_date=None,
            processed=False,
            notes="two",
            user_name="Elliot",
            site_name="Beta Site",
            method_name="ACH",
        ),
        _FakeRedemption(
            id=3,
            redemption_date=date(2026, 2, 1),
            redemption_time="12:00:00",
            amount=Decimal("382.40"),
            more_remaining=True,
            receipt_date=None,
            processed=True,
            notes="three",
            user_name="Elliot",
            site_name="Alpha Site",
            method_name="ACH",
        ),
    ]
    expected = {
        1: ("Crown Coins", "$169.00"),
        2: ("Beta Site", "$260.00"),
        3: ("Alpha Site", "$382.40"),
    }

    tab = RedemptionsTab(_FakeFacade(redemptions))
    tab.show()
    app.processEvents()

    # User sorts by Site A→Z using the header filter menu.
    tab.table_filter.sort_by_column(2, Qt.AscendingOrder)

    # Then a refresh or search re-populates while sorting is still enabled.
    tab._populate_table()
    app.processEvents()

    snapshot = _table_row_snapshot(tab)
    ids = [row_id for (row_id, _site, _amount) in snapshot]

    # No duplicates / ghosts.
    assert sorted(ids) == [1, 2, 3]

    # Each row must keep its own site + amount (no cross-row mixing).
    for row_id, site_text, amount_text in snapshot:
        assert expected[row_id] == (site_text, amount_text)

    tab.close()
