# Bug: Purchases tab selection sum duplicates values when filtered (hidden rows included)

## Problem
In the Purchases tab, the spreadsheet stats bar (Sum/Avg/Min/Max) can show inflated sums even when selecting only a couple of visible cells in a single numeric column (e.g. Amount or SC Received).

This is most noticeable after applying filters/search that hide rows.

## Repro (deterministic)
1. Open Purchases tab.
2. In the search bar, type `Modo`.
3. Apply header filter: User = `fooyay`.
4. Select only the Amount cells for:
   - 2/3/26 @ 09:11 for $8.99
   - 2/2/26 @ 18:46 for $17.99

### Expected
Sum = 26.98

### Actual
Sum = 44.97

Also reproducible in SC Received:
- selecting two visible SC values totaling 30 can display Sum = 50.

## Suspected root cause
`SpreadsheetUXController._extract_table_selection()` uses `selectedRanges()` and treats all cells within a selected range as selected, regardless of whether the row is currently hidden (`setRowHidden(True)`).

When filters/search hide rows between two visible rows, a range selection can implicitly include hidden rows, and those hidden rows’ numeric values get included in stats.

## Proposal
Update selection extraction / stats computation to ignore hidden rows and hidden columns:
- For `QTableWidget`: treat a cell as selectable only if `not table.isRowHidden(row)` and `not table.isColumnHidden(col)`.
- For `QTableView`: similarly ignore hidden rows/cols where applicable.

Add a headless regression test:
- Create a QTableWidget with 3 rows.
- Hide the middle row.
- Range-select the Amount column across the top and bottom visible rows.
- Assert sum only includes visible selected cells.

## Acceptance criteria
- Stats bar sum matches visible selected values when rows are hidden by filters.
- Regression test covers the hidden-row-in-range case.
- No changes to how non-filtered selections work.
