import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import AppShell from "./components/AppShell";
import MarketingShell from "./components/MarketingShell";
import MigrationShell from "./components/MigrationShell";
import "./styles.css";

export default function App() {
  const auth = useAuth();

  return (
    <Routes>
      <Route path="/migration" element={<MigrationShell auth={auth} />} />
      <Route
        path="/setup/:tabKey"
        element={auth.sessionEmail ? <AppShell auth={auth} /> : <MarketingShell auth={auth} />}
      />
      <Route
        path="/"
        element={auth.sessionEmail ? <Navigate to="/setup/users" replace /> : <MarketingShell auth={auth} />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
