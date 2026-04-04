"""Hosted account/workspace models for the shared backend path."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class HostedAccount:
    """Product account identity, distinct from business-domain players in `users`."""

    owner_email: str
    auth_provider: str = "google"
    role: str = "owner"
    status: str = "active"
    supabase_user_id: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.owner_email = self.owner_email.strip().lower()
        if not self.owner_email:
            raise ValueError("Hosted account owner email is required.")
        if self.auth_provider != "google":
            raise ValueError("Hosted account auth_provider must currently be 'google'.")
        if self.role not in {"owner", "administrator"}:
            raise ValueError("Hosted account role must currently be 'owner' or 'administrator'.")
        if self.status not in {"active", "disabled", "deleted"}:
            raise ValueError("Hosted account status must currently be 'active', 'disabled', or 'deleted'.")


@dataclass
class HostedWorkspace:
    """A tenant/workspace that owns imported and future Sezzions data."""

    name: str
    account_id: Optional[str] = None
    source_db_path: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Hosted workspace name is required.")


@dataclass
class HostedUser:
    """Business-domain user/player owned by a hosted workspace."""

    name: str
    workspace_id: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("User name is required")

        if self.email is not None:
            self.email = self.email.strip() or None

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "email": self.email,
            "notes": self.notes,
            "is_active": self.is_active,
        }


@dataclass
class HostedSite:
    """Sweepstakes site/casino owned by a hosted workspace."""

    name: str
    workspace_id: Optional[str] = None
    url: Optional[str] = None
    sc_rate: float = 1.0
    playthrough_requirement: float = 1.0
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Site name is required")

        if self.url is not None:
            self.url = self.url.strip() or None

        if self.notes is not None:
            self.notes = self.notes.strip() or None

        if self.sc_rate < 0:
            raise ValueError("SC rate must be non-negative")

        if self.playthrough_requirement < 0:
            raise ValueError("Playthrough requirement must be non-negative")

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "url": self.url,
            "sc_rate": self.sc_rate,
            "playthrough_requirement": self.playthrough_requirement,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedCard:
    """Payment card owned by a hosted workspace user."""

    name: str
    user_id: str
    workspace_id: Optional[str] = None
    last_four: Optional[str] = None
    cashback_rate: float = 0.0
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None
    user_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Card name is required")

        if not self.user_id:
            raise ValueError("User is required")

        if self.last_four is not None:
            self.last_four = self.last_four.strip() or None
            if self.last_four and len(self.last_four) != 4:
                raise ValueError("Last four must be exactly 4 characters")

        if self.cashback_rate < 0 or self.cashback_rate > 100:
            raise ValueError("Cashback rate must be between 0 and 100")

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "last_four": self.last_four,
            "cashback_rate": self.cashback_rate,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedRedemptionMethod:
    """Redemption method (e.g., 'Chase checking', 'Coinbase BTC') owned by a hosted workspace."""

    name: str
    method_type_id: str
    user_id: str
    workspace_id: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None
    user_name: Optional[str] = None
    method_type_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Redemption method name is required")

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "method_type_id": self.method_type_id,
            "method_type_name": self.method_type_name,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedRedemptionMethodType:
    """Redemption method type (e.g., Bank, Crypto, Check) owned by a hosted workspace."""

    name: str
    workspace_id: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Method type name is required")

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedGameType:
    """Game type (e.g., Slots, Table Games, Live Dealer) owned by a hosted workspace."""

    name: str
    workspace_id: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Game type name is required")

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedGame:
    """Game (e.g., 'Sugar Rush', 'Gates of Olympus') owned by a hosted workspace."""

    name: str
    game_type_id: str
    workspace_id: Optional[str] = None
    rtp: Optional[float] = None
    actual_rtp: float = 0.0
    is_active: bool = True
    notes: Optional[str] = None
    id: Optional[str] = None
    game_type_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Game name is required")

        if not self.game_type_id:
            raise ValueError("Game type is required")

        if self.rtp is not None:
            self.rtp = float(self.rtp)
            if not 0 <= self.rtp <= 100:
                raise ValueError("RTP must be between 0 and 100")

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "game_type_id": self.game_type_id,
            "game_type_name": self.game_type_name,
            "rtp": self.rtp,
            "actual_rtp": self.actual_rtp,
            "is_active": self.is_active,
            "notes": self.notes,
        }


@dataclass
class HostedPurchase:
    """A purchase transaction (FIFO cost-basis lot) owned by a hosted workspace."""

    user_id: str
    site_id: str
    amount: str
    purchase_date: str
    workspace_id: Optional[str] = None
    purchase_time: Optional[str] = None
    sc_received: Optional[str] = None
    starting_sc_balance: str = "0.00"
    starting_redeemable_balance: str = "0.00"
    cashback_earned: str = "0.00"
    cashback_is_manual: bool = False
    card_id: Optional[str] = None
    remaining_amount: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None
    id: Optional[str] = None
    # Joined display names
    user_name: Optional[str] = None
    site_name: Optional[str] = None
    card_name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("User is required")

        if not self.site_id:
            raise ValueError("Site is required")

        if not self.amount:
            raise ValueError("Amount is required")
        try:
            amt = Decimal(str(self.amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Amount must be a valid number") from exc
        if amt <= 0:
            raise ValueError("Amount must be greater than zero")
        self.amount = str(amt)

        if not self.purchase_date or not self.purchase_date.strip():
            raise ValueError("Purchase date is required")
        self.purchase_date = self.purchase_date.strip()

        if self.purchase_time is not None:
            self.purchase_time = self.purchase_time.strip() or None

        # Default sc_received to amount if not provided
        if self.sc_received is None:
            self.sc_received = self.amount
        else:
            try:
                Decimal(str(self.sc_received))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("SC received must be a valid number") from exc

        # Default remaining_amount to amount if not provided
        if self.remaining_amount is None:
            self.remaining_amount = self.amount

        if self.notes is not None:
            self.notes = self.notes.strip() or None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "amount": self.amount,
            "sc_received": self.sc_received,
            "starting_sc_balance": self.starting_sc_balance,
            "starting_redeemable_balance": self.starting_redeemable_balance,
            "cashback_earned": self.cashback_earned,
            "cashback_is_manual": self.cashback_is_manual,
            "purchase_date": self.purchase_date,
            "purchase_time": self.purchase_time,
            "card_id": self.card_id,
            "card_name": self.card_name,
            "remaining_amount": self.remaining_amount,
            "status": self.status,
            "notes": self.notes,
        }
