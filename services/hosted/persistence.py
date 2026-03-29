"""Hosted persistence primitives for account/workspace bootstrap."""

from __future__ import annotations

from functools import lru_cache
from uuid import uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint, create_engine
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
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_workspaces.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HostedSiteRecord(HostedBase):
    __tablename__ = "hosted_sites"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sc_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    playthrough_requirement: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedCardRecord(HostedBase):
    __tablename__ = "hosted_cards"
    __table_args__ = (Index("idx_hosted_cards_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_four: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cashback_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedRedemptionMethodTypeRecord(HostedBase):
    __tablename__ = "hosted_redemption_method_types"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedRedemptionMethodRecord(HostedBase):
    __tablename__ = "hosted_redemption_methods"
    __table_args__ = (Index("idx_hosted_redemption_methods_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_redemption_method_types.id"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_users.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedGameTypeRecord(HostedBase):
    __tablename__ = "hosted_game_types"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedGameRecord(HostedBase):
    __tablename__ = "hosted_games"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    game_type_id: Mapped[str] = mapped_column(ForeignKey("hosted_game_types.id"), nullable=False, index=True)
    rtp: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_rtp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedPurchaseRecord(HostedBase):
    __tablename__ = "hosted_purchases"
    __table_args__ = (
        Index("idx_hosted_purchases_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_purchases_date", "purchase_date", "purchase_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    sc_received: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    starting_sc_balance: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    cashback_earned: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    cashback_is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    purchase_date: Mapped[str] = mapped_column(String(32), nullable=False)
    purchase_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    purchase_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_cards.id"), nullable=True, index=True)
    remaining_amount: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedUnrealizedPositionRecord(HostedBase):
    __tablename__ = "hosted_unrealized_positions"
    __table_args__ = (UniqueConstraint("workspace_id", "site_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedRedemptionRecord(HostedBase):
    __tablename__ = "hosted_redemptions"
    __table_args__ = (
        Index("idx_hosted_redemptions_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_redemptions_date", "redemption_date", "redemption_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    fees: Mapped[str] = mapped_column(String(32), nullable=False, default="0.00")
    redemption_date: Mapped[str] = mapped_column(String(32), nullable=False)
    redemption_time: Mapped[str] = mapped_column(String(32), nullable=False, default="00:00:00")
    redemption_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    redemption_method_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_redemption_methods.id"),
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


class HostedGameSessionRecord(HostedBase):
    __tablename__ = "hosted_game_sessions"
    __table_args__ = (
        Index("idx_hosted_game_sessions_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_game_sessions_date", "session_date", "session_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
    game_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_games.id"), nullable=True, index=True)
    game_type_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosted_game_types.id"),
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


class HostedGameSessionEventLinkRecord(HostedBase):
    __tablename__ = "hosted_game_session_event_links"
    __table_args__ = (
        UniqueConstraint("workspace_id", "game_session_id", "event_type", "event_id", "relation"),
        Index("idx_hosted_gsel_event", "event_type", "event_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    game_session_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_game_sessions.id"),
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
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    game_id: Mapped[str] = mapped_column(ForeignKey("hosted_games.id"), nullable=False, index=True)
    total_wager: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    session_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_updated: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRedemptionAllocationRecord(HostedBase):
    __tablename__ = "hosted_redemption_allocations"
    __table_args__ = (UniqueConstraint("workspace_id", "redemption_id", "purchase_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    redemption_id: Mapped[str] = mapped_column(ForeignKey("hosted_redemptions.id"), nullable=False, index=True)
    purchase_id: Mapped[str] = mapped_column(ForeignKey("hosted_purchases.id"), nullable=False, index=True)
    allocated_amount: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HostedRealizedTransactionRecord(HostedBase):
    __tablename__ = "hosted_realized_transactions"
    __table_args__ = (Index("idx_hosted_realized_workspace_user_site", "workspace_id", "user_id", "site_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    redemption_date: Mapped[str] = mapped_column(String(32), nullable=False)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    redemption_id: Mapped[str] = mapped_column(ForeignKey("hosted_redemptions.id"), nullable=False, index=True)
    cost_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    payout: Mapped[str] = mapped_column(String(32), nullable=False)
    net_pl: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedRealizedDailyNoteRecord(HostedBase):
    __tablename__ = "hosted_realized_daily_notes"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedExpenseRecord(HostedBase):
    __tablename__ = "hosted_expenses"
    __table_args__ = (Index("idx_hosted_expenses_workspace_user", "workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    expense_date: Mapped[str] = mapped_column(String(32), nullable=False)
    expense_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount: Mapped[str] = mapped_column(String(32), nullable=False)
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("hosted_users.id"), nullable=True, index=True)
    expense_entry_time_zone: Mapped[str | None] = mapped_column(String(128), nullable=True)


class HostedDailySessionRecord(HostedBase):
    __tablename__ = "hosted_daily_sessions"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    total_other_income: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_session_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    num_game_sessions: Mapped[int] = mapped_column(nullable=False, default=0)
    num_other_income_items: Mapped[int] = mapped_column(nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedDailyDateTaxRecord(HostedBase):
    __tablename__ = "hosted_daily_date_tax"
    __table_args__ = (UniqueConstraint("workspace_id", "session_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    net_daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_withholding_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_withholding_is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tax_withholding_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HostedAccountAdjustmentRecord(HostedBase):
    __tablename__ = "hosted_account_adjustments"
    __table_args__ = (
        Index("idx_hosted_adjustments_workspace_user_site", "workspace_id", "user_id", "site_id"),
        Index("idx_hosted_adjustments_date", "effective_date", "effective_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("hosted_workspaces.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("hosted_users.id"), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("hosted_sites.id"), nullable=False, index=True)
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


@lru_cache(maxsize=4)
def get_hosted_session_factory(sqlalchemy_url: str):
    engine = create_engine(sqlalchemy_url, future=True, pool_pre_ping=True)
    HostedBase.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)