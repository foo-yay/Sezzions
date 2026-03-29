"""
Phase 1 unit tests for Reports tab metrics (Issue #102)
"""
import pytest
from decimal import Decimal
from datetime import date

from services.report_service import ReportService
from models.redemption import Redemption


def _close_session(game_session_service, session):
    game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="23:59:59",
    )


def _find_row(rows, key_name, key_value):
    for row in rows:
        if getattr(row, key_name) == key_value:
            return row
    return None


def test_kpi_snapshot_and_breakdowns(test_db, user_service, site_service, card_service,
                                     purchase_service, redemption_service, game_session_service,
                                     sample_game, sample_user, sample_site):
    """Snapshot and breakdowns should reconcile for a mixed dataset."""
    # Create second user/site
    user2 = user_service.create_user(name="User Two", email="u2@example.com")
    site2 = site_service.create_site(name="Site Two", url="https://site2.com")

    # Card for cashback (2%)
    card = card_service.create_card(name="Card A", user_id=user2.id, last_four="5678", cashback_rate=2.0)

    # User1 / Site1 data
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 5),
    )
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("40.00"),
        fees=Decimal("1.00"),
        redemption_date=date(2026, 1, 6),
        apply_fifo=False
    )
    session1 = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 7),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("120.00"),
        ending_redeemable=Decimal("20.00")
    )
    _close_session(game_session_service, session1)

    # User2 / Site2 data (cashback auto-calculated)
    purchase_service.create_purchase(
        user_id=user2.id,
        site_id=site2.id,
        amount=Decimal("200.00"),
        purchase_date=date(2026, 1, 8),
        cashback_earned=Decimal("4.00"),
        card_id=card.id,
    )
    redemption_service.create_redemption(
        user_id=user2.id,
        site_id=site2.id,
        amount=Decimal("50.00"),
        fees=Decimal("2.00"),
        redemption_date=date(2026, 1, 9),
        apply_fifo=False
    )
    session2 = game_session_service.create_session(
        user_id=user2.id,
        site_id=site2.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("90.00"),
        ending_redeemable=Decimal("0.00")
    )
    _close_session(game_session_service, session2)

    report_service = ReportService(test_db)
    report_filter = {
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
        "user_ids": None,
        "site_ids": None,
        "include_deleted": False,
    }

    snapshot = report_service.get_kpi_snapshot(report_filter)
    user_rows = report_service.get_user_breakdown(report_filter)
    site_rows = report_service.get_site_breakdown(report_filter)

    # Snapshot assertions
    assert snapshot.session_net_pl == Decimal("20.00")
    assert snapshot.total_cashback == Decimal("4.00")
    assert snapshot.session_pl_plus_cashback == Decimal("24.00")
    assert snapshot.total_purchases == Decimal("300.00")
    assert snapshot.total_redemptions == Decimal("90.00")
    assert snapshot.total_fees == Decimal("3.00")
    assert snapshot.outstanding_balance == Decimal("300.00")

    # Breakdown totals reconcile
    assert sum(r.session_net_pl for r in user_rows) == snapshot.session_net_pl
    assert sum(r.cashback for r in user_rows) == snapshot.total_cashback
    assert sum(r.purchases for r in user_rows) == snapshot.total_purchases

    assert sum(r.session_net_pl for r in site_rows) == snapshot.session_net_pl
    assert sum(r.cashback for r in site_rows) == snapshot.total_cashback
    assert sum(r.redemptions for r in site_rows) == snapshot.total_redemptions


def test_kpi_snapshot_site_filter(test_db, user_service, site_service, purchase_service, redemption_service, game_session_service, sample_game):
    """Filtering by site should restrict snapshot and breakdowns."""
    user = user_service.create_user(name="User Filter", email="uf@example.com")
    site1 = site_service.create_site(name="Site Filter", url="https://sf.com")
    site2 = site_service.create_site(name="Site Other", url="https://so.com")

    purchase_service.create_purchase(
        user_id=user.id,
        site_id=site1.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 5),
    )
    purchase_service.create_purchase(
        user_id=user.id,
        site_id=site2.id,
        amount=Decimal("200.00"),
        purchase_date=date(2026, 1, 6),
    )

    report_service = ReportService(test_db)
    report_filter = {
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
        "user_ids": None,
        "site_ids": [site1.id],
        "include_deleted": False,
    }

    snapshot = report_service.get_kpi_snapshot(report_filter)
    site_rows = report_service.get_site_breakdown(report_filter)

    assert snapshot.total_purchases == Decimal("100.00")
    assert len(site_rows) == 1
    assert site_rows[0].site_id == site1.id


def test_kpi_snapshot_no_data(test_db):
    """No data in range should return zeros and empty breakdowns."""
    report_service = ReportService(test_db)
    report_filter = {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 1, 31),
        "user_ids": None,
        "site_ids": None,
        "include_deleted": False,
    }

    snapshot = report_service.get_kpi_snapshot(report_filter)
    user_rows = report_service.get_user_breakdown(report_filter)
    site_rows = report_service.get_site_breakdown(report_filter)

    assert snapshot.total_purchases == Decimal("0.00")
    assert snapshot.total_redemptions == Decimal("0.00")
    assert snapshot.session_net_pl == Decimal("0.00")
    assert user_rows == []
    assert site_rows == []


def test_kpi_snapshot_excludes_soft_deleted(test_db, user_service, site_service, purchase_repo, redemption_repo, game_session_service, sample_game):
    """Soft-deleted activity should not appear in snapshot or breakdowns."""
    user = user_service.create_user(name="User Deleted", email="ud@example.com")
    site = site_service.create_site(name="Site Deleted", url="https://sd.com")

    # Purchase
    from models.purchase import Purchase
    purchase = purchase_repo.create(Purchase(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 5),
    ))

    # Redemption
    redemption = redemption_repo.create(Redemption(
        user_id=user.id,
        site_id=site.id,
        amount=Decimal("20.00"),
        fees=Decimal("1.00"),
        redemption_date=date(2026, 1, 6),
    ))

    # Session
    session = game_session_service.create_session(
        user_id=user.id,
        site_id=site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 7),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("120.00"),
        ending_redeemable=Decimal("20.00")
    )
    _close_session(game_session_service, session)

    # Soft-delete all
    purchase_repo.delete(purchase.id)
    redemption_repo.delete(redemption.id)
    game_session_service.session_repo.delete(session.id)

    report_service = ReportService(test_db)
    report_filter = {
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 1, 31),
        "user_ids": None,
        "site_ids": None,
        "include_deleted": False,
    }

    snapshot = report_service.get_kpi_snapshot(report_filter)
    assert snapshot.total_purchases == Decimal("0.00")
    assert snapshot.total_redemptions == Decimal("0.00")
    assert snapshot.session_net_pl == Decimal("0.00")
