"""Tests for HostedRecalculationService — bulk FIFO + realized-transaction rebuilds."""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.persistence import (
    HostedBase,
    HostedAccountAdjustmentRecord,
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionAllocationRecord,
    HostedRedemptionRecord,
    HostedRealizedTransactionRecord,
)
from services.hosted.hosted_recalculation_service import (
    HostedRecalculationService,
    _parse_close_balance_loss,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

W = "workspace-1"
U = "user-1"
S = "site-1"


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    HostedBase.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _purchase(date, time, amount, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount=str(amount),
        remaining_amount=str(amount),
        purchase_date=date,
        purchase_time=time,
    )
    defaults.update(kw)
    return HostedPurchaseRecord(**defaults)


def _redemption(date, time, amount, *, more_remaining=False, is_free_sc=False, notes=None, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount=str(amount),
        redemption_date=date,
        redemption_time=time,
        more_remaining=more_remaining,
        is_free_sc=is_free_sc,
        notes=notes,
        status="PENDING",
    )
    defaults.update(kw)
    return HostedRedemptionRecord(**defaults)


def _game_session(date, time, *, end_date=None, end_time=None, status="Active", **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        session_date=date,
        session_time=time,
        end_date=end_date,
        end_time=end_time,
        status=status,
    )
    defaults.update(kw)
    return HostedGameSessionRecord(**defaults)


def _adjustment(date, time, delta_basis, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        effective_date=date,
        effective_time=time,
        type="BASIS_USD_CORRECTION",
        delta_basis_usd=str(delta_basis),
        reason="test adjustment",
    )
    defaults.update(kw)
    return HostedAccountAdjustmentRecord(**defaults)


# ------------------------------------------------------------------
# Tests — _parse_close_balance_loss (pure function)
# ------------------------------------------------------------------


def test_parse_close_balance_loss_simple():
    assert _parse_close_balance_loss("Net Loss: $45.00") == Decimal("45.00")


def test_parse_close_balance_loss_with_comma():
    assert _parse_close_balance_loss("Net Loss: $1,234.56") == Decimal("1234.56")


def test_parse_close_balance_loss_none():
    assert _parse_close_balance_loss(None) is None
    assert _parse_close_balance_loss("No loss here") is None
    assert _parse_close_balance_loss("") is None


# ------------------------------------------------------------------
# Tests — rebuild_fifo_for_pair (happy path)
# ------------------------------------------------------------------


def test_single_purchase_single_redemption():
    """One purchase, one full redemption → cost basis equals available amount."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            r = _redemption("2026-01-15", "12:00:00", 150, more_remaining=False)
            session.add_all([p, r])
            session.flush()

            result = svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            # Check result
            assert result.pairs_processed == 1
            assert result.redemptions_processed == 1
            assert result.allocations_written == 1

            # Check allocation
            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 1
            assert allocs[0].purchase_id == p.id
            assert allocs[0].redemption_id == r.id
            assert Decimal(allocs[0].allocated_amount) == Decimal("100")

            # Check realized transaction
            realized = session.query(HostedRealizedTransactionRecord).all()
            assert len(realized) == 1
            assert Decimal(realized[0].cost_basis) == Decimal("100")
            assert Decimal(realized[0].payout) == Decimal("150")
            assert Decimal(realized[0].net_pl) == Decimal("50")

            # Check purchase remaining reset to 0
            p_updated = session.get(HostedPurchaseRecord, p.id)
            assert Decimal(p_updated.remaining_amount) == Decimal("0")
    finally:
        engine.dispose()


def test_multiple_purchases_multiple_redemptions():
    """Multiple purchases consumed in FIFO order across redemptions."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p1 = _purchase("2026-01-01", "10:00:00", 50)
            p2 = _purchase("2026-01-02", "10:00:00", 75)
            # Partial: consumes only payout amount ($40)
            r1 = _redemption("2026-01-10", "12:00:00", 40, more_remaining=True)
            # Full: consumes ALL remaining basis
            r2 = _redemption("2026-01-20", "12:00:00", 200, more_remaining=False)
            session.add_all([p1, p2, r1, r2])
            session.flush()

            svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            allocs = (
                session.query(HostedRedemptionAllocationRecord)
                .order_by(HostedRedemptionAllocationRecord.created_at)
                .all()
            )
            # r1 (partial, $40): takes $40 from p1
            # r2 (full): takes remaining $10 from p1 + $75 from p2 = $85
            r1_allocs = [a for a in allocs if a.redemption_id == r1.id]
            r2_allocs = [a for a in allocs if a.redemption_id == r2.id]

            assert len(r1_allocs) == 1
            assert Decimal(r1_allocs[0].allocated_amount) == Decimal("40")

            assert len(r2_allocs) == 2
            r2_total = sum(Decimal(a.allocated_amount) for a in r2_allocs)
            assert r2_total == Decimal("85")  # 10 + 75

            # Check realized
            realized = (
                session.query(HostedRealizedTransactionRecord)
                .order_by(HostedRealizedTransactionRecord.redemption_date)
                .all()
            )
            assert len(realized) == 2
            # r1: payout=40, cost_basis=40, net_pl=0
            assert Decimal(realized[0].net_pl) == Decimal("0")
            # r2: payout=200, cost_basis=85, net_pl=115
            assert Decimal(realized[1].payout) == Decimal("200")
            assert Decimal(realized[1].cost_basis) == Decimal("85")
            assert Decimal(realized[1].net_pl) == Decimal("115")
    finally:
        engine.dispose()


# ------------------------------------------------------------------
# Tests — special cases
# ------------------------------------------------------------------


def test_free_sc_redemption_skips_fifo():
    """Free SC redemptions should not generate FIFO allocations."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            r = _redemption("2026-01-15", "12:00:00", 50, is_free_sc=True)
            session.add_all([p, r])
            session.flush()

            svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 0

            # Realized transaction still written (cost_basis = 0)
            realized = session.query(HostedRealizedTransactionRecord).all()
            assert len(realized) == 1
            assert Decimal(realized[0].cost_basis) == Decimal("0")
            assert Decimal(realized[0].payout) == Decimal("50")
            assert Decimal(realized[0].net_pl) == Decimal("50")

            # Purchase remaining unchanged
            assert Decimal(session.get(HostedPurchaseRecord, p.id).remaining_amount) == Decimal("100")
    finally:
        engine.dispose()


def test_close_balance_net_loss():
    """Close-balance (Net Loss) redemption consumes the loss amount as basis."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            r = _redemption(
                "2026-01-15", "12:00:00", 0,
                notes="Close balance: Net Loss: $30.00",
            )
            session.add_all([p, r])
            session.flush()

            svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 1
            assert Decimal(allocs[0].allocated_amount) == Decimal("30")

            realized = session.query(HostedRealizedTransactionRecord).all()
            assert len(realized) == 1
            assert Decimal(realized[0].cost_basis) == Decimal("30")
            assert Decimal(realized[0].payout) == Decimal("0")
            assert Decimal(realized[0].net_pl) == Decimal("-30")
    finally:
        engine.dispose()


