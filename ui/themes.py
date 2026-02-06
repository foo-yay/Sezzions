"""
Theme system for Sezzions application

Provides modular, expandable theme support with easy theme switching.
"""
from typing import Dict
from pathlib import Path
from string import Template
from PySide6 import QtGui


class Theme:
    """Base theme class defining color palette and styles"""
    
    def __init__(self, name: str, colors: Dict[str, str]):
        self.name = name
        self.colors = colors
    
    def get_stylesheet(self) -> str:
        """Generate Qt stylesheet from theme colors"""
        icon_path = (Path(__file__).resolve().parents[1] / "resources" / "chevron-down.svg").as_posix().replace(" ", "\\ ")
        bg = self.colors.get('bg', self.colors.get('background', '#ffffff'))
        surface = self.colors.get('surface', self.colors.get('background', '#f7f9ff'))
        surface2 = self.colors.get('surface2', self.colors.get('header_bg', '#edf2fe'))
        border = self.colors.get('border', '#dfeaff')
        input_bg = self.colors.get('input_bg', '#fdfdfe')
        text = self.colors.get('text', '#1e1f24')
        text_muted = self.colors.get('text_muted', '#62636c')
        accent = self.colors.get('accent', '#3d63dd')
        accent_hover = self.colors.get('accent_hover', '#3657c3')
        selection = self.colors.get('selection', '#d0dfff')
        focus = self.colors.get('focus', '#a6bff9')
        scrollbar = self.colors.get('scrollbar', '#b9bbc6')
        template_path = Path(__file__).resolve().parents[1] / "resources" / "theme.qss"
        template = Template(template_path.read_text(encoding="utf-8"))
        return template.safe_substitute(
            bg=bg,
            surface=surface,
            surface2=surface2,
            border=border,
            input_bg=input_bg,
            text=text,
            text_muted=text_muted,
            accent=accent,
            accent_hover=accent_hover,
            selection=selection,
            focus=focus,
            scrollbar=scrollbar,
            icon_path=icon_path,
        )


# Light theme (default)
LIGHT_THEME = Theme("Light", {
    'bg': '#ffffff',
    'surface': '#f7f9ff',
    'surface2': '#edf2fe',
    'border': '#dfeaff',
    'input_bg': '#fdfdfe',
    'text': '#1e1f24',
    'text_muted': '#62636c',
    'accent': '#3d63dd',
    'accent_hover': '#3657c3',
    'selection': '#d0dfff',
    'focus': '#a6bff9',
    'scrollbar': '#b9bbc6',
})


# Dark theme
DARK_THEME = Theme("Dark", {
    'bg': '#1e1e1e',
    'surface': '#252525',
    'surface2': '#2d2d2d',
    'border': '#3c3c3c',
    'input_bg': '#2b2b2b',
    'text': '#e0e0e0',
    'text_muted': '#b0b0b0',
    'accent': '#4fc3f7',
    'accent_hover': '#38b2e6',
    'selection': '#0d47a1',
    'focus': '#4fc3f7',
    'scrollbar': '#4a4a4a',
})


# Blue theme (example of adding more themes)
BLUE_THEME = Theme("Blue", {
    'bg': '#e3f2fd',
    'surface': '#edf4ff',
    'surface2': '#dbe9ff',
    'border': '#90caf9',
    'input_bg': '#ffffff',
    'text': '#0d47a1',
    'text_muted': '#37517a',
    'accent': '#1976d2',
    'accent_hover': '#1565c0',
    'selection': '#bbdefb',
    'focus': '#90caf9',
    'scrollbar': '#90a4ae',
})


# Theme registry - easy to add new themes here
THEMES = {
    'Light': LIGHT_THEME,
    'Dark': DARK_THEME,
    'Blue': BLUE_THEME,
}


def get_theme(name: str) -> Theme:
    """Get theme by name, fallback to Light if not found"""
    return THEMES.get(name, LIGHT_THEME)


def get_theme_names():
    """Get list of available theme names"""
    return list(THEMES.keys())
