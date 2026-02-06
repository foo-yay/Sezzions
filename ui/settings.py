"""
Application settings and preferences

Stores user preferences like theme selection in a JSON file.
"""
import json
import os
from typing import Any, Dict


class Settings:
    """Manage application settings"""
    
    def __init__(self, settings_file: str = "settings.json"):
        self.settings_file = settings_file
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from file"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load settings: {e}")
                return self._default_settings()
        return self._default_settings()
    
    def _default_settings(self) -> Dict[str, Any]:
        """Get default settings"""
        return {
            'theme': 'Light',
            'window_width': 1400,
            'window_height': 900,
            'last_tab': 0,
            'automatic_backup': {
                'enabled': False,
                'directory': '',
                'frequency_hours': 24,
                'last_backup_time': None,
                # Notification settings (Issue #35)
                'notify_on_failure': True,
                'notify_when_overdue': True,
                'overdue_threshold_days': 1
            },
            # Repair Mode settings (Issue #55)
            'repair_mode_enabled': False,
            'repair_mode_stale_pairs': {}
        }

    
    def save(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force OS to write to disk
        except Exception as e:
            print(f"Warning: Could not save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set setting value and save"""
        self.settings[key] = value
        self.save()
    
    def get_theme(self) -> str:
        """Get current theme name"""
        return self.get('theme', 'Light')
    
    def set_theme(self, theme_name: str):
        """Set theme"""
        self.set('theme', theme_name)
    
    def get_automatic_backup_config(self) -> Dict[str, Any]:
        """Get automatic backup configuration"""
        default_config = self._default_settings()['automatic_backup']
        stored_config = self.get('automatic_backup', {})
        # Merge stored config with defaults to ensure new keys have default values
        merged = default_config.copy()
        merged.update(stored_config)
        return merged
    
    def set_automatic_backup_config(self, config: Dict[str, Any]):
        """Set automatic backup configuration"""
        self.set('automatic_backup', config)
