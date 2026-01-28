"""
Tests for automatic cashback calculation.

Verifies that cashback_earned is automatically calculated:
1. At purchase creation time
2. At purchase update time (when amount or card changes)
3. At recalculation time (bulk rebuild)
"""
import pytest
from decimal import Decimal
from datetime import date

from repositories.database import DatabaseManager
from services.purchase_service import PurchaseService
from services.recalculation_service import RecalculationService
from services.game_session_service import GameSessionService
from repositories.purchase_repository import PurchaseRepository
from repositories.card_repository import CardRepository


@pytest.fixture
def db():
    """Create test database in memory."""
    database = DatabaseManager(':memory:')
    yield database
    database.close()


@pytest.fixture
def setup_test_data(db):
    """Create test user, site, and card with 2% cashback rate."""
    conn = db._connection
    cursor = conn.cursor()
    
    # Create user
    cursor.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)",
        ("testuser", "test@example.com")
    )
    user_id = cursor.lastrowid
    
    # Create site
    cursor.execute(
        "INSERT INTO sites (name, url) VALUES (?, ?)",
        ("Test Casino", "https://test.casino")
    )
    site_id = cursor.lastrowid
    
    # Create card with 2% cashback
    cursor.execute(
        "INSERT INTO cards (name, user_id, last_four, cashback_rate) VALUES (?, ?, ?, ?)",
        ("Test Card", user_id, "1234", 2.0)
    )
    card_id = cursor.lastrowid
    
    conn.commit()
    
    return {
        'user_id': user_id,
        'site_id': site_id,
        'card_id': card_id
    }


def test_cashback_auto_calculated_on_purchase_creation(db, setup_test_data):
    """Test that cashback is automatically calculated when creating a purchase."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create purchase without specifying cashback_earned
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=test_data['card_id'],
        # cashback_earned NOT provided - should auto-calculate
    )
    
    # Verify cashback was calculated: $100 * 2% = $2.00
    assert purchase.cashback_earned == Decimal("2.00")


def test_cashback_auto_calculated_on_amount_update(db, setup_test_data):
    """Test that cashback is recalculated when purchase amount changes."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create purchase with $100
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=test_data['card_id'],
    )
    
    # Verify initial cashback: $100 * 2% = $2.00
    assert purchase.cashback_earned == Decimal("2.00")
    
    # Update amount to $200 (cashback should recalculate)
    updated_purchase = purchase_service.update_purchase(
        purchase_id=purchase.id,
        amount=Decimal("200.00")
    )
    
    # Verify cashback recalculated: $200 * 2% = $4.00
    assert updated_purchase.cashback_earned == Decimal("4.00")


def test_cashback_auto_calculated_on_card_change(db, setup_test_data):
    """Test that cashback is recalculated when card changes."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create second card with 3% cashback
    conn = db._connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (name, user_id, last_four, cashback_rate) VALUES (?, ?, ?, ?)",
        ("Premium Card", test_data['user_id'], "5678", 3.0)
    )
    premium_card_id = cursor.lastrowid
    conn.commit()
    
    # Create purchase with 2% card
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=test_data['card_id'],
    )
    
    # Verify initial cashback: $100 * 2% = $2.00
    assert purchase.cashback_earned == Decimal("2.00")
    
    # Change to premium card (cashback should recalculate)
    updated_purchase = purchase_service.update_purchase(
        purchase_id=purchase.id,
        card_id=premium_card_id
    )
    
    # Verify cashback recalculated: $100 * 3% = $3.00
    assert updated_purchase.cashback_earned == Decimal("3.00")


def test_cashback_recalculated_during_rebuild_all(db, setup_test_data):
    """Test that cashback is recalculated during full rebuild."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    from repositories.game_session_repository import GameSessionRepository
    session_repo = GameSessionRepository(db)
    game_session_service = GameSessionService(session_repo)
    recalc_service = RecalculationService(db, game_session_service)
    
    # Create purchase WITHOUT explicit cashback (auto-calculated)
    auto_purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=test_data['card_id'],
        # cashback_earned NOT provided - should auto-calculate $2.00
    )
    
    # Verify auto-calculated cashback
    assert auto_purchase.cashback_earned == Decimal("2.00")
    assert auto_purchase.cashback_is_manual == False
    
    # Manually corrupt the auto-calculated cashback in DB to test recalc fixes it
    conn = db._connection
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE purchases SET cashback_earned = ? WHERE id = ?",
        ("99.99", auto_purchase.id)
    )
    conn.commit()
    
    # Verify corruption
    corrupted = purchase_repo.get_by_id(auto_purchase.id)
    assert corrupted.cashback_earned == Decimal("99.99")
    
    # Run recalculation
    result = recalc_service.rebuild_all()
    
    # Verify cashback was corrected: $100 * 2% = $2.00
    corrected_purchase = purchase_repo.get_by_id(auto_purchase.id)
    assert corrected_purchase.cashback_earned == Decimal("2.00")


