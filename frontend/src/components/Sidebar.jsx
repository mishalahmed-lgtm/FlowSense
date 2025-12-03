import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

const navItems = [
  { label: "Dashboard", path: "/dashboard" },
  {
    label: "Devices",
    path: "/devices",
    subLinks: [
      { label: "Device List", target: "#devices-list" },
      { label: "Add Device", target: "#add-device" },
      { label: "Rotate Key", target: "#devices-list" },
    ],
  },
  {
    label: "Utility",
    path: "/utility/billing",
    subLinks: [
      { label: "Billing", target: "" },
    ],
  },
];

export default function Sidebar() {
  const location = useLocation();
  const { adminEmail } = useAuth();

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
        <p className="sidebar__footer-email">{adminEmail}</p>
      </div>
    </aside>
  );
}

