"""Persistence helpers for hosted workspace-owned expenses."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import aliased

from services.hosted.models import HostedExpense
from services.hosted.persistence import (
    HostedExpenseRecord,
    HostedUserRecord,
)


class HostedExpenseRepository:
    def list_by_workspace_id(
        self,
        session,
        workspace_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HostedExpense]:
        user_alias = aliased(HostedUserRecord)
        query = (
            select(
                HostedExpenseRecord,
                user_alias.name.label("user_name"),
            )
            .outerjoin(user_alias, HostedExpenseRecord.user_id == user_alias.id)
            .where(HostedExpenseRecord.workspace_id == workspace_id)
            .order_by(
                HostedExpenseRecord.expense_date.desc(),
                HostedExpenseRecord.expense_time.desc(),
                HostedExpenseRecord.id.desc(),
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
            .select_from(HostedExpenseRecord)
            .where(HostedExpenseRecord.workspace_id == workspace_id)
        ) or 0

    def get_by_id_and_workspace_id(
        self,
        session,
        *,
        expense_id: str,
        workspace_id: str,
    ) -> HostedExpense | None:
        user_alias = aliased(HostedUserRecord)
        row = session.execute(
            select(
                HostedExpenseRecord,
                user_alias.name.label("user_name"),
            )
            .outerjoin(user_alias, HostedExpenseRecord.user_id == user_alias.id)
            .where(
                HostedExpenseRecord.id == expense_id,
                HostedExpenseRecord.workspace_id == workspace_id,
            )
        ).first()
        if row is None:
            return None
        return self._row_to_model(row)

    def create(
        self,
        session,
        *,
        workspace_id: str,
        expense_date: str,
        amount: str,
        vendor: str,
        expense_time: str | None = None,
        expense_entry_time_zone: str | None = None,
        description: str | None = None,
        category: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> HostedExpense:
        record = HostedExpenseRecord(
            workspace_id=workspace_id,
            expense_date=expense_date,
            expense_time=expense_time,
            expense_entry_time_zone=expense_entry_time_zone,
            amount=amount,
            vendor=vendor,
            description=description,
            category=category,
            user_id=user_id,
            notes=notes,
        )
        session.add(record)
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, expense_id=record.id, workspace_id=workspace_id
        )

    def update(
        self,
        session,
        *,
        expense_id: str,
        workspace_id: str,
        expense_date: str,
        amount: str,
        vendor: str,
        expense_time: str | None = None,
        expense_entry_time_zone: str | None = None,
        description: str | None = None,
        category: str | None = None,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> HostedExpense | None:
        record = session.scalar(
            select(HostedExpenseRecord).where(
                HostedExpenseRecord.id == expense_id,
                HostedExpenseRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return None

        record.expense_date = expense_date
        record.expense_time = expense_time
        record.expense_entry_time_zone = expense_entry_time_zone
        record.amount = amount
        record.vendor = vendor
        record.description = description
        record.category = category
        record.user_id = user_id
        record.notes = notes
        session.flush()
        return self.get_by_id_and_workspace_id(
            session, expense_id=record.id, workspace_id=workspace_id
        )

    def delete(self, session, *, expense_id: str, workspace_id: str) -> bool:
        record = session.scalar(
            select(HostedExpenseRecord).where(
                HostedExpenseRecord.id == expense_id,
                HostedExpenseRecord.workspace_id == workspace_id,
            )
        )
        if record is None:
            return False

        session.delete(record)
        session.flush()
        return True

    def delete_many(self, session, *, expense_ids: list[str], workspace_id: str) -> int:
        normalized_ids = list(dict.fromkeys(expense_ids))
        if not normalized_ids:
            return 0

        result = session.execute(
            delete(HostedExpenseRecord).where(
                HostedExpenseRecord.workspace_id == workspace_id,
                HostedExpenseRecord.id.in_(normalized_ids),
            )
        )
        session.flush()
        return int(result.rowcount or 0)

    @staticmethod
    def _row_to_model(row) -> HostedExpense:
        record = row[0] if hasattr(row, "__getitem__") else row
        user_name = row.user_name if hasattr(row, "user_name") else None
        return HostedExpense(
            id=record.id,
            workspace_id=record.workspace_id,
            expense_date=record.expense_date,
            expense_time=record.expense_time,
            expense_entry_time_zone=record.expense_entry_time_zone,
            amount=record.amount,
            vendor=record.vendor,
            description=record.description,
            category=record.category,
            user_id=record.user_id,
            notes=record.notes,
            user_name=user_name,
        )
