import { initialMethodTypeForm } from "./methodTypesConstants";

export default function MethodTypeModal({
  mode,
  methodType,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  suggestions
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Method Type" : mode === "edit" ? "Edit Method Type" : "View Method Type";
  const nameInvalid = !form.name.trim();
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && methodType) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card method-type-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="method-type-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="method-type-modal-title">View Method Type</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{methodType.name}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={methodType.is_active ? "status-chip active" : "status-chip inactive"}>
                    {methodType.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{methodType.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Method Type</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card method-type-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="method-type-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="method-type-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="method-type-name-input">Name</label>
          <div>
            <input
              id="method-type-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="method-type-name-suggestions"
              placeholder="Required"
              title={nameInvalid ? "Name is required" : undefined}
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="method-type-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="method-type-active-input">Active</label>
          <label className="toggle-row" htmlFor="method-type-active-input">
            <input
              id="method-type-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="method-type-notes-input">Notes</label>
          <textarea
            id="method-type-notes-input"
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
          <button className="primary-button" type="button" onClick={onSubmit} disabled={nameInvalid}>
            Save Method Type
          </button>
        </div>
      </section>
    </div>
  );
}
