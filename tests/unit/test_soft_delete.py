"""
Tests for soft delete functionality (Issue #92)
"""
import pytest
from decimal import Decimal
from datetime import date
from repositories.database import DatabaseManager
from repositories.purchase_repository import PurchaseRepository
from repositories.redemption_repository import RedemptionRepository
from repositories.game_session_repository import GameSessionRepository
from models.purchase import Purchase
from models.redemption import Redemption
from models.game_session import GameSession


@pytest.fixture
def db():
    """Create in-memory database for testing"""
    db = DatabaseManager(":memory:")
    
    # Create required parent records for foreign keys (order matters!)
    db.execute("INSERT INTO users (id, name) VALUES (1, 'Test User')")
    db.execute("INSERT INTO sites (id, name) VALUES (1, 'Test Site')")
    db.execute("INSERT INTO game_types (id, name) VALUES (1, 'Test Type')")
    db.execute("INSERT INTO games (id, name, game_type_id) VALUES (1, 'Test Game', 1)")
    db.execute("INSERT INTO redemption_methods (id, name) VALUES (1, 'Test Method')")
    db.commit()
    
    yield db
    db.close()


@pytest.fixture
def purchase_repo(db):
    return PurchaseRepository(db)


@pytest.fixture
def redemption_repo(db):
    return RedemptionRepository(db)


@pytest.fixture
def session_repo(db):
    return GameSessionRepository(db)


def test_purchase_soft_delete_excludes_from_queries(db, purchase_repo):
    """Test that soft-deleted purchases are excluded from queries"""
    # Create a purchase
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        purchase_time="10:00:00"
    )
    created = purchase_repo.create(purchase)
    purchase_id = created.id
    
    # Verify it appears in queries
    assert purchase_repo.get_by_id(purchase_id) is not None
    assert len(purchase_repo.get_all()) == 1
    assert len(purchase_repo.get_available_for_fifo(1, 1)) == 1
    
    # Soft delete
    purchase_repo.delete(purchase_id)
    
    # Verify it's excluded from all queries
    assert purchase_repo.get_by_id(purchase_id) is None
    assert len(purchase_repo.get_all()) == 0
    assert len(purchase_repo.get_available_for_fifo(1, 1)) == 0


def test_purchase_restore_after_soft_delete(db, purchase_repo):
    """Test that restore() brings back soft-deleted purchases"""
    # Create and soft-delete
    purchase = Purchase(
        user_id=1,
        site_id=1,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        purchase_time="10:00:00"
    )
    created = purchase_repo.create(purchase)
    purchase_id = created.id
    purchase_repo.delete(purchase_id)
    
    # Verify it's gone
    assert purchase_repo.get_by_id(purchase_id) is None
    
    # Restore
    purchase_repo.restore(purchase_id)
    
    # Verify it's back
    restored = purchase_repo.get_by_id(purchase_id)
    assert restored is not None
    assert restored.id == purchase_id


def test_redemption_soft_delete_excludes_from_queries(db, redemption_repo):
    """Test that soft-deleted redemptions are excluded from queries"""
    # Create a redemption
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 2),
        redemption_time="14:00:00",
        redemption_method_id=1
    )
    created = redemption_repo.create(redemption)
    redemption_id = created.id
    
    # Verify it appears in queries
    assert redemption_repo.get_by_id(redemption_id) is not None
    assert len(redemption_repo.get_all()) == 1
    
    # Soft delete
    redemption_repo.delete(redemption_id)
    
    # Verify it's excluded
    assert redemption_repo.get_by_id(redemption_id) is None
    assert len(redemption_repo.get_all()) == 0


def test_redemption_restore_after_soft_delete(db, redemption_repo):
    """Test that restore() brings back soft-deleted redemptions"""
    # Create and soft-delete
    redemption = Redemption(
        user_id=1,
        site_id=1,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 2),
        redemption_time="14:00:00",
        redemption_method_id=1
    )
    created = redemption_repo.create(redemption)
    redemption_id = created.id
    redemption_repo.delete(redemption_id)
    
    # Restore
    redemption_repo.restore(redemption_id)
    
    # Verify it's back
    restored = redemption_repo.get_by_id(redemption_id)
    assert restored is not None
    assert restored.id == redemption_id


def test_game_session_soft_delete_excludes_from_queries(db, session_repo):
    """Test that soft-deleted sessions are excluded from queries"""
    # Create a session
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 3),
        session_time="18:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    )
    created = session_repo.create(session)
    session_id = created.id
    
    # Verify it appears in queries
    assert session_repo.get_by_id(session_id) is not None
    assert len(session_repo.get_all()) == 1
    
    # Soft delete
    session_repo.delete(session_id)
    
    # Verify it's excluded
    assert session_repo.get_by_id(session_id) is None
    assert len(session_repo.get_all()) == 0


def test_game_session_restore_after_soft_delete(db, session_repo):
    """Test that restore() brings back soft-deleted sessions"""
    # Create and soft-delete
    session = GameSession(
        user_id=1,
        site_id=1,
        game_id=1,
        session_date=date(2026, 1, 3),
        session_time="18:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00")
    )
    created = session_repo.create(session)
    session_id = created.id
    session_repo.delete(session_id)
    
    # Restore
    session_repo.restore(session_id)
    
    # Verify it's back
    restored = session_repo.get_by_id(session_id)
    assert restored is not None
    assert restored.id == session_id


def test_fifo_excludes_soft_deleted_purchases(db, purchase_repo):
    """CRITICAL: Soft-deleted purchases must not appear in FIFO calculations"""
    # Create 3 purchases
    p1 = purchase_repo.create(Purchase(
        user_id=1, site_id=1,
        amount=Decimal("100.00"), remaining_amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1), purchase_time="10:00:00"
    ))
    p2 = purchase_repo.create(Purchase(
        user_id=1, site_id=1,
        amount=Decimal("200.00"), remaining_amount=Decimal("200.00"),
        purchase_date=date(2026, 1, 2), purchase_time="11:00:00"
    ))
    p3 = purchase_repo.create(Purchase(
        user_id=1, site_id=1,
        amount=Decimal("300.00"), remaining_amount=Decimal("300.00"),
        purchase_date=date(2026, 1, 3), purchase_time="12:00:00"
    ))
    
    # All 3 should be available for FIFO
    fifo_purchases = purchase_repo.get_available_for_fifo(1, 1)
    assert len(fifo_purchases) == 3
    
    # Soft delete the middle purchase
    purchase_repo.delete(p2.id)
    
    # Only 2 should remain for FIFO
    fifo_purchases = purchase_repo.get_available_for_fifo(1, 1)
    assert len(fifo_purchases) == 2
    assert fifo_purchases[0].id == p1.id
    assert fifo_purchases[1].id == p3.id
