"""
Test Issue #40: Receipt-date-only redemption edit should not trigger balance warnings

Scenario:
- User has a redemption pending receipt (no receipt_date set)
- User wants to update ONLY the receipt_date (metadata change)
- This should NOT trigger FIFO rebuild or session balance checks
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from app_facade import AppFacade
from repositories.database import DatabaseManager


@pytest.fixture
def app_facade(tmp_path):
    """Create test facade with empty database"""
    db_path = tmp_path / "test.db"
    facade = AppFacade(str(db_path))
    yield facade
    facade.db.close()


def test_receipt_date_only_update_no_balance_check(app_facade):
    """
    Happy path: Updating only receipt_date should skip balance validation
    even when purchases exist after redemption date.
    """
    # Setup user/site
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)
    
    # Create purchase BEFORE redemption date
    purchase_date = date.today() - timedelta(days=10)
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=purchase_date,
        sc_received=Decimal("100.00"),
    )
    
    # Create redemption
    redemption_date = date.today() - timedelta(days=5)
    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=redemption_date,
        apply_fifo=True,
        receipt_date=None,  # Not received yet
    )
    
    # Create ANOTHER purchase AFTER redemption date (this would cause balance warnings)
    later_purchase_date = date.today() - timedelta(days=2)
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("200.00"),
        purchase_date=later_purchase_date,
        sc_received=Decimal("200.00"),
    )
    
    # ACT: Update ONLY the receipt_date (metadata change)
    # This should NOT trigger balance validation
    updated_redemption = app_facade.update_redemption(
        redemption.id,
        receipt_date=date.today(),
    )
    
    # ASSERT: Update succeeded without errors
    assert updated_redemption.receipt_date == date.today()
    assert updated_redemption.amount == Decimal("50.00")  # Amount unchanged


def test_receipt_date_update_with_later_purchases(app_facade):
    """
    Edge case: Verify that receipt_date updates work even with complex
    purchase/redemption timelines.
    """
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)
    
    # Create multiple purchases at different times
    for i, days_ago in enumerate([20, 15, 10, 5]):
        app_facade.create_purchase(
            user_id=user.id,
            site_id=site.id,
            amount=Decimal("100.00"),
            purchase_date=date.today() - timedelta(days=days_ago),
            sc_received=Decimal("100.00"),
        )
    
    # Create redemption in the middle of the timeline
    redemption_date = date.today() - timedelta(days=12)
    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("150.00"),
        redemption_date=redemption_date,
        apply_fifo=True,
        receipt_date=None,
    )
    
    # ACT: Update receipt_date (should not fail even with later purchases)
    updated_redemption = app_facade.update_redemption(
        redemption.id,
        receipt_date=date.today(),
    )
    
    # ASSERT: Update succeeded
    assert updated_redemption.receipt_date == date.today()


def test_accounting_field_update_still_validates(app_facade):
    """
    Verify that updating accounting fields (amount) still triggers proper
    validation and rebuilds.
    """
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)
    
    purchase_date = date.today() - timedelta(days=10)
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=purchase_date,
        sc_received=Decimal("100.00"),
    )
    
    redemption_date = date.today() - timedelta(days=5)
    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=redemption_date,
        apply_fifo=True,
    )
    
    # ACT: Update accounting field (amount) - should use reprocess path
    updated_redemption = app_facade.update_redemption_reprocess(
        redemption.id,
        amount=Decimal("75.00"),
    )
    
    # ASSERT: Amount updated
    assert updated_redemption.amount == Decimal("75.00")


def test_accounting_reprocess_update_is_audited_and_undoable(app_facade):
    """Accounting reprocess edits must hit audit/undo so values can be restored."""
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)

    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("1000.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("1000.00"),
    )

    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("500.00"),
        redemption_date=date.today() - timedelta(days=5),
        apply_fifo=True,
    )

    # Isolate the reprocess edit as the only undoable operation.
    app_facade.undo_redo_service.clear_stacks()

    updated_redemption = app_facade.update_redemption_reprocess(
        redemption.id,
        amount=Decimal("250.00"),
    )

    assert updated_redemption.amount == Decimal("250.00")
    assert app_facade.undo_redo_service.can_undo()

    audit_row = app_facade.db.fetch_one(
        """
        SELECT old_data, new_data
        FROM audit_log
        WHERE action = 'UPDATE' AND table_name = 'redemptions' AND record_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (redemption.id,),
    )

    assert audit_row is not None
    assert '"amount": "500.00"' in audit_row["old_data"] or '"amount": "500"' in audit_row["old_data"]
    assert '"amount": "250.00"' in audit_row["new_data"] or '"amount": "250"' in audit_row["new_data"]

    app_facade.undo_redo_service.undo()

    reverted = app_facade.get_redemption(redemption.id)
    assert reverted is not None
    assert reverted.amount == Decimal("500.00")


def test_processed_flag_only_update_no_rebuild(app_facade):
    """
    Verify that updating only the 'processed' flag (another metadata field)
    does not trigger FIFO rebuild.
    """
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)
    
    purchase_date = date.today() - timedelta(days=10)
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=purchase_date,
        sc_received=Decimal("100.00"),
    )
    
    redemption_date = date.today() - timedelta(days=5)
    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=redemption_date,
        apply_fifo=True,
        processed=False,
    )
    
    # Create later purchase that would cause issues if rebuild triggered
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("200.00"),
        purchase_date=date.today() - timedelta(days=2),
        sc_received=Decimal("200.00"),
    )
    
    # ACT: Update only processed flag
    updated_redemption = app_facade.update_redemption(
        redemption.id,
        processed=True,
    )
    
    # ASSERT: Update succeeded
    assert updated_redemption.processed is True


def test_notes_only_update_no_rebuild(app_facade):
    """
    Verify that updating only notes (metadata) doesn't trigger rebuild.
    """
    user = app_facade.create_user("TestUser")
    site = app_facade.create_site("TestSite", sc_rate=1.0)
    
    purchase_date = date.today() - timedelta(days=10)
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=purchase_date,
        sc_received=Decimal("100.00"),
    )
    
    redemption_date = date.today() - timedelta(days=5)
    redemption = app_facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=redemption_date,
        apply_fifo=True,
        notes="",
    )
    
    # Create later purchase
    app_facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("200.00"),
        purchase_date=date.today() - timedelta(days=2),
        sc_received=Decimal("200.00"),
    )
    
    # ACT: Update only notes
    updated_redemption = app_facade.update_redemption(
        redemption.id,
        notes="Updated notes",
    )
    
    # ASSERT: Update succeeded
    assert updated_redemption.notes == "Updated notes"
