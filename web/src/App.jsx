import { useEffect, useMemo, useState } from "react";

import { supabase, supabaseConfigError, supabaseConfigured } from "./lib/supabaseClient";
import "./styles.css";

const setupTabs = [
  { key: "users", label: "Users", enabled: true },
  { key: "sites", label: "Sites", enabled: false },
  { key: "cards", label: "Cards", enabled: false },
  { key: "method-types", label: "Method Types", enabled: false },
  { key: "redemption-methods", label: "Redemption Methods", enabled: false },
  { key: "game-types", label: "Game Types", enabled: false },
  { key: "games", label: "Games", enabled: false },
  { key: "tools", label: "Tools", enabled: false }
];

const initialUserForm = {
  name: "",
  email: "",
  notes: "",
  is_active: true
};

const oauthReturnRouteStorageKey = "sezzions.oauthReturnRoute";

function readCurrentRoute() {
  const hashRoute = window.location.hash.replace(/^#/, "").replace(/\/+$/, "") || "";
  const pathRoute = window.location.pathname.replace(/\/+$/, "") || "/";
  return hashRoute || pathRoute;
}

function rememberOAuthReturnRoute(route) {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  window.sessionStorage.setItem(oauthReturnRouteStorageKey, route);
}

function consumeOAuthReturnRoute() {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  const route = window.sessionStorage.getItem(oauthReturnRouteStorageKey);
  if (route) {
    window.sessionStorage.removeItem(oauthReturnRouteStorageKey);
  }
  return route;
}

function applyRoute(route) {
  if (typeof window === "undefined" || !route) {
    return;
  }
  const normalizedRoute = route === "/" ? "/" : route.replace(/\/+$/, "");
  const nextHash = normalizedRoute === "/" ? "#/" : `#${normalizedRoute}`;
  if (window.location.hash !== nextHash) {
    window.location.hash = nextHash;
  }
}

function describeFetchFailure(error, fallback) {
  if (error instanceof TypeError && /failed to fetch/i.test(error.message)) {
    return `${fallback} Verify that the hosted API URL is reachable from the browser and that CORS is allowing this origin.`;
  }

  return error instanceof Error ? error.message : fallback;
}

function downloadUsersCsv(users) {
  const rows = [
    ["Name", "Email", "Status", "Notes"],
    ...users.map((user) => [
      user.name,
      user.email || "",
      user.is_active ? "Active" : "Inactive",
      user.notes || ""
    ])
  ];
  const csv = rows
    .map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `users_${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function UserModal({ mode, user, form, setForm, onClose, onSubmit, submitError, suggestions }) {
  const readOnly = mode === "view";
  const title = mode === "create" ? "Add User" : mode === "edit" ? "Edit User" : "View User";
  const nameInvalid = !form.name.trim();

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <p className="section-kicker">Setup / Users</p>
            <h2 id="user-modal-title">{title}</h2>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            Close
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
              value={form.name}
              readOnly={readOnly}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
            <datalist id="user-name-suggestions">
              {suggestions.names.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {nameInvalid ? <p className="field-error">Name is required.</p> : null}
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

        <div className="modal-actions">
          {!readOnly ? (
            <button className="primary-button" type="button" onClick={onSubmit} disabled={nameInvalid}>
              Save User
            </button>
          ) : null}
          {mode === "view" && user ? (
            <div className="view-summary">
              <span>{user.email || "No email"}</span>
              <span>{user.is_active ? "Active" : "Inactive"}</span>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

export default function App() {
  const [currentRoute, setCurrentRoute] = useState(() => readCurrentRoute());
  const isMigrationPage = currentRoute === "/migration";
  const [sessionEmail, setSessionEmail] = useState(null);
  const [authMessage, setAuthMessage] = useState(
    supabaseConfigured ? "Sign in with Google to activate the hosted Sezzions workspace." : supabaseConfigError
  );
  const [apiStatus, setApiStatus] = useState("Protected API handshake will run after Google sign-in.");
  const [hostedStatus, setHostedStatus] = useState(
    "Hosted account bootstrap will run after the protected API handshake."
  );
  const [importPlanStatus, setImportPlanStatus] = useState(
    "Hosted import planning will run after workspace bootstrap."
  );
  const [hostedSummary, setHostedSummary] = useState(null);
  const [importPlanSummary, setImportPlanSummary] = useState(null);
  const [uploadSummary, setUploadSummary] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(
    "Upload a SQLite database to inspect it for hosted migration planning."
  );
  const [selectedUploadFile, setSelectedUploadFile] = useState(null);
  const [setupTab, setSetupTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [usersStatus, setUsersStatus] = useState("Sign in to load hosted users.");
  const [usersSearch, setUsersSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [userModalMode, setUserModalMode] = useState(null);
  const [userForm, setUserForm] = useState(initialUserForm);
  const [userSubmitError, setUserSubmitError] = useState(null);
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || null;
  const supabaseApiKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || null;
  const hasAuthenticatedSession = Boolean(sessionEmail);
  const hostedWorkspaceReady = Boolean(hostedSummary);
  const workspaceName = hostedSummary?.workspace?.name || (sessionEmail ? `${sessionEmail} Workspace` : "Hosted Workspace");
  const accountOwner = hostedSummary?.account?.owner_email || sessionEmail || "Not signed in";
  const accountRole = hostedSummary?.account?.role || "Pending bootstrap";
  const accountStatus = hostedSummary?.account?.status || "Pending bootstrap";

  const filteredUsers = useMemo(() => {
    const searchText = usersSearch.trim().toLowerCase();
    if (!searchText) {
      return users;
    }

    return users.filter((user) =>
      user.name.toLowerCase().includes(searchText)
      || (user.email || "").toLowerCase().includes(searchText)
      || (user.notes || "").toLowerCase().includes(searchText)
    );
  }, [users, usersSearch]);

  const selectedUser = filteredUsers.find((user) => user.id === selectedUserId)
    || users.find((user) => user.id === selectedUserId)
    || null;

  const userSuggestions = useMemo(() => ({
    names: [...new Set(users.map((user) => user.name).filter(Boolean))],
    emails: [...new Set(users.map((user) => user.email).filter(Boolean))]
  }), [users]);

  function authHeaders(accessToken) {
    return {
      Authorization: `Bearer ${accessToken}`,
      ...(supabaseApiKey ? { apikey: supabaseApiKey } : {})
    };
  }

  async function getAccessToken() {
    if (!supabase?.auth) {
      return null;
    }

    const { data, error } = await supabase.auth.getSession();
    if (error) {
      throw error;
    }

    return data.session?.access_token || null;
  }

  async function loadUsers(accessToken) {
    if (!accessToken) {
      setUsers([]);
      setUsersStatus("Sign in to load hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setUsers([]);
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    setUsersStatus("Loading hosted users...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/users`, {
        headers: authHeaders(accessToken)
      });
      const payload = await response.json();

      if (!response.ok) {
        setUsers([]);
        setUsersStatus(payload.detail || `Hosted users failed to load (${response.status}).`);
        return;
      }

      setUsers(payload.users || []);
      setUsersStatus(payload.users?.length ? "Hosted users ready." : "No hosted users yet. Add your first user to get started.");
      setSelectedUserId((current) => ((payload.users || []).some((user) => user.id === current) ? current : null));
    } catch (error) {
      setUsers([]);
      setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
    }
  }

  function openUserModal(mode, user = null) {
    setUserModalMode(mode);
    setUserSubmitError(null);

    if (user) {
      setUserForm({
        name: user.name || "",
        email: user.email || "",
        notes: user.notes || "",
        is_active: Boolean(user.is_active)
      });
      setSelectedUserId(user.id);
      return;
    }

    setUserForm(initialUserForm);
  }

  async function submitUserModal() {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      setUserSubmitError("Google sign-in is required before managing hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setUserSubmitError("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    const payload = {
      name: userForm.name,
      email: userForm.email || null,
      notes: userForm.notes || null,
      ...(userModalMode === "edit" ? { is_active: userForm.is_active } : {})
    };
    const url = userModalMode === "edit" && selectedUser
      ? `${apiBaseUrl}/v1/workspace/users/${selectedUser.id}`
      : `${apiBaseUrl}/v1/workspace/users`;
    const method = userModalMode === "edit" ? "PATCH" : "POST";

    try {
      const response = await fetch(url, {
        method,
        headers: {
          ...authHeaders(accessToken),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      const data = await response.json();

      if (!response.ok) {
        setUserSubmitError(data.detail || `Hosted users save failed (${response.status}).`);
        return;
      }

      setUsers((current) => {
        if (method === "POST") {
          return [...current, data].sort((left, right) => left.name.localeCompare(right.name));
        }

        return current
          .map((user) => (user.id === data.id ? data : user))
          .sort((left, right) => left.name.localeCompare(right.name));
      });
      setSelectedUserId(data.id);
      setUsersStatus("Hosted users ready.");
      setUserModalMode(null);
      setUserForm(initialUserForm);
      setUserSubmitError(null);
    } catch (error) {
      setUserSubmitError(describeFetchFailure(error, "Hosted users save failed."));
    }
  }

  async function handleUsersRefresh() {
    try {
      const accessToken = await getAccessToken();
      await loadUsers(accessToken);
    } catch (error) {
      setUsersStatus(describeFetchFailure(error, "Hosted users failed to load."));
    }
  }

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

      if (!apiBaseUrl) {
        setUploadSummary(null);
        setUploadStatus("Set VITE_API_BASE_URL to enable SQLite upload planning.");
        return;
      }

      setUploadStatus("Uploading SQLite file for hosted migration planning...");
      const formData = new FormData();
      formData.append("sqlite_db", selectedUploadFile);

      const response = await fetch(`${apiBaseUrl}/v1/workspace/import-upload-plan`, {
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

  async function syncWorkspaceImportPlan(nextSession) {
    if (!nextSession?.access_token) {
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      return;
    }

    if (!apiBaseUrl) {
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      return;
    }

    setImportPlanStatus("Loading hosted workspace import planning status...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/import-plan`, {
        headers: authHeaders(nextSession.access_token)
      });

      const data = await response.json();
      if (!response.ok) {
        setImportPlanSummary(null);
        setImportPlanStatus(data.detail || `Hosted import planning failed (${response.status}).`);
        return;
      }

      setImportPlanSummary(data);
      setImportPlanStatus(data.detail || "Hosted import planning is ready.");
    } catch (error) {
      setImportPlanSummary(null);
      setImportPlanStatus(describeFetchFailure(error, "Hosted import planning failed."));
    }
  }

  async function syncHostedBootstrap(nextSession) {
    if (!nextSession?.access_token) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersStatus("Sign in to load hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      setUsers([]);
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    setHostedStatus("Bootstrapping the hosted Sezzions account workspace...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/account/bootstrap`, {
        method: "POST",
        headers: authHeaders(nextSession.access_token)
      });
      const data = await response.json();

      if (!response.ok) {
        setHostedSummary(null);
        setImportPlanSummary(null);
        setUsers([]);
        setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
        setUsersStatus("Hosted users will load after workspace bootstrap.");
        setHostedStatus(data.detail || `Hosted account bootstrap failed (${response.status}).`);
        return;
      }

      setHostedSummary(data);
      setHostedStatus(
        data.created_account || data.created_workspace
          ? "Hosted account workspace created and ready."
          : "Hosted account workspace ready."
      );

      await Promise.all([
        syncWorkspaceImportPlan(nextSession),
        loadUsers(nextSession.access_token)
      ]);
    } catch (error) {
      setHostedSummary(null);
      setImportPlanSummary(null);
      setUsers([]);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsersStatus("Hosted users will load after workspace bootstrap.");
      setHostedStatus(describeFetchFailure(error, "Hosted account bootstrap could not reach the hosted API."));
    }
  }

  async function syncProtectedApi(nextSession) {
    if (!nextSession?.access_token) {
      setApiStatus("Protected API handshake will run after Google sign-in.");
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersStatus("Sign in to load hosted users.");
      return;
    }

    if (!apiBaseUrl) {
      setApiStatus("Set VITE_API_BASE_URL to enable the protected API handshake.");
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
      setUsers([]);
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }

    setApiStatus("Calling the protected Render API with the Supabase session token...");
    try {
      const response = await fetch(`${apiBaseUrl}/v1/session`, {
        headers: authHeaders(nextSession.access_token)
      });
      const data = await response.json();

      if (!response.ok) {
        setApiStatus(data.detail || `Protected API handshake failed (${response.status}).`);
        return;
      }

      setApiStatus(`Protected API handshake ready for ${data.email || data.user_id}.`);
      await syncHostedBootstrap(nextSession);
    } catch (error) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
      setUsers([]);
      setUsersStatus("Sign in to load hosted users.");
      setApiStatus(describeFetchFailure(error, "Protected API handshake could not reach the hosted API."));
    }
  }

  async function handleRetryHostedConnection() {
    if (!supabase?.auth) {
      setAuthMessage(supabaseConfigError);
      return;
    }

    try {
      const { data, error } = await supabase.auth.getSession();
      if (error) {
        setApiStatus(error.message);
        return;
      }

      await syncProtectedApi(data.session || null);
    } catch (error) {
      setApiStatus(describeFetchFailure(error, "Protected API handshake could not reach the hosted API."));
    }
  }

  useEffect(() => {
    function syncRoute() {
      setCurrentRoute(readCurrentRoute());
    }

    window.addEventListener("hashchange", syncRoute);
    window.addEventListener("popstate", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
      window.removeEventListener("popstate", syncRoute);
    };
  }, []);

  useEffect(() => {
    if (!supabase) {
      return undefined;
    }

    let cancelled = false;

    supabase.auth.getSession().then(({ data, error }) => {
      if (cancelled) {
        return;
      }

      if (error) {
        setAuthMessage(error.message);
        return;
      }

      const email = data.session?.user?.email || null;
      if (data.session?.access_token) {
        const pendingRoute = consumeOAuthReturnRoute();
        if (pendingRoute && pendingRoute !== readCurrentRoute()) {
          applyRoute(pendingRoute);
        }
      }
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. Hosted Sezzions is ready."
          : "Sign in with Google to activate the hosted Sezzions workspace."
      );
      void syncProtectedApi(data.session || null);
    });

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      const email = nextSession?.user?.email || null;
      if (nextSession?.access_token) {
        const pendingRoute = consumeOAuthReturnRoute();
        if (pendingRoute && pendingRoute !== readCurrentRoute()) {
          applyRoute(pendingRoute);
        }
      }
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. Hosted Sezzions is ready."
          : "Sign in with Google to activate the hosted Sezzions workspace."
      );
      void syncProtectedApi(nextSession || null);
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, []);

  async function handleGoogleSignIn() {
    if (!supabase) {
      setAuthMessage(supabaseConfigError);
      return;
    }

    rememberOAuthReturnRoute(readCurrentRoute());

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin
      }
    });

    if (error) {
      setAuthMessage(error.message);
    }
  }

  async function handleSignOut() {
    if (!supabase) {
      return;
    }

    const { error } = await supabase.auth.signOut();
    if (error) {
      setAuthMessage(error.message);
      return;
    }

    setSessionEmail(null);
    setHostedSummary(null);
    setImportPlanSummary(null);
    setUploadSummary(null);
    setSelectedUploadFile(null);
    setUsers([]);
    setSelectedUserId(null);
    setUserModalMode(null);
    setUserForm(initialUserForm);
    setAuthMessage("Signed out. Sign in with Google to reactivate the hosted workspace.");
    setApiStatus("Protected API handshake will run after Google sign-in.");
    setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
    setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
    setUploadStatus("Upload a SQLite database to inspect it for hosted migration planning.");
    setUsersStatus("Sign in to load hosted users.");
  }

  async function handleDeleteUser(user) {
    const accessToken = await getAccessToken();
    if (!user || !accessToken) {
      setUsersStatus("Google sign-in is required before managing hosted users.");
      return;
    }
    if (!apiBaseUrl) {
      setUsersStatus("Set VITE_API_BASE_URL to enable hosted users.");
      return;
    }
    if (!window.confirm(`Delete user '${user.name}'? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`${apiBaseUrl}/v1/workspace/users/${user.id}`, {
        method: "DELETE",
        headers: authHeaders(accessToken)
      });
      if (!response.ok) {
        const detail = response.headers.get("content-type")?.includes("application/json")
          ? (await response.json()).detail
          : `Hosted users delete failed (${response.status}).`;
        setUsersStatus(detail || `Hosted users delete failed (${response.status}).`);
        return;
      }

      setUsers((current) => current.filter((candidate) => candidate.id !== user.id));
      setSelectedUserId((current) => (current === user.id ? null : current));
      setUserModalMode(null);
      setUsersStatus("Hosted users ready.");
    } catch (error) {
      setUsersStatus(describeFetchFailure(error, "Hosted users delete failed."));
    }
  }

  if (isMigrationPage) {
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
            <a className="ghost-button" href="/#/">Back to Hosted App</a>
            {sessionEmail ? (
              <button className="ghost-button" type="button" onClick={handleSignOut}>Sign Out</button>
            ) : (
              <button className="primary-button" type="button" onClick={handleGoogleSignIn}>Continue With Google</button>
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

  if (!sessionEmail) {
    return (
      <div className="marketing-shell">
        <header className="marketing-hero">
          <div className="marketing-copy">
            <p className="section-kicker">Sezzions Hosted</p>
            <h1>Hosted Sezzions is ready for the first true app slice.</h1>
            <p className="shell-copy">
              Sign in with Google to open the hosted workspace shell, bootstrap your account, and begin porting the real Setup workflow into the browser.
            </p>
            <div className="toolbar-row">
              <button className="primary-button" type="button" onClick={handleGoogleSignIn}>Continue With Google</button>
              <a className="ghost-button" href="/#/migration">Open Migration Upload</a>
            </div>
          </div>

          <aside className="workspace-panel auth-panel">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Auth state</p>
                <h2>{sessionEmail || "Not signed in"}</h2>
              </div>
            </div>
            <dl className="detail-grid compact-grid">
              <div><dt>Authentication</dt><dd>{authMessage}</dd></div>
              <div><dt>API handshake</dt><dd>{apiStatus}</dd></div>
              <div><dt>Hosted bootstrap</dt><dd>{hostedStatus}</dd></div>
              <div><dt>Import planning</dt><dd>{importPlanStatus}</dd></div>
            </dl>
          </aside>
        </header>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar-shell">
        <div>
          <p className="sidebar-brand">Sezzions</p>
          <h1 className="sidebar-heading">Hosted Workspace</h1>
          <p className="sidebar-copy">Faithful desktop-style slices, ported onto the hosted backend one workflow at a time.</p>
        </div>

        <nav className="primary-nav" aria-label="Primary navigation">
          <button className="primary-nav-item active" type="button">Setup</button>
        </nav>

        <div className="sidebar-footer">
          <dl className="detail-grid compact-grid">
            <div><dt>Account</dt><dd>{accountOwner}</dd></div>
            <div><dt>Role</dt><dd>{accountRole}</dd></div>
            <div><dt>Status</dt><dd>{accountStatus}</dd></div>
            <div><dt>Workspace</dt><dd>{workspaceName}</dd></div>
          </dl>
          <button className="ghost-button full-width" type="button" onClick={handleSignOut}>Sign Out</button>
        </div>
      </aside>

      <main className="workspace-shell">
        <header className="workspace-header">
          <div>
            <p className="section-kicker">Setup</p>
            <h2>Users</h2>
            <p className="status-note">
              {hostedWorkspaceReady
                ? "Start with hosted users before sites and cards so later setup slices attach to real workspace-owned people."
                : "You are signed in, but the hosted backend is not connected yet. Retry the hosted connection after verifying the API deployment and browser access."}
            </p>
          </div>
          <div className="header-actions">
            <button className="ghost-button" type="button" onClick={handleRetryHostedConnection}>Retry Hosted Connection</button>
            <a className="ghost-button" href="/#/migration">Migration Upload</a>
          </div>
        </header>

        <section className="workspace-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Hosted Status</p>
              <h2>Connection</h2>
            </div>
          </div>
          <dl className="detail-grid compact-grid">
            <div><dt>Authentication</dt><dd>{authMessage}</dd></div>
            <div><dt>API handshake</dt><dd>{apiStatus}</dd></div>
            <div><dt>Hosted bootstrap</dt><dd>{hostedStatus}</dd></div>
            <div><dt>Import planning</dt><dd>{importPlanStatus}</dd></div>
          </dl>
        </section>

        <section className="workspace-panel setup-panel">
          <div className="subtab-row" role="tablist" aria-label="Setup sections">
            {setupTabs.map((tab) => (
              <button
                key={tab.key}
                className={tab.key === setupTab ? "subtab-button active" : "subtab-button"}
                type="button"
                role="tab"
                aria-selected={tab.key === setupTab}
                disabled={!tab.enabled}
                onClick={() => setSetupTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {setupTab === "users" ? (
            <section className="users-surface" aria-label="Setup Users">
              <div className="panel-header sticky-tools">
                <div>
                  <p className="section-kicker">Setup / Users</p>
                  <h2>Users</h2>
                </div>
                <div className="toolbar-row wrap-toolbar">
                  <button className="primary-button" type="button" onClick={() => openUserModal("create")} disabled={!hostedWorkspaceReady}>Add User</button>
                  <button className="ghost-button" type="button" onClick={() => selectedUser && openUserModal("view", selectedUser)} disabled={!hostedWorkspaceReady || !selectedUser}>View</button>
                  <button className="ghost-button" type="button" onClick={() => selectedUser && openUserModal("edit", selectedUser)} disabled={!hostedWorkspaceReady || !selectedUser}>Edit</button>
                  <button className="ghost-button" type="button" onClick={() => selectedUser && handleDeleteUser(selectedUser)} disabled={!hostedWorkspaceReady || !selectedUser}>Delete</button>
                  <button className="ghost-button" type="button" onClick={() => downloadUsersCsv(filteredUsers)} disabled={!filteredUsers.length}>Export CSV</button>
                  <button className="ghost-button" type="button" onClick={handleUsersRefresh} disabled={!hostedWorkspaceReady}>Refresh</button>
                </div>
              </div>

              <div className="users-toolbar-grid">
                <div className="search-stack">
                  <label className="field-label-left" htmlFor="users-search-input">Search users</label>
                  <div className="search-row">
                    <input
                      id="users-search-input"
                      className="text-input"
                      type="search"
                      placeholder="Search users..."
                      value={usersSearch}
                      disabled={!hostedWorkspaceReady}
                      onChange={(event) => setUsersSearch(event.target.value)}
                    />
                    <button className="ghost-button" type="button" onClick={() => setUsersSearch("")} disabled={!usersSearch}>Clear</button>
                  </div>
                </div>
                <div className="status-card">
                  <dt>Workspace users</dt>
                  <dd>{usersStatus}</dd>
                </div>
              </div>

              <div className="table-shell">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Status</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.length ? filteredUsers.map((user) => (
                      <tr
                        key={user.id}
                        className={selectedUserId === user.id ? "selected-row" : undefined}
                        onClick={() => setSelectedUserId(user.id)}
                        onDoubleClick={() => openUserModal("view", user)}
                      >
                        <td>{user.name}</td>
                        <td>{user.email || ""}</td>
                        <td>
                          <span className={user.is_active ? "status-chip active" : "status-chip inactive"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td>{(user.notes || "").slice(0, 100)}</td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan="4" className="empty-state-cell">
                          {hostedWorkspaceReady
                            ? "No users match the current view yet."
                            : "Finish the hosted connection to load workspace users."}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </section>
      </main>

      {userModalMode ? (
        <UserModal
          mode={userModalMode}
          user={selectedUser}
          form={userForm}
          setForm={setUserForm}
          submitError={userSubmitError}
          suggestions={userSuggestions}
          onClose={() => {
            setUserModalMode(null);
            setUserSubmitError(null);
          }}
          onSubmit={submitUserModal}
        />
      ) : null}
    </div>
  );
}