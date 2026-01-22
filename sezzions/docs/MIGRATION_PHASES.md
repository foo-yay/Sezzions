# Migration Phases

## Overview

This document defines the **phased implementation timeline** for migrating from the legacy procedural app to the new OOP architecture (Sezzions).

**Estimated Total Time:** 16-20 weeks (4-5 months)

**Approach:** Incremental - build new alongside old, verify each phase

---

## Phase Summary

| Phase | Duration | Focus | Milestone |
|-------|----------|-------|-----------|
| **Phase 0** | Week 1 | Setup & Dependencies | Environment ready |
| **Phase 1** | Weeks 2-4 | Simple Domains | Users, Cards, Sites working |
| **Phase 2** | Weeks 5-8 | Purchases | Purchase CRUD with tests |
| **Phase 3** | Weeks 9-12 | Redemptions & FIFO | **CRITICAL** - FIFO verified |
| **Phase 4** | Weeks 13-16 | Sessions | Session P/L verified |
| **Phase 5** | Weeks 17-18 | Reports & Tools | Feature complete |
| **Phase 6** | Weeks 19-20 | UI & Polish | Desktop app ready |

---

## Phase 0: Setup & Dependencies (Week 1)

### Goal: Environment configured, dependencies installed

### Tasks:
1. ✅ Create `sezzions/` directory
2. ✅ Read all planning documents
3. ✅ Install dependencies from `requirements.txt`
4. ✅ Set up pytest environment
5. ✅ Create `sezzions.db` database
6. ✅ Run initial migrations
7. ✅ Configure development tools (black, mypy, ruff)
8. ✅ Create initial directory structure

### Deliverables:
- `sezzions/` folder with structure
- `requirements.txt` installed
- `pytest` working
- `sezzions.db` created with tables
- Development tools configured

### Verification:
```bash
# Test imports
python3 -c "import PySide6; import sqlalchemy; import pytest; print('OK')"

# Test database
python3 -c "from repositories.database import DatabaseManager; db = DatabaseManager('sezzions.db'); print('OK')"

# Test pytest
pytest --version
```

---

## Phase 1: Simple Domains (Weeks 2-4)

### Goal: Implement Users, Cards, Sites, RedemptionMethods, Games

### Why Start Here:
- No complex business logic
- No dependencies on other entities
- Build confidence with OOP patterns
- Establish testing patterns

### Week 2: Users & Sites

#### Tasks:
1. Create `models/user.py`
2. Create `models/site.py`
3. Create `repositories/user_repository.py`
4. Create `repositories/site_repository.py`
5. Create `services/user_service.py`
6. Create `services/site_service.py`
7. Write unit tests for each
8. Write integration tests

#### Deliverables:
- ✅ User CRUD working
- ✅ Site CRUD working
- ✅ Tests passing (90%+ coverage)

#### Verification:
```python
# Test creating user
user_service = UserService(user_repo)
user = user_service.create_user("John Doe", "john@example.com")
assert user.id is not None

# Test listing users
users = user_service.list_active_users()
assert len(users) > 0
```

---

### Week 3: Cards

#### Tasks:
1. Create `models/card.py`
2. Create `repositories/card_repository.py`
3. Create `services/card_service.py`
4. Implement card name display logic (with suffix)
5. Write unit tests
6. Write integration tests

#### Deliverables:
- ✅ Card CRUD working
- ✅ Display name with suffix working
- ✅ Tests passing

#### Critical Logic:
```python
class Card:
    def display_name(self) -> str:
        """Returns formatted name with suffix"""
        if self.last_four:
            return f"{self.name} -- x{self.last_four}"
        return self.name
```

---

### Week 4: Redemption Methods, Games, Game Types

#### Tasks:
1. Create `models/redemption_method.py`
2. Create `models/game.py`
3. Create `models/game_type.py`
4. Create repositories for each
5. Create services for each
6. Write tests

#### Deliverables:
- ✅ All simple domain entities working
- ✅ Full test coverage
- ✅ Ready for complex domains

#### Phase 1 Milestone Review:
- [ ] All simple CRUD operations working
- [ ] Tests passing with 90%+ coverage
- [ ] Code reviewed and documented
- [ ] Ready to proceed to purchases

---

## Phase 2: Purchases (Weeks 5-8)

### Goal: Implement purchase tracking with basis management

