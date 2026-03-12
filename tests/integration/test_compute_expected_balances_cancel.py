"""
Golden scenario tests for Issue #148: Two-event delta model in compute_expected_balances

Requires a CLOSED SESSION as the balance anchor so redemption deltas are
applied on top of the session's ending balance (purchase starting_sc_balance
would overwrite accumulated redemption deltas).

When a redemption is CANCELED its status contributes:
  Event 1 — debit of -amount  at redemption_date  (applies to ALL statuses)
  Event 2 — credit of +amount at canceled_at       (CANCELED only)

Net effect for a fully resolved CANCELED redemption = $0 impact on any balance
snapshot taken after canceled_at.

Scenarios:
  B1 — PENDING redemption reduces running balance
  B2 — CANCELED redemption is net-zero after cancellation date
  B3 — Balance snapshot between redemption_date and canceled_at shows debit only
  B4 — Uncancel re-introduces debit (PENDING again)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from app_facade import AppFacade


@pytest.fixture
def facade(tmp_path):
    db_path = tmp_path / "test_balance.db"
    f = AppFacade(str(db_path))
    yield f
    f.db.close()


@pytest.fixture
def ctx(facade):
    """User/site with a closed session ending at total=200, redeemable=100."""
    user = facade.create_user("Bob")
    site = facade.create_site("SiteB", sc_rate=1.0)

    # Create + close a session as the anchor
    sess = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=30),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("200.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("100.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=sess.id,
        ending_balance=Decimal("200.00"),
        ending_redeemable=Decimal("100.00"),
        end_date=date.today() - timedelta(days=30),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )
    return {"user": user, "site": site}


def _balance(facade, ctx, as_of_date: date) -> Decimal:
    """Expected total balance at midnight on as_of_date."""
    total, _ = facade.compute_expected_balances(
        user_id=ctx["user"].id,
        site_id=ctx["site"].id,
        session_date=as_of_date,
        session_time="00:00:00",
    )
    return total


# ---------------------------------------------------------------------------
# B1 — PENDING redemption reduces running balance
# ---------------------------------------------------------------------------

def test_b1_pending_reduces_balance(facade, ctx):
    # Before any redemption: expected = session ending balance (200)
    assert _balance(facade, ctx, date.today()) == Decimal("200.00")

    facade.create_redemption(
        user_id=ctx["user"].id,
        site_id=ctx["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=None,
    )

    balance = _balance(facade, ctx, date.today())
    assert balance == Decimal("150.00"), f"Expected 150, got {balance}"


# ---------------------------------------------------------------------------
# B2 — CANCELED redemption is net-zero after cancellation date
# ---------------------------------------------------------------------------

def test_b2_canceled_is_net_zero(facade, ctx):
    redemption = facade.create_redemption(
        user_id=ctx["user"].id,
        site_id=ctx["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=None,
    )

    # Before cancel: balance reduced by 50
    assert _balance(facade, ctx, date.today()) == Decimal("150.00")

    facade.cancel_redemption(redemption.id, reason="b2 test")

    # After cancel (cutoff = tomorrow, past canceled_at): net-zero, balance restored
    after = _balance(facade, ctx, date.today() + timedelta(days=1))
    assert after == Decimal("200.00"), f"Expected 200 after cancel, got {after}"


# ---------------------------------------------------------------------------
# B3 — Balance snapshot between redemption_date and canceled_at shows debit
# ---------------------------------------------------------------------------

def test_b3_balance_snapshot_in_window_shows_debit(facade, ctx):
    """
    Timeline:
      day -10: redemption of $50
      ~now:    cancellation (canceled_at ~ UTC today)
      day +1:  net-zero

    Cutoff at day -5: only debit event (day-10) is before cutoff; credit (today)
    is not yet reached -> balance = 150.

    Cutoff at day +1: both debit and credit are before cutoff -> net-zero = 200.
    """
    redemption = facade.create_redemption(
        user_id=ctx["user"].id,
        site_id=ctx["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=None,
    )

    facade.cancel_redemption(redemption.id, reason="b3 test")

    # Midpoint (before cancel credit): only debit visible
    mid = _balance(facade, ctx, date.today() - timedelta(days=5))
    assert mid == Decimal("150.00"), f"Expected 150 during window (day-5), got {mid}"

    # After cancel: net-zero
    after = _balance(facade, ctx, date.today() + timedelta(days=1))
    assert after == Decimal("200.00"), f"Expected 200 after cancel, got {after}"


# ---------------------------------------------------------------------------
# B4 — Uncancel re-introduces debit
# ---------------------------------------------------------------------------

def test_b4_uncancel_reintroduces_debit(facade, ctx):
    redemption = facade.create_redemption(
        user_id=ctx["user"].id,
        site_id=ctx["site"].id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=10),
        apply_fifo=True,
        receipt_date=None,
    )

    facade.cancel_redemption(redemption.id, reason="b4 cancel")
    # Confirm net-zero after cancel
    assert _balance(facade, ctx, date.today() + timedelta(days=1)) == Decimal("200.00")

    facade.uncancel_redemption(redemption.id)
    # Debit is back: status = PENDING, no credit event
    balance = _balance(facade, ctx, date.today() + timedelta(days=1))
    assert balance == Decimal("150.00"), f"Expected 150 after uncancel, got {balance}"


def test_redemption_amount_converts_from_usd_to_sc_for_non_unit_rate(facade):
    """At sc_rate=0.01, a $64.97 redemption must debit 6497 SC from expected balances."""
    user = facade.create_user("Rate User")
    site = facade.create_site("Rate Site", sc_rate=0.01)

    # Anchor expected total at 7000 SC from a closed session.
    sess = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=3),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("7000.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("7000.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=sess.id,
        ending_balance=Decimal("7000.00"),
        ending_redeemable=Decimal("7000.00"),
        end_date=date.today() - timedelta(days=3),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("64.97"),
        redemption_date=date.today() - timedelta(days=2),
        apply_fifo=True,
        receipt_date=None,
    )

    total, redeem = facade.compute_expected_balances(
        user_id=user.id,
        site_id=site.id,
        session_date=date.today(),
        session_time="00:00:00",
    )

    # $64.97 / 0.01 = 6497 SC debit.
    assert total == Decimal("503.00")
    assert redeem == Decimal("503.00")


def test_redemption_after_purchase_before_cutoff_is_applied_chronologically(facade):
    """A redemption after a purchase (both before cutoff) must reduce expected balances."""
    user = facade.create_user("Chronology User")
    site = facade.create_site("Chronology Site", sc_rate=0.01)

    # Anchor at 1000/1000 from a closed session.
    sess = facade.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=3),
        session_time="10:00:00",
        starting_balance=Decimal("0.00"),
        ending_balance=Decimal("1000.00"),
        starting_redeemable=Decimal("0.00"),
        ending_redeemable=Decimal("1000.00"),
        calculate_pl=False,
    )
    facade.update_game_session(
        session_id=sess.id,
        ending_balance=Decimal("1000.00"),
        ending_redeemable=Decimal("1000.00"),
        end_date=date.today() - timedelta(days=3),
        end_time="22:00:00",
        status="Closed",
        recalculate_pl=False,
    )

    # Purchase snapshot is post-purchase balance.
    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("3.00"),
        sc_received=Decimal("300.00"),
        starting_sc_balance=Decimal("1300.00"),
        purchase_date=date.today() - timedelta(days=2),
        purchase_time="10:00:00",
    )

    # $5.00 at sc_rate=0.01 => 500 SC redemption, after purchase and before cutoff.
    facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("5.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="11:00:00",
        apply_fifo=True,
        receipt_date=None,
    )

    total, redeem = facade.compute_expected_balances(
        user_id=user.id,
        site_id=site.id,
        session_date=date.today() - timedelta(days=2),
        session_time="12:00:00",
    )

    assert total == Decimal("800.00")
    assert redeem == Decimal("500.00")
