# Testing Strategy

## Overview

This document defines the testing approach for Sezzions, with emphasis on **verification tests** that ensure the new OOP implementation produces identical accounting results to the legacy app.

**Target: 90%+ code coverage**

---

## Testing Pyramid

```
         /\
        /  \  Unit Tests (70%)
       /____\
      /      \  Integration Tests (20%)
     /________\
    /          \  Verification Tests (10%)
   /____________\
```

---

## Test Categories

### 1. Unit Tests (70% of tests)
**Purpose:** Test individual methods in isolation

**Scope:**
- Repository methods (CRUD operations)
- Service methods (business logic)
- Model validation
- Utility functions

**Pattern:**
```python
def test_user_repository_create():
    """Test creating a user"""
    db = create_test_database()
    user_repo = UserRepository(db)
    
    user = User(name="Test User", email="test@example.com")
    created_user = user_repo.create(user)
    
    assert created_user.id is not None
    assert created_user.name == "Test User"
    assert created_user.email == "test@example.com"
```

---

### 2. Integration Tests (20% of tests)
**Purpose:** Test service + repository interaction

**Scope:**
- Service methods calling multiple repositories
- Transaction management
- Database constraints
- Foreign key relationships

**Pattern:**
```python
def test_create_redemption_with_fifo():
    """Test redemption creation with FIFO allocation"""
    db = create_test_database()
    
    # Setup services
    purchase_repo = PurchaseRepository(db)
    redemption_repo = RedemptionRepository(db)
    allocation_repo = RedemptionAllocationRepository(db)
    realized_repo = RealizedTransactionRepository(db)
    
    fifo_service = FIFOService(
        purchase_repo, redemption_repo,
        allocation_repo, realized_repo
    )
    
    redemption_service = RedemptionService(
        redemption_repo, fifo_service, realized_repo
    )
    
    # Create test data
    create_test_purchase(db, amount=100.00, remaining=100.00)
    
    # Create redemption
    redemption = redemption_service.create_redemption(
        redemption_date=date(2026, 1, 15),
        redemption_time=time(10, 0),
        site_id=1,
        user_id=1,
        amount=Decimal('50.00'),
        method_id=1,
        is_free_sc=False,
        fees=Decimal('0.00'),
        notes=None
    )
    
    # Verify allocation created
    allocations = allocation_repo.get_by_redemption(redemption.id)
    assert len(allocations) == 1
    assert allocations[0].allocated_amount == Decimal('50.00')
    
    # Verify purchase remaining updated
    purchase = purchase_repo.get_by_id(1)
    assert purchase.remaining_amount == Decimal('50.00')
    
    # Verify realized transaction created
    realized = realized_repo.get_by_redemption(redemption.id)
    assert realized.cost_basis == Decimal('50.00')
    assert realized.payout == Decimal('50.00')
    assert realized.net_pl == Decimal('0.00')
```

---

### 3. Verification Tests (10% of tests)
**Purpose:** **CRITICAL** - Compare new vs legacy calculations

**Scope:**
- FIFO allocation results
- Session P/L calculations
- Weighted average basis
- Scoped recalculation

**Pattern:**
```python
def test_fifo_matches_legacy():
    """
    Verify FIFO calculations match legacy app.
    
    This is a CRITICAL test - if this fails, the new app
    produces incorrect tax calculations.
    """
    # Import real data from legacy DB
    legacy_db = Database('casino_accounting.db')
    new_db = DatabaseManager('test_sezzions.db')
    
    # Get test redemption
    redemption_id = 123
    
    # Legacy calculation
    legacy_calc = FIFOCalculator(legacy_db)
    legacy_basis, legacy_allocs = legacy_calc.calculate_cost_basis(
        site_id=1,
        user_id=1,
        redemption_amount=100.00,
        redemption_date='2026-01-15',
        redemption_time='10:00:00'
    )
    
    # New calculation
    fifo_service = FIFOService(
        PurchaseRepository(new_db),
        RedemptionRepository(new_db),
        RedemptionAllocationRepository(new_db),
        RealizedTransactionRepository(new_db)
    )
    
    new_basis, new_allocs = fifo_service.calculate_cost_basis(
        site_id=1,
        user_id=1,
        redemption_amount=Decimal('100.00'),
        redemption_date=date(2026, 1, 15),
        redemption_time=time(10, 0)
    )
    
    # Assert exact match
    assert new_basis == Decimal(str(legacy_basis))
    assert len(new_allocs) == len(legacy_allocs)
    
    for i, (new_alloc, legacy_alloc) in enumerate(zip(new_allocs, legacy_allocs)):
        assert new_alloc['purchase_id'] == legacy_alloc['purchase_id']
        assert new_alloc['allocated_amount'] == Decimal(str(legacy_alloc['allocated_amount']))
```

---

## Test Structure

