"""
Setup tab - Container for setup/configuration sub-tabs
"""
from PySide6 import QtWidgets
from app_facade import AppFacade
from ui.tabs.users_tab import UsersTab
from ui.tabs.sites_tab import SitesTab
from ui.tabs.cards_tab import CardsTab
from ui.tabs.redemption_methods_tab import RedemptionMethodsTab
from ui.tabs.redemption_method_types_tab import RedemptionMethodTypesTab
from ui.tabs.game_types_tab import GameTypesTab
from ui.tabs.games_tab import GamesTab


class SetupTab(QtWidgets.QWidget):
    """Container tab for all setup/configuration tabs"""
    
    def __init__(self, facade: AppFacade):
        super().__init__()
        self.facade = facade
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Setup")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_spacer = QtWidgets.QWidget()
        header_spacer.setFixedSize(300, 32)
        header_layout.addWidget(header_spacer)
        layout.addLayout(header_layout)

        layout.addSpacing(2)

        info = QtWidgets.QLabel("Manage users, sites, cards, redemption methods, game types, and games.")
        info.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info)
        
        # Create sub-tab widget
        self.sub_tabs = QtWidgets.QTabWidget()
        self.sub_tabs.setObjectName("SetupSubTabs")
        self.sub_tabs.setUsesScrollButtons(False)
        if self.sub_tabs.tabBar():
            self.sub_tabs.tabBar().setExpanding(False)
        
        # Add setup tabs
        self.users_tab = UsersTab(facade)
        self.sites_tab = SitesTab(facade)
        self.cards_tab = CardsTab(facade)
        self.redemption_methods_tab = RedemptionMethodsTab(facade)
        self.redemption_method_types_tab = RedemptionMethodTypesTab(facade)
        self.game_types_tab = GameTypesTab(facade)
        self.games_tab = GamesTab(facade)
        
        self.sub_tabs.addTab(self.users_tab, "👤 Users")
        self.sub_tabs.addTab(self.sites_tab, "🏢 Sites")
        self.sub_tabs.addTab(self.cards_tab, "💳 Cards")
        self.sub_tabs.addTab(self.redemption_method_types_tab, "🏷️ Method Types")
        self.sub_tabs.addTab(self.redemption_methods_tab, "💵 Redemption Methods")
        self.sub_tabs.addTab(self.game_types_tab, "🎯 Game Types")
        self.sub_tabs.addTab(self.games_tab, "🎮 Games")
        
        card = QtWidgets.QFrame()
        card.setObjectName("SetupCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.addWidget(self.sub_tabs)

        layout.addWidget(card, 1)
    
    def refresh_all(self):
        """Refresh all setup tabs"""
        self.users_tab.refresh_data()
        self.sites_tab.refresh_data()
        self.cards_tab.refresh_data()
        self.redemption_method_types_tab.refresh_data()
        self.redemption_methods_tab.refresh_data()
        self.game_types_tab.refresh_data()
        self.games_tab.refresh_data()
