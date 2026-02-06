"""
Repair Mode Service - Manage stale pair tracking when auto-cascade is disabled

When Repair Mode is enabled:
- CRUD writes skip automatic derived rebuilds
- Affected (user_id, site_id) pairs are marked as "stale" with a rebuild boundary
- User must explicitly rebuild stale pairs via Tools

This service manages the stale pair registry and boundary tracking.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class StalePair:
    """Represents a (user_id, site_id) pair needing rebuild."""
    user_id: int
    site_id: int
    from_date: str  # YYYY-MM-DD
    from_time: str  # HH:MM:SS
    updated_at: str  # ISO timestamp
    reasons: List[str]  # e.g., ["purchase edit", "redemption delete"]
    user_name: str = ""  # User name for display
    site_name: str = ""  # Site name for display
    
    def key(self) -> str:
        """Return unique key for this pair."""
        return f"{self.user_id}:{self.site_id}"


class RepairModeService:
    """
    Manages stale pair tracking for Repair Mode.
    
    Stale pairs are persisted in settings.json via the Settings class.
    """
    
    def __init__(self, settings):
        """
        Initialize service with settings manager.
        
        Args:
            settings: Settings instance (duck-typed, must support get/set)
        """
        self.settings = settings
    
    def is_enabled(self) -> bool:
        """Check if Repair Mode is currently enabled."""
        return bool(self.settings.get('repair_mode_enabled', False))
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable Repair Mode."""
        self.settings.set('repair_mode_enabled', enabled)
    
    def get_stale_pairs(self) -> List[StalePair]:
        """Get all currently stale pairs."""
        stale_data = self.settings.get('repair_mode_stale_pairs', {})
        
        # Try to get user/site names from repositories (may not be available in tests)
        try:
            from repositories.user_repository import UserRepository
            from repositories.site_repository import SiteRepository
            from repositories.database import get_connection
            conn = get_connection()
            user_repo = UserRepository(conn)
            site_repo = SiteRepository(conn)
            users_dict = {u.id: u.username for u in user_repo.get_all()}
            sites_dict = {s.id: s.site_name for s in site_repo.get_all()}
        except:
            users_dict = {}
            sites_dict = {}
        
        pairs = []
        for key, data in stale_data.items():
            try:
                user_id, site_id = key.split(':')
                user_id_int = int(user_id)
                site_id_int = int(site_id)
                
                # Get user name
                user_name = users_dict.get(user_id_int, f"Unknown User (ID: {user_id_int})")
                site_name = sites_dict.get(site_id_int, f"Unknown Site (ID: {site_id_int})")
                
                pairs.append(StalePair(
                    user_id=user_id_int,
                    site_id=site_id_int,
                    from_date=data.get('from_date', '1900-01-01'),
                    from_time=data.get('from_time', '00:00:00'),
                    updated_at=data.get('updated_at', ''),
                    reasons=data.get('reasons', []),
                    user_name=user_name,
                    site_name=site_name
                ))
            except (ValueError, KeyError):
                continue
        
        return pairs
    
    def mark_pair_stale(
        self,
        user_id: int,
        site_id: int,
        from_date: str,
        from_time: str,
        reason: Optional[str] = None
    ) -> None:
        """
        Mark a (user_id, site_id) pair as stale.
        
        If the pair is already stale, keeps the earliest boundary and appends reason.
        
        Args:
            user_id: User ID
            site_id: Site ID
            from_date: Rebuild boundary date (YYYY-MM-DD)
            from_time: Rebuild boundary time (HH:MM:SS)
            reason: Optional reason string for UI display
        """
        key = f"{user_id}:{site_id}"
        stale_data = self.settings.get('repair_mode_stale_pairs', {})
        
        if key in stale_data:
            # Pair already stale - keep earliest boundary
            existing = stale_data[key]
            # Handle both HH:MM and HH:MM:SS formats
            existing_time = existing['from_time']
            if len(existing_time) == 5:  # HH:MM
                existing_time += ":00"
            new_time = from_time if from_time else "00:00:00"
            if new_time and len(new_time) == 5:  # HH:MM
                new_time += ":00"
            
            existing_dt = datetime.strptime(
                f"{existing['from_date']} {existing_time}",
                "%Y-%m-%d %H:%M:%S"
            )
            new_dt = datetime.strptime(
                f"{from_date} {new_time}",
                "%Y-%m-%d %H:%M:%S"
            )
            
            if new_dt < existing_dt:
                # New boundary is earlier - update it
                existing['from_date'] = from_date
                existing['from_time'] = from_time
            
            # Append reason if not already present (allow empty strings)
            if reason is not None and reason not in existing.get('reasons', []):
                existing.setdefault('reasons', []).append(reason)
            
            existing['updated_at'] = datetime.now().isoformat()
        else:
            # New stale pair
            stale_data[key] = {
                'from_date': from_date,
                'from_time': from_time,
                'updated_at': datetime.now().isoformat(),
                'reasons': [reason] if reason is not None else []
            }
        
        self.settings.set('repair_mode_stale_pairs', stale_data)
    
    def clear_pair(self, user_id: int, site_id: int) -> None:
        """Clear stale marker for a specific pair (after rebuild)."""
        key = f"{user_id}:{site_id}"
        stale_data = self.settings.get('repair_mode_stale_pairs', {})
        
        if key in stale_data:
            del stale_data[key]
            self.settings.set('repair_mode_stale_pairs', stale_data)
    
    def clear_all(self) -> None:
        """Clear all stale pairs."""
        self.settings.set('repair_mode_stale_pairs', {})
    
    def get_stale_count(self) -> int:
        """Get count of stale pairs."""
        stale_data = self.settings.get('repair_mode_stale_pairs', {})
        return len(stale_data)
