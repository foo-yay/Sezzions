# Session App - OOP Backend + Qt UI

## Overview
Complete casino sweepstakes tracker with OOP backend (259 tests, 97.45% coverage) and modern PySide6 UI. Tracks purchases, redemptions, and game sessions with FIFO cost basis and taxable P/L calculations.

## Current Status

### ✅ Completed
- **OOP Backend**: All 9 domains implemented with comprehensive tests
- **Qt Application**: Standalone PySide6 app with theme system
- **Primary Tabs**:
  - 💰 Purchases - Track coin purchases with FIFO consumption
  - 💵 Redemptions - Cashouts with cost basis calculation
  - 🎮 Game Sessions - Gameplay tracking with taxable P/L
- **Setup Tab** (container with sub-tabs):
  - 👤 Users - Player accounts
  - 🏢 Sites - Casino sites with SC:Dollar rates
  - 💳 Cards - Payment methods

### 📝 Pending
- Daily Sessions tab (aggregate by day)
- Unrealized tab (current balances)
- Realized tab (completed transactions)
- Reports tab (tax reports, analytics)
- Setup sub-tabs: Redemption Methods, Games, Game Types

## Architecture

### Three-Layer Pattern
```
Models (Domain Objects)
    ↓
Repositories (Data Access)
    ↓
Services (Business Logic)
```

### Database
- SQLite with `DatabaseManager` class
- PostgreSQL-ready design (TEXT storage for Decimal values)
- Row factory for dict-like access
- Foreign key constraints enabled

## Implemented Domains

### Phase 1: Simple CRUD (134 tests)
- **User** - Player accounts
- **Site** - Casino sites with SC:Dollar ratios
- **Card** - Payment methods
- **RedemptionMethod** - Cash-out methods
- **GameType** - Game categories
- **Game** - Individual games with RTP tracking

### Phase 2: Purchases (38 tests)
- **Purchase** - Coin purchases with FIFO tracking
- `remaining_amount` field tracks unconsumed balance
- Edit restrictions when consumed

### Phase 3: Redemptions & FIFO (23 tests)
- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca- **Redemption** - Ca-xable_profit`

### P### P### P### P#sions (36 te### P### P###Session** - Play sessions with P/L tracking
- Calculates: `(redemptions + ending) - (starting + purchases)`
- Recalculation methods for data consistency

### Phase 5: Reports & Tools (11 tests)
- **ReportService** - Aggregation and analytics
  - User/Site summaries
  - Tax reports (FIFO cost basis, gains/losses)
  - Session P/L analytics (win rate, best/worst)
- **ValidationService** - Data integrity checks
  - FIFO allocation validation
  - Session P/L verification
  - Data summary counts

## Usage Examples

### Creating a Purchase
```python
from repositories.database import Databasefrom repositories.database import Databasefrom rport PurchaseRepository
from services.purchase_service import PurchaseService
from decimal import Decimal
from datetime import date

db = DatabaseManager('sezzions.db')
purchase_repo = PurchaseRepository(db)
purchase_service = PurchaseService(purchase_repo)

