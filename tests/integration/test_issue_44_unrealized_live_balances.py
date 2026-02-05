"""
Integration tests for Issue #44: Unrealized tab reflects purchases/redemptions after last session
"""
import pytest
from decimal import Decimal
from datetime import date

from repositories.database import DatabaseManager
from repositories.unrealized_position_repository import UnrealizedPositionRepository


@pytest.fixture
def db():
    """In-memory database for testing"""
    db = DatabaseManager(":memory:")
    
    # Insert test data
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')")
    db.execute("INSERT INTO sites (id, name, sc_rate) VALUES (1, 'CasinoA', 1.0)")
    db.execute("INSERT INTO game_types (id, name) VALUES (1, 'Slots')")
    db.execute("INSERT INTO games (id, name, game_type_id) VALUES (1, 'Buffalo Gold', 1)")
    
    db.commit()
    yield db
    db.close()


@pytest.fixture
def repo(db):
    return UnrealizedPositionRepository(db)


class TestUnrealizedBalancesAfterSession:
    """Test that unrealized positions incorporate transactions after last session"""
    
    def test_purchase_after_session_updates_current_sc(self, db, repo):
        """After adding a purchase following a session, Current SC should increase"""
        # Insert purchase
        db.execute("""
            INSERT INTO purchases 
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 100.00)
        """)
        
        # Insert session that ends with 50 SC remaining
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 50.00, 50.00, 'completed')
        """)
        db.commit()
        
        # Check position before new purchase
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.total_sc == Decimal("50.00")  # From session ending
        assert pos.redeemable_sc == Decimal("50.00")  # Last-known from session ending
        assert pos.purchase_basis == Decimal("100.00")  # Remaining basis
        
        # Add another purchase after the session
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-02', '10:00:00', 25.00, 25.00, 25.00)
        """)
        db.commit()
        
        # Check position after new purchase
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Current SC should now include the new purchase
        assert pos.total_sc == Decimal("75.00")  # 50 (session end) + 25 (new purchase)
        assert pos.redeemable_sc == Decimal("50.00")  # Last-known from session ending
        assert pos.purchase_basis == Decimal("125.00")  # 100 + 25 remaining
        assert pos.current_value == Decimal("75.00")  # total_sc * 1.0 rate
        assert pos.unrealized_pl == Decimal("-50.00")  # 75 - 125
    
    def test_redemption_after_session_updates_current_sc(self, db, repo):
        """After a redemption following a session, Current SC should decrease"""
        # Insert purchase
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 50.00)
        """)
        
        # Insert session that ends with 80 SC
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 80.00, 80.00, 'completed')
        """)
        db.commit()
        
        # Check position before redemption
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.total_sc == Decimal("80.00")
        
        # Add redemption after session
        db.execute("""
            INSERT INTO redemptions
            (user_id, site_id, redemption_date, redemption_time, amount, processed)
            VALUES (1, 1, '2024-01-03', '10:00:00', 30.00, 1)
        """)
        db.commit()
        
        # Check position after redemption
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Current SC should reflect the redemption
        assert pos.total_sc == Decimal("50.00")  # 80 - 30
        assert pos.redeemable_sc == Decimal("80.00")  # Last-known from session ending
        assert pos.purchase_basis == Decimal("50.00")  # Remaining basis unchanged
        assert pos.current_value == Decimal("50.00")
        assert pos.unrealized_pl == Decimal("0.00")  # 50 - 50
    
    def test_multiple_purchases_and_redemptions_after_session(self, db, repo):
        """Multiple transactions after session should all be incorporated"""
        # Insert initial purchase
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 60.00)
        """)
        
        # Insert session
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 120.00, 100.00, 'completed')
        """)
        db.commit()
        
        # Add transactions after session: 2 purchases, 1 redemption
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-02', '10:00:00', 50.00, 50.00, 50.00)
        """)
        db.execute("""
            INSERT INTO redemptions
            (user_id, site_id, redemption_date, redemption_time, amount, processed)
            VALUES (1, 1, '2024-01-02', '14:00:00', 20.00, 1)
        """)
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-03', '10:00:00', 25.00, 25.00, 25.00)
        """)
        db.commit()
        
        # Check final position
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Current SC: 120 (session end total) + 50 + 25 (purchases) - 20 (redemption)
        assert pos.total_sc == Decimal("175.00")
        assert pos.redeemable_sc == Decimal("100.00")  # Last-known from session ending
        assert pos.purchase_basis == Decimal("135.00")  # 60 + 50 + 25
        assert pos.unrealized_pl == Decimal("40.00")  # 175 - 135


