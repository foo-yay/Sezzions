"""Failure-injection tests for Accounting TZ changes (Issue #117)."""
from datetime import date
import pytest

from services.accounting_time_zone_service import AccountingTimeZoneService
from ui.settings import Settings


def test_accounting_tz_change_rolls_back_on_failure(test_db, tmp_path, monkeypatch):
    settings = Settings(settings_file=str(tmp_path / "settings.json"))
    settings.set("accounting_time_zone", "America/New_York")

    service = AccountingTimeZoneService(test_db, settings)
    service.ensure_history_seeded()

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "recompute_from_utc", boom)

    with pytest.raises(RuntimeError):
        service.change_accounting_time_zone(
            "America/Phoenix",
            effective_date=date(2026, 2, 15),
            effective_time="00:00:00",
            reason="test",
        )

    rows = test_db.fetch_all(
        "SELECT accounting_time_zone FROM accounting_time_zone_history ORDER BY effective_utc_timestamp",
        (),
    )
    assert [row["accounting_time_zone"] for row in rows] == ["America/New_York"]
