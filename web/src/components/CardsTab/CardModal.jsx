import { initialCardForm } from "./cardsConstants";

export default function CardModal({
  mode,
  card,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  suggestions,
  users
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Card" : mode === "edit" ? "Edit Card" : "View Card";
  const nameInvalid = !form.name.trim();
  const userIdInvalid = !form.user_id;
  const lastFourValue = form.last_four.trim();
  const lastFourInvalid = lastFourValue.length > 0 && lastFourValue.length !== 4;
  const cashbackValue = parseFloat(form.cashback_rate);
  const cashbackInvalid = form.cashback_rate !== "" && (isNaN(cashbackValue) || cashbackValue < 0 || cashbackValue > 100);
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && card) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card site-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="card-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="card-modal-title">View Card</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{card.name}</dd></div>
              <div><dt>User</dt><dd>{card.user_name || "\u2014"}</dd></div>
              <div><dt>Last Four</dt><dd>{card.last_four || "\u2014"}</dd></div>
              <div><dt>Cashback Rate</dt><dd>{Number(card.cashback_rate).toFixed(2)}%</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={card.is_active ? "status-chip active" : "status-chip inactive"}>
                    {card.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{card.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Card</button>
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
        aria-labelledby="card-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="card-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="card-name-input">Name</label>
          <div>
            <input
              id="card-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="card-name-suggestions"
              placeholder="Required"
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="card-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {nameInvalid ? <p className="field-error">Name is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="card-user-input">User</label>
          <div>
            <select
              id="card-user-input"
              className={userIdInvalid ? "text-input invalid" : "text-input"}
              value={form.user_id}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, user_id: event.target.value }))}
            >
              <option value="">Select a user...</option>
              {users.map((user) => (
                <option key={user.id} value={user.id}>{user.display_name || user.email || user.id}</option>
              ))}
            </select>
            {userIdInvalid ? <p className="field-error">User is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="card-last-four-input">Last Four</label>
          <div>
            <input
              id="card-last-four-input"
              className={lastFourInvalid ? "text-input invalid" : "text-input"}
              type="text"
              maxLength={4}
              placeholder="Optional (4 digits)"
              value={form.last_four}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, last_four: event.target.value }))}
            />
            {lastFourInvalid ? <p className="field-error">Must be exactly 4 characters.</p> : null}
          </div>

          <label className="field-label" htmlFor="card-cashback-input">Cashback Rate</label>
          <div>
            <input
              id="card-cashback-input"
              className={cashbackInvalid ? "text-input invalid" : "text-input"}
              type="number"
              step="any"
              min="0"
              max="100"
              placeholder="0.00"
              value={form.cashback_rate}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, cashback_rate: event.target.value }))}
            />
            {cashbackInvalid ? <p className="field-error">Cashback rate must be 0–100.</p> : null}
          </div>

          <label className="field-label" htmlFor="card-active-input">Active</label>
          <label className="toggle-row" htmlFor="card-active-input">
            <input
              id="card-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="card-notes-input">Notes</label>
          <textarea
            id="card-notes-input"
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
            disabled={nameInvalid || userIdInvalid || lastFourInvalid || cashbackInvalid}
          >
            Save Card
          </button>
        </div>
      </section>
    </div>
  );
}