class TestUnrealizedBalancesNoSession:
    """Test positions when no sessions exist yet"""
    
    def test_purchases_only_no_session(self, db, repo):
        """With no sessions, current SC should sum all purchases"""
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 100.00)
        """)
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-02', '10:00:00', 50.00, 50.00, 50.00)
        """)
        db.commit()
        
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        assert pos.total_sc == Decimal("150.00")  # Sum of all purchases
        assert pos.redeemable_sc == Decimal("0.00")  # No sessions => no last-known redeemable
        assert pos.purchase_basis == Decimal("150.00")
        assert pos.unrealized_pl == Decimal("0.00")

    def test_active_session_does_not_zero_out_total_sc(self, db, repo):
        """An Active session (ending_balance default 0.00) should not be used as the baseline."""
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 100.00)
        """)

        # Mimic how the app starts a session: status Active + ending_balance 0.00.
        # This should NOT become the "last session" baseline for Unrealized.
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time,
             starting_balance, ending_balance, starting_redeemable, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00',
                    101.00, 0.00, 0.00, 0.00, 'Active')
        """)
        db.commit()

        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]

        # With no closed session checkpoint, Total SC should reflect purchases (not be forced to 0).
        assert pos.total_sc == Decimal("100.00")
        assert pos.purchase_basis == Decimal("100.00")


class TestUnrealizedLastActivity:
    """Test that last_activity reflects most recent transaction"""
    
    def test_last_activity_from_recent_purchase(self, db, repo):
        """Last activity should be most recent purchase if after session"""
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 100.00)
        """)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 80.00, 80.00, 'completed')
        """)
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-05', '15:00:00', 50.00, 50.00, 50.00)
        """)
        db.commit()
        
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Last activity should be the most recent purchase
        assert pos.last_activity == date(2024, 1, 5)


class TestUnrealizedInvariantBasis:
    """Test that remaining basis calculation remains correct"""
    
    def test_basis_always_sums_remaining_amount(self, db, repo):
        """Basis should always equal sum of remaining_amount regardless of sessions"""
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 75.00)
        """)
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-02', '10:00:00', 50.00, 50.00, 50.00)
        """)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-02', '11:00:00', '2024-01-02', '12:00:00',
                    150.00, 200.00, 150.00, 'completed')
        """)
        db.commit()
        
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Basis should be sum of remaining amounts
        assert pos.purchase_basis == Decimal("125.00")  # 75 + 50


