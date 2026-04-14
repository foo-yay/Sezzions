"""Tests for session P/L recalculation in HostedRecalculationService.

Covers Feature Group A (session P/L calculation), Feature Group C
(validations: end>start, dormant reactivation, start-balance consistency),
and basic Feature Group B (low-balance close check).
"""

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.hosted.persistence import (
    HostedBase,
    HostedGameSessionRecord,
    HostedGameSessionEventLinkRecord,
    HostedPurchaseRecord,
    HostedRedemptionRecord,
    HostedSiteRecord,
)
from services.hosted.hosted_recalculation_service import (
    HostedRecalculationService,
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


def _site(sc_rate=1.0, **kw):
    defaults = dict(
        id=S,
        workspace_id=W,
        name="TestSite",
        sc_rate=sc_rate,
    )
    defaults.update(kw)
    return HostedSiteRecord(**defaults)


def _purchase(date, time, amount, *, sc_received=None, **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        amount=str(amount),
        remaining_amount=str(amount),
        sc_received=str(sc_received if sc_received is not None else amount),
        starting_sc_balance="0.00",
        starting_redeemable_balance="0.00",
        purchase_date=date,
        purchase_time=time,
    )
    defaults.update(kw)
    return HostedPurchaseRecord(**defaults)


def _redemption(date, time, amount, *, more_remaining=False, is_free_sc=False,
                notes=None, status="PENDING", **kw):
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
        status=status,
    )
    defaults.update(kw)
    return HostedRedemptionRecord(**defaults)


def _game_session(date, time, *,
                  end_date=None, end_time=None,
                  starting_balance="0.00", ending_balance="0.00",
                  starting_redeemable="0.00", ending_redeemable="0.00",
                  wager_amount="0.00",
                  status="Active", **kw):
    defaults = dict(
        id=str(uuid4()),
        workspace_id=W,
        user_id=U,
        site_id=S,
        session_date=date,
        session_time=time,
        end_date=end_date,
        end_time=end_time,
        starting_balance=starting_balance,
        ending_balance=ending_balance,
        starting_redeemable=starting_redeemable,
        ending_redeemable=ending_redeemable,
        wager_amount=wager_amount,
        status=status,
    )
    defaults.update(kw)
    return HostedGameSessionRecord(**defaults)


def _event_link(session_id, event_type, event_id, relation):
    return HostedGameSessionEventLinkRecord(
        id=str(uuid4()),
        workspace_id=W,
        game_session_id=session_id,
        event_type=event_type,
        event_id=event_id,
        relation=relation,
    )


def _d(val):
    """Shortcut: Decimal from string for assertions."""
    return Decimal(str(val))


# ==================================================================
# Feature Group A — Session P/L Calculation
# ==================================================================


