import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL, createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function DashboardPage() {
  const { token, user } = useAuth();
  const api = createApiClient(token);
  const [metrics, setMetrics] = useState(null);
    const [activity, setActivity] = useState(null);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const isTenantAdmin = user?.role === "tenant_admin";
        const url = `${API_BASE_URL}${isTenantAdmin ? "/metrics/tenant" : "/metrics"}`;
        
        const [metricsResp, activityResp, alertsResp] = await Promise.all([
          axios.get(url, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          }),
          api.get("/dashboard/activity"),
          api.get("/alerts", { params: { limit: 10, status: "open" } }).catch(() => ({ data: [] }))
        ]);
        
        setMetrics(metricsResp.data);
        setActivity(activityResp.data);
        setRecentAlerts(alertsResp.data || []);
        setError(null);
      } catch (err) {
        setError(err.response?.data?.detail || err.message);
      } finally {
        setLoading(false);
      }
    };
    
    if (!token) return;
    loadData();
  }, [token, user]);

  // Format chart data for recharts
  const chartData = activity?.buckets?.map(bucket => ({
    time: new Date(bucket.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    timestamp: bucket.timestamp,
    events: bucket.count
  })) || [];

  const getPriorityColor = (priority) => {
    switch (priority?.toLowerCase()) {
      case "critical":
      case "high":
        return "var(--color-error-text)";
      case "medium":
        return "var(--color-warning-text)";
      case "low":
        return "var(--color-info-text)";
      default:
        return "var(--color-text-secondary)";
    }
  };

  const getStatusBadge = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "open" || statusLower === "acknowledged") {
      return "badge--warning";
    } else if (statusLower === "resolved" || statusLower === "closed") {
      return "badge--success";
    }
    return "badge--neutral";
  };

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Dashboard", path: "/dashboard" }]} />
      
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Dashboard</h1>
          <p className="page-header__subtitle">
            Real-time system metrics and device status
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn-icon" onClick={() => window.location.reload()} title="Refresh">
            <Icon name="refresh" size={18} />
          </button>
        </div>
      </div>

      {loading && (
        <div className="card" style={{ 
          textAlign: "center", 
          padding: "var(--space-12)",
          background: "linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%)",
          border: "1px solid var(--color-border-light)"
        }}>
          <div style={{ 
            fontSize: "var(--font-size-3xl)", 
            marginBottom: "var(--space-4)", 
            opacity: 0.4,
            animation: "pulse 2s infinite"
          }}>
            <Icon name="activity" size={48} />
          </div>
          <h3 style={{ 
            color: "var(--color-text-primary)",
            fontSize: "var(--font-size-lg)",
            fontWeight: "var(--font-weight-semibold)",
            marginBottom: "var(--space-1)"
          }}>
            Loading Dashboard
          </h3>
          <p style={{ 
            color: "var(--color-text-secondary)",
            fontSize: "var(--font-size-xs)"
          }}>
            Fetching metrics and system status...
          </p>
        </div>
      )}

      {error && (
        <div style={{
          padding: "var(--space-4)",
          background: "linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.05) 100%)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "var(--radius-lg)",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)"
        }}>
          <div style={{
            width: "40px",
            height: "40px",
            borderRadius: "var(--radius-full)",
            background: "rgba(239, 68, 68, 0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0
          }}>
            <Icon name="warning" size={20} style={{ color: "var(--color-error-text)" }} />
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{
              color: "var(--color-error-text)",
              fontSize: "var(--font-size-sm)",
              fontWeight: "var(--font-weight-semibold)",
              marginBottom: "var(--space-1)"
            }}>
              Error Loading Dashboard
            </h4>
            <p style={{
              color: "var(--color-text-secondary)",
              fontSize: "var(--font-size-xs)",
              margin: 0
            }}>
          {error}
            </p>
          </div>
        </div>
      )}

      {!loading && !error && metrics && (
        <>
          {/* Key Metrics */}
          <div className="metrics-grid" style={{ gridTemplateColumns: "repeat(5, 1fr)" }}>
            <div className="metric-card">
              <div className="metric-card__header">
                <div className="metric-card__icon metric-card__icon--primary">
                  <Icon name="devices" size={24} />
                </div>
              </div>
              <div className="metric-card__label">TOTAL ACTIVE DEVICES</div>
              <div className="metric-card__value">{metrics.active_devices}</div>
              <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
                Currently active
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

            {/* Protocol Distribution - Combined MQTT and HTTP in one card */}
            {(() => {
              const sources = metrics.sources || {};
              const hasMqtt = (sources.MQTT || sources.mqtt || 0) > 0;
              const hasHttp = (sources.HTTP || sources.http || 0) > 0;
              
              return (
                <div className="metric-card">
                  <div className="metric-card__header">
                    <div className="metric-card__icon metric-card__icon--primary">
                      <Icon name="activity" size={24} />
                    </div>
                  </div>
                  <div className="metric-card__label">PROTOCOL DISTRIBUTION</div>
                  <div style={{ 
                    fontSize: "var(--font-size-sm)", 
                    color: "var(--color-text-primary)", 
                    marginTop: "var(--space-3)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--space-2)",
                    fontWeight: "var(--font-weight-medium)"
                  }}>
                    {hasMqtt && (
                      <div>MQTT</div>
                    )}
                    {hasHttp && (
                      <div>HTTP</div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Main Content - Event Activity Chart and System Status */}
          <div style={{ 
            display: "grid",
            gridTemplateColumns: "70% 30%",
            gap: "var(--space-4)",
            marginTop: "var(--space-4)",
            alignItems: "stretch"
          }}>
            {/* Event Activity Chart */}
            <div className="card" style={{ 
              background: "linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%)",
              border: "1px solid var(--color-border-light)",
              boxShadow: "var(--shadow-lg)",
              transition: "all 0.3s ease"
            }}>
              <div className="card__header" style={{ 
                marginBottom: "var(--space-4)",
                paddingBottom: "var(--space-3)",
                borderBottom: "1px solid var(--color-border-light)"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-3)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", flex: 1 }}>
                    <div style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "var(--radius-lg)",
                      background: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)",
                      flexShrink: 0
                    }}>
                      <Icon name="activity" size={20} style={{ color: "#ffffff" }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <h3 className="card__title" style={{ margin: 0, fontSize: "var(--font-size-lg)", marginBottom: "var(--space-1)" }}>Event Activity</h3>
                      <p style={{ 
                        margin: 0,
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-tertiary)"
                      }}>
                        Last 24 hours
                      </p>
                    </div>
                </div>
                {activity && (
                    <div style={{ 
                      padding: "var(--space-2) var(--space-3)",
                      backgroundColor: "rgba(59, 130, 246, 0.1)",
                      borderRadius: "var(--radius-full)",
                      border: "1px solid rgba(59, 130, 246, 0.2)",
                      flexShrink: 0,
                      whiteSpace: "nowrap"
                    }}>
                      <span style={{ 
                      fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-tertiary)"
                      }}>
                        Total: <strong style={{ 
                          color: "var(--color-primary-400)",
                          fontWeight: "var(--font-weight-bold)"
                        }}>{activity.total_events.toLocaleString()}</strong>
                    </span>
                  </div>
                )}
                </div>
              </div>
              
              {chartData.length > 0 ? (
                <div style={{ height: "320px", width: "100%" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="rgba(59, 130, 246, 0.4)" stopOpacity={0.8}/>
                          <stop offset="95%" stopColor="rgba(59, 130, 246, 0.1)" stopOpacity={0.1}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-light)" opacity={0.3} />
                      <XAxis 
                        dataKey="time" 
                        stroke="var(--color-text-tertiary)"
                        style={{ fontSize: "var(--font-size-xs)" }}
                        tick={{ fill: "var(--color-text-tertiary)" }}
                      />
                      <YAxis 
                        stroke="var(--color-text-tertiary)"
                        style={{ fontSize: "var(--font-size-xs)" }}
                        tick={{ fill: "var(--color-text-tertiary)" }}
                      />
                      <Tooltip 
                        contentStyle={{
                          backgroundColor: "var(--color-bg-secondary)",
                          border: "1px solid var(--color-border-medium)",
                          borderRadius: "var(--radius-md)",
                          color: "var(--color-text-primary)"
                        }}
                        labelStyle={{ color: "var(--color-text-primary)" }}
                      />
                      <Area 
                        type="monotone" 
                        dataKey="events" 
                        stroke="rgba(59, 130, 246, 1)" 
                        strokeWidth={2}
                        fillOpacity={1} 
                        fill="url(#colorEvents)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div style={{ 
                  height: "320px", 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center",
                  color: "var(--color-text-tertiary)"
                }}>
                  <div style={{ textAlign: "center" }}>
                    <Icon name="inbox" size={40} style={{ opacity: 0.3, marginBottom: "var(--space-3)" }} />
                    <p style={{ fontSize: "var(--font-size-sm)" }}>No activity data available</p>
                  </div>
                </div>
              )}
            </div>

            {/* System Status Sidebar */}
            <div className="card" style={{
              background: "linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(5, 150, 105, 0.02) 100%)",
              border: "1px solid var(--color-border-light)",
              position: "sticky",
              top: "var(--space-4)",
              boxShadow: "var(--shadow-lg)",
              transition: "all 0.3s ease",
              padding: "var(--space-5)",
              display: "flex",
              flexDirection: "column",
              height: "100%"
            }}>
              <div className="card__header" style={{ 
                marginBottom: "var(--space-5)",
                paddingBottom: "var(--space-4)",
                borderBottom: "1px solid var(--color-border-light)"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flex: 1, minWidth: 0 }}>
                    <div style={{
                      width: "28px",
                      height: "28px",
                      borderRadius: "var(--radius-md)",
                      background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      boxShadow: "0 4px 12px rgba(16, 185, 129, 0.3)",
                      flexShrink: 0
                    }}>
                      <Icon name="activity" size={14} style={{ color: "#ffffff" }} />
                    </div>
                    <h3 className="card__title" style={{ 
                      margin: 0, 
                      fontSize: "var(--font-size-sm)",
                      fontWeight: "var(--font-weight-semibold)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis"
                    }}>
                      System Status
                    </h3>
                  </div>
                  <span className="badge badge--success" style={{ 
                    fontSize: "var(--font-size-xs)",
                    padding: "var(--space-1) var(--space-2)",
                    flexShrink: 0
                  }}>
                    <span style={{ 
                      display: "inline-block",
                      width: "5px",
                      height: "5px",
                      borderRadius: "50%",
                      backgroundColor: "var(--color-success-bright)",
                      marginRight: "var(--space-1)",
                      animation: "pulse 2s infinite"
                    }}></span>
                    Online
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", flex: 1, justifyContent: "space-between" }}>
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="cpu" size={16} style={{ color: "var(--color-primary-400)" }} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        CPU
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
                      borderRadius: "var(--radius-full)",
                      transition: "width 0.3s ease"
                    }}></div>
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="cpu" size={16} style={{ color: "var(--color-success-text)" }} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        Memory
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
                      borderRadius: "var(--radius-full)",
                      transition: "width 0.3s ease"
                    }}></div>
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-2)", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="database" size={16} style={{ color: "var(--color-warning-text)" }} />
                      <span style={{ color: "var(--color-text-secondary)", fontSize: "var(--font-size-sm)" }}>
                        Disk
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
                      borderRadius: "var(--radius-full)",
                      transition: "width 0.3s ease"
                    }}></div>
                  </div>
                </div>

                <div style={{ 
                  paddingTop: "var(--space-4)", 
                  marginTop: "var(--space-4)",
                  borderTop: "1px solid var(--color-border-light)",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--color-text-tertiary)"
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "var(--space-3)" }}>
                    <span>Uptime</span>
                    <span style={{ color: "var(--color-text-primary)", fontWeight: "var(--font-weight-medium)" }}>196h 36m</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Last sync</span>
                    <span style={{ color: "var(--color-text-primary)", fontWeight: "var(--font-weight-medium)" }}>8 min ago</span>
                  </div>
                  </div>
                </div>
              </div>
            </div>

          {/* Recent Events - Full Width Below */}
          {recentAlerts.length > 0 && (
            <div className="card" style={{
              background: "linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.02) 100%)",
              border: "1px solid var(--color-border-light)",
              boxShadow: "var(--shadow-lg)",
              transition: "all 0.3s ease",
              marginTop: "var(--space-4)"
            }}>
              <div className="card__header" style={{ 
                marginBottom: "var(--space-3)",
                paddingBottom: "var(--space-3)",
                borderBottom: "1px solid var(--color-border-light)"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <div style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "var(--radius-md)",
                    background: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 4px 12px rgba(245, 158, 11, 0.3)"
                  }}>
                    <Icon name="warning" size={18} style={{ color: "#ffffff" }} />
                  </div>
                  <div>
                    <h3 className="card__title" style={{ margin: 0, fontSize: "var(--font-size-base)" }}>Recent Events</h3>
                    <p style={{ 
                      margin: 0,
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-tertiary)"
                    }}>
                      Latest alerts
                    </p>
                  </div>
                </div>
              </div>
              
              <div style={{ 
                display: "grid", 
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", 
                gap: "var(--space-3)" 
              }}>
                {recentAlerts.slice(0, 6).map((alert, idx) => (
                  <div
                    key={alert.id}
                    style={{
                      padding: "var(--space-4)",
                      backgroundColor: "var(--color-bg-secondary)",
                      borderRadius: "var(--radius-lg)",
                      border: "1px solid var(--color-border-light)",
                      boxShadow: "var(--shadow-sm)",
                      transition: "all 0.3s ease",
                      cursor: "pointer",
                      position: "relative",
                      overflow: "hidden"
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-primary-400)";
                      e.currentTarget.style.backgroundColor = "var(--color-bg-tertiary)";
                      e.currentTarget.style.transform = "translateY(-4px)";
                      e.currentTarget.style.boxShadow = "var(--shadow-xl)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--color-border-light)";
                      e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                      e.currentTarget.style.transform = "translateY(0)";
                      e.currentTarget.style.boxShadow = "var(--shadow-sm)";
                    }}
                  >
                    <div style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "4px",
                      height: "100%",
                      background: `linear-gradient(180deg, ${getPriorityColor(alert.priority)} 0%, transparent 100%)`
                    }}></div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-2)", gap: "var(--space-2)" }}>
                      <div style={{
                        fontWeight: "var(--font-weight-semibold)", 
                        color: "var(--color-text-primary)",
                        fontSize: "var(--font-size-sm)",
                        flex: 1,
                        lineHeight: 1.3
                      }}>
                        {alert.title}
                      </div>
                      <span className={`badge ${getStatusBadge(alert.status)}`} style={{ 
                        fontSize: "var(--font-size-xs)",
                        padding: "2px 8px",
                        flexShrink: 0
                      }}>
                        {alert.status}
                      </span>
                        </div>
                    {alert.message && (
                        <div style={{ 
                          fontSize: "var(--font-size-xs)", 
                        color: "var(--color-text-secondary)",
                        lineHeight: 1.4,
                        marginBottom: "var(--space-2)"
                        }}>
                        {alert.message.length > 50 ? `${alert.message.substring(0, 50)}...` : alert.message}
                      </div>
                    )}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "var(--space-2)" }}>
                      <span style={{ 
                        fontSize: "var(--font-size-xs)",
                        color: getPriorityColor(alert.priority),
                        fontWeight: "var(--font-weight-semibold)"
                      }}>
                        {alert.priority}
                      </span>
                      <span style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)" }}>
                        {formatTimeAgo(alert.triggered_at)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