def test_canceled_redemptions_excluded():
    """Canceled redemptions should not participate in FIFO."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            r_canceled = _redemption(
                "2026-01-15", "12:00:00", 50,
                status="CANCELED",
            )
            session.add_all([p, r_canceled])
            session.flush()

            result = svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            assert result.redemptions_processed == 0
            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 0
    finally:
        engine.dispose()


def test_synthetic_adjustment_participates_in_fifo():
    """BASIS_USD_CORRECTION adjustments act as synthetic purchase lots."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 50)
            adj = _adjustment("2026-01-05", "10:00:00", 25)
            # Full redemption — consumes all basis ($50 purchase + $25 adjustment = $75)
            r = _redemption("2026-01-20", "12:00:00", 100, more_remaining=False)
            session.add_all([p, adj, r])
            session.flush()

            svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            # Allocations only for real purchases (not synthetic adj-*)
            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 1
            assert allocs[0].purchase_id == p.id
            assert Decimal(allocs[0].allocated_amount) == Decimal("50")

            # Realized: cost_basis = 50 + 25 = 75, payout = 100
            realized = session.query(HostedRealizedTransactionRecord).all()
            assert len(realized) == 1
            assert Decimal(realized[0].cost_basis) == Decimal("75")
            assert Decimal(realized[0].net_pl) == Decimal("25")
    finally:
        engine.dispose()


# ------------------------------------------------------------------
# Tests — iter_pairs
# ------------------------------------------------------------------


def test_iter_pairs_returns_distinct():
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            session.add(_purchase("2026-01-01", "10:00:00", 100))
            session.add(_purchase("2026-01-02", "10:00:00", 50))
            session.add(_redemption("2026-01-15", "12:00:00", 50))
            session.add(_purchase(
                "2026-01-01", "10:00:00", 25,
                user_id="user-2", site_id="site-2",
            ))
            session.flush()

            pairs = svc.iter_pairs(session, W)
    finally:
        engine.dispose()

    assert len(pairs) == 2
    assert (U, S) in pairs
    assert ("user-2", "site-2") in pairs


# ------------------------------------------------------------------
# Tests — rebuild_all
# ------------------------------------------------------------------


