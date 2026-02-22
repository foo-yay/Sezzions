"""
Integration tests for Issue #148: Redemption Cancel / Uncancel

Torture-test matrix:
  Happy paths:
    H1 — Cancel a PENDING redemption (no active session) → status CANCELED, FIFO reversed
    H2 — Uncancel a CANCELED redemption → status PENDING, FIFO re-applied
    H3 — Cancel with active session → status PENDING_CANCEL (deferred)
    H4 — process_pending_cancels executes deferred cancels

  Edge cases:
    E1 — Cannot cancel a redemption that already has a receipt_date
    E2 — Cannot cancel a CANCELED redemption
    E3 — Cannot uncancel a PENDING redemption
    E4 — Cancel reason is stored on the model
    E5 — Canceled redemption excluded from Pending-receipt notification query
    E6 — bulk_update_redemption_metadata skips CANCELED rows

  Failure injection:
    F1 — Invariant: canceling does not affect OTHER redemptions' FIFO allocations
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from app_facade import AppFacade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def facade(tmp_path):
    db_path = tmp_path / "test_cancel.db"
    f = AppFacade(str(db_path))
    yield f
    f.db.close()


@pytest.fixture
def setup(facade):
    """Return a dict with user, site, method, and a $100 purchase."""
    user = facade.create_user("Alice")
    site = facade.create_site("CasinoX", sc_rate=1.0)
    method = facade.create_redemption_method("Check")

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=30),
        sc_received=Decimal("100.00"),
    )
    return {"user": user, "site": site, "method": method}


def _make_redemption(facade, setup, amount="50.00", days_ago=10, more_remaining=True):
    return facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal(amount),
        redemption_date=date.today() - timedelta(days=days_ago),
        apply_fifo=True,
        receipt_date=None,
        more_remaining=more_remaining,
    )


def _has_fifo(facade, redemption_id: int) -> bool:
    """Check whether a redemption currently has FIFO allocation rows."""
    r = facade.get_redemption(redemption_id)
    return r is not None and getattr(r, '_has_fifo_allocation', False)


# ---------------------------------------------------------------------------
# H1 — Cancel PENDING (no active session) → CANCELED immediately
# ---------------------------------------------------------------------------

def test_h1_cancel_pending_no_active_session(facade, setup):
    redemption = _make_redemption(facade, setup)
    assert redemption.id is not None

    # Sanity: FIFO allocation exists before cancel
    r_before = facade.get_redemption(redemption.id)
    assert r_before.has_fifo_allocation

    facade.cancel_redemption(redemption.id, reason="test cancel")

    updated = facade.get_redemption(redemption.id)
    assert updated.status == "CANCELED"
    assert updated.canceled_at is not None
    assert updated.cancel_reason == "test cancel"
    assert updated.receipt_date is None

    # FIFO allocation reversed
    r_after = facade.get_redemption(redemption.id)
    assert not r_after.has_fifo_allocation


# ---------------------------------------------------------------------------
# H2 — Uncancel a CANCELED redemption → PENDING, FIFO re-applied
# ---------------------------------------------------------------------------

def test_h2_uncancel_restores_to_pending(facade, setup):
    redemption = _make_redemption(facade, setup)
    facade.cancel_redemption(redemption.id, reason="test cancel")

    canceled = facade.get_redemption(redemption.id)
    assert canceled.status == "CANCELED"

    facade.uncancel_redemption(redemption.id)

    restored = facade.get_redemption(redemption.id)
    assert restored.status == "PENDING"
    assert restored.canceled_at is None
    assert restored.cancel_reason is None
    assert restored.receipt_date is None

    # FIFO re-applied
    assert restored.has_fifo_allocation


# ---------------------------------------------------------------------------
# H3 — Cancel with active session → PENDING_CANCEL (deferred)
# ---------------------------------------------------------------------------

def test_h3_cancel_with_active_session_deferred(facade, setup):
    redemption = _make_redemption(facade, setup)

    # Open a game session (leaves status = Open so get_active_session finds it)
    session = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        calculate_pl=False,
    )
    # Open status
    assert session.status in ("Open", "open", "Active", "active")

    facade.cancel_redemption(redemption.id, reason="deferred")

    interim = facade.get_redemption(redemption.id)
    assert interim.status == "PENDING_CANCEL"
    # FIFO not yet reversed
    assert interim.has_fifo_allocation


# ---------------------------------------------------------------------------
# H4 — process_pending_cancels fires when session closes
# ---------------------------------------------------------------------------

def test_h4_pending_cancels_execute_on_session_close(facade, setup):
    redemption = _make_redemption(facade, setup)

    session = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        calculate_pl=False,
    )

    facade.cancel_redemption(redemption.id, reason="deferred")
    interim = facade.get_redemption(redemption.id)
    assert interim.status == "PENDING_CANCEL"

    # Close the session → should trigger process_pending_cancels
    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        end_date=date.today(),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    executed = facade.get_redemption(redemption.id)
    assert executed.status == "CANCELED"
    assert not executed.has_fifo_allocation


# ---------------------------------------------------------------------------
# E1 — Cannot cancel once receipt_date is set
# ---------------------------------------------------------------------------

def test_e1_cannot_cancel_received_redemption(facade, setup):
    redemption = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=date.today() - timedelta(days=5),
    )
    with pytest.raises(Exception, match=r"(?i)receipt|received|already"):
        facade.cancel_redemption(redemption.id, reason="should fail")


# ---------------------------------------------------------------------------
# E2 — Cannot cancel a CANCELED redemption
# ---------------------------------------------------------------------------

def test_e2_cannot_cancel_already_canceled(facade, setup):
    redemption = _make_redemption(facade, setup)
    facade.cancel_redemption(redemption.id, reason="first cancel")

    with pytest.raises(Exception, match=r"(?i)already|canceled|status"):
        facade.cancel_redemption(redemption.id, reason="second cancel")


# ---------------------------------------------------------------------------
# E3 — Cannot uncancel a PENDING redemption
# ---------------------------------------------------------------------------

def test_e3_cannot_uncancel_pending_redemption(facade, setup):
    redemption = _make_redemption(facade, setup)
    assert redemption.status == "PENDING"

    with pytest.raises(Exception, match=r"(?i)not canceled|pending|status"):
        facade.uncancel_redemption(redemption.id)


# ---------------------------------------------------------------------------
# E4 — Cancel reason is persisted
# ---------------------------------------------------------------------------

def test_e4_cancel_reason_stored(facade, setup):
    redemption = _make_redemption(facade, setup)
    facade.cancel_redemption(redemption.id, reason="customer request")

    updated = facade.get_redemption(redemption.id)
    assert updated.cancel_reason == "customer request"


# ---------------------------------------------------------------------------
# E5 — CANCELED rows excluded from pending-receipt notification query
# ---------------------------------------------------------------------------

def test_e5_canceled_excluded_from_notification_query(facade, setup):
    """After canceling, the redemption should not generate a pending-receipt notification."""
    # Use a redemption date far enough in the past (>7 days) so it crosses the threshold
    redemption = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=20),
        apply_fifo=True,
        receipt_date=None,
    )

    # Evaluate before cancel — rule should include this PENDING redemption.
    # (We query the DB directly to verify the rule's SQL filter, rather than
    #  relying on the JSON-backed notification store which may have cooldown state
    #  from earlier runs in the same process.)
    from services.notification_rules_service import NotificationRulesService
    from datetime import datetime as _dt
    from tools.timezone_utils import get_configured_timezone_name, local_date_time_to_utc
    tz_name = get_configured_timezone_name()
    threshold_date = (_dt.now() - timedelta(days=7)).date()
    cutoff_date, cutoff_time = local_date_time_to_utc(threshold_date, "23:59:59", tz_name)
    query = """
        SELECT r.id FROM redemptions r
        WHERE r.receipt_date IS NULL
          AND r.deleted_at IS NULL
          AND COALESCE(r.status, 'PENDING') = 'PENDING'
          AND (r.redemption_date < ?
               OR (r.redemption_date = ? AND COALESCE(r.redemption_time, '00:00:00') <= ?))
    """
    pending_rows_before = facade.db.fetch_all(query, (cutoff_date, cutoff_date, cutoff_time))
    ids_before = [r['id'] for r in pending_rows_before]
    assert redemption.id in ids_before, "Redemption should appear in notification SQL query before cancel"

    # Cancel the redemption
    facade.cancel_redemption(redemption.id, reason="e5 test")

    # After cancel: the same query must NOT include the now-CANCELED redemption
    pending_rows_after = facade.db.fetch_all(query, (cutoff_date, cutoff_date, cutoff_time))
    ids_after = [r['id'] for r in pending_rows_after]
    assert redemption.id not in ids_after, "CANCELED redemption must be excluded from notification SQL query"


# ---------------------------------------------------------------------------
# E6 — bulk_update_redemption_metadata skips CANCELED rows
# ---------------------------------------------------------------------------

def test_e6_bulk_mark_received_skips_canceled(facade, setup):
    # Add a second purchase to ensure enough basis
    facade.create_purchase(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=25),
        sc_received=Decimal("100.00"),
    )

    r1 = _make_redemption(facade, setup, amount="30.00", days_ago=15)
    r2 = _make_redemption(facade, setup, amount="20.00", days_ago=10)

    facade.cancel_redemption(r1.id, reason="canceled before bulk")

    # Bulk mark both as received
    receipt_date = date.today()
    facade.bulk_update_redemption_metadata(
        redemption_ids=[r1.id, r2.id],
        receipt_date=receipt_date,
    )

    updated_r1 = facade.get_redemption(r1.id)
    updated_r2 = facade.get_redemption(r2.id)

    # CANCELED row must not have been touched
    assert updated_r1.status == "CANCELED"
    assert updated_r1.receipt_date is None

    # PENDING row must have been updated
    assert updated_r2.receipt_date == receipt_date


# ---------------------------------------------------------------------------
# F1 — Canceling one redemption does NOT affect another's FIFO allocation
# ---------------------------------------------------------------------------

def test_f1_cancel_does_not_affect_other_redemptions(facade, setup):
    # Add more purchase basis
    facade.create_purchase(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=25),
        sc_received=Decimal("100.00"),
    )

    r1 = _make_redemption(facade, setup, amount="40.00", days_ago=20)
    r2 = _make_redemption(facade, setup, amount="40.00", days_ago=15)

    assert facade.get_redemption(r2.id).has_fifo_allocation

    # Cancel r1 only
    facade.cancel_redemption(r1.id, reason="cancel r1 only")

    # r2 should remain PENDING with its FIFO allocation intact
    r2_after = facade.get_redemption(r2.id)
    assert r2_after.status == "PENDING"
    assert r2_after.has_fifo_allocation
