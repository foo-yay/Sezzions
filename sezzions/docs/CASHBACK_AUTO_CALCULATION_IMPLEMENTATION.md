# Cashback Auto-Calculation Implementation Summary

## Overview
Implemented comprehensive automatic cashback calculation across all purchase operations in the sezzions OOP architecture, with support for manual overrides that are preserved during recalculation.

## Implementation Date
January 28, 2026

## Problem Statement
The Card model includes a `cashback_rate` field (0-100 representing percentage), but `cashback_earned` on purchases was always defaulting to 0.00. Cashback was never being calculated automatically.

## Solution
Implemented auto-calculation at three critical points with a flag to distinguish manual vs auto-calculated values:
1. **Purchase creation** - When user creates new purchase via UI
2. **Purchase update** - When user modifies purchase amount or changes card
3. **Recalculation** - When bulk recalculation operations run (skips manual overrides)

## Cashback Formula
```python
cashback_earned = amount * (card.cashback_rate / 100)
```
Result is rounded to 2 decimal places using `Decimal.quantize(Decimal("0.01"))`

## Files Modified

### 1. repositories/database.py
**Changes:**
- Added `cashback_is_manual INTEGER DEFAULT 0` column to purchases table schema
- Added migration for existing tables to add the column

### 2. models/purchase.py
**Changes:**
- Added `cashback_is_manual: bool = False` field to Purchase dataclass

### 3. repositories/purchase_repository.py
**Changes:**
- Updated `create()` to save `cashback_is_manual` flag
- Updated `update()` to save `cashback_is_manual` flag
- Updated `_row_to_model()` to read `cashback_is_manual` from database

### 4. services/purchase_service.py
**Changes:**
- Added `card_repo: Optional[CardRepository]` parameter to `__init__`
- Added `_calculate_cashback()` helper method
- Modified `create_purchase()` to auto-calculate if `cashback_earned=None`
- Modified `update_purchase()` to auto-recalculate when amount or card changes

**Key Logic:**
```python
def _calculate_cashback(self, amount: Decimal, card_id: Optional[int]) -> Decimal:
    """Calculate cashback based on card's cashback_rate.
    
    Returns:
        Decimal cashback amount, or 0.00 if no card or no rate
    """
    if not card_id or not self.card_repo:
        return Decimal("0.00")
    
    card = self.card_repo.get_by_id(card_id)
    if not card or card.cashback_rate <= 0:
        return Decimal("0.00")
    
    # Calculate: amount * (rate / 100)
    cashback = amount * Decimal(str(card.cashback_rate)) / Decimal("100")
    return cashback.quantize(Decimal("0.01"))
```

### 4. services/purchase_service.py
**Changes:**
- Added `card_repo: Optional[CardRepository]` parameter to `__init__`
- Added `_calculate_cashback()` helper method
- Modified `create_purchase()` to:
  - Auto-calculate if `cashback_earned=None` and set `cashback_is_manual=False`
  - Use explicit value if provided and set `cashback_is_manual=True`
- Modified `update_purchase()` to:
  - Set `cashback_is_manual=True` if user explicitly changes cashback
  - Auto-recalculate only if amount/card changes AND `cashback_is_manual=False`

**Key Logic:**
```python
def create_purchase(..., cashback_earned: Optional[Decimal] = None, ...):
    # Determine if manual or auto
    cashback_is_manual = False
    if cashback_earned is None:
        cashback_earned = self._calculate_cashback(amount, card_id)
        cashback_is_manual = False  # Auto-calculated
    else:
        cashback_is_manual = True  # User explicitly provided
    
    purchase = Purchase(..., cashback_is_manual=cashback_is_manual)

def update_purchase(..., **kwargs):
    if "cashback_earned" in kwargs:
        # User explicitly changed cashback - mark as manual
        purchase.cashback_is_manual = True
    elif ("amount" in kwargs or "card_id" in kwargs) and not purchase.cashback_is_manual:
        # Amount or card changed, and cashback is auto - recalculate
        purchase.cashback_earned = self._calculate_cashback(purchase.amount, purchase.card_id)
```

