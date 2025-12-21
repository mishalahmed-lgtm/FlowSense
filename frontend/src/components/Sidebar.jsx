import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "./Icon.jsx";

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, hasModule, isAdmin, isTenantAdmin, logout } = useAuth();
  
  // Debug: Log module access
  if (process.env.NODE_ENV === 'development') {
    console.log('Sidebar - User:', user?.email);
    console.log('Sidebar - Enabled Modules:', user?.enabled_modules);
    console.log('Sidebar - Has alerts module:', hasModule('alerts'));
  }
  
  // Build navigation items based on user role
  const navItems = [];

  // Admin users only see Admin Portal
  if (isAdmin) {
    navItems.push({
      label: "Admin Portal",
      path: "/admin",
      icon: "admin",
      module: null,
    });
  }
  
  // Tenant admin users see tenant features
  if (isTenantAdmin) {
    navItems.push(
      { label: "Dashboard", path: "/dashboard", icon: "dashboard", module: null }
    );

    if (hasModule("devices")) {
      navItems.push({
        label: "Devices",
        path: "/devices",
        icon: "devices",
        module: "devices",
        badge: null,
      });
    }

    if (hasModule("utility")) {
      navItems.push({
        label: "Utility Billing",
        path: "/utility/billing",
        icon: "utility",
        module: "utility",
      });
    }

    if (hasModule("alerts")) {
      navItems.push({
        label: "Alerts",
        path: "/alerts",
        icon: "alerts",
        module: "alerts",
      });
    }

    if (hasModule("fota")) {
      navItems.push({
        label: "Firmware",
        path: "/fota/jobs",
        icon: "firmware",
        module: "fota",
      });
    }

    if (hasModule("health")) {
      navItems.push({
        label: "Device Health",
        path: "/health",
        icon: "health",
        module: "health",
      });
    }

    if (hasModule("analytics")) {
      navItems.push({
        label: "Analytics",
        path: "/analytics",
        icon: "analytics",
        module: "analytics",
      });
    }
  }

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">
          <Icon name="admin" size={24} />
        </div>
        <div>
          <p className="sidebar__title">FlowSense</p>
          <p className="sidebar__subtitle">IoT Platform</p>
        </div>
      </div>

      {/* Monitoring Section */}
      {isTenantAdmin && (
        <div className="sidebar__section">
          <div className="sidebar__section-label">Monitoring</div>
          <nav className="sidebar__nav">
            {navItems.filter(item => ['Dashboard', 'Devices', 'Analytics', 'Device Health'].includes(item.label)).map((item) => (
              <NavLink 
                key={item.label} 
                to={item.path} 
                className="sidebar__link"
              >
                <span className="sidebar__link-icon">
                  <Icon name={item.icon} size={18} />
                </span>
                <span>{item.label}</span>
                {item.badge && <span className="sidebar__link-badge">{item.badge}</span>}
              </NavLink>
            ))}
            {hasModule("utility") && (
              <NavLink 
                to="/dashboard/energy" 
                className="sidebar__link"
              >
                <span className="sidebar__link-icon">
                  <Icon name="zap" size={18} />
                </span>
                <span>Energy Management</span>
              </NavLink>
            )}
            {hasModule("dashboards") && (
              <NavLink 
                to="/dashboard/environmental" 
                className="sidebar__link"
              >
                <span className="sidebar__link-icon">
                  <Icon name="activity" size={18} />
                </span>
                <span>Environmental</span>
              </NavLink>
            )}
          </nav>
        </div>
      )}

      {/* Management Section */}
      {(isTenantAdmin || isAdmin) && (
        <div className="sidebar__section">
          <div className="sidebar__section-label">Management</div>
          <nav className="sidebar__nav">
            {navItems.filter(item => ['Admin Portal', 'Alerts', 'Firmware', 'Utility Billing'].includes(item.label)).map((item) => (
              <NavLink 
                key={item.label} 
                to={item.path} 
                className="sidebar__link"
              >
                <span className="sidebar__link-icon">
                  <Icon name={item.icon} size={18} />
                </span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      )}

      {/* Footer with Status */}
      <div className="sidebar__footer">
        <div className="sidebar__status">
          <span className="sidebar__status-dot"></span>
          <span className="sidebar__status-text">System Online</span>
        </div>
        {user?.email && (
          <div style={{ marginTop: "var(--space-3)", fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)" }}>
            <div>{user.email}</div>
            {user?.role && (
              <div style={{ marginTop: "var(--space-1)", textTransform: "capitalize", color: "var(--color-text-secondary)" }}>
                {user.role.replace("_", " ")}
              </div>
            )}
          </div>
        )}
        <button
          onClick={() => {
            logout();
            navigate("/login");
          }}
          className="btn btn--ghost"
          style={{
            width: "100%",
            marginTop: "var(--space-4)",
            justifyContent: "flex-start",
            fontSize: "var(--font-size-sm)",
          }}
        >
          <Icon name="logout" size={16} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}

