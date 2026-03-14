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
from datetime import date, datetime, timedelta
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


def _allocation_map(facade) -> dict[tuple[int, int], Decimal]:
    rows = facade.db.fetch_all(
        """
        SELECT redemption_id, purchase_id, allocated_amount
        FROM redemption_allocations
        ORDER BY redemption_id, purchase_id
        """
    )
    return {
        (int(row["redemption_id"]), int(row["purchase_id"])): Decimal(str(row["allocated_amount"]))
        for row in rows
    }


def _realized_cost_basis_map(facade) -> dict[int, Decimal]:
    rows = facade.db.fetch_all(
        """
        SELECT redemption_id, cost_basis
        FROM realized_transactions
        ORDER BY redemption_id
        """
    )
    return {
        int(row["redemption_id"]): Decimal(str(row["cost_basis"]))
        for row in rows
    }


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


def test_h4_pending_cancels_execute_on_session_close_with_default_recalc(facade, setup):
    """Closing a session through the normal path must complete queued cancels before rebuild."""
    anchor = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=3),
        session_time="08:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=anchor.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=3),
        end_time="09:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    active = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    redemption = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("25.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="12:00:00",
        apply_fifo=True,
        receipt_date=None,
    )

    facade.cancel_redemption(redemption.id, reason="queued during active session")
    assert facade.get_redemption(redemption.id).status == "PENDING_CANCEL"

    facade.update_game_session(
        session_id=active.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today(),
        end_time="22:00:00",
        status="Closed",
    )

    executed = facade.get_redemption(redemption.id)
    assert executed.status == "CANCELED"
    assert executed.has_fifo_allocation is False

    events = facade.get_linked_events_for_session(active.id)
    assert [r.id for r in events["redemptions"]] == []
    closed_session = facade.get_game_session(active.id)
    assert closed_session.redemptions_during == Decimal("0.00")


def test_pending_cancel_immediately_drops_from_closed_session_links_and_totals(facade):
    """Queued cancels should stop counting in closed-session links/totals before the later active session closes."""
    user = facade.create_user("Queued Link User")
    site = facade.create_site("Queued Link Site", sc_rate=1.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("100.00"),
    )

    closed_session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=4),
        session_time="08:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=closed_session.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=1),
        end_time="09:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("15.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="12:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    assert facade.get_game_session(closed_session.id).redemptions_during == Decimal("15.00")

    active_session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today(),
        session_time="10:00:00",
        starting_balance=Decimal("85.00"),
        ending_balance=Decimal("85.00"),
        starting_redeemable=Decimal("85.00"),
        ending_redeemable=Decimal("85.00"),
        calculate_pl=False,
    )
    assert active_session.status == "Active"

    facade.cancel_redemption(redemption.id, reason="queue but exclude now")

    queued = facade.get_redemption(redemption.id)
    assert queued.status == "PENDING_CANCEL"
    assert queued.has_fifo_allocation is True

    linked = facade.get_linked_events_for_session(closed_session.id)
    assert [r.id for r in linked["redemptions"]] == []
    refreshed_closed = facade.get_game_session(closed_session.id)
    assert refreshed_closed.redemptions_during == Decimal("0.00")


def test_delete_queued_redemption_keeps_closed_session_totals_clean(facade):
    """Deleting a queued cancel should not let prior closed sessions keep stale redemption totals."""
    user = facade.create_user("Queued Delete User")
    site = facade.create_site("Queued Delete Site", sc_rate=1.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("100.00"),
    )

    closed_session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=4),
        session_time="08:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=closed_session.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=1),
        end_time="09:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("15.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="12:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    assert facade.get_game_session(closed_session.id).redemptions_during == Decimal("15.00")

    active_session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today(),
        session_time="10:00:00",
        starting_balance=Decimal("85.00"),
        ending_balance=Decimal("85.00"),
        starting_redeemable=Decimal("85.00"),
        ending_redeemable=Decimal("85.00"),
        calculate_pl=False,
    )
    assert active_session.status == "Active"

    facade.cancel_redemption(redemption.id, reason="queue then delete")
    facade.delete_redemption(redemption.id)

    assert facade.get_redemption(redemption.id) is None
    linked = facade.get_linked_events_for_session(closed_session.id)
    assert [r.id for r in linked["redemptions"]] == []
    refreshed_closed = facade.get_game_session(closed_session.id)
    assert refreshed_closed.redemptions_during == Decimal("0.00")


