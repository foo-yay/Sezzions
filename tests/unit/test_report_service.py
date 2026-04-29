"""
Unit tests for ReportService
"""
import pytest
from decimal import Decimal
from datetime import date
from services.report_service import ReportService


def test_get_user_summary(test_db, sample_user, sample_site, purchase_repo, redemption_service, game_session_service, sample_game):
    """Test getting user summary"""
    from models.purchase import Purchase
    
    # Create test data
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=False
    )
    
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("120.00"),
        ending_redeemable=Decimal("20.00")
    )
    game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=date(2026, 1, 10),
        end_time="23:59:59",
    )
    
    # Get summary
    report_service = ReportService(test_db)
    summary = report_service.get_user_summary(sample_user.id)
    
    assert summary.user_id == sample_user.id
    assert summary.total_purchases == Decimal("100.00")
    assert summary.total_redemptions == Decimal("50.00")
    assert summary.total_sessions == 1
    assert summary.total_profit_loss == Decimal("20.00")


def test_get_user_summary_with_site_filter(test_db, sample_user, sample_site, purchase_repo):
    """Test getting user summary filtered by site"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    report_service = ReportService(test_db)
    summary = report_service.get_user_summary(sample_user.id, site_id=sample_site.id)
    
    assert summary.total_purchases == Decimal("100.00")


def test_get_user_summary_not_found(test_db):
    """Test getting summary for non-existent user"""
    report_service = ReportService(test_db)
    
    with pytest.raises(ValueError, match="User .* not found"):
        report_service.get_user_summary(99999)


def test_get_site_summary(test_db, sample_user, sample_site, purchase_repo, redemption_service):
    """Test getting site summary"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("200.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("75.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=False
    )
    
    report_service = ReportService(test_db)
    summary = report_service.get_site_summary(sample_site.id)
    
    assert summary.site_id == sample_site.id
    assert summary.total_purchases == Decimal("200.00")
    assert summary.total_redemptions == Decimal("75.00")


def test_get_all_user_summaries(test_db, sample_user, sample_site, purchase_repo):
    """Test getting all user summaries"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    report_service = ReportService(test_db)
    summaries = report_service.get_all_user_summaries()
    
    assert len(summaries) >= 1
    assert any(s.user_id == sample_user.id for s in summaries)


def test_get_all_site_summaries(test_db, sample_user, sample_site, purchase_repo):
    """Test getting all site summaries"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    report_service = ReportService(test_db)
    summaries = report_service.get_all_site_summaries()
    
    assert len(summaries) >= 1
    assert any(s.site_id == sample_site.id for s in summaries)


def test_get_tax_report(test_db, sample_user, sample_site, purchase_repo, redemption_service):
    """Test generating tax report"""
    from models.purchase import Purchase
    
    # Create purchase
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    # Create redemption with FIFO
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("80.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=True,
        more_remaining=True
    )
    
    report_service = ReportService(test_db)
    tax_report = report_service.get_tax_report(sample_user.id)
    
    assert tax_report["total_cost_basis"] == Decimal("80.00")
    assert tax_report["total_proceeds"] == Decimal("80.00")
    assert tax_report["total_gain_loss"] == Decimal("0.00")


