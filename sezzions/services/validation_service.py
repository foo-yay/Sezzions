"""
Validation service for data integrity checks
"""
from typing import List, Dict, Tuple
from decimal import Decimal
from services.report_service import ReportService


class ValidationService:
    """Service for validating data integrity and consistency"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.report_service = ReportService(db_manager)
    
    def validate_fifo_allocations(self, user_id: int, site_id: int) -> Dict[str, any]:
        """
        Validate that FIFO allocations are correct
        - Purchases consumed amounts match allocations
        - No negative remaining amounts
        - Redemptions have valid cost basis
        
        Returns dict with:
        - is_valid: bool
        - errors: List of error messages
        - warnings: List of warning messages
        """
        errors = []
        warnings = []
        
        # Check for negative remaining amounts
        query = """
            SELECT id, amount, remaining_amount 
            FROM purchases 
            WHERE user_id = ? AND site_id = ? 
            AND CAST(remaining_amount AS REAL) < 0
        """
        negative_purchases = self.db.fetch_all(query, (user_id, site_id))
        
        for purchase in negative_purchases:
            errors.append(
                f"Purchase {purchase['id']} has negative remaining amount: {purchase['remaining_amount']}"
            )
        
        # Check for remaining amount > original amount
        query = """
            SELECT id, amount, remaining_amount 
            FROM purchases 
            WHERE user_id = ? AND site_id = ? 
            AND CAST(remaining_amount AS REAL) > CAST(amount AS REAL)
        """
        invalid_purchases = self.db.fetch_all(query, (user_id, site_id))
        
        for purchase in invalid_purchases:
            errors.append(
                f"Purchase {purchase['id']} has remaining ({purchase['remaining_amount']}) "
                f"greater than original amount ({purchase['amount']})"
            )
        
        # Check redemptions with FIFO that have invalid cost basis
        query = """
            SELECT r.id, r.amount, rt.cost_basis, rt.net_pl
            FROM realized_transactions rt
            JOIN redemptions r ON r.id = rt.redemption_id
            WHERE r.user_id = ? AND r.site_id = ?
            AND CAST(rt.cost_basis AS REAL) > CAST(r.amount AS REAL)
        """
        invalid_redemptions = self.db.fetch_all(query, (user_id, site_id))
        
        for redemption in invalid_redemptions:
            errors.append(
                f"Redemption {redemption['id']} has cost basis ({redemption['cost_basis']}) "
                f"greater than amount ({redemption['amount']})"
            )
        
        # Check for redemptions without FIFO when they should have it
        query = """
            SELECT r.id, r.amount, r.redemption_date
            FROM redemptions r
            WHERE r.user_id = ? AND r.site_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM redemption_allocations ra
                WHERE ra.redemption_id = r.id
            )
        """
        redemptions_without_fifo = self.db.fetch_all(query, (user_id, site_id))
        
        if redemptions_without_fifo:
            warnings.append(
                f"{len(redemptions_without_fifo)} redemptions without FIFO allocation"
            )
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_errors": len(errors),
            "total_warnings": len(warnings)
        }
    
    def validate_session_calculations(self, user_id: int, site_id: int) -> Dict[str, any]:
        """
        Validate that session P/L calculations are correct
        
        Returns dict with validation results
        """
        errors = []
        warnings = []
        
        # Get all sessions with calculated P/L
        query = """
            SELECT gs.id, gs.discoverable_sc, gs.delta_redeem, gs.basis_consumed,
                   gs.net_taxable_pl, s.sc_rate
            FROM game_sessions gs
            JOIN sites s ON s.id = gs.site_id
            WHERE gs.user_id = ? AND gs.site_id = ?
            AND gs.net_taxable_pl IS NOT NULL
        """
        sessions = self.db.fetch_all(query, (user_id, site_id))
        
        for session in sessions:
            discoverable_sc = Decimal(str(session["discoverable_sc"] or 0))
            delta_redeem = Decimal(str(session["delta_redeem"] or 0))
            basis_consumed = Decimal(str(session["basis_consumed"] or 0))
            sc_rate = Decimal(str(session["sc_rate"] or 1))
            stored_pl = Decimal(str(session["net_taxable_pl"] or 0))
            
            expected_pl = ((discoverable_sc + delta_redeem) * sc_rate) - basis_consumed
            
            # Check if stored P/L matches calculation
            if stored_pl != expected_pl:
                errors.append(
                    f"Session {session['id']} P/L mismatch: stored={stored_pl}, expected={expected_pl}"
                )
        
        # Check for sessions without P/L calculation
        query = """
            SELECT COUNT(*) as count
            FROM game_sessions
            WHERE user_id = ? AND site_id = ?
            AND net_taxable_pl IS NULL
        """
        result = self.db.fetch_one(query, (user_id, site_id))
        
        if result["count"] > 0:
            warnings.append(f"{result['count']} sessions without P/L calculation")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "total_errors": len(errors),
            "total_warnings": len(warnings)
        }
    
    def validate_all(self, user_id: int, site_id: int) -> Dict[str, any]:
        """
        Run all validation checks for a user/site combination
        
        Returns comprehensive validation report
        """
        fifo_results = self.validate_fifo_allocations(user_id, site_id)
        session_results = self.validate_session_calculations(user_id, site_id)
        
        all_errors = fifo_results["errors"] + session_results["errors"]
        all_warnings = fifo_results["warnings"] + session_results["warnings"]
        
        return {
            "is_valid": len(all_errors) == 0,
            "fifo_validation": fifo_results,
            "session_validation": session_results,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
            "errors": all_errors,
            "warnings": all_warnings
        }
    
    def get_data_summary(self) -> Dict[str, int]:
        """Get counts of all data in the system"""
        return {
            "users": self.db.fetch_one("SELECT COUNT(*) as count FROM users", ())["count"],
            "sites": self.db.fetch_one("SELECT COUNT(*) as count FROM sites", ())["count"],
            "cards": self.db.fetch_one("SELECT COUNT(*) as count FROM cards", ())["count"],
            "games": self.db.fetch_one("SELECT COUNT(*) as count FROM games", ())["count"],
            "purchases": self.db.fetch_one("SELECT COUNT(*) as count FROM purchases", ())["count"],
            "redemptions": self.db.fetch_one("SELECT COUNT(*) as count FROM redemptions", ())["count"],
            "sessions": self.db.fetch_one("SELECT COUNT(*) as count FROM game_sessions", ())["count"],
        }
