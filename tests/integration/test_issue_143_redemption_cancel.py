from datetime import date, timedelta
from decimal import Decimal

import pytest

from app_facade import AppFacade


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test_issue_143.db"
    facade = AppFacade(str(db_path))
    yield facade
    facade.db.close()


@pytest.fixture
def seeded_pair(app):
    user = app.create_user("Issue143 User")
    site = app.create_site("Issue143 Site", sc_rate=1.0)

    purchase = app.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("500.00"),
        purchase_date=date.today() - timedelta(days=20),
        purchase_time="09:00:00",
        sc_received=Decimal("500.00"),
    )

    r1 = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        fees=Decimal("5.00"),
        redemption_date=date.today() - timedelta(days=10),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
        receipt_date=None,
        processed=False,
    )

    r2 = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        fees=Decimal("2.00"),
        redemption_date=date.today() - timedelta(days=5),
        redemption_time="11:00:00",
        apply_fifo=True,
        more_remaining=True,
        receipt_date=None,
        processed=False,
    )

    return user, site, purchase, r1, r2


def _purchase_remaining(app, purchase_id: int) -> Decimal:
    row = app.db.fetch_one("SELECT remaining_amount FROM purchases WHERE id = ?", (purchase_id,))
    return Decimal(str(row["remaining_amount"]))


def _count_allocations(app, redemption_id: int) -> int:
    row = app.db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM redemption_allocations WHERE redemption_id = ?",
        (redemption_id,),
    )
    return int(row["cnt"])


def _count_realized(app, redemption_id: int) -> int:
    row = app.db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM realized_transactions WHERE redemption_id = ?",
        (redemption_id,),
    )
    return int(row["cnt"])


def test_cancel_redemption_voids_and_rebuilds_downstream(app, seeded_pair):
    _user, _site, purchase, r1, r2 = seeded_pair

    assert _purchase_remaining(app, purchase.id) == Decimal("350.00")
    assert _count_allocations(app, r1.id) > 0
    assert _count_realized(app, r1.id) == 1

    app.cancel_redemption(r1.id, reason="Site rejected payout")

    canceled = app.get_redemption(r1.id)
    assert canceled is not None
    assert canceled.canceled_at is not None
    assert canceled.canceled_reason == "Site rejected payout"

    assert _count_allocations(app, r1.id) == 0
    assert _count_realized(app, r1.id) == 0

    # Only later active redemption should consume basis after rebuild
    assert _purchase_remaining(app, purchase.id) == Decimal("450.00")
    assert _count_allocations(app, r2.id) > 0


def test_uncancel_redemption_restores_accounting_and_supports_undo_redo(app, seeded_pair):
    _user, _site, purchase, r1, _r2 = seeded_pair

    app.cancel_redemption(r1.id, reason="Canceled for test")
    assert _purchase_remaining(app, purchase.id) == Decimal("450.00")

    app.uncancel_redemption(r1.id)
    restored = app.get_redemption(r1.id)
    assert restored.canceled_at is None
    assert restored.canceled_reason is None
    assert _purchase_remaining(app, purchase.id) == Decimal("350.00")

    app.undo_redo_service.undo()
    re_canceled = app.get_redemption(r1.id)
    assert re_canceled.canceled_at is not None

    app.undo_redo_service.redo()
    re_restored = app.get_redemption(r1.id)
    assert re_restored.canceled_at is None


def test_cancel_dismisses_pending_receipt_notification(app, seeded_pair):
    _user, _site, _purchase, r1, _r2 = seeded_pair

    existing = app.notification_service.notification_repo.get_by_composite_key(
        "redemption_pending_receipt",
        str(r1.id),
    )
    if existing:
        app.notification_service.notification_repo.hard_delete(existing.id)

    app.notification_service.create_or_update(
        type="redemption_pending_receipt",
        title="Pending receipt",
        body="Test pending notification",
        subject_id=str(r1.id),
    )
    before = app.notification_service.notification_repo.get_by_composite_key(
        "redemption_pending_receipt",
        str(r1.id),
    )
    assert before is not None
    assert not before.is_deleted

    app.cancel_redemption(r1.id, reason="No payout")

    after = app.notification_service.notification_repo.get_by_composite_key(
        "redemption_pending_receipt",
        str(r1.id),
    )
    assert after is not None
    assert after.is_deleted


def test_bulk_metadata_update_skips_canceled_rows(app, seeded_pair):
    _user, _site, _purchase, r1, r2 = seeded_pair

    app.cancel_redemption(r1.id, reason="No payout")
    target = date.today()
    updated_count = app.bulk_update_redemption_metadata([r1.id, r2.id], receipt_date=target)

    # only active redemption should be updated
    assert updated_count == 1
    assert app.get_redemption(r1.id).receipt_date is None
    assert app.get_redemption(r2.id).receipt_date == target


def test_report_summary_excludes_canceled_redemptions(app, seeded_pair):
    user, site, _purchase, r1, _r2 = seeded_pair

    before = app.report_service.get_user_summary(user.id, site_id=site.id)
    assert before.total_redemptions == Decimal("150.0")

    app.cancel_redemption(r1.id, reason="Accounting correction")

    after = app.report_service.get_user_summary(user.id, site_id=site.id)
    assert after.total_redemptions == Decimal("50.0")


def test_cancel_failure_rolls_back_state(app, seeded_pair, monkeypatch):
    _user, _site, purchase, r1, _r2 = seeded_pair

    def _boom(_allocations, *args, **kwargs):
        raise RuntimeError("forced reversal failure")

    monkeypatch.setattr(app.fifo_service, "reverse_allocation", _boom)

    with pytest.raises(RuntimeError):
        app.cancel_redemption(r1.id, reason="Should rollback")

    # no partial writes
    current = app.get_redemption(r1.id)
    assert current.canceled_at is None
    assert _count_allocations(app, r1.id) > 0
    assert _count_realized(app, r1.id) == 1
    assert _purchase_remaining(app, purchase.id) == Decimal("350.00")


