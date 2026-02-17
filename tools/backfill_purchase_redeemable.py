#!/usr/bin/env python3
"""
One-time migration script to backfill starting_redeemable_balance for existing purchases.

Issue #130: Purchase checkpoints should store redeemable balance to prevent reset.

This script:
1. Finds all purchases with starting_sc_balance > 0 and starting_redeemable_balance = 0
2. For each, computes expected redeemable using compute_expected_balances
3. Updates the purchase with the computed value

Usage:
    python3 tools/backfill_purchase_redeemable.py [--dry-run]
"""

import sys
import os

# Add parent directory to path so we can import from the project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from app_facade import AppFacade


def backfill_purchase_redeemable(db_path: str = "sezzions.db", dry_run: bool = False):
    """
    Backfill starting_redeemable_balance for existing purchases.
    
    Args:
        db_path: Path to the database file
        dry_run: If True, print what would be done without making changes
    """
    print(f"Backfilling purchase redeemable balances ({db_path})...")
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    
    facade = AppFacade(db_path)
    
    # Find all purchases with starting_sc_balance > 0
    query = """
        SELECT id, user_id, site_id, purchase_date, purchase_time, 
               starting_sc_balance, COALESCE(starting_redeemable_balance, 0) as starting_redeemable_balance
        FROM purchases
        WHERE deleted_at IS NULL
          AND starting_sc_balance > 0.001
        ORDER BY purchase_date ASC, purchase_time ASC, id ASC
    """
    
    purchases_to_update = facade.db.fetch_all(query)
    
    print(f"Found {len(purchases_to_update)} purchases with starting_sc_balance > 0")
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    for p in purchases_to_update:
        purchase_id = p['id']
        user_id = p['user_id']
        site_id = p['site_id']
        purchase_date = p['purchase_date']
        purchase_time = p['purchase_time'] or "00:00:00"
        current_redeemable = Decimal(str(p['starting_redeemable_balance'] or 0))
        
        try:
            # Compute expected redeemable at this purchase time
            _, expected_redeemable = facade.compute_expected_balances(
                user_id=user_id,
                site_id=site_id,
                session_date=purchase_date,
                session_time=purchase_time,
                exclude_purchase_id=purchase_id,  # Exclude this purchase from the calculation
            )
            
            # Only update if the value would change
            if expected_redeemable != current_redeemable:
                if dry_run:
                    print(f"  [DRY RUN] Would update purchase {purchase_id}: "
                          f"{current_redeemable} → {expected_redeemable}")
                    updated_count += 1
                else:
                    # Update the purchase
                    update_query = """
                        UPDATE purchases
                        SET starting_redeemable_balance = ?
                        WHERE id = ?
                    """
                    facade.db.execute(update_query, (str(expected_redeemable), purchase_id))
                    print(f"  Updated purchase {purchase_id}: {current_redeemable} → {expected_redeemable}")
                    updated_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"  ERROR processing purchase {purchase_id}: {e}")
            error_count += 1
    
    if not dry_run:
        facade.db.commit()
    
    print(f"\nBackfill complete:")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped (already correct): {skipped_count}")
    print(f"  Errors: {error_count}")
    
    facade.db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill starting_redeemable_balance for purchases")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--db", default="sezzions.db", help="Path to database file (default: sezzions.db)")
    
    args = parser.parse_args()
    
    backfill_purchase_redeemable(db_path=args.db, dry_run=args.dry_run)
