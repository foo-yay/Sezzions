"""Tests for HostedEventLinkService — temporal event classification."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.persistence import (
    HostedBase,
    HostedGameSessionEventLinkRecord,
    HostedGameSessionRecord,
    HostedPurchaseRecord,
    HostedRedemptionRecord,
)
from services.hosted.hosted_event_link_service import (
    HostedEventLinkService,
    _classify_timestamp,
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


def _purchase(date, time, **kw):
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


def _redemption(date, time, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount="50.00",
        redemption_date=date,
        redemption_time=time,
        status="PENDING",
    )
    defaults.update(kw)
    return HostedRedemptionRecord(**defaults)


def _dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------
# Tests — _classify_timestamp (pure function)
# ------------------------------------------------------------------


def test_during_closed_session():
    """Event between start (inclusive) and end (exclusive) → DURING."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 10:30:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    assert result == "DURING"


def test_during_at_exact_start():
    """Event at exactly session start → DURING (start inclusive)."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 10:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    assert result == "DURING"


def test_not_during_at_exact_end():
    """Event at exactly session end → NOT DURING (end exclusive)."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 11:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="redemption",
    )
    # Should be AFTER (for redemptions on closed sessions)
    assert result == "AFTER"


def test_during_active_session():
    """Active (open) session — events after start are DURING if no next session."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 14:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=None,
        prev_end=None,
        next_start=None,
        is_active=True,
        link_type="purchase",
    )
    assert result == "DURING"


def test_before_first_session():
    """Event before first session with no previous session → BEFORE."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 08:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    assert result == "BEFORE"


def test_before_between_sessions():
    """Event between previous session end and current start → BEFORE current."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 09:30:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=_dt("2026-01-15 09:00:00"),
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    assert result == "BEFORE"


def test_after_closed_session_redemption():
    """Redemption after closed session end → AFTER."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 12:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="redemption",
    )
    assert result == "AFTER"


def test_after_not_for_purchases():
    """Purchases after a closed session → None (AFTER only for redemptions)."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 12:00:00"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=None,
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    assert result is None


def test_no_link_between_prev_end_and_current_start():
    """Event right at prev session end time but not in BEFORE window → None."""
    result = _classify_timestamp(
        event_dt=_dt("2026-01-15 08:59:59"),
        session_start=_dt("2026-01-15 10:00:00"),
        session_end=_dt("2026-01-15 11:00:00"),
        prev_end=_dt("2026-01-15 09:00:00"),
        next_start=None,
        is_active=False,
        link_type="purchase",
    )
    # 08:59:59 < 09:00:00 (prev_end), so not in BEFORE window for this session
    assert result is None


# ------------------------------------------------------------------
# Tests — rebuild_links_for_pair (integration)
# ------------------------------------------------------------------


def test_rebuild_links_basic():
    """Rebuild produces correct BEFORE/DURING/AFTER links."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            gs = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="12:00:00",
                status="Closed",
            )
            p_before = _purchase("2026-01-15", "09:00:00")
            p_during = _purchase("2026-01-15", "10:30:00")
            r_after = _redemption("2026-01-15", "13:00:00")
            session.add_all([gs, p_before, p_during, r_after])
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            link_dict = {(l.event_type, l.event_id, l.relation) for l in links}

            assert ("purchase", p_before.id, "BEFORE") in link_dict
            assert ("purchase", p_during.id, "DURING") in link_dict
            assert ("redemption", r_after.id, "AFTER") in link_dict
    finally:
        engine.dispose()


def test_rebuild_links_active_session():
    """Active session links events after start as DURING."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            gs = _game_session("2026-01-15", "10:00:00")  # Active
            p = _purchase("2026-01-15", "14:00:00")
            session.add_all([gs, p])
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            assert len(links) == 1
            assert links[0].relation == "DURING"
    finally:
        engine.dispose()


def test_rebuild_links_multiple_sessions():
    """Events classified correctly across multiple closed sessions."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            gs1 = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="11:00:00",
                status="Closed",
            )
            gs2 = _game_session(
                "2026-01-15", "12:00:00",
                end_date="2026-01-15", end_time="14:00:00",
                status="Closed",
            )
            # Between sessions → BEFORE gs2
            p = _purchase("2026-01-15", "11:30:00")
            # During gs2
            r = _redemption("2026-01-15", "13:00:00")
            session.add_all([gs1, gs2, p, r])
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            link_dict = {(l.game_session_id, l.event_type, l.event_id, l.relation) for l in links}

            # p (11:30) is AFTER gs1 end (11:00) but BEFORE gs2 start (12:00)
            # Since prev_end (11:00) <= 11:30 < start (12:00) → BEFORE gs2
            assert (gs2.id, "purchase", p.id, "BEFORE") in link_dict
            # r (13:00) is DURING gs2
            assert (gs2.id, "redemption", r.id, "DURING") in link_dict
    finally:
        engine.dispose()


def test_rebuild_idempotent():
    """Running rebuild twice produces the same links (no duplicates)."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            gs = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="12:00:00",
                status="Closed",
            )
            p = _purchase("2026-01-15", "09:00:00")
            session.add_all([gs, p])
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            assert len(links) == 1
    finally:
        engine.dispose()


def test_rebuild_no_sessions_no_links():
    """No game sessions → no links created."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            p = _purchase("2026-01-15", "09:00:00")
            session.add(p)
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            assert len(links) == 0
    finally:
        engine.dispose()


def test_canceled_redemptions_excluded():
    """Canceled redemptions should not generate event links."""
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            gs = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="12:00:00",
                status="Closed",
            )
            r = _redemption(
                "2026-01-15", "10:30:00",
                status="CANCELED",
            )
            session.add_all([gs, r])
            session.flush()

            svc.rebuild_links_for_pair(
                session, workspace_id=W, user_id=U, site_id=S,
            )
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            assert len(links) == 0
    finally:
        engine.dispose()


# ------------------------------------------------------------------
# Tests — rebuild_links_all
# ------------------------------------------------------------------


def test_rebuild_all_processes_multiple_pairs():
    engine, sf = _session_factory()
    svc = HostedEventLinkService()
    try:
        with sf() as session:
            # Pair 1
            gs1 = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="12:00:00",
                status="Closed",
            )
            p1 = _purchase("2026-01-15", "09:00:00")
            # Pair 2
            gs2 = _game_session(
                "2026-01-15", "10:00:00",
                end_date="2026-01-15", end_time="12:00:00",
                status="Closed",
                user_id="user-2", site_id="site-2",
            )
            p2 = _purchase("2026-01-15", "09:00:00", user_id="user-2", site_id="site-2")
            session.add_all([gs1, p1, gs2, p2])
            session.flush()

            svc.rebuild_links_all(session, workspace_id=W)
            session.flush()

            links = session.query(HostedGameSessionEventLinkRecord).all()
            assert len(links) == 2  # One link per pair
    finally:
        engine.dispose()
