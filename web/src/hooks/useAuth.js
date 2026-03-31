import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

import { supabase, supabaseConfigError, supabaseConfigured } from "../lib/supabaseClient";
import { authHeaders, classifyStatusTone, describeFetchFailure } from "../services/api";
import { applyRoute, consumeOAuthReturnRoute, rememberOAuthReturnRoute } from "../services/routing";

export function useAuth() {
  const location = useLocation();
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() || null;

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

  const hasAuthenticatedSession = Boolean(sessionEmail);
  const hostedWorkspaceReady = Boolean(hostedSummary);
  const workspaceName = hostedSummary?.workspace?.name || (sessionEmail ? `${sessionEmail} Workspace` : "Hosted Workspace");
  const accountOwner = hostedSummary?.account?.owner_email || sessionEmail || "Not signed in";
  const accountRole = hostedSummary?.account?.role || "Pending bootstrap";
  const accountStatus = hostedSummary?.account?.status || "Pending bootstrap";

  const statusItems = useMemo(() => {
    const authenticationTone = sessionEmail ? "good" : "bad";
    const apiTone = classifyStatusTone(apiStatus, { ready: apiStatus.toLowerCase().includes("ready for"), available: Boolean(apiBaseUrl) });
    const bootstrapTone = classifyStatusTone(hostedStatus, { ready: hostedWorkspaceReady, available: Boolean(apiBaseUrl) });
    const importTone = classifyStatusTone(importPlanStatus, { ready: Boolean(importPlanSummary), available: Boolean(apiBaseUrl) });

    return [
      { label: "Authentication", message: authMessage, tone: authenticationTone },
      { label: "API Handshake", message: apiStatus, tone: apiTone },
      { label: "Hosted Bootstrap", message: hostedStatus, tone: bootstrapTone },
      { label: "Import Planning", message: importPlanStatus, tone: importTone }
    ];
  }, [authMessage, apiBaseUrl, apiStatus, hostedStatus, hostedWorkspaceReady, importPlanStatus, importPlanSummary, sessionEmail]);

  const overallStatusTone = useMemo(() => {
    const failures = statusItems.filter((item) => item.tone === "bad").length;
    const allGood = statusItems.every((item) => item.tone === "good");

    if (allGood) {
      return "good";
    }

    if (failures === statusItems.length) {
      return "bad";
    }

    return "warn";
  }, [statusItems]);

  // --- Orchestration ---

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
      return;
    }

    if (!apiBaseUrl) {
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
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
        setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
        setHostedStatus(data.detail || `Hosted account bootstrap failed (${response.status}).`);
        return;
      }

      setHostedSummary(data);
      setHostedStatus(
        data.created_account || data.created_workspace
          ? "Hosted account workspace created and ready."
          : "Hosted account workspace ready."
      );

      await syncWorkspaceImportPlan(nextSession);
    } catch (error) {
      setHostedSummary(null);
      setImportPlanSummary(null);
      setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
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
      return;
    }

    if (!apiBaseUrl) {
      setApiStatus("Set VITE_API_BASE_URL to enable the protected API handshake.");
      setHostedSummary(null);
      setHostedStatus("Set VITE_API_BASE_URL to enable hosted account bootstrap.");
      setImportPlanSummary(null);
      setImportPlanStatus("Set VITE_API_BASE_URL to enable hosted import planning.");
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
      setApiStatus(describeFetchFailure(error, "Protected API handshake could not reach the hosted API."));
    }
  }

  // --- Auth lifecycle ---

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
        if (pendingRoute && pendingRoute !== location.pathname) {
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
        if (pendingRoute && pendingRoute !== location.pathname) {
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

  // --- Actions ---

  async function handleGoogleSignIn() {
    if (!supabase) {
      setAuthMessage(supabaseConfigError);
      return;
    }

    rememberOAuthReturnRoute(location.pathname);

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
    setAuthMessage("Signed out. Sign in with Google to reactivate the hosted workspace.");
    setApiStatus("Protected API handshake will run after Google sign-in.");
    setHostedStatus("Hosted account bootstrap will run after the protected API handshake.");
    setImportPlanStatus("Hosted import planning will run after workspace bootstrap.");
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

  return {
    sessionEmail,
    authMessage,
    apiStatus,
    hostedStatus,
    importPlanStatus,
    hostedSummary,
    importPlanSummary,
    hasAuthenticatedSession,
    hostedWorkspaceReady,
    workspaceName,
    accountOwner,
    accountRole,
    accountStatus,
    statusItems,
    overallStatusTone,
    apiBaseUrl,
    handleGoogleSignIn,
    handleSignOut,
    handleRetryHostedConnection
  };
}
