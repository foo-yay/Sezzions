import { useEffect, useState } from "react";

import { supabase, supabaseConfigured, supabaseConfigError } from "./lib/supabaseClient";
import "./styles.css";

const milestones = [
  {
    title: "Shared backend",
    detail: "Web and desktop will eventually consume the same hosted API instead of duplicating accounting logic."
  },
  {
    title: "Tenant-aware accounts",
    detail: "The browser app is being shaped around account-level ownership so each Sezzions customer gets isolated data."
  },
  {
    title: "Staged rollout",
    detail: "Development deploys land on the dev host first, while production remains a separate promotion step."
  }
];

const surfaces = [
  {
    label: "Desktop",
    summary: "Current production workflow for power users and deep accounting tools."
  },
  {
    label: "Web",
    summary: "New browser surface for hosted sign-in, review flows, and shared backend access."
  },
  {
    label: "Backend",
    summary: "Future hosted API and database layer that becomes the single source of truth for both clients."
  }
];

const launchPlan = [
  "Google sign-in is now wired through Supabase from the web shell.",
  "Connect the authenticated shell to the hosted API on Render.",
  "Port feature areas incrementally without rewriting accounting rules twice."
];

export default function App() {
  const [sessionEmail, setSessionEmail] = useState(null);
  const [hostedSummary, setHostedSummary] = useState(null);
  const [authMessage, setAuthMessage] = useState(
    supabaseConfigured ? "Sign in with Google to activate the hosted web shell." : supabaseConfigError
  );
  const [apiStatus, setApiStatus] = useState(
    "Protected API handshake will run after Google sign-in."
  );
  const [hostedStatus, setHostedStatus] = useState(
    "Hosted account bootstrap will run after the protected API handshake."
  );
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || null;
  const supabaseApiKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() || null;

  async function syncHostedBootstrap(nextSession) {
    if (!nextSession?.access_token) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      return;
    }

    if (!apiBaseUrl) {
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      return;
    }

    setHostedStatus("Bootstrapping the hosted Sezzions account workspace...");

    try {
      const response = await fetch(`${apiBaseUrl}/v1/account/bootstrap`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${nextSession.access_token}`,
          ...(supabaseApiKey ? { apikey: supabaseApiKey } : {})
        }
      });

      if (!response.ok) {
        setHostedSummary(null);
        setHostedStatus(`Hosted account bootstrap failed (${response.status}).`);
        return;
      }

      const data = await response.json();
      setHostedSummary(data);
      setHostedStatus(
        data.created_account || data.created_workspace
          ? "Hosted account workspace created and ready."
          : "Hosted account workspace ready."
      );
    } catch (error) {
      setHostedSummary(null);
      setHostedStatus(error instanceof Error ? error.message : "Hosted account bootstrap failed.");
    }
  }

  async function syncProtectedApi(nextSession) {
    if (!nextSession?.access_token) {
      setApiStatus("Protected API handshake will run after Google sign-in.");
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      return;
    }

    if (!apiBaseUrl) {
      setApiStatus("Set VITE_API_BASE_URL to enable the protected API handshake.");
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      return;
    }

    setApiStatus("Calling the protected Render API with the Supabase session token...");

    try {
      const response = await fetch(`${apiBaseUrl}/v1/session`, {
        headers: {
          Authorization: `Bearer ${nextSession.access_token}`,
          ...(supabaseApiKey ? { apikey: supabaseApiKey } : {})
        }
      });

      if (!response.ok) {
        setApiStatus(`Protected API handshake failed (${response.status}).`);
        return;
      }

      const data = await response.json();
      setApiStatus(
        `Protected API handshake ready for ${data.email || data.user_id}.`
      );
      await syncHostedBootstrap(nextSession);
    } catch (error) {
      setHostedSummary(null);
      setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
      setApiStatus(error instanceof Error ? error.message : "Protected API handshake failed.");
    }
  }

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
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. The web app is ready for the first authenticated API call."
          : "Sign in with Google to activate the hosted web shell."
      );
      void syncProtectedApi(data.session || null);
    });

    const {
      data: { subscription }
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      const email = nextSession?.user?.email || null;
      setSessionEmail(email);
      setAuthMessage(
        email
          ? "Google session active. The web app is ready for the first authenticated API call."
          : "Sign in with Google to activate the hosted web shell."
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
    setAuthMessage("Signed out. Sign in with Google to reactivate the hosted web shell.");
    setApiStatus("Protected API handshake will run after Google sign-in.");
    setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
  }

  return (
    <div className="shell">
      <div className="ambient ambient-left" aria-hidden="true" />
      <div className="ambient ambient-right" aria-hidden="true" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Sezzions</p>
          <h1>Sezzions Web Control Tower</h1>
          <p className="lede">
            The browser client now includes the first real hosted-auth path. This shell is ready
            to establish a Google session through Supabase and become the front door for the
            shared Sezzions backend.
          </p>
          <div className="hero-actions">
            <button className="primary-link action-button" type="button" onClick={handleGoogleSignIn}>
              Continue With Google
            </button>
            <span className="status-pill">
              {sessionEmail ? "Google session live" : "Awaiting Google sign-in"}
            </span>
          </div>
        </div>

        <aside className="hero-aside">
          <p className="aside-label">Auth state</p>
          <strong>{sessionEmail || "Not signed in"}</strong>
          <p>
            {authMessage}
          </p>
          <dl className="aside-meta">
            <div>
              <dt>Web host</dt>
              <dd>dev.sezzions.com</dd>
            </div>
            <div>
              <dt>API host</dt>
              <dd>{apiBaseUrl || "Set VITE_API_BASE_URL"}</dd>
            </div>
            <div>
              <dt>API handshake</dt>
              <dd>{apiStatus}</dd>
            </div>
            <div>
              <dt>Hosted bootstrap</dt>
              <dd>{hostedStatus}</dd>
            </div>
          </dl>
          {sessionEmail ? (
            <button className="secondary-button" type="button" onClick={handleSignOut}>
              Sign Out
            </button>
          ) : null}
        </aside>
      </header>

      <main className="content-grid">
        <section className="panel feature-panel">
          <div className="panel-head">
            <p className="panel-kicker">Auth rollout</p>
            <h2>How Google sign-in fits the product</h2>
          </div>
          <div className="milestone-grid">
            {milestones.map((milestone) => (
              <article key={milestone.title} className="milestone-card">
                <h3>{milestone.title}</h3>
                <p>{milestone.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel surfaces-panel">
          <div className="panel-head">
            <p className="panel-kicker">Connected surfaces</p>
            <h2>One product, one identity layer</h2>
          </div>
          <div className="surface-stack">
            {surfaces.map((surface) => (
              <article key={surface.label} className="surface-row">
                <h3>{surface.label}</h3>
                <p>{surface.summary}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel launch-panel">
          <div className="panel-head">
            <p className="panel-kicker">Launch sequence</p>
            <h2>Immediate authenticated next steps</h2>
          </div>
          <ol className="launch-list">
            {launchPlan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="launch-note">
            After Google sign-in is live, the next slice is a protected call into the Render API
            and then the first controlled import of desktop data from the local SQLite source.
          </p>
        </section>

        <section className="panel launch-panel">
          <div className="panel-head">
            <p className="panel-kicker">Hosted account</p>
            <h2>Authenticated workspace bootstrap</h2>
          </div>
          {hostedSummary ? (
            <dl className="aside-meta">
              <div>
                <dt>Hosted account owner</dt>
                <dd>{hostedSummary.account.owner_email}</dd>
              </div>
              <div>
                <dt>Auth provider</dt>
                <dd>{hostedSummary.account.auth_provider}</dd>
              </div>
              <div>
                <dt>Workspace</dt>
                <dd>{hostedSummary.workspace.name}</dd>
              </div>
              <div>
                <dt>Bootstrap result</dt>
                <dd>{hostedStatus}</dd>
              </div>
            </dl>
          ) : (
            <p className="launch-note">{hostedStatus}</p>
          )}
        </section>
      </main>
    </div>
  );
}