export default function ConfirmationModal({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel", tone = "danger", onCancel, onConfirm }) {
  return (
    <div className="modal-backdrop modal-backdrop-elevated" role="presentation" onClick={onCancel}>
      <section
        className="modal-card confirmation-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmation-modal-title"
        aria-describedby="confirmation-modal-message"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="confirmation-modal-title">{title}</h2>
          </div>
        </div>

        <p id="confirmation-modal-message" className="status-note">{message}</p>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onCancel}>{cancelLabel}</button>
          <button className={tone === "danger" ? "danger-button" : "primary-button"} type="button" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}