def test_get_tax_report_with_filters(test_db, sample_user, sample_site, purchase_repo, redemption_service):
    """Test tax report with date filters"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        redemption_date=date(2026, 1, 5),
        apply_fifo=True,
        more_remaining=True
    )
    
    report_service = ReportService(test_db)
    tax_report = report_service.get_tax_report(
        sample_user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    
    assert tax_report["total_cost_basis"] == Decimal("50.00")


def test_get_tax_report_uses_local_redemption_dates(
    monkeypatch,
    test_db,
    sample_user,
    sample_site,
    purchase_repo,
    redemption_service,
):
    """Tax report filters should respect local day boundaries."""
    from models.purchase import Purchase
    from tools.timezone_utils import local_date_time_to_utc

    monkeypatch.setattr(
        "repositories.redemption_repository.get_accounting_timezone_name",
        lambda: "America/New_York",
    )
    monkeypatch.setattr(
        "services.report_service.get_configured_timezone_name",
        lambda: "America/New_York",
    )

    purchase_repo.create(
        Purchase(
            user_id=sample_user.id,
            site_id=sample_site.id,
            amount=Decimal("100.00"),
            purchase_date=date(2026, 1, 1),
        )
    )

    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("80.00"),
        redemption_date=date(2026, 1, 1),
        redemption_time="23:30:00",
        apply_fifo=True,
        more_remaining=True,
    )

    utc_date, _ = local_date_time_to_utc(
        date(2026, 1, 1),
        "23:30:00",
        "America/New_York",
    )
    test_db.execute(
        "UPDATE realized_transactions SET redemption_date = ? WHERE redemption_id = ?",
        (utc_date, redemption.id),
    )

    report_service = ReportService(test_db)
    tax_report = report_service.get_tax_report(
        sample_user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
    )

    assert tax_report["total_cost_basis"] == Decimal("80.00")
    assert tax_report["total_proceeds"] == Decimal("80.00")


def test_get_session_profit_loss_report(test_db, sample_user, sample_site, sample_game, game_session_service):
    """Test session P/L report"""
    # Create winning session
    win = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("150.00"),
        ending_redeemable=Decimal("50.00")
    )
    game_session_service.update_session(
        win.id,
        status="Closed",
        end_date=win.session_date,
        end_time="23:59:59",
    )
    
    # Create losing session
    loss = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 11),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("50.00"),
        ending_balance=Decimal("80.00"),
        ending_redeemable=Decimal("30.00")
    )
    game_session_service.update_session(
        loss.id,
        status="Closed",
        end_date=loss.session_date,
        end_time="23:59:59",
    )
    
    report_service = ReportService(test_db)
    pl_report = report_service.get_session_profit_loss_report(user_id=sample_user.id)
    
    assert pl_report["total_sessions"] == 2
    assert pl_report["winning_sessions"] == 1
    assert pl_report["losing_sessions"] == 1
    assert pl_report["total_pl"] == Decimal("30.00")  # 50 - 20
    assert pl_report["win_rate"] == 50.0


def test_get_session_profit_loss_report_with_filters(test_db, sample_user, sample_site, sample_game, game_session_service):
    """Test session P/L report with date filters"""
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 1, 10),
        starting_balance=Decimal("100.00"),
        starting_redeemable=Decimal("0.00"),
        ending_balance=Decimal("120.00"),
        ending_redeemable=Decimal("20.00")
    )
    game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=session.session_date,
        end_time="23:59:59",
    )
    
    report_service = ReportService(test_db)
    pl_report = report_service.get_session_profit_loss_report(
        user_id=sample_user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 15)
    )
    
    assert pl_report["total_sessions"] == 1
    assert pl_report["total_pl"] == Decimal("20.00")


def test_get_session_profit_loss_report_uses_local_session_dates(monkeypatch, test_db, sample_user, sample_site):
    """Session P/L filters should respect local day boundaries."""
    from tools.timezone_utils import local_date_time_to_utc

    monkeypatch.setattr(
        "services.report_service.get_configured_timezone_name",
        lambda: "America/New_York",
    )

    cursor = test_db._connection.cursor()
    first_date, first_time = local_date_time_to_utc(
        date(2026, 1, 1),
        "23:30:00",
        "America/New_York",
    )
    second_date, second_time = local_date_time_to_utc(
        date(2026, 1, 2),
        "00:30:00",
        "America/New_York",
    )

    cursor.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, session_date, session_time, net_taxable_pl, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, first_date, first_time, "20.00", "Closed"),
    )
    cursor.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, session_date, session_time, net_taxable_pl, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, second_date, second_time, "10.00", "Closed"),
    )
    test_db._connection.commit()

    report_service = ReportService(test_db)
    pl_report = report_service.get_session_profit_loss_report(
        user_id=sample_user.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
    )

    assert pl_report["total_sessions"] == 1
    assert pl_report["total_pl"] == Decimal("20.00")


def test_get_session_profit_loss_report_no_sessions(test_db, sample_user):
    """Test P/L report with no sessions returns zero stats"""
    report_service = ReportService(test_db)
    pl_report = report_service.get_session_profit_loss_report(user_id=sample_user.id)
    
    assert pl_report["total_sessions"] == 0
    assert pl_report["win_rate"] == 0


def test_get_bridge_reconciliation_report(test_db, sample_user, sample_site, purchase_repo):
    """Test bridge/reconciliation report aggregates site roll-forward values."""
    from models.purchase import Purchase

    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    test_db.execute(
        "UPDATE purchases SET remaining_amount = ? WHERE id = ?",
        ("40.00", purchase.id),
    )

    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "80.00", "2026-01-05", "12:00:00"),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-05", sample_site.id, sample_user.id, redemption_id, "60.00", "80.00", "20.00"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-01-10", "23:59:59", "15.00", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    assert len(report["site_rows"]) == 1
    site_row = report["site_rows"][0]
    assert site_row["site_name"] == sample_site.name
    assert site_row["total_purchases"] == Decimal("100.00")
    assert site_row["redeemed_basis"] == Decimal("60.00")
    assert site_row["open_basis"] == Decimal("40.00")
    assert site_row["basis_delta"] == Decimal("0.00")
    assert site_row["realized_pl"] == Decimal("20.00")
    assert site_row["economic_pl"] == Decimal("20.00")
    assert site_row["session_pl"] == Decimal("15.00")
    assert site_row["bridge_gap"] == Decimal("5.00")
    assert "$20.00 on 2026-01-05 redemption timing difference" in site_row["bridge_gap_explanation"]
    assert "-$15.00 on 2026-01-10 closed session not yet redeemed" in site_row["bridge_gap_explanation"]
    assert "Audit items that add up to the current actionable gap:" in site_row["bridge_gap_detail"]

    totals = report["totals"]
    assert totals["basis_delta"] == Decimal("0.00")
    assert totals["bridge_gap"] == Decimal("5.00")


def test_get_bridge_reconciliation_report_uses_accounting_local_timestamps_in_explanations(
    monkeypatch,
    test_db,
    sample_user,
    sample_site,
):
    """Bridge explanations should display accounting-local dates/times, not raw stored UTC timestamps."""
    from tools.timezone_utils import utc_date_time_to_local

    monkeypatch.setattr(
        "services.report_service.utc_date_time_to_accounting_local",
        lambda db, utc_date, utc_time, settings=None: utc_date_time_to_local(
            utc_date,
            utc_time,
            "America/New_York",
        ),
    )

    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "80.00", "2026-04-08", "01:46:22"),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-04-08", sample_site.id, sample_user.id, redemption_id, "50.00", "105.10", "55.10"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-08", "01:30:00", "55.02", "Closed"),
    )
    close_marker_id = test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-04-13",
            "14:00:00",
            1,
            "Balance Closed - Net Loss: $9.99 ($0.59 SC marked dormant)",
            "COMPLETED",
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-04-13", sample_site.id, sample_user.id, close_marker_id, "9.99", "0.00", "-9.99"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-13", "13:30:00", "-9.40", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert "$0.08 on 2026-04-07 redemption timing difference" in site_row["bridge_gap_explanation"]
    assert "on 2026-04-07 21:46:22: redemption realized $55.10 while closed sessions since the prior redemption total $55.02." in site_row["bridge_gap_detail"]
    assert "-$0.59 on 2026-04-13 close marker vs sessions" in site_row["bridge_gap_explanation"]


def test_get_bridge_reconciliation_report_explains_dormant_and_pending_redemption(
    test_db,
    sample_user,
    sample_site,
    purchase_repo,
):
    """Bridge explanation should surface dormant SC and pending-redemption signals."""
    from models.purchase import Purchase

    purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 2, 1),
    ))
    test_db.execute(
        "UPDATE purchases SET remaining_amount = ?, status = ? WHERE id = ?",
        ("25.00", "dormant", purchase.id),
    )
    test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "30.00", "2026-02-05", "12:00:00", "PENDING"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-02-10", "23:59:59", "8.00", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    assert len(report["site_rows"]) == 1
    site_row = report["site_rows"][0]
    assert "-$8.00 on 2026-02-10 closed session not yet redeemed" in site_row["bridge_gap_explanation"]
    assert "Dormant purchase basis still parked: $25.00." in site_row["bridge_gap_detail"]
    assert "Pending redemptions without realized rows: 1 for $30.00." in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_explains_close_balance_writeoff(
    test_db,
    sample_user,
    sample_site,
):
    """Close-balance markers should be called out explicitly instead of falling back to generic timing text."""
    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-03-01",
            "09:00:00",
            1,
            "Balance Closed - Net Loss: $50.00 ($12.00 SC marked dormant)",
            "PENDING",
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-03-01", sample_site.id, sample_user.id, redemption_id, "50.00", "0.00", "-50.00"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert "-$50.00 on 2026-03-01 close marker vs sessions" in site_row["bridge_gap_explanation"]
    assert "close marker realized -$50.00 while closed sessions since the prior redemption total $0.00" in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_surfaces_zero_basis_close_marker_context(
    test_db,
    sample_user,
    sample_site,
):
    """Zero-basis close markers should appear as context for an unmatched session-profit bridge gap."""
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-10", "21:00:00", "12.31", "Closed"),
    )
    test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status, more_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-04-11",
            "09:00:00",
            1,
            "Balance Closed - Net Loss: $0.00 ($12.31 SC marked dormant)",
            "COMPLETED",
            1,
        ),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["bridge_gap"] == Decimal("-12.31")
    assert "-$12.31 on 2026-04-10 closed session not yet redeemed" in site_row["bridge_gap_explanation"]
    assert "2026-04-11 05:00:00 close marker parked 12.31 SC dormant with no realized row." in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_suppresses_reactivated_close_marker_residue(
    test_db,
    sample_user,
    sample_site,
):
    """Historical close-marker residue should be removed from the current gap after later session activity."""
    close_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status, more_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-03-09",
            "18:31:09",
            1,
            "Balance Closed - Net Loss: $49.99 ($0.10 SC marked dormant)",
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-03-09", sample_site.id, sample_user.id, close_redemption_id, "49.99", "0.00", "-49.99"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-03-09", "18:21:33", "-49.89", "Closed"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-13", "19:09:44", "64.22", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["raw_bridge_gap"] == Decimal("-64.32")
    assert site_row["bridge_gap"] == Decimal("-64.22")
    assert site_row["bridge_gap_explanation"] == "-$64.22 on 2026-04-13 closed session not yet redeemed"
    assert "Current actionable gap: -$64.22" in site_row["bridge_gap_detail"]
    assert "Historical items suppressed from the current actionable gap:" not in site_row["bridge_gap_detail"]
    assert "Raw lifetime gap:" not in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_suppresses_close_marker_carryforward_consumed_by_later_redemption(
    test_db,
    sample_user,
    sample_site,
):
    """Dormant carry-forward consumed into a later redemption should not remain in the current actionable gap."""
    close_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status, more_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-03-26",
            "13:21:58",
            1,
            "Balance Closed - Net Loss: $57.98 ($8.00 SC marked dormant)",
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-03-26", sample_site.id, sample_user.id, close_redemption_id, "57.98", "0.00", "-57.98"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, delta_redeem, ending_redeemable, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-03-26", "13:01:43", "8.00", "8.00", "-57.90", "Closed"),
    )

    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time, processed, status, more_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "80.08", "2026-04-08", "01:46:22", 1, "COMPLETED", 0),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-04-08", sample_site.id, sample_user.id, redemption_id, "24.98", "80.08", "55.10"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, starting_redeemable, delta_redeem, ending_redeemable, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-08", "01:41:15", "8.00", "80.00", "80.08", "55.02", "Closed"),
    )

    later_close_marker_id = test_db.execute(
        """
        INSERT INTO redemptions
            (user_id, site_id, amount, redemption_date, redemption_time, processed, notes, status, more_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "0.00",
            "2026-04-13",
            "12:33:23",
            1,
            "Balance Closed - Net Loss: $9.99 ($64.00 SC marked dormant)",
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-04-13", sample_site.id, sample_user.id, later_close_marker_id, "9.99", "0.00", "-9.99"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, starting_redeemable, delta_redeem, ending_redeemable, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-04-13", "12:28:27", "59.00", "0.00", "59.00", "-9.40", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["raw_bridge_gap"] == Decimal("-0.59")
    assert site_row["bridge_gap"] == Decimal("-0.59")
    assert site_row["bridge_gap_explanation"] == "-$0.59 on 2026-04-13 close left dormant redeemable on site"
    assert "$0.08 on 2026-04-08 redemption timing difference" not in site_row["bridge_gap_explanation"]
    assert "the latest closed session ended with $0.59 still redeemable on site" in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_explains_latest_partial_redemption_as_remaining_on_site(
    test_db,
    sample_user,
    sample_site,
):
    """A latest partial redemption should surface the still-redeemable amount left on site."""
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id,
            site_id,
            session_date,
            session_time,
            starting_redeemable,
            ending_redeemable,
            delta_redeem,
            net_taxable_pl,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-04-24",
            "17:08:00",
            "6.09",
            "1040.91",
            "1034.82",
            "160.52",
            "Closed",
        ),
    )
    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "900.00",
            "2026-04-24",
            "20:18:53",
            1,
            "COMPLETED",
            1,
            "140.91 remaining on site, redeemable, but $900 max daily redemption limit.",
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-04-24",
            sample_site.id,
            sample_user.id,
            redemption_id,
            "879.99",
            "900.00",
            "20.01",
        ),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["raw_bridge_gap"] == Decimal("-140.51")
    assert site_row["bridge_gap"] == Decimal("-140.91")
    assert site_row["bridge_gap_explanation"] == "-$140.91 on 2026-04-24 partial redemption left redeemable on site"
    assert "partial redemption paid $900.00 while $1,040.91 was still redeemable on site at close, leaving $140.91 still on site for a later redemption." in site_row["bridge_gap_detail"]


