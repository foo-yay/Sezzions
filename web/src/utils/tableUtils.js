/**
 * Shared table utility functions used across all entity tabs.
 *
 * Entity-specific logic (column value formatting, form normalization, etc.)
 * lives in each entity's own utils file. Only structurally identical functions
 * that are copy-pasted across entities belong here.
 */

/** Returns true if the given element is a focused text-entry field. */
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

/** Parse a display string into a numeric value, or null if not numeric. */
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

/** Compute aggregate stats for an array of cell display values. */
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

/**
 * Merge incoming items into an existing array by ID, preserving sort order by name.
 * Updates existing items in-place, appends new items, then re-sorts.
 */
export function mergeItemsById(existingItems, incomingItems) {
  const nextItems = [...existingItems];
  const existingIds = new Set(existingItems.map((item) => item.id));

  incomingItems.forEach((item) => {
    if (existingIds.has(item.id)) {
      const existingIndex = nextItems.findIndex((candidate) => candidate.id === item.id);
      nextItems[existingIndex] = item;
      return;
    }
    nextItems.push(item);
  });

  return nextItems.sort((left, right) => (left.name || "").localeCompare(right.name || "", undefined, { sensitivity: "base" }));
}

/**
 * Build filter dropdown options for a given column from the item data.
 * Returns sorted unique values formatted as filter option objects.
 */
export function buildGenericFilterOptions(items, columnKey, getColumnValue) {
  const values = [...new Set(items.map((item) => getColumnValue(item, columnKey)))].sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" }));

  return values.map((value) => ({
    value,
    label: value || "(Blank)",
    path: [value || "(Blank)"],
    searchValue: value
  }));
}

/** Download items as CSV using the provided columns and cell display function. */
export function downloadCsv(items, columns, getCellDisplayValue, filenamePrefix) {
  const rows = [
    columns.map((c) => c.label),
    ...items.map((item) => columns.map((c) => getCellDisplayValue(item, c.key)))
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filenamePrefix}_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

/** Collect all leaf values from a filter tree. */
export function collectLeafValues(nodes) {
  return nodes.flatMap((node) => (node.children?.length ? collectLeafValues(node.children) : [node.value]));
}

/** Build a hierarchical filter tree from flat filter options. */
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

/** Filter tree nodes by search text, keeping matching branches. */
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

/** Determine checkbox state for a filter tree node. */
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
