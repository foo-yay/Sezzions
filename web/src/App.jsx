import { useEffect, useMemo, useRef, useState } from "react";

import { supabase, supabaseConfigError, supabaseConfigured } from "./lib/supabaseClient";
import "./styles.css";

const setupTabs = [
  { key: "users", label: "Users", icon: "users", enabled: true },
  { key: "sites", label: "Sites", icon: "sites", enabled: false },
  { key: "cards", label: "Cards", icon: "cards", enabled: false },
  { key: "method-types", label: "Method Types", icon: "methodTypes", enabled: false },
  { key: "redemption-methods", label: "Redemption Methods", icon: "redemptionMethods", enabled: false },
  { key: "game-types", label: "Game Types", icon: "gameTypes", enabled: false },
  { key: "games", label: "Games", icon: "games", enabled: false },
  { key: "tools", label: "Tools", icon: "tools", enabled: false }
];

function Icon({ name, className }) {
  const svgProps = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    className
  };

  switch (name) {
    case "menu":
      return (
        <svg {...svgProps}>
          <path d="M4 7h16" />
          <path d="M4 12h16" />
          <path d="M4 17h16" />
        </svg>
      );
    case "notifications":
      return (
        <svg {...svgProps}>
          <path d="M15 18H9" />
          <path d="M18 16V11a6 6 0 0 0-12 0v5l-2 2h16z" />
        </svg>
      );
    case "account":
      return (
        <svg {...svgProps}>
          <path d="M20 21a8 8 0 0 0-16 0" />
          <circle cx="12" cy="8" r="4" />
        </svg>
      );
    case "settings":
      return (
        <svg {...svgProps}>
          <path d="M10 5H4" />
          <path d="M20 5h-4" />
          <path d="M14 5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
          <path d="M6 12H4" />
          <path d="M20 12h-8" />
          <path d="M12 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
          <path d="M20 19h-4" />
          <path d="M10 19H4" />
          <path d="M18 19a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z" />
        </svg>
      );
    case "setup":
      return (
        <svg {...svgProps}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1 1 0 0 1 0 1.4l-1.3 1.3a1 1 0 0 1-1.4 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a1 1 0 0 1-1.4 0l-1.3-1.3a1 1 0 0 1 0-1.4l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a1 1 0 0 1 0-1.4l1.3-1.3a1 1 0 0 1 1.4 0l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a1 1 0 0 1 1.4 0l1.3 1.3a1 1 0 0 1 0 1.4l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-.2a1 1 0 0 0-.9.6Z" />
        </svg>
      );
    case "users":
      return (
        <svg {...svgProps}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9.5" cy="7" r="3.5" />
          <path d="M20 8.5a3 3 0 0 0-2-2.83" />
          <path d="M20 16a3 3 0 0 0-3-3h-1" />
        </svg>
      );
    case "sites":
      return (
        <svg {...svgProps}>
          <path d="M12 21s6-5.7 6-11a6 6 0 1 0-12 0c0 5.3 6 11 6 11Z" />
          <circle cx="12" cy="10" r="2.5" />
        </svg>
      );
    case "cards":
      return (
        <svg {...svgProps}>
          <rect x="3" y="6" width="18" height="12" rx="2" />
          <path d="M3 10h18" />
          <path d="M7 15h3" />
        </svg>
      );
    case "methodTypes":
      return (
        <svg {...svgProps}>
          <path d="M8 7h8" />
          <path d="M8 12h8" />
          <path d="M8 17h5" />
          <path d="M5 7h.01" />
          <path d="M5 12h.01" />
          <path d="M5 17h.01" />
        </svg>
      );
    case "redemptionMethods":
      return (
        <svg {...svgProps}>
          <path d="M9 7H5v4" />
          <path d="M5 11a7 7 0 1 0 2-4" />
        </svg>
      );
    case "gameTypes":
      return (
        <svg {...svgProps}>
          <rect x="5" y="5" width="14" height="14" rx="2" />
          <circle cx="9" cy="9" r="1" fill="currentColor" stroke="none" />
          <circle cx="15" cy="9" r="1" fill="currentColor" stroke="none" />
          <circle cx="9" cy="15" r="1" fill="currentColor" stroke="none" />
          <circle cx="15" cy="15" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "games":
      return (
        <svg {...svgProps}>
          <path d="M6 12h12" />
          <path d="M8 12V9a4 4 0 0 1 8 0v3" />
          <rect x="4" y="12" width="16" height="7" rx="3" />
          <path d="M9 15h.01" />
          <path d="M15 15h.01" />
        </svg>
      );
    case "tools":
      return (
        <svg {...svgProps}>
          <path d="M14.5 6.5a3.5 3.5 0 0 0-4.95 4.95l-4.05 4.05a1.5 1.5 0 1 0 2.12 2.12l4.05-4.05a3.5 3.5 0 0 0 4.95-4.95l-2.12 2.12-2.12-2.12 2.12-2.12Z" />
        </svg>
      );
    case "upload":
      return (
        <svg {...svgProps}>
          <path d="M12 16V5" />
          <path d="m7 10 5-5 5 5" />
          <path d="M5 19h14" />
        </svg>
      );
    case "search":
      return (
        <svg {...svgProps}>
          <circle cx="11" cy="11" r="6" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      );
    case "filterMenu":
      return (
        <svg {...svgProps}>
          <path d="M4 7h16" />
          <path d="M7 12h10" />
          <path d="M10 17h4" />
        </svg>
      );
    case "chevronDown":
      return (
        <svg {...svgProps}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      );
    case "chevronRight":
      return (
        <svg {...svgProps}>
          <path d="m9 6 6 6-6 6" />
        </svg>
      );
    default:
      return null;
  }
}

const initialUserForm = {
  name: "",
  email: "",
  notes: "",
  is_active: true
};