def test_cancel_impact_summary_counts_downstream_activity(app, seeded_pair):
    _user, _site, _purchase, r1, _r2 = seeded_pair

    summary = app.get_redemption_cancel_impact_summary(r1.id)
    assert summary["later_redemptions"] >= 1
    assert "later_purchases" in summary
    assert "later_sessions" in summary


def test_delete_redemption_succeeds_when_allocated_purchase_soft_deleted(app, seeded_pair):
    _user, _site, purchase, r1, _r2 = seeded_pair

    app.purchase_repo.delete(purchase.id)

    app.delete_redemptions_bulk([r1.id])

    row = app.db.fetch_one("SELECT deleted_at FROM redemptions WHERE id = ?", (r1.id,))
    assert row is not None
    assert row["deleted_at"] is not None


def test_cancel_redemption_succeeds_when_allocated_purchase_soft_deleted(app, seeded_pair):
    _user, _site, purchase, r1, _r2 = seeded_pair

    app.purchase_repo.delete(purchase.id)

    app.cancel_redemption(r1.id, reason="Cancel after purchase soft-delete")

    current = app.get_redemption(r1.id)
    assert current is not None
    assert current.canceled_at is not None


def test_cancel_impact_summary_excludes_current_and_prior_activity(app):
    user = app.create_user("Impact User")
    site = app.create_site("Impact Site", sc_rate=1.0)

    app.create_game_session(
        user_id=user.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="09:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )

    redemption = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("25.00"),
        fees=Decimal("1.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="10:00:00",
        apply_fifo=False,
        more_remaining=True,
    )

    summary = app.get_redemption_cancel_impact_summary(redemption.id)
    assert summary["later_purchases"] == 0
    assert summary["later_redemptions"] == 0
    assert summary["later_sessions"] == 0


def test_full_redemption_ignores_soft_deleted_purchases_for_cost_basis(app):
    user = app.create_user("Deleted Purchase User")
    site = app.create_site("Funrize", sc_rate=1.0)

    p1 = app.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("500.00"),
        purchase_date=date.today() - timedelta(days=5),
        purchase_time="08:00:00",
        sc_received=Decimal("500.00"),
    )
    p2 = app.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("500.00"),
        purchase_date=date.today() - timedelta(days=4),
        purchase_time="09:00:00",
        sc_received=Decimal("500.00"),
    )
    app.purchase_repo.delete(p1.id)
    app.purchase_repo.delete(p2.id)

    redemption = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=False,
    )

    realized_row = app.db.fetch_one(
        "SELECT cost_basis, payout, net_pl FROM realized_transactions WHERE redemption_id = ?",
        (redemption.id,),
    )
    assert realized_row is not None
    assert Decimal(str(realized_row["cost_basis"])) == Decimal("0.00")
    assert Decimal(str(realized_row["payout"])) == Decimal("100.00")
    assert Decimal(str(realized_row["net_pl"])) == Decimal("100.00")


def test_rebuild_from_clears_stale_realized_for_deleted_and_canceled_redemptions(app):
    user = app.create_user("Funrize Cleanup User")
    site = app.create_site("Funrize Cleanup", sc_rate=1.0)

    app.create_purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("200.00"),
        purchase_date=date.today() - timedelta(days=5),
        purchase_time="08:00:00",
        sc_received=Decimal("200.00"),
    )

    r1 = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="10:00:00",
        apply_fifo=True,
        more_remaining=True,
    )
    r2 = app.create_redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="11:00:00",
        apply_fifo=True,
        more_remaining=True,
    )

    app.delete_redemption(r1.id)
    app.cancel_redemption(r2.id, reason="test cancel")

    stale = app.db.fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM realized_transactions
        WHERE redemption_id IN (?, ?)
        """,
        (r1.id, r2.id),
    )
    assert int(stale["cnt"]) == 0


def test_cancel_impact_summary_scoped_to_user_and_site_pair_only(app):
    user_a = app.create_user("Scope User A")
    user_b = app.create_user("Scope User B")
    site = app.create_site("Scope Site", sc_rate=1.0)

    target = app.create_redemption(
        user_id=user_a.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        redemption_date=date.today() - timedelta(days=2),
        redemption_time="10:00:00",
        apply_fifo=False,
        more_remaining=True,
    )

    # Later activity on same site but different user must NOT be counted.
    app.create_purchase(
        user_id=user_b.id,
        site_id=site.id,
        amount=Decimal("50.00"),
        purchase_date=date.today() - timedelta(days=1),
        purchase_time="11:00:00",
        sc_received=Decimal("50.00"),
    )
    app.create_redemption(
        user_id=user_b.id,
        site_id=site.id,
        amount=Decimal("25.00"),
        redemption_date=date.today() - timedelta(days=1),
        redemption_time="12:00:00",
        apply_fifo=False,
        more_remaining=True,
    )
    app.create_game_session(
        user_id=user_b.id,
        site_id=site.id,
        game_id=None,
        session_date=date.today() - timedelta(days=1),
        session_time="13:00:00",
        starting_balance=Decimal("100.0"),
        ending_balance=Decimal("100.0"),
        starting_redeemable=Decimal("100.0"),
        ending_redeemable=Decimal("100.0"),
    )

    summary = app.get_redemption_cancel_impact_summary(target.id)
    assert summary["later_purchases"] == 0
    assert summary["later_redemptions"] == 0
    assert summary["later_sessions"] == 0
