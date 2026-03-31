import { initialSiteForm } from "./sitesConstants";

export default function SiteModal({
  mode,
  site,
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
  const title = mode === "create" ? "Add Site" : mode === "edit" ? "Edit Site" : "View Site";
  const nameInvalid = !form.name.trim();
  const scRateValue = parseFloat(form.sc_rate);
  const scRateInvalid = isNaN(scRateValue) || scRateValue < 0;
  const playthroughValue = parseFloat(form.playthrough_requirement);
  const playthroughInvalid = isNaN(playthroughValue) || playthroughValue < 0;
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && site) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card site-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="site-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="site-modal-title">View Site</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{site.name}</dd></div>
              <div><dt>URL</dt><dd>{site.url || "-"}</dd></div>
              <div><dt>SC Rate</dt><dd>{site.sc_rate}</dd></div>
              <div><dt>Playthrough</dt><dd>{site.playthrough_requirement}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={site.is_active ? "status-chip active" : "status-chip inactive"}>
                    {site.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{site.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Site</button>
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
        aria-labelledby="site-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="site-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="site-name-input">Name</label>
          <div>
            <input
              id="site-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="site-name-suggestions"
              placeholder="Required"
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="site-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {nameInvalid ? <p className="field-error">Name is required.</p> : null}
          </div>

          <label className="field-label" htmlFor="site-url-input">URL</label>
          <div>
            <input
              id="site-url-input"
              className="text-input"
              type="url"
              placeholder="Optional"
              value={form.url}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, url: event.target.value }))}
            />
          </div>

          <label className="field-label" htmlFor="site-sc-rate-input">SC Rate</label>
          <div>
            <input
              id="site-sc-rate-input"
              className={scRateInvalid ? "text-input invalid" : "text-input"}
              type="number"
              step="any"
              min="0"
              placeholder="1.0"
              value={form.sc_rate}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, sc_rate: event.target.value }))}
            />
            {scRateInvalid ? <p className="field-error">SC rate must be a non-negative number.</p> : null}
          </div>

          <label className="field-label" htmlFor="site-playthrough-input">Playthrough</label>
          <div>
            <input
              id="site-playthrough-input"
              className={playthroughInvalid ? "text-input invalid" : "text-input"}
              type="number"
              step="any"
              min="0"
              placeholder="1.0"
              value={form.playthrough_requirement}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, playthrough_requirement: event.target.value }))}
            />
            {playthroughInvalid ? <p className="field-error">Playthrough must be a non-negative number.</p> : null}
          </div>

          <label className="field-label" htmlFor="site-active-input">Active</label>
          <label className="toggle-row" htmlFor="site-active-input">
            <input
              id="site-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="site-notes-input">Notes</label>
          <textarea
            id="site-notes-input"
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
            disabled={nameInvalid || scRateInvalid || playthroughInvalid}
          >
            Save Site
          </button>
        </div>
      </section>
    </div>
  );
}
