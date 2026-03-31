export default function AccountModal({ accountOwner, accountRole, accountStatus, workspaceName, onClose, onSignOut }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card utility-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h2 id="account-modal-title">My Account</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>Close</button>
        </div>

        <dl className="detail-grid compact-grid">
          <div><dt>Owner</dt><dd>{accountOwner}</dd></div>
          <div><dt>Role</dt><dd>{accountRole}</dd></div>
          <div><dt>Status</dt><dd>{accountStatus}</dd></div>
          <div><dt>Workspace</dt><dd>{workspaceName}</dd></div>
        </dl>

        <div className="modal-actions modal-actions-end">
          <button className="ghost-button" type="button" onClick={onSignOut}>Sign Out</button>
        </div>
      </section>
    </div>
  );
}
