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
        "repositories.redemption_repository.get_configured_timezone_name",
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
