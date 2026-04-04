"""Tests for HostedTimestampService — timestamp uniqueness enforcement."""

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.persistence import (
    HostedBase,
    HostedPurchaseRecord,
    HostedRedemptionRecord,
    HostedGameSessionRecord,
)
from services.hosted.hosted_timestamp_service import HostedTimestampService


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


def _make_purchase(date: str, time: str, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount="100.00",
        remaining_amount="100.00",
        purchase_date=date,
        purchase_time=time,
    )
    defaults.update(kw)
    return HostedPurchaseRecord(**defaults)


def _make_redemption(date: str, time: str, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount="50.00",
        redemption_date=date,
        redemption_time=time,
    )
    defaults.update(kw)
    return HostedRedemptionRecord(**defaults)


def _make_session(date: str, time: str, *, end_date=None, end_time=None, status="Active", **kw):
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


# ------------------------------------------------------------------
# Tests — happy path
# ------------------------------------------------------------------


def test_no_conflict_returns_unchanged():
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30:00",
            )
    finally:
        engine.dispose()

    assert date == "2026-01-15"
    assert time == "14:30:00"
    assert adjusted is False


def test_conflict_with_purchase_auto_increments():
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-15", "14:30:00"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30:00",
                event_type="purchase",
            )
    finally:
        engine.dispose()

    assert date == "2026-01-15"
    assert time == "14:30:01"
    assert adjusted is True


def test_conflict_with_redemption_auto_increments():
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_redemption("2026-01-15", "10:00:00"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="10:00:00",
                event_type="purchase",
            )
    finally:
        engine.dispose()

    assert time == "10:00:01"
    assert adjusted is True


def test_conflict_with_session_start_auto_increments():
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_session("2026-01-15", "09:00:00"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="09:00:00",
                event_type="purchase",
            )
    finally:
        engine.dispose()

    assert time == "09:00:01"
    assert adjusted is True


def test_conflict_with_closed_session_end_auto_increments():
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_session(
                "2026-01-15", "08:00:00",
                end_date="2026-01-15", end_time="10:00:00",
                status="Closed",
            ))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="10:00:00",
                event_type="session_end",
            )
    finally:
        engine.dispose()

    assert time == "10:00:01"
    assert adjusted is True


# ------------------------------------------------------------------
# Tests — edge cases
# ------------------------------------------------------------------


def test_exclude_id_skips_own_record():
    """When editing an existing purchase, its own timestamp should not conflict."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    own_id = str(uuid4())
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-15", "14:30:00", id=own_id))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30:00",
                exclude_id=own_id,
                event_type="purchase",
            )
    finally:
        engine.dispose()

    assert time == "14:30:00"
    assert adjusted is False


def test_cross_event_conflict():
    """A purchase blocks a new session from the same timestamp."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-03-01", "12:00:00"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-03-01", time_str="12:00:00",
                event_type="session_start",
            )
    finally:
        engine.dispose()

    assert time == "12:00:01"
    assert adjusted is True


def test_multiple_conflicts_skip_ahead():
    """When several consecutive seconds are occupied, find the first free slot."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-02-01", "10:00:00"))
            session.add(_make_redemption("2026-02-01", "10:00:01"))
            session.add(_make_session("2026-02-01", "10:00:02"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-02-01", time_str="10:00:00",
            )
    finally:
        engine.dispose()

    assert time == "10:00:03"
    assert adjusted is True


def test_time_normalization_hhmm():
    """Short time '14:30' is normalized to '14:30:00'."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30",
            )
    finally:
        engine.dispose()

    assert time == "14:30:00"
    assert adjusted is False


def test_different_scope_no_conflict():
    """Purchases on a different site don't cause conflicts."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_purchase("2026-01-15", "14:30:00", site_id="other-site"))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30:00",
            )
    finally:
        engine.dispose()

    assert time == "14:30:00"
    assert adjusted is False


def test_deleted_records_ignored():
    """Soft-deleted purchases should not be treated as conflicts."""
    engine, sf = _session_factory()
    svc = HostedTimestampService()
    try:
        with sf() as session:
            session.add(_make_purchase(
                "2026-01-15", "14:30:00",
                deleted_at="2026-01-16T00:00:00",
            ))
            session.flush()

            date, time, adjusted = svc.ensure_unique_timestamp(
                session,
                workspace_id=W, user_id=U, site_id=S,
                date_str="2026-01-15", time_str="14:30:00",
            )
    finally:
        engine.dispose()

    assert time == "14:30:00"
    assert adjusted is False
