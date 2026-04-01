import { useState } from "react";

export default function ExportModal({ filteredItems, selectedItems, selectedCells, allColumns, getCellDisplayValue, onExport, onClose }) {
  const hasSelection = selectedItems.length > 0;
  const [scope, setScope] = useState(hasSelection ? "selected" : "filtered");
  const [enabledColumns, setEnabledColumns] = useState(() => new Set(allColumns.map((c) => c.key)));

  const scopeOptions = [
    { value: "filtered", label: `All shown (${filteredItems.length})` },
    ...(hasSelection ? [{ value: "selected", label: `Selected rows (${selectedItems.length})` }] : []),
  ];

  const dataItems = scope === "selected" ? selectedItems : filteredItems;
  const activeColumns = allColumns.filter((c) => enabledColumns.has(c.key));
  const previewRows = dataItems.slice(0, 5);

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
            <label className="export-label">Preview ({dataItems.length} row{dataItems.length !== 1 ? "s" : ""})</label>
            <div className="export-preview-scroll">
              <table className="export-preview-table">
                <thead>
                  <tr>{activeColumns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
                </thead>
                <tbody>
                  {previewRows.map((item, i) => (
                    <tr key={i}>
                      {activeColumns.map((c) => (
                        <td key={c.key}>{getCellDisplayValue ? getCellDisplayValue(item, c.key) : String(item[c.key] || "")}</td>
                      ))}
                    </tr>
                  ))}
                  {dataItems.length > 5 ? <tr><td colSpan={activeColumns.length} className="export-preview-more">... and {dataItems.length - 5} more</td></tr> : null}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="modal-actions modal-actions-end">
          <button className="primary-button" type="button" onClick={() => { onExport(dataItems, activeColumns); onClose(); }}>
            Export {dataItems.length} Row{dataItems.length !== 1 ? "s" : ""}
          </button>
        </div>
      </section>
    </div>
  );
}
