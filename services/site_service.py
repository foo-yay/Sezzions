"""
Site service - Business logic for Site operations
"""
from typing import List, Optional
from models.site import Site
from repositories.site_repository import SiteRepository


class SiteService:
    """Business logic for Site operations"""
    
    def __init__(self, site_repo: SiteRepository):
        self.site_repo = site_repo
    
    def create_site(
        self,
        name: str,
        url: Optional[str] = None,
        sc_rate: float = 1.0,
        playthrough_requirement: float = 1.0,
        notes: Optional[str] = None
    ) -> Site:
        """Create new site with validation"""
        # Create site model (validates in __post_init__)
        site = Site(
            name=name,
            url=url,
            sc_rate=sc_rate,
            playthrough_requirement=playthrough_requirement,
            notes=notes,
        )
        
        # Save to database
        return self.site_repo.create(site)
    
    def update_site(self, site_id: int, **kwargs) -> Site:
        """Update site with validation"""
        site = self.site_repo.get_by_id(site_id)
        if not site:
            raise ValueError(f"Site {site_id} not found")
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(site, key):
                setattr(site, key, value)
        
        # Validate (will raise if invalid)
        site.__post_init__()
        
        return self.site_repo.update(site)
    
    def deactivate_site(self, site_id: int) -> Site:
        """Deactivate site (soft delete)"""
        return self.update_site(site_id, is_active=False)
    
    def activate_site(self, site_id: int) -> Site:
        """Activate site"""
        return self.update_site(site_id, is_active=True)
    
    def delete_site(self, site_id: int) -> None:
        """Hard delete site (use with caution - prefer deactivate_site)"""
        site = self.site_repo.get_by_id(site_id)
        if not site:
            raise ValueError(f"Site {site_id} not found")
        
        # Note: Cascade delete behavior is handled at database level
        # via foreign key constraints
        try:
            self.site_repo.delete(site_id)
        except Exception as e:
            if "FOREIGN KEY constraint failed" in str(e):
                raise ValueError(
                    f"Cannot delete site '{site.name}' because it has related records. "
                    f"Purchases, redemptions, or game sessions still reference this site. "
                    f"Consider deactivating instead of deleting."
                ) from e
            raise
    
    def list_active_sites(self) -> List[Site]:
        """Get all active sites"""
        return self.site_repo.get_active()
    
    def list_all_sites(self) -> List[Site]:
        """Get all sites (including inactive)"""
        return self.site_repo.get_all()
    
    def get_site(self, site_id: int) -> Optional[Site]:
        """Get site by ID"""
        return self.site_repo.get_by_id(site_id)
