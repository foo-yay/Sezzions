"""
Site repository - Data access for Site entity
"""
from typing import Optional, List
from models.site import Site


class SiteRepository:
    """Repository for Site entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_by_id(self, site_id: int) -> Optional[Site]:
        """Get site by ID"""
        query = "SELECT * FROM sites WHERE id = ?"
        row = self.db.fetch_one(query, (site_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(self) -> List[Site]:
        """Get all sites"""
        query = "SELECT * FROM sites ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def get_active(self) -> List[Site]:
        """Get active sites only"""
        query = "SELECT * FROM sites WHERE is_active = 1 ORDER BY name"
        rows = self.db.fetch_all(query)
        return [self._row_to_model(row) for row in rows]
    
    def create(self, site: Site) -> Site:
        """Create new site"""
        query = """
            INSERT INTO sites (name, url, sc_rate, is_active, notes)
            VALUES (?, ?, ?, ?, ?)
        """
        site_id = self.db.execute(query, (
            site.name,
            site.url,
            site.sc_rate,
            1 if site.is_active else 0,
            site.notes
        ))
        site.id = site_id
        return site
    
    def update(self, site: Site) -> Site:
        """Update existing site"""
        if not site.id:
            raise ValueError("Cannot update site without ID")
        
        query = """
            UPDATE sites
            SET name = ?, url = ?, sc_rate = ?, is_active = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self.db.execute(query, (
            site.name,
            site.url,
            site.sc_rate,
            1 if site.is_active else 0,
            site.notes,
            site.id
        ))
        return site
    
    def delete(self, site_id: int) -> None:
        """Delete site (hard delete)"""
        query = "DELETE FROM sites WHERE id = ?"
        self.db.execute(query, (site_id,))
    
    def _row_to_model(self, row: dict) -> Site:
        """Convert database row to Site model"""
        return Site(
            id=row['id'],
            name=row['name'],
            url=row.get('url'),
            sc_rate=float(row['sc_rate']) if row.get('sc_rate') else 1.0,
            is_active=bool(row['is_active']),
            notes=row.get('notes'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
