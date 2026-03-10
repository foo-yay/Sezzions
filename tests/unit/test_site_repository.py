"""
Unit tests for SiteRepository
"""
import pytest
from models.site import Site


def test_create_site(site_repo):
    """Test creating a site in database"""
    site = Site(name="Stake", url="https://stake.us", playthrough_requirement=3.0)
    created_site = site_repo.create(site)
    
    assert created_site.id is not None
    assert created_site.name == "Stake"
    assert created_site.url == "https://stake.us"
    assert created_site.playthrough_requirement == pytest.approx(3.0)


def test_get_site_by_id(site_repo):
    """Test getting site by ID"""
    site = Site(name="Fortune Coins")
    created_site = site_repo.create(site)
    
    retrieved_site = site_repo.get_by_id(created_site.id)
    assert retrieved_site is not None
    assert retrieved_site.name == "Fortune Coins"


def test_get_site_by_id_not_found(site_repo):
    """Test getting non-existent site returns None"""
    site = site_repo.get_by_id(9999)
    assert site is None


def test_get_all_sites(site_repo):
    """Test getting all sites"""
    site_repo.create(Site(name="Site 1"))
    site_repo.create(Site(name="Site 2"))
    site_repo.create(Site(name="Site 3"))
    
    sites = site_repo.get_all()
    assert len(sites) == 3


def test_get_active_sites(site_repo):
    """Test getting only active sites"""
    site1 = site_repo.create(Site(name="Active Site", is_active=True))
    site2 = site_repo.create(Site(name="Inactive Site", is_active=False))
    
    active_sites = site_repo.get_active()
    assert len(active_sites) == 1
    assert active_sites[0].name == "Active Site"


def test_update_site(site_repo):
    """Test updating site"""
    site = site_repo.create(Site(name="Old Name"))
    site.name = "New Name"
    site.url = "https://newsite.com"
    site.sc_rate = 2.0
    site.playthrough_requirement = 4.0
    
    updated_site = site_repo.update(site)
    assert updated_site.name == "New Name"
    assert updated_site.url == "https://newsite.com"
    assert updated_site.sc_rate == 2.0
    assert updated_site.playthrough_requirement == pytest.approx(4.0)
    
    # Verify in database
    retrieved = site_repo.get_by_id(site.id)
    assert retrieved.name == "New Name"
    assert retrieved.playthrough_requirement == pytest.approx(4.0)


def test_delete_site(site_repo):
    """Test deleting site"""
    site = site_repo.create(Site(name="To Delete"))
    site_id = site.id
    
    site_repo.delete(site_id)
    
    # Verify deleted
    retrieved = site_repo.get_by_id(site_id)
    assert retrieved is None
