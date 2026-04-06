import { useRef, useEffect } from "react";
import { getRedemptionColumnValue } from "./redemptionsUtils";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function RedemptionModal({
  mode,
  redemption,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  users,
  sites,
  redemptionMethods,
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Redemption" : mode === "edit" ? "Edit Redemption" : "View Redemption";
  const userInvalid = !form.user_id;
  const siteInvalid = !form.site_id;
  const amountRaw = form.amount;
  const amountInvalid = !amountRaw || amountRaw === "" || isNaN(Number(amountRaw)) || Number(amountRaw) < 0;
  const dateInvalid = !form.redemption_date;
  const formInvalid = userInvalid || siteInvalid || amountInvalid || dateInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  // Auto-focus User field on mount
  const userRef = useRef(null);
  useEffect(() => {
    if (!readOnly && userRef.current) {
      const input = userRef.current.querySelector ? userRef.current.querySelector("input") : userRef.current;
      if (input) input.focus();
    }
  }, [readOnly]);

  // Filter methods by selected user
  const filteredMethods = form.user_id
    ? redemptionMethods.filter((m) => m.user_id === form.user_id)
    : redemptionMethods;

  // ── View Mode ─────────────────────────────────────────────
  if (readOnly && redemption) {
    return (
      <div className="modal-overlay" role="dialog" aria-label={title}>
        <section className="entity-modal redemption-view-modal">
          <div className="modal-header">
            <h2 className="modal-title">{title}</h2>
            <div className="modal-header-actions">
              <button className="ghost-button" type="button" onClick={onRequestEdit}>Edit</button>
              <button className="ghost-button danger" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="modal-detail-grid">
            <span className="modal-detail-label">Date</span>
            <span className="modal-detail-value">{redemption.redemption_date || "—"}</span>
            <span className="modal-detail-label">Time</span>
            <span className="modal-detail-value">{redemption.redemption_time || "—"}</span>

            <span className="modal-detail-label">User</span>
            <span className="modal-detail-value">{redemption.user_name || "—"}</span>
            <span className="modal-detail-label">Site</span>
            <span className="modal-detail-value">{redemption.site_name || "—"}</span>

            <span className="modal-detail-label">Amount</span>
            <span className="modal-detail-value">{getRedemptionColumnValue(redemption, "amount")}</span>
            <span className="modal-detail-label">Fees</span>
            <span className="modal-detail-value">{getRedemptionColumnValue(redemption, "fees")}</span>

            <span className="modal-detail-label">Method</span>
            <span className="modal-detail-value">{redemption.method_name || "—"}</span>
            <span className="modal-detail-label">Type</span>
            <span className="modal-detail-value">{redemption.more_remaining ? "Partial" : "Full"}</span>

            <span className="modal-detail-label">Status</span>
            <span className="modal-detail-value">
              <span className={`status-chip ${redemption.status === "PENDING" ? "active" : "inactive"}`}>
                {redemption.status || "PENDING"}
              </span>
            </span>
            <span className="modal-detail-label">Free SC</span>
            <span className="modal-detail-value">{redemption.is_free_sc ? "Yes" : "No"}</span>

            <span className="modal-detail-label">Receipt Date</span>
            <span className="modal-detail-value">{redemption.receipt_date || "—"}</span>
            <span className="modal-detail-label">Processed</span>
            <span className="modal-detail-value">{redemption.processed ? "Yes" : "No"}</span>

            <span className="modal-detail-label">Cost Basis</span>
            <span className="modal-detail-value">{getRedemptionColumnValue(redemption, "cost_basis")}</span>
            <span className="modal-detail-label">Net P&amp;L</span>
            <span className="modal-detail-value">{getRedemptionColumnValue(redemption, "net_pl")}</span>

            {redemption.cancel_reason ? (
              <>
                <span className="modal-detail-label">Cancel Reason</span>
                <span className="modal-detail-value" style={{ gridColumn: "2 / -1" }}>{redemption.cancel_reason}</span>
              </>
            ) : null}

            <span className="modal-detail-label">Notes</span>
            <span className="modal-detail-value" style={{ gridColumn: "2 / -1" }}>{redemption.notes || "—"}</span>
          </div>
        </section>
      </div>
    );
  }

  // ── Create / Edit Mode ────────────────────────────────────
  return (
    <div className="modal-overlay" role="dialog" aria-label={title}>
      <section className="entity-modal redemption-edit-modal">
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="redemption-form">
          {/* ── Date / Time ── */}
          <div className="pf-datetime-row">
            <label className="field-label" htmlFor="redemption-date-input">Date</label>
            <input
              id="redemption-date-input"
              className={dateInvalid ? "text-input invalid" : "text-input"}
              type="date"
              value={form.redemption_date}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, redemption_date: event.target.value }))}
            />
            <label className="field-label" htmlFor="redemption-time-input">Time</label>
            <input
              id="redemption-time-input"
              className="text-input"
              type="time"
              step="1"
              value={form.redemption_time}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, redemption_time: event.target.value }))}
            />
          </div>

          {/* ── Redemption Details — 4-column grid ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>💸</span> Redemption Details</p>
            <div className="pf-grid">
              {/* Left column: User → Site → Method */}
              <label className="field-label" htmlFor="redemption-user-input" style={{gridRow: 1, gridColumn: 1}}>User</label>
              <div className="pf-cell" ref={userRef} style={{gridRow: 1, gridColumn: 2}}>
                <TypeaheadSelect
                  id="redemption-user-input"
                  options={users.map((u) => ({ value: u.id, label: u.name }))}
                  value={form.user_id}
                  onChange={(userId) => {
                    setForm((current) => ({
                      ...current,
                      user_id: userId,
                      redemption_method_id: userId === current.user_id ? current.redemption_method_id : "",
                    }));
                  }}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={userInvalid}
                  title={userInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="redemption-site-input" style={{gridRow: 2, gridColumn: 1}}>Site</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 2}}>
                <TypeaheadSelect
                  id="redemption-site-input"
                  options={sites.map((s) => ({ value: s.id, label: s.name }))}
                  value={form.site_id}
                  onChange={(siteId) => setForm((current) => ({ ...current, site_id: siteId }))}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={siteInvalid}
                  title={siteInvalid ? "Required" : undefined}
                />
              </div>
              <label className="field-label" htmlFor="redemption-method-input" style={{gridRow: 3, gridColumn: 1}}>Method</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 2}}>
                <TypeaheadSelect
                  id="redemption-method-input"
                  options={filteredMethods.map((m) => ({ value: m.id, label: m.name }))}
                  value={form.redemption_method_id}
                  onChange={(methodId) => setForm((current) => ({ ...current, redemption_method_id: methodId }))}
                  placeholder={form.user_id ? "Select…" : "Pick user first"}
                  disabled={readOnly}
                  noMatchText="No methods for this user"
                />
              </div>

              {/* Right column: Amount → Fees → Receipt Date */}
              <label className="field-label" htmlFor="redemption-amount-input" style={{gridRow: 1, gridColumn: 3}}>Amount</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 4}}>
                <input
                  id="redemption-amount-input"
                  className={amountInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  title={amountInvalid ? "Required" : undefined}
                  value={form.amount}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="redemption-fees-input" style={{gridRow: 2, gridColumn: 3}}>Fees</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 4}}>
                <input
                  id="redemption-fees-input"
                  className="text-input"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={form.fees}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, fees: event.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="redemption-receipt-date-input" style={{gridRow: 3, gridColumn: 3}}>Receipt</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 4}}>
                <input
                  id="redemption-receipt-date-input"
                  className="text-input"
                  type="date"
                  value={form.receipt_date}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, receipt_date: event.target.value }))}
                />
              </div>
            </div>
          </div>

          {/* ── Options row — inline toggles ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>⚙️</span> Options</p>
            <div className="pf-grid" style={{ gridTemplateRows: "auto auto" }}>
              <label className="field-label" style={{gridRow: 1, gridColumn: 1}}>Type</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 2}}>
                <div className="radio-group-inline">
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="redemption-type"
                      checked={!form.more_remaining}
                      disabled={readOnly}
                      onChange={() => setForm((current) => ({ ...current, more_remaining: false }))}
                    />
                    Full
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="redemption-type"
                      checked={form.more_remaining}
                      disabled={readOnly}
                      onChange={() => setForm((current) => ({ ...current, more_remaining: true }))}
                    />
                    Partial
                  </label>
                </div>
              </div>

              <label className="field-label" style={{gridRow: 1, gridColumn: 3}}>Processed</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 4}}>
                <input
                  type="checkbox"
                  checked={form.processed}
                  disabled={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, processed: event.target.checked }))}
                />
              </div>

              <label className="field-label" style={{gridRow: 2, gridColumn: 1}}>Free SC</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 2}}>
                <input
                  type="checkbox"
                  checked={form.is_free_sc}
                  disabled={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, is_free_sc: event.target.checked }))}
                />
              </div>
            </div>
          </div>

          {/* ── Notes ── */}
          <div className="pf-notes-row">
            <label className="field-label" htmlFor="redemption-notes-input">Notes</label>
            <textarea
              id="redemption-notes-input"
              className="notes-input"
              placeholder="Optional"
              rows={2}
              value={form.notes}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
            />
          </div>
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}

        <div className="modal-actions modal-actions-end">
          <button
            className="primary-button"
            type="button"
            onClick={onSubmit}
            disabled={formInvalid}
          >
            Save Redemption
          </button>
        </div>
      </section>
    </div>
  );
}
