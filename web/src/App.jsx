import { useEffect, useState } from "react";

import { useAuth } from "./hooks/useAuth";
import { readCurrentRoute } from "./services/routing";
import AppShell from "./components/AppShell";
import MarketingShell from "./components/MarketingShell";
import MigrationShell from "./components/MigrationShell";
import "./styles.css";

export default function App() {
  const [currentRoute, setCurrentRoute] = useState(() => readCurrentRoute());
  const auth = useAuth();

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

  const isMigrationPage = currentRoute === "/migration";

  if (isMigrationPage) {
    return <MigrationShell auth={auth} />;
  }

  if (!auth.sessionEmail) {
    return <MarketingShell auth={auth} />;
  }

  return <AppShell auth={auth} />;
}
