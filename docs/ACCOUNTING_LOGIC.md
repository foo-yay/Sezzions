# Accounting Logic - CRITICAL

## ⚠️ WARNING: This Logic Must Be Preserved 100%

This document contains the **core accounting algorithms** that **MUST** work identically in the new OOP app. Any deviation will produce incorrect tax calculations.

---

## Core Principles

### 1. Session-Based Taxation (Not Transaction-Based)
- Taxable profit/loss is calculated per **game session**, not per purchase/redemption
- Formula: `net_taxable_pl = discoverable_sc + delta_play - basis_consumed`
- A session can close at zero redemption (total loss)

### 2. FIFO Cost Basis
- Redemptions consume basis from purchases in **chronological order**
- Only purchases with `purchase_date/time ≤ redemption_date/time` are eligible
- Remaining basis tracked in `purchases.remaining_amount`

### 3. Discoverable SC
- "Found money" - redeemable SC that appears without purchase
- Calculated as: `starting_redeemable - expected_start_redeemable`
- Expected start = previous session's ending_redeemable

### 4. Basis Consumption
- Basis consumed **only** when redeemable balance **increases**
- Measured as: `delta_redeemable` when positive
- Uses weighted average basis per SC

---

## FIFOService Implementation

Extract from `business_logic.py` → `services/fifo_service.py`

### Class Structure

```python
from decimal import Decimal
from datetime import date, time
from typing import List, Tuple
from repositories.purchase_repository import PurchaseRepository
from repositories.redemption_repository import RedemptionRepository
from repositories.redemption_allocation_repository import RedemptionAllocationRepository
from repositories.realized_transaction_repository import RealizedTransactionRepository

class FIFOService:
    """Implements FIFO cost basis allocation"""
    
    def __init__(
        self,
        purchase_repo: PurchaseRepository,
        redemption_repo: RedemptionRepository,
        allocation_repo: RedemptionAllocationRepository,
        realized_repo: RealizedTransactionRepository
    ):
        self.purchase_repo = purchase_repo
        self.redemption_repo = redemption_repo
        self.allocation_repo = allocation_repo
        self.realized_repo = realized_repo
```

---

### Method 1: Calculate Cost Basis (FIFO Allocation)

**Purpose:** Allocate redemption amount to purchases using FIFO

**Algorithm:**
1. Get all purchases for site/user with `remaining_amount > 0`
2. Filter: only purchases where `purchase_datetime <= redemption_datetime`
3. Sort chronologically: `(purchase_date, purchase_time, id) ASC`
4. Allocate redemption amount to purchases until fully allocated
5. Track allocations in `redemption_allocations` table
6. Update `purchases.remaining_amount` for each allocation

**Critical Implementation:**

```python
def calculate_cost_basis(
    self,
    site_id: int,
    user_id: int,
    redemption_amount: Decimal,
    redemption_date: date,
    redemption_time: time
) -> Tuple[Decimal, List[dict]]:
    """
    Calculate cost basis for redemption using FIFO.
    
    Returns:
        (total_basis, allocations)
        
    allocations = [
        {'purchase_id': int, 'allocated_amount': Decimal},
        ...
    ]
    """
    # Combine date and time for comparison
    redemption_datetime = f"{redemption_date} {redemption_time}"
    
    # Get purchases with remaining basis, chronologically
    purchases = self.purchase_repo.get_available_for_fifo(
        site_id=site_id,
        user_id=user_id,
        before_datetime=redemption_datetime
    )
    
    # Sort chronologically (should already be sorted from repo)
    purchases.sort(key=lambda p: (p.purchase_date, p.purchase_time, p.id))
    
    total_basis = Decimal('0.00')
    remaining_to_allocate = redemption_amount
    allocations = []
    
    for purchase in purchases:
        if remaining_to_allocate <= 0:
            break
        
        # How much can we take from this purchase?
        available = purchase.remaining_amount
        to_allocate = min(available, remaining_to_allocate)
        
        allocations.append({
            'purchase_id': purchase.id,
            'allocated_amount': to_allocate
        })
        
        total_basis += to_allocate
        remaining_to_allocate -= to_allocate
    
    # If we couldn't fully allocate, that's an error condition
    if remaining_to_allocate > Decimal('0.01'):  # Allow small rounding
        raise ValueError(
            f"Insufficient basis: need {redemption_amount}, "
            f"only {total_basis} available"
        )
    
    return total_basis, allocations
```