def test_queued_historical_zero_basis_cancel_clears_realized_row_on_close(facade):
    """Queued cancel completion must delete realized rows even when the redemption had no FIFO allocations."""
    user = facade.create_user("Zero Basis User")
    site = facade.create_site("Zero Basis Site", sc_rate=1.0)

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("15.00"),
        redemption_date=date.today() - timedelta(days=10),
        redemption_time="09:00:00",
        apply_fifo=True,
        more_remaining=False,
    )

    realized_before = facade.db.fetch_all(
        "SELECT redemption_id FROM realized_transactions WHERE redemption_id = ?",
        (redemption.id,),
    )
    redemption = facade.get_redemption(redemption.id)
    assert realized_before == [{"redemption_id": redemption.id}]
    assert redemption.has_fifo_allocation is False

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("0.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        calculate_pl=False,
    )

    facade.cancel_redemption(redemption.id, reason="queue historical zero-basis")
    assert facade.get_redemption(redemption.id).status == "PENDING_CANCEL"

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        end_date=date.today(),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    refreshed = facade.get_redemption(redemption.id)
    realized_after = facade.db.fetch_all(
        "SELECT redemption_id FROM realized_transactions WHERE redemption_id = ?",
        (redemption.id,),
    )

    assert refreshed.status == "CANCELED"
    assert refreshed.has_fifo_allocation is False
    assert realized_after == []


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


def test_cancel_rebuilds_closed_session_expected_start_values(facade):
    """Cancel must propagate into closed-session recalculation, not only expected balances."""
    user = facade.create_user("Session Recalc User")
    site = facade.create_site("Session Recalc Site", sc_rate=1.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("200.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("200.00"),
    )

    anchor = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=8),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("200.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("200.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=anchor.id,
        ending_balance=Decimal("200.00"),
        ending_redeemable=Decimal("200.00"),
        end_date=date.today() - timedelta(days=8),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=5),
        redemption_time="12:00:00",
        apply_fifo=True,
        receipt_date=None,
    )

    facade.cancel_redemption(redemption.id, reason="session recalc")

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() + timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("200.00"),
        ending_balance=Decimal("200.00"),
        starting_redeemable=Decimal("200.00"),
        ending_redeemable=Decimal("200.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("200.00"),
        ending_redeemable=Decimal("200.00"),
        end_date=date.today() + timedelta(days=1),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    after = facade.get_game_session(session.id)
    assert after.expected_start_total == Decimal("200.00")
    assert after.expected_start_redeemable == Decimal("200.00")


def test_cancel_removes_redemption_from_session_links_and_redemptions_during(facade):
    """Canceled redemptions must not remain linked into closed-session DURING totals."""
    user = facade.create_user("Link User")
    site = facade.create_site("Link Site", sc_rate=1.0)

    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=10),
        sc_received=Decimal("100.00"),
    )

    anchor = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=5),
        session_time="08:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=anchor.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=5),
        end_time="09:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    session = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=2),
        session_time="10:00:00",
        starting_balance=Decimal("100.00"),
        ending_balance=Decimal("100.00"),
        starting_redeemable=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("100.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=2),
        end_time="11:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="10:30:00",
        apply_fifo=True,
        receipt_date=None,
    )

    linked_before = facade.get_linked_events_for_session(session.id)
    assert [r.id for r in linked_before["redemptions"]] == [redemption.id]
    assert facade.get_game_session(session.id).redemptions_during == Decimal("50.00")

    facade.cancel_redemption(redemption.id, reason="remove links")

    linked_after = facade.get_linked_events_for_session(session.id)
    assert [r.id for r in linked_after["redemptions"]] == []
    assert facade.get_game_session(session.id).redemptions_during == Decimal("0.00")


