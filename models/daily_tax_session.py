"""Daily session model"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class DailySession:
    session_date: str
    user_id: int
    total_other_income: float = 0.0
    total_session_pnl: float = 0.0
    net_daily_pnl: float = 0.0
    status: Optional[str] = None
    num_game_sessions: int = 0
    num_other_income_items: int = 0
    notes: Optional[str] = None
