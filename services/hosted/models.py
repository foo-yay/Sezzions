"""Hosted account/workspace models for the shared backend path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HostedAccount:
    """Product account identity, distinct from business-domain players in `users`."""

    owner_email: str
    auth_provider: str = "google"
    supabase_user_id: Optional[str] = None
    id: Optional[str] = None

    def __post_init__(self) -> None:
        self.owner_email = self.owner_email.strip().lower()
        if not self.owner_email:
            raise ValueError("Hosted account owner email is required.")
        if self.auth_provider != "google":
            raise ValueError("Hosted account auth_provider must currently be 'google'.")


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
