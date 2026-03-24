from datetime import date, timedelta
from decimal import Decimal

import pytest

from app_facade import AppFacade


@pytest.fixture

def facade():
    app = AppFacade(":memory:")
    try:
        yield app
    finally:
        app.db.close()



def _seed_reference_data(facade: AppFacade) -> None:
    facade.db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    facade.db.execute("INSERT INTO sites (id, name, sc_rate) VALUES (1, 'CasinoA', 1.0)")
    facade.db.execute("INSERT INTO game_types (id, name) VALUES (1, 'Slots')")
    facade.db.execute("INSERT INTO games (id, name, game_type_id) VALUES (1, 'Buffalo Gold', 1)")



def _seed_zero_basis_visible_position(facade: AppFacade) -> None:
    today = date.today()
    purchase_date = today - timedelta(days=2)
    session_date = today - timedelta(days=1)

    _seed_reference_data(facade)
    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, status)
        VALUES
            (1, 1, ?, '10:00:00', 20.00, 20.00, 0.00, 'active')
        """,
        (purchase_date.isoformat(),),
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (1, 1, 1, ?, '11:00:00', ?, '12:00:00',
             20.00, 0.14, 0.14, 'completed')
        """,
        (session_date.isoformat(), session_date.isoformat()),
    )
    facade.db.commit()



def _seed_basis_position(facade: AppFacade) -> None:
    today = date.today()
    purchase_date = today - timedelta(days=2)
    session_date = today - timedelta(days=1)

    _seed_reference_data(facade)
    facade.db.execute(
        """
        INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount, status)
        VALUES
            (1, 1, ?, '10:00:00', 100.00, 100.00, 100.00, 'active')
        """,
        (purchase_date.isoformat(),),
    )
    facade.db.execute(
        """
        INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
        VALUES
            (1, 1, 1, ?, '11:00:00', ?, '12:00:00',
             100.00, 80.00, 80.00, 'completed')
        """,
        (session_date.isoformat(), session_date.isoformat()),
    )
    facade.db.commit()


class TestIssue191ZeroBasisUnrealizedClose:
    def test_zero_basis_close_creates_marker_without_fifo_or_realized_loss(self, facade):
        _seed_zero_basis_visible_position(facade)

        position = facade.get_unrealized_position(1, 1)
        assert position is not None
        assert position.purchase_basis == Decimal("0.00")
        assert position.total_sc == Decimal("0.14")

        result = facade.close_unrealized_position(
            site_id=1,
            user_id=1,
            current_sc=position.total_sc,
            current_value=position.current_value,
            total_basis=position.purchase_basis,
        )

        assert result == {
            "net_loss": Decimal("0.00"),
            "current_sc": Decimal("0.14"),
            "current_value": Decimal("0.14"),
        }

        marker = facade.db.fetch_one(
            """
            SELECT amount, processed, more_remaining, notes
            FROM redemptions
            ORDER BY id DESC
            LIMIT 1
            """
        )
        assert Decimal(str(marker["amount"])) == Decimal("0.00")
        assert marker["processed"] == 1
        assert marker["more_remaining"] == 1
        assert marker["notes"].startswith("Balance Closed - Net Loss: $0.00")

        purchase = facade.db.fetch_one(
            "SELECT remaining_amount, status FROM purchases WHERE id = 1"
        )
        assert Decimal(str(purchase["remaining_amount"])) == Decimal("0.00")
        assert purchase["status"] == "active"

        allocation_count = facade.db.fetch_one(
            "SELECT COUNT(*) AS count FROM redemption_allocations"
        )["count"]
        realized_count = facade.db.fetch_one(
            "SELECT COUNT(*) AS count FROM realized_transactions"
        )["count"]
        assert allocation_count == 0
        assert realized_count == 0
        assert facade.get_unrealized_positions() == []

    def test_zero_basis_close_reopens_on_later_activity(self, facade):
        _seed_zero_basis_visible_position(facade)
        position = facade.get_unrealized_position(1, 1)
        assert position is not None

        facade.close_unrealized_position(
            site_id=1,
            user_id=1,
            current_sc=position.total_sc,
            current_value=position.current_value,
            total_basis=position.purchase_basis,
        )
        assert facade.get_unrealized_positions() == []

        later_date = date.today() + timedelta(days=1)
        facade.db.execute(
            """
            INSERT INTO game_sessions
                (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
                 starting_balance, ending_balance, ending_redeemable, status)
            VALUES
                (1, 1, 1, ?, '09:00:00', ?, '10:00:00',
                 0.14, 0.20, 0.20, 'completed')
            """,
            (later_date.isoformat(), later_date.isoformat()),
        )
        facade.db.commit()

        reopened = facade.get_unrealized_position(1, 1)
        assert reopened is not None
        assert reopened.purchase_basis == Decimal("0.00")
        assert reopened.total_sc == Decimal("0.20")
        assert reopened.redeemable_sc == Decimal("0.20")

    def test_zero_basis_close_is_blocked_when_session_active(self, facade):
        _seed_reference_data(facade)
        today = date.today()
        facade.db.execute(
            """
            INSERT INTO game_sessions
                (user_id, site_id, game_id, session_date, session_time,
                 starting_balance, ending_balance, ending_redeemable, status)
            VALUES
                (1, 1, 1, ?, '11:00:00', 0.14, 0.14, 0.14, 'Active')
            """,
            (today.isoformat(),),
        )
        facade.db.commit()

        with pytest.raises(ValueError, match="Cannot close balance while a session is active"):
            facade.close_unrealized_position(
                site_id=1,
                user_id=1,
                current_sc=Decimal("0.14"),
                current_value=Decimal("0.14"),
                total_basis=Decimal("0.00"),
            )

        redemption_count = facade.db.fetch_one(
            "SELECT COUNT(*) AS count FROM redemptions"
        )["count"]
        assert redemption_count == 0

    def test_basis_close_still_consumes_basis_and_creates_realized_loss(self, facade):
        _seed_basis_position(facade)

        position = facade.get_unrealized_position(1, 1)
        assert position is not None
        assert position.purchase_basis == Decimal("100.00")

        result = facade.close_unrealized_position(
            site_id=1,
            user_id=1,
            current_sc=position.total_sc,
            current_value=position.current_value,
            total_basis=position.purchase_basis,
        )

        assert result["net_loss"] == Decimal("100.00")

        redemption = facade.db.fetch_one(
            "SELECT more_remaining, notes FROM redemptions ORDER BY id DESC LIMIT 1"
        )
        assert redemption["more_remaining"] == 0
        assert redemption["notes"].startswith("Balance Closed - Net Loss: $100.00")

        realized = facade.db.fetch_one(
            "SELECT cost_basis, payout, net_pl FROM realized_transactions"
        )
        assert Decimal(str(realized["cost_basis"])) == Decimal("100.00")
        assert Decimal(str(realized["payout"])) == Decimal("0.00")
        assert Decimal(str(realized["net_pl"])) == Decimal("-100.00")

        purchase = facade.db.fetch_one(
            "SELECT remaining_amount, status FROM purchases WHERE id = 1"
        )
        assert Decimal(str(purchase["remaining_amount"])) == Decimal("0.00")
