# Issue (Phase 2): Convert grid tabs to QTableView + model/proxy, preserve Spreadsheet UX parity (no inline editing)

Sezzions prioritizes correctness and reproducibility:
- Business semantics live in `docs/PROJECT_SPEC.md`
- Noteworthy changes go in `docs/status/CHANGELOG.md`

## Problem / motivation

Phase 1 delivered spreadsheet-style **selection/copy/stats** across tabs.

We are choosing to **skip inline editing** (Phase 2/3 editing work) and keep edits in dialogs where they are deliberate and already strongly validated.

However, we may still want the structural benefits of moving grid tabs from `QTableWidget` → `QTableView` + `QAbstractTableModel`:
- Better performance/virtualization for larger datasets
- Cleaner separation of data vs view
- Proxy-based filtering/sorting (`QSortFilterProxyModel`) rather than widget-centric hacks
- A foundation that keeps Spreadsheet UX consistent regardless of widget type

This issue focuses on **QTableView migration + feature parity**, not editing.

## Proposed solution

### A) Refactor grid tabs for consistency

Convert these grid-based tabs from `QTableWidget` → `QTableView`:
- Purchases
- Redemptions
- Game Sessions
- Expenses
- Unrealized
- Setup sub-tabs:
  - Users
  - Sites
  - Cards
  - Redemption Method Types
  - Redemption Methods
  - Game Types
  - Games

Explicitly excluded:
- Tools (no grid/table)
- Daily Sessions + Realized remain hierarchical for now (tree-based); this issue must not regress selection/copy/stats on those tabs.

Introduce a consistent model pipeline for each migrated tab:
- Source model: `QAbstractTableModel`
- Proxy: `QSortFilterProxyModel` for search/filter/sort
- Header filter UI compatible with `QTableView` (proxy-based)

### B) Preserve Spreadsheet UX (Phase 1) on QTableView

Phase 2 MUST preserve (and extend) Phase 1 spreadsheet UX:
- Multi-cell selection
- Copy to clipboard as TSV (Cmd/Ctrl+C)
- Selection stats bar (Count, Numeric Count, Sum, Avg, Min, Max)
- Context menu: Copy, Copy With Headers

Implementation requirement:
- Extend `ui/spreadsheet_ux.py` to support `QTableView` selections via `selectionModel().selectedIndexes()` and `model().data()`.
- Ensure copy/stats behave the same as they did for `QTableWidget`.

### C) Keep edits dialog-only (explicit non-goal)

No inline editing is introduced in this issue.
- Setup edits remain in dialogs
- Notes remain in dialogs
- Purchases/Redemptions/Game Sessions/Expenses edits remain in dialogs

## Scope

### In-scope
- QTableWidget → QTableView migration for all grid tabs listed above
- Proxy-based search/sort/filter parity
- Spreadsheet UX parity on migrated tabs (selection/copy/stats/context menu/shortcuts)
- Headless UI smoke coverage for migrated tabs

### Out-of-scope
- Inline editing / `setData()` persistence
- Paste, undo/redo
- Converting Daily Sessions / Realized to QTreeView

## Acceptance criteria

- All listed grid tabs are now QTableView-based and show equivalent columns.
- Spreadsheet UX parity on migrated tabs:
  - Multi-cell selection works
  - Stats bar updates on selection
  - Cmd/Ctrl+C copies selection as TSV
  - Context menu copy options work
- Filtering/sorting parity:
  - Search works via proxy
  - Sorting works via proxy
  - Header filters work via proxy
- Daily Sessions + Realized retain existing Phase 1 selection/copy/stats behavior (no regressions).

## Test plan

Automated:
- Headless UI smoke: app boots and each migrated tab instantiates cleanly.
- At least one QTableView tab test triggers a selection change (validates selectionModel wiring + stats bar).
- Spreadsheet UX tests: add/extend unit tests to cover QTableView selection extraction.

Manual:
- Spot-check a migrated tab for selection/copy/stats
- Spot-check search + header filter behavior on a migrated tab

## Notes

- [X] This change likely requires updating `docs/PROJECT_SPEC.md`.
- [X] This change likely requires adding/updating tests.
- [ ] This change likely touches the database schema or migrations.
- [ ] This change includes destructive actions (must add warnings/backup prompts).
