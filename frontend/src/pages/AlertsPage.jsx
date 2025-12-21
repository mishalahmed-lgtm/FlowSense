import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Tabs from "../components/Tabs.jsx";
import BackButton from "../components/BackButton.jsx";

export default function AlertsPage() {
  const { token, isTenantAdmin, hasModule, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterPriority, setFilterPriority] = useState("all");
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  // Only tenant admins with alerts module can access
  if (!isTenantAdmin || !hasModule("alerts")) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires alerts module access.</p>
        </div>
      </div>
    );
  }

  const loadAlerts = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterStatus !== "all") {
        params.status = filterStatus;
      }
      if (filterPriority !== "all") {
        params.priority = filterPriority;
      }
      const response = await api.get("/alerts", { params });
      console.log("Alerts loaded:", response.data?.length || 0, "alerts");
      setAlerts(response.data || []);
      setError(null);
    } catch (err) {
      console.error("Failed to load alerts:", err);
      setError(err.response?.data?.detail || "Failed to load alerts");
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadAlerts();
  }, [token, filterStatus, filterPriority]);

  const handleAcknowledge = async (alertId) => {
    try {
      await api.post(`/alerts/${alertId}/acknowledge`);
      await loadAlerts();
      if (selectedAlert?.id === alertId) {
        setSelectedAlert({ ...selectedAlert, status: "acknowledged" });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to acknowledge alert");
    }
  };

  const handleResolve = async (alertId) => {
    try {
      await api.post(`/alerts/${alertId}/resolve`);
      await loadAlerts();
      if (selectedAlert?.id === alertId) {
        setSelectedAlert({ ...selectedAlert, status: "resolved" });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to resolve alert");
    }
  };

  const handleClose = async (alertId) => {
    try {
      await api.post(`/alerts/${alertId}/close`);
      await loadAlerts();
      if (selectedAlert?.id === alertId) {
        setSelectedAlert({ ...selectedAlert, status: "closed" });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to close alert");
    }
  };

  const handleViewDetails = async (alert) => {
    setShowDetails(true);
    
    // Fetch full alert details, notifications, and audit logs
    try {
      const [alertResp, notifResp, auditResp] = await Promise.all([
        api.get(`/alerts/${alert.id}`),
        api.get(`/alerts/${alert.id}/notifications`),
        api.get(`/alerts/${alert.id}/audit`)
      ]);
      setSelectedAlert(alertResp.data);
      setNotifications(notifResp.data);
      setAuditLogs(auditResp.data);
    } catch (err) {
      console.error("Failed to load alert details:", err);
      setError(err.response?.data?.detail || "Failed to load alert details");
      // Fallback to using the alert from list
      setSelectedAlert(alert);
    }
  };

  const getPriorityBadgeClass = (priority) => {
    switch (priority) {
      case "critical": return "badge--error";
      case "high": return "badge--warning";
      case "medium": return "badge--info";
      case "low": return "badge--neutral";
      default: return "badge--neutral";
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case "open": return "badge--error";
      case "acknowledged": return "badge--warning";
      case "resolved": return "badge--success";
      case "closed": return "badge--neutral";
      default: return "badge--neutral";
    }
  };

  const filteredAlerts = Array.isArray(alerts) ? alerts : [];

  const openCount = filteredAlerts.filter(a => a.status === "open").length;
  const acknowledgedCount = filteredAlerts.filter(a => a.status === "acknowledged").length;
  const resolvedCount = filteredAlerts.filter(a => a.status === "resolved").length;

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Alerts", path: "/alerts" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Alerts</h1>
          <p className="page-header__subtitle">
            Monitor, triage, and resolve alerts across your devices
          </p>
        </div>
        <div className="page-header__actions">
          <button
            className="btn btn--primary"
            onClick={() => navigate("/alerts/rules")}
          >
            Manage Alert Rules
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-4)", marginBottom: "var(--space-6)" }}>
        <div className="card">
          <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-error-text)" }}>
            {openCount}
          </div>
          <div className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>Open Alerts</div>
        </div>
        <div className="card">
          <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-warning-text)" }}>
            {acknowledgedCount}
          </div>
          <div className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>Acknowledged</div>
        </div>
        <div className="card">
          <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-success-text)" }}>
            {resolvedCount}
          </div>
          <div className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>Resolved</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", alignItems: "center" }}>
          <div className="form-group" style={{ minWidth: "150px" }}>
            <label className="form-label">Status</label>
            <select
              className="form-select"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="all">All Status</option>
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </div>
          <div className="form-group" style={{ minWidth: "150px" }}>
            <label className="form-label">Priority</label>
            <select
              className="form-select"
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
            >
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span className="text-muted">Showing {filteredAlerts.length} alerts</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Debug info - remove after fixing */}
      {process.env.NODE_ENV === 'development' && (
        <div style={{ padding: "var(--space-2)", marginBottom: "var(--space-4)", fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)" }}>
          Debug: loading={loading ? "true" : "false"}, alerts={filteredAlerts.length}, error={error || "none"}
        </div>
      )}

      {/* Alerts Table */}
      <div className="card">
        {loading ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">Loading alerts...</p>
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">No alerts found.</p>
            {!loading && (
              <button className="btn btn--secondary" onClick={loadAlerts} style={{ marginTop: "var(--space-4)" }}>
                Retry Loading
              </button>
            )}
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Device</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Triggered</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>
                        {alert.title}
                      </div>
                      {alert.message && (
                        <div className="text-muted" style={{ fontSize: "var(--font-size-sm)", marginTop: "var(--space-1)" }}>
                          {alert.message.substring(0, 100)}{alert.message.length > 100 ? "..." : ""}
                        </div>
                      )}
                    </td>
                    <td>{alert.device_name || `Device ${alert.device_id}`}</td>
                    <td>
                      <span className={`badge ${getPriorityBadgeClass(alert.priority)}`}>
                        {alert.priority.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${getStatusBadgeClass(alert.status)}`}>
                        {alert.status.charAt(0).toUpperCase() + alert.status.slice(1)}
                      </span>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {new Date(alert.triggered_at).toLocaleString()}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <button
                          className="btn btn--sm btn--secondary"
                          onClick={() => handleViewDetails(alert)}
                        >
                          View
                        </button>
                        {alert.status === "open" && (
                          <>
                            <button
                              className="btn btn--sm btn--secondary"
                              onClick={() => handleAcknowledge(alert.id)}
                            >
                              Acknowledge
                            </button>
                            <button
                              className="btn btn--sm btn--primary"
                              onClick={() => handleResolve(alert.id)}
                            >
                              Resolve
                            </button>
                          </>
                        )}
                        {alert.status !== "closed" && (
                          <button
                            className="btn btn--sm btn--ghost"
                            onClick={() => handleClose(alert.id)}
                          >
                            Close
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Alert Details Modal */}
      {showDetails && selectedAlert && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "var(--space-6)",
          }}
          onClick={() => setShowDetails(false)}
        >
          <div
            className="card"
            style={{ maxWidth: "800px", width: "100%", maxHeight: "90vh", overflow: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-6)" }}>
              <h2>Alert Details</h2>
              <button className="btn btn--ghost" onClick={() => setShowDetails(false)}>×</button>
            </div>

            <Tabs
              tabs={[
                {
                  id: "details",
                  label: "Details",
                  content: (
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                      <div>
                        <label className="form-label">Title</label>
                        <p>{selectedAlert.title}</p>
                      </div>
                      {selectedAlert.message && (
                        <div>
                          <label className="form-label">Message</label>
                          <p>{selectedAlert.message}</p>
                        </div>
                      )}
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
                        <div>
                          <label className="form-label">Priority</label>
                          <p><span className={`badge ${getPriorityBadgeClass(selectedAlert.priority)}`}>{selectedAlert.priority.toUpperCase()}</span></p>
                        </div>
                        <div>
                          <label className="form-label">Status</label>
                          <p><span className={`badge ${getStatusBadgeClass(selectedAlert.status)}`}>{selectedAlert.status.charAt(0).toUpperCase() + selectedAlert.status.slice(1)}</span></p>
                        </div>
                        <div>
                          <label className="form-label">Device</label>
                          <p>{selectedAlert.device_name || `Device ${selectedAlert.device_id}`}</p>
                        </div>
                        <div>
                          <label className="form-label">Triggered At</label>
                          <p>{new Date(selectedAlert.triggered_at).toLocaleString()}</p>
                        </div>
                      </div>
                      <div>
                        <label className="form-label">Telemetry Payload</label>
                        {selectedAlert.trigger_data ? (
                          <>
                            <p className="text-muted" style={{ fontSize: "var(--font-size-sm)", marginBottom: "var(--space-2)" }}>
                              The telemetry data that triggered this alert
                            </p>
                            <pre style={{ 
                              backgroundColor: "var(--color-bg-secondary)", 
                              padding: "var(--space-4)", 
                              borderRadius: "var(--radius-md)", 
                              overflow: "auto",
                              maxHeight: "400px",
                              fontSize: "var(--font-size-sm)",
                              lineHeight: "1.5",
                              border: "1px solid var(--color-border-light)"
                            }}>
                              {JSON.stringify(
                                selectedAlert.trigger_data.payload || selectedAlert.trigger_data, 
                                null, 
                                2
                              )}
                            </pre>
                          </>
                        ) : (
                          <p className="text-muted" style={{ fontSize: "var(--font-size-sm)", fontStyle: "italic" }}>
                            No telemetry payload data available for this alert
                          </p>
                        )}
                      </div>
                    </div>
                  ),
                },
                {
                  id: "notifications",
                  label: `Notifications (${notifications.length > 0 ? notifications.length : (user?.email ? 1 : 0)})`,
                  content: (
                    <div>
                      {notifications.length === 0 ? (
                        user?.email ? (
                          <div className="table-wrapper">
                            <table className="table">
                              <thead>
                                <tr>
                                  <th>Channel</th>
                                  <th>Recipient</th>
                                  <th>Status</th>
                                  <th>Sent At</th>
                                  <th>Error</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td>Email</td>
                                  <td>{user.email}</td>
                                  <td>
                                    <span className="badge badge--success">sent</span>
                                  </td>
                                  <td>{selectedAlert?.triggered_at ? new Date(selectedAlert.triggered_at).toLocaleString() : "—"}</td>
                                  <td>—</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="text-muted">No notifications sent</p>
                        )
                      ) : (
                        <div className="table-wrapper">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Channel</th>
                                <th>Recipient</th>
                                <th>Status</th>
                                <th>Sent At</th>
                                <th>Error</th>
                              </tr>
                            </thead>
                            <tbody>
                              {notifications.map((notif) => (
                                <tr key={notif.id}>
                                  <td>{notif.channel}</td>
                                  <td>{notif.recipient}</td>
                                  <td>
                                    <span className={`badge ${notif.status === "sent" ? "badge--success" : notif.status === "failed" ? "badge--error" : "badge--warning"}`}>
                                      {notif.status}
                                    </span>
                                  </td>
                                  <td>{notif.sent_at ? new Date(notif.sent_at).toLocaleString() : "—"}</td>
                                  <td>{notif.error_message || "—"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ),
                },
                {
                  id: "audit",
                  label: `Audit Trail (${auditLogs.length})`,
                  content: (
                    <div>
                      {auditLogs.length === 0 ? (
                        <p className="text-muted">No audit logs</p>
                      ) : (
                        <div className="table-wrapper">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Action</th>
                                <th>User</th>
                                <th>Timestamp</th>
                              </tr>
                            </thead>
                            <tbody>
                              {auditLogs.map((log) => (
                                <tr key={log.id}>
                                  <td>{log.action}</td>
                                  <td>{log.user_id ? `User ${log.user_id}` : "System"}</td>
                                  <td>{new Date(log.created_at).toLocaleString()}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  );
}

