"""Recalculation service - rebuild derived data after edits.

This is the Sezzions OOP equivalent of legacy qt_app.py "Recalculate Everything" and
"scoped rebuild" flows.

This service orchestrates BOTH FIFO and session recalculation together, matching legacy
behavior where rebuild_all_derived() includes both rebuild_fifo=True and rebuild_sessions=True.

NOTE: This service intentionally operates directly on the DB for bulk operations.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING

from repositories.database import DatabaseManager

if TYPE_CHECKING:
    from services.game_session_service import GameSessionService


# Type alias for progress callback
ProgressCallback = Callable[[int, int, str], None]  # (current, total, message)


def _normalize_time(value: Optional[str]) -> str:
    if not value:
        return "00:00:00"
    value = value.strip()
    if len(value) == 5:
        return f"{value}:00"
    return value


def _to_dt(date_str: str, time_str: Optional[str]) -> datetime:
    return datetime.strptime(f"{date_str} {_normalize_time(time_str)}", "%Y-%m-%d %H:%M:%S")


_CLOSE_BALANCE_RE = re.compile(r"Net Loss:\s*\$([0-9,]+(?:\.[0-9]{1,2})?)")


def _parse_close_balance_loss(notes: Optional[str]) -> Optional[Decimal]:
    if not notes:
        return None
    match = _CLOSE_BALANCE_RE.search(notes)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    try:
        return Decimal(value)
    except Exception:
        return None


@dataclass(frozen=True)
class RebuildResult:
    """Result of a recalculation operation."""
    pairs_processed: int
    redemptions_processed: int
    allocations_written: int
    purchases_updated: int
    game_sessions_processed: int = 0
    errors: List[str] = None
    operation: Optional[str] = None  # Track which operation completed (all, pair, user, site, after_import)
    
    def __post_init__(self):
        """Initialize mutable fields."""
        if self.errors is None:
            object.__setattr__(self, 'errors', [])


class RecalculationService:
    """Bulk rebuild operations for derived accounting data.
    
    This service orchestrates BOTH:
    1. FIFO recalculation (redemption allocations, cost basis, realized transactions)
    2. Session recalculation (taxable P/L, redeemable balance calculations)
    
    Individual methods (_rebuild_fifo_only, _recalculate_sessions_only) exist for
    code organization, but user-facing operations always do both together.
    """

    def __init__(self, db: DatabaseManager, game_session_service: Optional['GameSessionService'] = None, tax_withholding_service=None, adjustment_service=None):
        self.db = db
        self._game_session_service = game_session_service
        self.tax_withholding_service = tax_withholding_service
        self.adjustment_service = adjustment_service

    @property
    def game_session_service(self) -> 'GameSessionService':
        """Lazy-load GameSessionService to avoid circular imports."""
        if self._game_session_service is None:
            from services.game_session_service import GameSessionService
            from repositories.game_session_repository import GameSessionRepository
            from repositories.purchase_repository import PurchaseRepository
            from repositories.redemption_repository import RedemptionRepository
            
            session_repo = GameSessionRepository(self.db)
            purchase_repo = PurchaseRepository(self.db)
            redemption_repo = RedemptionRepository(self.db)
            
            # Use keyword arguments to match GameSessionService signature
            self._game_session_service = GameSessionService(
                session_repo=session_repo,
                purchase_repo=purchase_repo,
                redemption_repo=redemption_repo
            )
        return self._game_session_service

    def iter_pairs(self) -> List[Tuple[int, int]]:
        """Return distinct (user_id, site_id) pairs with any activity."""
        rows = self.db.fetch_all(
            """
            SELECT DISTINCT user_id, site_id FROM purchases
            UNION
            SELECT DISTINCT user_id, site_id FROM redemptions WHERE deleted_at IS NULL AND canceled_at IS NULL
            UNION
            SELECT DISTINCT user_id, site_id FROM game_sessions
            UNION
            SELECT DISTINCT user_id, site_id FROM account_adjustments WHERE deleted_at IS NULL
            """
        )
        pairs: List[Tuple[int, int]] = []
        for r in rows:
            if "user_id" not in r.keys() or "site_id" not in r.keys():
                continue
            if r["user_id"] is None or r["site_id"] is None:
                continue
            pairs.append((int(r["user_id"]), int(r["site_id"])))
        pairs.sort()
        return pairs

    def rebuild_for_pair(
        self, 
        user_id: int, 
        site_id: int,
        progress_callback: Optional[ProgressCallback] = None
    ) -> RebuildResult:
        """Rebuild FIFO allocations + session P/L + cashback for one (user_id, site_id).
        
        This matches legacy rebuild_all_derived(rebuild_fifo=True, rebuild_sessions=True)
        for a single pair, plus cashback recalculation.
        """
        # Step 1: Rebuild FIFO
        if progress_callback:
            progress_callback(0, 3, f"Rebuilding FIFO for user {user_id}, site {site_id}")
        
        fifo_result = self._rebuild_fifo_for_pair(user_id, site_id)
        
        # Step 2: Recalculate sessions
        if progress_callback:
            progress_callback(1, 3, f"Recalculating sessions for user {user_id}, site {site_id}")
        
        sessions_updated = self.game_session_service.recalculate_all_sessions(user_id, site_id)
        
        # Step 3: Recalculate cashback
        if progress_callback:
            progress_callback(2, 3, f"Recalculating cashback for user {user_id}, site {site_id}")
        
        cashback_updated = self._recalculate_cashback_for_pair(user_id, site_id)
        
        if progress_callback:
            progress_callback(3, 3, f"Completed rebuild for user {user_id}, site {site_id}")
        
        return RebuildResult(
            pairs_processed=1,
            redemptions_processed=fifo_result.redemptions_processed,
            allocations_written=fifo_result.allocations_written,
            purchases_updated=fifo_result.purchases_updated,
            game_sessions_processed=sessions_updated,
        )

    def _rebuild_fifo_for_pair(
        self, 
        user_id: int, 
        site_id: int,
        progress_callback: Optional[ProgressCallback] = None
    ) -> RebuildResult:
        """Internal: Rebuild FIFO allocations + realized_transactions only (no session recalc)."""
        if progress_callback:
            progress_callback(0, 1, f"Rebuilding FIFO for user {user_id}, site {site_id}")
        
        conn = self.db._connection
        cursor = conn.cursor()

        # Fetch purchases
        cursor.execute(
            """
            SELECT id, amount, purchase_date, COALESCE(purchase_time,'00:00:00') AS pt
            FROM purchases
            WHERE user_id = ? AND site_id = ?
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        purchase_rows = cursor.fetchall()

        purchases: List[Tuple[int, datetime, Decimal]] = []
        remaining: Dict[int, Decimal] = {}
        for r in purchase_rows:
            purchase_id = int(r["id"])
            amt = Decimal(str(r["amount"]))
            dt = _to_dt(r["purchase_date"], r["pt"])
            purchases.append((purchase_id, dt, amt))
            remaining[purchase_id] = amt

        # Fetch basis adjustments and merge them as synthetic purchases
        # Adjustments with negative delta reduce basis, positive delta increases it
        # They participate in FIFO allocation chronologically
        if self.adjustment_service:
            basis_adjustments = self.adjustment_service.get_active_basis_adjustments(user_id, site_id)
            for adj in basis_adjustments:
                # Create synthetic purchase ID using negative numbers to avoid collisions
                synthetic_id = -(adj.id)
                dt = _to_dt(adj.effective_date, adj.effective_time)
                delta = adj.delta_basis_usd or Decimal("0.00")
                
                # Insert in chronological order
                purchases.append((synthetic_id, dt, delta))
                remaining[synthetic_id] = delta
            
            # Re-sort to ensure chronological order after merging adjustments
            purchases.sort(key=lambda x: (x[1], x[0]))  # Sort by datetime, then ID

        cursor.execute(
            """
                 SELECT id, amount, redemption_date, COALESCE(redemption_time,'00:00:00') AS rt,
                     COALESCE(is_free_sc, 0) AS is_free_sc, COALESCE(more_remaining, 0) AS more_remaining, notes
            FROM redemptions
            WHERE user_id = ? AND site_id = ? AND deleted_at IS NULL AND canceled_at IS NULL
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        redemption_rows = cursor.fetchall()

        redemption_ids = [int(r["id"]) for r in redemption_rows]

        # Clear existing derived records for this pair
        if redemption_ids:
            placeholders = ",".join(["?"] * len(redemption_ids))
            cursor.execute(
                f"DELETE FROM redemption_allocations WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )
        cursor.execute(
            "DELETE FROM realized_transactions WHERE user_id = ? AND site_id = ?",
            (user_id, site_id),
        )

        allocations_to_write: List[Tuple[int, int, str]] = []
        realized_to_write: List[Tuple[str, int, int, int, str, str, str]] = []

        # Rebuild chronologically
        for red_row in redemption_rows:
            redemption_id = int(red_row["id"])
            payout = Decimal(str(red_row["amount"]))
            is_free_sc = bool(int(red_row["is_free_sc"] or 0))
            red_dt = _to_dt(red_row["redemption_date"], red_row["rt"])
            notes = red_row["notes"] if "notes" in red_row.keys() else None

            close_balance_loss = _parse_close_balance_loss(notes)
            if payout == 0 and close_balance_loss is not None:
                cost_basis = close_balance_loss
                net_pl = -close_balance_loss
                realized_to_write.append(
                    (
                        red_row["redemption_date"],
                        site_id,
                        user_id,
                        redemption_id,
                        str(cost_basis),
                        str(payout),
                        str(net_pl),
                    )
                )
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                # Check if this is a Full redemption (more_remaining=False/0)
                more_remaining = bool(int(red_row["more_remaining"] if "more_remaining" in red_row.keys() else 1))
                
                if not more_remaining:
                    # Full redemption: consume ALL remaining basis up to this timestamp
                    remaining_to_allocate = sum(
                        avail for pid, pdt, _pamt in purchases 
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                else:
                    # Partial redemption: just allocate the payout amount
                    remaining_to_allocate = payout
                
                for purchase_id, purchase_dt, _purchase_amt in purchases:
                    if remaining_to_allocate <= 0:
                        break
                    if purchase_dt > red_dt:
                        break

                    avail = remaining.get(purchase_id, Decimal("0.00"))
                    if avail <= 0:
                        continue

                    alloc = min(avail, remaining_to_allocate)
                    if alloc <= 0:
                        continue

                    remaining[purchase_id] = avail - alloc
                    remaining_to_allocate -= alloc
                    cost_basis += alloc
                    
                    # Only write allocations for actual purchases (positive IDs), not synthetic adjustments
                    if purchase_id > 0:
                        allocations_to_write.append((redemption_id, purchase_id, str(alloc)))

            net_pl = payout - cost_basis
            realized_to_write.append(
                (
                    red_row["redemption_date"],
                    site_id,
                    user_id,
                    redemption_id,
                    str(cost_basis),
                    str(payout),
                    str(net_pl),
                )
            )

        # Write updated remaining_amount for all purchases in pair (excluding synthetic adjustment IDs)
        purchases_updated = 0
        for purchase_id, _dt, _amt in purchases:
            # Skip synthetic adjustment IDs (negative)
            if purchase_id < 0:
                continue
            cursor.execute(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(remaining[purchase_id]), purchase_id),
            )
            purchases_updated += 1

        if allocations_to_write:
            cursor.executemany(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                allocations_to_write,
            )

        if realized_to_write:
            cursor.executemany(
                """
                INSERT INTO realized_transactions
                    (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                realized_to_write,
            )

        conn.commit()
        
        if progress_callback:
            progress_callback(1, 1, f"Completed FIFO rebuild for user {user_id}, site {site_id}")

        return RebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    def rebuild_fifo_for_pair_from(
        self,
        user_id: int,
        site_id: int,
        from_date: str,
        from_time: Optional[str] = None,
    ) -> RebuildResult:
        """Scoped FIFO rebuild starting at a boundary redemption timestamp."""
        conn = self.db._connection
        cursor = conn.cursor()
        from_time = _normalize_time(from_time)

        cursor.execute(
            """
            SELECT id, amount, purchase_date, COALESCE(purchase_time,'00:00:00') AS pt
            FROM purchases
            WHERE user_id = ? AND site_id = ?
            ORDER BY purchase_date ASC, COALESCE(purchase_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id),
        )
        purchase_rows = cursor.fetchall()

        purchases: List[Tuple[int, datetime, Decimal]] = []
        remaining: Dict[int, Decimal] = {}
        for r in purchase_rows:
            purchase_id = int(r["id"])
            amt = Decimal(str(r["amount"]))
            dt = _to_dt(r["purchase_date"], r["pt"])
            purchases.append((purchase_id, dt, amt))
            remaining[purchase_id] = amt

        # Fetch basis adjustments and merge them as synthetic purchases
        if self.adjustment_service:
            basis_adjustments = self.adjustment_service.get_active_basis_adjustments(user_id, site_id)
            for adj in basis_adjustments:
                # Create synthetic purchase ID using negative numbers to avoid collisions
                synthetic_id = -(adj.id)
                dt = _to_dt(adj.effective_date, adj.effective_time)
                delta = adj.delta_basis_usd or Decimal("0.00")
                
                # Insert in chronological order
                purchases.append((synthetic_id, dt, delta))
                remaining[synthetic_id] = delta
            
            # Re-sort to ensure chronological order after merging adjustments
            purchases.sort(key=lambda x: (x[1], x[0]))  # Sort by datetime, then ID

        cursor.execute(
            """
            SELECT ra.purchase_id, ra.allocated_amount
            FROM redemption_allocations ra
            JOIN redemptions r ON ra.redemption_id = r.id
            WHERE r.user_id = ? AND r.site_id = ?
                            AND r.deleted_at IS NULL
                            AND r.canceled_at IS NULL
              AND (r.redemption_date < ?
                   OR (r.redemption_date = ? AND COALESCE(r.redemption_time,'00:00:00') < ?))
            """,
            (user_id, site_id, from_date, from_date, from_time),
        )
        allocation_rows = cursor.fetchall()
        for row in allocation_rows:
            purchase_id = int(row["purchase_id"])
            allocated = Decimal(str(row["allocated_amount"]))
            if purchase_id in remaining:
                remaining[purchase_id] = max(Decimal("0.00"), remaining[purchase_id] - allocated)

        cursor.execute(
            """
            SELECT id, amount, redemption_date, COALESCE(redemption_time,'00:00:00') AS rt,
                   COALESCE(is_free_sc, 0) AS is_free_sc, COALESCE(more_remaining, 0) AS more_remaining, notes
                        FROM redemptions
                            WHERE user_id = ? AND site_id = ? AND deleted_at IS NULL AND canceled_at IS NULL
              AND (redemption_date > ?
                   OR (redemption_date = ? AND COALESCE(redemption_time,'00:00:00') >= ?))
            ORDER BY redemption_date ASC, COALESCE(redemption_time,'00:00:00') ASC, id ASC
            """,
            (user_id, site_id, from_date, from_date, from_time),
        )
        redemption_rows = cursor.fetchall()

        redemption_ids = [int(r["id"]) for r in redemption_rows]
        if redemption_ids:
            placeholders = ",".join(["?"] * len(redemption_ids))
            cursor.execute(
                f"DELETE FROM redemption_allocations WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )
            cursor.execute(
                f"DELETE FROM realized_transactions WHERE redemption_id IN ({placeholders})",
                tuple(redemption_ids),
            )

        allocations_to_write: List[Tuple[int, int, str]] = []
        realized_to_write: List[Tuple[str, int, int, int, str, str, str]] = []

        for red_row in redemption_rows:
            redemption_id = int(red_row["id"])
            payout = Decimal(str(red_row["amount"]))
            is_free_sc = bool(int(red_row["is_free_sc"] or 0))
            red_dt = _to_dt(red_row["redemption_date"], red_row["rt"])
            notes = red_row["notes"] if "notes" in red_row.keys() else None

            close_balance_loss = _parse_close_balance_loss(notes)
            if payout == 0 and close_balance_loss is not None:
                cost_basis = close_balance_loss
                net_pl = -close_balance_loss
                realized_to_write.append(
                    (
                        red_row["redemption_date"],
                        site_id,
                        user_id,
                        redemption_id,
                        str(cost_basis),
                        str(payout),
                        str(net_pl),
                    )
                )
                continue

            cost_basis = Decimal("0.00")
            if not is_free_sc and payout > 0:
                # Check if this is a Full redemption (more_remaining=False/0)
                more_remaining = bool(int(red_row["more_remaining"] if "more_remaining" in red_row.keys() else 1))
                
                if not more_remaining:
                    # Full redemption: consume ALL remaining basis up to this timestamp
                    remaining_to_allocate = sum(
                        avail for pid, pdt, _pamt in purchases 
                        if pdt <= red_dt and (avail := remaining.get(pid, Decimal("0.00"))) > 0
                    )
                else:
                    # Partial redemption: just allocate the payout amount
                    remaining_to_allocate = payout
                
                for purchase_id, purchase_dt, _purchase_amt in purchases:
                    if remaining_to_allocate <= 0:
                        break
                    if purchase_dt > red_dt:
                        break

                    avail = remaining.get(purchase_id, Decimal("0.00"))
                    if avail <= 0:
                        continue

                    alloc = min(avail, remaining_to_allocate)
                    if alloc <= 0:
                        continue

                    remaining[purchase_id] = avail - alloc
                    remaining_to_allocate -= alloc
                    cost_basis += alloc
                    
                    # Only write allocations for actual purchases (positive IDs), not synthetic adjustments
                    if purchase_id > 0:
                        allocations_to_write.append((redemption_id, purchase_id, str(alloc)))

            net_pl = payout - cost_basis
            realized_to_write.append(
                (
                    red_row["redemption_date"],
                    site_id,
                    user_id,
                    redemption_id,
                    str(cost_basis),
                    str(payout),
                    str(net_pl),
                )
            )

        purchases_updated = 0
        for purchase_id, _dt, _amt in purchases:
            # Skip synthetic adjustment IDs (negative)
            if purchase_id < 0:
                continue
            cursor.execute(
                "UPDATE purchases SET remaining_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(remaining[purchase_id]), purchase_id),
            )
            purchases_updated += 1

        if allocations_to_write:
            cursor.executemany(
                """
                INSERT INTO redemption_allocations (redemption_id, purchase_id, allocated_amount)
                VALUES (?, ?, ?)
                """,
                allocations_to_write,
            )

        if realized_to_write:
            cursor.executemany(
                """
                INSERT INTO realized_transactions
                    (redemption_date, site_id, user_id, redemption_id, cost_basis, payout, net_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                realized_to_write,
            )

        conn.commit()

        return RebuildResult(
            pairs_processed=1,
            redemptions_processed=len(redemption_rows),
            allocations_written=len(allocations_to_write),
            purchases_updated=purchases_updated,
        )

    def _recalculate_cashback_for_pair(self, user_id: int, site_id: int) -> int:
        """Recalculate cashback for all purchases with cards for a user/site pair.
        
        Returns:
            Number of purchases updated
        """
        conn = self.db._connection
        cursor = conn.cursor()
        
        # Get all purchases with cards for this pair (skip manually set cashback)
        cursor.execute(
            """
            SELECT p.id, p.amount, c.cashback_rate
            FROM purchases p
            JOIN cards c ON p.card_id = c.id
            WHERE p.user_id = ? AND p.site_id = ? 
              AND p.card_id IS NOT NULL
              AND (p.cashback_is_manual = 0 OR p.cashback_is_manual IS NULL)
            """,
            (user_id, site_id)
        )
        
        purchases = cursor.fetchall()
        updated_count = 0
        
        for purchase in purchases:
            purchase_id = purchase[0]
            amount = Decimal(str(purchase[1]))
            cashback_rate = Decimal(str(purchase[2]))
            
            # Calculate: amount * (rate / 100)
            cashback = (amount * cashback_rate / Decimal("100")).quantize(Decimal("0.01"))
            
            # Update the purchase
            cursor.execute(
                "UPDATE purchases SET cashback_earned = ? WHERE id = ?",
                (str(cashback), purchase_id)
            )
            updated_count += 1
        
        conn.commit()
        return updated_count

    def _sync_daily_sessions(self, progress_callback: Optional[ProgressCallback] = None):
        """Synchronize daily_sessions table from closed game_sessions.
        
        Populates daily_sessions with aggregated P/L data from closed sessions.
        Uses INSERT OR REPLACE to handle both new and existing rows.
        Notes are stored in daily_date_tax table (not here).
        Tax data is now stored in daily_date_tax table (see TaxWithholdingService).
        """
        if progress_callback:
            progress_callback(0, 1, "Synchronizing daily sessions from closed game sessions...")
        
        # Check if daily_sessions table exists first (for tests/old DBs)
        cursor = self.db._connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_sessions'")
        if not cursor.fetchone():
            return  # Table doesn't exist, skip sync
        
        self.db.execute(
            """
            INSERT OR REPLACE INTO daily_sessions (
                session_date, 
                user_id, 
                net_daily_pnl, 
                num_game_sessions
            )
            SELECT 
                gs.end_date,
                gs.user_id,
                SUM(COALESCE(gs.net_taxable_pl, 0)) as net_daily_pnl,
                COUNT(*) as num_game_sessions
            FROM game_sessions gs
            WHERE gs.status = 'Closed' AND gs.end_date IS NOT NULL
            GROUP BY gs.end_date, gs.user_id
            """,
            ()
        )

    def rebuild_all(self, progress_callback: Optional[ProgressCallback] = None) -> RebuildResult:
        """Rebuild ALL derived data (FIFO + sessions + cashback + daily_sessions) for all pairs.
        
        This matches legacy recalculate_everything() which calls:
        rebuild_all_derived(rebuild_fifo=True, rebuild_sessions=True)
        
        Now also includes:
        - Cashback recalculation
        - Daily sessions synchronization
        """
        pairs = self.iter_pairs()
        total_pairs = len(pairs)
        total_steps = total_pairs * 3 + 2  # 3 steps per pair + RTP + daily_sessions
        
        redemptions_processed = 0
        allocations_written = 0
        purchases_updated = 0
        sessions_processed = 0
        cashback_updated = 0
        current_step = 0

        for idx, (user_id, site_id) in enumerate(pairs, 1):
            # Step 1: FIFO
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, 
                                f"[{idx}/{total_pairs}] Rebuilding FIFO for user {user_id}, site {site_id}")
            
            fifo_result = self._rebuild_fifo_for_pair(user_id, site_id)
            redemptions_processed += fifo_result.redemptions_processed
            allocations_written += fifo_result.allocations_written
            purchases_updated += fifo_result.purchases_updated
            
            # Step 2: Sessions
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps,
                                f"[{idx}/{total_pairs}] Recalculating sessions for user {user_id}, site {site_id}")
            
            sessions_count = self.game_session_service.recalculate_all_sessions(user_id, site_id)
            sessions_processed += sessions_count
            
            # Step 3: Cashback
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps,
                                f"[{idx}/{total_pairs}] Recalculating cashback for user {user_id}, site {site_id}")
            
            cashback_count = self._recalculate_cashback_for_pair(user_id, site_id)
            cashback_updated += cashback_count

        # Rebuild game RTP aggregates for all games
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Recalculating game RTP aggregates...")
        
        try:
            from repositories.game_repository import GameRepository
            game_repo = GameRepository(self.db)
            games = game_repo.get_all()
            for game in games:
                try:
                    self.game_session_service.recalculate_game_rtp_full(game.id)
                except Exception:
                    continue
        except Exception:
            pass

        # Synchronize daily_sessions table from closed game sessions
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Synchronizing daily sessions...")
        
        self._sync_daily_sessions(progress_callback)

        # Recalculate tax withholding (if enabled in settings)
        current_step += 1
        if progress_callback:
            progress_callback(current_step, total_steps, "Recalculating tax withholding...")
        
        try:
            if hasattr(self, 'tax_withholding_service'):
                config = self.tax_withholding_service.get_config()
                if config.enabled:
                    self.tax_withholding_service.bulk_recalculate(
                        start_date=None,
                        end_date=None,
                        overwrite_custom=False
                    )
        except Exception:
            pass

        return RebuildResult(
            pairs_processed=len(pairs),
            redemptions_processed=redemptions_processed,
            allocations_written=allocations_written,
            purchases_updated=purchases_updated,
            game_sessions_processed=sessions_processed,
        )
    
    def rebuild_after_import(
        self,
        entity_type: str,
        user_ids: Optional[List[int]] = None,
        site_ids: Optional[List[int]] = None,
        progress_callback: Optional[ProgressCallback] = None
    ) -> RebuildResult:
        """
        Rebuild FIFO after CSV import.
        
        Determines which pairs need recalculation based on imported entity type
        and affected IDs.
        
        Args:
            entity_type: Type of entity imported (purchases, redemptions, game_sessions)
            user_ids: List of affected user IDs (None = all)
            site_ids: List of affected site IDs (None = all)
            progress_callback: Optional progress tracking callback
        
        Returns:
            RebuildResult with stats
        
        Example:
            >>> # After importing purchases for user 1, site 1
            >>> result = service.rebuild_after_import(
            ...     entity_type='purchases',
            ...     user_ids=[1],
            ...     site_ids=[1]
            ... )
        """
        # Get all pairs
        all_pairs = self.iter_pairs()
        
        # Filter pairs based on affected IDs
        affected_pairs = []
        for user_id, site_id in all_pairs:
            if user_ids is not None and user_id not in user_ids:
                continue
            if site_ids is not None and site_id not in site_ids:
                continue
            affected_pairs.append((user_id, site_id))
        
        if not affected_pairs:
            return RebuildResult(
                pairs_processed=0,
                redemptions_processed=0,
                allocations_written=0,
                purchases_updated=0
            )
        
        # Rebuild affected pairs
        total_pairs = len(affected_pairs)
        redemptions_processed = 0
        allocations_written = 0
        purchases_updated = 0
        game_sessions_processed = 0
        
        for idx, (user_id, site_id) in enumerate(affected_pairs, 1):
            if progress_callback:
                progress_callback(
                    idx, total_pairs,
                    f"Recalculating after {entity_type} import: pair {idx}/{total_pairs}"
                )
            
            # Use full rebuild_for_pair to include FIFO + sessions + cashback
            result = self.rebuild_for_pair(user_id, site_id)
            redemptions_processed += result.redemptions_processed
            allocations_written += result.allocations_written
            purchases_updated += result.purchases_updated
            game_sessions_processed += result.game_sessions_processed
        
        return RebuildResult(
            pairs_processed=len(affected_pairs),
            redemptions_processed=redemptions_processed,
            allocations_written=allocations_written,
            purchases_updated=purchases_updated,
            game_sessions_processed=game_sessions_processed
        )
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get recalculation statistics.
        
        Returns counts of key entities for progress tracking.
        
        Returns:
            Dict with counts: pairs, purchases, redemptions, allocations, realized_transactions
        """
        conn = self.db._connection
        cursor = conn.cursor()
        
        # Count pairs
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id || '-' || site_id) FROM (
                SELECT user_id, site_id FROM purchases
                UNION
                SELECT user_id, site_id FROM redemptions
                UNION
                SELECT user_id, site_id FROM game_sessions
            )
        """)
        pairs_count = cursor.fetchone()[0]
        
        # Count purchases
        cursor.execute("SELECT COUNT(*) FROM purchases")
        purchases_count = cursor.fetchone()[0]
        
        # Count redemptions
        cursor.execute("SELECT COUNT(*) FROM redemptions")
        redemptions_count = cursor.fetchone()[0]
        
        # Count allocations
        cursor.execute("SELECT COUNT(*) FROM redemption_allocations")
        allocations_count = cursor.fetchone()[0]
        
        # Count realized transactions
        cursor.execute("SELECT COUNT(*) FROM realized_transactions")
        realized_count = cursor.fetchone()[0]
        
        # Count game sessions
        cursor.execute("SELECT COUNT(*) FROM game_sessions")
        sessions_count = cursor.fetchone()[0]
        
        return {
            'pairs': pairs_count,
            'purchases': purchases_count,
            'redemptions': redemptions_count,
            'sessions': sessions_count,
            'allocations': allocations_count,
            'realized_transactions': realized_count
        }

