import { useEffect, useMemo, useRef, useState } from "react";

import { authHeaders, describeFetchFailure, getAccessToken } from "../../services/api";
import Icon from "../common/Icon";
import HighlightMatch from "../common/HighlightMatch";
import ConfirmationModal from "../common/ConfirmationModal";
import SiteModal from "./SiteModal";
import ExportModal from "../UsersTab/ExportModal";
import UserHeaderFilterMenu from "../UsersTab/UserHeaderFilterMenu";
import TableContextMenu from "../UsersTab/TableContextMenu";
import {
  initialSiteForm,
  initialSiteColumnFilters,
  siteTableColumns,
  sitesPageSize,
  sitesFallbackPageSize
} from "./sitesConstants";
import {
  normalizeSiteForm,
  isTextEntryElement,
  computeCellStats,
  getCellDisplayValue,
  downloadSitesCsv,
  getSiteColumnValue,
  buildSiteFilterOptions,
  mergeSitesById
} from "./sitesUtils";

export default function SitesTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const sitesScrollGateRef = useRef({ armed: false, lastScrollTop: 0 });
  const sitesPagingRequestRef = useRef(false);
  const sitesTableViewportRef = useRef(null);
  const siteNavCursorRef = useRef(null);
  const [sites, setSites] = useState([]);
  const [sitesStatus, setSitesStatus] = useState("Sign in to load hosted sites.");
  const [sitesSearch, setSitesSearch] = useState("");
  const [siteColumnFilters, setSiteColumnFilters] = useState(initialSiteColumnFilters);
  const [sitesSort, setSitesSort] = useState({ column: null, direction: "asc" });
  const [openSiteHeaderMenu, setOpenSiteHeaderMenu] = useState(null);
  const [selectedSiteIds, setSelectedSiteIds] = useState([]);
  const [selectionAnchorSiteId, setSelectionAnchorSiteId] = useState(null);
  const [selectedColumnKeys, setSelectedColumnKeys] = useState(new Set());
  const [selectedCells, setSelectedCells] = useState(new Set());
  const cellAnchorRef = useRef(null);
  const [sitesTotalCount, setSitesTotalCount] = useState(null);
  const [sitesNextOffset, setSitesNextOffset] = useState(0);
  const [sitesHasMore, setSitesHasMore] = useState(false);
  const [sitesLoadingInitial, setSitesLoadingInitial] = useState(false);
  const [sitesLoadingMore, setSitesLoadingMore] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const [columnWidths, setColumnWidths] = useState(null);
  const columnResizeRef = useRef(null);
  const headerRef = useRef(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [siteModalMode, setSiteModalMode] = useState(null);
  const [siteForm, setSiteForm] = useState(initialSiteForm);
  const [siteFormBaseline, setSiteFormBaseline] = useState(initialSiteForm);
  const [siteSubmitError, setSiteSubmitError] = useState(null);
  const [confirmationState, setConfirmationState] = useState(null);

  const filteredSites = useMemo(() => {
    const searchText = sitesSearch.trim().toLowerCase();
    const searchFiltered = !searchText
      ? sites
      : sites.filter((site) =>
          site.name.toLowerCase().includes(searchText)
          || (site.url || "").toLowerCase().includes(searchText)
          || (site.notes || "").toLowerCase().includes(searchText)
        );

    const columnFiltered = searchFiltered.filter((site) => {
      for (const col of siteTableColumns) {
        const filterValues = siteColumnFilters[col.key];
        if (filterValues && filterValues.length && !filterValues.includes(getSiteColumnValue(site, col.key))) {
          return false;
        }
      }
      return true;
    });

    if (!sitesSort.column) {
      return columnFiltered;
    }

    const sortedSites = [...columnFiltered].sort((left, right) => {
      const leftValue = getSiteColumnValue(left, sitesSort.column);
      const rightValue = getSiteColumnValue(right, sitesSort.column);

      // Numeric sort for numeric columns
      if (sitesSort.column === "sc_rate" || sitesSort.column === "playthrough_requirement") {
        const leftNum = parseFloat(leftValue) || 0;
        const rightNum = parseFloat(rightValue) || 0;
        return leftNum - rightNum;
      }

      return leftValue.localeCompare(rightValue, undefined, { sensitivity: "base" });
    });

    return sitesSort.direction === "desc" ? sortedSites.reverse() : sortedSites;
  }, [siteColumnFilters, sites, sitesSearch, sitesSort]);

  const siteFilterOptions = useMemo(() => {
    const options = {};
    for (const col of siteTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildSiteFilterOptions(sites, col.key);
      }
    }
    return options;
  }, [sites]);

  const filteredSiteCount = filteredSites.length;
  const totalSiteCount = sitesTotalCount ?? sites.length;

  const selectedSites = sites.filter((site) => selectedSiteIds.includes(site.id));
  const selectedSite = selectedSites.length === 1 ? selectedSites[0] : null;
  const siteModalDirty = siteModalMode && siteModalMode !== "view"
    ? JSON.stringify(normalizeSiteForm(siteForm)) !== JSON.stringify(normalizeSiteForm(siteFormBaseline))
    : false;

  const sitesFiltersActive = Boolean(
    sitesSearch
    || Object.values(siteColumnFilters).some((values) => values.length)
    || sitesSort.column
  );

  const siteSuggestions = useMemo(() => ({
    names: [...new Set(sites.map((site) => site.name).filter(Boolean))]
  }), [sites]);

  function clearSiteSelection() {
    setSelectedSiteIds([]);
    setSelectionAnchorSiteId(null);
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
  }

  function closeSiteModalImmediately() {
    setSiteModalMode(null);
    setSiteSubmitError(null);
    setSiteForm(initialSiteForm);
    setSiteFormBaseline(initialSiteForm);
  }

  function openConfirmation(options) {
    setConfirmationState(options);
  }

  function requestCloseSiteModal() {
    if (!siteModalDirty) {
      closeSiteModalImmediately();
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
        closeSiteModalImmediately();
      }
    });
  }

  // --- Data loading ---

  async function loadSites(accessToken, { append = false } = {}) {
    if (!accessToken) {
      setSites([]);
      setSitesTotalCount(null);
      setSitesNextOffset(0);
      setSitesHasMore(false);
      clearSiteSelection();
      setSitesStatus("Sign in to load hosted sites.");
      return;
    }

    if (!apiBaseUrl) {
      setSites([]);
      setSitesTotalCount(null);
      setSitesNextOffset(0);
      setSitesHasMore(false);
      clearSiteSelection();
      setSitesStatus("Set VITE_API_BASE_URL to enable hosted sites.");
      return;
    }

    const requestOffset = append ? sitesNextOffset : 0;
    if (append) {
      setSitesLoadingMore(true);
    } else {
      setSitesLoadingInitial(true);
      setSitesStatus("Loading hosted sites...");
    }

    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/sites?limit=${sitesPageSize}&offset=${requestOffset}`, {
        headers: authHeaders(accessToken)
      });
      const payload = await response.json();

      if (!response.ok) {
        setSites([]);
        setSitesTotalCount(null);
        setSitesNextOffset(0);
        setSitesHasMore(false);
        clearSiteSelection();
        setSitesStatus(payload.detail || `Hosted sites failed to load (${response.status}).`);
        return;
      }

      const payloadSites = Array.isArray(payload.sites) ? payload.sites : [];
      let loadedSites = payloadSites.slice(0, sitesPageSize);
      let mergedSites = append ? mergeSitesById(sites, loadedSites) : loadedSites;
      let reportedTotalCount = Number.isFinite(payload.total_count) ? payload.total_count : null;
      let nextOffset = requestOffset + loadedSites.length;
      let inferredHasMore = loadedSites.length === sitesPageSize;
      let hasMore = Boolean(payload.has_more) || nextOffset < (reportedTotalCount ?? 0) || inferredHasMore;

      if (append && loadedSites.length && mergedSites.length === sites.length) {
        const fallbackResponse = await fetch(`${apiBaseUrl}/v1/workspace/sites?limit=${sitesFallbackPageSize}&offset=0`, {
          headers: authHeaders(accessToken)
        });
        const fallbackPayload = await fallbackResponse.json();

        if (fallbackResponse.ok) {
          const fallbackSites = Array.isArray(fallbackPayload.sites)
            ? fallbackPayload.sites.slice(0, sitesFallbackPageSize)
            : [];
          const fallbackMergedSites = mergeSitesById(sites, fallbackSites);

          if (fallbackMergedSites.length > sites.length) {
            loadedSites = fallbackSites;
            mergedSites = fallbackMergedSites;
            reportedTotalCount = Number.isFinite(fallbackPayload.total_count)
              ? fallbackPayload.total_count
              : reportedTotalCount;
            nextOffset = mergedSites.length;
            inferredHasMore = fallbackSites.length === sitesFallbackPageSize;
            hasMore = Boolean(fallbackPayload.has_more)
              || nextOffset < (reportedTotalCount ?? 0)
              || inferredHasMore;
          } else {
            hasMore = false;
          }
        } else {
          hasMore = false;
        }
      }

      const totalCount = Math.max(reportedTotalCount ?? 0, mergedSites.length);

      if (!append) {
        sitesScrollGateRef.current = {
          armed: false,
          lastScrollTop: sitesTableViewportRef.current?.scrollTop || 0,
        };
      }

      setSites(mergedSites);
      setSitesTotalCount(totalCount);
      setSitesNextOffset(nextOffset);
      setSitesHasMore(hasMore);
      setSelectedSiteIds((current) => current.filter((siteId) => mergedSites.some((site) => site.id === siteId)));

      if (!mergedSites.length) {
        setSitesStatus("No hosted sites yet. Add your first site to get started.");
      } else if (hasMore) {
        setSitesStatus(`Loaded ${mergedSites.length} of ${totalCount} hosted sites.`);
      } else {
        setSitesStatus("Hosted sites ready.");
      }
    } catch (error) {
      setSites([]);
      setSitesTotalCount(null);
      setSitesNextOffset(0);
      setSitesHasMore(false);
      clearSiteSelection();
      setSitesStatus(describeFetchFailure(error, "Hosted sites failed to load."));
    } finally {
      setSitesLoadingInitial(false);
      setSitesLoadingMore(false);
    }
  }

  // --- Load sites when workspace becomes ready ---

  useEffect(() => {
    if (!hostedWorkspaceReady || !apiBaseUrl) {
      return;
    }

    (async () => {
      try {
        const accessToken = await getAccessToken();
        if (accessToken) {
          await loadSites(accessToken);
        }
      } catch (error) {
        setSitesStatus(describeFetchFailure(error, "Hosted sites failed to load."));
      }
    })();
  }, [hostedWorkspaceReady]);

  // --- Header menu close on outside click ---

  useEffect(() => {
    if (!openSiteHeaderMenu) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (event.target instanceof Element && event.target.closest(".table-header-menu-wrap, .table-header-menu")) {
        return;
      }
      setOpenSiteHeaderMenu(null);
    }

    function handleViewportChange() {
      setOpenSiteHeaderMenu(null);
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("resize", handleViewportChange);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("resize", handleViewportChange);
    };
  }, [openSiteHeaderMenu]);

  // --- Escape key handler ---

  useEffect(() => {
    const anyModalOpen = Boolean(
      openSiteHeaderMenu
      || siteModalMode
      || confirmationState
      || exportModalOpen
    );

    if (!anyModalOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key !== "Escape") {
        return;
      }

      const activeElement = document.activeElement;
      const blurActiveTextFieldWithin = (selector) => {
        if (!isTextEntryElement(activeElement)) {
          return false;
        }
        if (!(activeElement instanceof Element) || !activeElement.closest(selector)) {
          return false;
        }
        activeElement.blur();
        return true;
      };

      event.preventDefault();
      event.stopImmediatePropagation();

      if (confirmationState) {
        setConfirmationState(null);
        return;
      }

      if (openSiteHeaderMenu) {
        if (blurActiveTextFieldWithin(".table-header-menu")) {
          return;
        }
        setOpenSiteHeaderMenu(null);
        return;
      }

      if (siteModalMode) {
        if (blurActiveTextFieldWithin(".modal-card")) {
          return;
        }
        requestCloseSiteModal();
        return;
      }

      if (exportModalOpen) {
        setExportModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmationState, exportModalOpen, openSiteHeaderMenu, siteModalMode, siteModalDirty]);

  // --- Keyboard navigation ---

  useEffect(() => {
    function handleArrowNav(event) {
      if (event.key === "c" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (selectedCells.size) {
          event.preventDefault();
          copyCellsAsTSV();
          return;
        }
        if (selectedSiteIds.length) {
          event.preventDefault();
          copyRowsAsTSV();
          return;
        }
        return;
      }

      if (event.key === "a" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (confirmationState || siteModalMode || openSiteHeaderMenu) return;
        if (!filteredSites.length) return;
        event.preventDefault();
        if (selectedSiteIds.length === filteredSites.length && filteredSites.every((s) => selectedSiteIds.includes(s.id))) {
          setSelectedSiteIds([]);
          setSelectionAnchorSiteId(null);
          siteNavCursorRef.current = null;
        } else {
          setSelectedSiteIds(filteredSites.map((s) => s.id));
          setSelectionAnchorSiteId(filteredSites[0].id);
          siteNavCursorRef.current = filteredSites[filteredSites.length - 1].id;
        }
        return;
      }

      if (event.key === "f" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (confirmationState || siteModalMode || openSiteHeaderMenu) return;
        event.preventDefault();
        const searchInput = document.getElementById("sites-search-input");
        if (searchInput) searchInput.focus();
        return;
      }

      if (event.key === "Escape") {
        const searchInput = document.getElementById("sites-search-input");
        if (document.activeElement === searchInput) {
          event.preventDefault();
          if (sitesSearch) {
            setSitesSearch("");
          } else {
            searchInput.blur();
          }
          return;
        }
      }

      if (event.key !== "ArrowUp" && event.key !== "ArrowDown" && event.key !== "Enter") return;
      if (isTextEntryElement(document.activeElement)) return;
      if (confirmationState || siteModalMode || openSiteHeaderMenu) return;

      if (event.key === "Enter") {
        if (selectedSiteIds.length === 1) {
          const site = filteredSites.find((s) => s.id === selectedSiteIds[0]);
          if (site) openSiteModal("view", site);
        }
        return;
      }

      if (!filteredSites.length || !selectedSiteIds.length) return;

      event.preventDefault();
      const orderedIds = filteredSites.map((s) => s.id);
      const cursorId = siteNavCursorRef.current ?? selectedSiteIds[selectedSiteIds.length - 1];
      const currentIndex = orderedIds.indexOf(cursorId);
      if (currentIndex === -1) return;

      const nextIndex = event.key === "ArrowDown"
        ? Math.min(currentIndex + 1, orderedIds.length - 1)
        : Math.max(currentIndex - 1, 0);
      const nextId = orderedIds[nextIndex];
      siteNavCursorRef.current = nextId;

      if (event.shiftKey) {
        setSelectedSiteIds(() => {
          const anchor = selectionAnchorSiteId && orderedIds.includes(selectionAnchorSiteId)
            ? orderedIds.indexOf(selectionAnchorSiteId)
            : currentIndex;
          const [start, end] = anchor < nextIndex ? [anchor, nextIndex] : [nextIndex, anchor];
          return orderedIds.slice(start, end + 1);
        });
      } else {
        setSelectedSiteIds([nextId]);
        setSelectionAnchorSiteId(nextId);
      }

      const viewport = sitesTableViewportRef.current;
      if (viewport) {
        requestAnimationFrame(() => {
          const row = viewport.querySelector(`tbody tr:nth-child(${nextIndex + 1})`);
          if (row) row.scrollIntoView({ block: "nearest" });
        });
      }
    }

    window.addEventListener("keydown", handleArrowNav);
    return () => window.removeEventListener("keydown", handleArrowNav);
  }, [confirmationState, filteredSites, openSiteHeaderMenu, selectedCells, selectedSiteIds, selectionAnchorSiteId, siteModalMode]);

  // --- Sort / filter ---

  function toggleSiteSort(column) {
    setSitesSort((current) => {
      if (current.column !== column) {
        return { column, direction: "asc" };
      }
      if (current.direction === "asc") {
        return { column, direction: "desc" };
      }
      return { column: null, direction: "asc" };
    });
  }

  function clearAllSiteFilters() {
    setSitesSearch("");
    setSiteColumnFilters(initialSiteColumnFilters);
    setSitesSort({ column: null, direction: "asc" });
    setOpenSiteHeaderMenu(null);
    clearSiteSelection();
  }

  // --- Row / cell selection ---

  function handleSiteRowSelection(event, siteId) {
    event.preventDefault();
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
    const orderedIds = filteredSites.map((site) => site.id);

    if (event.shiftKey && selectionAnchorSiteId && orderedIds.includes(selectionAnchorSiteId)) {
      const anchorIndex = orderedIds.indexOf(selectionAnchorSiteId);
      const targetIndex = orderedIds.indexOf(siteId);
      const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
      const rangeIds = orderedIds.slice(start, end + 1);
      setSelectedSiteIds((current) => (event.metaKey || event.ctrlKey ? [...new Set([...current, ...rangeIds])] : rangeIds));
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      setSelectedSiteIds((current) => (
        current.includes(siteId)
          ? current.filter((candidate) => candidate !== siteId)
          : [...current, siteId]
      ));
      setSelectionAnchorSiteId(siteId);
      return;
    }

    setSelectedSiteIds([siteId]);
    setSelectionAnchorSiteId(siteId);
    siteNavCursorRef.current = siteId;
  }

  function handleCellClick(event, siteId, columnKey) {
    if (!event.altKey) return false;
    event.stopPropagation();
    event.preventDefault();

    setSelectedSiteIds([]);
    setSelectionAnchorSiteId(null);

    const cellId = `${siteId}:${columnKey}`;
    const columnKeys = siteTableColumns.map((c) => c.key);

    if (event.shiftKey && cellAnchorRef.current) {
      const anchor = cellAnchorRef.current;
      const orderedIds = filteredSites.map((s) => s.id);
      const anchorRowIdx = orderedIds.indexOf(anchor.siteId);
      const targetRowIdx = orderedIds.indexOf(siteId);
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
      cellAnchorRef.current = { siteId, columnKey };
    }
    return true;
  }

  // --- Copy ---

  function copyCellsAsTSV() {
    const columnKeys = siteTableColumns.map((c) => c.key);
    const orderedIds = filteredSites.map((s) => s.id);
    const rows = [];
    for (const sid of orderedIds) {
      const row = [];
      let hasCell = false;
      for (const col of columnKeys) {
        if (selectedCells.has(`${sid}:${col}`)) {
          const s = filteredSites.find((x) => x.id === sid);
          row.push(s ? getCellDisplayValue(s, col) : "");
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
    const columnKeys = siteTableColumns.map((c) => c.key);
    const orderedIds = filteredSites.map((s) => s.id);
    const rows = [];
    for (const sid of orderedIds) {
      if (!selectedSiteIds.includes(sid)) continue;
      const s = filteredSites.find((x) => x.id === sid);
      if (!s) continue;
      rows.push(columnKeys.map((col) => getCellDisplayValue(s, col)));
    }
    const tsv = rows.map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).catch(() => {});
  }

  // --- Context menu ---

  function handleTableContextMenu(event, site) {
    event.preventDefault();
    setContextMenu(null);

    let td = event.target;
    while (td && td.tagName !== "TD") td = td.parentElement;
    const clickedColumnKey = td?.dataset?.col || null;

    const items = [];
    const isRowSelected = selectedSiteIds.includes(site.id);
    const hasCellSelection = selectedCells.size > 0;
    const hasRowSelection = selectedSiteIds.length > 0;

    if (clickedColumnKey) {
      const cellValue = getCellDisplayValue(site, clickedColumnKey);
      const truncated = cellValue.length > 30 ? `${cellValue.slice(0, 27)}…` : cellValue;
      items.push({ label: `Copy "${truncated}"`, action: () => { navigator.clipboard.writeText(cellValue).catch(() => {}); }});
    }

    if (hasCellSelection) {
      items.push({ label: `Copy ${selectedCells.size} cell${selectedCells.size > 1 ? "s" : ""}`, action: copyCellsAsTSV });
    }

    if (hasRowSelection) {
      const count = selectedSiteIds.length;
      items.push({ label: count > 1 ? `Copy ${count} rows` : "Copy row", action: copyRowsAsTSV });
    }

    items.push({ divider: true });

    if (!isRowSelected) {
      items.push({ label: "Select row", action: () => { setSelectedSiteIds([site.id]); setSelectionAnchorSiteId(site.id); }});
      items.push({ divider: true });
    }

    const targetSites = isRowSelected ? selectedSites : [site];
    const targetCount = targetSites.length;

    items.push({ label: "View", action: () => openSiteModal("view", targetCount === 1 ? targetSites[0] : site), disabled: targetCount !== 1 });
    items.push({ label: "Edit", action: () => openSiteModal("edit", targetCount === 1 ? targetSites[0] : site), disabled: targetCount !== 1 });
    items.push({ divider: true });

    if (hasCellSelection) {
      items.push({ label: "Clear cell selection", action: () => { setSelectedCells(new Set()); setSelectedColumnKeys(new Set()); cellAnchorRef.current = null; }});
    }

    items.push({
      label: targetCount > 1 ? `Delete ${targetCount} sites` : "Delete",
      danger: true,
      action: () => handleDeleteSite(targetSites),
      disabled: !hostedWorkspaceReady
    });

    setContextMenu({ x: event.clientX, y: event.clientY, items });
  }

  // --- Column resize ---

  function getComputedColumnWidths() {
    const header = headerRef.current;
    if (!header) return null;
    const cells = header.querySelectorAll(".users-table-header-cell");
    const widths = [];
    for (let i = 1; i < cells.length; i++) {
      widths.push(cells[i].getBoundingClientRect().width);
    }
    return widths.length === siteTableColumns.length ? widths : null;
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
      const viewport = sitesTableViewportRef.current;
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

    const columnKey = siteTableColumns[colIndex]?.key;
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

    for (const site of filteredSites) {
      const value = getCellDisplayValue(site, columnKey);
      const textWidth = ctx.measureText(value).width;
      maxWidth = Math.max(maxWidth, textWidth + 24);
    }

    widths[colIndex] = Math.min(Math.ceil(maxWidth), 600);

    const viewport = sitesTableViewportRef.current;
    if (viewport) {
      const available = viewport.clientWidth - 36;
      const total = widths.reduce((a, b) => a + b, 0);
      if (total < available) {
        widths[widths.length - 1] += available - total;
      }
    }
    setColumnWidths([...widths]);
  }

  // --- Paging ---

  async function loadNextSitesPage() {
    if (sitesPagingRequestRef.current || sitesLoadingInitial || sitesLoadingMore || !sitesHasMore || sitesFiltersActive) {
      return;
    }

    sitesPagingRequestRef.current = true;

    try {
      const accessToken = await getAccessToken();
      if (accessToken) {
        await loadSites(accessToken, { append: true });
      }
    } catch (error) {
      setSitesStatus(describeFetchFailure(error, "Hosted sites failed to load."));
    } finally {
      sitesPagingRequestRef.current = false;
    }
  }

  useEffect(() => {
    if (!sitesHasMore || sitesFiltersActive || sitesLoadingInitial || sitesLoadingMore || !hostedWorkspaceReady) {
      return undefined;
    }

    const viewport = sitesTableViewportRef.current;
    if (!viewport) {
      return undefined;
    }

    function handleViewportScroll() {
      const scrollTop = viewport.scrollTop || 0;
      const scrollGate = sitesScrollGateRef.current;

      if (!scrollGate.armed) {
        if (scrollTop <= scrollGate.lastScrollTop) {
          return;
        }
        scrollGate.armed = true;
      }

      scrollGate.lastScrollTop = scrollTop;
      const viewportBottom = scrollTop + viewport.clientHeight;
      const documentHeight = viewport.scrollHeight;

      if (documentHeight - viewportBottom <= 220) {
        loadNextSitesPage();
      }
    }

    viewport.addEventListener("scroll", handleViewportScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleViewportScroll);
  }, [hostedWorkspaceReady, sitesFiltersActive, sitesHasMore, sitesLoadingInitial, sitesLoadingMore, sitesNextOffset]);

  // --- Header menu ---

  function openSiteHeaderOptions(event, columnKey) {
    const buttonRect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 296;
    const left = Math.max(16, Math.min(buttonRect.right - menuWidth, window.innerWidth - menuWidth - 16));
    const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 24);

    setOpenSiteHeaderMenu((current) => current?.key === columnKey ? null : { key: columnKey, left, top });
  }

  // --- Site CRUD ---

  function openSiteModal(mode, site = null) {
    setSiteModalMode(mode);
    setSiteSubmitError(null);

    if (site) {
      const nextForm = {
        name: site.name || "",
        url: site.url || "",
        sc_rate: String(site.sc_rate ?? "1"),
        playthrough_requirement: String(site.playthrough_requirement ?? "1"),
        notes: site.notes || "",
        is_active: Boolean(site.is_active)
      };
      setSiteForm(nextForm);
      setSiteFormBaseline(nextForm);
      setSelectedSiteIds([site.id]);
      setSelectionAnchorSiteId(site.id);
      return;
    }

    setSiteForm(initialSiteForm);
    setSiteFormBaseline(initialSiteForm);
  }

  async function submitSiteModal() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setSiteSubmitError("Google sign-in is required before managing hosted sites.");
      return;
    }

    if (!apiBaseUrl) {
      setSiteSubmitError("Set VITE_API_BASE_URL to enable hosted sites.");
      return;
    }

    const payload = {
      name: siteForm.name,
      url: siteForm.url || null,
      sc_rate: parseFloat(siteForm.sc_rate) || 1.0,
      playthrough_requirement: parseFloat(siteForm.playthrough_requirement) || 1.0,
      notes: siteForm.notes || null,
      ...(siteModalMode === "edit" ? { is_active: siteForm.is_active } : {})
    };
    const url = siteModalMode === "edit" && selectedSite
      ? `${apiBaseUrl}/v1/workspace/sites/${selectedSite.id}`
      : `${apiBaseUrl}/v1/workspace/sites`;
    const method = siteModalMode === "edit" ? "PATCH" : "POST";

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
        setSiteSubmitError(data.detail || `Hosted sites save failed (${response.status}).`);
        return;
      }

      setSites((current) => mergeSitesById(current, [data]));
      setSitesTotalCount((current) => (method === "POST" && current !== null ? current + 1 : current));
      setSelectedSiteIds([data.id]);
      setSelectionAnchorSiteId(data.id);
      setSitesStatus("Hosted sites ready.");
      closeSiteModalImmediately();
    } catch (error) {
      setSiteSubmitError(describeFetchFailure(error, "Hosted sites save failed."));
    }
  }

  async function handleSitesRefresh() {
    try {
      const accessToken = await getAccessToken();
      clearSiteSelection();
      await loadSites(accessToken, { append: false });
    } catch (error) {
      setSitesStatus(describeFetchFailure(error, "Hosted sites failed to load."));
    }
  }

  async function handleDeleteSite(sitesToDelete = selectedSites) {
    const accessToken = await getAccessToken();
    if (!sitesToDelete.length || !accessToken) {
      setSitesStatus("Google sign-in is required before managing hosted sites.");
      return;
    }
    if (!apiBaseUrl) {
      setSitesStatus("Set VITE_API_BASE_URL to enable hosted sites.");
      return;
    }
    const prompt = sitesToDelete.length === 1
      ? `Delete site '${sitesToDelete[0].name}'? This cannot be undone.`
      : `Delete ${sitesToDelete.length} sites? This cannot be undone.`;

    openConfirmation({
      title: sitesToDelete.length === 1 ? "Delete site?" : "Delete sites?",
      message: prompt,
      confirmLabel: sitesToDelete.length === 1 ? "Delete Site" : `Delete ${sitesToDelete.length} Sites`,
      cancelLabel: "Cancel",
      tone: "danger",
      onConfirm: async () => {
        setConfirmationState(null);

        try {
          setSitesStatus(`Deleting ${sitesToDelete.length} hosted ${sitesToDelete.length === 1 ? "site" : "sites"}...`);

          const response = await fetch(`${apiBaseUrl}/v1/workspace/sites/batch-delete`, {
            method: "POST",
            headers: {
              ...authHeaders(accessToken),
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              site_ids: sitesToDelete.map((site) => site.id)
            })
          });

          if (!response.ok) {
            const detail = response.headers.get("content-type")?.includes("application/json")
              ? (await response.json()).detail
              : `Hosted sites delete failed (${response.status}).`;
            setSitesStatus(detail || `Hosted sites delete failed (${response.status}).`);
            return;
          }

          const deletedIds = new Set(sitesToDelete.map((site) => site.id));
          setSites((current) => current.filter((candidate) => !deletedIds.has(candidate.id)));
          setSitesTotalCount((current) => (current === null ? null : Math.max(0, current - sitesToDelete.length)));
          clearSiteSelection();
          closeSiteModalImmediately();
          setSitesStatus("Hosted sites ready.");
        } catch (error) {
          setSitesStatus(describeFetchFailure(error, "Hosted sites delete failed."));
        }
      }
    });
  }

  // --- Render ---

  return (
    <section className="workspace-panel setup-panel users-page" aria-label="Setup Sites">
      <div className="users-surface">
        <div className="users-toolbar">
          <div className="users-toolbar-top">
            <nav className="users-breadcrumb" aria-label="Breadcrumb">
              <span className="breadcrumb-segment">Setup</span>
              <span className="breadcrumb-separator" aria-hidden="true">›</span>
              <h2 className="breadcrumb-segment current" title="Manage workspace sites, inspect individual records, and export the current filtered view.">Sites</h2>
            </nav>
            <div className="toolbar-row wrap-toolbar users-toolbar-actions">
              <button className="primary-button" type="button" onClick={() => openSiteModal("create")} disabled={!hostedWorkspaceReady}>Add Site</button>
              <button className="ghost-button" type="button" onClick={() => selectedSite && openSiteModal("view", selectedSite)} disabled={!hostedWorkspaceReady || selectedSiteIds.length !== 1}>View</button>
              <button className="ghost-button" type="button" onClick={() => selectedSite && openSiteModal("edit", selectedSite)} disabled={!hostedWorkspaceReady || selectedSiteIds.length !== 1}>Edit</button>
              <button className="ghost-button" type="button" onClick={() => handleDeleteSite()} disabled={!hostedWorkspaceReady || !selectedSiteIds.length}>Delete</button>
              <button className="ghost-button" type="button" onClick={() => setExportModalOpen(true)} disabled={!filteredSites.length}>Export CSV</button>
              <button className="ghost-button" type="button" onClick={handleSitesRefresh} disabled={!hostedWorkspaceReady}>Refresh</button>
            </div>
          </div>
          <div className="users-search-bar">
            <label className="users-search-field" htmlFor="sites-search-input">
              <span className="users-search-icon" aria-hidden="true"><Icon name="search" className="app-icon" /></span>
              <input
                id="sites-search-input"
                className="text-input hero-search-input"
                type="text"
                placeholder="Search sites..."
                value={sitesSearch}
                disabled={!hostedWorkspaceReady}
                onChange={(event) => setSitesSearch(event.target.value)}
              />
            </label>
            <div className="toolbar-row users-search-actions">
              <button className="ghost-button" type="button" onClick={() => { setSitesSearch(""); clearSiteSelection(); }}>Clear Search</button>
              <button className="ghost-button" type="button" onClick={clearAllSiteFilters}>Clear All Filters</button>
            </div>
          </div>
        </div>

        <div className="users-table-scroll-area table-viewport" ref={sitesTableViewportRef} onScroll={(e) => setShowBackToTop(e.currentTarget.scrollTop > 120)}>
          <div className="users-table-header" ref={headerRef} style={columnWidths ? { gridTemplateColumns: `36px ${columnWidths.map((w) => `${w}px`).join(" ")}`, minWidth: `${36 + columnWidths.reduce((a, b) => a + b, 0)}px` } : undefined}>
            <div className="users-table-header-cell users-checkbox-cell">
              <input
                type="checkbox"
                className="row-select-checkbox"
                aria-label="Select all rows"
                checked={filteredSites.length > 0 && selectedSiteIds.length === filteredSites.length}
                ref={(el) => { if (el) el.indeterminate = selectedSiteIds.length > 0 && selectedSiteIds.length < filteredSites.length; }}
                onChange={() => {
                  if (selectedSiteIds.length === filteredSites.length) {
                    setSelectedSiteIds([]);
                    setSelectionAnchorSiteId(null);
                    siteNavCursorRef.current = null;
                  } else {
                    setSelectedSiteIds(filteredSites.map((s) => s.id));
                    setSelectionAnchorSiteId(filteredSites[0]?.id ?? null);
                    siteNavCursorRef.current = filteredSites[filteredSites.length - 1]?.id ?? null;
                  }
                }}
                disabled={!filteredSites.length}
              />
            </div>
            {siteTableColumns.map((column, colIndex) => {
              const sortDirection = sitesSort.column === column.key ? sitesSort.direction : null;
              const filterValues = siteColumnFilters[column.key];
              return (
                <div key={column.key} className={`users-table-header-cell${selectedColumnKeys.has(column.key) ? " selected-column" : ""}`} onClick={(event) => {
                  setSelectedSiteIds([]);
                  setSelectionAnchorSiteId(null);

                  const columnKeys = siteTableColumns.map((c) => c.key);
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
                  for (const site of filteredSites) {
                    for (const col of nextCols) {
                      next.add(`${site.id}:${col}`);
                    }
                  }
                  setSelectedCells(next);
                  cellAnchorRef.current = null;
                }} onContextMenu={(event) => { event.preventDefault(); openSiteHeaderOptions(event, column.key); }}>
                  <span className="users-table-header-label">{column.label}</span>
                  <button
                    className={sortDirection || filterValues.length ? "table-sort-button active" : "table-sort-button"}
                    type="button"
                    aria-label={`${column.label} options`}
                    onClick={(event) => { event.stopPropagation(); openSiteHeaderOptions(event, column.key); }}
                  >
                    <span className="table-sort-indicator" aria-hidden="true">
                      {sortDirection === "asc"
                        ? "↑"
                        : sortDirection === "desc"
                          ? "↓"
                          : filterValues.length
                            ? filterValues.length
                            : <Icon name="filterMenu" className="app-icon table-filter-icon" />}
                    </span>
                  </button>

                  {openSiteHeaderMenu?.key === column.key ? (
                    <UserHeaderFilterMenu
                        column={column}
                        options={siteFilterOptions[column.key]}
                        selectedValues={filterValues}
                        sortDirection={sortDirection}
                        onClearFilter={() => {
                          setSiteColumnFilters((current) => ({ ...current, [column.key]: [] }));
                          setOpenSiteHeaderMenu(null);
                        }}
                        onSortAsc={() => {
                          setSitesSort({ column: column.key, direction: "asc" });
                          setOpenSiteHeaderMenu(null);
                        }}
                        onSortDesc={() => {
                          setSitesSort({ column: column.key, direction: "desc" });
                          setOpenSiteHeaderMenu(null);
                        }}
                        onClearSort={() => {
                          setSitesSort({ column: null, direction: "asc" });
                          setOpenSiteHeaderMenu(null);
                        }}
                        onApplyFilter={(values) => {
                          setSiteColumnFilters((current) => ({ ...current, [column.key]: values }));
                        }}
                      onClose={() => setOpenSiteHeaderMenu(null)}
                      style={openSiteHeaderMenu}
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
                    <col style={{ width: "18%" }} />
                    <col style={{ width: "22%" }} />
                    <col style={{ width: "10%" }} />
                    <col style={{ width: "12%" }} />
                    <col style={{ width: "10%" }} />
                    <col />
                  </>
              }
            </colgroup>
            <tbody>
              {filteredSites.length ? filteredSites.map((site) => (
                <tr
                  key={site.id}
                  className={selectedSiteIds.includes(site.id) ? "selected-row" : undefined}
                  aria-selected={selectedSiteIds.includes(site.id)}
                  onMouseDown={(event) => {
                    if (event.shiftKey || event.metaKey || event.ctrlKey) {
                      event.preventDefault();
                    }
                  }}
                  onClick={(event) => handleSiteRowSelection(event, site.id)}
                  onDoubleClick={() => openSiteModal("view", site)}
                  onContextMenu={(event) => handleTableContextMenu(event, site)}
                >
                  <td className="row-checkbox-cell" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="row-select-checkbox"
                      aria-label={`Select ${site.name}`}
                      checked={selectedSiteIds.includes(site.id)}
                      onChange={() => {
                        setSelectedSiteIds((current) =>
                          current.includes(site.id)
                            ? current.filter((id) => id !== site.id)
                            : [...current, site.id]
                        );
                        setSelectionAnchorSiteId(site.id);
                      }}
                    />
                  </td>
                  <td data-col="name" className={selectedCells.has(`${site.id}:name`) ? "selected-cell" : selectedColumnKeys.has("name") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, site.id, "name")) return; }}><HighlightMatch text={site.name} query={sitesSearch} /></td>
                  <td data-col="url" className={selectedCells.has(`${site.id}:url`) ? "selected-cell" : selectedColumnKeys.has("url") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, site.id, "url")) return; }}><HighlightMatch text={site.url || ""} query={sitesSearch} /></td>
                  <td data-col="sc_rate" className={selectedCells.has(`${site.id}:sc_rate`) ? "selected-cell" : selectedColumnKeys.has("sc_rate") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, site.id, "sc_rate")) return; }}>{site.sc_rate}</td>
                  <td data-col="playthrough_requirement" className={selectedCells.has(`${site.id}:playthrough_requirement`) ? "selected-cell" : selectedColumnKeys.has("playthrough_requirement") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, site.id, "playthrough_requirement")) return; }}>{site.playthrough_requirement}</td>
                  <td data-col="status" className={selectedCells.has(`${site.id}:status`) ? "selected-cell" : selectedColumnKeys.has("status") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, site.id, "status")) return; }}>
                    <span className={site.is_active ? "status-chip active" : "status-chip inactive"}>
                      {site.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td data-col="notes" className={`notes-cell${selectedCells.has(`${site.id}:notes`) ? " selected-cell" : selectedColumnKeys.has("notes") ? " selected-column-cell" : ""}`} onClick={(event) => { if (handleCellClick(event, site.id, "notes")) return; }} title={(site.notes || "").length > 100 ? site.notes : undefined}><HighlightMatch text={(site.notes || "").slice(0, 100) || "-"} query={sitesSearch} /></td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={siteTableColumns.length + 1} className="empty-state-cell">
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
                        ? (sitesSearch
                          ? <>No results for &ldquo;{sitesSearch}&rdquo;. <button className="inline-link-button" type="button" onClick={() => { setSitesSearch(""); clearSiteSelection(); }}>Clear search</button></>
                          : "No sites match the current view.")
                        : "Connect the hosted workspace to load sites."
                      }</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="users-summary-rail users-summary-rail-bottom" aria-label="Site summary">
          <div className="users-page-metrics">
            <span className="users-metric-chip">{filteredSiteCount} shown</span>
            <span className="users-metric-chip subdued">{totalSiteCount} total</span>
            {selectedSiteIds.length ? <span className="users-metric-chip accent">{selectedSiteIds.length} selected</span> : null}
            {sitesFiltersActive ? <span className="users-metric-chip subdued">Filtered view</span> : null}
            {selectedCells.size ? (() => {
              const cellValues = [];
              for (const cellId of selectedCells) {
                const [siteId, colKey] = cellId.split(":");
                const site = filteredSites.find((s) => s.id === siteId);
                if (site) cellValues.push(getCellDisplayValue(site, colKey));
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
            {sitesHasMore && !sitesFiltersActive ? (
              <button className="ghost-button" type="button" onClick={loadNextSitesPage} disabled={sitesLoadingMore}>
                {sitesLoadingMore ? "Loading..." : "Load More Sites"}
              </button>
            ) : null}
          </div>
        </div>

        <button
          className={`back-to-top-button${showBackToTop ? " visible" : ""}`}
          type="button"
          aria-label="Back to top"
          onClick={() => {
            const viewport = sitesTableViewportRef.current;
            if (viewport) viewport.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          ↑
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
          filteredUsers={filteredSites}
          selectedUsers={selectedSites}
          selectedCells={selectedCells}
          allColumns={siteTableColumns}
          onExport={(data, columns) => downloadSitesCsv(data, columns)}
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

      {siteModalMode ? (
        <SiteModal
          mode={siteModalMode}
          site={selectedSite}
          form={siteForm}
          setForm={setSiteForm}
          submitError={siteSubmitError}
          suggestions={siteSuggestions}
          onClose={requestCloseSiteModal}
          onRequestEdit={() => selectedSite && openSiteModal("edit", selectedSite)}
          onRequestDelete={() => selectedSite && handleDeleteSite([selectedSite])}
          onSubmit={submitSiteModal}
        />
      ) : null}
    </section>
  );
}
