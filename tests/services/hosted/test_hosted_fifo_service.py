"""Tests for HostedFIFOService — FIFO cost-basis calculation."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.persistence import HostedBase, HostedPurchaseRecord
from services.hosted.hosted_fifo_service import HostedFIFOService


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


def _make_purchase(date: str, time: str, amount: str, remaining: str | None = None, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount=amount,
        remaining_amount=remaining or amount,
        purchase_date=date,
        purchase_time=time,
    )
    defaults.update(kw)
    return HostedPurchaseRecord(**defaults)


# ------------------------------------------------------------------
# Tests — calculate_cost_basis
# ------------------------------------------------------------------


def test_single_purchase_full_redemption():
    """One purchase covers the entire redemption."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-01", "10:00:00", "100.00"))
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("80.00"),
                redemption_date="2026-01-15",
                redemption_time="12:00:00",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("80.00")
    assert profit == Decimal("0.00")
    assert len(allocs) == 1
    assert allocs[0][1] == Decimal("80.00")


def test_multiple_purchases_fifo_order():
    """Purchases are consumed oldest-first."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            p1 = _make_purchase("2026-01-01", "10:00:00", "30.00")
            p2 = _make_purchase("2026-01-02", "10:00:00", "50.00")
            p3 = _make_purchase("2026-01-03", "10:00:00", "40.00")
            session.add_all([p1, p2, p3])
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("60.00"),
                redemption_date="2026-01-15",
            )
    finally:
        engine.dispose()

    # Should consume $30 from p1, $30 from p2
    assert cost == Decimal("60.00")
    assert profit == Decimal("0.00")
    assert len(allocs) == 2
    assert allocs[0] == (p1.id, Decimal("30.00"))
    assert allocs[1] == (p2.id, Decimal("30.00"))


def test_insufficient_basis_partial():
    """When basis < redemption amount, taxable profit is the remainder."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-01", "10:00:00", "40.00"))
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("100.00"),
                redemption_date="2026-01-15",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("40.00")
    assert profit == Decimal("60.00")
    assert len(allocs) == 1


def test_no_purchases_zero_basis():
    """No available purchases → zero cost basis."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("50.00"),
                redemption_date="2026-01-15",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("0.00")
    assert profit == Decimal("50.00")
    assert allocs == []


def test_consumed_purchases_skipped():
    """Purchases with remaining_amount=0 are not allocated."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-01", "10:00:00", "50.00", remaining="0.00"))
            session.add(_make_purchase("2026-01-02", "10:00:00", "30.00"))
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("30.00"),
                redemption_date="2026-01-15",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("30.00")
    assert len(allocs) == 1  # Only the second purchase


def test_future_purchases_excluded():
    """Purchases after the redemption date/time are not eligible."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-20", "10:00:00", "100.00"))
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("50.00"),
                redemption_date="2026-01-15",
                redemption_time="12:00:00",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("0.00")
    assert allocs == []


# ------------------------------------------------------------------
# Tests — apply_allocation / reverse_allocation
# ------------------------------------------------------------------


def test_apply_allocation_reduces_remaining():
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            p = _make_purchase("2026-01-01", "10:00:00", "100.00")
            session.add(p)
            session.flush()
            pid = p.id

            svc.apply_allocation(session, [(pid, Decimal("40.00"))])
            session.flush()

            updated = session.get(HostedPurchaseRecord, pid)
            assert Decimal(updated.remaining_amount) == Decimal("60.00")
    finally:
        engine.dispose()


def test_reverse_allocation_restores_remaining():
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            p = _make_purchase("2026-01-01", "10:00:00", "100.00", remaining="60.00")
            session.add(p)
            session.flush()
            pid = p.id

            svc.reverse_allocation(session, [(pid, Decimal("40.00"))])
            session.flush()

            updated = session.get(HostedPurchaseRecord, pid)
            assert Decimal(updated.remaining_amount) == Decimal("100.00")
    finally:
        engine.dispose()


def test_apply_allocation_over_remaining_raises():
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            p = _make_purchase("2026-01-01", "10:00:00", "50.00")
            session.add(p)
            session.flush()

            with pytest.raises(ValueError, match="Cannot allocate"):
                svc.apply_allocation(session, [(p.id, Decimal("60.00"))])
    finally:
        engine.dispose()


def test_reverse_allocation_over_original_raises():
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            p = _make_purchase("2026-01-01", "10:00:00", "50.00")
            session.add(p)
            session.flush()

            with pytest.raises(ValueError, match="Would exceed original"):
                svc.reverse_allocation(session, [(p.id, Decimal("10.00"))])
    finally:
        engine.dispose()


def test_deleted_purchases_excluded():
    """Soft-deleted purchases are not eligible for FIFO."""
    engine, sf = _session_factory()
    svc = HostedFIFOService()
    try:
        with sf() as session:
            session.add(_make_purchase(
                "2026-01-01", "10:00:00", "100.00",
                deleted_at="2026-01-10T00:00:00",
            ))
            session.flush()

            cost, profit, allocs = svc.calculate_cost_basis(
                session,
                workspace_id=W, user_id=U, site_id=S,
                redemption_amount=Decimal("50.00"),
                redemption_date="2026-01-15",
            )
    finally:
        engine.dispose()

    assert cost == Decimal("0.00")
    assert allocs == []