purchase = purchase_service.create_purchase(
    user_id=1,
    site_id=1,
    a    a    a    a    a    a    a    a    a    a    a    a    a    a    a    a    a    a    with FIFO
```python
from repositories.redemption_repository import RedemptionRepository
from services.fifo_service import FIFOService
from services.redemption_service import RedemptionService

redemption_repo = RedemptionRepository(db)
fifo_service = FIFOService(purchasefifo_service = FIFOService(purchasefifo_serve(redemption_repo, fifo_service)

redemption = redemption_service.create_redemption(
    user_id=1,
    site_id=1    site_id=1    site_80.00"),
    redemptio    re=date.today(),
    apply_fifo=True  # Automatically calculates cost basis
)

print(f"Cost Basis: {redemption.cost_basis}")
print(f"Taxable Profit: {redemption.taxable_profit}")
```

### Generating Reports
```python
from services.report_service import ReportService

report_service = ReportService(db)

# User summary
summary = report_service.get_user_summary(user_id=1)
print(f"Total Purchases: {summary.total_purchases}")
print(f"Total P/L: {summary.total_profit_loss}")
print(f"Available Balance: {summary.available_balance}")

# Tax report
tax_report = report_service.get_tax_report(
    user_id=1,
    start_date=date(2026, 1, 1),
    end_date=date(2026, 12, 31)
)
print(f"Totprint(f"Totprint(f"Totprint(f"Totprint(f"Totprint(f"
### Va### Va### Va### Va### Va### Va### Va### Vrvices.validation_service import ValidationService

validation_service = ValidationService(db)

# Validate FIFO allocations
result = validation_service.validate_all(user_id=1, site_id=1)

if result["is_valid"]:
    print("All validations passed!")
else:
    print(f"Errors found: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
```

## Running Tests## Running Tests## Running Tests## Running Tests## R   # Run all tests
pytest --copy                   # With coverage report
pytest tests/unit/test_fifo_service.py -v  # Specific test file
```

**Current Status: 242 tests, 92.83% coverage**

## Key Design Patterns

### Repository Pattern
All repositories follow the same structure:
- `__init__(self, db_manager)` - Inject DatabaseManager
- `_row_to_model(row)` - Conve- `_row_to_model(row)` - Conve- `_row_tod)` - Single record lookup
- `get_all()` - All records
- `create(model)` - Insert new - `create(model)` - Insert new - `create(model)` - Insert new )` - Remove record

### Service Pattern
Services contain business logic:
- Validation rules
- Cross-domain operations
- Calculated fields
- Edit restrictions

### Database A### Database A### Database A### Database A### Database A### D(qu### Databas)` - Single ### Database A### Database A### Darams)` - ### Database A### Database A### Database A#Inse### Database A### Database A### D Money Handling
- All amounts use `Decimal` type
- Stored as TEXT in database
- Converted to/from Decimal in repositories
- Use `CAST(field AS REAL)` for SQL n- Use `CAST(field AS REAL)` for SQL nting Rules

### FIFO (First#In, ### FIFO (First#In, ### FIFO (First#In, ### Ffirst
2. `remaining_amount`2. `remaining_amou bala2. `remaining_amount`2. `remaining_amou baer once consumed
4. Cost basis = sum of allocated purchase4. Cost basis = sum of allocated purchase4. Cost basis = sum of allocated purchase4. Cost basis= starting_balance + purchases4. Cost basis = sum of allocated purchase4. Cost basis = sum of allocated purchase4. Cost basis = sum of alloctio4. Cost basis = su: Cannot modify amount, site, or user if `consumed > 0`
- **Redemptions**: Cannot modify amount, site, user, or date if FIFO allocated
- **Sessions**: Can always recalculate P/L from stored values

## Integration with Legacy Code

The OOP backend is designed to coexist with the legacy `session2.py` code:

1. **Shared Database**: Both systems use the same SQLite database
2. **Compatible Schema**: Table structures match legacy expectations
3. **Gradual Migration**: Can migrate feature-by-feature
4. **Validation**: Use `ValidationService` to verify d4. **Validation**: Use `ValidationService` to verify d4. **Validace business_logic.py calls** with Service calls
2. **Use Services in GUI event handlers** instead of direct DB access
3. **Keep table_helpers.py** for UI rendering (compatible with Service outputs)
4. **Update session2.py** to use OOP services gradually
5. **Run ValidationService** after major operations to ensure integrity

## Testing Strategy

- **Unit Tests**: Each model, repository, and service
- **In-Memory Database**: Tests use `:memory:` for isolation
- **Fixtures**: Reusable test data in `conftest.py`
- **Coverage Target**: 90% minimum (currently 92.83%)
- **Critical Path**: FIFO calculations have extensive test coverage

## Performance Considerations

- DatabaseManager maintains single connection
- Queries use indexes on foreign keys
- Bulk operations should use transactions
- Consider connection pooling for concurrent access

## Future Enhancements

- **RedemptionAllocation** link t- **RedemptionAllocation** link t- **RedemptionAllocation** link t- **RedemptionAllocation** link t- **RedemptionAllocation** link t- **RedemptionAllocation- **CSV Imp- **RedemptionAllocation** link t- **RedemptionAllocation** link t- igration** scripts for legacy data
