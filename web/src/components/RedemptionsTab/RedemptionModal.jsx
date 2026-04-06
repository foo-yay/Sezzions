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
  methodTypes,
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Redemption" : mode === "edit" ? "Edit Redemption" : "View Redemption";
  const userInvalid = !form.user_id;
  const siteInvalid = !form.site_id;
  const amountRaw = form.amount;
  const amountInvalid = !amountRaw || amountRaw === "" || isNaN(Number(amountRaw)) || Number(amountRaw) <= 0;
  const dateInvalid = !form.redemption_date;
  const methodInvalid = !form.redemption_method_id;
  const feesNum = form.fees !== "" && !isNaN(Number(form.fees)) ? Number(form.fees) : 0;
  const amountNum = !isNaN(Number(amountRaw)) ? Number(amountRaw) : 0;
  const feesInvalid = form.fees !== "" && feesNum > amountNum;
  const receiptDateInvalid = form.receipt_date && form.redemption_date && form.receipt_date < form.redemption_date;
  const formInvalid = userInvalid || siteInvalid || amountInvalid || dateInvalid || methodInvalid || feesInvalid || receiptDateInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  // Auto-focus User field on mount
  const userRef = useRef(null);
  useEffect(() => {
    if (!readOnly && userRef.current) {
      const input = userRef.current.querySelector ? userRef.current.querySelector("input") : userRef.current;
      if (input) input.focus();
    }
  }, [readOnly]);

  // Two-step cascade: User → Method Type → Method (desktop parity)
  // Methods only populate when BOTH user AND method type are selected.
  // Global methods (user_id=null) are included for all users.
  const filteredMethods = (form.user_id && form.redemption_method_type_id)
    ? redemptionMethods.filter(
        (m) => (m.user_id === form.user_id || m.user_id === null)
          && m.method_type_id === form.redemption_method_type_id
      )
    : [];

  // ── View Mode ─────────────────────────────────────────────
  if (readOnly && redemption) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card entity-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="redemption-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="redemption-modal-title">View Redemption</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="modal-detail-body">
            <dl className="detail-grid modal-detail-grid">
              <div><dt>Date</dt><dd>{redemption.redemption_date || "—"}</dd></div>
              <div><dt>Time</dt><dd>{redemption.redemption_time || "—"}</dd></div>
              <div><dt>User</dt><dd>{redemption.user_name || "—"}</dd></div>
              <div><dt>Site</dt><dd>{redemption.site_name || "—"}</dd></div>
              <div><dt>Amount</dt><dd>{getRedemptionColumnValue(redemption, "amount")}</dd></div>
              <div><dt>Fees</dt><dd>{getRedemptionColumnValue(redemption, "fees")}</dd></div>
              <div><dt>Method Type</dt><dd>{redemption.method_type_name || "—"}</dd></div>
              <div><dt>Method</dt><dd>{redemption.method_name || "—"}</dd></div>
              <div><dt>Type</dt><dd>{redemption.more_remaining ? "Partial" : "Full"}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={redemption.status === "PENDING" ? "status-chip active" : "status-chip inactive"}>
                    {redemption.status || "PENDING"}
                  </span>
                </dd>
              </div>
              <div><dt>Receipt Date</dt><dd>{redemption.receipt_date || "—"}</dd></div>
              <div><dt>Processed</dt><dd>{redemption.processed ? "Yes" : "No"}</dd></div>
              <div><dt>Cost Basis</dt><dd>{getRedemptionColumnValue(redemption, "cost_basis")}</dd></div>
              <div><dt>Net P&amp;L</dt><dd>{getRedemptionColumnValue(redemption, "net_pl")}</dd></div>
            </dl>

            {redemption.cancel_reason ? (
              <div className="modal-detail-notes">
                <p className="field-label">Cancel Reason</p>
                <div className="notes-display">{redemption.cancel_reason}</div>
              </div>
            ) : null}

            <div className="modal-detail-notes">
              <p className="field-label">Notes</p>
              <div className="notes-display">{redemption.notes || "—"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Redemption</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  // ── Create / Edit Mode ────────────────────────────────────
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card entity-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="redemption-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="redemption-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="purchase-form">
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

          {/* ── Redemption Details — 4-column grid (desktop parity layout) ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>💰</span> Redemption Details</p>
            <div className="pf-grid">
              {/* DOM order = tab order: User → Site → Method Type → Method → Amount → Fees → Type → Receipt → Processed */}
              {/* Grid positions keep the visual 2-column layout via inline styles */}

              {/* User (row 1, left) */}
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
                      redemption_method_type_id: userId === current.user_id ? current.redemption_method_type_id : "",
                      redemption_method_id: userId === current.user_id ? current.redemption_method_id : "",
                    }));
                  }}
                  placeholder="Select…"
                  disabled={readOnly}
                  invalid={userInvalid}
                  title={userInvalid ? "Required" : undefined}
                />
              </div>

              {/* Site (row 2, left) */}
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

              {/* Method Type (row 3, left) */}
              <label className="field-label" htmlFor="redemption-method-type-input" style={{gridRow: 3, gridColumn: 1}}>Method Type</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 2}}>
                <TypeaheadSelect
                  id="redemption-method-type-input"
                  options={methodTypes.map((mt) => ({ value: mt.id, label: mt.name }))}
                  value={form.redemption_method_type_id}
                  onChange={(typeId) => {
                    setForm((current) => ({
                      ...current,
                      redemption_method_type_id: typeId,
                      redemption_method_id: typeId === current.redemption_method_type_id ? current.redemption_method_id : "",
                    }));
                  }}
                  placeholder={form.user_id ? "Select…" : "Pick user first"}
                  disabled={readOnly || !form.user_id}
                  noMatchText="No method types"
                />
              </div>

              {/* Method (row 4, left) */}
              <label className="field-label" htmlFor="redemption-method-input" style={{gridRow: 4, gridColumn: 1}}>Method</label>
              <div className="pf-cell" style={{gridRow: 4, gridColumn: 2}}>
                <TypeaheadSelect
                  id="redemption-method-input"
                  options={filteredMethods.map((m) => ({ value: m.id, label: m.name }))}
                  value={form.redemption_method_id}
                  onChange={(methodId) => setForm((current) => ({ ...current, redemption_method_id: methodId }))}
                  placeholder={form.user_id && form.redemption_method_type_id ? "Select…" : "Pick user & type first"}
                  disabled={readOnly || !form.user_id || !form.redemption_method_type_id}
                  invalid={methodInvalid}
                  title={methodInvalid ? "Required" : undefined}
                  noMatchText="No methods for this user & type"
                />
              </div>

              {/* Amount (row 1, right) */}
              <label className="field-label" htmlFor="redemption-amount-input" style={{gridRow: 1, gridColumn: 3}}>Amount</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 4}}>
                <input
                  id="redemption-amount-input"
                  className={amountInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder="0.00"
                  title={amountInvalid ? "Required (must be > $0)" : undefined}
                  value={form.amount}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                />
              </div>

              {/* Fees (row 2, right) */}
              <label className="field-label" htmlFor="redemption-fees-input" style={{gridRow: 2, gridColumn: 3}}>Fees</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 4}}>
                <input
                  id="redemption-fees-input"
                  className={feesInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  title={feesInvalid ? "Fees cannot exceed amount" : undefined}
                  value={form.fees}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, fees: event.target.value }))}
                />
              </div>

              {/* Redemption Type (row 3, right) */}
              <label className="field-label" style={{gridRow: 3, gridColumn: 3}}>Type</label>
              <div className="pf-cell" style={{gridRow: 3, gridColumn: 4}}>
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

              {/* Receipt Date (row 4, right) */}
              <label className="field-label" htmlFor="redemption-receipt-date-input" style={{gridRow: 4, gridColumn: 3}}>Receipt</label>
              <div className="pf-cell" style={{gridRow: 4, gridColumn: 4}}>
                <input
                  id="redemption-receipt-date-input"
                  className={receiptDateInvalid ? "text-input invalid" : "text-input"}
                  type="date"
                  title={receiptDateInvalid ? "Receipt date cannot be before redemption date" : undefined}
                  value={form.receipt_date}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, receipt_date: event.target.value }))}
                />
              </div>

              {/* Processed (row 5, right — left-justified) */}
              <label className="field-label" style={{gridRow: 5, gridColumn: 3}}>Processed</label>
              <div className="pf-cell" style={{gridRow: 5, gridColumn: 4, justifySelf: "start"}}>
                <input
                  type="checkbox"
                  checked={form.processed}
                  disabled={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, processed: event.target.checked }))}
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
