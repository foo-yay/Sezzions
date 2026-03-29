"""Persistence helpers for hosted product accounts."""

from __future__ import annotations

from sqlalchemy import select

from services.hosted.models import HostedAccount
from services.hosted.persistence import HostedAccountRecord


class HostedAccountRepository:
    def get_by_supabase_user_id(self, session, supabase_user_id: str) -> HostedAccount | None:
        record = session.scalar(
            select(HostedAccountRecord).where(HostedAccountRecord.supabase_user_id == supabase_user_id)
        )
        if record is None:
            return None
        return HostedAccount(
            id=record.id,
            owner_email=record.owner_email,
            auth_provider=record.auth_provider,
            supabase_user_id=record.supabase_user_id,
        )

    def create(
        self,
        session,
        *,
        owner_email: str,
        supabase_user_id: str,
        auth_provider: str = "google",
    ) -> HostedAccount:
        record = HostedAccountRecord(
            owner_email=owner_email,
            auth_provider=auth_provider,
            supabase_user_id=supabase_user_id,
        )
        session.add(record)
        session.flush()
        return HostedAccount(
            id=record.id,
            owner_email=record.owner_email,
            auth_provider=record.auth_provider,
            supabase_user_id=record.supabase_user_id,
        )

    def update_owner_email(self, session, *, supabase_user_id: str, owner_email: str) -> HostedAccount | None:
        record = session.scalar(
            select(HostedAccountRecord).where(HostedAccountRecord.supabase_user_id == supabase_user_id)
        )
        if record is None:
            return None

        record.owner_email = owner_email
        session.flush()
        return HostedAccount(
            id=record.id,
            owner_email=record.owner_email,
            auth_provider=record.auth_provider,
            supabase_user_id=record.supabase_user_id,
        )