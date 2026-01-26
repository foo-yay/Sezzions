"""
Repository for Expense database operations
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from models.expense import Expense


class ExpenseRepository:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_by_id(self, expense_id: int) -> Optional[Expense]:
        row = self.db.fetch_one(
            """
            SELECT e.*, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE e.id = ?
            """,
            (expense_id,)
        )
        return self._row_to_model(row) if row else None

    def get_all(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Expense]:
        query = """
            SELECT e.*, u.name as user_name
            FROM expenses e
            LEFT JOIN users u ON e.user_id = u.id
            WHERE 1=1
        """
        params = []
        if start_date:
            query += " AND e.expense_date >= ?"
            params.append(start_date.isoformat() if hasattr(start_date, "isoformat") else start_date)
        if end_date:
            query += " AND e.expense_date <= ?"
            params.append(end_date.isoformat() if hasattr(end_date, "isoformat") else end_date)
        query += " ORDER BY e.expense_date DESC, e.id DESC"
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]

    def create(self, expense: Expense) -> Expense:
        expense_id = self.db.execute(
            """
            INSERT INTO expenses (expense_date, expense_time, amount, vendor, description, category, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense.expense_date.isoformat(),
                expense.expense_time,
                str(expense.amount),
                expense.vendor,
                expense.description,
                expense.category,
                expense.user_id,
            ),
        )
        expense.id = expense_id
        return expense

    def update(self, expense: Expense) -> Expense:
        if not expense.id:
            raise ValueError("Cannot update expense without ID")
        self.db.execute(
            """
            UPDATE expenses
            SET expense_date = ?, expense_time = ?, amount = ?, vendor = ?, description = ?, category = ?,
                user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                expense.expense_date.isoformat(),
                expense.expense_time,
                str(expense.amount),
                expense.vendor,
                expense.description,
                expense.category,
                expense.user_id,
                expense.id,
            ),
        )
        return expense

    def delete(self, expense_id: int) -> None:
        self.db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

    def _row_to_model(self, row) -> Expense:
        expense_date = row["expense_date"]
        if isinstance(expense_date, str):
            expense_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
        expense = Expense(
            id=row["id"],
            expense_date=expense_date,
            amount=Decimal(str(row["amount"])),
            vendor=row["vendor"],
            description=row["description"] if "description" in row.keys() else None,
            category=row["category"] if "category" in row.keys() else None,
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            expense_time=row["expense_time"] if "expense_time" in row.keys() else None,
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )
        if "user_name" in row.keys():
            expense.user_name = row["user_name"]
        return expense