def test_rebuild_all_processes_all_pairs():
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            # Pair 1
            session.add(_purchase("2026-01-01", "10:00:00", 100))
            session.add(_redemption("2026-01-15", "12:00:00", 50, more_remaining=True))
            # Pair 2
            session.add(_purchase(
                "2026-01-01", "10:00:00", 200,
                user_id="user-2", site_id="site-2",
            ))
            session.add(HostedRedemptionRecord(
                id=str(uuid4()),
                workspace_id=W,
                user_id="user-2",
                site_id="site-2",
                amount="80",
                redemption_date="2026-01-15",
                redemption_time="12:00:00",
                more_remaining=True,
                status="PENDING",
            ))
            session.flush()

            result = svc.rebuild_all(session, workspace_id=W)
            session.flush()
    finally:
        engine.dispose()

    assert result.pairs_processed == 2
    assert result.redemptions_processed == 2
    assert result.allocations_written == 2


# ------------------------------------------------------------------
# Tests — rebuild_fifo_for_pair clears prior derived records
# ------------------------------------------------------------------


def test_rebuild_clears_previous_allocations():
    """Running rebuild twice should produce the same result (idempotent)."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            r = _redemption("2026-01-15", "12:00:00", 60, more_remaining=True)
            session.add_all([p, r])
            session.flush()

            svc.rebuild_fifo_for_pair(session, workspace_id=W, user_id=U, site_id=S)
            session.flush()

            # Run again
            svc.rebuild_fifo_for_pair(session, workspace_id=W, user_id=U, site_id=S)
            session.flush()

            allocs = session.query(HostedRedemptionAllocationRecord).all()
            assert len(allocs) == 1  # Not duplicated

            realized = session.query(HostedRealizedTransactionRecord).all()
            assert len(realized) == 1  # Not duplicated
    finally:
        engine.dispose()


# ------------------------------------------------------------------
# Tests — scoped rebuild (from boundary)
# ------------------------------------------------------------------


def test_scoped_rebuild_from_boundary():
    """Scoped rebuild only re-processes redemptions at or after the boundary."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p1 = _purchase("2026-01-01", "10:00:00", 100)
            p2 = _purchase("2026-01-02", "10:00:00", 50)
            # r1 is before the boundary — its allocations should be preserved
            r1 = _redemption("2026-01-10", "08:00:00", 40, more_remaining=True)
            # r2 is at/after the boundary — will be re-processed
            r2 = _redemption("2026-01-20", "12:00:00", 80, more_remaining=True)
            session.add_all([p1, p2, r1, r2])
            session.flush()

            # First: full rebuild so prior allocations exist
            svc.rebuild_fifo_for_pair(session, workspace_id=W, user_id=U, site_id=S)
            session.flush()

            # Now scoped rebuild from boundary
            result = svc.rebuild_fifo_for_pair_from(
                session,
                workspace_id=W, user_id=U, site_id=S,
                from_date="2026-01-15",
                from_time="00:00:00",
            )
            session.flush()

            # r1 allocations should still exist
            r1_allocs = (
                session.query(HostedRedemptionAllocationRecord)
                .filter(HostedRedemptionAllocationRecord.redemption_id == r1.id)
                .all()
            )
            assert len(r1_allocs) == 1
            assert Decimal(r1_allocs[0].allocated_amount) == Decimal("40")

            # r2 allocations should be rebuilt
            r2_allocs = (
                session.query(HostedRedemptionAllocationRecord)
                .filter(HostedRedemptionAllocationRecord.redemption_id == r2.id)
                .all()
            )
            assert len(r2_allocs) >= 1
            r2_total = sum(Decimal(a.allocated_amount) for a in r2_allocs)
            assert r2_total == Decimal("80")

            assert result.redemptions_processed == 1  # Only r2
    finally:
        engine.dispose()


# ------------------------------------------------------------------
# Tests — failure injection / invariants
# ------------------------------------------------------------------


def test_empty_workspace_returns_zero_result():
    """Rebuilding with no data should not error."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            result = svc.rebuild_fifo_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()
    finally:
        engine.dispose()

    assert result.pairs_processed == 1
    assert result.redemptions_processed == 0
    assert result.allocations_written == 0


def test_only_purchases_no_allocations():
    """Purchases with no redemptions → no allocations, remaining unchanged."""
    engine, sf = _session_factory()
    svc = HostedRecalculationService()
    try:
        with sf() as session:
            p = _purchase("2026-01-01", "10:00:00", 100)
            session.add(p)
            session.flush()

            svc.rebuild_fifo_for_pair(session, workspace_id=W, user_id=U, site_id=S)
            session.flush()

            assert Decimal(session.get(HostedPurchaseRecord, p.id).remaining_amount) == Decimal("100")
            assert session.query(HostedRedemptionAllocationRecord).count() == 0
    finally:
        engine.dispose()