### 5. services/recalculation_service.py
**Changes:**
- Added `_recalculate_cashback_for_pair()` method
- Updated `rebuild_all()` to include cashback as Step 3 (now 3 steps per pair instead of 2)
- Updated `rebuild_for_pair()` to include cashback step
- Updated `rebuild_after_import()` to call full `rebuild_for_pair()` instead of just FIFO

**Key Logic:**
```python
def _recalculate_cashback_for_pair(self, user_id: int, site_id: int) -> int:
    """Recalculate cashback for all purchases with cards for a user/site pair.
    
    Returns:
        Number of purchases updated
    """
    conn = self.db._connection
    cursor = conn.cursor()
    
    # Get all purchases with cards for this pair
    cursor.execute(
        """
        SELECT p.id, p.amount, c.cashback_rate
        FROM purchases p
        JOIN cards c ON p.card_id = c.id
        WHERE p.user_id = ? AND p.site_id = ? AND p.card_id IS NOT NULL
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
```

### 5. services/recalculation_service.py
**Changes:**
- Added `_recalculate_cashback_for_pair()` method
- **CRITICAL:** Updated query to skip manually set cashback (`WHERE cashback_is_manual = 0 OR cashback_is_manual IS NULL`)
- Updated `rebuild_all()` to include cashback as Step 3 (now 3 steps per pair instead of 2)
- Updated `rebuild_for_pair()` to include cashback step
- Updated `rebuild_after_import()` to call full `rebuild_for_pair()` instead of just FIFO

**Key Logic:**
```python
def _recalculate_cashback_for_pair(self, user_id: int, site_id: int) -> int:
    # Get all purchases with cards BUT SKIP MANUAL OVERRIDES
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
    # Recalculate each one...
```

### 6. app_facade.py
**Changes:**
- Updated PurchaseService initialization to inject CardRepository
```python
self.purchase_service = PurchaseService(self.purchase_repo, card_repo=self.card_repo)
```

### 6. app_facade.py
**Changes:**
- Updated PurchaseService initialization to inject CardRepository
```python
self.purchase_service = PurchaseService(self.purchase_repo, card_repo=self.card_repo)
```

### 7. tests/test_cashback_calculation.py (NEW FILE)
**Purpose:** Comprehensive test coverage for all cashback calculation scenarios

**Test Cases:**
1. `test_cashback_auto_calculated_on_purchase_creation` - Verifies auto-calc at creation time
2. `test_cashback_auto_calculated_on_amount_update` - Verifies recalc when amount changes
3. `test_cashback_auto_calculated_on_card_change` - Verifies recalc when card changes
4. `test_cashback_recalculated_during_rebuild_all` - Verifies bulk recalculation corrects wrong values
5. **`test_manual_cashback_preserved_during_rebuild` - Verifies manual overrides are NOT recalculated** ✨
6. `test_cashback_zero_when_no_card` - Verifies no card = $0.00 cashback
7. `test_cashback_zero_when_card_has_zero_rate` - Verifies 0% rate = $0.00 cashback
8. `test_cashback_rounding` - Verifies proper rounding to 2 decimals

**All tests pass:** ✅ 8/8

## Calculation Points

### 1. Purchase Creation (PurchaseService.create_purchase)
**Trigger:** User creates new purchase in UI or via API

**Behavior:**
- If `cashback_earned` parameter is `None`, automatically calculates based on card
- If `cashback_earned` is explicitly provided, uses that value (allows manual override)
- If no card specified, defaults to `Decimal("0.00")`

**Example:**
```python
# User creates $100 purchase with 2% cashback card
purchase = purchase_service.create_purchase(
    user_id=1,
    site_id=1,
    amount=Decimal("100.00"),
    purchase_date=date.today(),
    card_id=5  # Card with 2% cashback rate
    # cashback_earned not specified, will auto-calculate $2.00
)
# Result: purchase.cashback_earned == Decimal("2.00")
```

### 2. Purchase Update (PurchaseService.update_purchase)
**Trigger:** User modifies existing purchase

**Behavior:**
- Recalculates cashback if:
  - `amount` field changes, OR
  - `card_id` field changes
- Only recalculates if `cashback_earned` is NOT explicitly provided in update
- Allows manual override by explicitly setting `cashback_earned`

