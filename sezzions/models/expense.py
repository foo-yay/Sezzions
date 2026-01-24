"""
Expense model
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Expense:
    id: Optional[int]
    expense_date: date
    amount: Decimal
    vendor: str
    description: Optional[str] = None
    category: str = "Other Expenses"
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if isinstance(self.expense_date, str):
            self.expense_date = datetime.strptime(self.expense_date, "%Y-%m-%d").date()
        if not self.vendor or not self.vendor.strip():
            raise ValueError("Vendor is required")
        self.vendor = self.vendor.strip()
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if not self.category:
            self.category = "Other Expenses"