function normalizeUserForm(form) {
  return {
    name: form.name || "",
    email: form.email || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

function isTextEntryElement(element) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  if (element instanceof HTMLTextAreaElement) {
    return !element.readOnly && !element.disabled;
  }

  if (element instanceof HTMLInputElement) {
    const textLikeTypes = new Set(["text", "search", "email", "url", "tel", "password", "number"]);
    return textLikeTypes.has(element.type) && !element.readOnly && !element.disabled;
  }

  return element.isContentEditable;
}

function parseNumericValue(text) {
  if (!text || typeof text !== "string") return null;
  const trimmed = text.trim();
  if (!trimmed || ["n/a", "na", "-", "\u2014", "\u2013"].includes(trimmed.toLowerCase())) return null;
  let cleaned = trimmed.replace(/[$\u20ac\u00a3\u00a5,\s]/g, "");
  if (cleaned.startsWith("(") && cleaned.endsWith(")")) cleaned = "-" + cleaned.slice(1, -1);
  if (cleaned.endsWith("%")) cleaned = cleaned.slice(0, -1);
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

function computeCellStats(values) {
  const count = values.length;
  const nums = values.map(parseNumericValue).filter((v) => v !== null);
  if (!nums.length) return { count, numericCount: 0, sum: 0, avg: 0, min: null, max: null };
  const sum = nums.reduce((a, b) => a + b, 0);
  return {
    count,
    numericCount: nums.length,
    sum,
    avg: sum / nums.length,
    min: Math.min(...nums),
    max: Math.max(...nums)
  };
}

function getCellDisplayValue(user, columnKey) {
  if (columnKey === "status") return user.is_active ? "Active" : "Inactive";
  return String(user[columnKey] || "");
}

function HighlightMatch({ text, query }) {
  if (!query || !text) return text || "";
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  if (parts.length === 1) return text;
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase()
      ? <mark key={i} className="search-highlight">{part}</mark>
      : part
  );
}

const initialUserColumnFilters = {
  name: [],
  email: [],
  status: [],
  notes: []
};

const userTableColumns = [
  { key: "name", label: "Name", sortable: true },
  { key: "email", label: "Email", sortable: true },
  { key: "status", label: "Status", sortable: true },
  { key: "notes", label: "Notes", sortable: true }
];

const usersPageSize = 100;
const usersFallbackPageSize = 500;

const oauthReturnRouteStorageKey = "sezzions.oauthReturnRoute";

function readCurrentRoute() {
  const hashRoute = window.location.hash.replace(/^#/, "").replace(/\/+$/, "") || "";
  const pathRoute = window.location.pathname.replace(/\/+$/, "") || "/";
  return hashRoute || pathRoute;
}

function rememberOAuthReturnRoute(route) {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  window.sessionStorage.setItem(oauthReturnRouteStorageKey, route);
}

function consumeOAuthReturnRoute() {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  const route = window.sessionStorage.getItem(oauthReturnRouteStorageKey);
  if (route) {
    window.sessionStorage.removeItem(oauthReturnRouteStorageKey);
  }
  return route;
}

function applyRoute(route) {
  if (typeof window === "undefined" || !route) {
    return;
  }
  const normalizedRoute = route === "/" ? "/" : route.replace(/\/+$/, "");
  const nextHash = normalizedRoute === "/" ? "#/" : `#${normalizedRoute}`;
  if (window.location.hash !== nextHash) {
    window.location.hash = nextHash;
  }
}

function describeFetchFailure(error, fallback) {
  if (error instanceof TypeError && /failed to fetch/i.test(error.message)) {
    return `${fallback} Verify that the hosted API URL is reachable from the browser and that CORS is allowing this origin.`;
  }

  return error instanceof Error ? error.message : fallback;
}

function classifyStatusTone(message, { ready = false, available = true } = {}) {
  if (ready) {
    return "good";
  }

  if (!available) {
    return "bad";
  }

  const normalizedMessage = String(message || "").toLowerCase();

  if (
    normalizedMessage.includes("failed")
    || normalizedMessage.includes("could not reach")
    || normalizedMessage.includes("set vite_api_base_url")
    || normalizedMessage.includes("not signed in")
  ) {
    return "bad";
  }

  return "warn";
}

function StatusModal({ overallTone, statusItems, onClose, onRetryHostedConnection }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card status-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="status-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="status-modal-title">Connection Health</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <div className="status-overview-strip">
          <span className={`status-dot large ${overallTone}`} aria-hidden="true" />
          <div>
            <strong>Overall status</strong>
            <p className="status-note">
              {overallTone === "good"
                ? "All hosted checks are healthy."
                : overallTone === "bad"
                  ? "All hosted checks are failing."
                  : "Hosted checks are mixed or partially degraded."}
            </p>
          </div>
        </div>

        <dl className="status-list">
          {statusItems.map((item) => (
            <div key={item.label} className="status-list-item">
              <dt>
                <span className={`status-dot ${item.tone}`} aria-hidden="true" />
                {item.label}
              </dt>
              <dd>{item.message}</dd>
            </div>
          ))}
        </dl>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onRetryHostedConnection}>Retry Hosted Connection</button>
        </div>
      </section>
    </div>
  );
}

function NotificationsModal({ onClose }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card utility-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notifications-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="notifications-modal-title">Notifications</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <p className="status-note">No notifications.</p>
      </section>
    </div>
  );
}

function AccountModal({ accountOwner, accountRole, accountStatus, workspaceName, onClose, onSignOut }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card utility-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="account-modal-title">My Account</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <dl className="detail-grid compact-grid">
          <div><dt>Owner</dt><dd>{accountOwner}</dd></div>
          <div><dt>Role</dt><dd>{accountRole}</dd></div>
          <div><dt>Status</dt><dd>{accountStatus}</dd></div>
          <div><dt>Workspace</dt><dd>{workspaceName}</dd></div>
        </dl>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onSignOut}>Sign Out</button>
        </div>
      </section>
    </div>
  );
}

function SettingsModal({ onClose }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card utility-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="settings-modal-title">Settings</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <p className="status-note">No settings available.</p>
      </section>
    </div>
  );
}