**Examples:**
```python
# User changes purchase amount from $100 to $200
purchase_service.update_purchase(
    purchase_id=10,
    amount=Decimal("200.00")
    # cashback will auto-recalculate: $100 * 2% = $2.00 → $200 * 2% = $4.00
)

# User switches from 2% card to 3% card
purchase_service.update_purchase(
    purchase_id=10,
    card_id=6  # Different card with 3% rate
    # cashback will auto-recalculate: $100 * 2% = $2.00 → $100 * 3% = $3.00
)

# User manually overrides cashback
purchase_service.update_purchase(
    purchase_id=10,
    amount=Decimal("200.00"),
    cashback_earned=Decimal("5.00")  # Explicit override, won't auto-calculate
)
```

### 3. Recalculation (RecalculationService)
**Trigger:** 
- User clicks "Recalculate Everything" button
- System runs scoped recalculation after CSV import
- Background maintenance operations

**Behavior:**
- Queries all purchases with cards for user/site pair
- Recalculates cashback for each based on current card rate
- Updates database with corrected values
- Returns count of purchases updated

**Integration Points:**
- `rebuild_all()` - Full system recalculation (all pairs)
  - Now 3 steps per pair: FIFO → Sessions → Cashback
  - Progress tracking shows "Recalculating cashback for user X, site Y"
- `rebuild_for_pair()` - Single pair recalculation
  - Includes cashback step
- `rebuild_after_import()` - Post-import recalculation
  - Calls full `rebuild_for_pair()` to include cashback

## Edge Cases Handled

### 1. No Card Specified
```python
# Purchase without card
purchase = create_purchase(amount=100.00, card_id=None)
# Result: cashback_earned = Decimal("0.00"), cashback_is_manual = False
```

### 2. Card with Zero Rate
```python
# Card exists but has 0% cashback rate
purchase = create_purchase(amount=100.00, card_id=5)  # Card 5 has 0% rate
# Result: cashback_earned = Decimal("0.00"), cashback_is_manual = False
```

### 3. Rounding
```python
# Amount that produces fractional cents
purchase = create_purchase(amount=33.33, card_id=5)  # Card has 1.5% rate
# Calculation: 33.33 * 1.5% = 0.49995
# Result: cashback_earned = Decimal("0.50"), cashback_is_manual = False
```

### 4. Manual Override (Preserved During Recalculation) ✨
```python
# User wants to manually set cashback (e.g., promotional bonus)
purchase = create_purchase(
    amount=100.00,
    card_id=5,  # 2% card would calculate $2.00
    cashback_earned=Decimal("10.00")  # Override to $10.00
)
# Result: cashback_earned = Decimal("10.00"), cashback_is_manual = True

# Later, "Recalculate All" runs...
recalc_service.rebuild_all()
# Result: cashback STILL $10.00 (preserved because cashback_is_manual = True)
```

### 5. Update Without Recalculation
```python
# User updates notes field only
update_purchase(purchase_id=10, notes="Updated note")
# Cashback NOT recalculated (amount and card unchanged)
# cashback_is_manual flag unchanged
```

### 6. Update Triggers Recalculation (Only If Auto)
```python
# Purchase was auto-calculated originally
purchase = create_purchase(amount=100.00, card_id=5)  # Auto: $2.00, manual=False

# User changes amount
update_purchase(purchase_id=10, amount=150.00)
# Cashback recalculated to $3.00 because cashback_is_manual = False

# But if user had manually set it:
purchase2 = create_purchase(amount=100.00, card_id=5, cashback_earned=10.00)  # Manual

# User changes amount
update_purchase(purchase_id=11, amount=150.00)
# Cashback PRESERVED at $10.00 because cashback_is_manual = True
```

## Testing Strategy

### Unit Tests (8 tests, all passing)
- Test auto-calculation at creation time
- Test recalculation on amount change
- Test recalculation on card change
- Test bulk recalculation corrects wrong values (only auto-calculated ones)
- **Test manual overrides are preserved during recalculation** ✨
- Test zero cashback when no card
- Test zero cashback when card has 0% rate
- Test proper rounding to 2 decimals