def test_cancel_rollback_restores_allocations_when_status_update_fails(facade, setup, monkeypatch):
    """Failure injection: cancel must roll back to the original state atomically."""
    redemption = _make_redemption(facade, setup)
    purchase = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    remaining_before = purchase.remaining_amount

    def boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(facade.redemption_service, "_update_redemption_no_commit", boom)

    with pytest.raises(RuntimeError, match="forced failure"):
        facade.cancel_redemption(redemption.id, reason="rollback test")

    refreshed = facade.get_redemption(redemption.id)
    refreshed_purchase = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    assert refreshed.status == "PENDING"
    assert refreshed.has_fifo_allocation is True
    assert refreshed_purchase.remaining_amount == remaining_before


def test_update_redemption_rejects_cancel_lifecycle_fields(facade, setup):
    """Lightweight metadata updates must not mutate cancel lifecycle/accounting fields."""
    redemption = _make_redemption(facade, setup)

    with pytest.raises(ValueError, match=r"(?i)cancel lifecycle|not directly editable"):
        facade.update_redemption(
            redemption.id,
            status="CANCELED",
            canceled_at="2026-03-13 12:00:00",
        )

    refreshed = facade.get_redemption(redemption.id)
    assert refreshed.status == "PENDING"
    assert refreshed.canceled_at is None


def test_uncancel_rebuilds_fifo_chronologically_when_later_redemption_exists(facade, setup):
    """Uncancel must rebuild from the original timestamp when later pending redemptions exist."""
    first = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("60.00"),
        redemption_date=date.today() - timedelta(days=10),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )

    facade.cancel_redemption(first.id, reason="re-open chronology")

    later = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("80.00"),
        redemption_date=date.today() - timedelta(days=9),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )

    facade.uncancel_redemption(first.id)

    allocations = _allocation_map(facade)
    realized = _realized_cost_basis_map(facade)
    purchase = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]

    assert allocations[(first.id, purchase.id)] == Decimal("60.00")
    assert allocations[(later.id, purchase.id)] == Decimal("40.00")
    assert realized[first.id] == Decimal("60.00")
    assert realized[later.id] == Decimal("40.00")
    assert purchase.remaining_amount == Decimal("0.00")


def test_nested_cancel_uncancel_sequence_stays_rebuild_stable(facade, setup):
    """Nested cancel/uncancel chains should land in the same FIFO state as a fresh rebuild."""
    original_purchase = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    first = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("60.00"),
        redemption_date=date.today() - timedelta(days=10),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    facade.cancel_redemption(first.id, reason="first off")

    extra_purchase = facade.create_purchase(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("40.00"),
        purchase_date=date.today() - timedelta(days=9),
        purchase_time="09:00:00",
        sc_received=Decimal("40.00"),
    )
    second = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("80.00"),
        redemption_date=date.today() - timedelta(days=8),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    facade.cancel_redemption(second.id, reason="second off")

    facade.uncancel_redemption(first.id)
    facade.uncancel_redemption(second.id)

    allocations = _allocation_map(facade)
    realized = _realized_cost_basis_map(facade)
    original_purchase = facade.purchase_repo.get_by_id(original_purchase.id)
    extra_purchase = facade.purchase_repo.get_by_id(extra_purchase.id)

    assert allocations[(first.id, original_purchase.id)] == Decimal("60.00")
    assert allocations[(second.id, original_purchase.id)] == Decimal("40.00")
    assert allocations[(second.id, extra_purchase.id)] == Decimal("40.00")
    assert realized[first.id] == Decimal("60.00")
    assert realized[second.id] == Decimal("80.00")
    assert original_purchase.remaining_amount == Decimal("0.00")
    assert extra_purchase.remaining_amount == Decimal("0.00")


def test_recalculate_everything_preserves_pending_cancel_accounting_state(facade, setup):
    """Full rebuild must not corrupt queued-cancel FIFO/realized state or break later close."""
    redemption = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("20.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    session = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="09:00:00",
        starting_balance=Decimal("80.00"),
        ending_balance=Decimal("80.00"),
        starting_redeemable=Decimal("80.00"),
        ending_redeemable=Decimal("80.00"),
        calculate_pl=False,
    )

    facade.cancel_redemption(redemption.id, reason="queued before rebuild")
    assert facade.get_redemption(redemption.id).status == "PENDING_CANCEL"

    facade.recalculate_everything()

    queued = facade.get_redemption(redemption.id)
    purchase = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    realized = _realized_cost_basis_map(facade)

    assert queued.status == "PENDING_CANCEL"
    assert queued.has_fifo_allocation is True
    assert purchase.remaining_amount == Decimal("80.00")
    assert realized[redemption.id] == Decimal("20.00")

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("80.00"),
        ending_redeemable=Decimal("80.00"),
        end_date=date.today() - timedelta(days=1),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    executed = facade.get_redemption(redemption.id)
    assert executed.status == "CANCELED"
    assert executed.has_fifo_allocation is False


