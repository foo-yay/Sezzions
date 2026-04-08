import { useState } from "react";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function MarkReceivedDialog({ count, onSave, onClose }) {
  const [receiptDate, setReceiptDate] = useState(todayISO());

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mark-received-title"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 400 }}
      >
        <div className="modal-header">
          <div>
            <h2 id="mark-received-title">Mark Received — Set Receipt Date</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <p className="status-note" style={{ color: "var(--muted)" }}>
          Set receipt date for {count} redemption{count !== 1 ? "s" : ""}.
        </p>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label htmlFor="mark-received-date" style={{ fontWeight: 600, whiteSpace: "nowrap" }}>Receipt Date</label>
          <input
            id="mark-received-date"
            className="text-input"
            type="date"
            value={receiptDate}
            onChange={(e) => setReceiptDate(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="ghost-button" type="button" onClick={() => setReceiptDate(todayISO())}>Today</button>
        </div>

        <div className="modal-actions modal-actions-split">
          <button className="ghost-button" type="button" onClick={() => onSave(null)}>Clear</button>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="ghost-button" type="button" onClick={onClose}>Cancel</button>
            <button className="primary-button" type="button" onClick={() => onSave(receiptDate)}>Save</button>
          </div>
        </div>
      </section>
    </div>
  );
}