**Repository Query (`PurchaseRepository.get_available_for_fifo`):**

```python
def get_available_for_fifo(
    self,
    site_id: int,
    user_id: int,
    before_datetime: str  # "YYYY-MM-DD HH:MM:SS"
) -> List[Purchase]:
    """Get purchases with remaining basis, before datetime"""
    query = """
        SELECT * FROM purchases
        WHERE site_id = ? AND user_id = ?
          AND remaining_amount > 0
          AND (purchase_date || ' ' || purchase_time) <= ?
        ORDER BY purchase_date ASC, purchase_time ASC, id ASC
    """
    rows = self.db.fetch_all(query, (site_id, user_id, before_datetime))
    return [self._row_to_model(row) for row in rows]
```

---

### Method 2: Apply Allocation

**Purpose:** Save allocations and update purchase remaining amounts

```python
def apply_allocation(
    self,
    redemption_id: int,
    allocations: List[dict]
) -> None:
    """
    Apply FIFO allocations to database.
    
    Args:
        redemption_id: The redemption being allocated
        allocations: List of {'purchase_id': int, 'allocated_amount': Decimal}
    """
    try:
        self.db.begin_transaction()
        
        for alloc in allocations:
            purchase_id = alloc['purchase_id']
            allocated_amount = alloc['allocated_amount']
            
            # Insert allocation record
            self.allocation_repo.create(
                redemption_id=redemption_id,
                purchase_id=purchase_id,
                allocated_amount=allocated_amount
            )
            
            # Update purchase remaining_amount
            purchase = self.purchase_repo.get_by_id(purchase_id)
            new_remaining = purchase.remaining_amount - allocated_amount
            
            # Ensure non-negative (guard against rounding errors)
            if new_remaining < Decimal('0.00'):
                new_remaining = Decimal('0.00')
            
            self.purchase_repo.update_remaining_amount(
                purchase_id=purchase_id,
                remaining_amount=new_remaining
            )
        
        self.db.commit()
        
    except Exception as e:
        self.db.rollback()
        raise e
```

---

### Method 3: Reverse Cost Basis

**Purpose:** Undo allocations when editing/deleting redemption

```python
def reverse_cost_basis(
    self,
    redemption_id: int
) -> None:
    """
    Reverse FIFO allocations for a redemption.
    Used when editing or deleting redemption.
    """
    try:
        self.db.begin_transaction()
        
        # Get all allocations for this redemption
        allocations = self.allocation_repo.get_by_redemption(redemption_id)
        
        for alloc in allocations:
            purchase_id = alloc.purchase_id
            allocated_amount = alloc.allocated_amount
            
            # Restore basis to purchase
            purchase = self.purchase_repo.get_by_id(purchase_id)
            new_remaining = purchase.remaining_amount + allocated_amount
            
            # Cap at original amount (prevent overshooting)
            if new_remaining > purchase.amount:
                new_remaining = purchase.amount
            
            self.purchase_repo.update_remaining_amount(
                purchase_id=purchase_id,
                remaining_amount=new_remaining
            )
        
        # Delete allocation records
        self.allocation_repo.delete_by_redemption(redemption_id)
        
        # Delete realized transaction
        self.realized_repo.delete_by_redemption(redemption_id)
        
        self.db.commit()
        
    except Exception as e:
        self.db.rollback()
        raise e
```

---

### Method 4: Get Weighted Average Basis Per SC

**Purpose:** Calculate average cost per SC for session P/L calculation