def test_canceled_at_is_localized_for_closed_session_recalc_events(facade, setup, monkeypatch):
    """Closed-session recalculation must place cancel credits on the accounting-local timeline."""
    redemption = _make_redemption(facade, setup, amount="10.00")
    facade.cancel_redemption(redemption.id, reason="timezone parity")
    facade.db.execute(
        "UPDATE redemptions SET canceled_at = ? WHERE id = ?",
        ("2026-03-13 01:30:00", redemption.id),
    )

    monkeypatch.setattr(
        "services.game_session_service.utc_date_time_to_accounting_local",
        lambda db, utc_date, utc_time, settings=None: (date(2026, 3, 12), "20:30:00"),
    )

    events = facade.game_session_service._load_redemption_balance_events(
        setup["user"].id,
        setup["site"].id,
    )

    assert (datetime(2026, 3, 12, 20, 30, 0), Decimal("-10.00")) in events


def test_undo_completed_pending_cancel_restores_pending_with_fifo_allocation(facade, setup):
    """Undoing deferred-cancel completion must restore a usable pending redemption state."""
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

    facade.cancel_redemption(redemption.id, reason="queued")
    assert facade.get_redemption(redemption.id).status == "PENDING_CANCEL"

    facade.update_game_session(
        session_id=session.id,
        ending_balance=Decimal("0.00"),
        ending_redeemable=Decimal("0.00"),
        end_date=date.today(),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )
    assert facade.get_redemption(redemption.id).status == "CANCELED"

    facade.undo_redo_service.undo()

    restored = facade.get_redemption(redemption.id)
    assert restored.status == "PENDING"
    assert restored.receipt_date is None
    assert restored.has_fifo_allocation is True


