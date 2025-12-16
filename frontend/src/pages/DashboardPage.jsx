import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";

export default function DashboardPage() {
  const { token, user, isTenantAdmin } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMetrics = async () => {
      setLoading(true);
      try {
        const response = await axios.get(`${API_BASE_URL}/metrics`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setMetrics(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };
    if (!token) {
      return;
    }
    loadMetrics();
  }, [token]);

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Dashboard", path: "/dashboard" }]} />
      
      <div style={{ marginBottom: "var(--space-8)" }}>
        <h1 style={{ marginBottom: "var(--space-2)", fontSize: "var(--font-size-3xl)" }}>
          Platform Overview
        </h1>
        <p className="text-muted">
          Real-time metrics and system health monitoring
        </p>
      </div>

      {user && (
        <div className="card" style={{ marginBottom: "var(--space-6)", background: "var(--color-primary-50)", borderColor: "var(--color-primary-200)" }}>
          <p style={{ margin: 0 }}>
            Welcome back, <strong>{user.full_name || user.email}</strong>!
            {user.role === 'admin' && <span style={{ marginLeft: "var(--space-2)" }} className="badge badge--primary">Admin</span>}
            {user.role === 'tenant_admin' && user.tenant_id && (
              <span style={{ marginLeft: "var(--space-2)" }} className="badge badge--secondary">Tenant Admin</span>
            )}
          </p>
        </div>
      )}

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <p className="text-muted">Loading metrics...</p>
        </div>
      )}

      {error && (
        <div className="card" style={{ borderColor: "var(--color-error-500)" }}>
          <p className="text-error">{error}</p>
        </div>
      )}

      {!loading && !error && metrics && (
        <>
          <div className="metrics-grid">
            <MetricCard
              title="Messages Received"
              value={metrics.messages.total_received}
              icon="📥"
              color="var(--color-primary-500)"
            />
            <MetricCard
              title="Messages Published"
              value={metrics.messages.total_published}
              icon="📤"
              color="var(--color-success-500)"
            />
            <MetricCard
              title="Messages Rejected"
              value={metrics.messages.total_rejected}
              icon="⚠️"
              color="var(--color-error-500)"
            />
            <MetricCard
              title="Active Devices"
              value={metrics.active_devices}
              icon="🟢"
              color="var(--color-success-500)"
            />
          </div>

          <div className="card mt-8">
            <div className="card__header">
              <h3 className="card__title">Protocol Breakdown</h3>
            </div>
            <div className="card__body">
              <div style={{ display: "grid", gap: "var(--space-4)" }}>
                {Object.entries(metrics.sources || {}).map(([source, value]) => (
                  <div
                    key={source}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "var(--space-3)",
                      backgroundColor: "var(--color-gray-50)",
                      borderRadius: "var(--radius-md)",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <span style={{ fontSize: "var(--font-size-lg)" }}>
                        {source === "HTTP" && "🌐"}
                        {source === "MQTT" && "📡"}
                        {source === "TCP" && "🔌"}
                      </span>
                      <span style={{ fontWeight: "var(--font-weight-semibold)", textTransform: "uppercase" }}>
                        {source}
                      </span>
                    </div>
                    <span style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)" }}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({ title, value, icon, color }) {
  return (
    <div className="metric-card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
        <span className="metric-card__label">{title}</span>
        {icon && <span style={{ fontSize: "var(--font-size-xl)" }}>{icon}</span>}
      </div>
      <div className="metric-card__value" style={{ color: color || "var(--color-text-primary)" }}>
        {value?.toLocaleString() || 0}
      </div>
    </div>
  );
}
