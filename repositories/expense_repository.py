"""
Repository for Expense database operations
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal
from models.expense import Expense
from tools.timezone_utils import (
    get_configured_timezone_name,
    local_date_time_to_utc,
    local_date_range_to_utc_bounds,
    utc_date_time_to_local,
)


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
        tz_name = get_configured_timezone_name()
        if start_date:
            start_utc, _ = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            query += " AND (e.expense_date > ? OR (e.expense_date = ? AND COALESCE(e.expense_time, '00:00:00') >= ?))"
            params.extend([start_utc[0], start_utc[0], start_utc[1]])
        if end_date:
            _, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            query += " AND (e.expense_date < ? OR (e.expense_date = ? AND COALESCE(e.expense_time, '00:00:00') <= ?))"
            params.extend([end_utc[0], end_utc[0], end_utc[1]])
        query += " ORDER BY e.expense_date DESC, e.id DESC"
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]

    def create(self, expense: Expense) -> Expense:
        tz_name = get_configured_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            expense.expense_date,
            expense.expense_time,
            tz_name,
        )
        expense_id = self.db.execute(
            """
            INSERT INTO expenses (expense_date, expense_time, amount, vendor, description, category, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_date,
                utc_time,
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
        tz_name = get_configured_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            expense.expense_date,
            expense.expense_time,
            tz_name,
        )
        self.db.execute(
            """
            UPDATE expenses
            SET expense_date = ?, expense_time = ?, amount = ?, vendor = ?, description = ?, category = ?,
                user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                utc_date,
                utc_time,
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
        tz_name = get_configured_timezone_name()
        expense_date, expense_time = utc_date_time_to_local(
            expense_date,
            row["expense_time"] if "expense_time" in row.keys() else None,
            tz_name,
        )
        expense = Expense(
            id=row["id"],
            expense_date=expense_date,
            amount=Decimal(str(row["amount"])),
            vendor=row["vendor"],
            description=row["description"] if "description" in row.keys() else None,
            category=row["category"] if "category" in row.keys() else None,
            user_id=row["user_id"] if "user_id" in row.keys() else None,
            expense_time=expense_time,
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None,
        )
        if "user_name" in row.keys():
            expense.user_name = row["user_name"]
        return expense
