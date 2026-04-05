import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Icon from "./common/Icon";
import StatusModal from "./common/StatusModal";
import NotificationsModal from "./common/NotificationsModal";
import AccountModal from "./common/AccountModal";
import SettingsModal from "./common/SettingsModal";
import UsersTab from "./UsersTab/UsersTab";
import SitesTab from "./SitesTab/SitesTab";
import CardsTab from "./CardsTab/CardsTab";
import MethodTypesTab from "./MethodTypesTab/MethodTypesTab";
import RedemptionMethodsTab from "./RedemptionMethodsTab/RedemptionMethodsTab";
import GameTypesTab from "./GameTypesTab/GameTypesTab";
import GamesTab from "./GamesTab/GamesTab";
import PurchasesTab from "./PurchasesTab/PurchasesTab";

const setupTabs = [
  { key: "users", label: "Users", icon: "users", enabled: true },
  { key: "sites", label: "Sites", icon: "sites", enabled: true },
  { key: "cards", label: "Cards", icon: "cards", enabled: true },
  { key: "method-types", label: "Method Types", icon: "methodTypes", enabled: true },
  { key: "redemption-methods", label: "Redemption Methods", icon: "redemptionMethods", enabled: true },
  { key: "game-types", label: "Game Types", icon: "gameTypes", enabled: true },
  { key: "games", label: "Games", icon: "games", enabled: true },
  { key: "purchases", label: "Purchases", icon: "purchases", enabled: true },
  { key: "tools", label: "Tools", icon: "tools", enabled: false }
];

const validSetupKeys = new Set(setupTabs.map((t) => t.key));

