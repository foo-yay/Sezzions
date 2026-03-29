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
  "Stand up the frontend shell and deployment lane.",
  "Introduce the hosted API surface and auth flow.",
  "Port feature areas incrementally without rewriting accounting rules twice."
];

export default function App() {
  return (
    <div className="shell">
      <div className="ambient ambient-left" aria-hidden="true" />
      <div className="ambient ambient-right" aria-hidden="true" />

      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Sezzions</p>
          <h1>Sezzions Web Control Tower</h1>
          <p className="lede">
            The browser client is now a real frontend codebase instead of a static placeholder.
            This shell is the starting point for the hosted Sezzions experience and the future
            shared backend rollout.
          </p>
          <div className="hero-actions">
            <a className="primary-link" href="https://dev.sezzions.com">
              Development Environment Live
            </a>
            <span className="status-pill">Staging lane verified</span>
          </div>
        </div>

        <aside className="hero-aside">
          <p className="aside-label">Current deployment target</p>
          <strong>dev.sezzions.com</strong>
          <p>
            This frontend is built for static deployment today so the team can iterate on web UI
            while the hosted backend is introduced in controlled stages.
          </p>
        </aside>
      </header>

      <main className="content-grid">
        <section className="panel feature-panel">
          <div className="panel-head">
            <p className="panel-kicker">Roadmap</p>
            <h2>How the web app fits the product</h2>
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
            <p className="panel-kicker">Surfaces</p>
            <h2>One product, multiple clients</h2>
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
            <h2>Immediate next steps</h2>
          </div>
          <ol className="launch-list">
            {launchPlan.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </section>
      </main>
    </div>
  );
}