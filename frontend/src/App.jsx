import { useEffect } from "react";
import { Route, Routes, Navigate, useLocation } from "react-router-dom";
import "./App.css";
import "./design-system.css";
import LoginPage from "./pages/LoginPage.jsx";
import DevicesPage from "./pages/DevicesPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import DeviceRulesPage from "./pages/DeviceRulesPage.jsx";
import DeviceDashboardPage from "./pages/DeviceDashboardPage.jsx";
import UtilityBillingPage from "./pages/UtilityBillingPage.jsx";
import AdminPortalPage from "./pages/AdminPortalPage.jsx";
import TenantManagementPage from "./pages/TenantManagementPage.jsx";
import UserManagementPage from "./pages/UserManagementPage.jsx";
import Navbar from "./components/Navbar.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { useAuth } from "./context/AuthContext.jsx";

function AppLayout({ children }) {
  const { isAuthenticated } = useAuth();
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

  // If not authenticated, show login page
  if (!isAuthenticated) {
    return <LoginPage />;
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
  const { hasModule, isAdmin, isTenantAdmin, isAuthenticated } = useAuth();

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <AppLayout>
      <Routes>
        {/* Admin Routes - Only accessible to admins */}
        {isAdmin && (
          <>
            <Route path="/" element={<Navigate to="/admin" replace />} />
            <Route path="/admin" element={<AdminPortalPage />} />
            <Route path="/admin/tenants" element={<TenantManagementPage />} />
            <Route path="/admin/users" element={<UserManagementPage />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </>
        )}
        
        {/* Tenant Routes - Only accessible to tenant admins */}
        {isTenantAdmin && (
          <>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            
            {/* Device Management Routes */}
            {hasModule("devices") && (
              <>
                <Route path="/devices" element={<DevicesPage />} />
                <Route path="/devices/:deviceId/rules" element={<DeviceRulesPage />} />
              </>
            )}
            
            {/* Dashboard Routes */}
            {hasModule("dashboards") && (
              <Route path="/devices/:deviceId/dashboard" element={<DeviceDashboardPage />} />
            )}
            
            {/* Utility Routes */}
            {hasModule("utility") && (
              <Route path="/utility/billing" element={<UtilityBillingPage />} />
            )}
            
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </>
        )}
        
        {/* Fallback for users without proper role */}
        {!isAdmin && !isTenantAdmin && (
          <Route path="*" element={
            <div className="page">
              <div className="card">
                <p className="text-error">Your account is not properly configured. Please contact an administrator.</p>
              </div>
            </div>
          } />
        )}
      </Routes>
    </AppLayout>
  );
}

export default App;