### Why Important:
- Foundation for FIFO
- Introduces `remaining_amount` tracking
- Tests edit restrictions (consumed > 0)

### Week 5: Purchase Model & Repository

#### Tasks:
1. Create `models/purchase.py`
   - Validation: amount > 0, max 2 decimals
   - Computed field: `consumed = amount - remaining_amount`
2. Create `repositories/purchase_repository.py`
   - `get_available_for_fifo()` method (critical)
   - `update_remaining_amount()` method
3. Write unit tests

#### Deliverables:
- ✅ Purchase model with validation
- ✅ Repository with FIFO query
- ✅ Tests passing

#### Critical Query:
```python
def get_available_for_fifo(self, site_id, user_id, before_datetime):
    query = """
        SELECT * FROM purchases
        WHERE site_id = ? AND user_id = ?
          AND remaining_amount > 0
          AND (purchase_date || ' ' || purchase_time) <= ?
        ORDER BY purchase_date ASC, purchase_time ASC, id ASC
    """
    return self.fetch_all(query, (site_id, user_id, before_datetime))
```

---

### Week 6: Purchase Service

#### Tasks:
1. Create `services/purchase_service.py`
2. Implement `create_purchase()`
3. Implement `update_purchase()` with edit restrictions
4. Implement `delete_purchase()` with consumed check
5. Write integration tests

#### Deliverables:
- ✅ Purchase CRUD with business rules
- ✅ Edit restrictions enforced
- ✅ Tests passing

#### Critical Business Rule:
```python
def update_purchase(self, purchase_id, **kwargs):
    purchase = self.purchase_repo.get_by_id(purchase_id)
    
    # Check consumed restriction
    if purchase.consumed > 0:
        restricted_fields = {'amount', 'site_id', 'user_id', 'sc_received'}
        if any(field in kwargs for field in restricted_fields):
            raise ValueError("Cannot edit consumed purchase")
    
    # Apply updates
    for key, value in kwargs.items():
        setattr(purchase, key, value)
    
    return self.purchase_repo.update(purchase)
```

---

### Week 7-8: Purchase Integration & Testing

#### Tasks:
1. Write comprehensive integration tests
2. Test edge cases (negative amounts, date validation)
3. Test CSV import workflow
4. Test remaining_amount updates
5. Performance testing (1000+ purchases)

#### Deliverables:
- ✅ All purchase tests passing
- ✅ CSV import working
- ✅ Performance benchmarks met

#### Phase 2 Milestone Review:
- [ ] Purchase CRUD fully working
- [ ] Edit restrictions enforced
- [ ] FIFO query tested and optimized
- [ ] Ready for redemptions

---

## Phase 3: Redemptions & FIFO (Weeks 9-12) **CRITICAL**

### ⚠️ MOST IMPORTANT PHASE - Accounting accuracy depends on this

### Goal: Implement FIFO allocation and verification

### Week 9: Redemption Model & Repository

#### Tasks:
1. Create `models/redemption.py`
2. Create `models/realized_transaction.py`
3. Create `models/redemption_allocation.py` (link table)
4. Create repositories for each
5. Write unit tests

#### Deliverables:
- ✅ Redemption model with validation
- ✅ Allocation tracking model
- ✅ Repositories working

---

### Week 10: FIFO Service **CRITICAL**

#### Tasks:
1. Create `services/fifo_service.py`
2. Implement `calculate_cost_basis()` **CRITICAL**
3. Implement `apply_allocation()`
4. Implement `reverse_cost_basis()`
5. Implement `get_weighted_average_basis_per_sc()`
6. Write unit tests for each method

#### Deliverables:
- ✅ FIFO service working
- ✅ Unit tests passing

#### Critical Implementation:
See **[ACCOUNTING_LOGIC.md](ACCOUNTING_LOGIC.md)** - must implement exactly

---

### Week 11: Redemption Service & Integration

#### Tasks:
1. Create `services/redemption_service.py`
2. Implement `create_redemption()` with FIFO
3. Implement `update_redemption()` with reverse + reapply
4. Implement `delete_redemption()` with basis restoration
5. Write integration tests

#### Deliverables:
- ✅ Redemption service working
- ✅ Integration with FIFO verified
- ✅ Transaction management working

---

### Week 12: FIFO Verification **CRITICAL**

