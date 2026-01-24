"""
Expense service - business logic for Expenses
"""
from typing import List, Optional
from datetime import date
from decimal import Decimal
from models.expense import Expense
from repositories.expense_repository import ExpenseRepository


class ExpenseService:
    def __init__(self, expense_repo: ExpenseRepository):
        self.expense_repo = expense_repo

    def list_expenses(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Expense]:
        return self.expense_repo.get_all(start_date=start_date, end_date=end_date)

    def get_expense(self, expense_id: int) -> Optional[Expense]:
        return self.expense_repo.get_by_id(expense_id)

    def create_expense(
        self,
        expense_date: date,
        amount: Decimal,
        vendor: str,
        description: Optional[str] = None,
        category: str = "Other Expenses",
        user_id: Optional[int] = None,
    ) -> Expense:
        expense = Expense(
            id=None,
            expense_date=expense_date,
            amount=amount,
            vendor=vendor,
            description=description,
            category=category,
            user_id=user_id,
        )
        return self.expense_repo.create(expense)

    def update_expense(self, expense_id: int, **kwargs) -> Expense:
        expense = self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise ValueError(f"Expense {expense_id} not found")
        for key, value in kwargs.items():
            if hasattr(expense, key) and value is not None:
                setattr(expense, key, value)
        expense.__post_init__()
        return self.expense_repo.update(expense)

    def delete_expense(self, expense_id: int) -> None:
        self.expense_repo.delete(expense_id)
