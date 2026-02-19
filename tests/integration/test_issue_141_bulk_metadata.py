"""
Tests for Issue #141: Bulk Mark Received / Mark Processed

Tests confirm:
- bulk_update_redemption_metadata() sets receipt_date for multiple rows
- bulk_update_redemption_metadata() sets processed=True for multiple rows
- No FIFO rebuild / recalculation occurs (invariant)
- Pending-receipt notifications are dismissed after bulk mark-received
- Clear path: bulk update with receipt_date=None clears the date
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from app_facade import AppFacade
from repositories.database import DatabaseManager


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    facade = AppFacade(str(db_path))
    yield facade
    facade.db.close()


@pytest.fixture
def two_redemptions(app):
    """Create two redemptions with no receipt_date and processed=False."""
    user = app.create_user("Alice")
    site = app.create_site("SiteA", sc_rate=1.0)
    app.create_purchase(
        user_id=user.id, site_id=site.id,
        amount=Decimal("500.00"),
        purchase_date=date.today() - timedelta(days=30),
        sc_received=Decimal("500.00"),
    )
    r1 = app.create_redemption(
        user_id=user.id, site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=20),
        apply_fifo=True,
        receipt_date=None,
        processed=False,
        more_remaining=True,
    )
    r2 = app.create_redemption(
        user_id=user.id, site_id=site.id,
        amount=Decimal("30.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=None,
        processed=False,
        more_remaining=True,
    )
    return r1, r2


# ---------------------------------------------------------------------------
# Happy path: bulk set receipt_date
# ---------------------------------------------------------------------------

def test_bulk_mark_received_sets_receipt_date(app, two_redemptions):
    r1, r2 = two_redemptions
    target_date = date.today()

    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=target_date)

    updated_r1 = app.get_redemption(r1.id)
    updated_r2 = app.get_redemption(r2.id)
    assert updated_r1.receipt_date == target_date
    assert updated_r2.receipt_date == target_date


def test_bulk_mark_received_does_not_change_other_fields(app, two_redemptions):
    r1, r2 = two_redemptions
    app.bulk_update_redemption_metadata([r1.id], receipt_date=date.today())
    updated = app.get_redemption(r1.id)
    assert updated.amount == r1.amount
    assert updated.processed is False  # untouched


# ---------------------------------------------------------------------------
# Happy path: bulk set processed
# ---------------------------------------------------------------------------

def test_bulk_mark_processed_sets_flag(app, two_redemptions):
    r1, r2 = two_redemptions
    app.bulk_update_redemption_metadata([r1.id, r2.id], processed=True)

    updated_r1 = app.get_redemption(r1.id)
    updated_r2 = app.get_redemption(r2.id)
    assert updated_r1.processed is True
    assert updated_r2.processed is True


def test_bulk_mark_processed_does_not_change_receipt_date(app, two_redemptions):
    r1, _ = two_redemptions
    app.bulk_update_redemption_metadata([r1.id], processed=True)
    updated = app.get_redemption(r1.id)
    assert updated.receipt_date is None  # untouched


# ---------------------------------------------------------------------------
# Edge: clear receipt_date (set to None)
# ---------------------------------------------------------------------------

def test_bulk_clear_receipt_date(app, two_redemptions):
    r1, r2 = two_redemptions
    # First set a date, then clear it
    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=date.today())
    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=None)
    updated_r1 = app.get_redemption(r1.id)
    updated_r2 = app.get_redemption(r2.id)
    assert updated_r1.receipt_date is None
    assert updated_r2.receipt_date is None


# ---------------------------------------------------------------------------
# Edge: empty list is a no-op
# ---------------------------------------------------------------------------

def test_bulk_update_empty_list(app):
    # Should not raise
    app.bulk_update_redemption_metadata([], receipt_date=date.today())
    app.bulk_update_redemption_metadata([], processed=True)


# ---------------------------------------------------------------------------
# Invariant: no FIFO rebuild triggered
# ---------------------------------------------------------------------------

def test_bulk_mark_received_does_not_trigger_fifo_rebuild(app, two_redemptions):
    r1, r2 = two_redemptions
    with patch.object(app, "_rebuild_or_mark_stale") as mock_rebuild, \
         patch.object(app.game_session_event_link_service, "rebuild_links_for_pair") as mock_links:
        app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=date.today())
        mock_rebuild.assert_not_called()
        mock_links.assert_not_called()


def test_bulk_mark_processed_does_not_trigger_fifo_rebuild(app, two_redemptions):
    r1, r2 = two_redemptions
    with patch.object(app, "_rebuild_or_mark_stale") as mock_rebuild, \
         patch.object(app.game_session_event_link_service, "rebuild_links_for_pair") as mock_links:
        app.bulk_update_redemption_metadata([r1.id, r2.id], processed=True)
        mock_rebuild.assert_not_called()
        mock_links.assert_not_called()


# ---------------------------------------------------------------------------
# Notification: pending-receipt notifications dismissed after mark-received
# ---------------------------------------------------------------------------

def test_bulk_mark_received_dismisses_notifications(app, two_redemptions):
    r1, r2 = two_redemptions
    dismissed = []

    def fake_on_received(rid):
        dismissed.append(rid)

    app.notification_rules_service.on_redemption_received = fake_on_received

    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=date.today())

    assert r1.id in dismissed
    assert r2.id in dismissed


def test_bulk_mark_processed_does_not_dismiss_notifications(app, two_redemptions):
    r1, _ = two_redemptions
    dismissed = []

    def fake_on_received(rid):
        dismissed.append(rid)

    app.notification_rules_service.on_redemption_received = fake_on_received

    app.bulk_update_redemption_metadata([r1.id], processed=True)

    # processed flag update should NOT trigger notification dismissal
    assert len(dismissed) == 0


def test_bulk_clear_receipt_date_does_not_dismiss_notifications(app, two_redemptions):
    """Clearing receipt_date (mark NOT received) should not dismiss notifications."""
    r1, _ = two_redemptions
    dismissed = []

    def fake_on_received(rid):
        dismissed.append(rid)

    app.notification_rules_service.on_redemption_received = fake_on_received

    app.bulk_update_redemption_metadata([r1.id], receipt_date=None)
    assert len(dismissed) == 0


# ---------------------------------------------------------------------------
# Undo/redo: bulk op pushes one undoable entry; Ctrl+Z reverts all rows
# ---------------------------------------------------------------------------

def test_bulk_mark_received_pushes_undo_entry(app, two_redemptions):
    """Bulk mark-received creates exactly one entry on the undo stack."""
    r1, r2 = two_redemptions
    before = len(app.undo_redo_service._undo_stack)

    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=date.today())

    assert len(app.undo_redo_service._undo_stack) == before + 1
    assert "received" in app.undo_redo_service._undo_stack[-1].description.lower()


def test_bulk_mark_processed_pushes_undo_entry(app, two_redemptions):
    """Bulk mark-processed creates exactly one entry on the undo stack."""
    r1, r2 = two_redemptions
    before = len(app.undo_redo_service._undo_stack)

    app.bulk_update_redemption_metadata([r1.id, r2.id], processed=True)

    assert len(app.undo_redo_service._undo_stack) == before + 1
    assert "processed" in app.undo_redo_service._undo_stack[-1].description.lower()


def test_undo_reverts_bulk_mark_received(app, two_redemptions):
    """Ctrl+Z after bulk mark-received restores receipt_date=None on all rows."""
    r1, r2 = two_redemptions
    target_date = date.today()

    app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=target_date)
    assert app.get_redemption(r1.id).receipt_date == target_date
    assert app.get_redemption(r2.id).receipt_date == target_date

    app.undo_redo_service.undo()

    assert app.get_redemption(r1.id).receipt_date is None
    assert app.get_redemption(r2.id).receipt_date is None


def test_undo_reverts_bulk_mark_processed(app, two_redemptions):
    """Ctrl+Z after bulk mark-processed restores processed=False on all rows."""
    r1, r2 = two_redemptions

    app.bulk_update_redemption_metadata([r1.id, r2.id], processed=True)
    assert app.get_redemption(r1.id).processed is True
    assert app.get_redemption(r2.id).processed is True

    app.undo_redo_service.undo()

    assert app.get_redemption(r1.id).processed is False
    assert app.get_redemption(r2.id).processed is False
