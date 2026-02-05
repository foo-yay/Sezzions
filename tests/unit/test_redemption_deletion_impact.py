from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_get_deletion_impact_empty_when_no_allocations(redemption_service, sample_user, sample_site):
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("10.00"),
        redemption_date=date(2026, 1, 15),
        processed=True,
        more_remaining=True,
        apply_fifo=False,
    )

    impact = redemption_service.get_deletion_impact(redemption.id)
    assert impact == ""


def test_get_deletion_impact_mentions_allocations(redemption_service, purchase_service, sample_user, sample_site):
    purchase_service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 1, 10),
    )

    # Full redemption consumes all remaining basis via FIFO, creating redemption_allocations
    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("0.00"),
        redemption_date=date(2026, 1, 15),
        processed=True,
        more_remaining=False,
        apply_fifo=True,
        redemption_time="12:00:00",
    )

    impact = redemption_service.get_deletion_impact(redemption.id)
    assert "FIFO allocation" in impact
