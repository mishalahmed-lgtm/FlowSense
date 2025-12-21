import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";

export default function AdminPortalPage() {
  const { user, isAdmin } = useAuth();

  if (!isAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Admin access required to view this page.</p>
        </div>
      </div>
    );
  }

  const adminModules = [
    {
      title: "Tenant Management",
      description: "Create and manage tenant organizations",
      icon: "🏢",
      path: "/admin/tenants",
      color: "var(--color-primary-500)",
    },
    {
      title: "User Management",
      description: "Manage user accounts and permissions",
      icon: "👥",
      path: "/admin/users",
      color: "var(--color-success-text)",
    },
  ];

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Admin Portal" }]} />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Admin Portal</h1>
          <p className="page-header__subtitle">
            Manage tenants, users, and platform-wide configuration
          </p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "var(--space-6)", background: "rgba(59, 130, 246, 0.1)", borderColor: "rgba(59, 130, 246, 0.3)" }}>
        <p style={{ margin: 0 }}>
          Welcome, <strong>{user?.full_name || user?.email}</strong>! 
          <span style={{ marginLeft: "var(--space-2)" }} className="badge badge--primary">Admin</span>
        </p>
        <p style={{ margin: "var(--space-2) 0 0", color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
          As an administrator, you can create and manage tenant profiles, assign users, and configure module access for each tenant.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "var(--space-6)" }}>
        {adminModules.map((module) => (
          <Link
            key={module.path}
            to={module.path}
            style={{ textDecoration: "none" }}
          >
            <div
              className="card"
              style={{
                borderLeft: `4px solid ${module.color}`,
                cursor: "pointer",
                transition: "all var(--transition-base)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow = "var(--shadow-lg)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "var(--shadow-md)";
              }}
            >
              <div style={{ fontSize: "3rem", marginBottom: "var(--space-4)" }}>
                {module.icon}
              </div>
              <h3 style={{ marginBottom: "var(--space-2)" }}>{module.title}</h3>
              <p style={{ color: "var(--color-text-secondary)", margin: 0 }}>
                {module.description}
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