```python
def get_weighted_average_basis_per_sc(
    self,
    site_id: int,
    user_id: int,
    as_of_date: date,
    as_of_time: time
) -> Decimal:
    """
    Get weighted average basis per SC.
    Used for calculating basis consumed in game sessions.
    """
    as_of_datetime = f"{as_of_date} {as_of_time}"
    
    # Get all purchases with remaining basis
    purchases = self.purchase_repo.get_available_for_fifo(
        site_id=site_id,
        user_id=user_id,
        before_datetime=as_of_datetime
    )
    
    total_basis = Decimal('0.00')
    total_sc = Decimal('0.00')
    
    for purchase in purchases:
        # Basis = remaining_amount
        # SC = remaining_amount (1:1 ratio unless otherwise specified)
        total_basis += purchase.remaining_amount
        total_sc += purchase.remaining_amount  # Assume 1:1 SC:Dollar
    
    if total_sc == 0:
        return Decimal('0.00')
    
    return total_basis / total_sc
```

---

## SessionService Implementation

Extract from `business_logic.py` → `services/session_service.py`

### Class Structure

```python
from decimal import Decimal
from datetime import date, time
from typing import List, Optional
from repositories.game_session_repository import GameSessionRepository
from services.fifo_service import FIFOService

class SessionService:
    """Manages game session accounting"""
    
    # Fields that don't trigger recalculation when edited
    ADMINISTRATIVE_FIELDS = {
        'notes', 'game_id', 'game_name', 'wager_amount', 'rtp', 'status'
    }
    
    def __init__(
        self,
        session_repo: GameSessionRepository,
        fifo_service: FIFOService
    ):
        self.session_repo = session_repo
        self.fifo_service = fifo_service
```

---

### Method 1: Calculate Session P/L

**Purpose:** Calculate net taxable P/L for a session

**Formula:**
```
net_taxable_pl = discoverable_sc + delta_play - basis_consumed
```

**Where:**
- `discoverable_sc = starting_redeemable - expected_start_redeemable`
- `expected_start_redeemable` = previous session's `ending_redeemable`
- `delta_play = ending_balance - starting_balance`
- `basis_consumed` = amount of basis used (only when redeemable increases)

**Critical Implementation:**

```python
def calculate_session_pl(
    self,
    session: GameSession,
    prev_session: Optional[GameSession] = None
) -> Decimal:
    """
    Calculate net taxable P/L for session.
    
    Args:
        session: Current session
        prev_session: Previous chronological session (for expected_start)
    
    Returns:
        net_taxable_pl
    """
    # Step 1: Calculate discoverable SC
    expected_start_redeemable = Decimal('0.00')
    if prev_session:
        expected_start_redeemable = prev_session.ending_redeemable or Decimal('0.00')
    
    discoverable_sc = session.starting_redeemable - expected_start_redeemable
    discoverable_sc = max(Decimal('0.00'), discoverable_sc)  # Can't be negative
    
    # Step 2: Calculate deltas
    delta_play = session.ending_balance - session.starting_balance
    delta_redeemable = session.ending_redeemable - session.starting_redeemable
    
    # Step 3: Calculate basis consumed
    basis_consumed = Decimal('0.00')
    
    if delta_redeemable > 0:
        # Redeemable increased - consume basis
        avg_basis_per_sc = self.fifo_service.get_weighted_average_basis_per_sc(
            site_id=session.site_id,
            user_id=session.user_id,
            as_of_date=session.session_date,
            as_of_time=session.session_time
        )
        
        basis_consumed = delta_redeemable * avg_basis_per_sc
    
    # Step 4: Calculate net P/L
    net_taxable_pl = discoverable_sc + delta_play - basis_consumed
    
    return net_taxable_pl
```

---

### Method 2: Rebuild All Derived Fields

**Purpose:** Recompute all FIFO and session fields from scratch

**When to use:**
- After importing data
- After major data changes
- To fix inconsistencies