function ConfirmationModal({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", tone = "danger", onCancel, onConfirm }) {
  return (
    <div className="modal-backdrop modal-backdrop-elevated" role="presentation" onClick={onCancel}>
      <section
        className="modal-card confirmation-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmation-modal-title"
        aria-describedby="confirmation-modal-message"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="confirmation-modal-title">{title}</h2>
          </div>
        </div>

        <p id="confirmation-modal-message" className="status-note">{message}</p>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onCancel}>{cancelLabel}</button>
          <button className={tone === "danger" ? "danger-button" : "primary-button"} type="button" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}

function downloadUsersCsv(users, columns) {
  const activeColumns = columns || userTableColumns;
  const rows = [
    activeColumns.map((c) => c.label),
    ...users.map((user) => activeColumns.map((c) => {
      if (c.key === "status") return user.is_active ? "Active" : "Inactive";
      return String(user[c.key] || "");
    }))
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `users_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function getUserColumnValue(user, columnKey) {
  if (columnKey === "status") {
    return user.is_active ? "Active" : "Inactive";
  }

  return String(user[columnKey] || "");
}

function buildUserFilterOptions(users, columnKey) {
  const values = [...new Set(users.map((user) => getUserColumnValue(user, columnKey)))].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));

  return values.map((value) => ({
    value,
    label: value || "(Blank)",
    path: [value || "(Blank)"],
    searchValue: value
  }));
}

function collectLeafValues(nodes) {
  return nodes.flatMap((node) => (node.children?.length ? collectLeafValues(node.children) : [node.value]));
}

function buildFilterTree(options) {
  const tree = [];

  options.forEach((option) => {
    let currentLevel = tree;
    option.path.forEach((segment, index) => {
      const isLeaf = index === option.path.length - 1;
      const nodeId = isLeaf
        ? `leaf:${option.value}`
        : `group:${option.path.slice(0, index + 1).join("/")}`;
      let node = currentLevel.find((entry) => entry.id === nodeId);

      if (!node) {
        node = {
          id: nodeId,
          label: isLeaf ? option.label : segment,
          value: isLeaf ? option.value : null,
          children: []
        };
        currentLevel.push(node);
      }

      currentLevel = node.children;
    });
  });

  return tree;
}

function mergeUsersById(existingUsers, incomingUsers) {
  const nextUsers = [...existingUsers];
  const existingIds = new Set(existingUsers.map((user) => user.id));

  incomingUsers.forEach((user) => {
    if (existingIds.has(user.id)) {
      const existingIndex = nextUsers.findIndex((candidate) => candidate.id === user.id);
      nextUsers[existingIndex] = user;
      return;
    }
    nextUsers.push(user);
  });

  return nextUsers.sort((left, right) => left.name.localeCompare(right.name, undefined, { sensitivity: "base" }));
}

function filterTreeNodes(nodes, searchText) {
  if (!searchText) {
    return nodes;
  }

  const normalizedSearch = searchText.trim().toLowerCase();

  return nodes.flatMap((node) => {
    if (!node.children.length) {
      return node.label.toLowerCase().includes(normalizedSearch) ? [node] : [];
    }

    const filteredChildren = filterTreeNodes(node.children, normalizedSearch);
    if (node.label.toLowerCase().includes(normalizedSearch) || filteredChildren.length) {
      return [{ ...node, children: filteredChildren }];
    }

    return [];
  });
}

function getNodeSelectionState(node, selectedValues) {
  if (!node.children.length) {
    return selectedValues.has(node.value) ? "checked" : "unchecked";
  }

  const descendantValues = collectLeafValues(node.children);
  const selectedCount = descendantValues.filter((value) => selectedValues.has(value)).length;

  if (!selectedCount) {
    return "unchecked";
  }

  if (selectedCount === descendantValues.length) {
    return "checked";
  }

  return "mixed";
}

function FilterTreeNode({ node, depth, selectedValues, onToggle }) {
  const selectionState = getNodeSelectionState(node, selectedValues);
  const descendantValues = node.children.length ? collectLeafValues(node.children) : [node.value];

  return (
    <div className="filter-tree-node" style={{ paddingLeft: `${depth * 16}px` }}>
      <label className="filter-tree-label">
        <input
          className="filter-tree-checkbox"
          type="checkbox"
          checked={selectionState === "checked"}
          ref={(element) => {
            if (element) {
              element.indeterminate = selectionState === "mixed";
            }
          }}
          onChange={(event) => onToggle(descendantValues, event.target.checked)}
        />
        <span>{node.label}</span>
      </label>

      {node.children.length ? (
        <div className="filter-tree-children">
          {node.children.map((child) => (
            <FilterTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedValues={selectedValues}
              onToggle={onToggle}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function UserHeaderFilterMenu({
  column,
  options,
  selectedValues,
  sortDirection,
  onSortAsc,
  onSortDesc,
  onClearSort,
  onClearFilter,
  onApplyFilter,
  onClose,
  style
}) {
  const [searchText, setSearchText] = useState("");
  const allValues = useMemo(() => options.map((option) => option.value), [options]);
  const [draftValues, setDraftValues] = useState(() => new Set(selectedValues.length ? selectedValues : allValues));

  useEffect(() => {
    setSearchText("");
    setDraftValues(new Set(selectedValues.length ? selectedValues : allValues));
  }, [allValues, selectedValues]);

  const tree = useMemo(() => buildFilterTree(options), [options]);
  const filteredTree = useMemo(() => filterTreeNodes(tree, searchText), [searchText, tree]);
  const suggestionId = `header-filter-search-${column.key}`;

  function updateDraft(values, checked) {
    setDraftValues((current) => {
      const next = new Set(current);
      values.forEach((value) => {
        if (checked) {
          next.add(value);
        } else {
          next.delete(value);
        }
      });
      return next;
    });
  }

  function applyFilter() {
    const normalizedSelection = draftValues.size === 0 || draftValues.size === allValues.length
      ? []
      : allValues.filter((value) => draftValues.has(value));
    onApplyFilter(normalizedSelection);
    onClose();
  }

  return (
    <div className="table-header-menu table-header-filter-menu" role="dialog" aria-label={`${column.label} sort and filter`} style={style ? { top: `${style.top}px`, left: `${style.left}px` } : undefined}>
      <div className="table-header-menu-actions-row">
        <button className="table-header-menu-action" type="button" onClick={onSortAsc}>Sort A to Z</button>
        <button className="table-header-menu-action" type="button" onClick={onSortDesc}>Sort Z to A</button>
      </div>

      <div className="table-header-menu-reset-row">
        <button className="table-header-menu-action muted" type="button" onClick={onClearSort} disabled={!sortDirection}>Clear Sort</button>
        <button className="table-header-menu-action muted" type="button" onClick={onClearFilter} disabled={!selectedValues.length}>Clear Filter</button>
      </div>

      <div className="table-header-menu-divider" />

      <label className="table-header-menu-label" htmlFor={`header-filter-search-${column.key}`}>
        Filter {column.label}
      </label>
      <input
        id={`header-filter-search-${column.key}`}
        className="table-header-menu-search"
        type="search"
        list={suggestionId}
        placeholder="Search values..."
        value={searchText}
        onChange={(event) => setSearchText(event.target.value)}
      />
      <datalist id={suggestionId}>
        {options.map((option) => (
          <option key={option.value || "__blank__"} value={option.searchValue || option.label} />
        ))}
      </datalist>

      <div className="table-header-menu-toolbar">
        <button className="table-header-menu-action" type="button" onClick={() => setDraftValues(new Set(allValues))}>Select All</button>
        <button className="table-header-menu-action" type="button" onClick={() => setDraftValues(new Set())}>Clear All</button>
      </div>

      <div className="table-filter-tree" role="group" aria-label={`${column.label} values`}>
        {filteredTree.length ? filteredTree.map((node) => (
          <FilterTreeNode
            key={node.id}
            node={node}
            depth={0}
            selectedValues={draftValues}
            onToggle={updateDraft}
          />
        )) : <p className="table-filter-empty">No matching values.</p>}
      </div>

      <div className="table-header-menu-footer">
        <button className="ghost-button" type="button" onClick={onClose}>Cancel</button>
        <button className="primary-button" type="button" onClick={applyFilter}>Apply Filter</button>
      </div>
    </div>
  );
}

function TableContextMenu({ position, items, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClick(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) onClose();
    }
    function handleKey(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  // Adjust position so menu doesn't overflow viewport
  const style = {
    position: "fixed",
    zIndex: 1500,
    left: Math.min(position.x, window.innerWidth - 220),
    top: Math.min(position.y, window.innerHeight - items.length * 36 - 16),
  };

  return (
    <div className="table-context-menu" ref={menuRef} style={style} role="menu">
      {items.map((item, i) =>
        item.divider
          ? <div key={i} className="context-menu-divider" role="separator" />
          : (
            <button
              key={i}
              className={`context-menu-item${item.danger ? " danger" : ""}`}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => { item.action(); onClose(); }}
            >
              {item.label}
            </button>
          )
      )}
    </div>
  );
}

function ExportModal({ filteredUsers, selectedUsers, selectedCells, allColumns, onExport, onClose }) {
  const hasSelection = selectedUsers.length > 0;
  const hasCellSelection = selectedCells.size > 0;
  const [scope, setScope] = useState(hasSelection ? "selected" : "filtered");
  const [enabledColumns, setEnabledColumns] = useState(() => new Set(allColumns.map((c) => c.key)));

  const scopeOptions = [
    { value: "filtered", label: `All shown (${filteredUsers.length})` },
    ...(hasSelection ? [{ value: "selected", label: `Selected rows (${selectedUsers.length})` }] : []),
  ];

  const dataUsers = scope === "selected" ? selectedUsers : filteredUsers;
  const activeColumns = allColumns.filter((c) => enabledColumns.has(c.key));
  const previewRows = dataUsers.slice(0, 5);

  function toggleColumn(key) {
    setEnabledColumns((current) => {
      const next = new Set(current);
      if (next.has(key)) { if (next.size > 1) next.delete(key); } else next.add(key);
      return next;
    });
  }

  return (
    <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="modal-card export-modal" aria-modal="true" role="dialog">
        <header className="modal-header">
          <h3>Export CSV</h3>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </header>

        <div className="export-modal-body">
          <div className="export-section">
            <label className="export-label">Data scope</label>
            <div className="export-scope-options">
              {scopeOptions.map((opt) => (
                <label key={opt.value} className="export-radio-label">
                  <input type="radio" name="export-scope" value={opt.value} checked={scope === opt.value} onChange={() => setScope(opt.value)} />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          <div className="export-section">
            <label className="export-label">Columns</label>
            <div className="export-column-options">
              {allColumns.map((col) => (
                <label key={col.key} className="export-checkbox-label">
                  <input type="checkbox" checked={enabledColumns.has(col.key)} onChange={() => toggleColumn(col.key)} />
                  {col.label}
                </label>
              ))}
            </div>
          </div>

          <div className="export-section">
            <label className="export-label">Preview ({dataUsers.length} row{dataUsers.length !== 1 ? "s" : ""})</label>
            <div className="export-preview-scroll">
              <table className="export-preview-table">
                <thead>
                  <tr>{activeColumns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
                </thead>
                <tbody>
                  {previewRows.map((user, i) => (
                    <tr key={i}>
                      {activeColumns.map((c) => (
                        <td key={c.key}>{c.key === "status" ? (user.is_active ? "Active" : "Inactive") : String(user[c.key] || "")}</td>
                      ))}
                    </tr>
                  ))}
                  {dataUsers.length > 5 ? <tr><td colSpan={activeColumns.length} className="export-preview-more">... and {dataUsers.length - 5} more</td></tr> : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="modal-actions modal-actions-end">
          <button className="primary-button" type="button" onClick={() => { onExport(dataUsers, activeColumns); onClose(); }}>
            Export {dataUsers.length} Row{dataUsers.length !== 1 ? "s" : ""}
          </button>
        </div>
      </section>
    </div>
  );
}

function UserModal({
  mode,
  user,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  suggestions
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add User" : mode === "edit" ? "Edit User" : "View User";
  const nameInvalid = !form.name.trim();
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && user) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card user-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="user-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="user-modal-title">View User</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{user.name}</dd></div>
              <div><dt>Email</dt><dd>{user.email || "-"}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={user.is_active ? "status-chip active" : "status-chip inactive"}>
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{user.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit User</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card user-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="user-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="user-name-input">Name</label>
          <div>
            <input
              id="user-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="user-name-suggestions"
              placeholder="Required"
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="user-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {nameInvalid ? <p className="field-error">Name is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="user-email-input">Email</label>
          <div>
            <input
              id="user-email-input"
              className="text-input"
              type="email"
              list="user-email-suggestions"
              placeholder="Optional"
              value={form.email}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            />
            <datalist id="user-email-suggestions">
              {suggestions.emails.map((email) => (
                <option key={email} value={email} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="user-active-input">Active</label>
          <label className="toggle-row" htmlFor="user-active-input">
            <input
              id="user-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="user-notes-input">Notes</label>
          <textarea
            id="user-notes-input"
            className="notes-input"
            placeholder="Optional"
            rows={5}
            value={form.notes}
            readOnly={readOnly}
            onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}

        <div className="modal-actions modal-actions-end">
          <button className="primary-button" type="button" onClick={onSubmit} disabled={nameInvalid}>
            Save User
          </button>
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const usersScrollGateRef = useRef({ armed: false, lastScrollTop: 0 });
  const usersPagingRequestRef = useRef(false);
  const usersTableViewportRef = useRef(null);
  const userNavCursorRef = useRef(null);
  const [currentRoute, setCurrentRoute] = useState(() => readCurrentRoute());
  const isMigrationPage = currentRoute === "/migration";
  const [railCollapsed, setRailCollapsed] = useState(false);
  const [setupNavOpen, setSetupNavOpen] = useState(false);
  const [notificationsModalOpen, setNotificationsModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [sessionEmail, setSessionEmail] = useState(null);
  const [authMessage, setAuthMessage] = useState(
    supabaseConfigured ? "Sign in with Google to activate the hosted Sezzions workspace." : supabaseConfigError
  );
  const [apiStatus, setApiStatus] = useState("Protected API handshake will run after Google sign-in.");
  const [hostedStatus, setHostedStatus] = useState(
    "Hosted account bootstrap will run after the protected API handshake."
  );
  const [importPlanStatus, setImportPlanStatus] = useState(
    "Hosted import planning will run after workspace bootstrap."
  );
  const [hostedSummary, setHostedSummary] = useState(null);
  const [importPlanSummary, setImportPlanSummary] = useState(null);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(
    "Upload a SQLite database to inspect it for hosted migration planning."
  );
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [setupTab, setSetupTab] = useState("users");
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
  const [statusModalOpen, setStatusModalOpen] = useState(false);
  const [userForm, setUserForm] = useState(initialUserForm);
  const [userFormBaseline, setUserFormBaseline] = useState(initialUserForm);
  const [userSubmitError, setUserSubmitError] = useState(null);
  const [confirmationState, setConfirmationState] = useState(null);
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || null;
  const supabaseApiKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || null;
  const hasAuthenticatedSession = Boolean(sessionEmail);
  const hostedWorkspaceReady = Boolean(hostedSummary);
  const workspaceName = hostedSummary?.workspace?.name || (sessionEmail ? `${sessionEmail} Workspace` : "Hosted Workspace");
  const accountOwner = hostedSummary?.account?.owner_email || sessionEmail || "Not signed in";
  const accountRole = hostedSummary?.account?.role || "Pending bootstrap";
  const accountStatus = hostedSummary?.account?.status || "Pending bootstrap";

  const statusItems = useMemo(() => {
    const authenticationTone = sessionEmail ? "good" : "bad";
    const apiTone = classifyStatusTone(apiStatus, { ready: apiStatus.toLowerCase().includes("ready for"), available: Boolean(apiBaseUrl) });
    const bootstrapTone = classifyStatusTone(hostedStatus, { ready: hostedWorkspaceReady, available: Boolean(apiBaseUrl) });
    const importTone = classifyStatusTone(importPlanStatus, { ready: Boolean(importPlanSummary), available: Boolean(apiBaseUrl) });

    return [
      { label: "Authentication", message: authMessage, tone: authenticationTone },
      { label: "API Handshake", message: apiStatus, tone: apiTone },
      { label: "Hosted Bootstrap", message: hostedStatus, tone: bootstrapTone },
      { label: "Import Planning", message: importPlanStatus, tone: importTone }
    ];
  }, [authMessage, apiBaseUrl, apiStatus, hostedStatus, hostedWorkspaceReady, importPlanStatus, importPlanSummary, sessionEmail]);

  const overallStatusTone = useMemo(() => {
    const failures = statusItems.filter((item) => item.tone === "bad").length;
    const allGood = statusItems.every((item) => item.tone === "good");

    if (allGood) {
      return "good";
    }

    if (failures === statusItems.length) {
      return "bad";
    }

    return "warn";
  }, [statusItems]);

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

  useEffect(() => {
    const anyModalOpen = Boolean(
      openUserHeaderMenu
      ||
      notificationsModalOpen
      || statusModalOpen
      || accountModalOpen
      || settingsModalOpen
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

      if (statusModalOpen) {
        setStatusModalOpen(false);
        return;
      }

      if (settingsModalOpen) {
        setSettingsModalOpen(false);
        return;
      }

      if (accountModalOpen) {
        setAccountModalOpen(false);
        return;
      }

      if (exportModalOpen) {
        setExportModalOpen(false);
        return;
      }

      if (notificationsModalOpen) {
        setNotificationsModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [accountModalOpen, confirmationState, exportModalOpen, notificationsModalOpen, openUserHeaderMenu, settingsModalOpen, statusModalOpen, userModalMode, userModalDirty]);

  useEffect(() => {
    if (setupTab !== "users") return undefined;

    function handleArrowNav(event) {
      // Ctrl+C: copy selected cells as TSV
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
        // Toggle: if all filtered are already selected, deselect all
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

      // Ctrl+F: focus search field
      if (event.key === "f" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        if (confirmationState || userModalMode || openUserHeaderMenu) return;
        event.preventDefault();
        const searchInput = document.getElementById("users-search-input");
        if (searchInput) searchInput.focus();
        return;
      }

      // Escape: clear search field if focused and has content, otherwise blur
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
  }, [confirmationState, filteredUsers, openUserHeaderMenu, selectedCells, selectedUserIds, selectionAnchorUserId, setupTab, userModalMode]);

  const userSuggestions = useMemo(() => ({
    names: [...new Set(users.map((user) => user.name).filter(Boolean))],
    emails: [...new Set(users.map((user) => user.email).filter(Boolean))]
  }), [users]);

  function authHeaders(accessToken) {
    return {
      Authorization: `Bearer ${accessToken}`,
      ...(supabaseApiKey ? { apikey: supabaseApiKey } : {})
    };
  }

  async function getAccessToken() {
    if (!supabase?.auth) {
      return null;
    }

    const { data, error } = await supabase.auth.getSession();
    if (error) {
      throw error;
    }

    return data.session?.access_token || null;
  }

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

  function handleUserRowSelection(event, userId) {
    event.preventDefault();
    // Clear cell/column selection when doing row selection
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
    if (!event.altKey) return false; // only Alt/Option+click enters cell mode
    event.stopPropagation();
    event.preventDefault();

    // Clear row selection when entering cell mode
    setSelectedUserIds([]);
    setSelectionAnchorUserId(null);

    const cellId = `${userId}:${columnKey}`;
    const columnKeys = userTableColumns.map((c) => c.key);

    if (event.shiftKey && cellAnchorRef.current) {
      // Rectangular range from anchor to this cell
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
      // Alt+click: toggle individual cell (Ctrl+Alt adds to selection)
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

  function handleTableContextMenu(event, user) {
    event.preventDefault();
    setContextMenu(null);

    // Detect which cell column was right-clicked
    let td = event.target;
    while (td && td.tagName !== "TD") td = td.parentElement;
    const clickedColumnKey = td?.dataset?.col || null;

    const items = [];
    const isRowSelected = selectedUserIds.includes(user.id);
    const hasCellSelection = selectedCells.size > 0;
    const hasRowSelection = selectedUserIds.length > 0;

    // 1. Copy the specific clicked cell value
    if (clickedColumnKey) {
      const cellValue = getCellDisplayValue(user, clickedColumnKey);
      const truncated = cellValue.length > 30 ? `${cellValue.slice(0, 27)}…` : cellValue;
      items.push({ label: `Copy "${truncated}"`, action: () => { navigator.clipboard.writeText(cellValue).catch(() => {}); }});
    }

    // 2. Copy selected cells as TSV (if any)
    if (hasCellSelection) {
      items.push({ label: `Copy ${selectedCells.size} cell${selectedCells.size > 1 ? "s" : ""}`, action: copyCellsAsTSV });
    }

    // 3. Copy selected rows as TSV (if any)
    if (hasRowSelection) {
      const count = selectedUserIds.length;
      items.push({ label: count > 1 ? `Copy ${count} rows` : "Copy row", action: copyRowsAsTSV });
    }

    items.push({ divider: true });

    // Row actions
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

  function getComputedColumnWidths() {
    // Read current rendered widths from the header grid cells
    const header = headerRef.current;
    if (!header) return null;
    const cells = header.querySelectorAll(".users-table-header-cell");
    // First cell is checkbox — skip it, return widths for data columns only
    const widths = [];
    for (let i = 1; i < cells.length; i++) {
      widths.push(cells[i].getBoundingClientRect().width);
    }
    return widths.length === userTableColumns.length ? widths : null;
  }

  function getColumnMinWidth(colIndex) {
    // Measure header label text + filter button + padding to determine smart minimum
    const header = headerRef.current;
    if (!header) return 80;
    const cells = header.querySelectorAll(".users-table-header-cell");
    const cell = cells[colIndex + 1]; // +1 for checkbox column
    if (!cell) return 80;
    const label = cell.querySelector(".users-table-header-label");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = "0.71rem -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    const labelW = label ? ctx.measureText(label.textContent || "").width : 30;
    // label text + sort/filter button (~28px) + cell padding (2×10) + gap (4) + resize handle (5)
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

    // Pre-compute per-column minimums
    const minWidths = widths.map((_, i) => getColumnMinWidth(i));

    function ensureViewportFill(w) {
      const viewport = usersTableViewportRef.current;
      if (!viewport) return w;
      const available = viewport.clientWidth - 36; // subtract checkbox column
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

    // Use a canvas context to measure text width directly (avoids DOM layout constraints)
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    // Match the table cell font
    ctx.font = "0.84rem -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";

    let maxWidth = 60;

    // Measure header label text
    const header = headerRef.current;
    if (header) {
      const headerCells = header.querySelectorAll(".users-table-header-cell");
      if (headerCells[colIndex + 1]) {
        const label = headerCells[colIndex + 1].querySelector(".users-table-header-label");
        if (label) {
          const textWidth = ctx.measureText(label.textContent || "").width;
          maxWidth = Math.max(maxWidth, textWidth + 52); // +padding+sort button
        }
      }
    }

    // Measure each row's cell content
    for (const user of filteredUsers) {
      const value = getCellDisplayValue(user, columnKey);
      const textWidth = ctx.measureText(value).width;
      maxWidth = Math.max(maxWidth, textWidth + 24); // +cell padding
    }

    widths[colIndex] = Math.min(Math.ceil(maxWidth), 600); // cap at reasonable max

    // Ensure columns fill viewport
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
    if (setupTab !== "users" || !usersHasMore || usersFiltersActive || usersLoadingInitial || usersLoadingMore || !hasAuthenticatedSession) {
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
  }, [hasAuthenticatedSession, setupTab, usersFiltersActive, usersHasMore, usersLoadingInitial, usersLoadingMore, usersNextOffset]);

  function openUserHeaderOptions(event, columnKey) {
    const buttonRect = event.currentTarget.getBoundingClientRect();
    const menuWidth = 296;
    const left = Math.max(16, Math.min(buttonRect.right - menuWidth, window.innerWidth - menuWidth - 16));
    const top = Math.min(buttonRect.bottom + 8, window.innerHeight - 24);

    setOpenUserHeaderMenu((current) => current?.key === columnKey ? null : { key: columnKey, left, top });
  }

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

      setUsers((current) => {
        if (method === "POST") {
          return mergeUsersById(current, [data]);
        }

        return mergeUsersById(current, [data]);
      });
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

  async function handleMigrationUpload() {
    if (!selectedUploadFile) {
      setUploadSummary(null);
      setUploadStatus("Choose a SQLite database file before uploading.");
      return;
    }

    try {
      const accessToken = await getAccessToken();
      if (!accessToken) {
        setUploadSummary(null);
        setUploadStatus("Google sign-in is required before uploading a SQLite file.");
        return;
      }

      if (!apiBaseUrl) {
        setUploadSummary(null);
        setUploadStatus("Set VITE_API_BASE_URL to enable SQLite upload planning.");
        return;
      }

      setUploadStatus("Uploading SQLite file for hosted migration planning...");
      const formData = new FormData();
      formData.append("sqlite_db", selectedUploadFile);

      const response = await fetch(`${apiBaseUrl}/v1/workspace/import-upload-plan`, {
        method: "POST",
        headers: authHeaders(accessToken),
        body: formData
      });
      const payload = await response.json();

      if (!response.ok) {
        setUploadSummary(null);
        setUploadStatus(payload.detail || `SQLite upload planning failed (${response.status}).`);
        return;
      }

      setUploadSummary(payload);
      setUploadStatus(payload.detail || "Uploaded SQLite inventory is ready.");
    } catch (error) {
      setUploadSummary(null);
      setUploadStatus(describeFetchFailure(error, "SQLite upload planning failed."));
    }
  }

  async function syncWorkspaceImportPlan(nextSession) {
    if (!nextSession?.access_token) {
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      return;
    }

    if (!apiBaseUrl) {
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      return;
    }

    setImportPlanStatus("Loading hosted workspace import planning status...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/import-plan`, {
        headers: authHeaders(nextSession.access_token)
      });

      const data = await response.json();
      if (!response.ok) {
        setImportPlanSummary(null);
        setImportPlanStatus(data.detail || `Hosted import planning failed (${response.status}).`);
        return;
      }

      setImportPlanSummary(data);
      setImportPlanStatus(data.detail || "Hosted import planning is ready.");
    } catch (error) {
      setImportPlanSummary(null);
      setImportPlanStatus(describeFetchFailure(error, "Hosted import planning failed."));
    }
  }

  async function syncHostedBootstrap(nextSession) {
    if (!nextSession?.access_token) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setUsersStatus("Sign in to load hosted users.");
      clearUserSelection();
      return;
    }

    if (!apiBaseUrl) {
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      clearUserSelection();
      return;
    }

    setHostedStatus("Bootstrapping the hosted Sezzions account workspace...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/account/bootstrap`, {
        method: "POST",
        headers: authHeaders(nextSession.access_token)
      });
      const data = await response.json();

      if (!response.ok) {
        setHostedSummary(null);
        setImportPlanSummary(null);
        setUsers([]);
        setUsersTotalCount(0);
        setUsersNextOffset(0);
        setUsersHasMore(false);
        setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
        setUsersStatus("Hosted users will load after workspace bootstrap.");
        clearUserSelection();
        setHostedStatus(data.detail || `Hosted account bootstrap failed (${response.status}).`);
        return;
      }

      setHostedSummary(data);
      setHostedStatus(
        data.created_account || data.created_workspace
          ? "Hosted account workspace created and ready."
          : "Hosted account workspace ready."
      );

      await Promise.all([
        syncWorkspaceImportPlan(nextSession),
        loadUsers(nextSession.access_token)
      ]);
    } catch (error) {
      setHostedSummary(null);
      setImportPlanSummary(null);
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsersStatus("Hosted users will load after workspace bootstrap.");
      clearUserSelection();
      setHostedStatus(describeFetchFailure(error, "Hosted account bootstrap could not reach the hosted API."));
    }
  }

  async function syncProtectedApi(nextSession) {
    if (!nextSession?.access_token) {
      setApiStatus("Protected API handshake will run after Google sign-in.");
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setUsersStatus("Sign in to load hosted users.");
      clearUserSelection();
      return;
    }

    if (!apiBaseUrl) {
      setApiStatus("Set VITE_API_BASE_URL to enable the protected API handshake.");
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      clearUserSelection();
      return;
    }

    setApiStatus("Calling the protected Render API with the Supabase session token...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/session`, {
        headers: authHeaders(nextSession.access_token)
      });
      const data = await response.json();

      if (!response.ok) {
        setApiStatus(data.detail || `Protected API handshake failed (${response.status}).`);
        return;
      }

      setApiStatus(`Protected API handshake ready for ${data.email || data.user_id}.`);
      await syncHostedBootstrap(nextSession);
    } catch (error) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersTotalCount(0);
      setUsersNextOffset(0);
      setUsersHasMore(false);
      setUsersStatus("Sign in to load hosted users.");
      clearUserSelection();
      setApiStatus(describeFetchFailure(error, "Protected API handshake could not reach the hosted API."));
    }
  }

  async function handleRetryHostedConnection() {
    if (!supabase?.auth) {
      setAuthMessage(supabaseConfigError);
      return;
    }

    try {
      const { data, error } = await supabase.auth.getSession();
      if (error) {
        setApiStatus(error.message);
        return;
      }

      await syncProtectedApi(data.session || null);
    } catch (error) {
      setApiStatus(describeFetchFailure(error, "Protected API handshake could not reach the hosted API."));
    }
  }

  useEffect(() => {
    function syncRoute() {
      setCurrentRoute(readCurrentRoute());
    }

    window.addEventListener("hashchange", syncRoute);
    window.addEventListener("popstate", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
      window.removeEventListener("popstate", syncRoute);
    };
  }, []);

  useEffect(() => {
    if (!supabase) {
      return undefined;
    }

    let cancelled = false;

    supabase.auth.getSession().then(({ data, error }) => {
      if (cancelled) {
        return;
      }

      if (error) {
        setAuthMessage(error.message);
        return;
      }

      const email = data.session?.user?.email || null;
      if (data.session?.access_token) {
        const pendingRoute = consumeOAuthReturnRoute();
        if (pendingRoute && pendingRoute !== readCurrentRoute()) {
          applyRoute(pendingRoute);
        }
      }
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. Hosted Sezzions is ready."
          : "Sign in with Google to activate the hosted Sezzions workspace."
      );
      void syncProtectedApi(data.session || null);
    });

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      const email = nextSession?.user?.email || null;
      if (nextSession?.access_token) {
        const pendingRoute = consumeOAuthReturnRoute();
        if (pendingRoute && pendingRoute !== readCurrentRoute()) {
          applyRoute(pendingRoute);
        }
      }
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. Hosted Sezzions is ready."
          : "Sign in with Google to activate the hosted Sezzions workspace."
      );
      void syncProtectedApi(nextSession || null);
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, []);

  async function handleGoogleSignIn() {
    if (!supabase) {
      setAuthMessage(supabaseConfigError);
      return;
    }

    rememberOAuthReturnRoute(readCurrentRoute());

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin
      }
    });

    if (error) {
      setAuthMessage(error.message);
    }
  }

  async function handleSignOut() {
    if (!supabase) {
      return;
    }

    const { error } = await supabase.auth.signOut();
    if (error) {
      setAuthMessage(error.message);
      return;
    }

    setSessionEmail(null);
    setHostedSummary(null);
    setImportPlanSummary(null);
    setUploadSummary(null);
    setSelectedUploadFile(null);
    setUsers([]);
    setUsersTotalCount(0);
    setUsersNextOffset(0);
    setUsersHasMore(false);
    clearUserSelection();
    setUserModalMode(null);
    setNotificationsModalOpen(false);
    setSettingsModalOpen(false);
    setAccountModalOpen(false);
    setStatusModalOpen(false);
    setUserForm(initialUserForm);
    setAuthMessage("Signed out. Sign in with Google to reactivate the hosted workspace.");
    setApiStatus("Protected API handshake will run after Google sign-in.");
    setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
    setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
    setUploadStatus("Upload a SQLite database to inspect it for hosted migration planning.");
    setUsersStatus("Sign in to load hosted users.");
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

  if (isMigrationPage) {
    return (
      <div className="migration-shell">
        <header className="migration-hero">
          <div>
            <p className="section-kicker">Sezzions Migration</p>
            <h1>Temporary SQLite Upload Planning</h1>
            <p className="shell-copy">
              Use this authenticated bridge to inspect a local Sezzions SQLite database for hosted migration planning.
            </p>
          </div>
          <div className="migration-actions">
            <a className="ghost-button" href="/#/">Back to Hosted App</a>
            {sessionEmail ? (
              <button className="ghost-button" type="button" onClick={handleSignOut}>Sign Out</button>
            ) : (
              <button className="primary-button" type="button" onClick={handleGoogleSignIn}>Continue With Google</button>
            )}
          </div>
        </header>

        <main className="migration-grid">
          <section className="workspace-panel">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Upload bridge</p>
                <h2>Inspect a local SQLite database</h2>
              </div>
            </div>
            <label className="field-label-left" htmlFor="sqlite-upload-input">SQLite database file</label>
            <input
              id="sqlite-upload-input"
              className="text-input"
              type="file"
              accept=".db,.sqlite,.sqlite3,application/octet-stream"
              onChange={(event) => setSelectedUploadFile(event.target.files?.[0] || null)}
            />
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={handleMigrationUpload}>Upload SQLite For Planning</button>
            </div>
            <p className="status-note">{uploadStatus}</p>
          </section>

          <section className="workspace-panel">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Inventory</p>
                <h2>Uploaded SQLite inspection</h2>
              </div>
            </div>
            {uploadSummary ? (
              <dl className="detail-grid compact-grid">
                <div><dt>Uploaded file</dt><dd>{uploadSummary.uploaded_filename}</dd></div>
                <div><dt>Status</dt><dd>{uploadSummary.status}</dd></div>
                <div><dt>Active users discovered</dt><dd>{uploadSummary.inventory?.active_user_names?.join(", ") || "None"}</dd></div>
                <div><dt>Sites discovered</dt><dd>{uploadSummary.inventory?.site_names?.join(", ") || "None"}</dd></div>
              </dl>
            ) : (
              <p className="status-note">Upload a SQLite file to inspect it here.</p>
            )}
          </section>
        </main>
      </div>
    );
  }

  if (!sessionEmail) {
    return (
      <div className="marketing-shell">
        <header className="marketing-hero">
          <div className="marketing-copy">
            <p className="section-kicker">Sezzions Hosted</p>
            <h1>Sezzions for the web.</h1>
            <p className="shell-copy">
              Sign in with Google to open your workspace.
            </p>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={handleGoogleSignIn}>Continue With Google</button>
              <a className="ghost-button" href="/#/migration">Open Migration Upload</a>
            </div>
          </div>

          <aside className="workspace-panel auth-panel">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Account</p>
                <h2>{sessionEmail || "Sign in"}</h2>
              </div>
            </div>
            <dl className="detail-grid compact-grid">
              <div><dt>Authentication</dt><dd>{authMessage}</dd></div>
              <div><dt>API handshake</dt><dd>{apiStatus}</dd></div>
              <div><dt>Hosted bootstrap</dt><dd>{hostedStatus}</dd></div>
              <div><dt>Import planning</dt><dd>{importPlanStatus}</dd></div>
            </dl>
          </aside>
        </header>
      </div>
    );
  }

  return (
    <div className={railCollapsed ? "app-shell rail-collapsed" : "app-shell"}>
      <header className="app-topbar-shell" aria-label="Workspace header">
        <div className="app-topbar-left">
          <button
            className={railCollapsed ? "rail-side-toggle collapsed" : "rail-side-toggle"}
            type="button"
            aria-label={railCollapsed ? "Expand navigation" : "Collapse navigation"}
            title={railCollapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={() => setRailCollapsed((current) => !current)}
          >
            <span className="rail-side-toggle-glyph" aria-hidden="true"><Icon name="menu" className="app-icon" /></span>
          </button>
          <h1 className="app-shell-title"><span className="app-shell-brand">Sezzions</span><span className="app-shell-divider"> - </span><span className="app-shell-subtitle">Sweepstakes Session Tracker</span></h1>
        </div>

        <div className="topbar-actions utility-button-row">
          <button
            className={notificationsModalOpen ? "header-utility-button notifications-utility-button active" : "header-utility-button notifications-utility-button"}
            type="button"
            aria-label="Open notifications"
            title="Notifications"
            onClick={() => setNotificationsModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="notifications" className="app-icon" /></span>
          </button>
          <button
            className={accountModalOpen ? "header-utility-button account-utility-button active" : "header-utility-button account-utility-button"}
            type="button"
            aria-label="Open my account"
            title={accountOwner}
            onClick={() => setAccountModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="account" className="app-icon" /></span>
          </button>
          <button
            className={settingsModalOpen ? "header-utility-button settings-utility-button active" : "header-utility-button settings-utility-button"}
            type="button"
            aria-label="Open settings"
            title="Settings"
            onClick={() => setSettingsModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="settings" className="app-icon" /></span>
          </button>
          <button
            className={statusModalOpen ? "header-utility-button status-utility-button active" : "header-utility-button status-utility-button"}
            type="button"
            onClick={() => setStatusModalOpen(true)}
            aria-label="Open hosted status"
            title="Hosted Status"
          >
            <span className={`status-dot ${overallStatusTone}`} aria-hidden="true" />
          </button>
        </div>
      </header>

      <aside className={railCollapsed ? "workspace-rail collapsed" : "workspace-rail"}>
        <div className="rail-section-block">
          <button
            className="rail-group-toggle"
            type="button"
            aria-expanded={!railCollapsed && setupNavOpen}
            aria-label={railCollapsed ? "Expand setup navigation" : "Toggle setup navigation"}
            title="Setup"
            onClick={() => {
              if (railCollapsed) {
                setRailCollapsed(false);
                return;
              }
              setSetupNavOpen((current) => !current);
            }}
          >
            <span className="rail-nav-main">
              <span className="rail-item-icon" aria-hidden="true"><Icon name="setup" className="app-icon" /></span>
              {!railCollapsed ? <span className="rail-group-label">Setup</span> : null}
            </span>
            {!railCollapsed ? <span className="rail-group-icon" aria-hidden="true"><Icon name={setupNavOpen ? "chevronDown" : "chevronRight"} className="app-icon rail-chevron-icon" /></span> : null}
          </button>

          {!railCollapsed && setupNavOpen ? (
            <nav className="rail-nav rail-subnav" aria-label="Setup navigation">
              {setupTabs.map((tab) => (
                <button
                  key={tab.key}
                  className={tab.key === setupTab ? "rail-nav-button rail-subnav-button active" : "rail-nav-button rail-subnav-button"}
                  type="button"
                  aria-current={tab.key === setupTab ? "page" : undefined}
                  aria-label={tab.label}
                  title={tab.label}
                  disabled={!tab.enabled}
                  onClick={() => setSetupTab(tab.key)}
                >
                  <span className="rail-nav-main">
                    <span className="rail-item-icon" aria-hidden="true"><Icon name={tab.icon} className="app-icon" /></span>
                    <span className="rail-nav-label">{tab.label}</span>
                  </span>
                  {!tab.enabled ? <span className="rail-nav-tag">Soon</span> : null}
                </button>
              ))}
            </nav>
          ) : null}
        </div>

        <div className="rail-footer-group">
          <div className="rail-footer">
            {railCollapsed ? (
              <a className="header-utility-button rail-footer-icon" href="/#/migration" aria-label="Open migration upload" title="Migration Upload">
                <span aria-hidden="true"><Icon name="upload" className="app-icon" /></span>
              </a>
            ) : (
              <a className="ghost-button full-width" href="/#/migration">Migration Upload</a>
            )}
          </div>
        </div>
      </aside>

      <main className="workspace-shell">
        {setupTab === "users" ? (
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
                        // Clear row selection when selecting columns
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

                        // Populate selectedCells with all cells in selected columns
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
              </div>{/* end .users-table-scroll-area */}

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
                </div>{/* end .users-summary-rail-bottom */}

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
            </div>{/* end .users-surface */}
          </section>
      ) : null}
      </main>

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

      {notificationsModalOpen ? (
        <NotificationsModal onClose={() => setNotificationsModalOpen(false)} />
      ) : null}

      {statusModalOpen ? (
        <StatusModal
          overallTone={overallStatusTone}
          statusItems={statusItems}
          onClose={() => setStatusModalOpen(false)}
          onRetryHostedConnection={async () => {
            await handleRetryHostedConnection();
          }}
        />
      ) : null}

      {accountModalOpen ? (
        <AccountModal
          accountOwner={accountOwner}
          accountRole={accountRole}
          accountStatus={accountStatus}
          workspaceName={workspaceName}
          onClose={() => setAccountModalOpen(false)}
          onSignOut={handleSignOut}
        />
      ) : null}

      {settingsModalOpen ? (
        <SettingsModal onClose={() => setSettingsModalOpen(false)} />
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
    </div>
  );
}