def test_get_bridge_reconciliation_report_suppresses_partial_redemption_remainder_consumed_by_later_full_redemption(
    test_db,
    sample_user,
    sample_site,
):
    """Older partial-redemption carry-forward should drop out once a later full redemption consumes it."""
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id,
            site_id,
            session_date,
            session_time,
            starting_redeemable,
            ending_redeemable,
            delta_redeem,
            net_taxable_pl,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-02-15",
            "00:36:00",
            "0.00",
            "120.00",
            "120.00",
            "50.00",
            "Closed",
        ),
    )
    partial_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "100.00",
            "2026-02-15",
            "02:58:59",
            1,
            "COMPLETED",
            1,
            "20.00 remaining on site, redeemable, but $100 max daily redemption limit.",
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-02-15",
            sample_site.id,
            sample_user.id,
            partial_redemption_id,
            "100.00",
            "100.00",
            "0.00",
        ),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id,
            site_id,
            session_date,
            session_time,
            starting_redeemable,
            ending_redeemable,
            delta_redeem,
            net_taxable_pl,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-02-16",
            "06:52:54",
            "20.00",
            "20.25",
            "0.25",
            "0.25",
            "Closed",
        ),
    )
    full_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "20.00",
            "2026-02-16",
            "06:56:03",
            1,
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-02-16",
            sample_site.id,
            sample_user.id,
            full_redemption_id,
            "-30.00",
            "20.00",
            "50.00",
        ),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["raw_bridge_gap"] == Decimal("-0.25")
    assert site_row["bridge_gap"] == Decimal("-0.25")
    assert site_row["bridge_gap_explanation"] == "-$0.25 on 2026-02-16 full redemption left dormant SC on site"
    assert "partial redemption left redeemable on site" not in site_row["bridge_gap_explanation"]


