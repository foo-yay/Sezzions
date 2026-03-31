export default function NotificationsModal({ onClose }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card utility-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notifications-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="notifications-modal-title">Notifications</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <p className="status-note">No notifications.</p>
      </section>
    </div>
  );
}
