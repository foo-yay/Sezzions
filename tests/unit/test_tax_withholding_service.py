from decimal import Decimal

import pytest

from repositories.game_session_repository import GameSessionRepository
from services.tax_withholding_service import TaxWithholdingService


class FakeSettings:
    def __init__(self, data):
        self._data = dict(data)

    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def service(test_db):
    settings = FakeSettings(
        {
            "tax_withholding_enabled": True,
            "tax_withholding_default_rate_pct": 20,
        }
    )
    return TaxWithholdingService(test_db, settings=settings)


@pytest.fixture
def session_repo(test_db):
    return GameSessionRepository(test_db)


def _insert_closed_session(test_db, sample_user, sample_site, net_taxable_pl: str, *, rate=None, is_custom=0):
    # Minimal insert; many columns have defaults.
    return test_db.execute(
        """
        INSERT INTO game_sessions (
            user_id, site_id, game_id,
            session_date, session_time,
            starting_balance, ending_balance,
            starting_redeemable, ending_redeemable,
            purchases_during, redemptions_during,
            wager_amount,
            net_taxable_pl,
            tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount,
            status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sample_user.id,
            sample_site.id,
            None,
            "2026-01-01",
            "00:00:00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            net_taxable_pl,
            rate,
            is_custom,
            None,
            "Closed",
            "",
        ),
    )


def test_compute_amount_positive_pl():
    assert TaxWithholdingService.compute_amount(Decimal("100.00"), Decimal("20")) == Decimal("20.00")


def test_compute_amount_non_positive_pl_is_zero():
    assert TaxWithholdingService.compute_amount(Decimal("0.00"), Decimal("20")) == Decimal("0.00")
    assert TaxWithholdingService.compute_amount(Decimal("-10.00"), Decimal("20")) == Decimal("0.00")


def test_bulk_recalc_sets_rate_and_amount_for_non_custom_sessions(service, test_db, sample_user, sample_site):
    sess_id = _insert_closed_session(test_db, sample_user, sample_site, "100.00", rate=None, is_custom=0)

    updated = service.bulk_recalculate(site_id=sample_site.id, user_id=sample_user.id, overwrite_custom=False)
    assert updated == 1

    row = test_db.fetch_one(
        """
        SELECT tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM game_sessions WHERE id = ?
        """,
        (sess_id,),
    )
    assert row["tax_withholding_rate_pct"] == 20.0
    assert row["tax_withholding_is_custom"] == 0
    assert row["tax_withholding_amount"] == "20.00"


def test_bulk_recalc_skips_custom_when_not_overwriting(service, test_db, sample_user, sample_site):
    custom_id = _insert_closed_session(test_db, sample_user, sample_site, "100.00", rate=30.0, is_custom=1)

    updated = service.bulk_recalculate(site_id=sample_site.id, user_id=sample_user.id, overwrite_custom=False)
    assert updated == 0

    row = test_db.fetch_one(
        """
        SELECT tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM game_sessions WHERE id = ?
        """,
        (custom_id,),
    )
    assert row["tax_withholding_rate_pct"] == 30.0
    assert row["tax_withholding_is_custom"] == 1
    assert row["tax_withholding_amount"] is None


def test_bulk_recalc_overwrites_custom_when_requested(service, test_db, sample_user, sample_site):
    custom_id = _insert_closed_session(test_db, sample_user, sample_site, "100.00", rate=30.0, is_custom=1)

    updated = service.bulk_recalculate(site_id=sample_site.id, user_id=sample_user.id, overwrite_custom=True)
    assert updated == 1

    row = test_db.fetch_one(
        """
        SELECT tax_withholding_rate_pct, tax_withholding_is_custom, tax_withholding_amount
        FROM game_sessions WHERE id = ?
        """,
        (custom_id,),
    )
    assert row["tax_withholding_rate_pct"] == 20.0
    assert row["tax_withholding_is_custom"] == 0
    assert row["tax_withholding_amount"] == "20.00"


def test_bulk_recalc_is_atomic_on_failure(service, test_db, sample_user, sample_site, monkeypatch):
    # Two sessions eligible for update.
    s1 = _insert_closed_session(test_db, sample_user, sample_site, "100.00", rate=None, is_custom=0)
    s2 = _insert_closed_session(test_db, sample_user, sample_site, "50.00", rate=None, is_custom=0)

    # Inject failure after the UPDATE executemany call begins.
    real_executemany = test_db.executemany_no_commit

    def boom(query, params_seq):
        # Fail before any statement is actually executed.
        raise RuntimeError("boom")

    monkeypatch.setattr(test_db, "executemany_no_commit", boom)

    with pytest.raises(RuntimeError, match="boom"):
        service.bulk_recalculate(site_id=sample_site.id, user_id=sample_user.id, overwrite_custom=False)

    # Nothing should be updated.
    for sess_id in (s1, s2):
        row = test_db.fetch_one(
            """
            SELECT tax_withholding_rate_pct, tax_withholding_amount
            FROM game_sessions WHERE id = ?
            """,
            (sess_id,),
        )
        assert row["tax_withholding_rate_pct"] is None
        assert row["tax_withholding_amount"] is None

    # Restore to avoid side effects
    monkeypatch.setattr(test_db, "executemany_no_commit", real_executemany)
