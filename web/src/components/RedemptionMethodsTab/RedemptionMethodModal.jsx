import { initialRedemptionMethodForm } from "./redemptionMethodsConstants";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function RedemptionMethodModal({
  mode,
  method,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  suggestions,
  users,
  methodTypes
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Redemption Method" : mode === "edit" ? "Edit Redemption Method" : "View Redemption Method";
  const nameInvalid = !form.name.trim();
  const methodTypeInvalid = !form.method_type_id;
  const userInvalid = !form.user_id;
  const formInvalid = nameInvalid || methodTypeInvalid || userInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && method) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card site-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="redemption-method-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="redemption-method-modal-title">View Redemption Method</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{method.name}</dd></div>
              <div><dt>Method Type</dt><dd>{method.method_type_name}</dd></div>
              <div><dt>User</dt><dd>{method.user_name}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={method.is_active ? "status-chip active" : "status-chip inactive"}>
                    {method.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{method.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Method</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card site-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="redemption-method-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="redemption-method-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="rm-name-input">Name</label>
          <div>
            <input
              id="rm-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="rm-name-suggestions"
              placeholder="Required"
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="rm-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {nameInvalid ? <p className="field-error">Name is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="rm-method-type-input">Method Type</label>
          <div>
            <TypeaheadSelect
              id="rm-method-type-input"
              options={methodTypes.map((mt) => ({
                value: mt.id,
                label: mt.name
              }))}
              value={form.method_type_id}
              onChange={(mtId) => setForm((current) => ({ ...current, method_type_id: mtId }))}
              placeholder="Required"
              disabled={readOnly}
            />
            {methodTypeInvalid ? <p className="field-error">Method type is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="rm-user-input">User</label>
          <div>
            <TypeaheadSelect
              id="rm-user-input"
              options={users.map((user) => ({
                value: user.id,
                label: user.name || user.email || user.id
              }))}
              value={form.user_id}
              onChange={(userId) => setForm((current) => ({ ...current, user_id: userId }))}
              placeholder="Required"
              disabled={readOnly}
            />
            {userInvalid ? <p className="field-error">User is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="rm-active-input">Active</label>
          <label className="toggle-row" htmlFor="rm-active-input">
            <input
              id="rm-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="rm-notes-input">Notes</label>
          <textarea
            id="rm-notes-input"
            className="notes-input"
            placeholder="Optional"
            rows={5}
            value={form.notes}
            readOnly={readOnly}
            onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
          />
        </div>

        {submitError ? <p className="submit-error">{submitError}</p> : null}

        <div className="modal-actions modal-actions-end">
          <button
            className="primary-button"
            type="button"
            onClick={onSubmit}
            disabled={formInvalid}
          >
            Save Method
          </button>
        </div>
      </section>
    </div>
  );
}