def test_get_bridge_reconciliation_report_suppresses_resolved_partial_redemption_chain_from_current_gap(
    test_db,
    sample_user,
    sample_site,
):
    """A partial redemption that is later fully cleared should not remain in the current-state gap."""
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id,
            site_id,
            session_date,
            session_time,
            starting_redeemable,
            ending_redeemable,
            delta_redeem,
            net_taxable_pl,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-03-27",
            "10:00:00",
            "0.00",
            "7014.97",
            "7014.97",
            "14.97",
            "Closed",
        ),
    )
    partial_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "5000.00",
            "2026-03-27",
            "10:05:00",
            1,
            "COMPLETED",
            1,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-03-27",
            sample_site.id,
            sample_user.id,
            partial_redemption_id,
            "5000.00",
            "5000.00",
            "0.00",
        ),
    )
    full_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2014.97",
            "2026-03-27",
            "10:06:00",
            1,
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-03-27",
            sample_site.id,
            sample_user.id,
            full_redemption_id,
            "2000.00",
            "2014.97",
            "14.97",
        ),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["raw_bridge_gap"] == Decimal("0.00")
    assert site_row["bridge_gap"] == Decimal("0.00")
    assert "partial redemption left redeemable on site" not in site_row["bridge_gap_explanation"]
    assert site_row["bridge_gap_detail"].startswith("Current actionable gap: $0.00")


