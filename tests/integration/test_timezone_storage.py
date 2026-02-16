"""Integration tests for UTC storage with local display (Issue #107)."""
from datetime import date
from decimal import Decimal

from repositories.purchase_repository import PurchaseRepository
from services.purchase_service import PurchaseService
from services.audit_service import AuditService


def test_purchase_stores_utc_and_displays_local(test_db, sample_user, sample_site, monkeypatch):
    monkeypatch.setattr(
        "repositories.purchase_repository.get_entry_timezone_name",
        lambda *args, **kwargs: "America/Los_Angeles",
    )

    repo = PurchaseRepository(test_db)
    service = PurchaseService(repo)

    purchase = service.create_purchase(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("100.00"),
        purchase_date=date(2026, 2, 13),
        purchase_time="20:30:00",
    )

    row = test_db.fetch_one(
        "SELECT purchase_date, purchase_time FROM purchases WHERE id = ?",
        (purchase.id,),
    )
    assert row["purchase_date"] == "2026-02-14"
    assert row["purchase_time"] == "04:30:00"

    fetched_local = repo.get_by_id(purchase.id)
    assert fetched_local.purchase_date == date(2026, 2, 13)
    assert fetched_local.purchase_time == "20:30:00"

    monkeypatch.setattr(
        "repositories.purchase_repository.get_configured_timezone_name",
        lambda *args, **kwargs: "UTC",
    )
    fetched_utc = repo.get_by_id(purchase.id)
    assert fetched_utc.purchase_date == date(2026, 2, 13)
    assert fetched_utc.purchase_time == "20:30:00"


def test_audit_log_date_filter_uses_local_time(test_db, monkeypatch):
    monkeypatch.setattr(
        "tools.timezone_utils.get_configured_timezone_name",
        lambda *args, **kwargs: "America/Los_Angeles",
    )
    audit = AuditService(test_db)
    audit.log_create("purchases", 1, {"id": 1})

    test_db.execute(
        "UPDATE audit_log SET timestamp = ? WHERE table_name = ?",
        ("2026-02-14 01:00:00", "purchases"),
    )

    entries = audit.get_audit_log(
        table_name="purchases",
        start_date=date(2026, 2, 13),
        end_date=date(2026, 2, 13),
        limit=10,
    )
    assert len(entries) == 1
