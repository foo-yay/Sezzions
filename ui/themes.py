"""
Theme system for Sezzions application

Provides modular, expandable theme support with easy theme switching.
"""
from typing import Dict
from pathlib import Path
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
        return f"""
            QMainWindow {{ background: {bg}; }}
            QWidget {{ color: {text}; font-size: 12px; }}
            QDialog, QMessageBox {{ background: {surface}; }}
            QDialog QScrollArea {{
                background: {surface};
                border: none;
            }}
            QDialog QScrollArea QWidget#qt_scrollarea_viewport {{
                background: {surface};
            }}
            
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                background: {input_bg};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 26px;
            }}
            QLineEdit[invalid="true"], QTextEdit[invalid="true"], QPlainTextEdit[invalid="true"], QComboBox[invalid="true"] {{
                border: 1px solid #c0392b;
            }}
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {focus};
            }}
            QComboBox {{
                padding-right: 30px;
            }}
            QComboBox::editable {{
                background: {input_bg};
                color: {text};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid {border};
                background: {surface2};
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }}
            QComboBox::down-arrow {{
                image: url("{icon_path}");
                width: 12px;
                height: 12px;
            }}
            QAbstractItemView,
            QListView,
            QComboBox QAbstractItemView {{
                background: {input_bg};
                color: {text};
                selection-background-color: {selection};
                selection-color: {text};
            }}
            QPlainTextEdit#NotesField {{
                min-height: 78px;
            }}
            QLabel#InfoField {{
                background: {input_bg};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 26px;
            }}
            QLabel#InfoField[status="positive"] {{ color: #2e7d32; }}
            QLabel#InfoField[status="negative"] {{ color: #c0392b; }}
            QLabel#InfoField[status="neutral"] {{ color: {text_muted}; }}
            QLabel#HelperText {{ color: {text_muted}; font-size: 11px; }}
            QLabel#HelperText[status="match"] {{ color: #2e7d32; }}
            QLabel#HelperText[status="warning"] {{ color: #f57c00; }}
            QLabel#HelperText[status="error"] {{ color: #c0392b; }}
            QLabel#TabTip {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 6px 12px;
                color: {accent_hover};
                font-weight: 500;
            }}
            QRadioButton[invalid="true"] {{ color: #c0392b; }}
            
            QPushButton {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 6px 14px;
                min-height: 26px;
            }}
            QPushButton:hover {{ background: {surface2}; }}
            QPushButton:disabled {{
                background: {surface};
                border: 1px solid {border};
                color: {text_muted};
            }}
            QPushButton:hover:disabled {{ background: {surface}; }}
            QPushButton#PrimaryButton {{
                background: {accent};
                border: 1px solid {accent_hover};
                color: white;
            }}
            QPushButton#PrimaryButton:hover {{ background: {accent_hover}; }}
            QPushButton#PrimaryButton:disabled {{
                background: {border};
                border: 1px solid {border};
                color: {text_muted};
            }}
            QPushButton#SuccessButton {{
                background: #28a745;
                border: 1px solid #218838;
                color: white;
            }}
            QPushButton#SuccessButton:hover {{ background: #218838; }}
            QPushButton#SuccessButton:disabled {{
                background: {border};
                border: 1px solid {border};
                color: {text_muted};
            }}
            QPushButton#DangerButton {{
                background: #dc3545;
                border: 1px solid #c82333;
                color: white;
            }}
            QPushButton#DangerButton:hover {{ background: #c82333; }}
            QPushButton#DangerButton:disabled {{
                background: {border};
                border: 1px solid {border};
                color: {text_muted};
            }}
            QPushButton#MiniButton {{
                padding: 4px 10px;
                min-height: 20px;
            }}
            QPushButton#NotificationBell {{
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                min-height: 0;
            }}
            QPushButton#NotificationBell:hover {{
                background: transparent;
                border: none;
            }}
            QPushButton#NotificationBell:pressed {{
                background: transparent;
                border: none;
            }}
            QToolButton#InfoButton {{
                background: {surface2};
                border: 1px solid {border};
                border-radius: 9px;
                min-width: 18px;
                min-height: 18px;
                padding: 0;
                font-weight: 600;
            }}
            QToolButton#InfoButton:hover {{ background: {border}; }}
            QCheckBox, QRadioButton {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {focus};
                border-radius: 4px;
                background: {input_bg};
            }}
            QCheckBox::indicator:checked {{
                background: {accent};
                border: 1px solid {accent_hover};
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {focus};
                border-radius: 8px;
                background: {input_bg};
            }}
            QRadioButton::indicator:checked {{
                background: {accent};
                border: 1px solid {accent_hover};
            }}

            QTableWidget {{
                background: {surface};
                gridline-color: {border};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QTreeWidget, QTreeView {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QTreeWidget::item, QTreeView::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {border};
            }}
            QTreeWidget::item:selected, QTreeView::item:selected {{
                background: {selection};
            }}
            QHeaderView::section {{
                background: {surface2};
                border: 1px solid {border};
                padding: 6px;
                font-weight: 600;
            }}
            QTableWidget::item:selected {{
                background: {selection};
            }}
            QScrollBar:vertical {{
                background: {surface};
                width: 12px;
                margin: 2px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {scrollbar};
                min-height: 30px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                background: none;
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {surface};
                height: 12px;
                margin: 2px;
                border-radius: 6px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scrollbar};
                min-width: 30px;
                border-radius: 6px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                background: none;
                width: 0;
            }}

            QTabWidget::pane {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar#MainTabs {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QFrame#MainContentFrame {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QTabBar#MainTabs::tab {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 6px 10px;
                margin: 4px 4px 8px 4px;
                color: {text_muted};
                min-height: 24px;
                min-width: 110px;
                max-width: 140px;
                font-weight: 600;
            }}
            QTabBar#MainTabs::tab:selected {{
                background: {accent};
                border: 1px solid {accent_hover};
                color: white;
            }}
            QTabBar#MainTabs::tab:hover {{
                background: {surface2};
                color: {text};
            }}

            QFrame#SetupCard {{
                background: transparent;
                border: none;
            }}
            QTabWidget#SetupSubTabs::pane {{
                border: 1px solid {border};
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                border-top-left-radius: 0px;
                border-top-right-radius: 8px;
                background: {surface2};
                top: -1px;
            }}
            QTabWidget#SetupSubTabs QTabBar::tab:first {{
                margin-left: 0px;
            }}
            QTabWidget#SetupSubTabs QTabBar::tab {{
                background: {surface};
                border: 1px solid {border};
                border-bottom: 1px solid {border};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 6px 10px;
                margin-right: 4px;
                margin-bottom: -1px;
                color: {text_muted};
                font-weight: 600;
            }}
            QTabWidget#SetupSubTabs QTabBar::tab:selected {{
                background: {surface2};
                border-bottom: 1px solid {surface2};
                border-left: 1px solid {border};
                border-right: 1px solid {border};
                color: {text};
                margin-right: 4px;
            }}

            QMenuBar {{
                background: {surface};
                color: {text};
            }}
            QMenuBar::item:selected {{
                background: {surface2};
            }}
            QMenu {{
                background: {input_bg};
                color: {text};
                border: 1px solid {border};
            }}
            QMenu::item:selected {{
                background: {selection};
            }}
            QStatusBar {{
                background: {surface2};
                color: {text_muted};
            }}
            QLabel {{
                color: {text};
            }}
            
            /* Dialog Section Styles */
            QWidget#SectionBackground {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 12px;
            }}
            QWidget#BalanceCheck {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 8px;
            }}
            QWidget#RemainingBasis {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 8px;
            }}
            QLabel#PageTitle {{
                font-size: 18px;
                font-weight: bold;
                color: {text};
                padding-bottom: 4px;
            }}
            QLabel#SectionHeader {{
                font-size: 13px;
                font-weight: 600;
                color: {text};
                padding-top: 4px;
                padding-bottom: 2px;
            }}
            QLabel#FieldLabel {{
                font-weight: 600;
                color: {text};
            }}
            QLabel#ValueChip {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 12px;
                color: {text};
                font-size: 12px;
            }}
            QLabel#ValueChip[status="positive"] {{ color: #2e7d32; }}
            QLabel#ValueChip[status="negative"] {{ color: #c0392b; }}
            QLabel#ValueChip[status="neutral"] {{ color: {text_muted}; }}
            QLabel#CashbackLabel {{
                color: {accent};
                font-size: 11px;
                font-weight: 500;
            }}
        """


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
