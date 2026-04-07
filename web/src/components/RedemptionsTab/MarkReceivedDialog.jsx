import { useState } from "react";

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function MarkReceivedDialog({ count, onSave, onClose }) {
  const [receiptDate, setReceiptDate] = useState(todayISO());

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 400 }}>
        <div className="modal-header">
          <h3>Mark Received — Set Receipt Date</h3>
          <button className="modal-close-button" type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body" style={{ padding: "16px 20px" }}>
          <p style={{ marginBottom: 12, color: "var(--muted)" }}>
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
        </div>
        <div className="modal-footer">
          <button className="ghost-button" type="button" onClick={onClose}>Cancel</button>
          <button className="ghost-button" type="button" onClick={() => onSave(null)}>Clear</button>
          <button className="primary-button" type="button" onClick={() => onSave(receiptDate)}>Save</button>
        </div>
      </div>
    </div>
  );
}