class TestUnrealizedRedeemableScopedToPosition:
    """Test that redeemable SC is only shown from sessions within current position"""
    
    def test_redeemable_zero_when_session_predates_position(self, db, repo):
        """
        Scenario: Fully redeemed old position, then repurchased.
        Session from old position should not leak redeemable into new position.
        """
        # Old position: purchase + session + full redemption (closes position)
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 0.00)
        """)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 120.00, 80.00, 'completed')
        """)
        db.execute("""
            INSERT INTO redemptions
            (user_id, site_id, redemption_date, redemption_time, amount, processed)
            VALUES (1, 1, '2024-01-02', '10:00:00', 120.00, 1)
        """)
        db.commit()
        
        # New position starts: purchase after redemption
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-02-01', '10:00:00', 50.00, 50.00, 50.00)
        """)
        db.commit()
        
        # Check unrealized position
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Position should reflect new purchase only
        assert pos.start_date == date(2024, 2, 1)  # New purchase start
        assert pos.purchase_basis == Decimal("50.00")
        # No sessions after new purchase, so total_sc is just sum of purchases
        assert pos.total_sc == Decimal("50.00")  # New purchase only (no session after it)
        
        # Redeemable should be 0 (old session predates current position basis)
        assert pos.redeemable_sc == Decimal("0.00")
    
    def test_redeemable_shown_when_session_within_position(self, db, repo):
        """
        Scenario: Purchase + session within same position.
        Redeemable should be shown from the session.
        """
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 60.00)
        """)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 120.00, 80.00, 'completed')
        """)
        db.commit()
        
        positions = repo.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        
        # Session is same day as position start, so redeemable should show
        assert pos.start_date == date(2024, 1, 1)
        assert pos.redeemable_sc == Decimal("80.00")  # From session


class TestIssue58RemainingBasisZeroButSCExists:
    """
    Test Issue #58: Unrealized should show positions where basis is fully allocated
    but SC remains on site (e.g., partial redemption consumed all basis, remainder pending).
    """
    
    def test_basis_zero_but_sc_remains_position_still_shows(self, db, repo):
        """
        Scenario (Moonspin cap): Partial redemption consumed all remaining basis
        due to FIFO, but ~175 SC remains on site pending next redemption.
        Position should still appear in Unrealized.
        """
        # Purchase with basis
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 2500.00, 2500.00, 0.00)
        """)
        
        # Session showing SC balance grew to 2675 (won 175 SC)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    2500.00, 2675.00, 2675.00, 'completed')
        """)
        
        # Partial redemption for 2500 SC (site cap) - FIFO consumed all remaining basis
        db.execute("""
            INSERT INTO redemptions
            (user_id, site_id, redemption_date, redemption_time, amount, more_remaining, processed)
            VALUES (1, 1, '2024-01-02', '10:00:00', 2500.00, 1, 0)
        """)
        db.commit()
        
        # Check unrealized position
        positions = repo.get_all_positions()
        
        # Position SHOULD still appear even though remaining_amount = 0
        assert len(positions) == 1, "Position with SC>0 but basis=0 should still be listed"
        
        pos = positions[0]
        assert pos.purchase_basis == Decimal("0.00")  # FIFO consumed all basis
        # Current SC: 2675 (session end) - 2500 (redemption) = 175
        assert pos.total_sc == Decimal("175.00")
        assert pos.current_value == Decimal("175.00")
        # Unrealized P/L: 175 - 0 = 175 (pure profit remainder)
        assert pos.unrealized_pl == Decimal("175.00")
    
    def test_basis_zero_sc_near_zero_position_does_not_show(self, db, repo):
        """
        Scenario: Basis consumed and SC is effectively zero (< threshold).
        Position should NOT appear.
        """
        # Purchase with basis fully consumed
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 0.00)
        """)
        
        # Session ending with tiny SC (< 0.01)
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 0.005, 0.005, 'completed')
        """)
        db.commit()
        
        # Check unrealized position
        positions = repo.get_all_positions()
        
        # Position should NOT appear (SC < threshold)
        assert len(positions) == 0, "Position with basis=0 and SC<threshold should not be listed"
    
    def test_balance_closed_marker_still_suppresses_position(self, db, repo):
        """
        Scenario: Basis=0, SC>0, but explicit "Balance Closed" redemption exists.
        Position should NOT appear (user explicitly closed it).
        """
        # Purchase with basis consumed
        db.execute("""
            INSERT INTO purchases
            (user_id, site_id, purchase_date, purchase_time, amount, sc_received, remaining_amount)
            VALUES (1, 1, '2024-01-01', '10:00:00', 100.00, 100.00, 0.00)
        """)
        
        # Session with SC remaining
        db.execute("""
            INSERT INTO game_sessions
            (user_id, site_id, game_id, session_date, session_time, end_date, end_time,
             starting_balance, ending_balance, ending_redeemable, status)
            VALUES (1, 1, 1, '2024-01-01', '11:00:00', '2024-01-01', '12:00:00',
                    100.00, 50.00, 50.00, 'completed')
        """)
        
        # "Balance Closed" marker redemption
        db.execute("""
            INSERT INTO redemptions
            (user_id, site_id, redemption_date, redemption_time, amount, processed, notes)
            VALUES (1, 1, '2024-01-03', '10:00:00', 0.00, 1, 'Balance Closed - Net Loss: $0.00 (50.00 SC marked dormant)')
        """)
        db.commit()
        
        # Check unrealized position
        positions = repo.get_all_positions()
        
        # Position should NOT appear (explicitly closed by user)
        assert len(positions) == 0, "Position with 'Balance Closed' marker should not be listed"
