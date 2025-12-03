import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

export default function DashboardPage() {
  const { token, isBootstrapping, bootstrapError } = useAuth();
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/metrics`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setMetrics(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      }
    };
    if (!token || isBootstrapping || bootstrapError) {
      return;
    }
    loadMetrics();
  }, [token, isBootstrapping, bootstrapError]);

  if (error) {
    return <p className="error-message">{error}</p>;
  }

  if (!metrics) {
    return <p>Loading metrics...</p>;
  }

  return (
    <div className="page">
      <div className="section-header">
        <h2>Platform Overview</h2>
      </div>
      
      <div className="metrics-grid">
        <MetricCard title="Messages Received" value={metrics.messages.total_received} />
        <MetricCard title="Messages Published" value={metrics.messages.total_published} />
        <MetricCard title="Messages Rejected" value={metrics.messages.total_rejected} />
        <MetricCard title="Active Devices" value={metrics.active_devices} />
      </div>
      
      <section className="card">
        <h3 style={{ marginTop: 0, marginBottom: "1rem", fontSize: "1.125rem", fontWeight: 600, color: "#334155" }}>
          Protocol Breakdown
        </h3>
        <ul style={{ margin: 0, padding: "0 0 0 1.5rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {Object.entries(metrics.sources || {}).map(([source, value]) => (
            <li key={source} style={{ fontSize: "0.95rem", color: "#475569" }}>
              <strong style={{ color: "#0f172a", textTransform: "uppercase" }}>{source}:</strong>{" "}
              <span style={{ fontWeight: 600 }}>{value}</span> messages
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function MetricCard({ title, value }) {
  return (
    <div className="card metric-card">
      <span className="metric-card__label">{title}</span>
      <span className="metric-card__value">{value}</span>
    </div>
  );
}


