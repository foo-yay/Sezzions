import { initialUserForm } from "./usersConstants";

export default function UserModal({
  mode,
  user,
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
  const title = mode === "create" ? "Add User" : mode === "edit" ? "Edit User" : "View User";
  const nameInvalid = !form.name.trim();
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && user) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card user-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="user-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="user-modal-title">View User</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{user.name}</dd></div>
              <div><dt>Email</dt><dd>{user.email || "-"}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={user.is_active ? "status-chip active" : "status-chip inactive"}>
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{user.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit User</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card user-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="user-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="user-name-input">Name</label>
          <div>
            <input
              id="user-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="user-name-suggestions"
              placeholder="Required"
              title={nameInvalid ? "Name is required" : undefined}
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="user-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="user-email-input">Email</label>
          <div>
            <input
              id="user-email-input"
              className="text-input"
              type="email"
              list="user-email-suggestions"
              placeholder="Optional"
              value={form.email}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            />
            <datalist id="user-email-suggestions">
              {suggestions.emails.map((email) => (
                <option key={email} value={email} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="user-active-input">Active</label>
          <label className="toggle-row" htmlFor="user-active-input">
            <input
              id="user-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="user-notes-input">Notes</label>
          <textarea
            id="user-notes-input"
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
            Save User
          </button>
        </div>
      </section>
    </div>
  );
}