#### Tasks:
1. **Import real data from legacy DB**
2. Run legacy `FIFOCalculator` on test cases
3. Run new `FIFOService` on same test cases
4. **Compare results - MUST MATCH EXACTLY**
5. Fix any discrepancies
6. Document verification results

#### Deliverables:
- ✅ Verification tests passing
- ✅ FIFO calculations match legacy 100%
- ✅ Documentation of verification process

#### Critical Test:
```python
def test_fifo_matches_legacy_on_real_data():
    """Test FIFO on 100 real redemptions from legacy DB"""
    legacy_db = Database('casino_accounting.db')
    new_db = DatabaseManager('sezzions.db')
    
    # Import same data to both
    import_test_data(legacy_db, new_db)
    
    # Get 100 test redemptions
    test_redemptions = get_test_redemptions(legacy_db, limit=100)
    
    for redemption in test_redemptions:
        # Legacy calculation
        legacy_calc = FIFOCalculator(legacy_db)
        legacy_basis, legacy_allocs = legacy_calc.calculate_cost_basis(...)
        
        # New calculation
        new_basis, new_allocs = fifo_service.calculate_cost_basis(...)
        
        # MUST match
        assert new_basis == Decimal(str(legacy_basis))
        assert_allocations_match(new_allocs, legacy_allocs)
```

#### Phase 3 Milestone Review: **CRITICAL GATE**
- [ ] FIFO calculations verified 100% accurate
- [ ] All redemption tests passing
- [ ] Transaction management working
- [ ] Performance acceptable
- **DO NOT PROCEED unless FIFO is verified**

---

## Phase 4: Sessions (Weeks 13-16)

### Goal: Implement game session tracking and P/L calculation

### Week 13: Session Model & Repository

#### Tasks:
1. Create `models/game_session.py`
2. Create `repositories/game_session_repository.py`
3. Implement chronological queries
4. Write unit tests

#### Deliverables:
- ✅ Session model with computed fields
- ✅ Repository working
- ✅ Tests passing

---

### Week 14: Session Service **CRITICAL**

#### Tasks:
1. Create `services/session_service.py`
2. Implement `calculate_session_pl()` **CRITICAL**
3. Implement `rebuild_all_derived()`
4. Implement `recalculate_affected_sessions()`
5. Implement administrative fields logic
6. Write unit tests

#### Deliverables:
- ✅ Session service working
- ✅ P/L calculation implemented
- ✅ Tests passing

#### Critical Implementation:
See **[ACCOUNTING_LOGIC.md](ACCOUNTING_LOGIC.md)** - formula must be exact

---

### Week 15: Session Integration & Testing

#### Tasks:
1. Integrate SessionService with FIFOService
2. Test session CRUD operations
3. Test scoped recalculation
4. Test administrative field edits
5. Write integration tests

#### Deliverables:
- ✅ Sessions fully integrated
- ✅ Recalculation working
- ✅ Tests passing

---

### Week 16: Session Verification **CRITICAL**

#### Tasks:
1. Import real session data from legacy DB
2. Run legacy `SessionManager` calculations
3. Run new `SessionService` calculations
4. **Compare results - MUST MATCH EXACTLY**
5. Fix any discrepancies
6. Document verification

#### Deliverables:
- ✅ Session P/L matches legacy 100%
- ✅ Verification tests passing
- ✅ Documentation complete

#### Phase 4 Milestone Review: **CRITICAL GATE**
- [ ] Session P/L calculations verified 100% accurate
- [ ] Rebuild functionality working
- [ ] Scoped recalculation working
- [ ] Performance acceptable
- **DO NOT PROCEED unless sessions verified**

---

## Phase 5: Reports & Tools (Weeks 17-18)

### Goal: Implement reporting and utility features

### Week 17: Reports

#### Tasks:
1. Create `services/report_service.py`
2. Implement Tax Diary report
3. Implement Unrealized/Realized reports
4. Implement Daily Sessions report
5. CSV export functionality
6. Write tests

#### Deliverables:
- ✅ All reports generating correctly
- ✅ CSV exports working
- ✅ Tests passing

---

### Week 18: Tools & Utilities

#### Tasks:
1. Implement database backup/restore
2. Implement refactor functionality
3. Implement recalculate everything
4. Implement audit logging
5. Implement settings management
6. Write tests

