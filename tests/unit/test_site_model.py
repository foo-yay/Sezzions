"""
Unit tests for Site model
"""
import pytest
from models.site import Site


def test_site_creation():
    """Test creating a site"""
    site = Site(name="Stake", url="https://stake.us")
    assert site.name == "Stake"
    assert site.url == "https://stake.us"
    assert site.sc_rate == 1.0
    assert site.is_active is True
    assert site.id is None


def test_site_validation_empty_name():
    """Test that empty name raises error"""
    with pytest.raises(ValueError, match="Site name is required"):
        Site(name="")


def test_site_validation_whitespace_name():
    """Test that whitespace-only name raises error"""
    with pytest.raises(ValueError, match="Site name is required"):
        Site(name="   ")


def test_site_strips_name():
    """Test that site name is stripped of whitespace"""
    site = Site(name="  Stake.us  ")
    assert site.name == "Stake.us"


def test_site_str():
    """Test string representation"""
    site = Site(name="Fortune Coins")
    assert str(site) == "Fortune Coins"


def test_site_custom_sc_rate():
    """Test site with custom SC rate"""
    site = Site(name="Modo", sc_rate=2.5)
    assert site.sc_rate == 2.5


def test_site_invalid_sc_rate():
    """Test that zero or negative SC rate raises error"""
    with pytest.raises(ValueError, match="SC rate must be positive"):
        Site(name="Test Site", sc_rate=0)
    
    with pytest.raises(ValueError, match="SC rate must be positive"):
        Site(name="Test Site", sc_rate=-1.0)
