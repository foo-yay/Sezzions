from datetime import date, timedelta
from decimal import Decimal
import pytest

from app_facade import AppFacade


def _seed_basic_pair(facade: AppFacade):
    user = facade.create_user("Issue145 User")
    site = facade.create_site("Issue145 Site", "https://example.com", sc_rate=1.0)
    facade.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        sc_received=Decimal("100.00"),
        starting_sc_balance=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
        purchase_time="09:00:00",
    )
    redemption = facade.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("40.00"),
        redemption_date=date(2026, 1, 2),
        redemption_time="10:00:00",
        apply_fifo=False,
        more_remaining=True,
    )
    return user, site, redemption


def test_cancel_without_active_session_applies_immediately_and_uncancel_reverts_unrealized():
    facade = AppFacade(":memory:")
    try:
        user, site, redemption = _seed_basic_pair(facade)

        before = facade.get_unrealized_position(site.id, user.id)
        assert before is not None
        before_total = before.total_sc

        canceled = facade.cancel_redemption(redemption.id, reason="Issue145 immediate cancel")
        assert canceled.redemption_status == "CANCELED"
        assert canceled.cancel_effective_date is not None
        assert canceled.cancellation_adjustment_id is not None

        after_cancel = facade.get_unrealized_position(site.id, user.id)
        assert after_cancel is not None
        assert after_cancel.total_sc > before_total

        uncanceled = facade.uncancel_redemption(redemption.id)
        assert uncanceled.redemption_status == "REDEEMED"
        assert uncanceled.cancel_effective_date is None
        assert uncanceled.cancellation_adjustment_id is None

        after_uncancel = facade.get_unrealized_position(site.id, user.id)
        assert after_uncancel is not None
        assert after_uncancel.total_sc == before_total
    finally:
        facade.db.close()


def test_cancel_during_active_session_is_pending_then_auto_finalizes_on_close():
    facade = AppFacade(":memory:")
    try:
        user, site, redemption = _seed_basic_pair(facade)

        session = facade.create_game_session(
            user_id=user.id,
            site_id=site.id,
            game_id=None,
            game_type_id=None,
            session_date=date(2026, 2, 19),
            session_time="11:00:00",
            starting_balance=Decimal("60.00"),
            ending_balance=Decimal("60.00"),
            starting_redeemable=Decimal("60.00"),
            ending_redeemable=Decimal("60.00"),
            notes="active",
        )

        pending = facade.cancel_redemption(redemption.id)
        assert pending.redemption_status == "PENDING_CANCELLATION"
        assert pending.cancellation_adjustment_id is None

        closed = facade.update_game_session(
            session.id,
            status="Closed",
            end_date=date(2026, 2, 19),
            end_time="12:00:00",
            ending_balance=Decimal("60.00"),
            ending_redeemable=Decimal("60.00"),
        )
        assert closed.status == "Closed"

        finalized = facade.get_redemption(redemption.id)
        assert finalized is not None
        assert finalized.redemption_status == "CANCELED"
        assert finalized.cancellation_adjustment_id is not None
        assert finalized.cancel_effective_date == date(2026, 2, 19)

        adj = facade.adjustment_service.adjustment_repo.get_by_id(finalized.cancellation_adjustment_id)
        assert adj is not None
        assert Decimal(str(adj.checkpoint_total_sc)) == Decimal("100.00")
        assert Decimal(str(adj.checkpoint_redeemable_sc)) == Decimal("100.00")

        next_expected_total, next_expected_redeemable = facade.compute_expected_balances(
            user.id,
            site.id,
            date(2026, 2, 19),
            "12:00:01",
        )
        assert next_expected_total == Decimal("100.00")
        assert next_expected_redeemable == Decimal("100.00")
    finally:
        facade.db.close()


def test_uncancel_during_active_session_requires_pending_uncancel_then_finalizes_on_close():
    facade = AppFacade(":memory:")
    try:
        user, site, redemption = _seed_basic_pair(facade)

        canceled = facade.cancel_redemption(redemption.id)
        assert canceled.redemption_status == "CANCELED"

        active = facade.create_game_session(
            user_id=user.id,
            site_id=site.id,
            game_id=None,
            game_type_id=None,
            session_date=date(2026, 2, 20),
            session_time="13:00:00",
            starting_balance=Decimal("60.00"),
            ending_balance=Decimal("60.00"),
            starting_redeemable=Decimal("60.00"),
            ending_redeemable=Decimal("60.00"),
            notes="active",
        )

        pending_uncancel = facade.uncancel_redemption(redemption.id)
        assert pending_uncancel.redemption_status == "PENDING_UNCANCEL"
        assert pending_uncancel.cancellation_adjustment_id is not None

        facade.update_game_session(
            active.id,
            status="Closed",
            end_date=date(2026, 2, 20),
            end_time="14:00:00",
            ending_balance=Decimal("60.00"),
            ending_redeemable=Decimal("60.00"),
        )

        finalized = facade.get_redemption(redemption.id)
        assert finalized is not None
        assert finalized.redemption_status == "REDEEMED"
        assert finalized.cancel_effective_date is None
        assert finalized.cancellation_adjustment_id is None
    finally:
        facade.db.close()


