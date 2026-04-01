import { useEffect, useMemo, useRef, useState } from "react";

import { authHeaders, describeFetchFailure, getAccessToken } from "../../services/api";
import Icon from "../common/Icon";
import HighlightMatch from "../common/HighlightMatch";
import ConfirmationModal from "../common/ConfirmationModal";
import CardModal from "./CardModal";
import ExportModal from "../UsersTab/ExportModal";
import UserHeaderFilterMenu from "../UsersTab/UserHeaderFilterMenu";
import TableContextMenu from "../UsersTab/TableContextMenu";
import {
  initialCardForm,
  initialCardColumnFilters,
  cardTableColumns,
  cardsPageSize,
  cardsFallbackPageSize
} from "./cardsConstants";
import {
  normalizeCardForm,
  isTextEntryElement,
  computeCellStats,
  getCellDisplayValue,
  downloadCardsCsv,
  getCardColumnValue,
  buildCardFilterOptions,
  mergeCardsById
} from "./cardsUtils";

export default function CardsTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const cardsScrollGateRef = useRef({ armed: false, lastScrollTop: 0 });
  const cardsPagingRequestRef = useRef(false);
  const cardsTableViewportRef = useRef(null);
  const cardNavCursorRef = useRef(null);
  const [cards, setCards] = useState([]);
  const [cardsStatus, setCardsStatus] = useState("Sign in to load hosted cards.");
  const [cardsSearch, setCardsSearch] = useState("");
  const [cardColumnFilters, setCardColumnFilters] = useState(initialCardColumnFilters);
  const [cardsSort, setCardsSort] = useState({ column: null, direction: "asc" });
  const [openCardHeaderMenu, setOpenCardHeaderMenu] = useState(null);
  const [selectedCardIds, setSelectedCardIds] = useState([]);
  const [selectionAnchorCardId, setSelectionAnchorCardId] = useState(null);
  const [selectedColumnKeys, setSelectedColumnKeys] = useState(new Set());
  const [selectedCells, setSelectedCells] = useState(new Set());
  const cellAnchorRef = useRef(null);
  const [cardsTotalCount, setCardsTotalCount] = useState(null);
  const [cardsNextOffset, setCardsNextOffset] = useState(0);
  const [cardsHasMore, setCardsHasMore] = useState(false);
  const [cardsLoadingInitial, setCardsLoadingInitial] = useState(false);
  const [cardsLoadingMore, setCardsLoadingMore] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const [columnWidths, setColumnWidths] = useState(null);
  const columnResizeRef = useRef(null);
  const headerRef = useRef(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [cardModalMode, setCardModalMode] = useState(null);
  const [cardForm, setCardForm] = useState(initialCardForm);
  const [cardFormBaseline, setCardFormBaseline] = useState(initialCardForm);
  const [cardSubmitError, setCardSubmitError] = useState(null);
  const [confirmationState, setConfirmationState] = useState(null);
  const [users, setUsers] = useState([]);

  const filteredCards = useMemo(() => {
    const searchText = cardsSearch.trim().toLowerCase();
    const searchFiltered = !searchText
      ? cards
      : cards.filter((card) =>
          card.name.toLowerCase().includes(searchText)
          || (card.user_name || "").toLowerCase().includes(searchText)
          || (card.last_four || "").toLowerCase().includes(searchText)
          || (card.notes || "").toLowerCase().includes(searchText)
        );

    const columnFiltered = searchFiltered.filter((card) => {
      for (const col of cardTableColumns) {
        const filterValues = cardColumnFilters[col.key];
        if (filterValues && filterValues.length && !filterValues.includes(getCardColumnValue(card, col.key))) {
          return false;
        }
      }
      return true;
    });

    if (!cardsSort.column) {
      return columnFiltered;
    }

    const sortedCards = [...columnFiltered].sort((left, right) => {
      const leftValue = getCardColumnValue(left, cardsSort.column);
      const rightValue = getCardColumnValue(right, cardsSort.column);

      if (cardsSort.column === "cashback_rate") {
        const leftNum = parseFloat(leftValue) || 0;
        const rightNum = parseFloat(rightValue) || 0;
        return leftNum - rightNum;
      }

      return leftValue.localeCompare(rightValue, undefined, { sensitivity: "base" });
    });

    return cardsSort.direction === "desc" ? sortedCards.reverse() : sortedCards;
  }, [cardColumnFilters, cards, cardsSearch, cardsSort]);

  const cardFilterOptions = useMemo(() => {
    const options = {};
    for (const col of cardTableColumns) {
      if (col.key === "status") {
        options[col.key] = [
          { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
          { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
        ];
      } else {
        options[col.key] = buildCardFilterOptions(cards, col.key);
      }
    }
    return options;
  }, [cards]);

  const filteredCardCount = filteredCards.length;
  const totalCardCount = cardsTotalCount ?? cards.length;

  const selectedCards = cards.filter((card) => selectedCardIds.includes(card.id));
  const selectedCard = selectedCards.length === 1 ? selectedCards[0] : null;
  const cardModalDirty = cardModalMode && cardModalMode !== "view"
    ? JSON.stringify(normalizeCardForm(cardForm)) !== JSON.stringify(normalizeCardForm(cardFormBaseline))
    : false;

  const cardsFiltersActive = Boolean(
    cardsSearch
    || Object.values(cardColumnFilters).some((values) => values.length)
    || cardsSort.column
  );

  const cardSuggestions = useMemo(() => ({
    names: [...new Set(cards.map((card) => card.name).filter(Boolean))]
  }), [cards]);

  function clearCardSelection() {
    setSelectedCardIds([]);
    setSelectionAnchorCardId(null);
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
  }

  function closeCardModalImmediately() {
    setCardModalMode(null);
    setCardSubmitError(null);
    setCardForm(initialCardForm);
    setCardFormBaseline(initialCardForm);
  }

  function openConfirmation(options) {
    setConfirmationState(options);
  }

  function requestCloseCardModal() {
    if (!cardModalDirty) {
      closeCardModalImmediately();
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
        closeCardModalImmediately();
      }
    });
  }

  // --- Data loading ---

  async function loadUsers(accessToken) {
    if (!accessToken || !apiBaseUrl) return;
    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/users?limit=500&offset=0`, {
        headers: authHeaders(accessToken)
      });
      if (response.ok) {
        const payload = await response.json();
        setUsers(Array.isArray(payload.users) ? payload.users : []);
      }
    } catch {
      // Users list is supplementary; silent failure is acceptable
    }
  }

  async function loadCards(accessToken, { append = false } = {}) {
    if (!accessToken) {
      setCards([]);
      setCardsTotalCount(null);
      setCardsNextOffset(0);
      setCardsHasMore(false);
      clearCardSelection();
      setCardsStatus("Sign in to load hosted cards.");
      return;
    }

    if (!apiBaseUrl) {
      setCards([]);
      setCardsTotalCount(null);
      setCardsNextOffset(0);
      setCardsHasMore(false);
      clearCardSelection();
      setCardsStatus("Set VITE_API_BASE_URL to enable hosted cards.");
      return;
    }

    const requestOffset = append ? cardsNextOffset : 0;
    if (append) {
      setCardsLoadingMore(true);
    } else {
      setCardsLoadingInitial(true);
      setCardsStatus("Loading hosted cards...");
    }

    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/cards?limit=${cardsPageSize}&offset=${requestOffset}`, {
        headers: authHeaders(accessToken)
      });
      const payload = await response.json();

      if (!response.ok) {
        setCards([]);
        setCardsTotalCount(null);
        setCardsNextOffset(0);
        setCardsHasMore(false);
        clearCardSelection();
        setCardsStatus(payload.detail || `Hosted cards failed to load (${response.status}).`);
        return;
      }

      const payloadCards = Array.isArray(payload.cards) ? payload.cards : [];
      let loadedCards = payloadCards.slice(0, cardsPageSize);
      let mergedCards = append ? mergeCardsById(cards, loadedCards) : loadedCards;
      let reportedTotalCount = Number.isFinite(payload.total_count) ? payload.total_count : null;
      let nextOffset = requestOffset + loadedCards.length;
      let inferredHasMore = loadedCards.length === cardsPageSize;
      let hasMore = Boolean(payload.has_more) || nextOffset < (reportedTotalCount ?? 0) || inferredHasMore;

      if (append && loadedCards.length && mergedCards.length === cards.length) {
        const fallbackResponse = await fetch(`${apiBaseUrl}/v1/workspace/cards?limit=${cardsFallbackPageSize}&offset=0`, {
          headers: authHeaders(accessToken)
        });
        const fallbackPayload = await fallbackResponse.json();

        if (fallbackResponse.ok) {
          const fallbackCards = Array.isArray(fallbackPayload.cards)
            ? fallbackPayload.cards.slice(0, cardsFallbackPageSize)
            : [];
          const fallbackMergedCards = mergeCardsById(cards, fallbackCards);

          if (fallbackMergedCards.length > cards.length) {
            loadedCards = fallbackCards;
            mergedCards = fallbackMergedCards;
            reportedTotalCount = Number.isFinite(fallbackPayload.total_count)
              ? fallbackPayload.total_count
              : reportedTotalCount;
            nextOffset = mergedCards.length;
            inferredHasMore = fallbackCards.length === cardsFallbackPageSize;
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

      const totalCount = Math.max(reportedTotalCount ?? 0, mergedCards.length);

      if (!append) {
        cardsScrollGateRef.current = {
          armed: false,
          lastScrollTop: cardsTableViewportRef.current?.scrollTop || 0,
        };
      }

      setCards(mergedCards);
      setCardsTotalCount(totalCount);
      setCardsNextOffset(nextOffset);
      setCardsHasMore(hasMore);
      setSelectedCardIds((current) => current.filter((cardId) => mergedCards.some((card) => card.id === cardId)));

      if (!mergedCards.length) {
        setCardsStatus("No hosted cards yet. Add your first card to get started.");
      } else if (hasMore) {
        setCardsStatus(`Loaded ${mergedCards.length} of ${totalCount} hosted cards.`);
      } else {
        setCardsStatus("Hosted cards ready.");
      }
    } catch (error) {
      setCards([]);
      setCardsTotalCount(null);
      setCardsNextOffset(0);
      setCardsHasMore(false);
      clearCardSelection();
      setCardsStatus(describeFetchFailure(error, "Hosted cards failed to load."));
    } finally {
      setCardsLoadingInitial(false);
      setCardsLoadingMore(false);
    }
  }

  // --- Load cards when workspace becomes ready ---

  useEffect(() => {
    if (!hostedWorkspaceReady || !apiBaseUrl) {
      return;
    }

    (async () => {
      try {
        const accessToken = await getAccessToken();
        if (accessToken) {
          await Promise.all([loadCards(accessToken), loadUsers(accessToken)]);
        }
      } catch (error) {
        setCardsStatus(describeFetchFailure(error, "Hosted cards failed to load."));
      }
    })();
  }, [hostedWorkspaceReady]);

  // --- Header menu close on outside click ---

  useEffect(() => {
    if (!openCardHeaderMenu) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (event.target instanceof Element && event.target.closest(".table-header-menu-wrap, .table-header-menu")) {
        return;
      }
      setOpenCardHeaderMenu(null);
    }

    function handleViewportChange() {
      setOpenCardHeaderMenu(null);
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("resize", handleViewportChange);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("resize", handleViewportChange);
    };
  }, [openCardHeaderMenu]);

  // --- Escape key handler ---

  useEffect(() => {
    const anyModalOpen = Boolean(
      openCardHeaderMenu
      || cardModalMode
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

      if (openCardHeaderMenu) {
        if (blurActiveTextFieldWithin(".table-header-menu")) {
          return;
        }
        setOpenCardHeaderMenu(null);
        return;
      }

      if (cardModalMode) {
        if (blurActiveTextFieldWithin(".modal-card")) {
          return;
        }
        requestCloseCardModal();
        return;
      }

      if (exportModalOpen) {
        setExportModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmationState, exportModalOpen, openCardHeaderMenu, cardModalMode, cardModalDirty]);

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
        if (selectedCardIds.length) {
          event.preventDefault();
          copyRowsAsTSV();
          return;
        }
        return;
      }

      if (event.key === "a" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (confirmationState || cardModalMode || openCardHeaderMenu) return;
        if (!filteredCards.length) return;
        event.preventDefault();
        if (selectedCardIds.length === filteredCards.length && filteredCards.every((c) => selectedCardIds.includes(c.id))) {
          setSelectedCardIds([]);
          setSelectionAnchorCardId(null);
          cardNavCursorRef.current = null;
        } else {
          setSelectedCardIds(filteredCards.map((c) => c.id));
          setSelectionAnchorCardId(filteredCards[0].id);
          cardNavCursorRef.current = filteredCards[filteredCards.length - 1].id;
        }
        return;
      }

      if (event.key === "f" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (confirmationState || cardModalMode || openCardHeaderMenu) return;
        event.preventDefault();
        const searchInput = document.getElementById("cards-search-input");
        if (searchInput) { searchInput.focus(); searchInput.select(); }
        return;
      }

      if (event.key === "Escape") {
        const searchInput = document.getElementById("cards-search-input");
        if (document.activeElement === searchInput) {
          event.preventDefault();
          if (cardsSearch) {
            setCardsSearch("");
          } else {
            searchInput.blur();
          }
          return;
        }
      }

      if (event.key !== "ArrowUp" && event.key !== "ArrowDown" && event.key !== "Enter") return;
      if (isTextEntryElement(document.activeElement)) return;
      if (confirmationState || cardModalMode || openCardHeaderMenu) return;

      if (event.key === "Enter") {
        if (selectedCardIds.length === 1) {
          const card = filteredCards.find((c) => c.id === selectedCardIds[0]);
          if (card) openCardModal("view", card);
        }
        return;
      }

      if (!filteredCards.length || !selectedCardIds.length) return;

      event.preventDefault();
      const orderedIds = filteredCards.map((c) => c.id);
      const cursorId = cardNavCursorRef.current ?? selectedCardIds[selectedCardIds.length - 1];
      const currentIndex = orderedIds.indexOf(cursorId);
      if (currentIndex === -1) return;

      const nextIndex = event.key === "ArrowDown"
        ? Math.min(currentIndex + 1, orderedIds.length - 1)
        : Math.max(currentIndex - 1, 0);
      const nextId = orderedIds[nextIndex];
      cardNavCursorRef.current = nextId;

      if (event.shiftKey) {
        setSelectedCardIds(() => {
          const anchor = selectionAnchorCardId && orderedIds.includes(selectionAnchorCardId)
            ? orderedIds.indexOf(selectionAnchorCardId)
            : currentIndex;
          const [start, end] = anchor < nextIndex ? [anchor, nextIndex] : [nextIndex, anchor];
          return orderedIds.slice(start, end + 1);
        });
      } else {
        setSelectedCardIds([nextId]);
        setSelectionAnchorCardId(nextId);
      }

      const viewport = cardsTableViewportRef.current;
      if (viewport) {
        requestAnimationFrame(() => {
          const row = viewport.querySelector(`tbody tr:nth-child(${nextIndex + 1})`);
          if (row) row.scrollIntoView({ block: "nearest" });
        });
      }
    }

    window.addEventListener("keydown", handleArrowNav);
    return () => window.removeEventListener("keydown", handleArrowNav);
  }, [confirmationState, filteredCards, openCardHeaderMenu, selectedCells, selectedCardIds, selectionAnchorCardId, cardModalMode]);

  // --- Sort / filter ---

  function toggleCardSort(column) {
    setCardsSort((current) => {
      if (current.column !== column) {
        return { column, direction: "asc" };
      }
      if (current.direction === "asc") {
        return { column, direction: "desc" };
      }
      return { column: null, direction: "asc" };
    });
  }

  function clearAllCardFilters() {
    setCardsSearch("");
    setCardColumnFilters(initialCardColumnFilters);
    setCardsSort({ column: null, direction: "asc" });
    setOpenCardHeaderMenu(null);
    clearCardSelection();
  }

  // --- Row / cell selection ---

  function handleCardRowSelection(event, cardId) {
    event.preventDefault();
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
    const orderedIds = filteredCards.map((card) => card.id);

    if (event.shiftKey && selectionAnchorCardId && orderedIds.includes(selectionAnchorCardId)) {
      const anchorIndex = orderedIds.indexOf(selectionAnchorCardId);
      const targetIndex = orderedIds.indexOf(cardId);
      const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
      const rangeIds = orderedIds.slice(start, end + 1);
      setSelectedCardIds((current) => (event.metaKey || event.ctrlKey ? [...new Set([...current, ...rangeIds])] : rangeIds));
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      setSelectedCardIds((current) => (
        current.includes(cardId)
          ? current.filter((candidate) => candidate !== cardId)
          : [...current, cardId]
      ));
      setSelectionAnchorCardId(cardId);
      return;
    }

    setSelectedCardIds([cardId]);
    setSelectionAnchorCardId(cardId);
    cardNavCursorRef.current = cardId;
  }

  function handleCellClick(event, cardId, columnKey) {
    if (!event.altKey) return false;
    event.stopPropagation();
    event.preventDefault();

    setSelectedCardIds([]);
    setSelectionAnchorCardId(null);

    const cellId = `${cardId}:${columnKey}`;
    const columnKeys = cardTableColumns.map((c) => c.key);

    if (event.shiftKey && cellAnchorRef.current) {
      const anchor = cellAnchorRef.current;
      const orderedIds = filteredCards.map((c) => c.id);
      const anchorRowIdx = orderedIds.indexOf(anchor.cardId);
      const targetRowIdx = orderedIds.indexOf(cardId);
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
      cellAnchorRef.current = { cardId, columnKey };
    }
    return true;
  }

  // --- Copy ---

  function copyCellsAsTSV() {
    const columnKeys = cardTableColumns.map((c) => c.key);
    const orderedIds = filteredCards.map((c) => c.id);
    const rows = [];
    for (const cid of orderedIds) {
      const row = [];
      let hasCell = false;
      for (const col of columnKeys) {
        if (selectedCells.has(`${cid}:${col}`)) {
          const c = filteredCards.find((x) => x.id === cid);
          row.push(c ? getCellDisplayValue(c, col) : "");
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
    const columnKeys = cardTableColumns.map((c) => c.key);
    const orderedIds = filteredCards.map((c) => c.id);
    const rows = [];
    for (const cid of orderedIds) {
      if (!selectedCardIds.includes(cid)) continue;
      const c = filteredCards.find((x) => x.id === cid);
      if (!c) continue;
      rows.push(columnKeys.map((col) => getCellDisplayValue(c, col)));
    }
    const tsv = rows.map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).catch(() => {});
  }

  // --- Context menu ---

  function handleTableContextMenu(event, card) {
    event.preventDefault();
    setContextMenu(null);

    let td = event.target;
    while (td && td.tagName !== "TD") td = td.parentElement;
    const clickedColumnKey = td?.dataset?.col || null;

    const items = [];
    const isRowSelected = selectedCardIds.includes(card.id);
    const hasCellSelection = selectedCells.size > 0;
    const hasRowSelection = selectedCardIds.length > 0;

    if (clickedColumnKey) {
      const cellValue = getCellDisplayValue(card, clickedColumnKey);
      const truncated = cellValue.length > 30 ? `${cellValue.slice(0, 27)}\u2026` : cellValue;
      items.push({ label: `Copy "${truncated}"`, action: () => { navigator.clipboard.writeText(cellValue).catch(() => {}); }});
    }

    if (hasCellSelection) {
      items.push({ label: `Copy ${selectedCells.size} cell${selectedCells.size > 1 ? "s" : ""}`, action: copyCellsAsTSV });
    }

    if (hasRowSelection) {
      const count = selectedCardIds.length;
      items.push({ label: count > 1 ? `Copy ${count} rows` : "Copy row", action: copyRowsAsTSV });
    }

    items.push({ divider: true });

    if (!isRowSelected) {
      items.push({ label: "Select row", action: () => { setSelectedCardIds([card.id]); setSelectionAnchorCardId(card.id); }});
      items.push({ divider: true });
    }

    const targetCards = isRowSelected ? selectedCards : [card];
    const targetCount = targetCards.length;

    items.push({ label: "View", action: () => openCardModal("view", targetCount === 1 ? targetCards[0] : card), disabled: targetCount !== 1 });
    items.push({ label: "Edit", action: () => openCardModal("edit", targetCount === 1 ? targetCards[0] : card), disabled: targetCount !== 1 });
    items.push({ divider: true });

    if (hasCellSelection) {
      items.push({ label: "Clear cell selection", action: () => { setSelectedCells(new Set()); setSelectedColumnKeys(new Set()); cellAnchorRef.current = null; }});
    }

    items.push({
      label: targetCount > 1 ? `Delete ${targetCount} cards` : "Delete",
      danger: true,
      action: () => handleDeleteCard(targetCards),
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
    return widths.length === cardTableColumns.length ? widths : null;
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
      const viewport = cardsTableViewportRef.current;
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

    const columnKey = cardTableColumns[colIndex]?.key;
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

    for (const card of filteredCards) {
      const value = getCellDisplayValue(card, columnKey);
      const textWidth = ctx.measureText(value).width;
      maxWidth = Math.max(maxWidth, textWidth + 24);
    }

    widths[colIndex] = Math.min(Math.ceil(maxWidth), 600);

    const viewport = cardsTableViewportRef.current;
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

  async function loadNextCardsPage() {
    if (cardsPagingRequestRef.current || cardsLoadingInitial || cardsLoadingMore || !cardsHasMore || cardsFiltersActive) {
      return;
    }

    cardsPagingRequestRef.current = true;

    try {
      const accessToken = await getAccessToken();
      if (accessToken) {
        await loadCards(accessToken, { append: true });
      }
    } catch (error) {
      setCardsStatus(describeFetchFailure(error, "Hosted cards failed to load."));
    } finally {
      cardsPagingRequestRef.current = false;
    }
  }

  useEffect(() => {
    if (!cardsHasMore || cardsFiltersActive || cardsLoadingInitial || cardsLoadingMore || !hostedWorkspaceReady) {
      return undefined;
    }

    const viewport = cardsTableViewportRef.current;
    if (!viewport) {
      return undefined;
    }

    function handleViewportScroll() {
      const scrollTop = viewport.scrollTop || 0;
      const scrollGate = cardsScrollGateRef.current;

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
        loadNextCardsPage();
      }
    }

    viewport.addEventListener("scroll", handleViewportScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleViewportScroll);
  }, [hostedWorkspaceReady, cardsFiltersActive, cardsHasMore, cardsLoadingInitial, cardsLoadingMore, cardsNextOffset]);

  // --- Header menu ---

  function openCardHeaderOptions(event, columnKey) {
    const buttonRect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 296;
    const left = Math.max(16, Math.min(buttonRect.right - menuWidth, window.innerWidth - menuWidth - 16));
    const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 24);

    setOpenCardHeaderMenu((current) => current?.key === columnKey ? null : { key: columnKey, left, top });
  }

  // --- Card CRUD ---

  function openCardModal(mode, card = null) {
    setCardModalMode(mode);
    setCardSubmitError(null);

    if (card) {
      const nextForm = {
        name: card.name || "",
        user_id: card.user_id || "",
        last_four: card.last_four || "",
        cashback_rate: String(card.cashback_rate ?? "0"),
        notes: card.notes || "",
        is_active: Boolean(card.is_active)
      };
      setCardForm(nextForm);
      setCardFormBaseline(nextForm);
      setSelectedCardIds([card.id]);
      setSelectionAnchorCardId(card.id);
      return;
    }

    setCardForm(initialCardForm);
    setCardFormBaseline(initialCardForm);
  }

  async function submitCardModal() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setCardSubmitError("Google sign-in is required before managing hosted cards.");
      return;
    }

    if (!apiBaseUrl) {
      setCardSubmitError("Set VITE_API_BASE_URL to enable hosted cards.");
      return;
    }

    const payload = {
      name: cardForm.name,
      user_id: cardForm.user_id,
      last_four: cardForm.last_four || null,
      cashback_rate: parseFloat(cardForm.cashback_rate) || 0.0,
      notes: cardForm.notes || null,
      ...(cardModalMode === "edit" ? { is_active: cardForm.is_active } : {})
    };
    const url = cardModalMode === "edit" && selectedCard
      ? `${apiBaseUrl}/v1/workspace/cards/${selectedCard.id}`
      : `${apiBaseUrl}/v1/workspace/cards`;
    const method = cardModalMode === "edit" ? "PATCH" : "POST";

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
        setCardSubmitError(data.detail || `Hosted cards save failed (${response.status}).`);
        return;
      }

      setCards((current) => mergeCardsById(current, [data]));
      setCardsTotalCount((current) => (method === "POST" && current !== null ? current + 1 : current));
      setSelectedCardIds([data.id]);
      setSelectionAnchorCardId(data.id);
      setCardsStatus("Hosted cards ready.");
      closeCardModalImmediately();
    } catch (error) {
      setCardSubmitError(describeFetchFailure(error, "Hosted cards save failed."));
    }
  }

  async function handleCardsRefresh() {
    try {
      const accessToken = await getAccessToken();
      clearCardSelection();
      await Promise.all([loadCards(accessToken, { append: false }), loadUsers(accessToken)]);
    } catch (error) {
      setCardsStatus(describeFetchFailure(error, "Hosted cards failed to load."));
    }
  }

  async function handleDeleteCard(cardsToDelete = selectedCards) {
    const accessToken = await getAccessToken();
    if (!cardsToDelete.length || !accessToken) {
      setCardsStatus("Google sign-in is required before managing hosted cards.");
      return;
    }
    if (!apiBaseUrl) {
      setCardsStatus("Set VITE_API_BASE_URL to enable hosted cards.");
      return;
    }
    const prompt = cardsToDelete.length === 1
      ? `Delete card '${cardsToDelete[0].name}'? This cannot be undone.`
      : `Delete ${cardsToDelete.length} cards? This cannot be undone.`;

    openConfirmation({
      title: cardsToDelete.length === 1 ? "Delete card?" : "Delete cards?",
      message: prompt,
      confirmLabel: cardsToDelete.length === 1 ? "Delete Card" : `Delete ${cardsToDelete.length} Cards`,
      cancelLabel: "Cancel",
      tone: "danger",
      onConfirm: async () => {
        setConfirmationState(null);

        try {
          setCardsStatus(`Deleting ${cardsToDelete.length} hosted ${cardsToDelete.length === 1 ? "card" : "cards"}...`);

          const response = await fetch(`${apiBaseUrl}/v1/workspace/cards/batch-delete`, {
            method: "POST",
            headers: {
              ...authHeaders(accessToken),
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              card_ids: cardsToDelete.map((card) => card.id)
            })
          });

          if (!response.ok) {
            const detail = response.headers.get("content-type")?.includes("application/json")
              ? (await response.json()).detail
              : `Hosted cards delete failed (${response.status}).`;
            setCardsStatus(detail || `Hosted cards delete failed (${response.status}).`);
            return;
          }

          const deletedIds = new Set(cardsToDelete.map((card) => card.id));
          setCards((current) => current.filter((candidate) => !deletedIds.has(candidate.id)));
          setCardsTotalCount((current) => (current === null ? null : Math.max(0, current - cardsToDelete.length)));
          clearCardSelection();
          closeCardModalImmediately();
          setCardsStatus("Hosted cards ready.");
        } catch (error) {
          setCardsStatus(describeFetchFailure(error, "Hosted cards delete failed."));
        }
      }
    });
  }

  // --- Render ---

  return (
    <section className="workspace-panel setup-panel users-page" aria-label="Setup Cards">
      <div className="users-surface">
        <div className="users-toolbar">
          <div className="users-toolbar-top">
            <nav className="users-breadcrumb" aria-label="Breadcrumb">
              <span className="breadcrumb-segment">Setup</span>
              <span className="breadcrumb-separator" aria-hidden="true">&rsaquo;</span>
              <h2 className="breadcrumb-segment current" title="Manage workspace cards, inspect individual records, and export the current filtered view.">Cards</h2>
            </nav>
            <div className="toolbar-row wrap-toolbar users-toolbar-actions">
              <button className="primary-button" type="button" onClick={() => openCardModal("create")} disabled={!hostedWorkspaceReady}>Add Card</button>
              <button className="ghost-button" type="button" onClick={() => selectedCard && openCardModal("view", selectedCard)} disabled={!hostedWorkspaceReady || selectedCardIds.length !== 1}>View</button>
              <button className="ghost-button" type="button" onClick={() => selectedCard && openCardModal("edit", selectedCard)} disabled={!hostedWorkspaceReady || selectedCardIds.length !== 1}>Edit</button>
              <button className="ghost-button" type="button" onClick={() => handleDeleteCard()} disabled={!hostedWorkspaceReady || !selectedCardIds.length}>Delete</button>
              <button className="ghost-button" type="button" onClick={() => setExportModalOpen(true)} disabled={!filteredCards.length}>Export CSV</button>
              <button className="ghost-button" type="button" onClick={handleCardsRefresh} disabled={!hostedWorkspaceReady}>Refresh</button>
            </div>
          </div>
          <div className="users-search-bar">
            <label className="users-search-field" htmlFor="cards-search-input">
              <span className="users-search-icon" aria-hidden="true"><Icon name="search" className="app-icon" /></span>
              <input
                id="cards-search-input"
                className="text-input hero-search-input"
                type="text"
                placeholder="Search cards..."
                value={cardsSearch}
                disabled={!hostedWorkspaceReady}
                onChange={(event) => setCardsSearch(event.target.value)}
              />
            </label>
            <div className="toolbar-row users-search-actions">
              <button className="ghost-button" type="button" onClick={() => { setCardsSearch(""); clearCardSelection(); }}>Clear Search</button>
              <button className="ghost-button" type="button" onClick={clearAllCardFilters}>Clear All Filters</button>
            </div>
          </div>
        </div>

        <div className="users-table-scroll-area table-viewport" ref={cardsTableViewportRef} onScroll={(e) => setShowBackToTop(e.currentTarget.scrollTop > 120)}>
          <div className="users-table-header" ref={headerRef} style={columnWidths ? { gridTemplateColumns: `36px ${columnWidths.map((w) => `${w}px`).join(" ")}`, minWidth: `${36 + columnWidths.reduce((a, b) => a + b, 0)}px` } : { gridTemplateColumns: "36px 20% 16% 10% 12% 10% 1fr" }}>
            <div className="users-table-header-cell users-checkbox-cell">
              <input
                type="checkbox"
                className="row-select-checkbox"
                aria-label="Select all rows"
                checked={filteredCards.length > 0 && selectedCardIds.length === filteredCards.length}
                ref={(el) => { if (el) el.indeterminate = selectedCardIds.length > 0 && selectedCardIds.length < filteredCards.length; }}
                onChange={() => {
                  if (selectedCardIds.length === filteredCards.length) {
                    setSelectedCardIds([]);
                    setSelectionAnchorCardId(null);
                    cardNavCursorRef.current = null;
                  } else {
                    setSelectedCardIds(filteredCards.map((c) => c.id));
                    setSelectionAnchorCardId(filteredCards[0]?.id ?? null);
                    cardNavCursorRef.current = filteredCards[filteredCards.length - 1]?.id ?? null;
                  }
                }}
                disabled={!filteredCards.length}
              />
            </div>
            {cardTableColumns.map((column, colIndex) => {
              const sortDirection = cardsSort.column === column.key ? cardsSort.direction : null;
              const filterValues = cardColumnFilters[column.key];
              return (
                <div key={column.key} className={`users-table-header-cell${selectedColumnKeys.has(column.key) ? " selected-column" : ""}`} onClick={(event) => {
                  setSelectedCardIds([]);
                  setSelectionAnchorCardId(null);

                  const columnKeys = cardTableColumns.map((c) => c.key);
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
                  for (const card of filteredCards) {
                    for (const col of nextCols) {
                      next.add(`${card.id}:${col}`);
                    }
                  }
                  setSelectedCells(next);
                  cellAnchorRef.current = null;
                }} onContextMenu={(event) => { event.preventDefault(); openCardHeaderOptions(event, column.key); }}>
                  <span className="users-table-header-label">{column.label}</span>
                  <button
                    className={sortDirection || filterValues.length ? "table-sort-button active" : "table-sort-button"}
                    type="button"
                    aria-label={`${column.label} options`}
                    onClick={(event) => { event.stopPropagation(); openCardHeaderOptions(event, column.key); }}
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

                  {openCardHeaderMenu?.key === column.key ? (
                    <UserHeaderFilterMenu
                        column={column}
                        options={cardFilterOptions[column.key]}
                        selectedValues={filterValues}
                        sortDirection={sortDirection}
                        onClearFilter={() => {
                          setCardColumnFilters((current) => ({ ...current, [column.key]: [] }));
                          setOpenCardHeaderMenu(null);
                        }}
                        onSortAsc={() => {
                          setCardsSort({ column: column.key, direction: "asc" });
                          setOpenCardHeaderMenu(null);
                        }}
                        onSortDesc={() => {
                          setCardsSort({ column: column.key, direction: "desc" });
                          setOpenCardHeaderMenu(null);
                        }}
                        onClearSort={() => {
                          setCardsSort({ column: null, direction: "asc" });
                          setOpenCardHeaderMenu(null);
                        }}
                        onApplyFilter={(values) => {
                          setCardColumnFilters((current) => ({ ...current, [column.key]: values }));
                        }}
                      onClose={() => setOpenCardHeaderMenu(null)}
                      style={openCardHeaderMenu}
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
                    <col style={{ width: "20%" }} />
                    <col style={{ width: "16%" }} />
                    <col style={{ width: "10%" }} />
                    <col style={{ width: "12%" }} />
                    <col style={{ width: "10%" }} />
                    <col />
                  </>
              }
            </colgroup>
            <tbody>
              {filteredCards.length ? filteredCards.map((card) => (
                <tr
                  key={card.id}
                  className={selectedCardIds.includes(card.id) ? "selected-row" : undefined}
                  aria-selected={selectedCardIds.includes(card.id)}
                  onMouseDown={(event) => {
                    if (event.shiftKey || event.metaKey || event.ctrlKey) {
                      event.preventDefault();
                    }
                  }}
                  onClick={(event) => handleCardRowSelection(event, card.id)}
                  onDoubleClick={() => openCardModal("view", card)}
                  onContextMenu={(event) => handleTableContextMenu(event, card)}
                >
                  <td className="row-checkbox-cell" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="row-select-checkbox"
                      aria-label={`Select ${card.name}`}
                      checked={selectedCardIds.includes(card.id)}
                      onChange={() => {
                        setSelectedCardIds((current) =>
                          current.includes(card.id)
                            ? current.filter((id) => id !== card.id)
                            : [...current, card.id]
                        );
                        setSelectionAnchorCardId(card.id);
                      }}
                    />
                  </td>
                  <td data-col="name" className={selectedCells.has(`${card.id}:name`) ? "selected-cell" : selectedColumnKeys.has("name") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, card.id, "name")) return; }}><HighlightMatch text={card.name} query={cardsSearch} /></td>
                  <td data-col="user_name" className={selectedCells.has(`${card.id}:user_name`) ? "selected-cell" : selectedColumnKeys.has("user_name") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, card.id, "user_name")) return; }}><HighlightMatch text={card.user_name || "\u2014"} query={cardsSearch} /></td>
                  <td data-col="last_four" className={selectedCells.has(`${card.id}:last_four`) ? "selected-cell" : selectedColumnKeys.has("last_four") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, card.id, "last_four")) return; }}><HighlightMatch text={card.last_four || "\u2014"} query={cardsSearch} /></td>
                  <td data-col="cashback_rate" className={selectedCells.has(`${card.id}:cashback_rate`) ? "selected-cell" : selectedColumnKeys.has("cashback_rate") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, card.id, "cashback_rate")) return; }}><HighlightMatch text={getCellDisplayValue(card, "cashback_rate")} query={cardsSearch} /></td>
                  <td data-col="status" className={selectedCells.has(`${card.id}:status`) ? "selected-cell" : selectedColumnKeys.has("status") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, card.id, "status")) return; }}>
                    <span className={card.is_active ? "status-chip active" : "status-chip inactive"}>
                      <HighlightMatch text={card.is_active ? "Active" : "Inactive"} query={cardsSearch} />
                    </span>
                  </td>
                  <td data-col="notes" className={`notes-cell${selectedCells.has(`${card.id}:notes`) ? " selected-cell" : selectedColumnKeys.has("notes") ? " selected-column-cell" : ""}`} onClick={(event) => { if (handleCellClick(event, card.id, "notes")) return; }} title={(card.notes || "").length > 100 ? card.notes : undefined}><HighlightMatch text={(card.notes || "").slice(0, 100) || "-"} query={cardsSearch} /></td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={cardTableColumns.length + 1} className="empty-state-cell">
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
                        ? (cardsSearch
                          ? <>No results for &ldquo;{cardsSearch}&rdquo;. <button className="inline-link-button" type="button" onClick={() => { setCardsSearch(""); clearCardSelection(); }}>Clear search</button></>
                          : "No cards match the current view.")
                        : "Connect the hosted workspace to load cards."
                      }</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="users-summary-rail users-summary-rail-bottom" aria-label="Card summary">
          <div className="users-page-metrics">
            <span className="users-metric-chip">{filteredCardCount} shown</span>
            <span className="users-metric-chip subdued">{totalCardCount} total</span>
            {selectedCardIds.length ? <span className="users-metric-chip accent">{selectedCardIds.length} selected</span> : null}
            {cardsFiltersActive ? <span className="users-metric-chip subdued">Filtered view</span> : null}
            {selectedCells.size ? (() => {
              const cellValues = [];
              for (const cellId of selectedCells) {
                const [cardId, colKey] = cellId.split(":");
                const card = filteredCards.find((c) => c.id === cardId);
                if (card) cellValues.push(getCellDisplayValue(card, colKey));
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
            {cardsHasMore && !cardsFiltersActive ? (
              <button className="ghost-button" type="button" onClick={loadNextCardsPage} disabled={cardsLoadingMore}>
                {cardsLoadingMore ? "Loading..." : "Load More Cards"}
              </button>
            ) : null}
          </div>
        </div>

        <button
          className={`back-to-top-button${showBackToTop ? " visible" : ""}`}
          type="button"
          aria-label="Back to top"
          onClick={() => {
            const viewport = cardsTableViewportRef.current;
            if (viewport) viewport.scrollTo({ top: 0, behavior: "smooth" });
          }}
        >
          &uarr;
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
          filteredUsers={filteredCards}
          selectedUsers={selectedCards}
          selectedCells={selectedCells}
          allColumns={cardTableColumns}
          onExport={(data, columns) => downloadCardsCsv(data, columns)}
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

      {cardModalMode ? (
        <CardModal
          mode={cardModalMode}
          card={selectedCard}
          form={cardForm}
          setForm={setCardForm}
          submitError={cardSubmitError}
          suggestions={cardSuggestions}
          users={users}
          onClose={requestCloseCardModal}
          onRequestEdit={() => selectedCard && openCardModal("edit", selectedCard)}
          onRequestDelete={() => selectedCard && handleDeleteCard([selectedCard])}
          onSubmit={submitCardModal}
        />
      ) : null}
    </section>
  );
}
