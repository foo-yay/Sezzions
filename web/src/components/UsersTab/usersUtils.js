import { userTableColumns } from "./usersConstants";

export function normalizeUserForm(form) {
  return {
    name: form.name || "",
    email: form.email || "",
    notes: form.notes || "",
    is_active: Boolean(form.is_active)
  };
}

export function isTextEntryElement(element) {
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

export function parseNumericValue(text) {
  if (!text || typeof text !== "string") return null;
  const trimmed = text.trim();
  if (!trimmed || ["n/a", "na", "-", "\u2014", "\u2013"].includes(trimmed.toLowerCase())) return null;
  let cleaned = trimmed.replace(/[$\u20ac\u00a3\u00a5,\s]/g, "");
  if (cleaned.startsWith("(") && cleaned.endsWith(")")) cleaned = "-" + cleaned.slice(1, -1);
  if (cleaned.endsWith("%")) cleaned = cleaned.slice(0, -1);
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

export function computeCellStats(values) {
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

export function getCellDisplayValue(user, columnKey) {
  if (columnKey === "status") return user.is_active ? "Active" : "Inactive";
  return String(user[columnKey] || "");
}

export function downloadUsersCsv(users, columns) {
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

export function getUserColumnValue(user, columnKey) {
  if (columnKey === "status") {
    return user.is_active ? "Active" : "Inactive";
  }

  return String(user[columnKey] || "");
}

export function buildUserFilterOptions(users, columnKey) {
  const values = [...new Set(users.map((user) => getUserColumnValue(user, columnKey)))].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));

  return values.map((value) => ({
    value,
    label: value || "(Blank)",
    path: [value || "(Blank)"],
    searchValue: value
  }));
}

export function collectLeafValues(nodes) {
  return nodes.flatMap((node) => (node.children?.length ? collectLeafValues(node.children) : [node.value]));
}

export function buildFilterTree(options) {
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

export function mergeUsersById(existingUsers, incomingUsers) {
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

export function filterTreeNodes(nodes, searchText) {
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

export function getNodeSelectionState(node, selectedValues) {
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
