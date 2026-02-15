from datetime import date
from decimal import Decimal


def test_get_all_uses_local_redemption_dates(
    monkeypatch,
    test_db,
    sample_user,
    sample_site,
    purchase_repo,
    redemption_service,
):
    """Realized transaction filters should respect local day boundaries."""
    from models.purchase import Purchase
    from repositories.realized_transaction_repository import RealizedTransactionRepository
    from tools.timezone_utils import local_date_time_to_utc

    monkeypatch.setattr(
        "repositories.redemption_repository.get_configured_timezone_name",
        lambda: "America/New_York",
    )
    monkeypatch.setattr(
        "repositories.realized_transaction_repository.get_configured_timezone_name",
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
        amount=Decimal("50.00"),
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

    repo = RealizedTransactionRepository(test_db)
    transactions = repo.get_all(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 1),
    )

    assert len(transactions) == 1
    assert transactions[0].redemption_id == redemption.id
