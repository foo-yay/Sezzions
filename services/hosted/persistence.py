"""Hosted persistence primitives for account/workspace bootstrap."""

from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class HostedBase(DeclarativeBase):
    """Base metadata for hosted persistence models."""


class HostedAccountRecord(HostedBase):
    __tablename__ = "hosted_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="owner")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    supabase_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedWorkspaceRecord(HostedBase):
    __tablename__ = "hosted_workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_db_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedUserRecord(HostedBase):
    __tablename__ = "hosted_users"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedSiteRecord(HostedBase):
    __tablename__ = "hosted_sites"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sc_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    playthrough_requirement: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedCardRecord(HostedBase):
    __tablename__ = "hosted_cards"
    __table_args__ = (Index("idx_hosted_cards_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_four: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cashback_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRedemptionMethodTypeRecord(HostedBase):
    __tablename__ = "hosted_redemption_method_types"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRedemptionMethodRecord(HostedBase):
    __tablename__ = "hosted_redemption_methods"
    __table_args__ = (Index("idx_hosted_redemption_methods_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_redemption_method_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedGameTypeRecord(HostedBase):
    __tablename__ = "hosted_game_types"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedGameRecord(HostedBase):
    __tablename__ = "hosted_games"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    game_type_id: Mapped[str] = mapped_column(ForeignKey("hosted_game_types.id", ondelete="CASCADE"), nullable=False, index=True)
    rtp: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_rtp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedPurchaseRecord(HostedBase):
    __tablename__ = "hosted_purchases"
    __table_args__ = (
        Index("idx_hosted_purchases_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_purchases_date", "purchase_date", "purchase_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    sc_received: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    starting_sc_balance: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    starting_redeemable_balance: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    cashback_earned: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    cashback_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    purchase_date: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    purchase_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_cards.id", ondelete="SET NULL"), nullable=True, index=True)
    remaining_amount: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedUnrealizedPositionRecord(HostedBase):
    __tablename__ = "hosted_unrealized_positions"
    __table_args__ = (UniqueConstraint("workspace_id", "site_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRedemptionRecord(HostedBase):
    __tablename__ = "hosted_redemptions"
    __table_args__ = (
        Index("idx_hosted_redemptions_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_redemptions_date", "redemption_date", "redemption_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    fees: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    redemption_date: Mapped[str] = mapped_column(String(32), nullable=False)
    redemption_time: Mapped[str] = mapped_column(String(32), nullable=False, default="00:00:00")
    redemption_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    redemption_method_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_redemption_methods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_free_sc: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    receipt_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    more_remaining: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="PENDING")
    canceled_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedGameSessionRecord(HostedBase):
    __tablename__ = "hosted_game_sessions"
    __table_args__ = (
        Index("idx_hosted_game_sessions_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_game_sessions_date", "session_date", "session_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_games.id", ondelete="CASCADE"), nullable=True, index=True)
    game_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_game_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    session_time: Mapped[str] = mapped_column(String(32), nullable=False, default="00:00:00")
    start_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    starting_balance: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    ending_balance: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    starting_redeemable: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    ending_redeemable: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    wager_amount: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    rtp: Mapped[float | None] = mapped_column(Float, nullable=True)
    purchases_during: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    redemptions_during: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    expected_start_total: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expected_start_redeemable: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discoverable_sc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delta_total: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delta_redeem: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_basis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    basis_consumed: Mapped[str | None] = mapped_column(String(32), nullable=True)
    net_taxable_pl: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tax_withholding_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_withholding_is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_withholding_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="Active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedGameSessionEventLinkRecord(HostedBase):
    __tablename__ = "hosted_game_session_event_links"
    __table_args__ = (
        UniqueConstraint("workspace_id", "game_session_id", "event_type", "event_id", "relation"),
        Index("idx_hosted_gsel_event", "event_type", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    game_session_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_game_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedGameRtpAggregateRecord(HostedBase):
    __tablename__ = "hosted_game_rtp_aggregates"
    __table_args__ = (UniqueConstraint("workspace_id", "game_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("hosted_games.id", ondelete="CASCADE"), nullable=False, index=True)
    total_wager: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    session_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_updated: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRedemptionAllocationRecord(HostedBase):
    __tablename__ = "hosted_redemption_allocations"
    __table_args__ = (UniqueConstraint("workspace_id", "redemption_id", "purchase_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    redemption_id: Mapped[str] = mapped_column(ForeignKey("hosted_redemptions.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_id: Mapped[str] = mapped_column(ForeignKey("hosted_purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    allocated_amount: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRealizedTransactionRecord(HostedBase):
    __tablename__ = "hosted_realized_transactions"
    __table_args__ = (Index("idx_hosted_realized_workspace_user_site", "workspace_id", "user_id", "site_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    redemption_date: Mapped[str] = mapped_column(String(32), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    redemption_id: Mapped[str] = mapped_column(ForeignKey("hosted_redemptions.id", ondelete="CASCADE"), nullable=False, index=True)
    cost_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    payout: Mapped[str] = mapped_column(String(32), nullable=False)
    net_pl: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRealizedDailyNoteRecord(HostedBase):
    __tablename__ = "hosted_realized_daily_notes"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedExpenseRecord(HostedBase):
    __tablename__ = "hosted_expenses"
    __table_args__ = (Index("idx_hosted_expenses_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    expense_date: Mapped[str] = mapped_column(String(32), nullable=False)
    expense_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_users.id", ondelete="SET NULL"), nullable=True, index=True)
    expense_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedDailySessionRecord(HostedBase):
    __tablename__ = "hosted_daily_sessions"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_other_income: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_session_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    num_game_sessions: Mapped[int] = mapped_column(nullable=False, default=0)
    num_other_income_items: Mapped[int] = mapped_column(nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedDailyDateTaxRecord(HostedBase):
    __tablename__ = "hosted_daily_date_tax"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    net_daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_withholding_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_withholding_is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_withholding_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedAccountAdjustmentRecord(HostedBase):
    __tablename__ = "hosted_account_adjustments"
    __table_args__ = (
        Index("idx_hosted_adjustments_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_adjustments_date", "effective_date", "effective_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_date: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_time: Mapped[str] = mapped_column(String(32), nullable=False, default="00:00:00")
    effective_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    delta_basis_usd: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    checkpoint_total_sc: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    checkpoint_redeemable_sc: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_table: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deleted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedAuditLogRecord(HostedBase):
    __tablename__ = "hosted_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    summary_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedSettingsRecord(HostedBase):
    __tablename__ = "hosted_settings"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedAccountingTimeZoneHistoryRecord(HostedBase):
    __tablename__ = "hosted_accounting_time_zone_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    effective_utc_timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    accounting_time_zone: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


def _ensure_hosted_schema_compatibility(engine) -> None:
    inspector = inspect(engine)

    if "hosted_accounts" in inspector.get_table_names():
        account_columns = {column["name"] for column in inspector.get_columns("hosted_accounts")}
        statements: list[str] = []

        if "auth_provider" not in account_columns:
            statements.append(
                "ALTER TABLE hosted_accounts ADD COLUMN auth_provider VARCHAR(32) NOT NULL DEFAULT 'google'"
            )
        if "role" not in account_columns:
            statements.append(
                "ALTER TABLE hosted_accounts ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'owner'"
            )
        if "status" not in account_columns:
            statements.append(
                "ALTER TABLE hosted_accounts ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active'"
            )

        if statements:
            with engine.begin() as connection:
                for statement in statements:
                    connection.execute(text(statement))

    _migrate_missing_columns(engine, inspector)
    _migrate_fk_ondelete_rules(engine, inspector)


# --- Missing column migration ---------------------------------------------


def _column_default_sql(column) -> str:
    """Return a SQL DEFAULT literal for a NOT NULL column being added to an existing table."""
    if column.default is not None:
        arg = column.default.arg
        if not callable(arg):
            if isinstance(arg, bool):
                return "TRUE" if arg else "FALSE"
            if isinstance(arg, (int, float)):
                return str(arg)
            if isinstance(arg, str):
                return f"'{arg}'"
    # Fallback based on column type
    type_name = type(column.type).__name__
    if type_name in ("String", "Text"):
        return "''"
    if type_name == "Boolean":
        return "FALSE"
    if type_name == "Float":
        return "0.0"
    return "''"


def _migrate_missing_columns(engine, inspector) -> None:
    """Add columns defined in ORM models but missing from live database tables.

    Idempotent: skips columns that already exist and tables not yet created.
    """
    existing_tables = set(inspector.get_table_names())
    statements: list[str] = []

    for table in HostedBase.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            if column.nullable:
                statements.append(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type} NULL"
                )
            else:
                default_val = _column_default_sql(column)
                statements.append(
                    f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type} NOT NULL DEFAULT {default_val}"
                )

    if statements:
        with engine.begin() as connection:
            for stmt in statements:
                connection.execute(text(stmt))


# --- FK ondelete migration ------------------------------------------------

# Maps Postgres pg_constraint confdeltype codes to ondelete keywords.
_PG_DELTYPE = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def _desired_fk_ondelete() -> dict[str, dict[str, str]]:
    """Return {table: {constraint_name: desired_ondelete}} derived from ORM models."""
    result: dict[str, dict[str, str]] = {}
    for table in HostedBase.metadata.sorted_tables:
        tbl_fks: dict[str, str] = {}
        for fk_constraint in table.foreign_key_constraints:
            rule = (fk_constraint.ondelete or "NO ACTION").upper()
            tbl_fks[fk_constraint.name] = rule
        if tbl_fks:
            result[table.name] = tbl_fks
    return result


def _migrate_fk_ondelete_rules(engine, inspector) -> None:
    """Ensure live Postgres FK constraints match the ondelete rules in the ORM models.

    Idempotent: skips constraints that already have the correct rule.
    """
    desired = _desired_fk_ondelete()
    existing_tables = set(inspector.get_table_names())
    statements: list[str] = []

    for table_name, fk_rules in desired.items():
        if table_name not in existing_tables:
            continue

        # Query actual ondelete behaviour from pg_constraint
        live_fks: dict[str, str] = {}
        for fk in inspector.get_foreign_keys(table_name):
            name = fk.get("name")
            if not name:
                continue
            live_fks[name] = True  # we know the constraint exists

        for constraint_name, desired_rule in fk_rules.items():
            if constraint_name not in live_fks:
                continue  # constraint doesn't exist yet (create_all will handle it)

            # We cannot cheaply read the current ondelete rule via the inspector,
            # so query pg_constraint directly.
            statements.append(
                f"DO $$ BEGIN "
                f"IF EXISTS ("
                f"  SELECT 1 FROM pg_constraint "
                f"  WHERE conname = '{constraint_name}' "
                f"  AND confdeltype != '{_ondelete_to_pg_code(desired_rule)}'"
                f") THEN "
                f"  ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}; "
                f"  {_build_add_constraint_sql(table_name, constraint_name, inspector, desired_rule)} "
                f"END IF; "
                f"END $$;"
            )

    if statements:
        with engine.begin() as connection:
            for stmt in statements:
                connection.execute(text(stmt))


def _ondelete_to_pg_code(rule: str) -> str:
    """Convert an ondelete keyword to a pg_constraint confdeltype code."""
    mapping = {"NO ACTION": "a", "RESTRICT": "r", "CASCADE": "c", "SET NULL": "n", "SET DEFAULT": "d"}
    return mapping.get(rule.upper(), "a")


def _build_add_constraint_sql(
    table_name: str, constraint_name: str, inspector, desired_rule: str
) -> str:
    """Build an ALTER TABLE ADD CONSTRAINT statement from the inspector metadata."""
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("name") == constraint_name:
            cols = ", ".join(fk["constrained_columns"])
            ref_table = fk["referred_table"]
            ref_cols = ", ".join(fk["referred_columns"])
            return (
                f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
                f"FOREIGN KEY ({cols}) REFERENCES {ref_table}({ref_cols}) ON DELETE {desired_rule};"
            )
    return ""


@lru_cache(maxsize=4)
def get_hosted_session_factory(sqlalchemy_url: str):
    engine = create_engine(sqlalchemy_url, future=True, pool_pre_ping=True)
    HostedBase.metadata.create_all(engine)
    _ensure_hosted_schema_compatibility(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)