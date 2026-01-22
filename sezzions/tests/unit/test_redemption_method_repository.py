"""
Unit tests for RedemptionMethodRepository
"""
import pytest
from models.redemption_method import RedemptionMethod


def test_create_method(method_repo):
    """Test creating a redemption method in database"""
    method = RedemptionMethod(name="ACH Transfer")
    created_method = method_repo.create(method)
    
    assert created_method.id is not None
    assert created_method.name == "ACH Transfer"


def test_get_method_by_id(method_repo):
    """Test getting redemption method by ID"""
    method = RedemptionMethod(name="PayPal")
    created_method = method_repo.create(method)
    
    retrieved_method = method_repo.get_by_id(created_method.id)
    assert retrieved_method is not None
    assert retrieved_method.name == "PayPal"


def test_get_method_by_id_not_found(method_repo):
    """Test getting non-existent redemption method returns None"""
    method = method_repo.get_by_id(9999)
    assert method is None


def test_get_all_methods(method_repo):
    """Test getting all redemption methods"""
    method_repo.create(RedemptionMethod(name="ACH"))
    method_repo.create(RedemptionMethod(name="Check"))
    method_repo.create(RedemptionMethod(name="PayPal"))
    
    methods = method_repo.get_all()
    assert len(methods) == 3


def test_get_active_methods(method_repo):
    """Test getting only active redemption methods"""
    method_repo.create(RedemptionMethod(name="Active", is_active=True))
    method_repo.create(RedemptionMethod(name="Inactive", is_active=False))
    
    active_methods = method_repo.get_active()
    assert len(active_methods) == 1
    assert active_methods[0].name == "Active"


def test_update_method(method_repo):
    """Test updating redemption method"""
    method = method_repo.create(RedemptionMethod(name="Old Name"))
    method.name = "New Name"
    method.notes = "Updated notes"
    
    updated_method = method_repo.update(method)
    assert updated_method.name == "New Name"
    assert updated_method.notes == "Updated notes"
    
    # Verify in database
    retrieved = method_repo.get_by_id(method.id)
    assert retrieved.name == "New Name"


def test_delete_method(method_repo):
    """Test deleting redemption method"""
    method = method_repo.create(RedemptionMethod(name="To Delete"))
    method_id = method.id
    
    method_repo.delete(method_id)
    
    # Verify deleted
    retrieved = method_repo.get_by_id(method_id)
    assert retrieved is None
