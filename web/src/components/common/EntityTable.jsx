import Icon from "./Icon";
import ConfirmationModal from "./ConfirmationModal";
import ExportModal from "./ExportModal";
import TableContextMenu from "./TableContextMenu";
import TableHeaderFilterMenu from "./TableHeaderFilterMenu";
import { computeCellStats, downloadCsv } from "../../utils/tableUtils";

/**
 * Shared table component for entity tabs (Users, Sites, Cards, etc.).
 *
 * Renders the complete table UI: toolbar, search bar, column headers with
 * sort/filter menus, data rows with selection, summary rail, back-to-top,
 * context menu, export modal, and confirmation modal.
 *
 * Entity-specific modals are rendered via `children`.
 */
export default function EntityTable({
  table,
  entityName,
  entitySingular,
  columns,
  getCellDisplayValue,
  renderCell,
  defaultColumnWidths,
  defaultHeaderGridTemplate,
  extraToolbarButtons,
  extraToolbarRow,
  getRowClassName,
  children,
}) {
  const {
    hostedWorkspaceReady,
    filteredItems, filteredCount, totalCount,
    search, setSearch,
    columnFilters, setColumnFilters,
    sort, setSort, filterOptions, filtersActive,
    toggleSort, clearAllFilters,
    selectedIds, selectedItems, selectedItem,
    selectedCells, selectedColumnKeys,
    setSelectedIds, setSelectionAnchorId,
    setSelectedCells, setSelectedColumnKeys,
    handleRowSelection, handleCellClick,
    clearSelection,
    openModal, handleDelete, handleRefresh,
    loadingMore, hasMore,
    loadNextPage,
    showBackToTop, setShowBackToTop,
    contextMenu, setContextMenu,
    openHeaderMenu, setOpenHeaderMenu,
    columnWidths, setColumnWidths,
    exportModalOpen, setExportModalOpen,
    confirmationState, setConfirmationState,
    handleTableContextMenu,
    openHeaderOptions,
    handleColumnResizeStart, handleColumnAutoFit,
    tableViewportRef, headerRef,
    cellAnchorRef, navCursorRef,
    status,
  } = table;

  const singularCap = entitySingular.charAt(0).toUpperCase() + entitySingular.slice(1);

  // ── Column header click (column selection) ────────────────────────────────

  function handleColumnHeaderClick(event, column) {
    setSelectedIds([]);
    setSelectionAnchorId(null);

    const columnKeys = columns.map((c) => c.key);
    let nextCols;
    if (event.shiftKey && selectedColumnKeys.size) {
      const lastKey = [...selectedColumnKeys].pop();
      const lastIdx = columnKeys.indexOf(lastKey);
      const curIdx = columnKeys.indexOf(column.key);
      const [start, end] = lastIdx < curIdx ? [lastIdx, curIdx] : [curIdx, lastIdx];
      nextCols = new Set(columnKeys.slice(start, end + 1));
    } else if (event.metaKey || event.ctrlKey) {
      nextCols = new Set(selectedColumnKeys);
      if (nextCols.has(column.key)) nextCols.delete(column.key); else nextCols.add(column.key);
    } else {
      nextCols = selectedColumnKeys.size === 1 && selectedColumnKeys.has(column.key) ? new Set() : new Set([column.key]);
    }
    setSelectedColumnKeys(nextCols);

    const next = new Set();
    for (const item of filteredItems) {
      for (const col of nextCols) {
        next.add(`${item.id}:${col}`);
      }
    }
    setSelectedCells(next);
    cellAnchorRef.current = null;
  }

  // ── Select-all checkbox handler ───────────────────────────────────────────

  function handleSelectAllChange() {
    if (selectedIds.length === filteredItems.length) {
      setSelectedIds([]);
      setSelectionAnchorId(null);
      navCursorRef.current = null;
    } else {
      setSelectedIds(filteredItems.map((item) => item.id));
      setSelectionAnchorId(filteredItems[0]?.id ?? null);
      navCursorRef.current = filteredItems[filteredItems.length - 1]?.id ?? null;
    }
  }

  // ── Row checkbox handler ──────────────────────────────────────────────────

  function handleRowCheckboxChange(itemId) {
    setSelectedIds((current) =>
      current.includes(itemId)
        ? current.filter((id) => id !== itemId)
        : [...current, itemId]
    );
    setSelectionAnchorId(itemId);
  }

  // ── Header style ──────────────────────────────────────────────────────────

  const headerStyle = columnWidths
    ? { gridTemplateColumns: `36px ${columnWidths.map((w) => `${w}px`).join(" ")}`, minWidth: `${36 + columnWidths.reduce((a, b) => a + b, 0)}px` }
    : defaultHeaderGridTemplate
      ? { gridTemplateColumns: defaultHeaderGridTemplate }
      : undefined;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <section className="workspace-panel setup-panel users-page" aria-label={`Setup ${singularCap}s`}>
      <div className="users-surface">
        <div className="users-toolbar">
          <div className="users-toolbar-top">
            <nav className="users-breadcrumb" aria-label="Breadcrumb">
              <span className="breadcrumb-segment">Setup</span>
              <span className="breadcrumb-separator" aria-hidden="true">{"\u203A"}</span>
              <h2 className="breadcrumb-segment current" title={`Manage workspace ${entityName}, inspect individual records, and export the current filtered view.`}>{singularCap}s</h2>
            </nav>
            <div className="toolbar-row wrap-toolbar users-toolbar-actions">
              <button className="primary-button" type="button" onClick={() => openModal("create")} disabled={!hostedWorkspaceReady}>Add {singularCap}</button>
              <button className="ghost-button" type="button" onClick={() => selectedItem && openModal("view", selectedItem)} disabled={!hostedWorkspaceReady || selectedIds.length !== 1}>View</button>
              <button className="ghost-button" type="button" onClick={() => selectedItem && openModal("edit", selectedItem)} disabled={!hostedWorkspaceReady || selectedIds.length !== 1}>Edit</button>
              <button className="ghost-button" type="button" onClick={() => handleDelete()} disabled={!hostedWorkspaceReady || !selectedIds.length}>Delete</button>
              <button className="ghost-button" type="button" onClick={() => setExportModalOpen(true)} disabled={!filteredItems.length}>Export CSV</button>
              <button className="ghost-button" type="button" onClick={handleRefresh} disabled={!hostedWorkspaceReady}>Refresh</button>
              {extraToolbarButtons}
            </div>
          </div>
          {extraToolbarRow && (
            <div className="toolbar-row users-toolbar-secondary">
              {extraToolbarRow}
            </div>
          )}
          <div className="users-search-bar">
            <label className="users-search-field" htmlFor={`${entityName}-search-input`}>
              <span className="users-search-icon" aria-hidden="true"><Icon name="search" className="app-icon" /></span>
              <input
                id={`${entityName}-search-input`}
                className="text-input hero-search-input"
                type="text"
                placeholder={`Search ${entityName}...`}
                value={search}
                disabled={!hostedWorkspaceReady}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <div className="toolbar-row users-search-actions">
              <button className="ghost-button" type="button" onClick={() => { setSearch(""); clearSelection(); }}>Clear Search</button>
              <button className="ghost-button" type="button" onClick={clearAllFilters}>Clear All Filters</button>
            </div>
          </div>
        </div>

        <div className="users-table-scroll-area table-viewport" ref={tableViewportRef} onScroll={(e) => setShowBackToTop(e.currentTarget.scrollTop > 120)}>
          <div className="users-table-header" ref={headerRef} style={headerStyle}>
            <div className="users-table-header-cell users-checkbox-cell">
              <input
                type="checkbox"
                className="row-select-checkbox"
                aria-label="Select all rows"
                checked={filteredItems.length > 0 && selectedIds.length === filteredItems.length}
                ref={(el) => { if (el) el.indeterminate = selectedIds.length > 0 && selectedIds.length < filteredItems.length; }}
                onChange={handleSelectAllChange}
                disabled={!filteredItems.length}
              />
            </div>
            {columns.map((column, colIndex) => {
              const sortDirection = sort.column === column.key ? sort.direction : null;
              const filterValues = columnFilters[column.key];
              return (
                <div
                  key={column.key}
                  className={`users-table-header-cell${selectedColumnKeys.has(column.key) ? " selected-column" : ""}`}
                  onClick={(event) => handleColumnHeaderClick(event, column)}
                  onContextMenu={(event) => { event.preventDefault(); openHeaderOptions(event, column.key); }}
                >
                  <span className="users-table-header-label">{column.label}</span>
                  <button
                    className={sortDirection || filterValues.length ? "table-sort-button active" : "table-sort-button"}
                    type="button"
                    aria-label={`${column.label} options`}
                    onClick={(event) => { event.stopPropagation(); openHeaderOptions(event, column.key); }}
                  >
                    <span className="table-sort-indicator" aria-hidden="true">
                      {sortDirection === "asc"
                        ? "\u2191"
                        : sortDirection === "desc"
                          ? "\u2193"
                          : filterValues.length
                            ? filterValues.length
                            : <Icon name="filterMenu" className="app-icon table-filter-icon" />}
                    </span>
                  </button>

                  {openHeaderMenu?.key === column.key ? (
                    <TableHeaderFilterMenu
                      column={column}
                      options={filterOptions[column.key]}
                      selectedValues={filterValues}
                      sortDirection={sortDirection}
                      onClearFilter={() => {
                        setColumnFilters((current) => ({ ...current, [column.key]: [] }));
                        setOpenHeaderMenu(null);
                      }}
                      onSortAsc={() => {
                        setSort({ column: column.key, direction: "asc" });
                        setOpenHeaderMenu(null);
                      }}
                      onSortDesc={() => {
                        setSort({ column: column.key, direction: "desc" });
                        setOpenHeaderMenu(null);
                      }}
                      onClearSort={() => {
                        setSort({ column: null, direction: "asc" });
                        setOpenHeaderMenu(null);
                      }}
                      onApplyFilter={(values) => {
                        setColumnFilters((current) => ({ ...current, [column.key]: values }));
                      }}
                      onClose={() => setOpenHeaderMenu(null)}
                      style={openHeaderMenu}
                    />
                  ) : null}
                  <div
                    className="column-resize-handle"
                    onMouseDown={(event) => handleColumnResizeStart(event, colIndex)}
                    onDoubleClick={(event) => { event.stopPropagation(); handleColumnAutoFit(colIndex); }}
                    onClick={(event) => event.stopPropagation()}
                  />
                </div>
              );
            })}
          </div>

          <table className="data-table users-data-table" style={columnWidths ? { tableLayout: "fixed" } : undefined}>
            <colgroup>
              <col style={{ width: "36px" }} />
              {columnWidths
                ? columnWidths.map((w, i) => <col key={i} style={{ width: `${w}px` }} />)
                : <>
                    {defaultColumnWidths.map((w, i) => <col key={i} style={{ width: w }} />)}
                    <col />
                  </>
              }
            </colgroup>
            <tbody>
              {filteredItems.length ? filteredItems.map((item) => (
                <tr
                  key={item.id}
                  className={[selectedIds.includes(item.id) ? "selected-row" : "", getRowClassName ? getRowClassName(item) : ""].filter(Boolean).join(" ") || undefined}
                  aria-selected={selectedIds.includes(item.id)}
                  onMouseDown={(event) => {
                    if (event.shiftKey || event.metaKey || event.ctrlKey) {
                      event.preventDefault();
                    }
                  }}
                  onClick={(event) => handleRowSelection(event, item.id)}
                  onDoubleClick={() => openModal("view", item)}
                  onContextMenu={(event) => handleTableContextMenu(event, item)}
                >
                  <td className="row-checkbox-cell" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="row-select-checkbox"
                      aria-label={`Select ${item.name}`}
                      checked={selectedIds.includes(item.id)}
                      onChange={() => handleRowCheckboxChange(item.id)}
                    />
                  </td>
                  {columns.map((column) => {
                    const isNotes = column.key === "notes";
                    const cellSelected = selectedCells.has(`${item.id}:${column.key}`);
                    const colSelected = selectedColumnKeys.has(column.key);
                    const selectionClass = cellSelected ? "selected-cell" : colSelected ? "selected-column-cell" : "";
                    const className = isNotes
                      ? `notes-cell${selectionClass ? ` ${selectionClass}` : ""}`
                      : selectionClass || undefined;
                    const title = isNotes && (item[column.key] || "").length > 100 ? item[column.key] : undefined;

                    return (
                      <td
                        key={column.key}
                        data-col={column.key}
                        className={className}
                        title={title}
                        onClick={(event) => { if (handleCellClick(event, item.id, column.key)) return; }}
                      >
                        {renderCell(item, column.key, search)}
                      </td>
                    );
                  })}
                </tr>
              )) : (
                <tr>
                  <td colSpan={columns.length + 1} className="empty-state-cell">
                    <div className="empty-state-graphic">
                      <svg width="64" height="64" viewBox="0 0 64 64" fill="none" aria-hidden="true">
                        <rect x="8" y="16" width="48" height="36" rx="4" stroke="rgba(255,255,255,0.12)" strokeWidth="1.5" />
                        <line x1="8" y1="28" x2="56" y2="28" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
                        <line x1="8" y1="38" x2="56" y2="38" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                        <line x1="28" y1="16" x2="28" y2="52" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                        <circle cx="32" cy="40" r="8" stroke="rgba(126,195,172,0.25)" strokeWidth="1.5" />
                        <line x1="38" y1="46" x2="44" y2="52" stroke="rgba(126,195,172,0.25)" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                      <p>{hostedWorkspaceReady
                        ? (search
                          ? <>No results for &ldquo;{search}&rdquo;. <button className="inline-link-button" type="button" onClick={() => { setSearch(""); clearSelection(); }}>Clear search</button></>
                          : `No ${entityName} match the current view.`)
                        : `Connect the hosted workspace to load ${entityName}.`
                      }</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="users-summary-rail users-summary-rail-bottom" aria-label={`${singularCap} summary`}>
          <div className="users-page-metrics">
            {status && status !== `Hosted ${entityName} ready.` ? <span className="users-metric-chip subdued">{status}</span> : null}
            <span className="users-metric-chip">{filteredCount} shown</span>
            <span className="users-metric-chip subdued">{totalCount} total</span>
            {selectedIds.length ? <span className="users-metric-chip accent">{selectedIds.length} selected</span> : null}
            {filtersActive ? <span className="users-metric-chip subdued">Filtered view</span> : null}
            {selectedCells.size ? (() => {
              const cellValues = [];
              for (const cellId of selectedCells) {
                const [itemId, colKey] = cellId.split(":");
                const item = filteredItems.find((i) => i.id === itemId);
                if (item) cellValues.push(getCellDisplayValue(item, colKey));
              }
              const stats = computeCellStats(cellValues);
              return (
                <>
                  <span className="users-metric-chip column-agg">Count: {stats.count}</span>
                  {stats.numericCount > 0 ? (
                    <>
                      <span className="users-metric-chip column-agg">Sum: {stats.sum.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</span>
                      <span className="users-metric-chip column-agg">Avg: {stats.avg.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}</span>
                      <span className="users-metric-chip column-agg">Min: {stats.min}</span>
                      <span className="users-metric-chip column-agg">Max: {stats.max}</span>
                    </>
                  ) : null}
                  {stats.numericCount === 0 ? <span className="users-metric-chip column-agg">{new Set(cellValues).size} unique</span> : null}
                </>
              );
            })() : null}
          </div>
          <div className="users-summary-actions">
            {hasMore && !filtersActive ? (
              <button className="ghost-button" type="button" onClick={loadNextPage} disabled={loadingMore}>
                {loadingMore ? "Loading..." : `Load More ${singularCap}s`}
              </button>
            ) : null}
          </div>
        </div>

        <button
          className={`back-to-top-button${showBackToTop ? " visible" : ""}`}
          type="button"
          aria-label="Back to top"
          onClick={() => {
            const viewport = tableViewportRef.current;
            if (viewport) viewport.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          {"\u2191"}
        </button>
      </div>

      {contextMenu ? (
        <TableContextMenu
          position={{ x: contextMenu.x, y: contextMenu.y }}
          items={contextMenu.items}
          onClose={() => setContextMenu(null)}
        />
      ) : null}

      {exportModalOpen ? (
        <ExportModal
          filteredItems={filteredItems}
          selectedItems={selectedItems}
          selectedCells={selectedCells}
          allColumns={columns}
          getCellDisplayValue={getCellDisplayValue}
          onExport={(exportData, exportCols) => downloadCsv(exportData, exportCols, getCellDisplayValue, entityName)}
          onClose={() => setExportModalOpen(false)}
        />
      ) : null}

      {confirmationState ? (
        <ConfirmationModal
          title={confirmationState.title}
          message={confirmationState.message}
          confirmLabel={confirmationState.confirmLabel}
          cancelLabel={confirmationState.cancelLabel}
          tone={confirmationState.tone}
          onCancel={() => setConfirmationState(null)}
          onConfirm={confirmationState.onConfirm}
        />
      ) : null}

      {children}
    </section>
  );
}
