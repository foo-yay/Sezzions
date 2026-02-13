"""Regression tests for data shown in Unrealized "View Position" -> Related tab.

The dialog should not show unrelated historical sessions, and should show purchases
within the position timeframe.
"""

from datetime import date
from decimal import Decimal

import pytest

from app_facade import AppFacade


@pytest.fixture
def facade():
    f = AppFacade(":memory:")
    try:
        yield f
    finally:
        f.db.close()


def test_unrealized_related_queries_are_scoped_to_start_date(facade):
    # Minimal reference data
    facade.db.execute("INSERT INTO users (name) VALUES ('mrs. fooyay')")
    facade.db.execute("INSERT INTO sites (name) VALUES ('Stake')")
    facade.db.execute("INSERT INTO game_types (name) VALUES ('Test Type')")
    facade.db.execute("INSERT INTO games (name, game_type_id) VALUES ('Test Game', 1)")

    # Old historical activity (should be excluded by start_date)
    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
        VALUES
            (1, 1, '2026-01-01', '10:00:00', 50.00, 50.00, 0.00)
        """
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (1, 1, 1, '2026-01-05', '11:00:00', '2026-01-05', '12:00:00',
             50.00, 40.00, 40.00, 'completed')
        """
    )

    # Current position activity
    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
        VALUES
            (1, 1, '2026-02-10', '09:00:00', 2500.00, 2506.26, 2500.00)
        """
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (1, 1, 1, '2026-02-10', '23:00:00', '2026-02-11', '01:00:00',
             2506.26, 2532.65, 2532.65, 'completed')
        """
    )

    facade.db.commit()

    start_date = date(2026, 2, 10)

    purchases = facade.get_unrealized_open_purchases(1, 1, start_date=start_date)
    sessions = facade.get_unrealized_sessions(1, 1, start_date=start_date)

    assert len(purchases) == 1
    assert purchases[0]["purchase_date"] == "2026-02-10"

    assert len(sessions) == 1
    assert sessions[0]["session_date"] == "2026-02-10"


def test_unrealized_related_anchor_uses_checkpoint_for_profit_only_positions(facade):
    # Minimal reference data
    facade.db.execute("INSERT INTO users (name) VALUES ('mrs. fooyay')")
    facade.db.execute("INSERT INTO sites (name) VALUES ('Stake')")
    facade.db.execute("INSERT INTO game_types (name) VALUES ('Test Type')")
    facade.db.execute("INSERT INTO games (name, game_type_id) VALUES ('Test Game', 1)")

    # Historical purchases fully consumed (profit-only position basis)
    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, starting_sc_balance)
        VALUES
            (1, 1, '2025-12-31', '19:23:00', 4500.00, 4511.25, 0.00, 4511.25)
        """
    )

    # Latest non-adjustment checkpoint: a session that ends the next day
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, starting_redeemable, ending_balance, ending_redeemable, status)
        VALUES
            (1, 1, 1, '2026-02-10', '19:08:45', '2026-02-11', '12:05:00',
             2513.79, 7.54, 2532.65, 2532.65, 'Closed')
        """
    )

    # Balance checkpoint correction is newer, but should NOT be used for Related anchoring
    # (we want the baseline activity checkpoint window, not earliest-ever purchase)
    facade.db.execute(
        """
        INSERT INTO account_adjustments
            (user_id, site_id, effective_date, effective_time, type,
             delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc, reason)
        VALUES
            (1, 1, '2026-02-13', '09:05:00', 'BALANCE_CHECKPOINT_CORRECTION',
             0.00, 2541.19, 2541.19, 'Bonus redeemable SC post-session-close')
        """
    )

    facade.db.commit()

    # Position start date would fall back to earliest purchase, but basis is zero.
    position_start_date = date(2025, 12, 31)
    anchor = facade.get_unrealized_related_anchor_date(
        1,
        1,
        position_start_date=position_start_date,
        purchase_basis=Decimal("0.00"),
    )
    assert anchor == date(2026, 2, 11)

    # Related sessions should include the spanning session because its end_date is on the anchor date.
    sessions = facade.get_unrealized_sessions(1, 1, start_date=anchor)
    assert len(sessions) == 1
    assert sessions[0]["session_date"] == "2026-02-10"
