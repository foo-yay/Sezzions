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

    app.notification_rules_service.evaluate_redemption_pending_rules()
    before = app.notification_service.notification_repo.get_all()
    assert any(n.type == "redemption_pending_receipt" and str(r1.id) == n.subject_id and not n.is_deleted for n in before)

    app.cancel_redemption(r1.id, reason="No payout")

    after = app.notification_service.notification_repo.get_all()
    assert not any(n.type == "redemption_pending_receipt" and str(r1.id) == n.subject_id and not n.is_deleted for n in after)


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

    def _boom(_allocations):
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
