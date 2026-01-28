"""
Unit tests for RedemptionMethodService
"""
import pytest
from models.redemption_method import RedemptionMethod


def test_create_method_service(method_service):
    """Test creating redemption method through service"""
    method = method_service.create_method(
        name="ACH Transfer",
        notes="Bank transfer"
    )
    
    assert method.id is not None
    assert method.name == "ACH Transfer"
    assert method.notes == "Bank transfer"


def test_create_method_validation(method_service):
    """Test service validates redemption method name"""
    with pytest.raises(ValueError, match="Redemption method name is required"):
        method_service.create_method(name="")


def test_update_method_service(method_service, sample_method):
    """Test updating redemption method through service"""
    updated = method_service.update_method(
        sample_method.id,
        name="Updated Name",
        notes="Updated notes"
    )
    
    assert updated.name == "Updated Name"
    assert updated.notes == "Updated notes"


def test_deactivate_method(method_service, sample_method):
    """Test deactivating redemption method"""
    method = method_service.deactivate_method(sample_method.id)
    assert method.is_active is False


def test_activate_method(method_service, sample_method):
    """Test activating redemption method"""
    # First deactivate
    method_service.deactivate_method(sample_method.id)
    
    # Then activate
    method = method_service.activate_method(sample_method.id)
    assert method.is_active is True


def test_list_active_methods(method_service):
    """Test listing active redemption methods"""
    method_service.create_method(name="Active 1")
    method_service.create_method(name="Active 2")
    method3 = method_service.create_method(name="Inactive")
    method_service.deactivate_method(method3.id)
    
    active = method_service.list_active_methods()
    assert len(active) == 2


def test_list_all_methods(method_service):
    """Test listing all redemption methods"""
    method_service.create_method(name="Method 1")
    method_service.create_method(name="Method 2")
    method3 = method_service.create_method(name="Method 3")
    method_service.deactivate_method(method3.id)
    
    all_methods = method_service.list_all_methods()
    assert len(all_methods) == 3
