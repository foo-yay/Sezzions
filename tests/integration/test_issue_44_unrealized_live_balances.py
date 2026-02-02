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
