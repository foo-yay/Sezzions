import { initialGameForm } from "./gamesConstants";
import { getGameColumnValue } from "./gamesUtils";
import TypeaheadSelect from "../common/TypeaheadSelect";

export default function GameModal({
  mode,
  game,
  form,
  setForm,
  onClose,
  onSubmit,
  onRequestEdit,
  onRequestDelete,
  submitError,
  suggestions,
  gameTypes
}) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add Game" : mode === "edit" ? "Edit Game" : "View Game";
  const nameInvalid = !form.name.trim();
  const gameTypeInvalid = !form.game_type_id;
  const rtpRaw = form.rtp;
  const rtpInvalid = rtpRaw !== "" && rtpRaw !== null && rtpRaw !== undefined
    && (isNaN(Number(rtpRaw)) || Number(rtpRaw) < 0 || Number(rtpRaw) > 100);
  const formInvalid = nameInvalid || gameTypeInvalid || rtpInvalid;
  const closeLabel = readOnly ? "Close" : "Cancel";

  if (readOnly && game) {
    return (
      <div className="modal-backdrop" role="presentation" onClick={onClose}>
        <section
          className="modal-card game-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="game-modal-title"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <div>
              <h2 id="game-modal-title">View Game</h2>
            </div>
            <button className="ghost-button" type="button" onClick={onClose}>{closeLabel}</button>
          </div>

          <div className="user-detail-body">
            <dl className="detail-grid user-detail-grid">
              <div><dt>Name</dt><dd>{game.name}</dd></div>
              <div><dt>Game Type</dt><dd>{game.game_type_name}</dd></div>
              <div><dt>Expected RTP</dt><dd>{getGameColumnValue(game, "rtp")}</dd></div>
              <div><dt>Actual RTP</dt><dd>{getGameColumnValue(game, "actual_rtp")}</dd></div>
              <div>
                <dt>Status</dt>
                <dd>
                  <span className={game.is_active ? "status-chip active" : "status-chip inactive"}>
                    {game.is_active ? "Active" : "Inactive"}
                  </span>
                </dd>
              </div>
            </dl>

            <div className="user-detail-notes">
              <p className="detail-label">Notes</p>
              <div className="notes-display">{game.notes || "-"}</div>
            </div>
          </div>

          <div className="modal-actions modal-actions-split">
            <div className="toolbar-row">
              <button className="ghost-button" type="button" onClick={onRequestDelete}>Delete</button>
            </div>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={onRequestEdit}>Edit Game</button>
            </div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card game-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="game-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="game-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            {closeLabel}
          </button>
        </div>

        <div className="form-grid">
          <label className="field-label" htmlFor="game-name-input">Name</label>
          <div>
            <input
              id="game-name-input"
              className={nameInvalid ? "text-input invalid" : "text-input"}
              type="text"
              list="game-name-suggestions"
              placeholder="Required"
              title={nameInvalid ? "Name is required" : undefined}
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="game-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <label className="field-label" htmlFor="game-type-input">Game Type</label>
          <div>
            <TypeaheadSelect
              id="game-type-input"
              options={gameTypes.map((gt) => ({
                value: gt.id,
                label: gt.name
              }))}
              value={form.game_type_id}
              onChange={(gtId) => setForm((current) => ({ ...current, game_type_id: gtId }))}
              placeholder="Required"
              disabled={readOnly}
              invalid={gameTypeInvalid}
              title={gameTypeInvalid ? "Game type is required" : undefined}
            />
          </div>

          <label className="field-label" htmlFor="game-rtp-input">Expected RTP (%)</label>
          <div>
            <input
              id="game-rtp-input"
              className={rtpInvalid ? "text-input invalid" : "text-input"}
              type="number"
              min="0"
              max="100"
              step="0.01"
              placeholder="Optional (0-100)"
              title={rtpInvalid ? "RTP must be between 0 and 100" : undefined}
              value={form.rtp}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, rtp: event.target.value }))}
            />
          </div>

          <label className="field-label" htmlFor="game-active-input">Active</label>
          <label className="toggle-row" htmlFor="game-active-input">
            <input
              id="game-active-input"
              type="checkbox"
              checked={form.is_active}
              disabled={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))}
            />
            <span>{form.is_active ? "Active" : "Inactive"}</span>
          </label>

          <label className="field-label field-label-top" htmlFor="game-notes-input">Notes</label>
          <textarea
            id="game-notes-input"
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
            Save Game
          </button>
        </div>
      </section>
    </div>
  );
}
