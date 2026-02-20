"""
Adjustment repository - Data access for Adjustment entity
"""
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from models.adjustment import Adjustment, AdjustmentType
from tools.timezone_utils import (
    get_accounting_timezone_name,
    get_entry_timezone_name,
    local_date_range_to_utc_bounds,
    local_date_time_to_utc,
    utc_date_time_to_local,
)


class AdjustmentRepository:
    """Repository for Adjustment entity"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self._redemptions_column_cache = {}

    def _has_redemptions_column(self, column_name: str) -> bool:
        cached = self._redemptions_column_cache.get(column_name)
        if cached is not None:
            return cached
        try:
            rows = self.db.fetch_all("PRAGMA table_info(redemptions)")
            exists = any((row[1] if not isinstance(row, dict) else row.get("name")) == column_name for row in rows)
        except Exception:
            exists = False
        self._redemptions_column_cache[column_name] = exists
        return exists
    
    def get_by_id(self, adjustment_id: int) -> Optional[Adjustment]:
        """Get adjustment by ID"""
        query = "SELECT * FROM account_adjustments WHERE id = ?"
        row = self.db.fetch_one(query, (adjustment_id,))
        return self._row_to_model(row) if row else None
    
    def get_all(
        self,
        user_id: Optional[int] = None,
        site_id: Optional[int] = None,
        adjustment_type: Optional[AdjustmentType] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get all adjustments with optional filters"""
        query = """
            SELECT a.*, 
                   u.name as user_name,
                   s.name as site_name
            FROM account_adjustments a
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN sites s ON a.site_id = s.id
            WHERE 1=1
        """
        params = []
        tz_name = get_accounting_timezone_name()
        
        if not include_deleted:
            query += " AND a.deleted_at IS NULL"
        
        if user_id:
            query += " AND a.user_id = ?"
            params.append(user_id)
        
        if site_id:
            query += " AND a.site_id = ?"
            params.append(site_id)
        
        if adjustment_type:
            query += " AND a.type = ?"
            params.append(adjustment_type.value)
        
        if start_date:
            start_utc, _ = local_date_range_to_utc_bounds(start_date, start_date, tz_name)
            query += " AND (a.effective_date > ? OR (a.effective_date = ? AND COALESCE(a.effective_time, '00:00:00') >= ?))"
            params.extend([start_utc[0], start_utc[0], start_utc[1]])
        
        if end_date:
            _, end_utc = local_date_range_to_utc_bounds(end_date, end_date, tz_name)
            query += " AND (a.effective_date < ? OR (a.effective_date = ? AND COALESCE(a.effective_time, '00:00:00') <= ?))"
            params.extend([end_utc[0], end_utc[0], end_utc[1]])
        
        query += " ORDER BY a.effective_date DESC, a.effective_time DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_by_user_and_site(
        self,
        user_id: int,
        site_id: int,
        include_deleted: bool = False
    ) -> List[Adjustment]:
        """Get adjustments for a specific user and site"""
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? AND site_id = ?
        """
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        
        query += " ORDER BY effective_date ASC, effective_time ASC"
        
        rows = self.db.fetch_all(query, (user_id, site_id))
        return [self._row_to_model(row) for row in rows]

    def get_by_related(
        self,
        related_table: str,
        related_id: int,
        include_deleted: bool = False,
    ) -> List[Adjustment]:
        """Get adjustments explicitly linked to a record via related_table/related_id."""
        query = """
            SELECT *
            FROM account_adjustments
            WHERE related_table = ?
              AND related_id = ?
        """
        params: list = [related_table, related_id]
        if not include_deleted:
            query += " AND deleted_at IS NULL"
        query += " ORDER BY effective_date DESC, effective_time DESC"
        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_active_checkpoints_before(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "23:59:59"
    ) -> List[Adjustment]:
        """Get active balance checkpoint adjustments before a cutoff datetime"""
        tz_name = get_entry_timezone_name()
        cutoff_date_str, cutoff_time_str = local_date_time_to_utc(
            cutoff_date,
            cutoff_time,
            tz_name,
        )
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? 
            AND site_id = ?
            AND type = ?
            AND deleted_at IS NULL
            AND (
                effective_date < ?
                OR (effective_date = ? AND effective_time <= ?)
            )
            ORDER BY effective_date DESC, effective_time DESC
        """
        rows = self.db.fetch_all(
            query,
            (
                user_id,
                site_id,
                AdjustmentType.BALANCE_CHECKPOINT_CORRECTION.value,
                cutoff_date_str,
                cutoff_date_str,
                cutoff_time_str,
            )
        )
        return [self._row_to_model(row) for row in rows]

    def get_active_checkpoints_after(
        self,
        user_id: int,
        site_id: int,
        cutoff_date: date,
        cutoff_time: str = "00:00:00",
    ) -> List[Adjustment]:
        """Get active balance checkpoint adjustments strictly after a cutoff datetime.

        Returns checkpoints ordered ASC by effective datetime (earliest first).
        """
        query = """
            SELECT * FROM account_adjustments
            WHERE user_id = ?
              AND site_id = ?
              AND type = ?
              AND deleted_at IS NULL
              AND (
                effective_date > ?
                OR (effective_date = ? AND effective_time > ?)
              )
            ORDER BY effective_date ASC, effective_time ASC
        """
        tz_name = get_entry_timezone_name()
        cutoff_date_str, cutoff_time_str = local_date_time_to_utc(
            cutoff_date,
            cutoff_time,
            tz_name,
        )
        rows = self.db.fetch_all(
            query,
            (
                user_id,
                site_id,
                AdjustmentType.BALANCE_CHECKPOINT_CORRECTION.value,
                cutoff_date_str,
                cutoff_date_str,
                cutoff_time_str,
            ),
        )
        return [self._row_to_model(row) for row in rows]

    def get_active_adjustments_in_window(
        self,
        user_id: int,
        site_id: int,
        start_date: Optional[date] = None,
        start_time: str = "00:00:00",
        end_date: Optional[date] = None,
        end_time: str = "23:59:59",
    ) -> List[Adjustment]:
        """Get active adjustments/checkpoints in an inclusive datetime window.

        Notes:
        - Filters to non-deleted rows.
        - Applies inclusive bounds when provided.
        - Orders ASC by effective datetime for stable window inspection.
        """
        query = """
            SELECT *
            FROM account_adjustments
            WHERE user_id = ?
              AND site_id = ?
              AND deleted_at IS NULL
        """
        params: list = [user_id, site_id]
        tz_name = get_entry_timezone_name()

        if start_date is not None:
            start_date_str, start_time_str = local_date_time_to_utc(
                start_date,
                start_time or "00:00:00",
                tz_name,
            )
            query += " AND (effective_date > ? OR (effective_date = ? AND effective_time >= ?))"
            params.extend([start_date_str, start_date_str, start_time_str])

        if end_date is not None:
            end_date_str, end_time_str = local_date_time_to_utc(
                end_date,
                end_time or "23:59:59",
                tz_name,
            )
            query += " AND (effective_date < ? OR (effective_date = ? AND effective_time <= ?))"
            params.extend([end_date_str, end_date_str, end_time_str])

        query += " ORDER BY effective_date ASC, effective_time ASC"

        rows = self.db.fetch_all(query, tuple(params))
        return [self._row_to_model(row) for row in rows]
    
    def get_active_basis_adjustments(
        self,
        user_id: int,
        site_id: int
    ) -> List[Adjustment]:
        """Get all active basis adjustments for FIFO pipeline"""
        query = """
            SELECT * FROM account_adjustments 
            WHERE user_id = ? 
            AND site_id = ?
            AND type = ?
            AND deleted_at IS NULL
            ORDER BY effective_date ASC, effective_time ASC
        """
        rows = self.db.fetch_all(
            query,
            (user_id, site_id, AdjustmentType.BASIS_USD_CORRECTION.value)
        )
        return [self._row_to_model(row) for row in rows]
    
    def create(self, adjustment: Adjustment, *, auto_commit: bool = True) -> Adjustment:
        """Create a new adjustment"""
        entry_tz = adjustment.effective_entry_time_zone or get_entry_timezone_name()
        utc_date, utc_time = local_date_time_to_utc(
            adjustment.effective_date,
            adjustment.effective_time or "00:00:00",
            entry_tz,
        )
        query = """
            INSERT INTO account_adjustments (
                user_id, site_id, effective_date, effective_time, effective_entry_time_zone, type,
                delta_basis_usd, checkpoint_total_sc, checkpoint_redeemable_sc,
                reason, notes, related_table, related_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            adjustment.user_id,
            adjustment.site_id,
            utc_date,
            utc_time,
            entry_tz,
            adjustment.type.value if isinstance(adjustment.type, AdjustmentType) else adjustment.type,
            str(adjustment.delta_basis_usd),
            str(adjustment.checkpoint_total_sc),
            str(adjustment.checkpoint_redeemable_sc),
            adjustment.reason,
            adjustment.notes,
            adjustment.related_table,
            adjustment.related_id
        )
        
        if auto_commit:
            adjustment.id = self.db.execute(query, params)
        else:
            adjustment.id = self.db.execute_no_commit(query, params)
        adjustment.effective_entry_time_zone = entry_tz
        return adjustment
    
    def update(self, adjustment: Adjustment) -> bool:
        """Update an existing adjustment (limited fields)"""
        if not adjustment.id:
            raise ValueError("Adjustment ID is required for update")
        
        query = """
            UPDATE account_adjustments 
            SET notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        params = (
            adjustment.notes,
            adjustment.id
        )
        
        self.db.execute(query, params)
        return True
    
    def soft_delete(self, adjustment_id: int, reason: str, *, auto_commit: bool = True) -> bool:
        """Soft delete an adjustment"""
        query = """
            UPDATE account_adjustments 
            SET deleted_at = CURRENT_TIMESTAMP,
                deleted_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NULL
        """
        if auto_commit:
            self.db.execute(query, (reason, adjustment_id))
        else:
            self.db.execute_no_commit(query, (reason, adjustment_id))
        return True

    def get_downstream_activity_summary(
        self,
        *,
        user_id: int,
        site_id: int,
        effective_date: date,
        effective_time: str,
        exclude_adjustment_id: Optional[int] = None,
        effective_redemptions_only: bool = False,
    ) -> dict:
        """Return counts of later activity after a given effective timestamp.

        Used for UI warnings when soft-deleting an adjustment/checkpoint.

        Notes:
        - Only counts non-deleted rows.
        - Uses each table's primary timestamp fields.
        """
        tz_name = get_entry_timezone_name()
        date_str, time_str = local_date_time_to_utc(
            effective_date,
            effective_time or "00:00:00",
            tz_name,
        )

        def _count(query: str, params: tuple) -> int:
            row = self.db.fetch_one(query, params)
            if not row:
                return 0
            try:
                return int(row["cnt"])
            except Exception:
                try:
                    return int(list(row.values())[0])
                except Exception:
                    return 0

        purchases = _count(
            """
            SELECT COUNT(1) AS cnt
            FROM purchases
            WHERE deleted_at IS NULL
              AND user_id = ? AND site_id = ?
              AND (
                    purchase_date > ? OR
                    (purchase_date = ? AND COALESCE(purchase_time, '00:00:00') > ?)
                  )
            """,
            (user_id, site_id, date_str, date_str, time_str),
        )

        redemption_status_filter = ""
        if effective_redemptions_only and self._has_redemptions_column("redemption_status"):
            redemption_status_filter = " AND COALESCE(redemption_status, 'REDEEMED') NOT IN ('CANCELED', 'PENDING_UNCANCEL')"

        redemptions = _count(
            f"""
            SELECT COUNT(1) AS cnt
            FROM redemptions
            WHERE deleted_at IS NULL
              AND user_id = ? AND site_id = ?
              AND (
                    redemption_date > ? OR
                    (redemption_date = ? AND COALESCE(redemption_time, '00:00:00') > ?)
                  )
              {redemption_status_filter}
            """,
            (user_id, site_id, date_str, date_str, time_str),
        )

        sessions = _count(
            """
            SELECT COUNT(1) AS cnt
            FROM game_sessions
            WHERE deleted_at IS NULL
              AND user_id = ? AND site_id = ?
              AND (
                    COALESCE(end_date, session_date) > ? OR
                    (
                      COALESCE(end_date, session_date) = ?
                      AND COALESCE(end_time, session_time, '00:00:00') > ?
                    )
                  )
            """,
            (user_id, site_id, date_str, date_str, time_str),
        )

        params = [user_id, site_id, date_str, date_str, time_str]
        extra = ""
        if exclude_adjustment_id is not None:
            extra = " AND id != ?"
            params.append(exclude_adjustment_id)

        later_adjustments = _count(
            f"""
            SELECT COUNT(1) AS cnt
            FROM account_adjustments
            WHERE deleted_at IS NULL
              AND user_id = ? AND site_id = ?
              AND (
                    effective_date > ? OR
                    (effective_date = ? AND COALESCE(effective_time, '00:00:00') > ?)
                  )
              {extra}
            """,
            tuple(params),
        )

        return {
            "purchases": purchases,
            "redemptions": redemptions,
            "sessions": sessions,
            "adjustments": later_adjustments,
        }
    
    def restore(self, adjustment_id: int, *, auto_commit: bool = True) -> bool:
        """Restore a soft-deleted adjustment"""
        query = """
            UPDATE account_adjustments 
            SET deleted_at = NULL,
                deleted_reason = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND deleted_at IS NOT NULL
        """
        if auto_commit:
            self.db.execute(query, (adjustment_id,))
        else:
            self.db.execute_no_commit(query, (adjustment_id,))
        return True
    
    def _row_to_model(self, row) -> Optional[Adjustment]:
        """Convert database row to Adjustment model"""
        if not row:
            return None
        
        # Parse datetime fields
        created_at = None
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'])
            except (ValueError, TypeError):
                pass
        
        updated_at = None
        if row['updated_at']:
            try:
                updated_at = datetime.fromisoformat(row['updated_at'])
            except (ValueError, TypeError):
                pass
        
        deleted_at = None
        if row['deleted_at']:
            try:
                deleted_at = datetime.fromisoformat(row['deleted_at'])
            except (ValueError, TypeError):
                pass
        
        # Parse date
        effective_date = row['effective_date']
        if isinstance(effective_date, str):
            effective_date = date.fromisoformat(effective_date)

        entry_tz = row.get('effective_entry_time_zone') or get_accounting_timezone_name()
        effective_date, effective_time = utc_date_time_to_local(
            effective_date,
            row['effective_time'] or "00:00:00",
            entry_tz,
        )
        
        return Adjustment(
            id=row['id'],
            user_id=row['user_id'],
            site_id=row['site_id'],
            effective_date=effective_date,
            effective_time=effective_time or "00:00:00",
            effective_entry_time_zone=row.get('effective_entry_time_zone') or entry_tz,
            type=AdjustmentType(row['type']),
            delta_basis_usd=Decimal(row['delta_basis_usd']),
            checkpoint_total_sc=Decimal(row['checkpoint_total_sc']),
            checkpoint_redeemable_sc=Decimal(row['checkpoint_redeemable_sc']),
            reason=row['reason'],
            notes=row['notes'],
            related_table=row['related_table'],
            related_id=row['related_id'],
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            deleted_reason=row['deleted_reason']
        )
