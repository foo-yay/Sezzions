## Problem / motivation

The desktop app has spreadsheet-like UX features on all data tables: Cmd+C to copy selected cells as TSV, "Copy With Headers" context menu, a stats bar showing sum/count/average of selected numeric cells, and extended multi-cell selection. These features are shared across all tabs (game sessions, purchases, redemptions, etc.) via `SpreadsheetUX` and `TableHeaderFilter` base classes.

The web app currently has no equivalent. This should be built as a shared component usable by all entity tables.

## Proposed solution

Build shared spreadsheet-like UX features for the web `EntityTable` component:
1. **Cell selection**: Click + drag / Shift+click to select table cells (not just rows)
2. **Copy**: Cmd/Ctrl+C copies selected cells as TSV; "Copy With Headers" option in context menu
3. **Stats bar**: Footer showing sum, count, and average of selected numeric cells
4. **Column header filters**: Click column header to filter/sort by that column's values

This should integrate with the existing `EntityTable` component as opt-in features.

## Scope

In-scope:
- Cell-level selection in EntityTable
- Clipboard copy (TSV format) with keyboard shortcut
- Copy With Headers context menu option
- Stats bar (sum/count/average) for numeric selections
- Column header click-to-filter/sort

Out-of-scope:
- Cell editing (this is read-only spreadsheet UX)
- Excel/CSV export (separate feature)
- Pivot tables or advanced analytics

## Acceptance criteria

- Users can select individual cells or ranges in any EntityTable
- Cmd/Ctrl+C copies selected cells as tab-separated values
- Right-click shows "Copy With Headers" option
- Stats bar appears when numeric cells are selected, showing sum/count/average
- Column headers support click-to-filter and sort
- Features work on all entity tables (purchases, redemptions, game sessions)

## Test plan

Manual verification:
- Select cells in game sessions table, copy, paste into spreadsheet
- Verify stats bar shows correct sum/count/average
- Verify column header filtering narrows displayed rows
