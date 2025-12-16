import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Sidebar() {
  const location = useLocation();
  const { user, hasModule, isAdmin, isTenantAdmin } = useAuth();
  
  // Build navigation items based on user role
  const navItems = [];

  // Admin users only see Admin Portal
  if (isAdmin) {
    navItems.push({
      label: "Admin Portal",
      path: "/admin",
      module: null,
      subLinks: [
        { label: "Tenants", target: "/tenants" },
        { label: "Users", target: "/users" },
      ],
    });
  }
  
  // Tenant admin users see tenant features
  if (isTenantAdmin) {
    navItems.push(
      { label: "Dashboard", path: "/dashboard", module: null }
    );

    if (hasModule("devices")) {
      navItems.push({
        label: "Devices",
        path: "/devices",
        module: "devices",
        subLinks: [
          { label: "Device List", target: "#devices-list" },
          { label: "Add Device", target: "#add-device" },
          { label: "Rotate Key", target: "#devices-list" },
        ],
      });
    }

    if (hasModule("utility")) {
      navItems.push({
        label: "Utility",
        path: "/utility/billing",
        module: "utility",
        subLinks: [
          { label: "Billing", target: "" },
        ],
      });
    }

    if (hasModule("alerts")) {
      navItems.push({
        label: "Alerts",
        path: "/alerts",
        module: "alerts",
        subLinks: [
          { label: "Alert List", target: "" },
          { label: "Alert Rules", target: "/rules" },
        ],
      });
    }
  }

  const renderSubLinks = (item) => {
    if (!item.subLinks) {
      return null;
    }

    const isActive = location.pathname.startsWith(item.path);

    return (
      <div className={`sidebar__sublinks ${isActive ? "sidebar__sublinks--open" : ""}`}>
        {item.subLinks.map((subLink) => (
          <Link
            key={subLink.label}
            className="sidebar__sublink"
            to={`${item.path}${subLink.target}`}
          >
            {subLink.label}
          </Link>
        ))}
      </div>
    );
  };

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">FS</div>
        <div>
          <p className="sidebar__title">FlowSense</p>
          <p className="sidebar__subtitle">IoT Admin Console</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        {navItems.map((item) => (
          <div key={item.label} className="sidebar__nav-item">
            <NavLink to={item.path} className="sidebar__link">
              {item.label}
            </NavLink>
            {renderSubLinks(item)}
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <p className="sidebar__footer-label">Signed in</p>
        <p className="sidebar__footer-email">{user?.email}</p>
        {user?.role && (
          <p className="sidebar__footer-label" style={{ marginTop: "var(--space-1)", textTransform: "capitalize" }}>
            {user.role.replace("_", " ")}
          </p>
        )}
      </div>
    </aside>
  );
}

