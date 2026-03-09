from repositories.database import DatabaseManager
from services.data_integrity_service import DataIntegrityService, ViolationType


def _create_db():
    db = DatabaseManager(":memory:")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'User')")
    db.execute("INSERT INTO sites (id, name) VALUES (1, 'Site')")
    return db


def test_purchase_remaining_check_casts_numeric_values():
    db = _create_db()
    db.execute(
        """
        INSERT INTO purchases (user_id, site_id, purchase_date, amount, sc_received, remaining_amount)
        VALUES (1, 1, '2026-03-08', '149.97', '168.00', '8.51')
        """
    )

    service = DataIntegrityService(db)
    result = service.check_integrity(quick=True)

    invalid_remaining = result.violations_by_type(ViolationType.PURCHASE_INVALID_REMAINING)
    assert invalid_remaining == []
    db.close()


def test_purchase_remaining_violation_when_numerically_greater():
    db = _create_db()
    db.execute(
        """
        INSERT INTO purchases (user_id, site_id, purchase_date, amount, sc_received, remaining_amount)
        VALUES (1, 1, '2026-03-08', '149.97', '168.00', '150.01')
        """
    )

    service = DataIntegrityService(db)
    result = service.check_integrity(quick=True)

    invalid_remaining = result.violations_by_type(ViolationType.PURCHASE_INVALID_REMAINING)
    assert len(invalid_remaining) == 1
    assert invalid_remaining[0].record_id is not None
    db.close()