export default function AppShell({ auth }) {
  const { tabKey } = useParams();
  const navigate = useNavigate();
  const activeTab = validSetupKeys.has(tabKey) ? tabKey : "users";

  const [railCollapsed, setRailCollapsed] = useState(false);
  const [setupNavOpen, setSetupNavOpen] = useState(true);
  const [notificationsModalOpen, setNotificationsModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [statusModalOpen, setStatusModalOpen] = useState(false);

  // Shell-level Escape handler for shell modals only
  useEffect(() => {
    const anyShellModalOpen = notificationsModalOpen || statusModalOpen || accountModalOpen || settingsModalOpen;
    if (!anyShellModalOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key !== "Escape") {
        return;
      }

      event.preventDefault();

      if (statusModalOpen) {
        setStatusModalOpen(false);
        return;
      }

      if (settingsModalOpen) {
        setSettingsModalOpen(false);
        return;
      }

      if (accountModalOpen) {
        setAccountModalOpen(false);
        return;
      }

      if (notificationsModalOpen) {
        setNotificationsModalOpen(false);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [accountModalOpen, notificationsModalOpen, settingsModalOpen, statusModalOpen]);

  return (
    <div className={railCollapsed ? "app-shell rail-collapsed" : "app-shell"}>
      <header className="app-topbar-shell" aria-label="Workspace header">
        <div className="app-topbar-left">
          <button
            className={railCollapsed ? "rail-side-toggle collapsed" : "rail-side-toggle"}
            type="button"
            aria-label={railCollapsed ? "Expand navigation" : "Collapse navigation"}
            title={railCollapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={() => setRailCollapsed((current) => !current)}
          >
            <span className="rail-side-toggle-glyph" aria-hidden="true"><Icon name="menu" className="app-icon" /></span>
          </button>
          <h1 className="app-shell-title"><span className="app-shell-brand">Sezzions</span><span className="app-shell-divider"> - </span><span className="app-shell-subtitle">Sweepstakes Session Tracker</span></h1>
        </div>

        <div className="topbar-actions utility-button-row">
          <button
            className={notificationsModalOpen ? "header-utility-button notifications-utility-button active" : "header-utility-button notifications-utility-button"}
            type="button"
            aria-label="Open notifications"
            title="Notifications"
            onClick={() => setNotificationsModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="notifications" className="app-icon" /></span>
          </button>
          <button
            className={accountModalOpen ? "header-utility-button account-utility-button active" : "header-utility-button account-utility-button"}
            type="button"
            aria-label="Open my account"
            title={auth.accountOwner}
            onClick={() => setAccountModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="account" className="app-icon" /></span>
          </button>
          <button
            className={settingsModalOpen ? "header-utility-button settings-utility-button active" : "header-utility-button settings-utility-button"}
            type="button"
            aria-label="Open settings"
            title="Settings"
            onClick={() => setSettingsModalOpen(true)}
          >
            <span aria-hidden="true"><Icon name="settings" className="app-icon" /></span>
          </button>
          <button
            className={statusModalOpen ? "header-utility-button status-utility-button active" : "header-utility-button status-utility-button"}
            type="button"
            onClick={() => setStatusModalOpen(true)}
            aria-label="Open hosted status"
            title="Hosted Status"
          >
            <span className={`status-dot ${auth.overallStatusTone}`} aria-hidden="true" />
          </button>
        </div>
      </header>

      <aside className={railCollapsed ? "workspace-rail collapsed" : "workspace-rail"}>
        <div className="rail-section-block">
          <button
            className="rail-group-toggle"
            type="button"
            aria-expanded={!railCollapsed && setupNavOpen}
            aria-label={railCollapsed ? "Expand setup navigation" : "Toggle setup navigation"}
            title="Setup"
            onClick={() => {
              if (railCollapsed) {
                setRailCollapsed(false);
                return;
              }
              setSetupNavOpen((current) => !current);
            }}
          >
            <span className="rail-nav-main">
              <span className="rail-item-icon" aria-hidden="true"><Icon name="setup" className="app-icon" /></span>
              {!railCollapsed ? <span className="rail-group-label">Setup</span> : null}
            </span>
            {!railCollapsed ? <span className="rail-group-icon" aria-hidden="true"><Icon name={setupNavOpen ? "chevronDown" : "chevronRight"} className="app-icon rail-chevron-icon" /></span> : null}
          </button>

          {!railCollapsed && setupNavOpen ? (
            <nav className="rail-nav rail-subnav" aria-label="Setup navigation">
              {setupTabs.map((tab) => (
                <button
                  key={tab.key}
                  className={tab.key === activeTab ? "rail-nav-button rail-subnav-button active" : "rail-nav-button rail-subnav-button"}
                  type="button"
                  aria-current={tab.key === activeTab ? "page" : undefined}
                  aria-label={tab.label}
                  title={tab.label}
                  disabled={!tab.enabled}
                  onClick={() => navigate(`/setup/${tab.key}`)}
                >
                  <span className="rail-nav-main">
                    <span className="rail-item-icon" aria-hidden="true"><Icon name={tab.icon} className="app-icon" /></span>
                    <span className="rail-nav-label">{tab.label}</span>
                  </span>
                  {!tab.enabled ? <span className="rail-nav-tag">Soon</span> : null}
                </button>
              ))}
            </nav>
          ) : null}
        </div>

        <div className="rail-footer-group">
          <div className="rail-footer">
            {railCollapsed ? (
              <Link className="header-utility-button rail-footer-icon" to="/migration" aria-label="Open migration upload" title="Migration Upload">
                <span aria-hidden="true"><Icon name="upload" className="app-icon" /></span>
              </Link>
            ) : (
              <Link className="ghost-button full-width" to="/migration">Migration Upload</Link>
            )}
          </div>
        </div>
      </aside>

      <main className="workspace-shell">
        {activeTab === "users" ? (
          <UsersTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "sites" ? (
          <SitesTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "cards" ? (
          <CardsTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "method-types" ? (
          <MethodTypesTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "redemption-methods" ? (
          <RedemptionMethodsTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "game-types" ? (
          <GameTypesTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "games" ? (
          <GamesTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
        {activeTab === "purchases" ? (
          <PurchasesTab
            apiBaseUrl={auth.apiBaseUrl}
            hostedWorkspaceReady={auth.hostedWorkspaceReady}
          />
        ) : null}
      </main>

      {notificationsModalOpen ? (
        <NotificationsModal onClose={() => setNotificationsModalOpen(false)} />
      ) : null}

      {statusModalOpen ? (
        <StatusModal
          overallTone={auth.overallStatusTone}
          statusItems={auth.statusItems}
          onClose={() => setStatusModalOpen(false)}
          onRetryHostedConnection={async () => {
            await auth.handleRetryHostedConnection();
          }}
        />
      ) : null}

      {accountModalOpen ? (
        <AccountModal
          accountOwner={auth.accountOwner}
          accountRole={auth.accountRole}
          accountStatus={auth.accountStatus}
          workspaceName={auth.workspaceName}
          onClose={() => setAccountModalOpen(false)}
          onSignOut={auth.handleSignOut}
        />
      ) : null}

      {settingsModalOpen ? (
        <SettingsModal onClose={() => setSettingsModalOpen(false)} />
      ) : null}
    </div>
  );
}
