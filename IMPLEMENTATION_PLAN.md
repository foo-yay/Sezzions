# Sezzions OOP Migration - Implementation Plan

## Executive Summary

This plan outlines the conversion of the Session App (21,000+ line procedural desktop app) to a modern OOP architecture called **Sezzions**, designed to support both desktop and eventual web/mobile deployment.

**Critical Success Criteria:**
- ✅ Preserve 100% of accounting algorithm accuracy (FIFO, session-based tax calculations)
- ✅ Support SQLite (desktop) and PostgreSQL (web) without code changes
- ✅ Enable platform portability (desktop → web → mobile)
- ✅ Maintain audit trail and data integrity
- ✅ Achieve 90%+ test coverage

**Timeline:** 4-6 months, phased approach with milestones

**Current Status:** Planning phase (no code written yet)

---

## Documentation Structure

This plan is split into focused documents for manageability:

| Document | Purpose | AI Usage |
|----------|---------|----------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Domain models, repositories, services design | Reference when building classes |
| **[DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** | Schema for dual-database support | Reference for migrations & queries |
| **[ACCOUNTING_LOGIC.md](docs/ACCOUNTING_LOGIC.md)** | FIFO & SessionManager algorithms | **CRITICAL** - Must implement exactly |
| **[TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md)** | pytest approach, verification tests | Follow for test-driven development |
| **[MIGRATION_PHASES.md](docs/MIGRATION_PHASES.md)** | Phase-by-phase timeline | Track progress, know what's next |
| **[DEPENDENCIES.md](docs/DEPENDENCIES.md)** | Libraries, tools, rationale | Install and configure these first |

---

## Quick Start for AI Implementers

### Phase 0: Setup (Week 1)
1. Read **[DEPENDENCIES.md](docs/DEPENDENCIES.md)** - install required libraries
2. Read **[DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - understand schema
3. Create `sezzions.db` and run initial migrations
4. Set up pytest environment

### Phase 1: Simple Domains (Weeks 2-4)
1. Read **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** sections: Users, Cards, Sites
2. Implement models → repositories → services for each
3. Follow **[TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md)** to write tests
4. Verify: Run tests, compare output to legacy app

### Phase 2-5: Complex Domains (Weeks 5-16)
1. Follow **[MIGRATION_PHASES.md](docs/MIGRATION_PHASES.md)** phase by phase
2. **CRITICAL:** Read **[ACCOUNTING_LOGIC.md](docs/ACCOUNTING_LOGIC.md)** before Phases 3-4
3. Implement Purchases → Redemptions → Sessions with accounting logic
4. Write verification tests comparing legacy vs new calculations

### Phase 6: UI Layer (Weeks 17-20)
1. Build Qt GUI using service layer (no direct database access)
2. Port table_helpers.py to new architecture
3. Maintain feature parity with legacy app

---

## Legacy UI Parity Runthrough (Authoritative)

**Source of truth:** legacy Qt app in [qt_app.py](../qt_app.py). The goal is **1:1 functionality and workflow parity**, including dialog flows, button visibility rules, validation, and table behaviors. Cosmetic differences (icons/emojis) are OK.

**Non-negotiable:** Do **not** deviate from legacy UI layouts, dialog structure, or accounting logic without explicit approval. Schema must remain **1:1** with legacy tables/columns (no missing fields, no workarounds).

### Verification Workflow
1. Inventory legacy UI behavior tab-by-tab (dialogs, button states, double-click behavior, validation rules).
2. Implement parity in Sezzions UI.
3. Confirm parity by running both apps side-by-side using a shared data set.
4. Record each verified item in the checklist below.

### Parity Checklist (Initial Baseline)

#### Purchases Tab (legacy: qt_app.py `PurchasesTab`)
- Buttons: **Add** always visible; **View/Edit/Delete** hidden until a row is selected.
- Double-click row: **opens View Purchase dialog** (not edit).
- View dialog includes **buttons for Edit** and possible navigation to related data.
- Date filter row: **From/To** with calendar buttons, quick ranges (Today / Last 30 / This Month / This Year / All Time), Apply/Clear.
- Search row: search box, Clear Search, Clear All Filters, Refresh, Export.
- Validation: consistent currency and date validation with legacy (see qt_app.py dialogs).
- Field order in Add/Edit dialog must match legacy order.

#### Redemptions Tab (legacy: qt_app.py `RedemptionsTab`)
- Same visibility rules as Purchases (View/Edit/Delete hidden until selection).
- Double-click row opens **View Redemption** dialog.
- Date filter row and search row match legacy layout and behavior.
- Validation and tooltips match legacy.

#### Game Sessions Tab (legacy: qt_app.py `GameSessionsTab`)
- Buttons: **Start** visible by default; **View/End/Edit/Delete** hidden until selection.
- Active sessions count label is displayed.
- Double-click row opens **View Session** dialog.
- Separate dialogs: **Start Session**, **View Session**, **End Session**, **Edit Session**.
- Start Session dialog **does not** include ending balances, purchases during, redemptions during, or P/L.
- Start Session dialog displays **Expected Start**, **Unexpected Balance**, **Undiscovered/New SC**.
- End Session dialog captures **Ending Total** and **Ending Redeemable**, with locked/bonus SC preview.
- P/L calculated **only** when session is closed.

#### Unrealized / Realized Tabs
- UI and data meaning must align with legacy (Realized = cash flow, not taxable P/L).
- Date filter and search behaviors match legacy.

#### Expenses Tab (legacy: qt_app.py `ExpensesTab`)
- Full tab parity required: add/view/edit/delete, hidden action buttons until selection.
- Double-click row opens **View Expense** dialog.
- Date filter and search rows match Purchases/Redemptions format.

#### Reports Tab (legacy: qt_app.py `ReportsTab`)
- Reports hub with left navigation and right report display.
- Categories and report list align with legacy.
- Filters and report-specific controls match legacy.

---

## Planned Parity Enhancements (Immediate Scope)
1. Add **Expenses** tab to Sezzions UI with full CRUD and legacy parity.
2. Add **Reports** tab with legacy layout and data flow.
3. Enforce **View-first** dialogs on double-click (Purchases, Redemptions, Sessions, Expenses).
4. Align dialog field order, validation rules, button visibility, and tooltips with legacy.

---

## UI Layout Updates (Jan 2026)

Recent layout alignment and styling changes made to keep Sezzions consistent with qt_app.py:

- **Main navigation tabs** are now a centered `QTabBar` paired with a `QStackedWidget` so the buttons remain centered and uniform without relying on `QTabWidget` alignment.
- **Main tab button sizing** uses fixed widths (narrow enough to avoid overflow), with consistent padding and no bold-resize jitter.
- **Setup sub-tabs** are folder-style tabs with readable active text and consistent spacing; top-right of the pane stays rounded with a straight blend into the selected tab.
- **Setup header/blurb** added to match other tabs, plus a spacer to align the header baseline with tabs that include a search box.
- **Tables**: removed row-number column across Users/Sites/Games/Method Types/Methods/Game Types/Unrealized; headers are sized to at least their text, and the last column stretches to fill remaining space.
- **Purchases/Redemptions header sizing** stabilized so refresh/clear filters doesn’t shrink columns.

---

## Project Structure

```
sezzions/
├── IMPLEMENTATION_PLAN.md          # This file
├── docs/
│   ├── ARCHITECTURE.md             # OOP design details
│   ├── DATABASE_DESIGN.md          # Schema & migrations
│   ├── ACCOUNTING_LOGIC.md         # FIFO & SessionManager
│   ├── TESTING_STRATEGY.md         # Testing approach
│   ├── MIGRATION_PHASES.md         # Timeline & milestones
│   └── DEPENDENCIES.md             # Libraries & tools
├── sezzions.py                     # Main entry point (to be created)
├── sezzions.db                     # SQLite database (to be created)
├── requirements.txt                # Python dependencies (to be created)
├── models/                         # Domain models (to be created)
├── repositories/                   # Data access layer (to be created)
├── services/                       # Business logic layer (to be created)
├── ui/                             # UI components (to be created)
├── tests/                          # Test suite (to be created)
└── migrations/                     # Database migrations (to be created)
```

---

## Key Architectural Changes

### From Procedural → OOP

| Legacy Pattern | New Pattern | Benefit |
|----------------|-------------|---------|
| Direct SQL in UI | Repository pattern | Testable, database-agnostic |
| Business logic in qt_app.py | Service layer | Reusable across platforms |
| sqlite3.Row dicts | Domain models (dataclasses) | Type safety, validation |
| Monolithic file | Modular packages | Maintainable, scalable |
| Manual testing | pytest with 90%+ coverage | Confidence, regression prevention |

### Preserved Patterns
- FIFO cost basis calculation (timestamp-aware)
- Session-based tax accounting (not transaction-based)
- Audit logging for compliance
- Scoped recalculation (efficiency)
- Administrative fields (don't trigger recalc)

---

## Critical Accounting Principles

⚠️ **These MUST work identically to legacy app:**

1. **FIFO Basis Allocation**
   - Redemptions consume basis from purchases in chronological order
   - Timestamp filtering: only purchases ≤ redemption timestamp
   - Weighted average basis per SC for session P/L

2. **Session Tax Calculation**
   - Formula: `net_taxable_pl = discoverable + delta_play - basis_consumed`
   - Discoverable SC = starting_redeemable - expected_start_redeemable
   - Basis consumed only when redeemable balance increases

3. **Reconciliation Rules**
   - Edit/delete triggers scoped rebuild from timestamp
   - Full rebuild if allocations invalidated
   - Administrative field edits don't trigger recalc

See **[ACCOUNTING_LOGIC.md](docs/ACCOUNTING_LOGIC.md)** for complete algorithms.

---

## Development Workflow

### For Each Feature:
1. **Read relevant docs** (Architecture, Testing)
2. **Write model** (domain entity with validation)
3. **Write repository** (database access, SQL queries)
4. **Write service** (business logic, orchestration)
5. **Write tests** (unit → integration → verification)
6. **Verify** against legacy app output
7. **Commit** with descriptive message

### Testing Levels:
- **Unit tests:** Test each method in isolation
- **Integration tests:** Test service + repository together
- **Verification tests:** Compare new vs legacy calculations
- **Regression tests:** Ensure bugs don't reappear

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Accounting logic errors | Verification tests comparing legacy vs new |
| Data corruption | Audit logging, transaction rollbacks |
| Performance degradation | Benchmark tests, scoped recalculation |
| Platform incompatibility | Database abstraction layer |
| Scope creep | Strict phase boundaries, milestone reviews |

---

## Success Metrics

### Per Phase:
- ✅ All tests passing (90%+ coverage)
- ✅ Verification tests match legacy output
- ✅ Code review completed
- ✅ Documentation updated

### Final Delivery:
- ✅ Feature parity with legacy app
- ✅ All accounting calculations verified
- ✅ SQLite + PostgreSQL tested
- ✅ Performance benchmarks acceptable
- ✅ Ready for UI development (web/mobile)

---

## Next Steps

1. **Read [DEPENDENCIES.md](docs/DEPENDENCIES.md)** - Install libraries
2. **Read [DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - Create database
3. **Read [ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Understand OOP design
4. **Read [MIGRATION_PHASES.md](docs/MIGRATION_PHASES.md)** - Start Phase 1

---

## Questions or Issues?

Refer to the specific documentation file for each concern:
- Architecture questions → **ARCHITECTURE.md**
- Database schema questions → **DATABASE_DESIGN.md**
- Accounting logic questions → **ACCOUNTING_LOGIC.md**
- Testing questions → **TESTING_STRATEGY.md**
- Timeline questions → **MIGRATION_PHASES.md**
- Library questions → **DEPENDENCIES.md**

---

**Last Updated:** January 16, 2026  
**Status:** Planning Complete - Ready for Implementation
