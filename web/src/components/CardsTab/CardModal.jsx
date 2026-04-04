import { initialCardForm } from "./cardsConstants";
import TypeaheadSelect from "../common/TypeaheadSelect";

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
          className="modal-card entity-modal"
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

          <div className="modal-detail-body">
            <dl className="detail-grid modal-detail-grid">
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

            <div className="modal-detail-notes">
              <p className="field-label">Notes</p>
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
        className="modal-card entity-modal"
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
              title={nameInvalid ? "Name is required" : undefined}
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="card-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="card-user-input">User</label>
          <div>
            <TypeaheadSelect
              id="card-user-input"
              options={users.map((user) => ({
                value: user.id,
                label: user.name || user.email || user.id
              }))}
              value={form.user_id}
              onChange={(userId) => setForm((current) => ({ ...current, user_id: userId }))}
              placeholder="Search users..."
              disabled={readOnly}
              invalid={userIdInvalid}
              title={userIdInvalid ? "User is required" : undefined}
            />
          </div>

          <label className="field-label" htmlFor="card-last-four-input">Last Four</label>
          <div>
            <input
              id="card-last-four-input"
              className={lastFourInvalid ? "text-input invalid" : "text-input"}
              type="text"
              maxLength={4}
              placeholder="Optional (4 digits)"
              title={lastFourInvalid ? "Must be exactly 4 characters" : undefined}
              value={form.last_four}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, last_four: event.target.value }))}
            />
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
              title={cashbackInvalid ? "Cashback rate must be 0\u2013100" : undefined}
              value={form.cashback_rate}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, cashback_rate: event.target.value }))}
            />

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
