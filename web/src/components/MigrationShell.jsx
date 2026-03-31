import { useState } from "react";
import { Link } from "react-router-dom";

import { authHeaders, describeFetchFailure, getAccessToken } from "../services/api";

export default function MigrationShell({ auth }) {
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(
    "Upload a SQLite database to inspect it for hosted migration planning."
  );
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);

  async function handleMigrationUpload() {
    if (!selectedUploadFile) {
      setUploadSummary(null);
      setUploadStatus("Choose a SQLite database file before uploading.");
      return;
    }

    try {
      const accessToken = await getAccessToken();
      if (!accessToken) {
        setUploadSummary(null);
        setUploadStatus("Google sign-in is required before uploading a SQLite file.");
        return;
      }

      if (!auth.apiBaseUrl) {
        setUploadSummary(null);
        setUploadStatus("Set VITE_API_BASE_URL to enable SQLite upload planning.");
        return;
      }

      setUploadStatus("Uploading SQLite file for hosted migration planning...");
      const formData = new FormData();
      formData.append("sqlite_db", selectedUploadFile);

      const response = await fetch(`${auth.apiBaseUrl}/v1/workspace/import-upload-plan`, {
        method: "POST",
        headers: authHeaders(accessToken),
        body: formData
      });
      const payload = await response.json();

      if (!response.ok) {
        setUploadSummary(null);
        setUploadStatus(payload.detail || `SQLite upload planning failed (${response.status}).`);
        return;
      }

      setUploadSummary(payload);
      setUploadStatus(payload.detail || "Uploaded SQLite inventory is ready.");
    } catch (error) {
      setUploadSummary(null);
      setUploadStatus(describeFetchFailure(error, "SQLite upload planning failed."));
    }
  }

  return (
    <div className="migration-shell">
      <header className="migration-hero">
        <div>
          <p className="section-kicker">Sezzions Migration</p>
          <h1>Temporary SQLite Upload Planning</h1>
          <p className="shell-copy">
            Use this authenticated bridge to inspect a local Sezzions SQLite database for hosted migration planning.
          </p>
        </div>
        <div className="migration-actions">
          <Link className="ghost-button" to="/">Back to Hosted App</Link>
          {auth.sessionEmail ? (
            <button className="ghost-button" type="button" onClick={auth.handleSignOut}>Sign Out</button>
          ) : (
            <button className="primary-button" type="button" onClick={auth.handleGoogleSignIn}>Continue With Google</button>
          )}
        </div>
      </header>

      <main className="migration-grid">
        <section className="workspace-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Upload bridge</p>
              <h2>Inspect a local SQLite database</h2>
            </div>
          </div>
          <label className="field-label-left" htmlFor="sqlite-upload-input">SQLite database file</label>
          <input
            id="sqlite-upload-input"
            className="text-input"
            type="file"
            accept=".db,.sqlite,.sqlite3,application/octet-stream"
            onChange={(event) => setSelectedUploadFile(event.target.files?.[0] || null)}
          />
          <div className="toolbar-row">
            <button className="primary-button" type="button" onClick={handleMigrationUpload}>Upload SQLite For Planning</button>
          </div>
          <p className="status-note">{uploadStatus}</p>
        </section>

        <section className="workspace-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Inventory</p>
              <h2>Uploaded SQLite inspection</h2>
            </div>
          </div>
          {uploadSummary ? (
            <dl className="detail-grid compact-grid">
              <div><dt>Uploaded file</dt><dd>{uploadSummary.uploaded_filename}</dd></div>
              <div><dt>Status</dt><dd>{uploadSummary.status}</dd></div>
              <div><dt>Active users discovered</dt><dd>{uploadSummary.inventory?.active_user_names?.join(", ") || "None"}</dd></div>
              <div><dt>Sites discovered</dt><dd>{uploadSummary.inventory?.site_names?.join(", ") || "None"}</dd></div>
            </dl>
          ) : (
            <p className="status-note">Upload a SQLite file to inspect it here.</p>
          )}
        </section>
      </main>
    </div>
  );
}
