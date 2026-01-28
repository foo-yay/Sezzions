#!/usr/bin/env python3
"""
Phase 4 Manual Testing Script
Run this to verify basic component integration before UI testing.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app_facade import AppFacade

def test_recalculation_service():
    """Test that RecalculationService is accessible and has required methods."""
    print("=" * 60)
    print("TEST 1: RecalculationService Integration")
    print("=" * 60)
    
    facade = AppFacade()
    recalc_service = facade.recalculation_service
    
    assert recalc_service is not None, "RecalculationService not accessible"
    print("✅ RecalculationService accessible via facade")
    
    # Check required methods exist
    assert hasattr(recalc_service, 'rebuild_fifo_all'), "Missing rebuild_fifo_all method"
    assert hasattr(recalc_service, 'rebuild_fifo_for_pair'), "Missing rebuild_fifo_for_pair method"
    assert hasattr(recalc_service, 'rebuild_after_import'), "Missing rebuild_after_import method"
    assert hasattr(recalc_service, 'get_stats'), "Missing get_stats method"
    print("✅ All required methods present")
    
    # Test get_stats
    stats = recalc_service.get_stats()
    print(f"✅ Statistics retrieved: {stats['pairs']} pairs, {stats['purchases']} purchases")
    
    print()

def test_import_result_dto():
    """Test that ImportResult has affected_user_ids and affected_site_ids fields."""
    print("=" * 60)
    print("TEST 2: ImportResult DTO Enhancement")
    print("=" * 60)
    
    from services.tools.dtos import ImportResult
    
    # Create ImportResult with new fields
    result = ImportResult(
        success=True,
        records_added=5,
        records_updated=0,
        records_skipped=0,
        entity_type="purchases",
        affected_user_ids=[1, 2, 3],
        affected_site_ids=[1]
    )
    
    assert hasattr(result, 'affected_user_ids'), "Missing affected_user_ids field"
    assert hasattr(result, 'affected_site_ids'), "Missing affected_site_ids field"
    print("✅ ImportResult has affected_user_ids field")
    print("✅ ImportResult has affected_site_ids field")
    
    assert result.affected_user_ids == [1, 2, 3], "affected_user_ids not set correctly"
    assert result.affected_site_ids == [1], "affected_site_ids not set correctly"
    print(f"✅ Affected IDs tracking works: {len(result.affected_user_ids)} users, {len(result.affected_site_ids)} sites")
    
    print()

def test_worker_classes():
    """Test that worker classes are importable and have required signals."""
    print("=" * 60)
    print("TEST 3: Background Worker Classes")
    print("=" * 60)
    
    from ui.tools_workers import RecalculationWorker, WorkerSignals
    
    print("✅ RecalculationWorker importable")
    print("✅ WorkerSignals importable")
    
    # Check signals exist
    signals = WorkerSignals()
    assert hasattr(signals, 'progress'), "Missing progress signal"
    assert hasattr(signals, 'finished'), "Missing finished signal"
    assert hasattr(signals, 'error'), "Missing error signal"
    assert hasattr(signals, 'cancelled'), "Missing cancelled signal"
    print("✅ All required signals present (progress, finished, error, cancelled)")
    
    print()

def test_dialog_classes():
    """Test that dialog classes are importable."""
    print("=" * 60)
    print("TEST 4: Dialog Classes")
    print("=" * 60)
    
    from ui.tools_dialogs import (
        ProgressDialog,
        RecalculationProgressDialog,
        RecalculationResultDialog,
        PostImportPromptDialog
    )
    
    print("✅ ProgressDialog importable")
    print("✅ RecalculationProgressDialog importable")
    print("✅ RecalculationResultDialog importable")
    print("✅ PostImportPromptDialog importable")
    
    print()

def test_tools_tab_methods():
    """Test that ToolsTab has required methods."""
    print("=" * 60)
    print("TEST 5: Tools Tab Integration")
    print("=" * 60)
    
    from ui.tabs.tools_tab import ToolsTab
    
    print("✅ ToolsTab importable")
    
    # Check required methods exist
    assert hasattr(ToolsTab, 'prompt_recalculate_after_import'), "Missing prompt_recalculate_after_import method"
    assert hasattr(ToolsTab, '_trigger_post_import_recalculation'), "Missing _trigger_post_import_recalculation method"
    assert hasattr(ToolsTab, '_on_recalculate_all'), "Missing _on_recalculate_all method"
    assert hasattr(ToolsTab, '_on_recalculate_scoped'), "Missing _on_recalculate_scoped method"
    print("✅ All required methods present")
    print("  - prompt_recalculate_after_import()")
    print("  - _trigger_post_import_recalculation()")
    print("  - _on_recalculate_all()")
    print("  - _on_recalculate_scoped()")
    
    print()

def test_database_stats():
    """Test database statistics to understand current data."""
    print("=" * 60)
    print("TEST 6: Database Statistics")
    print("=" * 60)
    
    facade = AppFacade()
    
    # Get counts
    users = facade.user_repo.get_all()
    sites = facade.site_repo.get_all()
    purchases = facade.purchase_repo.get_all()
    redemptions = facade.redemption_repo.get_all()
    
    print(f"📊 Current Database State:")
    print(f"   Users: {len(users)}")
    print(f"   Sites: {len(sites)}")
    print(f"   Purchases: {len(purchases)}")
    print(f"   Redemptions: {len(redemptions)}")
    
    if len(users) > 0:
        print(f"\n📋 Sample Users:")
        for user in users[:5]:
            print(f"   - ID {user.id}: {user.name}")
    
    if len(sites) > 0:
        print(f"\n📋 Sample Sites:")
        for site in sites[:5]:
            print(f"   - ID {site.id}: {site.name}")
    
    # Calculate user/site pairs
    pairs = len(users) * len(sites)
    print(f"\n🔗 Potential User/Site Pairs: {pairs}")
    
    if len(purchases) == 0:
        print("\n⚠️  WARNING: No purchases in database. Some tests may not be meaningful.")
    
    print()

def main():
    """Run all backend integration tests."""
    print("\n" + "=" * 60)
    print("PHASE 4 BACKEND INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_recalculation_service()
        test_import_result_dto()
        test_worker_classes()
        test_dialog_classes()
        test_tools_tab_methods()
        test_database_stats()
        
        print("=" * 60)
        print("✅ ALL BACKEND INTEGRATION TESTS PASSED")
        print("=" * 60)
        print()
        print("Next Steps:")
        print("1. Open the running application")
        print("2. Navigate to the Tools tab (🔧 Tools)")
        print("3. Follow PHASE4_TESTING_GUIDE.md for UI testing")
        print()
        
    except Exception as e:
        print("=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
