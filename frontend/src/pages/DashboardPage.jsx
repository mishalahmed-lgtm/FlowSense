import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL, createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "../components/Icon.jsx";

function EventActivityChart({ activity }) {
  const height = 300;
  const width = 800;
  const topPadding = 24;
  const bottomPadding = 40; // leave room for time labels
  const rightPadding = 48; // reserve space on the right for the total label

  if (!activity || !activity.buckets || activity.buckets.length === 0) {
    return (
      <div
        style={{
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "linear-gradient(180deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <Icon name="inbox" size={32} />
          <p
            className="text-muted"
            style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}
          >
            No activity in the last 24 hours
          </p>
        </div>
      </div>
    );
  }

  const buckets = activity.buckets;
  const maxCount = Math.max(...buckets.map((b) => b.count), 1);
  const chartHeight = height - topPadding - bottomPadding;
  const chartWidth = width - rightPadding;
  const stepX = buckets.length > 1 ? chartWidth / (buckets.length - 1) : 0;

  const points = buckets.map((bucket, index) => {
    const x = index * stepX;
    const ratio = bucket.count / maxCount;
    // Higher counts should be higher on the chart; 0 should sit above the labels
    const y = topPadding + (1 - ratio) * chartHeight;
    return { x, y };
  });

  const linePath = points
    .map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x},${p.y}`)
    .join(" ");
  const baselineY = topPadding + chartHeight;
  const areaPath =
    `${linePath} L ${chartWidth},${baselineY} L 0,${baselineY} Z`;

  const firstLabel = new Date(buckets[0].timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const lastLabel = new Date(
    buckets[buckets.length - 1].timestamp,
  ).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      style={{
        height,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "linear-gradient(180deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%)",
        borderRadius: "var(--radius-lg)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="activity-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop
              offset="0%"
              style={{ stopColor: "rgba(59, 130, 246, 0.35)", stopOpacity: 1 }}
            />
            <stop
              offset="100%"
              style={{ stopColor: "rgba(59, 130, 246, 0)", stopOpacity: 1 }}
            />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#activity-gradient)" />
        <path
          d={linePath}
          fill="none"
          stroke="rgba(59, 130, 246, 1)"
          strokeWidth="2"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          bottom: "var(--space-4)",
          left: "var(--space-4)",
          fontSize: "var(--font-size-xs)",
          color: "var(--color-text-tertiary)",
        }}
      >
        {firstLabel} - {lastLabel}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [metrics, setMetrics] = useState(null);
    const [activity, setActivity] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMetrics = async () => {
      setLoading(true);
      try {
        const isTenantAdmin = user?.role === "tenant_admin";
        const url = `${API_BASE_URL}${isTenantAdmin ? "/metrics/tenant" : "/metrics"}`;
        const [metricsResp, activityResp] = await Promise.all([
          axios.get(url, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          }),
          // Activity endpoint is tenant-aware on backend side
          createApiClient(token).get("/dashboard/activity"),
        ]);
        setMetrics(metricsResp.data);
        setActivity(activityResp.data);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };
    if (!token) return;
    loadMetrics();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadMetrics, 30000);
    return () => clearInterval(interval);
  }, [token, user]);

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <h1 className="page-header__title">Dashboard</h1>
          <p className="page-header__subtitle">
            IoT platform overview and system status
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn-icon" onClick={() => window.location.reload()} title="Refresh">
            <Icon name="refresh" size={18} />
          </button>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <div style={{ fontSize: "var(--font-size-4xl)", marginBottom: "var(--space-4)", opacity: 0.3 }}>
            <Icon name="activity" size={48} />
          </div>
          <p style={{ color: "var(--color-text-secondary)" }}>Loading metrics...</p>
        </div>
      )}

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)" }}>
          {error}
        </div>
      )}

      {!loading && !error && metrics && (
        <>
          {/* Key Metrics */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-card__header">
                <div className="metric-card__icon metric-card__icon--primary">
                  <Icon name="devices" size={24} />
                </div>
              </div>
              <div className="metric-card__label">TOTAL DEVICES</div>
              <div className="metric-card__value">{metrics.active_devices}</div>
              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
                {metrics.active_devices} Active
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-card__header">
                <div className="metric-card__icon metric-card__icon--success">
                  <Icon name="inbox" size={24} />
                </div>
              </div>
              <div className="metric-card__label">MESSAGES RECEIVED</div>
              <div className="metric-card__value">{metrics.messages.total_received.toLocaleString()}</div>
              <div className="metric-card__trend metric-card__trend--up">
                <Icon name="trending" size={12} /> Live streaming
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-card__header">
                <div className="metric-card__icon metric-card__icon--warning">
                  <Icon name="warning" size={24} />
                </div>
              </div>
              <div className="metric-card__label">REJECTED MESSAGES</div>
              <div className="metric-card__value">{metrics.messages.total_rejected}</div>
              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
                Last 24 hours
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-card__header">
                <div className="metric-card__icon metric-card__icon--primary">
                  <Icon name="send" size={24} />
                </div>
              </div>
              <div className="metric-card__label">MESSAGES PUBLISHED</div>
              <div className="metric-card__value">{metrics.messages.total_published.toLocaleString()}</div>
              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
                Processing
              </div>
            </div>
          </div>

          {/* Activity Chart and System Status */}
          <div className="grid grid--2">
            {/* Event Activity Chart */}
            <div className="card" style={{ gridColumn: "1 / -1" }}>
              <div className="card__header" style={{ marginBottom: "var(--space-6)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <Icon name="activity" size={20} />
                  <h3 className="card__title">Event Activity (24h)</h3>
                </div>
                {activity && (
                  <div
                    style={{
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-tertiary)",
                    }}
                  >
                    Total events:{" "}
                    <span style={{ color: "var(--color-text-primary)" }}>
                      {activity.total_events.toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
              <EventActivityChart activity={activity} />
            </div>

            {/* System Status */}
            <div className="card">
              <div className="card__header" style={{ marginBottom: "var(--space-6)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <Icon name="activity" size={20} />
                  <h3 className="card__title">System Status</h3>
                </div>
                <span className="badge badge--success">Online</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="cpu" size={16} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        CPU Usage
                      </span>
                    </div>
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                      76%
                    </span>
                  </div>
                  <div style={{
                    width: "100%",
                    height: "8px",
                    backgroundColor: "var(--color-bg-secondary)",
                    borderRadius: "var(--radius-full)",
                    overflow: "hidden"
                  }}>
                    <div style={{
                      width: "76%",
                      height: "100%",
                      background: "linear-gradient(90deg, #3b82f6, #60a5fa)",
                      borderRadius: "var(--radius-full)"
                    }}></div>
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="cpu" size={16} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        Memory Usage
                      </span>
                    </div>
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                      62%
                    </span>
                  </div>
                  <div style={{
                    width: "100%",
                    height: "8px",
                    backgroundColor: "var(--color-bg-secondary)",
                    borderRadius: "var(--radius-full)",
                    overflow: "hidden"
                  }}>
                    <div style={{
                      width: "62%",
                      height: "100%",
                      background: "linear-gradient(90deg, #10b981, #34d399)",
                      borderRadius: "var(--radius-full)"
                    }}></div>
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="database" size={16} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        Disk Usage
                      </span>
                    </div>
                    <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                      70%
                    </span>
                  </div>
                  <div style={{
                    width: "100%",
                    height: "8px",
                    backgroundColor: "var(--color-bg-secondary)",
                    borderRadius: "var(--radius-full)",
                    overflow: "hidden"
                  }}>
                    <div style={{
                      width: "70%",
                      height: "100%",
                      background: "linear-gradient(90deg, #f59e0b, #fbbf24)",
                      borderRadius: "var(--radius-full)"
                    }}></div>
                  </div>
                </div>

                <div style={{ 
                  marginTop: "var(--space-4)", 
                  paddingTop: "var(--space-4)", 
                  borderTop: "1px solid var(--color-border-light)",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--color-text-tertiary)"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
                    <span>Uptime</span>
                    <span style={{ color: "var(--color-text-primary)" }}>196:36:33s</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Last sync</span>
                    <span style={{ color: "var(--color-text-primary)" }}>8 min ago</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Protocol Distribution */}
            <div className="card">
              <div className="card__header" style={{ marginBottom: "var(--space-6)" }}>
                <h3 className="card__title">Protocol Distribution</h3>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                {Object.entries(metrics.sources || {}).map(([source, value]) => (
                  <div
                    key={source}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "var(--space-4)",
                      backgroundColor: "var(--color-bg-secondary)",
                      borderRadius: "var(--radius-lg)",
                      border: "1px solid var(--color-border-light)",
                      transition: "all var(--transition-fast)",
                      cursor: "pointer"
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-border-medium)";
                      e.currentTarget.style.backgroundColor = "var(--color-bg-tertiary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-border-light)";
                      e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                      <div style={{
                        width: "40px",
                        height: "40px",
                        borderRadius: "var(--radius-lg)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        backgroundColor: "rgba(59, 130, 246, 0.15)"
                      }}>
                        <Icon name={source === "HTTP" ? "inbox" : source === "MQTT" ? "activity" : "devices"} size={20} />
                      </div>
                      <div>
                        <div style={{ 
                          fontWeight: "var(--font-weight-semibold)", 
                          color: "var(--color-text-primary)",
                          fontSize: "var(--font-size-sm)"
                        }}>
                          {source}
                        </div>
                        <div style={{ 
                          fontSize: "var(--font-size-xs)", 
                          color: "var(--color-text-tertiary)" 
                        }}>
                          Protocol
                        </div>
                      </div>
                    </div>
                    <div style={{ 
                      fontWeight: "var(--font-weight-bold)", 
                      fontSize: "var(--font-size-xl)",
                      color: "var(--color-primary-400)"
                    }}>
                      {value}
                    </div>
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
