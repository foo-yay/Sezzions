import { useEffect, useMemo, useRef, useState } from "react";

import { authHeaders, describeFetchFailure, getAccessToken } from "../services/api";
import { computeCellStats, isTextEntryElement, mergeItemsById } from "../utils/tableUtils";

/**
 * Shared hook for entity table tabs (Users, Sites, Cards, etc.).
 *
 * Encapsulates all common state, data loading, selection, keyboard navigation,
 * copy-to-clipboard, context menu, column resize, pagination, and CRUD logic.
 *
 * @param {object} config - Entity-specific configuration.
 * @param {object} env    - Runtime environment: { apiBaseUrl, hostedWorkspaceReady }.
 */
export default function useEntityTable(config, { apiBaseUrl, hostedWorkspaceReady }) {
  const {
    entityName,
    entitySingular,
    apiEndpoint,
    responseKey,
    batchDeleteIdKey,
    columns,
    initialForm,
    initialColumnFilters,
    pageSize = 100,
    fallbackPageSize = 500,
    getColumnValue,
    getCellDisplayValue,
    searchFilter,
    numericSortColumns = [],
    normalizeForm,
    itemToForm,
    formToPayload,
    buildFilterOptions,
    buildSuggestions,
    extraLoaders = [],
    mergeById = mergeItemsById,
  } = config;

  // ── Refs ──────────────────────────────────────────────────────────────────

  const scrollGateRef = useRef({ armed: false, lastScrollTop: 0 });
  const pagingRequestRef = useRef(false);
  const tableViewportRef = useRef(null);
  const navCursorRef = useRef(null);
  const cellAnchorRef = useRef(null);
  const columnResizeRef = useRef(null);
  const headerRef = useRef(null);

  // ── State ─────────────────────────────────────────────────────────────────

  const [items, setItems] = useState([]);
  const [status, setStatus] = useState(`Sign in to load hosted ${entityName}.`);
  const [search, setSearch] = useState("");
  const [columnFilters, setColumnFilters] = useState(initialColumnFilters);
  const [sort, setSort] = useState({ column: null, direction: "asc" });
  const [openHeaderMenu, setOpenHeaderMenu] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [selectionAnchorId, setSelectionAnchorId] = useState(null);
  const [selectedColumnKeys, setSelectedColumnKeys] = useState(new Set());
  const [selectedCells, setSelectedCells] = useState(new Set());
  const [totalCount, setTotalCount] = useState(null);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const [columnWidths, setColumnWidths] = useState(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [formBaseline, setFormBaseline] = useState(initialForm);
  const [submitError, setSubmitError] = useState(null);
  const [confirmationState, setConfirmationState] = useState(null);
  const [extraData, setExtraData] = useState({});

  // ── Derived state ─────────────────────────────────────────────────────────

  const filteredItems = useMemo(() => {
    const searchText = search.trim().toLowerCase();
    const searchFiltered = !searchText
      ? items
      : items.filter((item) => searchFilter(item, searchText));

    const columnFiltered = searchFiltered.filter((item) => {
      for (const col of columns) {
        const filterValues = columnFilters[col.key];
        if (filterValues && filterValues.length && !filterValues.includes(getColumnValue(item, col.key))) {
          return false;
        }
      }
      return true;
    });

    if (!sort.column) {
      return columnFiltered;
    }

    const sorted = [...columnFiltered].sort((left, right) => {
      const leftValue = getColumnValue(left, sort.column);
      const rightValue = getColumnValue(right, sort.column);

      if (numericSortColumns.includes(sort.column)) {
        const leftNum = parseFloat(leftValue) || 0;
        const rightNum = parseFloat(rightValue) || 0;
        return leftNum - rightNum;
      }

      return leftValue.localeCompare(rightValue, undefined, { sensitivity: "base" });
    });

    return sort.direction === "desc" ? sorted.reverse() : sorted;
  }, [columnFilters, items, search, sort]);

  const filterOptions = useMemo(
    () => buildFilterOptions(items),
    [items]
  );

  const filteredCount = filteredItems.length;
  const totalCountDisplay = totalCount ?? items.length;

  const selectedItems = items.filter((item) => selectedIds.includes(item.id));
  const selectedItem = selectedItems.length === 1 ? selectedItems[0] : null;
  const modalDirty = modalMode && modalMode !== "view"
    ? JSON.stringify(normalizeForm(form)) !== JSON.stringify(normalizeForm(formBaseline))
    : false;

  const filtersActive = Boolean(
    search
    || Object.values(columnFilters).some((values) => values.length)
    || sort.column
  );

  const suggestions = useMemo(
    () => (buildSuggestions ? buildSuggestions(items) : {}),
    [items]
  );

  // ── Selection helpers ─────────────────────────────────────────────────────

  function clearSelection() {
    setSelectedIds([]);
    setSelectionAnchorId(null);
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
  }

  // ── Modal helpers ─────────────────────────────────────────────────────────

  function closeModalImmediately() {
    setModalMode(null);
    setSubmitError(null);
    setForm(initialForm);
    setFormBaseline(initialForm);
  }

  function openConfirmation(options) {
    setConfirmationState(options);
  }

  function requestCloseModal() {
    if (!modalDirty) {
      closeModalImmediately();
      return;
    }

    openConfirmation({
      title: "Discard unsaved changes?",
      message: "You have changes in this form that have not been saved.",
      confirmLabel: "Discard Changes",
      cancelLabel: "Keep Editing",
      tone: "danger",
      onConfirm: () => {
        setConfirmationState(null);
        closeModalImmediately();
      }
    });
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async function loadItems(accessToken, { append = false } = {}) {
    if (!accessToken) {
      setItems([]);
      setTotalCount(null);
      setNextOffset(0);
      setHasMore(false);
      clearSelection();
      setStatus(`Sign in to load hosted ${entityName}.`);
      return;
    }

    if (!apiBaseUrl) {
      setItems([]);
      setTotalCount(null);
      setNextOffset(0);
      setHasMore(false);
      clearSelection();
      setStatus(`Set VITE_API_BASE_URL to enable hosted ${entityName}.`);
      return;
    }

    const requestOffset = append ? nextOffset : 0;
    if (append) {
      setLoadingMore(true);
    } else {
      setLoadingInitial(true);
      setStatus(`Loading hosted ${entityName}...`);
    }

    try {
      const response = await fetch(`${apiBaseUrl}${apiEndpoint}?limit=${pageSize}&offset=${requestOffset}`, {
        headers: authHeaders(accessToken)
      });
      const payload = await response.json();

      if (!response.ok) {
        setItems([]);
        setTotalCount(null);
        setNextOffset(0);
        setHasMore(false);
        clearSelection();
        setStatus(payload.detail || `Hosted ${entityName} failed to load (${response.status}).`);
        return;
      }

      const payloadItems = Array.isArray(payload[responseKey]) ? payload[responseKey] : [];
      let loadedItems = payloadItems.slice(0, pageSize);
      let mergedItems = append ? mergeById(items, loadedItems) : loadedItems;
      let reportedTotal = Number.isFinite(payload.total_count) ? payload.total_count : null;
      let nxt = requestOffset + loadedItems.length;
      let inferredMore = loadedItems.length === pageSize;
      let more = Boolean(payload.has_more) || nxt < (reportedTotal ?? 0) || inferredMore;

      if (append && loadedItems.length && mergedItems.length === items.length) {
        const fallbackResponse = await fetch(`${apiBaseUrl}${apiEndpoint}?limit=${fallbackPageSize}&offset=0`, {
          headers: authHeaders(accessToken)
        });
        const fallbackPayload = await fallbackResponse.json();

        if (fallbackResponse.ok) {
          const fallbackItems = Array.isArray(fallbackPayload[responseKey])
            ? fallbackPayload[responseKey].slice(0, fallbackPageSize)
            : [];
          const fallbackMerged = mergeById(items, fallbackItems);

          if (fallbackMerged.length > items.length) {
            loadedItems = fallbackItems;
            mergedItems = fallbackMerged;
            reportedTotal = Number.isFinite(fallbackPayload.total_count)
              ? fallbackPayload.total_count
              : reportedTotal;
            nxt = mergedItems.length;
            inferredMore = fallbackItems.length === fallbackPageSize;
            more = Boolean(fallbackPayload.has_more)
              || nxt < (reportedTotal ?? 0)
              || inferredMore;
          } else {
            more = false;
          }
        } else {
          more = false;
        }
      }

      const computedTotal = Math.max(reportedTotal ?? 0, mergedItems.length);

      if (!append) {
        scrollGateRef.current = {
          armed: false,
          lastScrollTop: tableViewportRef.current?.scrollTop || 0,
        };
      }

      setItems(mergedItems);
      setTotalCount(computedTotal);
      setNextOffset(nxt);
      setHasMore(more);
      setSelectedIds((current) => current.filter((id) => mergedItems.some((item) => item.id === id)));

      if (!mergedItems.length) {
        setStatus(`No hosted ${entityName} yet. Add your first ${entitySingular} to get started.`);
      } else if (more) {
        setStatus(`Loaded ${mergedItems.length} of ${computedTotal} hosted ${entityName}.`);
      } else {
        setStatus(`Hosted ${entityName} ready.`);
      }
    } catch (error) {
      setItems([]);
      setTotalCount(null);
      setNextOffset(0);
      setHasMore(false);
      clearSelection();
      setStatus(describeFetchFailure(error, `Hosted ${entityName} failed to load.`));
    } finally {
      setLoadingInitial(false);
      setLoadingMore(false);
    }
  }

  async function runExtraLoaders(accessToken) {
    if (!extraLoaders.length) return;
    const results = {};
    await Promise.all(
      extraLoaders.map(async ({ key, load }) => {
        try {
          results[key] = await load(accessToken, apiBaseUrl);
        } catch {
          // Extra loaders are supplementary; silent failure is acceptable
        }
      })
    );
    setExtraData((current) => ({ ...current, ...results }));
  }

  // ── Effects ───────────────────────────────────────────────────────────────

  // Load items when workspace becomes ready
  useEffect(() => {
    if (!hostedWorkspaceReady || !apiBaseUrl) return;
    (async () => {
      try {
        const accessToken = await getAccessToken();
        if (accessToken) {
          await Promise.all([loadItems(accessToken), runExtraLoaders(accessToken)]);
        }
      } catch (error) {
        setStatus(describeFetchFailure(error, `Hosted ${entityName} failed to load.`));
      }
    })();
  }, [hostedWorkspaceReady]);

  // Header menu close on outside click
  useEffect(() => {
    if (!openHeaderMenu) return undefined;

    function handlePointerDown(event) {
      if (event.target instanceof Element && event.target.closest(".table-header-menu-wrap, .table-header-menu")) return;
      setOpenHeaderMenu(null);
    }

    function handleViewportChange() {
      setOpenHeaderMenu(null);
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("resize", handleViewportChange);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("resize", handleViewportChange);
    };
  }, [openHeaderMenu]);

  // Escape key handler for modals
  useEffect(() => {
    const anyModalOpen = Boolean(openHeaderMenu || modalMode || confirmationState || exportModalOpen);
    if (!anyModalOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key !== "Escape") return;

      const activeElement = document.activeElement;
      const blurActiveTextFieldWithin = (selector) => {
        if (!isTextEntryElement(activeElement)) return false;
        if (!(activeElement instanceof Element) || !activeElement.closest(selector)) return false;
        activeElement.blur();
        return true;
      };

      event.preventDefault();
      event.stopImmediatePropagation();

      if (confirmationState) { setConfirmationState(null); return; }

      if (openHeaderMenu) {
        if (blurActiveTextFieldWithin(".table-header-menu")) return;
        setOpenHeaderMenu(null);
        return;
      }

      if (modalMode) {
        if (blurActiveTextFieldWithin(".modal-card")) return;
        requestCloseModal();
        return;
      }

      if (exportModalOpen) { setExportModalOpen(false); }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmationState, exportModalOpen, openHeaderMenu, modalMode, modalDirty]);

  // Keyboard navigation (Ctrl+C, Ctrl+A, Ctrl+F, arrows, Enter, Escape in search)
  useEffect(() => {
    function handleArrowNav(event) {
      // Ctrl+C — copy cells or rows
      if (event.key === "c" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (selectedCells.size) { event.preventDefault(); copyCellsAsTSV(); return; }
        if (selectedIds.length) { event.preventDefault(); copyRowsAsTSV(); return; }
        return;
      }

      // Ctrl+A — select / deselect all
      if (event.key === "a" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (confirmationState || modalMode || openHeaderMenu) return;
        if (!filteredItems.length) return;
        event.preventDefault();
        if (selectedIds.length === filteredItems.length && filteredItems.every((item) => selectedIds.includes(item.id))) {
          setSelectedIds([]);
          setSelectionAnchorId(null);
          navCursorRef.current = null;
        } else {
          setSelectedIds(filteredItems.map((item) => item.id));
          setSelectionAnchorId(filteredItems[0].id);
          navCursorRef.current = filteredItems[filteredItems.length - 1].id;
        }
        return;
      }

      // Ctrl+F — focus search
      if (event.key === "f" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (confirmationState || modalMode || openHeaderMenu) return;
        event.preventDefault();
        const searchInput = document.getElementById(`${entityName}-search-input`);
        if (searchInput) { searchInput.focus(); searchInput.select(); }
        return;
      }

      // Escape — clear search or blur
      if (event.key === "Escape") {
        const searchInput = document.getElementById(`${entityName}-search-input`);
        if (document.activeElement === searchInput) {
          event.preventDefault();
          if (search) { setSearch(""); } else { searchInput.blur(); }
          return;
        }
      }

      // Arrow / Enter navigation
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown" && event.key !== "Enter") return;
      if (isTextEntryElement(document.activeElement)) return;
      if (confirmationState || modalMode || openHeaderMenu) return;

      if (event.key === "Enter") {
        if (selectedIds.length === 1) {
          const item = filteredItems.find((i) => i.id === selectedIds[0]);
          if (item) openModal("view", item);
        }
        return;
      }

      if (!filteredItems.length || !selectedIds.length) return;

      event.preventDefault();
      const orderedIds = filteredItems.map((item) => item.id);
      const cursorId = navCursorRef.current ?? selectedIds[selectedIds.length - 1];
      const currentIndex = orderedIds.indexOf(cursorId);
      if (currentIndex === -1) return;

      const nextIndex = event.key === "ArrowDown"
        ? Math.min(currentIndex + 1, orderedIds.length - 1)
        : Math.max(currentIndex - 1, 0);
      const nextId = orderedIds[nextIndex];
      navCursorRef.current = nextId;

      if (event.shiftKey) {
        setSelectedIds(() => {
          const anchor = selectionAnchorId && orderedIds.includes(selectionAnchorId)
            ? orderedIds.indexOf(selectionAnchorId)
            : currentIndex;
          const [start, end] = anchor < nextIndex ? [anchor, nextIndex] : [nextIndex, anchor];
          return orderedIds.slice(start, end + 1);
        });
      } else {
        setSelectedIds([nextId]);
        setSelectionAnchorId(nextId);
      }

      const viewport = tableViewportRef.current;
      if (viewport) {
        requestAnimationFrame(() => {
          const row = viewport.querySelector(`tbody tr:nth-child(${nextIndex + 1})`);
          if (row) row.scrollIntoView({ block: "nearest" });
        });
      }
    }

    window.addEventListener("keydown", handleArrowNav);
    return () => window.removeEventListener("keydown", handleArrowNav);
  }, [confirmationState, filteredItems, openHeaderMenu, selectedCells, selectedIds, selectionAnchorId, modalMode]);

  // Infinite scroll paging
  useEffect(() => {
    if (!hasMore || filtersActive || loadingInitial || loadingMore || !hostedWorkspaceReady) return undefined;

    const viewport = tableViewportRef.current;
    if (!viewport) return undefined;

    function handleViewportScroll() {
      const scrollTop = viewport.scrollTop || 0;
      const scrollGate = scrollGateRef.current;

      if (!scrollGate.armed) {
        if (scrollTop <= scrollGate.lastScrollTop) return;
        scrollGate.armed = true;
      }

      scrollGate.lastScrollTop = scrollTop;
      const viewportBottom = scrollTop + viewport.clientHeight;
      const documentHeight = viewport.scrollHeight;

      if (documentHeight - viewportBottom <= 220) {
        loadNextPage();
      }
    }

    viewport.addEventListener("scroll", handleViewportScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleViewportScroll);
  }, [hostedWorkspaceReady, filtersActive, hasMore, loadingInitial, loadingMore, nextOffset]);

  // ── Sort / filter ─────────────────────────────────────────────────────────

  function toggleSort(column) {
    setSort((current) => {
      if (current.column !== column) return { column, direction: "asc" };
      if (current.direction === "asc") return { column, direction: "desc" };
      return { column: null, direction: "asc" };
    });
  }

  function clearAllFilters() {
    setSearch("");
    setColumnFilters(initialColumnFilters);
    setSort({ column: null, direction: "asc" });
    setOpenHeaderMenu(null);
    clearSelection();
  }

  // ── Row / cell selection ──────────────────────────────────────────────────

  function handleRowSelection(event, itemId) {
    event.preventDefault();
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
    const orderedIds = filteredItems.map((item) => item.id);

    if (event.shiftKey && selectionAnchorId && orderedIds.includes(selectionAnchorId)) {
      const anchorIndex = orderedIds.indexOf(selectionAnchorId);
      const targetIndex = orderedIds.indexOf(itemId);
      const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
      const rangeIds = orderedIds.slice(start, end + 1);
      setSelectedIds((current) => (event.metaKey || event.ctrlKey ? [...new Set([...current, ...rangeIds])] : rangeIds));
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      setSelectedIds((current) =>
        current.includes(itemId)
          ? current.filter((id) => id !== itemId)
          : [...current, itemId]
      );
      setSelectionAnchorId(itemId);
      return;
    }

    setSelectedIds([itemId]);
    setSelectionAnchorId(itemId);
    navCursorRef.current = itemId;
  }

  function handleCellClick(event, itemId, columnKey) {
    if (!event.altKey) return false;
    event.stopPropagation();
    event.preventDefault();

    setSelectedIds([]);
    setSelectionAnchorId(null);

    const cellId = `${itemId}:${columnKey}`;
    const columnKeys = columns.map((c) => c.key);

    if (event.shiftKey && cellAnchorRef.current) {
      const anchor = cellAnchorRef.current;
      const orderedIds = filteredItems.map((item) => item.id);
      const anchorRowIdx = orderedIds.indexOf(anchor.itemId);
      const targetRowIdx = orderedIds.indexOf(itemId);
      const anchorColIdx = columnKeys.indexOf(anchor.columnKey);
      const targetColIdx = columnKeys.indexOf(columnKey);
      if (anchorRowIdx === -1 || targetRowIdx === -1) return true;

      const [rowStart, rowEnd] = anchorRowIdx < targetRowIdx ? [anchorRowIdx, targetRowIdx] : [targetRowIdx, anchorRowIdx];
      const [colStart, colEnd] = anchorColIdx < targetColIdx ? [anchorColIdx, targetColIdx] : [targetColIdx, anchorColIdx];

      const next = new Set();
      for (let r = rowStart; r <= rowEnd; r++) {
        for (let c = colStart; c <= colEnd; c++) {
          next.add(`${orderedIds[r]}:${columnKeys[c]}`);
        }
      }
      setSelectedCells(next);
      setSelectedColumnKeys(new Set());
    } else {
      if (event.metaKey || event.ctrlKey) {
        setSelectedCells((current) => {
          const next = new Set(current);
          if (next.has(cellId)) next.delete(cellId); else next.add(cellId);
          return next;
        });
      } else {
        setSelectedCells((current) => current.size === 1 && current.has(cellId) ? new Set() : new Set([cellId]));
      }
      setSelectedColumnKeys(new Set());
      cellAnchorRef.current = { itemId, columnKey };
    }
    return true;
  }

  // ── Copy ──────────────────────────────────────────────────────────────────

  function copyCellsAsTSV() {
    const columnKeys = columns.map((c) => c.key);
    const orderedIds = filteredItems.map((item) => item.id);
    const rows = [];
    for (const id of orderedIds) {
      const row = [];
      let hasCell = false;
      for (const col of columnKeys) {
        if (selectedCells.has(`${id}:${col}`)) {
          const item = filteredItems.find((x) => x.id === id);
          row.push(item ? getCellDisplayValue(item, col) : "");
          hasCell = true;
        } else {
          row.push("");
        }
      }
      if (hasCell) rows.push(row);
    }
    const usedCols = columnKeys.map((_, ci) => rows.some((r) => r[ci] !== ""));
    const tsv = rows.map((r) => r.filter((_, ci) => usedCols[ci]).join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).catch(() => {});
  }

  function copyRowsAsTSV() {
    const columnKeys = columns.map((c) => c.key);
    const orderedIds = filteredItems.map((item) => item.id);
    const rows = [];
    for (const id of orderedIds) {
      if (!selectedIds.includes(id)) continue;
      const item = filteredItems.find((x) => x.id === id);
      if (!item) continue;
      rows.push(columnKeys.map((col) => getCellDisplayValue(item, col)));
    }
    const tsv = rows.map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).catch(() => {});
  }

  // ── Context menu ──────────────────────────────────────────────────────────

  function handleTableContextMenu(event, item) {
    event.preventDefault();
    setContextMenu(null);

    let td = event.target;
    while (td && td.tagName !== "TD") td = td.parentElement;
    const clickedColumnKey = td?.dataset?.col || null;

    const menuItems = [];
    const isRowSelected = selectedIds.includes(item.id);
    const hasCellSelection = selectedCells.size > 0;
    const hasRowSelection = selectedIds.length > 0;

    if (clickedColumnKey) {
      const cellValue = getCellDisplayValue(item, clickedColumnKey);
      const truncated = cellValue.length > 30 ? `${cellValue.slice(0, 27)}\u2026` : cellValue;
      menuItems.push({ label: `Copy "${truncated}"`, action: () => { navigator.clipboard.writeText(cellValue).catch(() => {}); } });
    }

    if (hasCellSelection) {
      menuItems.push({ label: `Copy ${selectedCells.size} cell${selectedCells.size > 1 ? "s" : ""}`, action: copyCellsAsTSV });
    }

    if (hasRowSelection) {
      const count = selectedIds.length;
      menuItems.push({ label: count > 1 ? `Copy ${count} rows` : "Copy row", action: copyRowsAsTSV });
    }

    menuItems.push({ divider: true });

    if (!isRowSelected) {
      menuItems.push({ label: "Select row", action: () => { setSelectedIds([item.id]); setSelectionAnchorId(item.id); } });
      menuItems.push({ divider: true });
    }

    const targetItems = isRowSelected ? selectedItems : [item];
    const targetCount = targetItems.length;

    menuItems.push({ label: "View", action: () => openModal("view", targetCount === 1 ? targetItems[0] : item), disabled: targetCount !== 1 });
    menuItems.push({ label: "Edit", action: () => openModal("edit", targetCount === 1 ? targetItems[0] : item), disabled: targetCount !== 1 });
    menuItems.push({ divider: true });

    if (hasCellSelection) {
      menuItems.push({ label: "Clear cell selection", action: () => { setSelectedCells(new Set()); setSelectedColumnKeys(new Set()); cellAnchorRef.current = null; } });
    }

    menuItems.push({
      label: targetCount > 1 ? `Delete ${targetCount} ${entityName}` : "Delete",
      danger: true,
      action: () => handleDelete(targetItems),
      disabled: !hostedWorkspaceReady
    });

    setContextMenu({ x: event.clientX, y: event.clientY, items: menuItems });
  }

  // ── Column resize ─────────────────────────────────────────────────────────

  function getComputedColumnWidths() {
    const header = headerRef.current;
    if (!header) return null;
    const cells = header.querySelectorAll(".users-table-header-cell");
    const widths = [];
    for (let i = 1; i < cells.length; i++) {
      widths.push(cells[i].getBoundingClientRect().width);
    }
    return widths.length === columns.length ? widths : null;
  }

  function getColumnMinWidth(colIndex) {
    const header = headerRef.current;
    if (!header) return 80;
    const cells = header.querySelectorAll(".users-table-header-cell");
    const cell = cells[colIndex + 1];
    if (!cell) return 80;
    const label = cell.querySelector(".users-table-header-label");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = "0.71rem -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    const labelW = label ? ctx.measureText(label.textContent || "").width : 30;
    return Math.ceil(labelW + 57);
  }

  function handleColumnResizeStart(event, colIndex) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    let widths = columnWidths || getComputedColumnWidths();
    if (!widths) return;
    widths = [...widths];
    const startWidth = widths[colIndex];

    const minWidths = widths.map((_, i) => getColumnMinWidth(i));

    function ensureViewportFill(w) {
      const viewport = tableViewportRef.current;
      if (!viewport) return w;
      const available = viewport.clientWidth - 36;
      const total = w.reduce((a, b) => a + b, 0);
      if (total < available) {
        const result = [...w];
        result[result.length - 1] += available - total;
        return result;
      }
      return w;
    }

    function onMouseMove(moveEvent) {
      const delta = moveEvent.clientX - startX;
      widths[colIndex] = Math.max(minWidths[colIndex], startWidth + delta);
      setColumnWidths(ensureViewportFill([...widths]));
    }

    function onMouseUp() {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      columnResizeRef.current = null;
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    columnResizeRef.current = true;
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }

  function handleColumnAutoFit(colIndex) {
    let widths = columnWidths || getComputedColumnWidths();
    if (!widths) return;
    widths = [...widths];

    const columnKey = columns[colIndex]?.key;
    if (!columnKey) return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = "0.84rem -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    let maxWidth = 60;

    const header = headerRef.current;
    if (header) {
      const headerCells = header.querySelectorAll(".users-table-header-cell");
      if (headerCells[colIndex + 1]) {
        const label = headerCells[colIndex + 1].querySelector(".users-table-header-label");
        if (label) {
          const textWidth = ctx.measureText(label.textContent || "").width;
          maxWidth = Math.max(maxWidth, textWidth + 52);
        }
      }
    }

    for (const item of filteredItems) {
      const value = getCellDisplayValue(item, columnKey);
      const textWidth = ctx.measureText(value).width;
      maxWidth = Math.max(maxWidth, textWidth + 24);
    }

    widths[colIndex] = Math.min(Math.ceil(maxWidth), 600);

    const viewport = tableViewportRef.current;
    if (viewport) {
      const available = viewport.clientWidth - 36;
      const total = widths.reduce((a, b) => a + b, 0);
      if (total < available) {
        widths[widths.length - 1] += available - total;
      }
    }
    setColumnWidths([...widths]);
  }

  // ── Paging ────────────────────────────────────────────────────────────────

  async function loadNextPage() {
    if (pagingRequestRef.current || loadingInitial || loadingMore || !hasMore || filtersActive) return;

    pagingRequestRef.current = true;
    try {
      const accessToken = await getAccessToken();
      if (accessToken) {
        await loadItems(accessToken, { append: true });
      }
    } catch (error) {
      setStatus(describeFetchFailure(error, `Hosted ${entityName} failed to load.`));
    } finally {
      pagingRequestRef.current = false;
    }
  }

  // ── Header menu ───────────────────────────────────────────────────────────

  function openHeaderOptions(event, columnKey) {
    const buttonRect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 296;
    const left = Math.max(16, Math.min(buttonRect.right - menuWidth, window.innerWidth - menuWidth - 16));
    const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 24);
    setOpenHeaderMenu((current) => current?.key === columnKey ? null : { key: columnKey, left, top });
  }

  // ── CRUD ──────────────────────────────────────────────────────────────────

  function openModal(mode, item = null) {
    setModalMode(mode);
    setSubmitError(null);

    if (item) {
      const nextForm = itemToForm(item);
      setForm(nextForm);
      setFormBaseline(nextForm);
      setSelectedIds([item.id]);
      setSelectionAnchorId(item.id);
      return;
    }

    setForm(initialForm);
    setFormBaseline(initialForm);
  }

  async function submitModal() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setSubmitError(`Google sign-in is required before managing hosted ${entityName}.`);
      return;
    }

    if (!apiBaseUrl) {
      setSubmitError(`Set VITE_API_BASE_URL to enable hosted ${entityName}.`);
      return;
    }

    const payload = formToPayload(form, modalMode);
    const url = modalMode === "edit" && selectedItem
      ? `${apiBaseUrl}${apiEndpoint}/${selectedItem.id}`
      : `${apiBaseUrl}${apiEndpoint}`;
    const method = modalMode === "edit" ? "PATCH" : "POST";

    try {
      const response = await fetch(url, {
        method,
        headers: {
          ...authHeaders(accessToken),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (!response.ok) {
        setSubmitError(data.detail || `Hosted ${entityName} save failed (${response.status}).`);
        return;
      }

      setItems((current) => mergeById(current, [data]));
      setTotalCount((current) => (method === "POST" && current !== null ? current + 1 : current));
      setSelectedIds([data.id]);
      setSelectionAnchorId(data.id);
      setStatus(`Hosted ${entityName} ready.`);
      closeModalImmediately();
    } catch (error) {
      setSubmitError(describeFetchFailure(error, `Hosted ${entityName} save failed.`));
    }
  }

  async function handleRefresh() {
    try {
      const accessToken = await getAccessToken();
      clearSelection();
      await Promise.all([loadItems(accessToken, { append: false }), runExtraLoaders(accessToken)]);
    } catch (error) {
      setStatus(describeFetchFailure(error, `Hosted ${entityName} failed to load.`));
    }
  }

  async function handleDelete(itemsToDelete = selectedItems) {
    const accessToken = await getAccessToken();
    if (!itemsToDelete.length || !accessToken) {
      setStatus(`Google sign-in is required before managing hosted ${entityName}.`);
      return;
    }
    if (!apiBaseUrl) {
      setStatus(`Set VITE_API_BASE_URL to enable hosted ${entityName}.`);
      return;
    }

    const singularCap = entitySingular.charAt(0).toUpperCase() + entitySingular.slice(1);
    const pluralCap = entityName.charAt(0).toUpperCase() + entityName.slice(1);
    const prompt = itemsToDelete.length === 1
      ? `Delete ${entitySingular} '${itemsToDelete[0].name}'? This cannot be undone.`
      : `Delete ${itemsToDelete.length} ${entityName}? This cannot be undone.`;

    openConfirmation({
      title: itemsToDelete.length === 1 ? `Delete ${entitySingular}?` : `Delete ${entityName}?`,
      message: prompt,
      confirmLabel: itemsToDelete.length === 1 ? `Delete ${singularCap}` : `Delete ${itemsToDelete.length} ${pluralCap}`,
      cancelLabel: "Cancel",
      tone: "danger",
      onConfirm: async () => {
        setConfirmationState(null);

        try {
          setStatus(`Deleting ${itemsToDelete.length} hosted ${itemsToDelete.length === 1 ? entitySingular : entityName}...`);

          const response = await fetch(`${apiBaseUrl}${apiEndpoint}/batch-delete`, {
            method: "POST",
            headers: {
              ...authHeaders(accessToken),
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              [batchDeleteIdKey]: itemsToDelete.map((item) => item.id)
            })
          });

          if (!response.ok) {
            const detail = response.headers.get("content-type")?.includes("application/json")
              ? (await response.json()).detail
              : `Hosted ${entityName} delete failed (${response.status}).`;
            setStatus(detail || `Hosted ${entityName} delete failed (${response.status}).`);
            return;
          }

          const deletedIds = new Set(itemsToDelete.map((item) => item.id));
          setItems((current) => current.filter((item) => !deletedIds.has(item.id)));
          setTotalCount((current) => (current === null ? null : Math.max(0, current - itemsToDelete.length)));
          clearSelection();
          closeModalImmediately();
          setStatus(`Hosted ${entityName} ready.`);
        } catch (error) {
          setStatus(describeFetchFailure(error, `Hosted ${entityName} delete failed.`));
        }
      }
    });
  }

  // ── Return ────────────────────────────────────────────────────────────────

  return {
    // Environment (pass-through for EntityTable)
    hostedWorkspaceReady,

    // Core state
    items, filteredItems,
    totalCount: totalCountDisplay, filteredCount,
    status,

    // Search + filter + sort
    search, setSearch,
    columnFilters, setColumnFilters,
    sort, setSort, filterOptions,
    filtersActive,
    toggleSort, clearAllFilters,

    // Selection
    selectedIds, selectedItems, selectedItem,
    selectedCells, selectedColumnKeys,
    setSelectedIds, setSelectionAnchorId,
    setSelectedCells, setSelectedColumnKeys,
    handleRowSelection, handleCellClick,
    clearSelection,

    // Modal
    modalMode, form, setForm, submitError, modalDirty,
    openModal, requestCloseModal, submitModal,

    // CRUD
    handleDelete, handleRefresh,

    // Pagination
    loadingInitial, loadingMore, hasMore,
    loadNextPage,

    // UI state
    showBackToTop, setShowBackToTop,
    contextMenu, setContextMenu,
    openHeaderMenu, setOpenHeaderMenu,
    columnWidths, setColumnWidths,
    exportModalOpen, setExportModalOpen,
    confirmationState, setConfirmationState,

    // Handlers
    handleTableContextMenu,
    openHeaderOptions,
    copyCellsAsTSV, copyRowsAsTSV,
    handleColumnResizeStart, handleColumnAutoFit,

    // Refs
    tableViewportRef, headerRef,
    cellAnchorRef, navCursorRef,

    // Derived data
    suggestions,
    extraData,
  };
}
