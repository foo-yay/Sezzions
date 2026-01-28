"""
Unit tests for ValidationService
"""
import pytest
from decimal import Decimal
from datetime import date
from services.validation_service import ValidationService
from models.purchase import Purchase


def test_validate_fifo_allocations_valid(test_db, sample_user, sample_site, purchase_repo, redemption_service):
    """Test validation passes for valid FIFO allocations"""
    # Create valid purchase and redemption
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=True,
        more_remaining=True
    )
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_fifo_allocations(sample_user.id, sample_site.id)
    
    assert result["is_valid"] is True
    assert result["total_errors"] == 0


def test_validate_fifo_negative_remaining(test_db, sample_user, sample_site, purchase_repo):
    """Test validation catches negative remaining amounts"""
    # Create valid purchase first, then corrupt data directly in DB (data corruption scenario)
    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Directly corrupt the database to simulate data corruption
    test_db.execute(
        "UPDATE purchases SET remaining_amount = ? WHERE id = ?",
        ("-10.00", purchase.id)
    )
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_fifo_allocations(sample_user.id, sample_site.id)
    
    assert result["is_valid"] is False
    assert result["total_errors"] > 0
    assert "negative remaining amount" in result["errors"][0].lower()


def test_validate_fifo_redemptions_without_allocation(test_db, sample_user, sample_site, redemption_service):
    """Test validation warns about redemptions without FIFO"""
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=False  # No FIFO
    )
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_fifo_allocations(sample_user.id, sample_site.id)
    
    assert result["total_warnings"] > 0
    assert "without FIFO" in result["warnings"][0]


def test_validate_session_calculations_valid(test_db, sample_user, sample_site, sample_game, game_session_service):
    """Test validation passes for correct session P/L"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("120.00"),
        ending_redeemable=Decimal("20.00"),
        calculate_pl=True
    )
    game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="23:59:59",
    )
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_session_calculations(sample_user.id, sample_site.id)
    
    assert result["is_valid"] is True
    assert result["total_errors"] == 0


def test_validate_session_calculations_mismatch(test_db, sample_user, sample_site, sample_game, game_session_repo):
    """Test validation catches P/L calculation mismatches"""
    from models.game_session import GameSession
    
    # Create session with incorrect P/L
    session = game_session_repo.create(GameSession(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("120.00"),
        profit_loss=Decimal("50.00")  # Should be 20.00
    ))
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_session_calculations(sample_user.id, sample_site.id)
    
    assert result["is_valid"] is False
    assert result["total_errors"] > 0
    assert "mismatch" in result["errors"][0].lower()


def test_validate_all(test_db, sample_user, sample_site, purchase_repo, redemption_service, game_session_service, sample_game):
    """Test comprehensive validation"""
    # Create valid data
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=True,
        more_remaining=True
    )
    
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("50.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("60.00"),
        ending_redeemable=Decimal("10.00")
    )
    game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="23:59:59",
    )
    
    validation_service = ValidationService(test_db)
    result = validation_service.validate_all(sample_user.id, sample_site.id)
    
    assert result["is_valid"] is True
    assert result["total_errors"] == 0
    assert "fifo_validation" in result
    assert "session_validation" in result


def test_get_data_summary(test_db, sample_user, sample_site, purchase_repo):
    """Test getting data summary counts"""
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    validation_service = ValidationService(test_db)
    summary = validation_service.get_data_summary()
    
    assert "users" in summary
    assert "purchases" in summary
    assert summary["users"] >= 1
    assert summary["purchases"] >= 1
