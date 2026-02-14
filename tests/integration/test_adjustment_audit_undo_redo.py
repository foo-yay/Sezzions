"""Integration coverage for adjustment/checkpoint audit + undo/redo wiring."""

from datetime import date
from decimal import Decimal

from app_facade import AppFacade


def test_adjustment_create_writes_audit_and_pushes_undo():
    facade = AppFacade(":memory:")
    try:
        user = facade.create_user("Audit User")
        site = facade.create_site("Audit Site", "https://example.com", sc_rate=1.0)

        adj = facade.adjustment_service.create_basis_adjustment(
            user_id=user.id,
            site_id=site.id,
            effective_date=date(2026, 1, 15),
            delta_basis_usd=Decimal("25.00"),
            reason="Audit integration",
        )

        entries = facade.audit_service.get_audit_log(
            table_name="account_adjustments",
            action="CREATE",
            record_id=adj.id,
            limit=5,
        )
        assert entries
        assert facade.undo_redo_service.can_undo()
    finally:
        facade.db.close()


def test_adjustment_undo_reverses_create():
    facade = AppFacade(":memory:")
    try:
        user = facade.create_user("Undo User")
        site = facade.create_site("Undo Site", "https://example.com", sc_rate=1.0)

        adj = facade.adjustment_service.create_balance_checkpoint(
            user_id=user.id,
            site_id=site.id,
            effective_date=date(2026, 1, 16),
            checkpoint_total_sc=Decimal("1000.00"),
            checkpoint_redeemable_sc=Decimal("900.00"),
            reason="Undo integration",
        )

        assert facade.adjustment_service.get_by_id(adj.id) is not None
        facade.undo_redo_service.undo()
        assert facade.adjustment_service.get_by_id(adj.id).deleted_at is not None
    finally:
        facade.db.close()
