import { initialGameTypeForm } from "./gameTypesConstants";

export default function GameTypeModal({
  mode,
  gameType,
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
  const title = mode === "create" ? "Add Game Type" : mode === "edit" ? "Edit Game Type" : "View Game Type";
  const nameInvalid = !form.name.trim();
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && gameType) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card game-type-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="game-type-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="game-type-modal-title">View Game Type</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{gameType.name}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={gameType.is_active ? "status-chip active" : "status-chip inactive"}>
                    {gameType.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{gameType.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Game Type</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card game-type-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="game-type-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="game-type-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="game-type-name-input">Name</label>
          <div>
            <input
              id="game-type-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="game-type-name-suggestions"
              placeholder="Required"
              title={nameInvalid ? "Name is required" : undefined}
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="game-type-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="game-type-active-input">Active</label>
          <label className="toggle-row" htmlFor="game-type-active-input">
            <input
              id="game-type-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="game-type-notes-input">Notes</label>
          <textarea
            id="game-type-notes-input"
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
            Save Game Type
          </button>
        </div>
      </section>
    </div>
  );
}