def test_pending_cancel_batch_failure_rolls_back_all_and_session_close(facade, setup, monkeypatch):
    """Deferred-cancel completion should be all-or-nothing across the whole close operation."""
    first = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("20.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="11:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    second = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("30.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="12:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    session = facade.create_game_session(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="10:00:00",
        starting_balance=Decimal("50.00"),
        ending_balance=Decimal("50.00"),
        starting_redeemable=Decimal("50.00"),
        ending_redeemable=Decimal("50.00"),
        calculate_pl=False,
    )

    facade.cancel_redemption(first.id, reason="queue first")
    facade.cancel_redemption(second.id, reason="queue second")
    assert facade.get_redemption(first.id).status == "PENDING_CANCEL"
    assert facade.get_redemption(second.id).status == "PENDING_CANCEL"

    purchase_before = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    realized_before = _realized_cost_basis_map(facade)
    original_update = facade.redemption_service._update_redemption_no_commit

    def fail_on_second(redemption):
        if redemption.id == second.id and getattr(redemption, "status", None) == "CANCELED":
            raise RuntimeError("forced second pending cancel failure")
        return original_update(redemption)

    monkeypatch.setattr(facade.redemption_service, "_update_redemption_no_commit", fail_on_second)

    with pytest.raises(RuntimeError, match="forced second pending cancel failure"):
        facade.update_game_session(
            session_id=session.id,
            ending_balance=Decimal("50.00"),
            ending_redeemable=Decimal("50.00"),
            end_date=date.today(),
            end_time="22:00:00",
            status="Closed",
            recalculate_pl=False,
        )

    refreshed_session = facade.get_game_session(session.id)
    refreshed_first = facade.get_redemption(first.id)
    refreshed_second = facade.get_redemption(second.id)
    purchase_after = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    realized_after = _realized_cost_basis_map(facade)

    assert refreshed_session.status == "Active"
    assert refreshed_first.status == "PENDING_CANCEL"
    assert refreshed_second.status == "PENDING_CANCEL"
    assert refreshed_first.has_fifo_allocation is True
    assert refreshed_second.has_fifo_allocation is True
    assert purchase_after.remaining_amount == purchase_before.remaining_amount
    assert realized_after == realized_before


def test_undo_delete_pending_cancel_restores_queued_state_with_fifo(facade, setup):
    """Undoing delete of a queued cancel should restore the queued row plus preserved FIFO state."""
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
    redemption = _make_redemption(facade, setup)
    facade.cancel_redemption(redemption.id, reason="queue before delete")
    assert facade.get_redemption(redemption.id).status == "PENDING_CANCEL"

    facade.delete_redemption(redemption.id)
    assert facade.get_redemption(redemption.id) is None

    facade.undo_redo_service.undo()

    restored = facade.get_redemption(redemption.id)
    assert session.status == "Active"
    assert restored.status == "PENDING_CANCEL"
    assert restored.has_fifo_allocation is True


def test_undo_delete_canceled_redemption_restores_canceled_without_fifo(facade, setup):
    """Undoing delete of a canceled redemption should not resurrect live FIFO allocations."""
    redemption = _make_redemption(facade, setup)
    facade.cancel_redemption(redemption.id, reason="cancel before delete")
    canceled = facade.get_redemption(redemption.id)
    assert canceled.status == "CANCELED"
    assert canceled.has_fifo_allocation is False

    facade.delete_redemption(redemption.id)
    assert facade.get_redemption(redemption.id) is None

    facade.undo_redo_service.undo()

    restored = facade.get_redemption(redemption.id)
    assert restored.status == "CANCELED"
    assert restored.has_fifo_allocation is False


def test_undo_create_redemption_cleans_fifo_artifacts_and_restores_purchase(facade, setup):
    """Undoing redemption creation must remove FIFO/realized artifacts for the soft-deleted row."""
    redemption = facade.create_redemption(
        user_id=setup["user"].id,
        site_id=setup["site"].id,
        amount=Decimal("10.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="12:00:00",
        apply_fifo=True,
        more_remaining=True,
    )

    purchase_before_undo = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    assert purchase_before_undo.remaining_amount == Decimal("90.00")

    facade.undo_redo_service.undo()

    purchase_after_undo = facade.purchase_repo.get_by_user_and_site(setup["user"].id, setup["site"].id)[0]
    allocation_rows = facade.db.fetch_all(
        "SELECT redemption_id, purchase_id FROM redemption_allocations WHERE redemption_id = ?",
        (redemption.id,),
    )
    realized_rows = facade.db.fetch_all(
        "SELECT redemption_id FROM realized_transactions WHERE redemption_id = ?",
        (redemption.id,),
    )

    assert facade.get_redemption(redemption.id) is None
    assert purchase_after_undo.remaining_amount == Decimal("100.00")
    assert allocation_rows == []
    assert realized_rows == []


def test_rebuild_ignores_soft_deleted_purchases_after_undo(facade):
    """Scoped/full rebuilds must not reallocate against soft-deleted purchases restored only in audit history."""
    user = facade.create_user("Deleted Purchase User")
    site = facade.create_site("Deleted Purchase Site", sc_rate=1.0)

    purchase_1 = facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date.today() - timedelta(days=20),
        sc_received=Decimal("100.00"),
    )
    facade.undo_redo_service.undo()
    assert facade.get_purchase(purchase_1.id) is None

    purchase_2 = facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("40.00"),
        purchase_date=date.today() - timedelta(days=10),
        purchase_time="10:00:00",
        sc_received=Decimal("40.00"),
    )

    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("20.00"),
        redemption_date=date.today() - timedelta(days=5),
        redemption_time="14:00:00",
        apply_fifo=True,
        more_remaining=True,
    )

    allocation_rows = facade.db.fetch_all(
        "SELECT purchase_id, allocated_amount FROM redemption_allocations WHERE redemption_id = ?",
        (redemption.id,),
    )
    refreshed_purchase = facade.get_purchase(purchase_2.id)

    assert allocation_rows == [{"purchase_id": purchase_2.id, "allocated_amount": "20.00"}]
    assert refreshed_purchase.remaining_amount == Decimal("20.00")

    facade.delete_redemption(redemption.id)
    assert facade.get_redemption(redemption.id) is None