def test_get_bridge_reconciliation_report_explains_full_redemption_rounding_remainder_as_dormant_sc(
    test_db,
    sample_user,
    sample_site,
):
    """Whole-dollar full redemptions should be explained as dormant/on-site cents, not generic redemption variance."""
    test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id,
            site_id,
            session_date,
            session_time,
            starting_redeemable,
            ending_redeemable,
            delta_redeem,
            session_basis,
            basis_consumed,
            net_taxable_pl,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "2026-04-17",
            "18:56:16",
            "0.23",
            "378.53",
            "378.30",
            "339.78",
            "339.78",
            "38.52",
            "Closed",
        ),
    )
    redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (
            user_id,
            site_id,
            amount,
            redemption_date,
            redemption_time,
            processed,
            status,
            more_remaining
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            "378.00",
            "2026-04-17",
            "19:41:06",
            1,
            "COMPLETED",
            0,
        ),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-04-17",
            sample_site.id,
            sample_user.id,
            redemption_id,
            "339.78",
            "378.00",
            "38.22",
        ),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    site_row = report["site_rows"][0]
    assert site_row["bridge_gap"] == Decimal("-0.53")
    assert site_row["bridge_gap_explanation"] == "-$0.53 on 2026-04-17 full redemption left dormant SC on site"
    assert "full redemption paid $378.00 against $378.53 redeemable on site at close, leaving $0.53 parked on site as dormant SC." in site_row["bridge_gap_detail"]
    assert "redemption vs sessions" not in site_row["bridge_gap_explanation"]