```python
def rebuild_all_derived(
    self,
    site_id: int,
    user_id: int
) -> None:
    """
    Rebuild all derived data for a site/user pair.
    
    Steps:
    1. Reset all purchases.remaining_amount to purchases.amount
    2. Delete all redemption_allocations
    3. Delete all realized_transactions
    4. Replay all redemptions chronologically
    5. Recalculate all game sessions chronologically
    """
    try:
        self.db.begin_transaction()
        
        # Step 1: Reset purchase remaining amounts
        self.purchase_repo.reset_remaining_amounts(site_id, user_id)
        
        # Step 2: Delete allocations
        self.allocation_repo.delete_by_site_user(site_id, user_id)
        
        # Step 3: Delete realized transactions
        self.realized_repo.delete_by_site_user(site_id, user_id)
        
        # Step 4: Replay redemptions
        redemptions = self.redemption_repo.get_chronological(site_id, user_id)
        
        for redemption in redemptions:
            # Calculate and apply FIFO
            cost_basis, allocations = self.fifo_service.calculate_cost_basis(
                site_id=site_id,
                user_id=user_id,
                redemption_amount=redemption.amount,
                redemption_date=redemption.redemption_date,
                redemption_time=redemption.redemption_time
            )
            
            self.fifo_service.apply_allocation(redemption.id, allocations)
            
            # Create realized transaction
            self.realized_repo.create(
                redemption_date=redemption.redemption_date,
                site_id=site_id,
                user_id=user_id,
                redemption_id=redemption.id,
                cost_basis=cost_basis,
                payout=redemption.net_amount,  # amount - fees
                net_pl=redemption.net_amount - cost_basis
            )
        
        # Step 5: Recalculate game sessions
        sessions = self.session_repo.get_chronological(site_id, user_id)
        
        prev_session = None
        for session in sessions:
            # Calculate P/L
            net_pl = self.calculate_session_pl(session, prev_session)
            
            # Update session
            session.net_taxable_pl = net_pl
            self.session_repo.update(session)
            
            prev_session = session
        
        self.db.commit()
        
    except Exception as e:
        self.db.rollback()
        raise e
```

---

### Method 3: Scoped Recalculation

**Purpose:** Recalculate only affected records after edit/delete

**Optimization:** Don't rebuild everything, only from change point forward

```python
def recalculate_affected_sessions(
    self,
    site_id: int,
    user_id: int,
    from_datetime: str  # "YYYY-MM-DD HH:MM:SS"
) -> None:
    """
    Recalculate sessions starting from a timestamp.
    Used after editing/deleting purchase or redemption.
    
    Steps:
    1. Get all redemptions from timestamp forward
    2. Reverse their allocations
    3. Replay them chronologically
    4. Recalculate affected sessions
    """
    try:
        self.db.begin_transaction()
        
        # Get redemptions from timestamp forward
        redemptions = self.redemption_repo.get_from_datetime(
            site_id=site_id,
            user_id=user_id,
            from_datetime=from_datetime
        )
        
        # Reverse allocations for all affected redemptions
        for redemption in redemptions:
            self.fifo_service.reverse_cost_basis(redemption.id)
        
        # Replay redemptions chronologically
        for redemption in redemptions:
            cost_basis, allocations = self.fifo_service.calculate_cost_basis(
                site_id=site_id,
                user_id=user_id,
                redemption_amount=redemption.amount,
                redemption_date=redemption.redemption_date,
                redemption_time=redemption.redemption_time
            )
            
            self.fifo_service.apply_allocation(redemption.id, allocations)
            
            # Update realized transaction
            realized = self.realized_repo.get_by_redemption(redemption.id)
            if realized:
                realized.cost_basis = cost_basis
                realized.net_pl = redemption.net_amount - cost_basis
                self.realized_repo.update(realized)
        
        # Recalculate affected sessions
        sessions = self.session_repo.get_from_datetime(
            site_id=site_id,
            user_id=user_id,
            from_datetime=from_datetime
        )
        
        # Get previous session for expected_start calculation
        sessions_all = self.session_repo.get_chronological(site_id, user_id)
        
        for i, session in enumerate(sessions_all):
            if (session.session_date, session.session_time) >= tuple(from_datetime.split()):
                prev_session = sessions_all[i-1] if i > 0 else None
                net_pl = self.calculate_session_pl(session, prev_session)
                session.net_taxable_pl = net_pl
                self.session_repo.update(session)
        
        self.db.commit()
        
    except Exception as e:
        self.db.rollback()
        raise e
```

