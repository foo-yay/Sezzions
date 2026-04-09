"""Persistence helpers for hosted workspace-owned game sessions."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedGameSession
from services.hosted.persistence import (
    HostedGameRecord,
    HostedGameSessionRecord,
    HostedGameTypeRecord,
    HostedSiteRecord,
    HostedUserRecord,
)


class HostedGameSessionRepository:
    # ------------------------------------------------------------------ queries

    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedGameSession]:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        game_alias = aliased(HostedGameRecord)
        game_type_alias = aliased(HostedGameTypeRecord)
        query = (
            select(
                HostedGameSessionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                game_alias.name.label("game_name"),
                game_type_alias.name.label("game_type_name"),
            )
            .join(user_alias, HostedGameSessionRecord.user_id == user_alias.id)
            .join(site_alias, HostedGameSessionRecord.site_id == site_alias.id)
            .outerjoin(game_alias, HostedGameSessionRecord.game_id == game_alias.id)
            .outerjoin(game_type_alias, HostedGameSessionRecord.game_type_id == game_type_alias.id)
            .where(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
            .order_by(
                HostedGameSessionRecord.session_date.desc(),
                HostedGameSessionRecord.session_time.desc(),
                HostedGameSessionRecord.id.desc(),
            )
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)

        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def count_by_workspace_id(self, session, workspace_id: str) -> int:
        return session.scalar(
            select(func.count())
            .select_from(HostedGameSessionRecord)
            .where(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        ) or 0

    def list_by_workspace_user_and_site(
        self,
        session,
        workspace_id: str,
        user_id: str,
        site_id: str,
    ) -> list[HostedGameSession]:
        """Return sessions for a user+site pair ordered chronologically (ASC)."""
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        game_alias = aliased(HostedGameRecord)
        game_type_alias = aliased(HostedGameTypeRecord)
        query = (
            select(
                HostedGameSessionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                game_alias.name.label("game_name"),
                game_type_alias.name.label("game_type_name"),
            )
            .join(user_alias, HostedGameSessionRecord.user_id == user_alias.id)
            .join(site_alias, HostedGameSessionRecord.site_id == site_alias.id)
            .outerjoin(game_alias, HostedGameSessionRecord.game_id == game_alias.id)
            .outerjoin(game_type_alias, HostedGameSessionRecord.game_type_id == game_type_alias.id)
            .where(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.user_id == user_id,
                HostedGameSessionRecord.site_id == site_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
            .order_by(
                HostedGameSessionRecord.session_date.asc(),
                HostedGameSessionRecord.session_time.asc(),
                HostedGameSessionRecord.id.asc(),
            )
        )
        rows = session.execute(query).all()
        return [self._row_to_model(row) for row in rows]

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        game_session_id: str,
        workspace_id: str,
    ) -> HostedGameSession | None:
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        game_alias = aliased(HostedGameRecord)
        game_type_alias = aliased(HostedGameTypeRecord)
        row = session.execute(
            select(
                HostedGameSessionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                game_alias.name.label("game_name"),
                game_type_alias.name.label("game_type_name"),
            )
            .join(user_alias, HostedGameSessionRecord.user_id == user_alias.id)
            .join(site_alias, HostedGameSessionRecord.site_id == site_alias.id)
            .outerjoin(game_alias, HostedGameSessionRecord.game_id == game_alias.id)
            .outerjoin(game_type_alias, HostedGameSessionRecord.game_type_id == game_type_alias.id)
            .where(
                HostedGameSessionRecord.id == game_session_id,
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            return None
        return self._row_to_model(row)

    def get_active_session(
        self,
        session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        exclude_id: str | None = None,
    ) -> HostedGameSession | None:
        """Return the active (unclosed) session for a user+site, if any."""
        user_alias = aliased(HostedUserRecord)
        site_alias = aliased(HostedSiteRecord)
        game_alias = aliased(HostedGameRecord)
        game_type_alias = aliased(HostedGameTypeRecord)
        query = (
            select(
                HostedGameSessionRecord,
                user_alias.name.label("user_name"),
                site_alias.name.label("site_name"),
                game_alias.name.label("game_name"),
                game_type_alias.name.label("game_type_name"),
            )
            .join(user_alias, HostedGameSessionRecord.user_id == user_alias.id)
            .join(site_alias, HostedGameSessionRecord.site_id == site_alias.id)
            .outerjoin(game_alias, HostedGameSessionRecord.game_id == game_alias.id)
            .outerjoin(game_type_alias, HostedGameSessionRecord.game_type_id == game_type_alias.id)
            .where(
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.user_id == user_id,
                HostedGameSessionRecord.site_id == site_id,
                HostedGameSessionRecord.status == "Active",
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        )
        if exclude_id is not None:
            query = query.where(HostedGameSessionRecord.id != exclude_id)
        row = session.execute(query).first()
        if row is None:
            return None
        return self._row_to_model(row)

    # ------------------------------------------------------------------ mutations

    def create(
        self,
        session,
        *,
        workspace_id: str,
        user_id: str,
        site_id: str,
        session_date: str,
        session_time: str = "00:00:00",
        start_entry_time_zone: str | None = None,
        game_id: str | None = None,
        game_type_id: str | None = None,
        end_date: str | None = None,
        end_time: str | None = None,
        end_entry_time_zone: str | None = None,
        starting_balance: str = "0.00",
        ending_balance: str = "0.00",
        starting_redeemable: str = "0.00",
        ending_redeemable: str = "0.00",
        wager_amount: str = "0.00",
        rtp: float | None = None,
        purchases_during: str = "0.00",
        redemptions_during: str = "0.00",
        expected_start_total: str | None = None,
        expected_start_redeemable: str | None = None,
        discoverable_sc: str | None = None,
        delta_total: str | None = None,
        delta_redeem: str | None = None,
        session_basis: str | None = None,
        basis_consumed: str | None = None,
        net_taxable_pl: str | None = None,
        tax_withholding_rate_pct: float | None = None,
        tax_withholding_is_custom: bool = False,
        tax_withholding_amount: float | None = None,
        status: str = "Active",
        notes: str | None = None,
    ) -> HostedGameSession:
        record = HostedGameSessionRecord(
            workspace_id=workspace_id,
            user_id=user_id,
            site_id=site_id,
            session_date=session_date,
            session_time=session_time,
            start_entry_time_zone=start_entry_time_zone,
            game_id=game_id,
            game_type_id=game_type_id,
            end_date=end_date,
            end_time=end_time,
            end_entry_time_zone=end_entry_time_zone,
            starting_balance=starting_balance,
            ending_balance=ending_balance,
            starting_redeemable=starting_redeemable,
            ending_redeemable=ending_redeemable,
            wager_amount=wager_amount,
            rtp=rtp,
            purchases_during=purchases_during,
            redemptions_during=redemptions_during,
            expected_start_total=expected_start_total,
            expected_start_redeemable=expected_start_redeemable,
            discoverable_sc=discoverable_sc,
            delta_total=delta_total,
            delta_redeem=delta_redeem,
            session_basis=session_basis,
            basis_consumed=basis_consumed,
            net_taxable_pl=net_taxable_pl,
            tax_withholding_rate_pct=tax_withholding_rate_pct,
            tax_withholding_is_custom=tax_withholding_is_custom,
            tax_withholding_amount=tax_withholding_amount,
            status=status,
            notes=notes,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, game_session_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        game_session_id: str,
        workspace_id: str,
        user_id: str,
        site_id: str,
        session_date: str,
        session_time: str = "00:00:00",
        start_entry_time_zone: str | None = None,
        game_id: str | None = None,
        game_type_id: str | None = None,
        end_date: str | None = None,
        end_time: str | None = None,
        end_entry_time_zone: str | None = None,
        starting_balance: str = "0.00",
        ending_balance: str = "0.00",
        starting_redeemable: str = "0.00",
        ending_redeemable: str = "0.00",
        wager_amount: str = "0.00",
        rtp: float | None = None,
        purchases_during: str = "0.00",
        redemptions_during: str = "0.00",
        expected_start_total: str | None = None,
        expected_start_redeemable: str | None = None,
        discoverable_sc: str | None = None,
        delta_total: str | None = None,
        delta_redeem: str | None = None,
        session_basis: str | None = None,
        basis_consumed: str | None = None,
        net_taxable_pl: str | None = None,
        tax_withholding_rate_pct: float | None = None,
        tax_withholding_is_custom: bool = False,
        tax_withholding_amount: float | None = None,
        status: str = "Active",
        notes: str | None = None,
    ) -> HostedGameSession | None:
        record = session.scalar(
            select(HostedGameSessionRecord).where(
                HostedGameSessionRecord.id == game_session_id,
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            return None

        record.user_id = user_id
        record.site_id = site_id
        record.session_date = session_date
        record.session_time = session_time
        record.start_entry_time_zone = start_entry_time_zone
        record.game_id = game_id
        record.game_type_id = game_type_id
        record.end_date = end_date
        record.end_time = end_time
        record.end_entry_time_zone = end_entry_time_zone
        record.starting_balance = starting_balance
        record.ending_balance = ending_balance
        record.starting_redeemable = starting_redeemable
        record.ending_redeemable = ending_redeemable
        record.wager_amount = wager_amount
        record.rtp = rtp
        record.purchases_during = purchases_during
        record.redemptions_during = redemptions_during
        record.expected_start_total = expected_start_total
        record.expected_start_redeemable = expected_start_redeemable
        record.discoverable_sc = discoverable_sc
        record.delta_total = delta_total
        record.delta_redeem = delta_redeem
        record.session_basis = session_basis
        record.basis_consumed = basis_consumed
        record.net_taxable_pl = net_taxable_pl
        record.tax_withholding_rate_pct = tax_withholding_rate_pct
        record.tax_withholding_is_custom = tax_withholding_is_custom
        record.tax_withholding_amount = tax_withholding_amount
        record.status = status
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, game_session_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, game_session_id: str, workspace_id: str) -> bool:
        """Soft-delete a game session by setting deleted_at."""
        record = session.scalar(
            select(HostedGameSessionRecord).where(
                HostedGameSessionRecord.id == game_session_id,
                HostedGameSessionRecord.workspace_id == workspace_id,
                HostedGameSessionRecord.deleted_at.is_(None),
            )
        )
        if record is None:
            return False

        from datetime import datetime, timezone

        record.deleted_at = datetime.now(timezone.utc).isoformat()
        session.flush()
        return True

    def delete_many(self, session, *, game_session_ids: list[str], workspace_id: str) -> int:
        """Soft-delete multiple game sessions."""
        normalized_ids = list(dict.fromkeys(game_session_ids))
        if not normalized_ids:
            return 0

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for sid in normalized_ids:
            record = session.scalar(
                select(HostedGameSessionRecord).where(
                    HostedGameSessionRecord.id == sid,
                    HostedGameSessionRecord.workspace_id == workspace_id,
                    HostedGameSessionRecord.deleted_at.is_(None),
                )
            )
            if record is not None:
                record.deleted_at = now
                count += 1
        session.flush()
        return count

    # ------------------------------------------------------------------ mapping

    @staticmethod
    def _row_to_model(row) -> HostedGameSession:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        site_name = row.site_name if hasattr(row, "site_name") else None
        game_name = row.game_name if hasattr(row, "game_name") else None
        game_type_name = row.game_type_name if hasattr(row, "game_type_name") else None
        return HostedGameSession(
            id=record.id,
            workspace_id=record.workspace_id,
            user_id=record.user_id,
            site_id=record.site_id,
            game_id=record.game_id,
            game_type_id=record.game_type_id,
            session_date=record.session_date,
            session_time=record.session_time,
            start_entry_time_zone=record.start_entry_time_zone,
            end_date=record.end_date,
            end_time=record.end_time,
            end_entry_time_zone=record.end_entry_time_zone,
            starting_balance=record.starting_balance,
            ending_balance=record.ending_balance,
            starting_redeemable=record.starting_redeemable,
            ending_redeemable=record.ending_redeemable,
            wager_amount=record.wager_amount,
            rtp=record.rtp,
            purchases_during=record.purchases_during,
            redemptions_during=record.redemptions_during,
            expected_start_total=record.expected_start_total,
            expected_start_redeemable=record.expected_start_redeemable,
            discoverable_sc=record.discoverable_sc,
            delta_total=record.delta_total,
            delta_redeem=record.delta_redeem,
            session_basis=record.session_basis,
            basis_consumed=record.basis_consumed,
            net_taxable_pl=record.net_taxable_pl,
            tax_withholding_rate_pct=record.tax_withholding_rate_pct,
            tax_withholding_is_custom=record.tax_withholding_is_custom,
            tax_withholding_amount=record.tax_withholding_amount,
            status=record.status,
            notes=record.notes,
            deleted_at=record.deleted_at,
            user_name=user_name,
            site_name=site_name,
            game_name=game_name,
            game_type_name=game_type_name,
        )
