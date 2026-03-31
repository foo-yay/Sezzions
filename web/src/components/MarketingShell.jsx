export default function MarketingShell({ auth }) {
  return (
    <div className="marketing-shell">
      <header className="marketing-hero">
        <div className="marketing-copy">
          <p className="section-kicker">Sezzions Hosted</p>
          <h1>Sezzions for the web.</h1>
          <p className="shell-copy">
            Sign in with Google to open your workspace.
          </p>
          <div className="toolbar-row">
            <button className="primary-button" type="button" onClick={auth.handleGoogleSignIn}>Continue With Google</button>
            <a className="ghost-button" href="/#/migration">Open Migration Upload</a>
          </div>
        </div>

        <aside className="workspace-panel auth-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Account</p>
              <h2>{auth.sessionEmail || "Sign in"}</h2>
            </div>
          </div>
          <dl className="detail-grid compact-grid">
            <div><dt>Authentication</dt><dd>{auth.authMessage}</dd></div>
            <div><dt>API handshake</dt><dd>{auth.apiStatus}</dd></div>
            <div><dt>Hosted bootstrap</dt><dd>{auth.hostedStatus}</dd></div>
            <div><dt>Import planning</dt><dd>{auth.importPlanStatus}</dd></div>
          </dl>
        </aside>
      </header>
    </div>
  );
}
