import { useState } from "react";

import { userTableColumns } from "./usersConstants";

export default function ExportModal({ filteredUsers, selectedUsers, selectedCells, allColumns, onExport, onClose }) {
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
