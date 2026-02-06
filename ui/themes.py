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
        theme_qss_path = Path(__file__).resolve().parents[1] / "resources" / "theme.qss"
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
        try:
            qss_template = theme_qss_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Fallback: keep the app usable even if the template is missing.
            return "QMainWindow { background: %s; } QWidget { color: %s; font-size: 12px; }" % (bg, text)

        return Template(qss_template).safe_substitute(
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
    'bg': '#111111',           # --color-background
    'surface': '#19191b',      # --gray-2
    'surface2': '#222325',     # --gray-3
    'border': '#303136',       # --gray-5
    'input_bg': '#222325',     # --gray-3
    'text': '#eeeef0',         # --gray-12
    'text_muted': '#b2b3bd',   # --gray-11
    'accent': '#3d63dd',       # --blue-9
    'accent_hover': '#3f5cb0', # --blue-10
    'selection': '#243974',    # --blue-5
    'focus': '#93b4ff',        # --blue-11
    'scrollbar': '#5f606a',    # --gray-8
})


# Custom theme (example of adding more themes)
CUSTOM_THEME = Theme("Custom", {
    'bg': '#FDFDFE',
    'surface': '#EFF0F3',
    'surface2': '#EDF2FE',
    'border': '#BDD1FF',
    'input_bg': '#ffffff',
    'text': '#1E1F24',
    'text_muted': '#B9BBC6',
    'accent': '#395BC7',
    'accent_hover': '#87A5EF',
    'selection': '#395BC7',
    'focus': '#90caf9',
    'scrollbar': '#90a4ae',
})


# Blue theme (example of adding more themes)
BLUE_THEME = Theme("Blue", {
    'bg': '#ffffff',            # --color-background
    'surface': '#f7f9ff',       # --blue-2
    'surface2': '#edf2fe',      # --blue-3
    'border': '#dfeaff',        # --blue-4
    'input_bg': '#fdfdfe',      # --blue-1
    'text': '#1e1f24',          # --gray-12
    'text_muted': '#62636c',    # --gray-11
    'accent': '#3d63dd',        # --blue-9
    'accent_hover': '#3657c3',  # --blue-10
    'selection': '#d0dfff',     # --blue-5
    'focus': '#a6bff9',         # --blue-7
    'scrollbar': '#b9bbc6',     # --gray-8
})


# Theme registry - easy to add new themes here
THEMES = {
    'Light': LIGHT_THEME,
    'Dark': DARK_THEME,
    'Blue': BLUE_THEME,
    'Custom': CUSTOM_THEME,
}


def get_theme(name: str) -> Theme:
    """Get theme by name, fallback to Light if not found"""
    return THEMES.get(name, LIGHT_THEME)


def get_theme_names():
    """Get list of available theme names"""
    return list(THEMES.keys())
