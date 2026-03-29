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

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || null;

export default function App() {
  const [sessionEmail, setSessionEmail] = useState(null);
  const [authMessage, setAuthMessage] = useState(
    supabaseConfigured ? "Sign in with Google to activate the hosted web shell." : supabaseConfigError
  );

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
    setAuthMessage("Signed out. Sign in with Google to reactivate the hosted web shell.");
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
      </main>
    </div>
  );
}