### Test Coverage
```
tests/test_cashback_calculation.py::test_cashback_auto_calculated_on_purchase_creation PASSED
tests/test_cashback_calculation.py::test_cashback_auto_calculated_on_amount_update PASSED
tests/test_cashback_calculation.py::test_cashback_auto_calculated_on_card_change PASSED
tests/test_cashback_calculation.py::test_cashback_recalculated_during_rebuild_all PASSED
tests/test_cashback_calculation.py::test_manual_cashback_preserved_during_rebuild PASSED ✨
tests/test_cashback_calculation.py::test_cashback_zero_when_no_card PASSED
tests/test_cashback_calculation.py::test_cashback_zero_when_card_has_zero_rate PASSED
tests/test_cashback_calculation.py::test_cashback_rounding PASSED
```

## Usage Examples

### Scenario 1: User Creates Purchase with Credit Card
```python
# User purchases $50 in coins using their credit card (2% cashback)
purchase = purchase_service.create_purchase(
    user_id=1,
    site_id=2,
    amount=Decimal("50.00"),
    purchase_date=date(2026, 1, 28),
    card_id=3  # Card with 2% cashback
)
# Automatic result: cashback_earned = $1.00
```

### Scenario 2: User Realizes They Entered Wrong Amount
```python
# User edits purchase to correct amount
updated_purchase = purchase_service.update_purchase(
    purchase_id=15,
    amount=Decimal("75.00")  # Changed from $50 to $75
)
# Automatic result: cashback recalculated from $1.00 to $1.50
```

### Scenario 3: User Switches to Premium Credit Card
```python
# User got a new card with better cashback and updates old purchases
updated_purchase = purchase_service.update_purchase(
    purchase_id=15,
    card_id=7  # New card with 3% cashback
)
# Automatic result: cashback recalculated from $1.50 (2%) to $2.25 (3%)
```

### Scenario 4: Accountant Runs Year-End Recalculation
```python
# Recalculate all cashback to ensure accuracy
result = recalc_service.rebuild_all()
print(f"Recalculated {result.purchases_updated} purchases")
# All purchases with cards are recalculated based on current card rates
```

## Benefits

### 1. Accuracy
- Eliminates manual cashback entry errors
- Ensures consistency across all purchases
- Corrects historical data via recalculation

### 2. User Experience
- One less field users need to remember to fill in
- Automatic updates when amount or card changes
- No need to use calculator to figure out cashback

### 3. Data Integrity
- Cashback always reflects current card rate after recalculation **EXCEPT for manual overrides**
- Recalculation can fix any auto-calculated errors but preserves intentional manual values
- Test coverage ensures reliability
- `cashback_is_manual` flag provides audit trail

### 4. Compliance
- Accurate cashback tracking important for tax reporting
- Manual overrides preserved for special cases (promotions, bonuses, adjustments)
- Audit trail via recalculation operations and manual flag
- Consistent calculation formula across entire system

## Future Enhancements (Potential)

1. **Historical Cashback Rates**
   - Track cashback_rate changes over time
   - Preserve historical cashback based on purchase date, not current rate

2. **Cashback Categories**
   - Different rates for different purchase types
   - Bonus categories (e.g., 5% on gas stations)

3. **CSV Import Integration**
   - Auto-calculate cashback for imported purchases with cards
   - Option to override via CSV column

4. **Reporting**
   - Total cashback earned by card
   - Cashback trends over time
   - Best card recommendations based on spending patterns

## Conclusion
Comprehensive automatic cashback calculation is now implemented across all three critical points with intelligent manual override preservation:
1. ✅ Purchase creation (UI) - Auto-calculates by default, marks as manual if explicitly provided
2. ✅ Purchase updates (UI) - Recalculates only auto values, preserves manual overrides
3. ✅ Bulk recalculation (maintenance) - Fixes corrupted auto values, skips manual overrides

All 8 test cases pass, covering standard scenarios, edge cases, and the critical manual override preservation feature. The implementation provides automatic calculation as the default behavior while respecting intentional manual overrides for special cases like promotional bonuses, bank adjustments, or special deals.

**Key Innovation:** The `cashback_is_manual` flag allows the system to distinguish between auto-calculated values (which should be updated when card rates or amounts change) and manually set values (which represent special circumstances and should be preserved).
