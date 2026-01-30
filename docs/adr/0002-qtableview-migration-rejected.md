# ADR 0002: QTableView Migration Rejected

**Status:** Accepted  
**Date:** 2026-01-31  
**Deciders:** Project Owner, AI Agent  
**Related Issues:** #15, PR #24

## Context

Issue #15 originally proposed migrating grid tabs from `QTableWidget` to `QTableView` + `QAbstractTableModel` as part of a larger effort that included inline editing (Phase 2/3).

After deciding to remove inline editing from scope (keeping all edits in dialogs), the migration became a standalone architectural change. A pilot migration of the Sites tab was completed, along with supporting infrastructure:
- `ui/base_table_model.py` (BaseTableModel, ColumnDefinition)
- `ui/spreadsheet_ux.py` extended to support QTableView
- Sites tab migrated to QTableView + model + proxy

However, critical issues emerged during review.

## Decision

**We will NOT migrate tabs from QTableWidget to QTableView.**

All work from PR #24 is reverted except:
- Infrastructure code can remain (harmless, tested)
- Sites tab reverted to QTableWidget
- Issue #15 closed as "won't do"

## Rationale

### Critical Functionality Loss

**TableHeaderFilter incompatibility:**
- `TableHeaderFilter` provides per-column filtering UI (right-click headers, text/date filters)
- Works only with QTableWidget, not QTableView
- Rebuilding this for QTableView is non-trivial work
- Many tabs (Purchases, Redemptions, Game Sessions) rely on column filtering

**Trade-off analysis:**
- Lost: Column filtering UI (significant user-facing feature)
- Gained: Slightly cleaner architecture (minimal developer benefit)
- This is a net negative trade-off

### Weak Benefits Without Inline Editing

The supposed benefits were:

1. **"Cleaner separation: presentation vs data"**
   - Reality: QTableWidget's item-based approach is straightforward for simple CRUD tabs
   - Added complexity (model class, proxy mapping) without payoff

2. **"Built-in proxy model support for sorting/filtering"**
   - Lost column filtering UI (net negative)
   - Sorting already works with QTableWidget
   - "No re-populate" benefit only matters for huge datasets (we don't have those)

3. **"More idiomatic Qt architecture"**
   - QTableWidget is ALSO idiomatic Qt - designed specifically for editable tables
   - "Idiomatic" ≠ "better for our needs"

4. **"Foundation for future advanced features"**
   - Like what? We explicitly decided NO inline editing
   - Custom delegates? For what purpose?
   - Lazy loading? Our datasets are small
   - Speculative future-proofing without concrete need

5. **"No manual row-by-row population loops"**
   - Traded clear, obvious loops for model/proxy mapping complexity
   - Getting selected IDs now requires mapping through proxy → source → get object
   - More abstraction, not necessarily better code

### Original Context Removed

**QTableView migration made sense ONLY when bundled with inline editing.** Model/view separation shines when you need:
- Complex editing logic in the model
- Data validation at the model level
- Multiple views of the same data
- Large datasets with custom delegates

Once inline editing was removed, we're left with:
- ✅ Infrastructure that works
- ❌ Lost column filtering functionality
- ❌ More complex ID extraction logic
- ❌ More code for the same behavior
- ❌ No tangible user-facing improvements

This is architecture for architecture's sake.

## Consequences

### Positive

- **Preserve existing functionality:** Column filtering UI remains available
- **Simpler codebase:** QTableWidget is straightforward, well-understood
- **Less maintenance:** No need to rebuild filtering UI for QTableView
- **Focus on value:** Avoid speculative refactoring without clear benefits

### Negative

- **Sunk cost:** Time spent on PR #24 infrastructure and pilot migration
- **Infrastructure unused:** BaseTableModel and QTableView SpreadsheetUX support exist but aren't used

### Neutral

- **Infrastructure can stay:** The code is clean, tested, and harmless
- **Future option:** If we later need inline editing or another feature that benefits from model/view separation, the infrastructure is ready

## If Revisited

**Do NOT revisit QTableView migration unless:**

1. We decide to implement inline editing (original Phase 2/3 scope)
2. We have a concrete need that model/view separation solves
3. We solve the column filtering UI problem first (rebuild TableHeaderFilter for QTableView)

**Requirements for future QTableView work:**
- Must preserve ALL existing functionality (column filtering, sorting, search)
- Must demonstrate clear user-facing or developer benefits
- Must not be speculative future-proofing

## Related

- Issue #14: Spreadsheet UX (Phase 1) - Completed, works with QTableWidget
- Issue #15: QTableView migration - Closed as "won't do"
- Issue #16: Inline editing (Phase 3) - Closed as "not planned"
- PR #24: QTableView infrastructure and pilot - Closed without merge
