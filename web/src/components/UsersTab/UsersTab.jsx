import { useEffect, useMemo, useRef, useState } from "react";

import { authHeaders, describeFetchFailure, getAccessToken } from "../../services/api";
import Icon from "../common/Icon";
import HighlightMatch from "../common/HighlightMatch";
import ConfirmationModal from "../common/ConfirmationModal";
import UserModal from "./UserModal";
import ExportModal from "./ExportModal";
import UserHeaderFilterMenu from "./UserHeaderFilterMenu";
import TableContextMenu from "./TableContextMenu";
import {
  initialUserForm,
  initialUserColumnFilters,
  userTableColumns,
  usersPageSize,
  usersFallbackPageSize
} from "./usersConstants";
import {
  normalizeUserForm,
  isTextEntryElement,
  computeCellStats,
  getCellDisplayValue,
  downloadUsersCsv,
  getUserColumnValue,
  buildUserFilterOptions,
  mergeUsersById
} from "./usersUtils";

export default function UsersTab({ apiBaseUrl, hostedWorkspaceReady }) {
  const usersScrollGateRef = useRef({ armed: false, lastScrollTop: 0 });
  const usersPagingRequestRef = useRef(false);
  const usersTableViewportRef = useRef(null);
  const userNavCursorRef = useRef(null);
  const [users, setUsers] = useState([]);
  const [usersStatus, setUsersStatus] = useState("Sign in to load hosted users.");
  const [usersSearch, setUsersSearch] = useState("");
  const [userColumnFilters, setUserColumnFilters] = useState(initialUserColumnFilters);
  const [usersSort, setUsersSort] = useState({ column: null, direction: "asc" });
  const [openUserHeaderMenu, setOpenUserHeaderMenu] = useState(null);
  const [selectedUserIds, setSelectedUserIds] = useState([]);
  const [selectionAnchorUserId, setSelectionAnchorUserId] = useState(null);
  const [selectedColumnKeys, setSelectedColumnKeys] = useState(new Set());
  const [selectedCells, setSelectedCells] = useState(new Set());
  const cellAnchorRef = useRef(null);
  const [usersTotalCount, setUsersTotalCount] = useState(null);
  const [usersNextOffset, setUsersNextOffset] = useState(0);
  const [usersHasMore, setUsersHasMore] = useState(false);
  const [usersLoadingInitial, setUsersLoadingInitial] = useState(false);
  const [usersLoadingMore, setUsersLoadingMore] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const [columnWidths, setColumnWidths] = useState(null);
  const columnResizeRef = useRef(null);
  const headerRef = useRef(null);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [userModalMode, setUserModalMode] = useState(null);
  const [userForm, setUserForm] = useState(initialUserForm);
  const [userFormBaseline, setUserFormBaseline] = useState(initialUserForm);
  const [userSubmitError, setUserSubmitError] = useState(null);
  const [confirmationState, setConfirmationState] = useState(null);

  const filteredUsers = useMemo(() => {
    const searchText = usersSearch.trim().toLowerCase();
    const searchFiltered = !searchText
      ? users
      : users.filter((user) =>
          user.name.toLowerCase().includes(searchText)
          || (user.email || "").toLowerCase().includes(searchText)
          || (user.notes || "").toLowerCase().includes(searchText)
        );

    const columnFiltered = searchFiltered.filter((user) => {
      if (userColumnFilters.name.length && !userColumnFilters.name.includes(getUserColumnValue(user, "name"))) {
        return false;
      }
      if (userColumnFilters.email.length && !userColumnFilters.email.includes(getUserColumnValue(user, "email"))) {
        return false;
      }
      if (userColumnFilters.status.length && !userColumnFilters.status.includes(getUserColumnValue(user, "status"))) {
        return false;
      }
      if (userColumnFilters.notes.length && !userColumnFilters.notes.includes(getUserColumnValue(user, "notes"))) {
        return false;
      }
      return true;
    });

    if (!usersSort.column) {
      return columnFiltered;
    }

    const sortedUsers = [...columnFiltered].sort((left, right) => {
      const leftValue = usersSort.column === "status"
        ? (left.is_active ? "Active" : "Inactive")
        : String(left[usersSort.column] || "");
      const rightValue = usersSort.column === "status"
        ? (right.is_active ? "Active" : "Inactive")
        : String(right[usersSort.column] || "");

      return leftValue.localeCompare(rightValue, undefined, { sensitivity: "base" });
    });

    return usersSort.direction === "desc" ? sortedUsers.reverse() : sortedUsers;
  }, [userColumnFilters, users, usersSearch, usersSort]);

  const userFilterOptions = useMemo(() => ({
    name: buildUserFilterOptions(users, "name"),
    email: buildUserFilterOptions(users, "email"),
    status: [
      { value: "Active", label: "Active", path: ["Active"], searchValue: "Active" },
      { value: "Inactive", label: "Inactive", path: ["Inactive"], searchValue: "Inactive" }
    ],
    notes: buildUserFilterOptions(users, "notes")
  }), [users]);

  const filteredUserCount = filteredUsers.length;
  const totalUserCount = usersTotalCount ?? users.length;
  const devToolsVisible = Boolean(import.meta.env.DEV);

  const selectedUsers = users.filter((user) => selectedUserIds.includes(user.id));
  const selectedUser = selectedUsers.length === 1 ? selectedUsers[0] : null;
  const userModalDirty = userModalMode && userModalMode !== "view"
    ? JSON.stringify(normalizeUserForm(userForm)) !== JSON.stringify(normalizeUserForm(userFormBaseline))
    : false;

  const usersFiltersActive = Boolean(
    usersSearch
    || Object.values(userColumnFilters).some((values) => values.length)
    || usersSort.column
  );

  const userSuggestions = useMemo(() => ({
    names: [...new Set(users.map((user) => user.name).filter(Boolean))],
    emails: [...new Set(users.map((user) => user.email).filter(Boolean))]
  }), [users]);

  function clearUserSelection() {
    setSelectedUserIds([]);
    setSelectionAnchorUserId(null);
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
  }

  function closeUserModalImmediately() {
    setUserModalMode(null);
    setUserSubmitError(null);
    setUserForm(initialUserForm);
    setUserFormBaseline(initialUserForm);
  }

  function openConfirmation(options) {
    setConfirmationState(options);
  }

  function requestCloseUserModal() {
    if (!userModalDirty) {
      closeUserModalImmediately();
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
        closeUserModalImmediately();
      }
    });
  }

  // --- Data loading ---

  async function loadUsers(accessToken, { append = false } = {}) {
    if (!accessToken) {
      setUsers([]);
      setUsersTotalCount(null);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      clearUserSelection();
      setUsersStatus("Sign in to load hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setUsers([]);
      setUsersTotalCount(null);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      clearUserSelection();
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    const requestOffset = append ? usersNextOffset : 0;
    if (append) {
      setUsersLoadingMore(true);
    } else {
      setUsersLoadingInitial(true);
      setUsersStatus("Loading hosted users...");
    }

    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/users?limit=${usersPageSize}&offset=${requestOffset}`, {
        headers: authHeaders(accessToken)
      });
      const payload = await response.json();

      if (!response.ok) {
        setUsers([]);
        setUsersTotalCount(null);
        setUsersNextOffset(0);
        setUsersHasMore(false);
        clearUserSelection();
        setUsersStatus(payload.detail || `Hosted users failed to load (${response.status}).`);
        return;
      }

      const payloadUsers = Array.isArray(payload.users) ? payload.users : [];
      let loadedUsers = payloadUsers.slice(0, usersPageSize);
      let mergedUsers = append ? mergeUsersById(users, loadedUsers) : loadedUsers;
      let reportedTotalCount = Number.isFinite(payload.total_count) ? payload.total_count : null;
      let nextOffset = requestOffset + loadedUsers.length;
      let inferredHasMore = loadedUsers.length === usersPageSize;
      let hasMore = Boolean(payload.has_more) || nextOffset < (reportedTotalCount ?? 0) || inferredHasMore;

      if (append && loadedUsers.length && mergedUsers.length === users.length) {
        const fallbackResponse = await fetch(`${apiBaseUrl}/v1/workspace/users?limit=${usersFallbackPageSize}&offset=0`, {
          headers: authHeaders(accessToken)
        });
        const fallbackPayload = await fallbackResponse.json();

        if (fallbackResponse.ok) {
          const fallbackUsers = Array.isArray(fallbackPayload.users)
            ? fallbackPayload.users.slice(0, usersFallbackPageSize)
            : [];
          const fallbackMergedUsers = mergeUsersById(users, fallbackUsers);

          if (fallbackMergedUsers.length > users.length) {
            loadedUsers = fallbackUsers;
            mergedUsers = fallbackMergedUsers;
            reportedTotalCount = Number.isFinite(fallbackPayload.total_count)
              ? fallbackPayload.total_count
              : reportedTotalCount;
            nextOffset = mergedUsers.length;
            inferredHasMore = fallbackUsers.length === usersFallbackPageSize;
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

      const totalCount = Math.max(reportedTotalCount ?? 0, mergedUsers.length);

      if (!append) {
        usersScrollGateRef.current = {
          armed: false,
          lastScrollTop: usersTableViewportRef.current?.scrollTop || 0,
        };
      }

      setUsers(mergedUsers);
      setUsersTotalCount(totalCount);
      setUsersNextOffset(nextOffset);
      setUsersHasMore(hasMore);
      setSelectedUserIds((current) => current.filter((userId) => mergedUsers.some((user) => user.id === userId)));

      if (!mergedUsers.length) {
        setUsersStatus("No hosted users yet. Add your first user to get started.");
      } else if (hasMore) {
        setUsersStatus(`Loaded ${mergedUsers.length} of ${totalCount} hosted users.`);
      } else {
        setUsersStatus("Hosted users ready.");
      }
    } catch (error) {
      setUsers([]);
      setUsersTotalCount(null);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      clearUserSelection();
      setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
    } finally {
      setUsersLoadingInitial(false);
      setUsersLoadingMore(false);
    }
  }

  // --- Load users when workspace becomes ready ---

  useEffect(() => {
    if (!hostedWorkspaceReady || !apiBaseUrl) {
      return;
    }

    (async () => {
      try {
        const accessToken = await getAccessToken();
        if (accessToken) {
          await loadUsers(accessToken);
        }
      } catch (error) {
        setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
      }
    })();
  }, [hostedWorkspaceReady]);

  // --- Header menu close on outside click ---

  useEffect(() => {
    if (!openUserHeaderMenu) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (event.target instanceof Element && event.target.closest(".table-header-menu-wrap, .table-header-menu")) {
        return;
      }
      setOpenUserHeaderMenu(null);
    }

    function handleViewportChange() {
      setOpenUserHeaderMenu(null);
    }

    document.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("resize", handleViewportChange);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("resize", handleViewportChange);
    };
  }, [openUserHeaderMenu]);

  // --- Escape key handler for user-related modals ---

  useEffect(() => {
    const anyModalOpen = Boolean(
      openUserHeaderMenu
      || userModalMode
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

      if (openUserHeaderMenu) {
        if (blurActiveTextFieldWithin(".table-header-menu")) {
          return;
        }
        setOpenUserHeaderMenu(null);
        return;
      }

      if (userModalMode) {
        if (blurActiveTextFieldWithin(".modal-card")) {
          return;
        }
        requestCloseUserModal();
        return;
      }

      if (exportModalOpen) {
        setExportModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmationState, exportModalOpen, openUserHeaderMenu, userModalMode, userModalDirty]);

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
        if (selectedUserIds.length) {
          event.preventDefault();
          copyRowsAsTSV();
          return;
        }
        return;
      }

      if (event.key === "a" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (isTextEntryElement(document.activeElement)) return;
        if (confirmationState || userModalMode || openUserHeaderMenu) return;
        if (!filteredUsers.length) return;
        event.preventDefault();
        if (selectedUserIds.length === filteredUsers.length && filteredUsers.every((u) => selectedUserIds.includes(u.id))) {
          setSelectedUserIds([]);
          setSelectionAnchorUserId(null);
          userNavCursorRef.current = null;
        } else {
          setSelectedUserIds(filteredUsers.map((u) => u.id));
          setSelectionAnchorUserId(filteredUsers[0].id);
          userNavCursorRef.current = filteredUsers[filteredUsers.length - 1].id;
        }
        return;
      }

      if (event.key === "f" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (confirmationState || userModalMode || openUserHeaderMenu) return;
        event.preventDefault();
        const searchInput = document.getElementById("users-search-input");
        if (searchInput) searchInput.focus();
        return;
      }

      if (event.key === "Escape") {
        const searchInput = document.getElementById("users-search-input");
        if (document.activeElement === searchInput) {
          event.preventDefault();
          if (usersSearch) {
            setUsersSearch("");
          } else {
            searchInput.blur();
          }
          return;
        }
      }

      if (event.key !== "ArrowUp" && event.key !== "ArrowDown" && event.key !== "Enter") return;
      if (isTextEntryElement(document.activeElement)) return;
      if (confirmationState || userModalMode || openUserHeaderMenu) return;

      if (event.key === "Enter") {
        if (selectedUserIds.length === 1) {
          const user = filteredUsers.find((u) => u.id === selectedUserIds[0]);
          if (user) openUserModal("view", user);
        }
        return;
      }

      if (!filteredUsers.length || !selectedUserIds.length) return;

      event.preventDefault();
      const orderedIds = filteredUsers.map((u) => u.id);
      const cursorId = userNavCursorRef.current ?? selectedUserIds[selectedUserIds.length - 1];
      const currentIndex = orderedIds.indexOf(cursorId);
      if (currentIndex === -1) return;

      const nextIndex = event.key === "ArrowDown"
        ? Math.min(currentIndex + 1, orderedIds.length - 1)
        : Math.max(currentIndex - 1, 0);
      const nextId = orderedIds[nextIndex];
      userNavCursorRef.current = nextId;

      if (event.shiftKey) {
        setSelectedUserIds(() => {
          const anchor = selectionAnchorUserId && orderedIds.includes(selectionAnchorUserId)
            ? orderedIds.indexOf(selectionAnchorUserId)
            : currentIndex;
          const [start, end] = anchor < nextIndex ? [anchor, nextIndex] : [nextIndex, anchor];
          return orderedIds.slice(start, end + 1);
        });
      } else {
        setSelectedUserIds([nextId]);
        setSelectionAnchorUserId(nextId);
      }

      const viewport = usersTableViewportRef.current;
      if (viewport) {
        requestAnimationFrame(() => {
          const row = viewport.querySelector(`tbody tr:nth-child(${nextIndex + 1})`);
          if (row) row.scrollIntoView({ block: "nearest" });
        });
      }
    }

    window.addEventListener("keydown", handleArrowNav);
    return () => window.removeEventListener("keydown", handleArrowNav);
  }, [confirmationState, filteredUsers, openUserHeaderMenu, selectedCells, selectedUserIds, selectionAnchorUserId, userModalMode]);

  // --- Sort / filter ---

  function toggleUserSort(column) {
    setUsersSort((current) => {
      if (current.column !== column) {
        return { column, direction: "asc" };
      }
      if (current.direction === "asc") {
        return { column, direction: "desc" };
      }
      return { column: null, direction: "asc" };
    });
  }

  function clearAllUserFilters() {
    setUsersSearch("");
    setUserColumnFilters(initialUserColumnFilters);
    setUsersSort({ column: null, direction: "asc" });
    setOpenUserHeaderMenu(null);
    clearUserSelection();
  }

  // --- Row / cell selection ---

  function handleUserRowSelection(event, userId) {
    event.preventDefault();
    setSelectedCells(new Set());
    setSelectedColumnKeys(new Set());
    cellAnchorRef.current = null;
    const orderedIds = filteredUsers.map((user) => user.id);

    if (event.shiftKey && selectionAnchorUserId && orderedIds.includes(selectionAnchorUserId)) {
      const anchorIndex = orderedIds.indexOf(selectionAnchorUserId);
      const targetIndex = orderedIds.indexOf(userId);
      const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
      const rangeIds = orderedIds.slice(start, end + 1);
      setSelectedUserIds((current) => (event.metaKey || event.ctrlKey ? [...new Set([...current, ...rangeIds])] : rangeIds));
      return;
    }

    if (event.metaKey || event.ctrlKey) {
      setSelectedUserIds((current) => (
        current.includes(userId)
          ? current.filter((candidate) => candidate !== userId)
          : [...current, userId]
      ));
      setSelectionAnchorUserId(userId);
      return;
    }

    setSelectedUserIds([userId]);
    setSelectionAnchorUserId(userId);
    userNavCursorRef.current = userId;
  }

  function handleCellClick(event, userId, columnKey) {
    if (!event.altKey) return false;
    event.stopPropagation();
    event.preventDefault();

    setSelectedUserIds([]);
    setSelectionAnchorUserId(null);

    const cellId = `${userId}:${columnKey}`;
    const columnKeys = userTableColumns.map((c) => c.key);

    if (event.shiftKey && cellAnchorRef.current) {
      const anchor = cellAnchorRef.current;
      const orderedIds = filteredUsers.map((u) => u.id);
      const anchorRowIdx = orderedIds.indexOf(anchor.userId);
      const targetRowIdx = orderedIds.indexOf(userId);
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
      cellAnchorRef.current = { userId, columnKey };
    }
    return true;
  }

  // --- Copy ---

  function copyCellsAsTSV() {
    const columnKeys = userTableColumns.map((c) => c.key);
    const orderedIds = filteredUsers.map((u) => u.id);
    const rows = [];
    for (const uid of orderedIds) {
      const row = [];
      let hasCell = false;
      for (const col of columnKeys) {
        if (selectedCells.has(`${uid}:${col}`)) {
          const u = filteredUsers.find((x) => x.id === uid);
          row.push(u ? getCellDisplayValue(u, col) : "");
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
    const columnKeys = userTableColumns.map((c) => c.key);
    const orderedIds = filteredUsers.map((u) => u.id);
    const rows = [];
    for (const uid of orderedIds) {
      if (!selectedUserIds.includes(uid)) continue;
      const u = filteredUsers.find((x) => x.id === uid);
      if (!u) continue;
      rows.push(columnKeys.map((col) => getCellDisplayValue(u, col)));
    }
    const tsv = rows.map((r) => r.join("\t")).join("\n");
    navigator.clipboard.writeText(tsv).catch(() => {});
  }

  // --- Context menu ---

  function handleTableContextMenu(event, user) {
    event.preventDefault();
    setContextMenu(null);

    let td = event.target;
    while (td && td.tagName !== "TD") td = td.parentElement;
    const clickedColumnKey = td?.dataset?.col || null;

    const items = [];
    const isRowSelected = selectedUserIds.includes(user.id);
    const hasCellSelection = selectedCells.size > 0;
    const hasRowSelection = selectedUserIds.length > 0;

    if (clickedColumnKey) {
      const cellValue = getCellDisplayValue(user, clickedColumnKey);
      const truncated = cellValue.length > 30 ? `${cellValue.slice(0, 27)}…` : cellValue;
      items.push({ label: `Copy "${truncated}"`, action: () => { navigator.clipboard.writeText(cellValue).catch(() => {}); }});
    }

    if (hasCellSelection) {
      items.push({ label: `Copy ${selectedCells.size} cell${selectedCells.size > 1 ? "s" : ""}`, action: copyCellsAsTSV });
    }

    if (hasRowSelection) {
      const count = selectedUserIds.length;
      items.push({ label: count > 1 ? `Copy ${count} rows` : "Copy row", action: copyRowsAsTSV });
    }

    items.push({ divider: true });

    if (!isRowSelected) {
      items.push({ label: "Select row", action: () => { setSelectedUserIds([user.id]); setSelectionAnchorUserId(user.id); }});
      items.push({ divider: true });
    }

    const targetUsers = isRowSelected ? selectedUsers : [user];
    const targetCount = targetUsers.length;

    items.push({ label: "View", action: () => openUserModal("view", targetCount === 1 ? targetUsers[0] : user), disabled: targetCount !== 1 });
    items.push({ label: "Edit", action: () => openUserModal("edit", targetCount === 1 ? targetUsers[0] : user), disabled: targetCount !== 1 });
    items.push({ divider: true });

    if (hasCellSelection) {
      items.push({ label: "Clear cell selection", action: () => { setSelectedCells(new Set()); setSelectedColumnKeys(new Set()); cellAnchorRef.current = null; }});
    }

    items.push({
      label: targetCount > 1 ? `Delete ${targetCount} users` : "Delete",
      danger: true,
      action: () => handleDeleteUser(targetUsers),
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
    return widths.length === userTableColumns.length ? widths : null;
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
      const viewport = usersTableViewportRef.current;
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

    const columnKey = userTableColumns[colIndex]?.key;
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

    for (const user of filteredUsers) {
      const value = getCellDisplayValue(user, columnKey);
      const textWidth = ctx.measureText(value).width;
      maxWidth = Math.max(maxWidth, textWidth + 24);
    }

    widths[colIndex] = Math.min(Math.ceil(maxWidth), 600);

    const viewport = usersTableViewportRef.current;
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

  async function loadNextUsersPage() {
    if (usersPagingRequestRef.current || usersLoadingInitial || usersLoadingMore || !usersHasMore || usersFiltersActive) {
      return;
    }

    usersPagingRequestRef.current = true;

    try {
      const accessToken = await getAccessToken();
      if (accessToken) {
        await loadUsers(accessToken, { append: true });
      }
    } catch (error) {
      setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
    } finally {
      usersPagingRequestRef.current = false;
    }
  }

  useEffect(() => {
    if (!usersHasMore || usersFiltersActive || usersLoadingInitial || usersLoadingMore || !hostedWorkspaceReady) {
      return undefined;
    }

    const viewport = usersTableViewportRef.current;
    if (!viewport) {
      return undefined;
    }

    function handleViewportScroll() {
      const scrollTop = viewport.scrollTop || 0;
      const scrollGate = usersScrollGateRef.current;

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
        loadNextUsersPage();
      }
    }

    viewport.addEventListener("scroll", handleViewportScroll, { passive: true });
    return () => viewport.removeEventListener("scroll", handleViewportScroll);
  }, [hostedWorkspaceReady, usersFiltersActive, usersHasMore, usersLoadingInitial, usersLoadingMore, usersNextOffset]);

  // --- Header menu ---

  function openUserHeaderOptions(event, columnKey) {
    const buttonRect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 296;
    const left = Math.max(16, Math.min(buttonRect.right - menuWidth, window.innerWidth - menuWidth - 16));
    const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 24);

    setOpenUserHeaderMenu((current) => current?.key === columnKey ? null : { key: columnKey, left, top });
  }

  // --- User CRUD ---

  function openUserModal(mode, user = null) {
    setUserModalMode(mode);
    setUserSubmitError(null);

    if (user) {
      const nextForm = {
        name: user.name || "",
        email: user.email || "",
        notes: user.notes || "",
        is_active: Boolean(user.is_active)
      };
      setUserForm(nextForm);
      setUserFormBaseline(nextForm);
      setSelectedUserIds([user.id]);
      setSelectionAnchorUserId(user.id);
      return;
    }

    setUserForm(initialUserForm);
    setUserFormBaseline(initialUserForm);
  }

  async function submitUserModal() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setUserSubmitError("Google sign-in is required before managing hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setUserSubmitError("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    const payload = {
      name: userForm.name,
      email: userForm.email || null,
      notes: userForm.notes || null,
      ...(userModalMode === "edit" ? { is_active: userForm.is_active } : {})
    };
    const url = userModalMode === "edit" && selectedUser
      ? `${apiBaseUrl}/v1/workspace/users/${selectedUser.id}`
      : `${apiBaseUrl}/v1/workspace/users`;
    const method = userModalMode === "edit" ? "PATCH" : "POST";

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
        setUserSubmitError(data.detail || `Hosted users save failed (${response.status}).`);
        return;
      }

      setUsers((current) => mergeUsersById(current, [data]));
      setUsersTotalCount((current) => (method === "POST" && current !== null ? current + 1 : current));
      setSelectedUserIds([data.id]);
      setSelectionAnchorUserId(data.id);
      setUsersStatus("Hosted users ready.");
      closeUserModalImmediately();
    } catch (error) {
      setUserSubmitError(describeFetchFailure(error, "Hosted users save failed."));
    }
  }

  async function handleSeedDemoUsers() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setUsersStatus("Google sign-in is required before managing hosted users.");
      return;
    }
    if (!apiBaseUrl) {
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    setUsersStatus("Creating 200 demo users...");

    try {
      const demoUsers = Array.from({ length: 200 }, (_, index) => ({
        name: `Demo User ${String(index + 1).padStart(3, "0")}`,
        email: `demo.user.${String(index + 1).padStart(3, "0")}@sezzions.local`,
        notes: `Demo paging record ${index + 1}`,
        is_active: index % 5 !== 0
      }));

      for (const demoUser of demoUsers) {
        const response = await fetch(`${apiBaseUrl}/v1/workspace/users`, {
          method: "POST",
          headers: {
            ...authHeaders(accessToken),
            "Content-Type": "application/json"
          },
          body: JSON.stringify(demoUser)
        });

        if (!response.ok) {
          const detail = response.headers.get("content-type")?.includes("application/json")
            ? (await response.json()).detail
            : `Hosted users save failed (${response.status}).`;
          setUsersStatus(detail || `Hosted users save failed (${response.status}).`);
          return;
        }
      }

      clearUserSelection();
      await loadUsers(accessToken, { append: false });
      setUsersStatus("Created 200 demo users for paging preview.");
    } catch (error) {
      setUsersStatus(describeFetchFailure(error, "Hosted users save failed."));
    }
  }

  async function handleUsersRefresh() {
    try {
      const accessToken = await getAccessToken();
      clearUserSelection();
      await loadUsers(accessToken, { append: false });
    } catch (error) {
      setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
    }
  }

  async function handleDeleteUser(usersToDelete = selectedUsers) {
    const accessToken = await getAccessToken();
    if (!usersToDelete.length || !accessToken) {
      setUsersStatus("Google sign-in is required before managing hosted users.");
      return;
    }
    if (!apiBaseUrl) {
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }
    const prompt = usersToDelete.length === 1
      ? `Delete user '${usersToDelete[0].name}'? This cannot be undone.`
      : `Delete ${usersToDelete.length} users? This cannot be undone.`;

    openConfirmation({
      title: usersToDelete.length === 1 ? "Delete user?" : "Delete users?",
      message: prompt,
      confirmLabel: usersToDelete.length === 1 ? "Delete User" : `Delete ${usersToDelete.length} Users`,
      cancelLabel: "Cancel",
      tone: "danger",
      onConfirm: async () => {
        setConfirmationState(null);

        try {
          setUsersStatus(`Deleting ${usersToDelete.length} hosted ${usersToDelete.length === 1 ? "user" : "users"}...`);

          const response = await fetch(`${apiBaseUrl}/v1/workspace/users/batch-delete`, {
            method: "POST",
            headers: {
              ...authHeaders(accessToken),
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              user_ids: usersToDelete.map((user) => user.id)
            })
          });

          if (!response.ok) {
            const detail = response.headers.get("content-type")?.includes("application/json")
              ? (await response.json()).detail
              : `Hosted users delete failed (${response.status}).`;
            setUsersStatus(detail || `Hosted users delete failed (${response.status}).`);
            return;
          }

          const deletedIds = new Set(usersToDelete.map((user) => user.id));
          setUsers((current) => current.filter((candidate) => !deletedIds.has(candidate.id)));
          setUsersTotalCount((current) => (current === null ? null : Math.max(0, current - usersToDelete.length)));
          clearUserSelection();
          closeUserModalImmediately();
          setUsersStatus("Hosted users ready.");
        } catch (error) {
          setUsersStatus(describeFetchFailure(error, "Hosted users delete failed."));
        }
      }
    });
  }

  // --- Render ---

  return (
    <section className="workspace-panel setup-panel users-page" aria-label="Setup Users">
      <div className="users-surface">
        <div className="users-toolbar">
          <div className="users-toolbar-top">
            <nav className="users-breadcrumb" aria-label="Breadcrumb">
              <span className="breadcrumb-segment">Setup</span>
              <span className="breadcrumb-separator" aria-hidden="true">›</span>
              <h2 className="breadcrumb-segment current" title="Manage workspace users, inspect individual records, and export the current filtered view.">Users</h2>
            </nav>
            <div className="toolbar-row wrap-toolbar users-toolbar-actions">
              <button className="primary-button" type="button" onClick={() => openUserModal("create")} disabled={!hostedWorkspaceReady}>Add User</button>
              <button className="ghost-button" type="button" onClick={() => selectedUser && openUserModal("view", selectedUser)} disabled={!hostedWorkspaceReady || selectedUserIds.length !== 1}>View</button>
              <button className="ghost-button" type="button" onClick={() => selectedUser && openUserModal("edit", selectedUser)} disabled={!hostedWorkspaceReady || selectedUserIds.length !== 1}>Edit</button>
              <button className="ghost-button" type="button" onClick={() => handleDeleteUser()} disabled={!hostedWorkspaceReady || !selectedUserIds.length}>Delete</button>
              <button className="ghost-button" type="button" onClick={() => setExportModalOpen(true)} disabled={!filteredUsers.length}>Export CSV</button>
              <button className="ghost-button" type="button" onClick={handleUsersRefresh} disabled={!hostedWorkspaceReady}>Refresh</button>
              {devToolsVisible ? <button className="ghost-button" type="button" onClick={handleSeedDemoUsers} disabled={!hostedWorkspaceReady}>Seed 200 Demo Users</button> : null}
            </div>
          </div>
          <div className="users-search-bar">
            <label className="users-search-field" htmlFor="users-search-input">
              <span className="users-search-icon" aria-hidden="true"><Icon name="search" className="app-icon" /></span>
              <input
                id="users-search-input"
                className="text-input hero-search-input"
                type="text"
                placeholder="Search users..."
                value={usersSearch}
                disabled={!hostedWorkspaceReady}
                onChange={(event) => setUsersSearch(event.target.value)}
              />
            </label>
            <div className="toolbar-row users-search-actions">
              <button className="ghost-button" type="button" onClick={() => { setUsersSearch(""); clearUserSelection(); }}>Clear Search</button>
              <button className="ghost-button" type="button" onClick={clearAllUserFilters}>Clear All Filters</button>
            </div>
          </div>
        </div>

        <div className="users-table-scroll-area table-viewport" ref={usersTableViewportRef} onScroll={(e) => setShowBackToTop(e.currentTarget.scrollTop > 120)}>
          <div className="users-table-header" ref={headerRef} style={columnWidths ? { gridTemplateColumns: `36px ${columnWidths.map((w) => `${w}px`).join(" ")}`, minWidth: `${36 + columnWidths.reduce((a, b) => a + b, 0)}px` } : undefined}>
            <div className="users-table-header-cell users-checkbox-cell">
              <input
                type="checkbox"
                className="row-select-checkbox"
                aria-label="Select all rows"
                checked={filteredUsers.length > 0 && selectedUserIds.length === filteredUsers.length}
                ref={(el) => { if (el) el.indeterminate = selectedUserIds.length > 0 && selectedUserIds.length < filteredUsers.length; }}
                onChange={() => {
                  if (selectedUserIds.length === filteredUsers.length) {
                    setSelectedUserIds([]);
                    setSelectionAnchorUserId(null);
                    userNavCursorRef.current = null;
                  } else {
                    setSelectedUserIds(filteredUsers.map((u) => u.id));
                    setSelectionAnchorUserId(filteredUsers[0]?.id ?? null);
                    userNavCursorRef.current = filteredUsers[filteredUsers.length - 1]?.id ?? null;
                  }
                }}
                disabled={!filteredUsers.length}
              />
            </div>
            {userTableColumns.map((column, colIndex) => {
              const sortDirection = usersSort.column === column.key ? usersSort.direction : null;
              const filterValues = userColumnFilters[column.key];
              return (
                <div key={column.key} className={`users-table-header-cell${selectedColumnKeys.has(column.key) ? " selected-column" : ""}`} onClick={(event) => {
                  setSelectedUserIds([]);
                  setSelectionAnchorUserId(null);

                  const columnKeys = userTableColumns.map((c) => c.key);
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
                  for (const user of filteredUsers) {
                    for (const col of nextCols) {
                      next.add(`${user.id}:${col}`);
                    }
                  }
                  setSelectedCells(next);
                  cellAnchorRef.current = null;
                }} onContextMenu={(event) => { event.preventDefault(); openUserHeaderOptions(event, column.key); }}>
                  <span className="users-table-header-label">{column.label}</span>
                  <button
                    className={sortDirection || filterValues.length ? "table-sort-button active" : "table-sort-button"}
                    type="button"
                    aria-label={`${column.label} options`}
                    onClick={(event) => { event.stopPropagation(); openUserHeaderOptions(event, column.key); }}
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

                  {openUserHeaderMenu?.key === column.key ? (
                    <UserHeaderFilterMenu
                        column={column}
                        options={userFilterOptions[column.key]}
                        selectedValues={filterValues}
                        sortDirection={sortDirection}
                        onClearFilter={() => {
                          setUserColumnFilters((current) => ({ ...current, [column.key]: [] }));
                          setOpenUserHeaderMenu(null);
                        }}
                        onSortAsc={() => {
                          setUsersSort({ column: column.key, direction: "asc" });
                          setOpenUserHeaderMenu(null);
                        }}
                        onSortDesc={() => {
                          setUsersSort({ column: column.key, direction: "desc" });
                          setOpenUserHeaderMenu(null);
                        }}
                        onClearSort={() => {
                          setUsersSort({ column: null, direction: "asc" });
                          setOpenUserHeaderMenu(null);
                        }}
                        onApplyFilter={(values) => {
                          setUserColumnFilters((current) => ({ ...current, [column.key]: values }));
                        }}
                      onClose={() => setOpenUserHeaderMenu(null)}
                      style={openUserHeaderMenu}
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
                    <col style={{ width: "30%" }} />
                    <col style={{ width: "12%" }} />
                    <col />
                  </>
              }
            </colgroup>
            <tbody>
              {filteredUsers.length ? filteredUsers.map((user) => (
                <tr
                  key={user.id}
                  className={selectedUserIds.includes(user.id) ? "selected-row" : undefined}
                  aria-selected={selectedUserIds.includes(user.id)}
                  onMouseDown={(event) => {
                    if (event.shiftKey || event.metaKey || event.ctrlKey) {
                      event.preventDefault();
                    }
                  }}
                  onClick={(event) => handleUserRowSelection(event, user.id)}
                  onDoubleClick={() => openUserModal("view", user)}
                  onContextMenu={(event) => handleTableContextMenu(event, user)}
                >
                  <td className="row-checkbox-cell" onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="row-select-checkbox"
                      aria-label={`Select ${user.name}`}
                      checked={selectedUserIds.includes(user.id)}
                      onChange={() => {
                        setSelectedUserIds((current) =>
                          current.includes(user.id)
                            ? current.filter((id) => id !== user.id)
                            : [...current, user.id]
                        );
                        setSelectionAnchorUserId(user.id);
                      }}
                    />
                  </td>
                  <td data-col="name" className={selectedCells.has(`${user.id}:name`) ? "selected-cell" : selectedColumnKeys.has("name") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, user.id, "name")) return; }}><HighlightMatch text={user.name} query={usersSearch} /></td>
                  <td data-col="email" className={selectedCells.has(`${user.id}:email`) ? "selected-cell" : selectedColumnKeys.has("email") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, user.id, "email")) return; }}><HighlightMatch text={user.email || ""} query={usersSearch} /></td>
                  <td data-col="status" className={selectedCells.has(`${user.id}:status`) ? "selected-cell" : selectedColumnKeys.has("status") ? "selected-column-cell" : undefined} onClick={(event) => { if (handleCellClick(event, user.id, "status")) return; }}>
                    <span className={user.is_active ? "status-chip active" : "status-chip inactive"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td data-col="notes" className={`notes-cell${selectedCells.has(`${user.id}:notes`) ? " selected-cell" : selectedColumnKeys.has("notes") ? " selected-column-cell" : ""}`} onClick={(event) => { if (handleCellClick(event, user.id, "notes")) return; }} title={(user.notes || "").length > 100 ? user.notes : undefined}><HighlightMatch text={(user.notes || "").slice(0, 100) || "-"} query={usersSearch} /></td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" className="empty-state-cell">
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
                        ? (usersSearch
                          ? <>No results for &ldquo;{usersSearch}&rdquo;. <button className="inline-link-button" type="button" onClick={() => { setUsersSearch(""); clearUserSelection(); }}>Clear search</button></>
                          : "No users match the current view.")
                        : "Connect the hosted workspace to load users."
                      }</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="users-summary-rail users-summary-rail-bottom" aria-label="User summary">
          <div className="users-page-metrics">
            <span className="users-metric-chip">{filteredUserCount} shown</span>
            <span className="users-metric-chip subdued">{totalUserCount} total</span>
            {selectedUserIds.length ? <span className="users-metric-chip accent">{selectedUserIds.length} selected</span> : null}
            {usersFiltersActive ? <span className="users-metric-chip subdued">Filtered view</span> : null}
            {selectedCells.size ? (() => {
              const cellValues = [];
              for (const cellId of selectedCells) {
                const [userId, colKey] = cellId.split(":");
                const user = filteredUsers.find((u) => u.id === userId);
                if (user) cellValues.push(getCellDisplayValue(user, colKey));
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
            {usersHasMore && !usersFiltersActive ? (
              <button className="ghost-button" type="button" onClick={loadNextUsersPage} disabled={usersLoadingMore}>
                {usersLoadingMore ? "Loading..." : "Load More Users"}
              </button>
            ) : null}
          </div>
        </div>

        <button
          className={`back-to-top-button${showBackToTop ? " visible" : ""}`}
          type="button"
          aria-label="Back to top"
          onClick={() => {
            const viewport = usersTableViewportRef.current;
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
          filteredUsers={filteredUsers}
          selectedUsers={selectedUsers}
          selectedCells={selectedCells}
          allColumns={userTableColumns}
          onExport={(users, columns) => downloadUsersCsv(users, columns)}
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

      {userModalMode ? (
        <UserModal
          mode={userModalMode}
          user={selectedUser}
          form={userForm}
          setForm={setUserForm}
          submitError={userSubmitError}
          suggestions={userSuggestions}
          onClose={requestCloseUserModal}
          onRequestEdit={() => selectedUser && openUserModal("edit", selectedUser)}
          onRequestDelete={() => selectedUser && handleDeleteUser([selectedUser])}
          onSubmit={submitUserModal}
        />
      ) : null}
    </section>
  );
}