def test_manual_cashback_preserved_during_rebuild(db, setup_test_data):
    """Test that manually set cashback is NOT recalculated during rebuild."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    from repositories.game_session_repository import GameSessionRepository
    session_repo = GameSessionRepository(db)
    game_session_service = GameSessionService(session_repo)
    recalc_service = RecalculationService(db, game_session_service)
    
    # Create purchase with EXPLICIT cashback (manual override - e.g., promotional bonus)
    manual_purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=test_data['card_id'],  # 2% card would auto-calc $2.00
        cashback_earned=Decimal("10.00")  # Manual override - promotional bonus
    )
    
    # Verify manual cashback was saved with manual flag
    assert manual_purchase.cashback_earned == Decimal("10.00")
    assert manual_purchase.cashback_is_manual == True
    
    # Run recalculation
    result = recalc_service.rebuild_all()
    
    # Verify manual cashback was PRESERVED (not recalculated to $2.00)
    preserved_purchase = purchase_repo.get_by_id(manual_purchase.id)
    assert preserved_purchase.cashback_earned == Decimal("10.00")
    assert preserved_purchase.cashback_is_manual == True


def test_cashback_zero_when_no_card(db, setup_test_data):
    """Test that cashback is zero when no card is specified."""
    test_data = setup_test_data
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create purchase without card
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=None  # No card
    )
    
    # Verify cashback is zero
    assert purchase.cashback_earned == Decimal("0.00")


def test_cashback_zero_when_card_has_zero_rate(db, setup_test_data):
    """Test that cashback is zero when card has 0% cashback rate."""
    test_data = setup_test_data
    
    # Create card with 0% cashback
    conn = db._connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (name, user_id, last_four, cashback_rate) VALUES (?, ?, ?, ?)",
        ("No Cashback Card", test_data['user_id'], "0000", 0.0)
    )
    zero_card_id = cursor.lastrowid
    conn.commit()
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create purchase with zero-cashback card
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("100.00"),
        purchase_date=date.today(),
        card_id=zero_card_id
    )
    
    # Verify cashback is zero
    assert purchase.cashback_earned == Decimal("0.00")


def test_cashback_rounding(db, setup_test_data):
    """Test that cashback is properly rounded to 2 decimal places."""
    test_data = setup_test_data
    
    # Create card with 1.5% cashback (will produce rounding scenarios)
    conn = db._connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO cards (name, user_id, last_four, cashback_rate) VALUES (?, ?, ?, ?)",
        ("Fractional Card", test_data['user_id'], "9999", 1.5)
    )
    fractional_card_id = cursor.lastrowid
    conn.commit()
    
    # Create services
    purchase_repo = PurchaseRepository(db)
    card_repo = CardRepository(db)
    purchase_service = PurchaseService(purchase_repo, card_repo=card_repo)
    
    # Create purchase: $33.33 * 1.5% = $0.49995 -> should round to $0.50
    purchase = purchase_service.create_purchase(
        user_id=test_data['user_id'],
        site_id=test_data['site_id'],
        amount=Decimal("33.33"),
        purchase_date=date.today(),
        card_id=fractional_card_id
    )
    
    # Verify proper rounding
    assert purchase.cashback_earned == Decimal("0.50")
