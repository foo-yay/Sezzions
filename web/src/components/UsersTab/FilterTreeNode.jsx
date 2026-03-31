import { collectLeafValues, getNodeSelectionState } from "./usersUtils";

export default function FilterTreeNode({ node, depth, selectedValues, onToggle }) {
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
