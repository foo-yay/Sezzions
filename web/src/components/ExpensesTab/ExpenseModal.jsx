import { useRef, useEffect, useState, useMemo } from "react";
import { getExpenseColumnValue } from "./expensesUtils";
import { EXPENSE_CATEGORIES } from "./expensesConstants";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function ExpenseModal({
  mode,
  expense,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  users,
  suggestions,
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Expense" : mode === "edit" ? "Edit Expense" : "View Expense";
  const amountRaw = form.amount;
  const amountInvalid = !amountRaw || isNaN(Number(amountRaw)) || Number(amountRaw) < 0;
  const vendorInvalid = !form.vendor || !form.vendor.trim();
  const dateInvalid = !form.expense_date;
  const formInvalid = amountInvalid || vendorInvalid || dateInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  // Auto-focus vendor field on mount
  const vendorRef = useRef(null);
  useEffect(() => {
    if (!readOnly && vendorRef.current) {
      vendorRef.current.focus();
    }
  }, [readOnly]);

  // Category options for TypeaheadSelect
  const categoryOptions = useMemo(() => {
    const builtIn = EXPENSE_CATEGORIES.map((c) => ({ value: c, label: c }));
    // Add any custom categories from suggestions that aren't already in the list
    const extraCategories = (suggestions?.categories || [])
      .filter((c) => !EXPENSE_CATEGORIES.includes(c))
      .map((c) => ({ value: c, label: c }));
    return [...builtIn, ...extraCategories];
  }, [suggestions?.categories]);

  // Vendor autocomplete suggestions
  const vendorSuggestions = useMemo(
    () => (suggestions?.vendors || []),
    [suggestions?.vendors],
  );

  // Filtered vendor suggestions based on input
  const [vendorFocused, setVendorFocused] = useState(false);
  const filteredVendors = useMemo(() => {
    if (!form.vendor || !form.vendor.trim()) return vendorSuggestions.slice(0, 8);
    const lower = form.vendor.toLowerCase();
    return vendorSuggestions.filter((v) => v.toLowerCase().includes(lower)).slice(0, 8);
  }, [form.vendor, vendorSuggestions]);

  // Notes autocomplete suggestions
  const notesSuggestions = useMemo(
    () => (suggestions?.notes || []),
    [suggestions?.notes],
  );
  const [notesFocused, setNotesFocused] = useState(false);
  const filteredNotes = useMemo(() => {
    if (!form.notes || !form.notes.trim()) return notesSuggestions.slice(0, 5);
    const lower = form.notes.toLowerCase();
    return notesSuggestions.filter((n) => n.toLowerCase().includes(lower)).slice(0, 5);
  }, [form.notes, notesSuggestions]);

  // View mode
  if (readOnly && expense) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card entity-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="expense-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="expense-modal-title">View Expense</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="modal-detail-body">
            <dl className="detail-grid modal-detail-grid">
              <div><dt>Date</dt><dd>{expense.expense_date}</dd></div>
              <div><dt>Time</dt><dd>{expense.expense_time || "—"}</dd></div>
              <div><dt>Amount</dt><dd>{getExpenseColumnValue(expense, "amount")}</dd></div>
              <div><dt>Vendor</dt><dd>{expense.vendor || "—"}</dd></div>
              <div><dt>Category</dt><dd>{expense.category || "—"}</dd></div>
              <div><dt>User</dt><dd>{expense.user_name || "—"}</dd></div>
            </dl>

            <div className="modal-detail-notes">
              <p className="field-label">Description</p>
              <div className="notes-display">{expense.description || "-"}</div>
            </div>

            <div className="modal-detail-notes">
              <p className="field-label">Notes</p>
              <div className="notes-display">{expense.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Expense</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  // Create / Edit mode
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card entity-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="expense-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="expense-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="purchase-form">
          {/* ── Date / Time — compact inline, pre-filled ── */}
          <div className="pf-datetime-row">
            <label className="field-label" htmlFor="expense-date-input">Date</label>
            <input
              id="expense-date-input"
              className={dateInvalid ? "text-input invalid" : "text-input"}
              type="date"
              value={form.expense_date}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, expense_date: event.target.value }))}
            />
            <label className="field-label" htmlFor="expense-time-input">Time</label>
            <input
              id="expense-time-input"
              className="text-input"
              type="time"
              step="1"
              value={form.expense_time}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, expense_time: event.target.value }))}
            />
          </div>

          {/* ── Expense Details — 4-column grid matching desktop layout ── */}
          <div className="pf-section">
            <p className="pf-section-title"><span>💵</span> Expense Details</p>
            <div className="pf-grid">
              <label className="field-label" htmlFor="expense-amount-input" style={{gridRow: 1, gridColumn: 1}}>Amount ($)</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 2}}>
                <input
                  id="expense-amount-input"
                  className={amountInvalid ? "text-input invalid" : "text-input"}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  tabIndex={1}
                  title={amountInvalid ? "Required" : undefined}
                  value={form.amount}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, amount: event.target.value }))}
                />
              </div>
              <label className="field-label" htmlFor="expense-category-input" style={{gridRow: 1, gridColumn: 3}}>Category</label>
              <div className="pf-cell" style={{gridRow: 1, gridColumn: 4}}>
                <TypeaheadSelect
                  id="expense-category-input"
                  tabIndex={3}
                  options={categoryOptions}
                  value={form.category}
                  onChange={(category) => setForm((current) => ({ ...current, category }))}
                  placeholder="Choose…"
                  disabled={readOnly}
                  allowClear
                />
              </div>

              <label className="field-label" htmlFor="expense-vendor-input" style={{gridRow: 2, gridColumn: 1}}>Vendor</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 2, position: "relative"}}>
                <input
                  id="expense-vendor-input"
                  ref={vendorRef}
                  className={vendorInvalid ? "text-input invalid" : "text-input"}
                  type="text"
                  placeholder="Vendor name…"
                  tabIndex={2}
                  title={vendorInvalid ? "Required" : undefined}
                  value={form.vendor}
                  readOnly={readOnly}
                  onChange={(event) => setForm((current) => ({ ...current, vendor: event.target.value }))}
                  onFocus={() => setVendorFocused(true)}
                  onBlur={() => setTimeout(() => setVendorFocused(false), 150)}
                  autoComplete="off"
                />
                {vendorFocused && filteredVendors.length > 0 && !readOnly ? (
                  <ul className="typeahead-dropdown">
                    {filteredVendors.map((v) => (
                      <li
                        key={v}
                        className="typeahead-option"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setForm((current) => ({ ...current, vendor: v }));
                          setVendorFocused(false);
                        }}
                      >
                        {v}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <label className="field-label" htmlFor="expense-user-input" style={{gridRow: 2, gridColumn: 3}}>User</label>
              <div className="pf-cell" style={{gridRow: 2, gridColumn: 4}}>
                <TypeaheadSelect
                  id="expense-user-input"
                  tabIndex={4}
                  options={(users || []).map((u) => ({ value: u.id, label: u.name }))}
                  value={form.user_id}
                  onChange={(userId) => setForm((current) => ({ ...current, user_id: userId }))}
                  placeholder="Optional"
                  disabled={readOnly}
                  allowClear
                />
              </div>
            </div>
          </div>

          {/* ── Description — always visible, compact ── */}
          <div className="pf-notes-row">
            <label className="field-label" htmlFor="expense-description-input">Description</label>
            <textarea
              id="expense-description-input"
              className="notes-input"
              placeholder="Optional"
              rows={2}
              tabIndex={5}
              value={form.description}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            />
          </div>

          {/* ── Notes — always visible, compact ── */}
          <div className="pf-notes-row" style={{position: "relative"}}>
            <label className="field-label" htmlFor="expense-notes-input">Notes</label>
            <textarea
              id="expense-notes-input"
              className="notes-input"
              placeholder="Optional"
              rows={2}
              tabIndex={6}
              value={form.notes}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
              onFocus={() => setNotesFocused(true)}
              onBlur={() => setTimeout(() => setNotesFocused(false), 150)}
            />
            {notesFocused && filteredNotes.length > 0 && !readOnly ? (
              <ul className="typeahead-dropdown">
                {filteredNotes.map((n) => (
                  <li
                    key={n}
                    className="typeahead-option"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setForm((current) => ({ ...current, notes: n }));
                      setNotesFocused(false);
                    }}
                  >
                    {n.length > 80 ? n.slice(0, 80) + "…" : n}
                  </li>
                ))}
              </ul>
            ) : null}
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
            Save Expense
          </button>
        </div>
      </section>
    </div>
  );
}