#### Deliverables:
- ✅ All tools working
- ✅ Audit logging functional
- ✅ Tests passing

#### Phase 5 Milestone Review:
- [ ] All reports accurate
- [ ] Tools working correctly
- [ ] Audit trail complete
- [ ] Ready for UI

---

## Phase 6: UI & Polish (Weeks 19-20)

### Goal: Build Qt desktop interface

### Week 19: UI Framework

#### Tasks:
1. Create `ui/main_window.py`
2. Port `table_helpers.py` to OOP (`ui/widgets/searchable_table.py`)
3. Create tab structure
4. Create dialogs for CRUD operations
5. Wire services to UI

#### Deliverables:
- ✅ Main window with tabs
- ✅ Searchable tables working
- ✅ Dialogs functional

---

### Week 20: Testing & Polish

#### Tasks:
1. End-to-end testing
2. UI/UX polish
3. Error handling improvements
4. Performance optimization
5. Documentation updates
6. Final verification against legacy

#### Deliverables:
- ✅ Fully functional desktop app
- ✅ Feature parity with legacy
- ✅ All tests passing
- ✅ Documentation complete

#### Final Milestone Review:
- [ ] All features working
- [ ] Tests passing (90%+ coverage)
- [ ] Accounting verified against legacy
- [ ] Performance acceptable
- [ ] Documentation complete
- **READY FOR PRODUCTION**

---

## Verification Checklist (End of Each Phase)

### Code Quality:
- [ ] All tests passing
- [ ] Coverage >= 90%
- [ ] No linting errors (`ruff check`)
- [ ] Type checking passes (`mypy`)
- [ ] Code formatted (`black`)

### Functionality:
- [ ] Feature works as expected
- [ ] Edge cases handled
- [ ] Error messages helpful
- [ ] Transactions rollback on error

### Accounting Accuracy (Phases 3-4):
- [ ] Calculations match legacy **exactly**
- [ ] Verification tests documented
- [ ] Sample data tested
- [ ] Real data tested

### Documentation:
- [ ] Code comments added
- [ ] Docstrings complete
- [ ] README updated
- [ ] Changelog updated

---

## Rollback Plan

If a phase fails verification:

1. **Stop forward progress**
2. **Document the issue** in detail
3. **Review design documents**
4. **Fix root cause** (don't patch)
5. **Re-run verification**
6. **Only proceed when passing**

**DO NOT skip verification for Phases 3 & 4** - accounting accuracy is non-negotiable

---

## Post-Migration Tasks (Week 21+)

### Data Migration from Legacy:
1. Export all data from legacy DB
2. Import into Sezzions DB
3. Run full rebuild
4. Verify all calculations
5. Generate comparison reports
6. Document discrepancies (if any)

### User Acceptance:
1. Run legacy and Sezzions side-by-side
2. Compare outputs daily
3. Fix any issues found
4. Build confidence in new system

### Cutover:
1. Final data export from legacy
2. Final import into Sezzions
3. Final verification
4. **Switch to Sezzions as primary**
5. Keep legacy as read-only backup

---

## Risk Management

### High-Risk Areas:
1. **FIFO calculations** (Phase 3)
   - Mitigation: Extensive verification tests
2. **Session P/L** (Phase 4)
   - Mitigation: Formula verification against legacy
3. **Performance** (all phases)
   - Mitigation: Benchmark tests, indexing
4. **Data migration**
   - Mitigation: Multiple test runs, rollback plan

### If Behind Schedule:
- Prioritize Phases 3-4 (accounting)
- Phase 5 (reports) can be delayed
- Phase 6 (UI polish) can be iterative
- **Never compromise verification**

---

## Success Metrics

### Technical:
- ✅ 90%+ test coverage
- ✅ All verification tests passing
- ✅ Performance: <1s for typical operations
- ✅ Zero accounting discrepancies

### Business:
- ✅ Feature parity with legacy
- ✅ Same or better user experience
- ✅ Database supports both SQLite and PostgreSQL
- ✅ Ready for web/mobile migration

---

## Next Steps

1. Begin **Phase 0** (Setup)
2. Install dependencies
3. Create database
4. Move to **Phase 1** (Simple Domains)
5. Follow this timeline, verify each phase
6. **DO NOT SKIP VERIFICATION for Phases 3-4**

---

**Last Updated:** January 16, 2026  
**Status:** Ready for Implementation
