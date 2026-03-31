export default function StatusModal({ overallTone, statusItems, onClose, onRetryHostedConnection }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card status-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="status-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="status-modal-title">Connection Health</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <div className="status-overview-strip">
          <span className={`status-dot large ${overallTone}`} aria-hidden="true" />
          <div>
            <strong>Overall status</strong>
            <p className="status-note">
              {overallTone === "good"
                ? "All hosted checks are healthy."
                : overallTone === "bad"
                  ? "All hosted checks are failing."
                  : "Hosted checks are mixed or partially degraded."}
            </p>
          </div>
        </div>

        <dl className="status-list">
          {statusItems.map((item) => (
            <div key={item.label} className="status-list-item">
              <dt>
                <span className={`status-dot ${item.tone}`} aria-hidden="true" />
                {item.label}
              </dt>
              <dd>{item.message}</dd>
            </div>
          ))}
        </dl>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onRetryHostedConnection}>Retry Hosted Connection</button>
        </div>
      </section>
    </div>
  );
}
