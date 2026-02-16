from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_session_deletion_impact_warns_when_future_redemption_exists(
    game_session_service,
    redemption_service,
    sample_user,
    sample_site,
    sample_game,
):
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 2, 15),
        session_time="23:00:00",
        starting_balance=Decimal("375.10"),
        ending_balance=Decimal("388.60"),
        calculate_pl=False,
    )
    session = game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=date(2026, 2, 15),
        end_time="23:30:01",
        recalculate_pl=False,
    )

    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("82.60"),
        redemption_date=date(2026, 2, 16),
        redemption_time="00:00:00",
        processed=True,
        more_remaining=True,
        apply_fifo=False,
    )

    impact = game_session_service.get_deletion_impact(session.id)
    assert impact != ""
    assert "Found 1 redemption(s)" in impact
    assert "$82.60" in impact

    # Sanity: the redemption is real in DB
    assert redemption.id is not None


def test_session_deletion_impact_ignores_soft_deleted_future_redemption(
    game_session_service,
    redemption_service,
    sample_user,
    sample_site,
    sample_game,
):
    session = game_session_service.create_session(
        user_id=sample_user.id,
        site_id=sample_site.id,
        game_id=sample_game.id,
        session_date=date(2026, 2, 15),
        session_time="23:00:00",
        starting_balance=Decimal("375.10"),
        ending_balance=Decimal("388.60"),
        calculate_pl=False,
    )
    session = game_session_service.update_session(
        session.id,
        status="Closed",
        end_date=date(2026, 2, 15),
        end_time="23:30:01",
        recalculate_pl=False,
    )

    redemption = redemption_service.create_redemption(
        user_id=sample_user.id,
        site_id=sample_site.id,
        amount=Decimal("82.60"),
        redemption_date=date(2026, 2, 16),
        redemption_time="00:00:00",
        processed=True,
        more_remaining=True,
        apply_fifo=False,
    )
    redemption_service.delete_redemption(redemption.id)

    impact = game_session_service.get_deletion_impact(session.id)
    assert impact == ""