def test_cancel_and_uncancel_are_audited_and_undoable():
    facade = AppFacade(":memory:")
    try:
        _user, _site, redemption = _seed_basic_pair(facade)

        canceled = facade.cancel_redemption(redemption.id, reason="audit")
        assert canceled.redemption_status == "CANCELED"

        entries = facade.audit_service.get_audit_log(
            table_name="redemptions",
            action="UPDATE",
            record_id=redemption.id,
            limit=20,
        )
        assert any((e.get("new_data") or {}).get("redemption_status") == "CANCELED" for e in entries)
        assert facade.undo_redo_service.can_undo()

        facade.undo_redo_service.undo()
        after_undo = facade.get_redemption(redemption.id)
        assert after_undo is not None
        assert after_undo.redemption_status == "REDEEMED"

        uncanceled = facade.uncancel_redemption(redemption.id)
        assert uncanceled.redemption_status == "REDEEMED"

        # Re-cancel then uncancel for explicit uncancel audit
        facade.cancel_redemption(redemption.id, reason="audit2")
        facade.uncancel_redemption(redemption.id)
        entries2 = facade.audit_service.get_audit_log(
            table_name="redemptions",
            action="UPDATE",
            record_id=redemption.id,
            limit=30,
        )
        assert any((e.get("new_data") or {}).get("redemption_status") == "REDEEMED" for e in entries2)
    finally:
        facade.db.close()


def test_cancel_allows_undo_prune_inside_existing_transaction():
    facade = AppFacade(":memory:")
    try:
        _user, _site, redemption = _seed_basic_pair(facade)

        facade.undo_redo_service.set_max_undo_operations(1)
        facade.undo_redo_service.push_operation(
            group_id="seed-op",
            description="seed",
            timestamp="2026-02-20T00:00:00",
        )

        canceled = facade.cancel_redemption(redemption.id, reason="trigger prune")
        assert canceled.redemption_status in {"CANCELED", "PENDING_CANCELLATION"}
    finally:
        facade.db.close()


def test_undo_uncancel_restores_reinstatement_adjustment_state():
    facade = AppFacade(":memory:")
    try:
        _user, _site, redemption = _seed_basic_pair(facade)

        canceled = facade.cancel_redemption(redemption.id, reason="undo-adjustment-check")
        assert canceled.redemption_status == "CANCELED"
        assert canceled.cancellation_adjustment_id is not None

        adjustment_id = canceled.cancellation_adjustment_id
        before_uncancel = facade.adjustment_service.adjustment_repo.get_by_id(adjustment_id)
        assert before_uncancel is not None
        assert before_uncancel.deleted_at is None

        uncanceled = facade.uncancel_redemption(redemption.id)
        assert uncanceled.redemption_status == "REDEEMED"

        after_uncancel = facade.adjustment_service.adjustment_repo.get_by_id(adjustment_id)
        assert after_uncancel is not None
        assert after_uncancel.deleted_at is not None

        facade.undo_redo_service.undo()

        after_undo = facade.adjustment_service.adjustment_repo.get_by_id(adjustment_id)
        assert after_undo is not None
        assert after_undo.deleted_at is None
    finally:
        facade.db.close()


def test_uncancel_is_blocked_when_downstream_activity_exists_after_cancel_effective_time():
    facade = AppFacade(":memory:")
    try:
        user, site, redemption = _seed_basic_pair(facade)

        canceled = facade.cancel_redemption(redemption.id, reason="downstream-guard")
        assert canceled.redemption_status == "CANCELED"
        assert canceled.cancel_effective_date is not None

        later_date = canceled.cancel_effective_date + timedelta(days=1)
        session = facade.create_game_session(
            user_id=user.id,
            site_id=site.id,
            game_id=None,
            game_type_id=None,
            session_date=later_date,
            session_time="09:00:00",
            starting_balance=Decimal("100.00"),
            ending_balance=Decimal("120.00"),
            starting_redeemable=Decimal("100.00"),
            ending_redeemable=Decimal("120.00"),
            notes="downstream session",
        )
        facade.update_game_session(
            session.id,
            status="Closed",
            end_date=later_date,
            end_time="10:00:00",
            ending_balance=Decimal("120.00"),
            ending_redeemable=Decimal("120.00"),
        )

        facade.create_redemption(
            user_id=user.id,
            site_id=site.id,
            amount=Decimal("30.00"),
            redemption_date=later_date,
            redemption_time="11:00:00",
            apply_fifo=False,
            more_remaining=True,
        )

        with pytest.raises(ValueError, match="Cannot uncancel redemption because downstream activity exists"):
            facade.uncancel_redemption(redemption.id)

        current = facade.get_redemption(redemption.id)
        assert current is not None
        assert current.redemption_status == "CANCELED"
    finally:
        facade.db.close()
