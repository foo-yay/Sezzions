"""Hosted account/workspace models for the shared backend path."""

from __future__ import annotations

from dataclasses import dataclass
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
