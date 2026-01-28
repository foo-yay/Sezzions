"""
Unit tests for RedemptionMethod model
"""
import pytest
from models.redemption_method import RedemptionMethod


def test_method_creation():
    """Test creating a redemption method"""
    method = RedemptionMethod(name="ACH Transfer", notes="Bank transfer")
    assert method.name == "ACH Transfer"
    assert method.notes == "Bank transfer"
    assert method.is_active is True
    assert method.id is None


def test_method_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="Redemption method name is required"):
        RedemptionMethod(name="")


def test_method_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="Redemption method name is required"):
        RedemptionMethod(name="   ")


def test_method_strips_name():
    """Test that method name is stripped of whitespace"""
    method = RedemptionMethod(name="  PayPal  ")
    assert method.name == "PayPal"


def test_method_str():
    """Test string representation"""
    method = RedemptionMethod(name="Check")
    assert str(method) == "Check"
