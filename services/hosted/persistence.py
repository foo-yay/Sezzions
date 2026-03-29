"""Hosted persistence primitives for account/workspace bootstrap."""

from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class HostedBase(DeclarativeBase):
    """Base metadata for hosted persistence models."""


class HostedAccountRecord(HostedBase):
    __tablename__ = "hosted_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    supabase_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)


class HostedWorkspaceRecord(HostedBase):
    __tablename__ = "hosted_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_accounts.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_db_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class HostedUserRecord(HostedBase):
    __tablename__ = "hosted_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_workspaces.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


@lru_cache(maxsize=4)
def get_hosted_session_factory(sqlalchemy_url: str):
    engine = create_engine(sqlalchemy_url, future=True, pool_pre_ping=True)
    HostedBase.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)