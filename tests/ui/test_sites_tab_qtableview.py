"""
Tests for Sites tab QTableView migration
"""
import pytest
import sys
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from ui.tabs.sites_tab import SitesTab, SitesTableModel
from ui.base_table_model import ColumnDefinition
from models.site import Site


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_facade():
    """Mock facade with test sites"""
    facade = Mock()
    facade.get_all_sites.return_value = [
        Site(id=1, name="Site A", url="https://a.com", sc_rate=1.0, is_active=True, notes="Test note"),
        Site(id=2, name="Site B", url="https://b.com", sc_rate=2.0, is_active=False, notes=None),
        Site(id=3, name="Site C", url=None, sc_rate=0.5, is_active=True, notes="Another note"),
    ]
    return facade


def test_sites_table_model():
    """Test SitesTableModel structure"""
    model = SitesTableModel()
    
    # Verify column count
    assert model.columnCount() == 5
    
    # Verify column definitions
    assert model.columns[0].label == "Name"
    assert model.columns[1].label == "URL"
    assert model.columns[2].label == "SC Rate"
    assert model.columns[3].label == "Status"
    assert model.columns[4].label == "Notes"


def test_sites_tab_instantiation(qapp, mock_facade):
    """Test Sites tab can be instantiated with QTableView"""
    tab = SitesTab(mock_facade)
    
    # Verify model and proxy are set up
    assert tab.model is not None
    assert tab.proxy is not None
    assert tab.table.model() == tab.proxy
    
    # Verify data was loaded
    assert mock_facade.get_all_sites.called
    assert tab.proxy.rowCount() == 3
    
    # Clean up
    tab.deleteLater()


def test_sites_tab_model_data_access(qapp, mock_facade):
    """Test model correctly stores and retrieves Site objects"""
    tab = SitesTab(mock_facade)
    
    # Get first row's site object
    source_index = tab.model.index(0, 0)
    site = tab.model.get_row_object(source_index.row())
    
    assert site is not None
    assert site.id == 1
    assert site.name == "Site A"
    
    # Clean up
    tab.deleteLater()


def test_sites_tab_spreadsheet_ux(qapp, mock_facade):
    """Test spreadsheet UX (copy/stats) works with QTableView"""
    from ui.spreadsheet_ux import SpreadsheetUXController
    from PySide6.QtCore import QItemSelectionModel
    
    tab = SitesTab(mock_facade)
    
    # Select a cell
    selection_model = tab.table.selectionModel()
    first_index = tab.proxy.index(0, 0)
    selection_model.select(first_index, QItemSelectionModel.Select)
    
    # Extract selection grid
    grid = SpreadsheetUXController.extract_selection_grid(tab.table)
    
    # Should extract one cell
    assert len(grid) == 1
    assert len(grid[0]) == 1
    # Check that it's one of our test sites (sorting might change order)
    assert grid[0][0] in ["Site A", "Site B", "Site C"]
    
    # Clean up
    tab.deleteLater()


def test_sites_tab_filtering(qapp, mock_facade):
    """Test search filtering works"""
    tab = SitesTab(mock_facade)
    
    # Initial count
    assert tab.proxy.rowCount() == 3
    
    # Search for "Site A"
    tab.search_edit.setText("Site A")
    
    # Should filter to 1 row
    assert tab.proxy.rowCount() == 1
    
    # Clean up
    tab.deleteLater()