---

## RedemptionService Integration

### Create Redemption (with FIFO)

```python
def create_redemption(
    self,
    redemption_date: date,
    redemption_time: time,
    site_id: int,
    user_id: int,
    amount: Decimal,
    method_id: Optional[int],
    is_free_sc: bool,
    fees: Decimal,
    notes: Optional[str]
) -> Redemption:
    """
    Create redemption with automatic FIFO allocation.
    """
    try:
        self.db.begin_transaction()
        
        # Step 1: Create redemption
        redemption = Redemption(
            redemption_date=redemption_date,
            redemption_time=redemption_time,
            site_id=site_id,
            user_id=user_id,
            amount=amount,
            method_id=method_id,
            is_free_sc=is_free_sc,
            fees=fees,
            notes=notes
        )
        
        redemption = self.redemption_repo.create(redemption)
        
        # Step 2: Calculate FIFO
        cost_basis, allocations = self.fifo_service.calculate_cost_basis(
            site_id=site_id,
            user_id=user_id,
            redemption_amount=amount,
            redemption_date=redemption_date,
            redemption_time=redemption_time
        )
        
        # Step 3: Apply allocations
        self.fifo_service.apply_allocation(redemption.id, allocations)
        
        # Step 4: Create realized transaction
        self.realized_repo.create(
            redemption_date=redemption_date,
            site_id=site_id,
            user_id=user_id,
            redemption_id=redemption.id,
            cost_basis=cost_basis,
            payout=amount - fees,
            net_pl=(amount - fees) - cost_basis
        )
        
        self.db.commit()
        return redemption
        
    except Exception as e:
        self.db.rollback()
        raise e
```

---

## Business Rules & Validations

### Purchase Edit Restrictions

```python
def can_edit_purchase(purchase: Purchase, field: str) -> bool:
    """
    Check if purchase field can be edited.
    
    Rules:
    - Cannot change amount, site, user if consumed > 0
    - Administrative fields always editable
    """
    if purchase.consumed > 0:
        restricted_fields = {'amount', 'site_id', 'user_id', 'sc_received'}
        if field in restricted_fields:
            return False
    return True
```

### Administrative Fields (Don't Trigger Recalc)

```python
ADMINISTRATIVE_FIELDS = {
    'notes',
    'game_id',
    'game_name',
    'wager_amount',
    'rtp',
    'status'
}

def requires_recalculation(changed_fields: set) -> bool:
    """Check if changes require recalculation"""
    return not changed_fields.issubset(ADMINISTRATIVE_FIELDS)
```

---

## Testing Requirements

### Verification Tests (Critical)

These tests **MUST** pass - they verify new implementation matches legacy:

```python
def test_fifo_matches_legacy():
    """Verify FIFO calculations match legacy app"""
    # Import test data
    # Run legacy FIFOCalculator
    # Run new FIFOService
    # Assert results match
    pass

def test_session_pl_matches_legacy():
    """Verify session P/L calculations match legacy app"""
    # Import test sessions
    # Run legacy SessionManager
    # Run new SessionService
    # Assert results match
    pass
```

---

## Next Steps

1. Implement `FIFOService` in `services/fifo_service.py`
2. Implement `SessionService` in `services/session_service.py`
3. Write verification tests comparing to legacy
4. Read **[TESTING_STRATEGY.md](TESTING_STRATEGY.md)** for test approach

---

**Last Updated:** January 16, 2026
**Critical Status:** MUST PRESERVE EXACTLY
