import { useEffect } from "react";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";
import "./App.css";
import DevicesPage from "./pages/DevicesPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import DeviceRulesPage from "./pages/DeviceRulesPage.jsx";
import DeviceDashboardPage from "./pages/DeviceDashboardPage.jsx";
import UtilityBillingPage from "./pages/UtilityBillingPage.jsx";
import Navbar from "./components/Navbar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useAuth } from "./context/AuthContext.jsx";

function AppLayout({ children }) {
  const { isBootstrapping, bootstrapError } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (location.hash) {
      const element = document.querySelector(location.hash);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [location.pathname, location.hash]);

  if (isBootstrapping) {
    return (
      <div className="page page--centered">
        <p>Signing you in…</p>
      </div>
    );
  }

  if (bootstrapError) {
    return (
      <div className="page page--centered">
        <p className="error-message">{bootstrapError}</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Navbar />
        <main>{children}</main>
      </div>
    </div>
  );
}

function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/devices" element={<DevicesPage />} />
        <Route path="/devices/:deviceId/rules" element={<DeviceRulesPage />} />
        <Route path="/devices/:deviceId/dashboard" element={<DeviceDashboardPage />} />
        <Route path="/utility/billing" element={<UtilityBillingPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AppLayout>
  );
}

export default App;
