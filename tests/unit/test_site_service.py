"""
Unit tests for SiteService
"""
import pytest
from models.site import Site


def test_create_site_service(site_service):
    """Test creating site through service"""
    site = site_service.create_site(
        name="Stake",
        url="https://stake.us",
        sc_rate=1.0,
        notes="Test site"
    )
    
    assert site.id is not None
    assert site.name == "Stake"
    assert site.url == "https://stake.us"
    assert site.sc_rate == 1.0


def test_create_site_validation(site_service):
    """Test service validates site input"""
    with pytest.raises(ValueError, match="Site name is required"):
        site_service.create_site(name="")


def test_create_site_invalid_sc_rate(site_service):
    """Test service validates SC rate"""
    with pytest.raises(ValueError, match="SC rate must be positive"):
        site_service.create_site(name="Test Site", sc_rate=0)


def test_update_site_service(site_service, sample_site):
    """Test updating site through service"""
    updated = site_service.update_site(
        sample_site.id,
        name="Updated Name",
        url="https://updated.com"
    )
    
    assert updated.name == "Updated Name"
    assert updated.url == "https://updated.com"


def test_deactivate_site(site_service, sample_site):
    """Test deactivating site"""
    site = site_service.deactivate_site(sample_site.id)
    assert site.is_active is False


def test_activate_site(site_service, sample_site):
    """Test activating site"""
    # First deactivate
    site_service.deactivate_site(sample_site.id)
    
    # Then activate
    site = site_service.activate_site(sample_site.id)
    assert site.is_active is True


def test_list_active_sites(site_service):
    """Test listing active sites"""
    site1 = site_service.create_site(name="Active 1")
    site2 = site_service.create_site(name="Active 2")
    site3 = site_service.create_site(name="Inactive")
    site_service.deactivate_site(site3.id)
    
    active = site_service.list_active_sites()
    assert len(active) == 2


def test_list_all_sites(site_service):
    """Test listing all sites"""
    site_service.create_site(name="Site 1")
    site_service.create_site(name="Site 2")
    site_service.create_site(name="Site 3")
    
    all_sites = site_service.list_all_sites()
    assert len(all_sites) == 3
