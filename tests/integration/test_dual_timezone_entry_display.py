"""Integration tests for Entry vs Accounting TZ behavior (Issue #117)."""
from datetime import date
from decimal import Decimal

from repositories.purchase_repository import PurchaseRepository
from services.purchase_service import PurchaseService


def test_purchase_entry_timezone_persists_on_display(test_db, sample_user, sample_site, monkeypatch):
    monkeypatch.setattr(
        "repositories.purchase_repository.get_entry_timezone_name",
        lambda *args, **kwargs: "America/Phoenix",
    )

    repo = PurchaseRepository(test_db)
    service = PurchaseService(repo)

    purchase = service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("50.00"),
        purchase_date=date(2026, 2, 14),
        purchase_time="23:30:00",
    )

    row = test_db.fetch_one(
        "SELECT purchase_date, purchase_time, purchase_entry_time_zone FROM purchases WHERE id = ?",
        (purchase.id,),
    )
    assert row["purchase_date"] == "2026-02-15"
    assert row["purchase_time"] == "06:30:00"
    assert row["purchase_entry_time_zone"] == "America/Phoenix"

    monkeypatch.setattr(
        "tools.timezone_utils.get_entry_timezone_name",
        lambda *args, **kwargs: "America/New_York",
    )
    fetched = repo.get_by_id(purchase.id)
    assert fetched.purchase_date == date(2026, 2, 14)
    assert fetched.purchase_time == "23:30:00"