def test_get_bridge_reconciliation_report_lists_user_site_pairs_separately(
    test_db,
    sample_user,
    sample_site,
    user_service,
    purchase_repo,
):
    """Bridge report should not aggregate multiple users into one site row."""
    from models.purchase import Purchase

    other_user = user_service.create_user(
        name="Other User",
        email="other@example.com",
        notes="Second user for pair-scope testing",
    )

    first_purchase = purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1),
    ))
    second_purchase = purchase_repo.create(Purchase(
        user_id=other_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 1, 2),
    ))
    test_db.execute(
        "UPDATE purchases SET remaining_amount = ? WHERE id = ?",
        ("40.00", first_purchase.id),
    )
    test_db.execute(
        "UPDATE purchases SET remaining_amount = ? WHERE id = ?",
        ("10.00", second_purchase.id),
    )

    first_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "80.00", "2026-01-05", "12:00:00"),
    )
    second_redemption_id = test_db.execute(
        """
        INSERT INTO redemptions (user_id, site_id, amount, redemption_date, redemption_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (other_user.id, sample_site.id, "65.00", "2026-01-06", "12:00:00"),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-05", sample_site.id, sample_user.id, first_redemption_id, "60.00", "80.00", "20.00"),
    )
    test_db.execute(
        """
        INSERT INTO realized_transactions
            (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-06", sample_site.id, other_user.id, second_redemption_id, "40.00", "65.00", "25.00"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sample_user.id, sample_site.id, "2026-01-10", "23:59:59", "15.00", "Closed"),
    )
    test_db.execute(
        """
        INSERT INTO game_sessions (user_id, site_id, session_date, session_time, net_taxable_pl, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (other_user.id, sample_site.id, "2026-01-11", "23:59:59", "5.00", "Closed"),
    )

    report_service = ReportService(test_db)
    report = report_service.get_bridge_reconciliation_report()

    assert len(report["site_rows"]) == 2

    rows_by_user = {row["user_name"]: row for row in report["site_rows"]}

    first_row = rows_by_user[sample_user.name]
    assert first_row["site_name"] == sample_site.name
    assert first_row["total_purchases"] == Decimal("100.00")
    assert first_row["redeemed_basis"] == Decimal("60.00")
    assert first_row["open_basis"] == Decimal("40.00")
    assert first_row["session_pl"] == Decimal("15.00")
    assert first_row["bridge_gap"] == Decimal("5.00")

    second_row = rows_by_user[other_user.name]
    assert second_row["site_name"] == sample_site.name
    assert second_row["total_purchases"] == Decimal("50.00")
    assert second_row["redeemed_basis"] == Decimal("40.00")
    assert second_row["open_basis"] == Decimal("10.00")
    assert second_row["session_pl"] == Decimal("5.00")
    assert second_row["bridge_gap"] == Decimal("20.00")

    totals = report["totals"]
    assert totals["total_purchases"] == Decimal("150.00")
    assert totals["redeemed_basis"] == Decimal("100.00")
    assert totals["open_basis"] == Decimal("50.00")
    assert totals["session_pl"] == Decimal("20.00")
    assert totals["bridge_gap"] == Decimal("25.00")


def test_get_all_user_summaries_with_site_filter(test_db, sample_user, sample_site, purchase_repo):
    """Test getting all user summaries filtered by site"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    report_service = ReportService(test_db)
    summaries = report_service.get_all_user_summaries(site_id=sample_site.id)
    
    assert len(summaries) >= 1


def test_get_all_site_summaries_with_user_filter(test_db, sample_user, sample_site, purchase_repo):
    """Test getting all site summaries filtered by user"""
    from models.purchase import Purchase
    
    purchase_repo.create(Purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 1)
    ))
    
    report_service = ReportService(test_db)
    summaries = report_service.get_all_site_summaries(user_id=sample_user.id)
    
    assert len(summaries) >= 1