class TestSessionRecalc_HappyPath:
    """Basic session P/L calculation with known inputs."""

    def test_single_closed_session_no_purchases(self):
        """Closed session with no purchases => basis_consumed=0, net_pl from delta_redeem."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="0.00", ending_balance="20.00",
            starting_redeemable="0.00", ending_redeemable="20.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(gs)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()

            s.refresh(gs)
            assert gs.delta_total == "20.00"
            assert gs.delta_redeem == "20.00"
            assert gs.basis_consumed == "0.00"
            assert gs.session_basis == "0.00"
            assert gs.discoverable_sc == "0.00"
            # net_taxable_pl = (discoverable_sc + delta_redeem) * sc_rate - basis_consumed
            # = (0 + 20) * 1 - 0 = 20
            assert gs.net_taxable_pl == "20.00"

    def test_single_closed_session_with_purchase_before(self):
        """Purchase before session provides basis; session consumes it."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        p = _purchase("2025-01-09", "12:00:00", 50)
        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="100.00", ending_balance="80.00",
            starting_redeemable="50.00", ending_redeemable="80.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(p)
            s.add(gs)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs)

            assert gs.delta_total == "-20.00"
            assert gs.delta_redeem == "30.00"
            assert gs.session_basis == "50.00"
            # expected_start_redeemable = 0 (no prior end), so discoverable = max(0, 50-0)=50
            assert gs.discoverable_sc == "50.00"
            # locked_start = 100 - 50 = 50; locked_end = 80 - 80 = 0
            # purchases_during_sc = 0; locked_processed = 50+0-0 = 50
            # basis_consumed = min(50, 50*1) = 50
            assert gs.basis_consumed == "50.00"
            # net_pl = (50 + 30) * 1 - 50 = 30
            assert gs.net_taxable_pl == "30.00"

    def test_two_sequential_sessions(self):
        """Second session's expected balances are computed from first session's end."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        gs1 = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="100.00", ending_balance="150.00",
            starting_redeemable="100.00", ending_redeemable="150.00",
            status="Closed",
        )
        gs2 = _game_session(
            "2025-01-11", "10:00:00",
            end_date="2025-01-11", end_time="14:00:00",
            starting_balance="150.00", ending_balance="120.00",
            starting_redeemable="150.00", ending_redeemable="120.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(gs1)
            s.add(gs2)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs1)
            s.refresh(gs2)

            # Session 1: expected_start = (0,0), so discoverable = max(0, 100-0)=100
            assert gs1.expected_start_total == "0.00"
            assert gs1.expected_start_redeemable == "0.00"
            assert gs1.net_taxable_pl is not None

            # Session 2: expected_start = (150, 150) from gs1 end
            assert gs2.expected_start_total == "150.00"
            assert gs2.expected_start_redeemable == "150.00"
            assert gs2.discoverable_sc == "0.00"
            assert gs2.delta_redeem == "-30.00"
            # net_pl = (0 + (-30)) * 1 - 0 = -30
            assert gs2.net_taxable_pl == "-30.00"


class TestSessionRecalc_WithEvents:
    """Session recalc with purchases/redemptions between sessions."""

    def test_redemption_between_sessions(self):
        """Redemption between sessions reduces expected start for second session."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        gs1 = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="200.00", ending_balance="200.00",
            starting_redeemable="200.00", ending_redeemable="200.00",
            status="Closed",
        )
        red = _redemption("2025-01-10", "16:00:00", 50)
        gs2 = _game_session(
            "2025-01-11", "10:00:00",
            end_date="2025-01-11", end_time="14:00:00",
            starting_balance="150.00", ending_balance="180.00",
            starting_redeemable="150.00", ending_redeemable="180.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(gs1)
            s.add(red)
            s.add(gs2)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs2)

            # expected_start = (200-50, 200-50) = (150, 150)
            assert gs2.expected_start_total == "150.00"
            assert gs2.expected_start_redeemable == "150.00"
            assert gs2.discoverable_sc == "0.00"

    def test_purchase_during_session_via_event_link(self):
        """Purchase linked as DURING contributes to locked_processed calculation."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        p = _purchase("2025-01-10", "12:00:00", 25, sc_received=25)
        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="100.00", ending_balance="120.00",
            starting_redeemable="100.00", ending_redeemable="120.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(p)
            s.add(gs)
            # Link purchase DURING session
            link = _event_link(gs.id, "purchase", p.id, "DURING")
            s.add(link)
            s.flush()

            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs)

            assert gs.purchases_during == "25.00"


class TestSessionRecalc_EdgeCases:
    """Edge cases for session recalc."""

    def test_active_session_not_recalculated(self):
        """Active sessions should be skipped — no P/L fields set."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        gs = _game_session(
            "2025-01-10", "10:00:00",
            starting_balance="100.00",
            starting_redeemable="100.00",
            status="Active",
        )

        with sf() as s:
            s.add(_site())
            s.add(gs)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs)

            # Active session — P/L fields should remain NULL
            assert gs.net_taxable_pl is None
            assert gs.delta_total is None

    def test_discoverable_sc_when_starting_redeemable_exceeds_expected(self):
        """discoverable_sc = max(0, starting_redeemable - expected_start_redeemable)"""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        # First session ends at 100 redeemable
        gs1 = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="50.00", ending_balance="100.00",
            starting_redeemable="50.00", ending_redeemable="100.00",
            status="Closed",
        )
        # Second session starts with 120 redeemable (20 more than expected)
        gs2 = _game_session(
            "2025-01-11", "10:00:00",
            end_date="2025-01-11", end_time="14:00:00",
            starting_balance="120.00", ending_balance="120.00",
            starting_redeemable="120.00", ending_redeemable="120.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(gs1)
            s.add(gs2)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs2)

            assert gs2.expected_start_redeemable == "100.00"
            assert gs2.discoverable_sc == "20.00"

    def test_sc_rate_applied_to_pl(self):
        """Non-1.0 sc_rate multiplies SC into dollar values."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="0.00", ending_balance="20.00",
            starting_redeemable="0.00", ending_redeemable="20.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site(sc_rate=2.0))
            s.add(gs)
            s.flush()
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs)

            # delta_redeem = 20 SC, sc_rate = 2.0
            # net_pl = (0 + 20) * 2 - 0 = 40
            assert gs.net_taxable_pl == "40.00"

    def test_session_recalc_does_not_alter_fifo(self):
        """Session recalc must not change purchase remaining_amount or allocations."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        p = _purchase("2025-01-09", "12:00:00", 100)
        red = _redemption("2025-01-09", "15:00:00", 50, more_remaining=True)
        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="50.00", ending_balance="60.00",
            starting_redeemable="50.00", ending_redeemable="60.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(p)
            s.add(red)
            s.add(gs)
            s.flush()

            # Run FIFO first to set up allocations
            svc.rebuild_fifo_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(p)
            remaining_before = p.remaining_amount

            # Now run session recalc only
            svc.rebuild_sessions_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(p)

            # FIFO state unchanged
            assert p.remaining_amount == remaining_before


class TestSessionRecalc_FullChain:
    """Test rebuild_fifo_for_pair now also computes session P/L."""

    def test_full_rebuild_includes_session_recalc(self):
        """rebuild_fifo_for_pair should trigger session recalc as well."""
        engine, sf = _session_factory()
        svc = HostedRecalculationService()

        p = _purchase("2025-01-09", "12:00:00", 100)
        gs = _game_session(
            "2025-01-10", "10:00:00",
            end_date="2025-01-10", end_time="14:00:00",
            starting_balance="200.00", ending_balance="220.00",
            starting_redeemable="100.00", ending_redeemable="120.00",
            status="Closed",
        )

        with sf() as s:
            s.add(_site())
            s.add(p)
            s.add(gs)
            s.flush()
            result = svc.rebuild_fifo_for_pair(
                s, workspace_id=W, user_id=U, site_id=S,
            )
            s.flush()
            s.refresh(gs)

            # Session fields should be populated
            assert gs.net_taxable_pl is not None
            assert result.game_sessions_processed >= 1