```
sezzions/
└── tests/
    ├── __init__.py
    ├── conftest.py                  # pytest fixtures
    ├── test_data/
    │   ├── test_purchases.csv
    │   ├── test_redemptions.csv
    │   └── test_sessions.csv
    ├── unit/
    │   ├── test_models.py
    │   ├── test_repositories/
    │   │   ├── test_user_repository.py
    │   │   ├── test_purchase_repository.py
    │   │   └── ...
    │   └── test_services/
    │       ├── test_user_service.py
    │       ├── test_fifo_service.py
    │       └── ...
    ├── integration/
    │   ├── test_purchase_workflow.py
    │   ├── test_redemption_workflow.py
    │   └── test_session_workflow.py
    └── verification/
        ├── test_fifo_accuracy.py
        ├── test_session_pl_accuracy.py
        └── test_rebuild_accuracy.py
```

---

## pytest Configuration

**File:** `sezzions/pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --cov=sezzions
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
```

---

## Fixtures (`conftest.py`)

```python
import pytest
from repositories.database import DatabaseManager
from repositories import *
from services import *

@pytest.fixture
def test_db():
    """Create fresh test database"""
    db = DatabaseManager(':memory:')  # In-memory SQLite
    # Run migrations
    # ...
    yield db
    db.close()

@pytest.fixture
def user_repo(test_db):
    return UserRepository(test_db)

@pytest.fixture
def purchase_repo(test_db):
    return PurchaseRepository(test_db)

@pytest.fixture
def fifo_service(test_db):
    return FIFOService(
        PurchaseRepository(test_db),
        RedemptionRepository(test_db),
        RedemptionAllocationRepository(test_db),
        RealizedTransactionRepository(test_db)
    )

@pytest.fixture
def sample_user(user_repo):
    """Create sample user for testing"""
    user = User(name="Test User", email="test@example.com")
    return user_repo.create(user)

@pytest.fixture
def sample_purchase(purchase_repo, sample_user):
    """Create sample purchase for testing"""
    purchase = Purchase(
        purchase_date=date(2026, 1, 1),
        purchase_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        amount=Decimal('100.00'),
        sc_received=Decimal('100.00'),
        remaining_amount=Decimal('100.00')
    )
    return purchase_repo.create(purchase)
```

---

## Critical Verification Tests

### Test 1: FIFO Accuracy

```python
# tests/verification/test_fifo_accuracy.py

import pytest
from decimal import Decimal
from datetime import date, time

def test_fifo_chronological_allocation(fifo_service, purchase_repo, sample_user):
    """Test FIFO allocates from earliest purchases first"""
    
    # Create 3 purchases at different times
    p1 = purchase_repo.create(Purchase(
        purchase_date=date(2026, 1, 1),
        purchase_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        amount=Decimal('50.00'),
        sc_received=Decimal('50.00'),
        remaining_amount=Decimal('50.00')
    ))
    
    p2 = purchase_repo.create(Purchase(
        purchase_date=date(2026, 1, 2),
        purchase_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        amount=Decimal('50.00'),
        sc_received=Decimal('50.00'),
        remaining_amount=Decimal('50.00')
    ))
    
    p3 = purchase_repo.create(Purchase(
        purchase_date=date(2026, 1, 3),
        purchase_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        amount=Decimal('50.00'),
        sc_received=Decimal('50.00'),
        remaining_amount=Decimal('50.00')
    ))
    
    # Redeem $75 - should consume p1 fully and p2 partially
    basis, allocs = fifo_service.calculate_cost_basis(
        site_id=1,
        user_id=sample_user.id,
        redemption_amount=Decimal('75.00'),
        redemption_date=date(2026, 1, 10),
        redemption_time=time(10, 0)
    )
    
    # Verify total basis
    assert basis == Decimal('75.00')
    
    # Verify allocations
    assert len(allocs) == 2
    assert allocs[0]['purchase_id'] == p1.id
    assert allocs[0]['allocated_amount'] == Decimal('50.00')
    assert allocs[1]['purchase_id'] == p2.id
    assert allocs[1]['allocated_amount'] == Decimal('25.00')


def test_fifo_timestamp_filter(fifo_service, purchase_repo, sample_user):
    """Test FIFO only uses purchases before redemption timestamp"""
    
    # Create purchase AFTER redemption
    p_future = purchase_repo.create(Purchase(
        purchase_date=date(2026, 1, 10),
        purchase_time=time(15, 0),
        site_id=1,
        user_id=sample_user.id,
        amount=Decimal('100.00'),
        sc_received=Decimal('100.00'),
        remaining_amount=Decimal('100.00')
    ))
    
    # Try to redeem BEFORE purchase
    with pytest.raises(ValueError, match="Insufficient basis"):
        fifo_service.calculate_cost_basis(
            site_id=1,
            user_id=sample_user.id,
            redemption_amount=Decimal('50.00'),
            redemption_date=date(2026, 1, 10),
            redemption_time=time(10, 0)  # Before purchase at 15:00
        )
```

