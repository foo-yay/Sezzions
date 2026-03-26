from datetime import date
from decimal import Decimal

from models.purchase import Purchase

import services.redemption_service as redemption_service_module


def test_issue_195_full_redemption_uses_local_timestamp_for_same_day_fifo_window(
    redemption_service,
    purchase_repo,
    sample_user,
    sample_site,
    monkeypatch,
):
    monkeypatch.setattr(redemption_service_module, "get_entry_timezone_name", lambda: "America/New_York")

    first = purchase_repo.create(
        Purchase(
            user_id=sample_user.id,
            site_id=sample_site.id,
            amount=Decimal("10.00"),
            purchase_date=date(2026, 3, 26),
            purchase_time="09:00:00",
            purchase_entry_time_zone="America/New_York",
        )
    )
    second = purchase_repo.create(
        Purchase(
            user_id=sample_user.id,
            site_id=sample_site.id,
            amount=Decimal("20.00"),
            purchase_date=date(2026, 3, 26),
            purchase_time="10:00:00",
            purchase_entry_time_zone="America/New_York",
        )
    )

    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("0.00"),
        redemption_date=date(2026, 3, 26),
        redemption_time="09:30:00",
        apply_fifo=True,
        more_remaining=False,
        processed=True,
        notes="Balance Closed - Net Loss: $10.00 ($1.00 SC marked dormant)",
    )

    assert redemption.cost_basis == Decimal("10.00")
    assert redemption.taxable_profit == Decimal("-10.00")

    updated_first = purchase_repo.get_by_id(first.id)
    updated_second = purchase_repo.get_by_id(second.id)
    assert updated_first.remaining_amount == Decimal("0.00")
    assert updated_second.remaining_amount == Decimal("20.00")
