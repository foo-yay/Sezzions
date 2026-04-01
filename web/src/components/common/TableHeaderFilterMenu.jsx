import { useEffect, useMemo, useState } from "react";

import { buildFilterTree, filterTreeNodes } from "../../utils/tableUtils";
import FilterTreeNode from "./FilterTreeNode";

export default function TableHeaderFilterMenu({
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