---

### Test 2: Session P/L Accuracy

```python
# tests/verification/test_session_pl_accuracy.py

def test_session_pl_calculation(session_service, sample_user):
    """Test session P/L calculation matches formula"""
    
    # Create first session (baseline)
    session1 = GameSession(
        session_date=date(2026, 1, 1),
        session_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        starting_balance=Decimal('0.00'),
        ending_balance=Decimal('100.00'),
        starting_redeemable=Decimal('0.00'),
        ending_redeemable=Decimal('50.00')
    )
    
    # Create second session with discoverable SC
    session2 = GameSession(
        session_date=date(2026, 1, 2),
        session_time=time(10, 0),
        site_id=1,
        user_id=sample_user.id,
        starting_balance=Decimal('100.00'),
        ending_balance=Decimal('120.00'),
        starting_redeemable=Decimal('75.00'),  # Increased from 50 -> discoverable
        ending_redeemable=Decimal('80.00')
    )
    
    # Calculate P/L
    net_pl = session_service.calculate_session_pl(session2, session1)
    
    # Expected calculation:
    # discoverable = 75 - 50 = 25
    # delta_play = 120 - 100 = 20
    # delta_redeemable = 80 - 75 = 5 (positive -> consume basis)
    # basis_consumed = 5 * avg_basis_per_sc
    # (Assuming avg_basis_per_sc = 1.0 for this test)
    # net_pl = 25 + 20 - 5 = 40
    
    assert net_pl == Decimal('40.00')
```

---

### Test 3: Rebuild Accuracy

```python
# tests/verification/test_rebuild_accuracy.py

def test_rebuild_matches_incremental(session_service, test_db):
    """Test full rebuild produces same results as incremental updates"""
    
    # Setup: Create purchases, redemptions, sessions incrementally
    # (normal workflow)
    
    # Capture results
    incremental_results = capture_all_data(test_db)
    
    # Now rebuild from scratch
    session_service.rebuild_all_derived(site_id=1, user_id=1)
    
    # Capture results again
    rebuild_results = capture_all_data(test_db)
    
    # Assert identical
    assert incremental_results == rebuild_results
```

---

## Coverage Requirements

### Minimum Coverage by Component:

| Component | Minimum Coverage | Priority |
|-----------|------------------|----------|
| `models/` | 100% | HIGH |
| `repositories/` | 95% | HIGH |
| `services/fifo_service.py` | 100% | **CRITICAL** |
| `services/session_service.py` | 100% | **CRITICAL** |
| `services/*_service.py` | 90% | HIGH |
| `ui/` | 70% | MEDIUM |

---

## Running Tests

### Run All Tests
```bash
cd sezzions/
pytest
```

### Run Unit Tests Only
```bash
pytest tests/unit/
```

### Run Verification Tests Only
```bash
pytest tests/verification/
```

### Run with Coverage Report
```bash
pytest --cov=sezzions --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Specific Test
```bash
pytest tests/verification/test_fifo_accuracy.py::test_fifo_chronological_allocation
```

---

## Continuous Integration

### GitHub Actions Workflow (`.github/workflows/test.yml`)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov=sezzions --cov-fail-under=90
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Test-Driven Development Workflow

1. **Write failing test** - Define expected behavior
2. **Run test** - Verify it fails (red)
3. **Implement minimum code** - Make test pass
4. **Run test** - Verify it passes (green)
5. **Refactor** - Clean up code
6. **Run all tests** - Ensure nothing broke

---

## Performance Benchmarks

### Benchmark Tests (`tests/benchmark/`)

```python
import time

def test_fifo_performance(fifo_service):
    """Benchmark FIFO calculation speed"""
    
    # Setup: 1000 purchases
    for i in range(1000):
        create_test_purchase(...)
    
    # Benchmark: Calculate FIFO for 100 redemptions
    start = time.time()
    
    for i in range(100):
        fifo_service.calculate_cost_basis(...)
    
    elapsed = time.time() - start
    
    # Should complete in < 5 seconds
    assert elapsed < 5.0
    print(f"FIFO 100 redemptions: {elapsed:.2f}s")
```

---

## Debugging Failed Tests

### Use pytest flags:
```bash
# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Show print statements
pytest -s

# Drop into debugger on failure
pytest --pdb
```

---

## Next Steps

1. Set up pytest environment
2. Create conftest.py with fixtures
3. Write unit tests for models
4. Write unit tests for repositories
5. Write integration tests for services
6. **Write verification tests** (CRITICAL)
7. Run full test suite
8. Read **[MIGRATION_PHASES.md](MIGRATION_PHASES.md)** for implementation timeline

---

**Last Updated:** January 16, 2026
