import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";

export default function DeviceHealthPage() {
  const { token, isTenantAdmin, hasModule } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [deviceHistory, setDeviceHistory] = useState([]);
  const [batteryTrend, setBatteryTrend] = useState(null);

  // Only tenant admins with health module can access
  if (!isTenantAdmin || !hasModule("health")) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires health monitoring module access.</p>
        </div>
      </div>
    );
  }

  const loadDevices = async () => {
    try {
      setLoading(true);
      const params = {};
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      const response = await api.get("/devices/health", { params });
      setDevices(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load device health data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadDevices();
    
    // Auto-refresh every 60 seconds
    const interval = setInterval(loadDevices, 60000);
    return () => clearInterval(interval);
  }, [token, statusFilter]);

  const handleViewDetails = async (device) => {
    setSelectedDevice(device);
    setShowDetails(true);
    
    try {
      // Load health history
      const historyResp = await api.get(`/devices/${device.device_id}/health/history`, {
        params: { hours: 168 } // 7 days
      });
      setDeviceHistory(historyResp.data);
      
      // Load battery trend
      try {
        const batteryResp = await api.get(`/devices/${device.device_id}/health/battery-trend`, {
          params: { days: 7 }
        });
        setBatteryTrend(batteryResp.data);
      } catch (err) {
        // Battery trend might not be available
        setBatteryTrend(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load device details");
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      online: "badge badge--success",
      offline: "badge badge--error",
      degraded: "badge badge--warning",
      unknown: "badge badge--secondary",
    };
    return badges[status] || badges.unknown;
  };

  const formatUptime = (percent) => {
    if (percent === null || percent === undefined) return "N/A";
    return `${percent.toFixed(1)}%`;
  };

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (loading && devices.length === 0) {
    return (
      <div className="page">
        <div className="card">
          <p>Loading device health data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Device Health Monitoring", path: "/health" }]} />
      
      <div className="page-header">
        <h1>Device Health Monitoring</h1>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: "auto" }}
          >
            <option value="all">All Status</option>
            <option value="online">Online</option>
            <option value="degraded">Degraded</option>
            <option value="offline">Offline</option>
          </select>
          <button className="btn btn-secondary" onClick={loadDevices}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card card--error">
          <p className="text-error">{error}</p>
        </div>
      )}

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Device</th>
              <th>Status</th>
              <th>Last Seen</th>
              <th>Uptime (24h)</th>
              <th>Uptime (7d)</th>
              <th>Uptime (30d)</th>
              <th>Connectivity</th>
              <th>Battery</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {devices.length === 0 ? (
              <tr>
                <td colSpan="9" className="text-center text-muted">
                  No devices found {statusFilter !== "all" ? `with status "${statusFilter}"` : ""}
                </td>
              </tr>
            ) : (
              devices.map((device) => (
                <tr key={device.device_id}>
                  <td>
                    <div>
                      <strong>{device.device_name}</strong>
                      <br />
                      <small className="text-muted">{device.device_identifier}</small>
                    </div>
                  </td>
                  <td>
                    <span className={getStatusBadge(device.current_status)}>
                      {device.current_status}
                    </span>
                  </td>
                  <td>{formatTimeAgo(device.last_seen_at)}</td>
                  <td>{formatUptime(device.uptime_24h_percent)}</td>
                  <td>{formatUptime(device.uptime_7d_percent)}</td>
                  <td>{formatUptime(device.uptime_30d_percent)}</td>
                  <td>
                    {device.connectivity_score !== null ? (
                      <div>
                        <span>{device.connectivity_score.toFixed(0)}%</span>
                        <br />
                        <small className="text-muted">
                          {device.message_count_24h} msgs/24h
                        </small>
                      </div>
                    ) : (
                      "N/A"
                    )}
                  </td>
                  <td>
                    {device.last_battery_level !== null ? (
                      <div>
                        <span>{device.last_battery_level.toFixed(1)}%</span>
                        {device.battery_trend && (
                          <>
                            <br />
                            <small className="text-muted">
                              {device.battery_trend === "decreasing" && "↓"}
                              {device.battery_trend === "increasing" && "↑"}
                              {device.battery_trend === "stable" && "→"}
                              {device.battery_trend}
                            </small>
                            {device.estimated_battery_days_remaining && (
                              <small className="text-muted" style={{ display: "block" }}>
                                ~{device.estimated_battery_days_remaining}d left
                              </small>
                            )}
                          </>
                        )}
                      </div>
                    ) : (
                      "N/A"
                    )}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleViewDetails(device)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Device Details Modal */}
      <Modal
        isOpen={showDetails}
        onClose={() => {
          setShowDetails(false);
          setSelectedDevice(null);
          setDeviceHistory([]);
          setBatteryTrend(null);
        }}
        title={selectedDevice ? `Health Details: ${selectedDevice.device_name}` : ""}
      >
        {selectedDevice && (
          <div>
            <div className="form-group">
              <h3>Current Status</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-3)" }}>
                <div>
                  <strong>Status:</strong>{" "}
                  <span className={getStatusBadge(selectedDevice.current_status)}>
                    {selectedDevice.current_status}
                  </span>
                </div>
                <div>
                  <strong>Last Seen:</strong> {formatTimeAgo(selectedDevice.last_seen_at)}
                </div>
                <div>
                  <strong>First Seen:</strong>{" "}
                  {selectedDevice.first_seen_at
                    ? new Date(selectedDevice.first_seen_at).toLocaleString()
                    : "N/A"}
                </div>
                <div>
                  <strong>Last Calculated:</strong>{" "}
                  {selectedDevice.calculated_at
                    ? formatTimeAgo(selectedDevice.calculated_at)
                    : "N/A"}
                </div>
              </div>
            </div>

            <div className="form-group">
              <h3>Uptime Metrics</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)" }}>
                <div>
                  <strong>24 Hours:</strong>
                  <div style={{ fontSize: "1.5em", fontWeight: "bold" }}>
                    {formatUptime(selectedDevice.uptime_24h_percent)}
                  </div>
                </div>
                <div>
                  <strong>7 Days:</strong>
                  <div style={{ fontSize: "1.5em", fontWeight: "bold" }}>
                    {formatUptime(selectedDevice.uptime_7d_percent)}
                  </div>
                </div>
                <div>
                  <strong>30 Days:</strong>
                  <div style={{ fontSize: "1.5em", fontWeight: "bold" }}>
                    {formatUptime(selectedDevice.uptime_30d_percent)}
                  </div>
                </div>
              </div>
            </div>

            <div className="form-group">
              <h3>Connectivity Metrics</h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-3)" }}>
                <div>
                  <strong>Connectivity Score:</strong>{" "}
                  {selectedDevice.connectivity_score !== null
                    ? `${selectedDevice.connectivity_score.toFixed(1)}%`
                    : "N/A"}
                </div>
                <div>
                  <strong>Messages (24h):</strong> {selectedDevice.message_count_24h}
                </div>
                <div>
                  <strong>Messages (7d):</strong> {selectedDevice.message_count_7d}
                </div>
                <div>
                  <strong>Avg Interval:</strong>{" "}
                  {selectedDevice.avg_message_interval_seconds
                    ? `${(selectedDevice.avg_message_interval_seconds / 60).toFixed(1)} minutes`
                    : "N/A"}
                </div>
              </div>
            </div>

            {selectedDevice.last_battery_level !== null && (
              <div className="form-group">
                <h3>Battery Status</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-3)" }}>
                  <div>
                    <strong>Current Level:</strong> {selectedDevice.last_battery_level.toFixed(1)}%
                  </div>
                  <div>
                    <strong>Trend:</strong> {selectedDevice.battery_trend || "N/A"}
                  </div>
                  {selectedDevice.estimated_battery_days_remaining && (
                    <div>
                      <strong>Estimated Days Remaining:</strong>{" "}
                      {selectedDevice.estimated_battery_days_remaining} days
                    </div>
                  )}
                </div>
                {batteryTrend && batteryTrend.data_points && batteryTrend.data_points.length > 0 && (
                  <div style={{ marginTop: "var(--space-3)" }}>
                    <strong>Battery Trend (7 days):</strong>
                    <div style={{ marginTop: "var(--space-2)" }}>
                      {batteryTrend.data_points.map((point, idx) => (
                        <div key={idx} style={{ fontSize: "0.9em", marginBottom: "4px" }}>
                          {new Date(point.timestamp).toLocaleDateString()}: {point.battery_level.toFixed(1)}%
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {deviceHistory.length > 0 && (
              <div className="form-group">
                <h3>Health History (Last 7 Days)</h3>
                <div style={{ maxHeight: "300px", overflowY: "auto" }}>
                  <table className="table" style={{ fontSize: "0.9em" }}>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Status</th>
                        <th>Battery</th>
                        <th>Uptime (24h)</th>
                        <th>Connectivity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deviceHistory.slice(0, 50).map((h, idx) => (
                        <tr key={idx}>
                          <td>{new Date(h.snapshot_at).toLocaleString()}</td>
                          <td>
                            <span className={getStatusBadge(h.status)}>{h.status}</span>
                          </td>
                          <td>{h.battery_level !== null ? `${h.battery_level.toFixed(1)}%` : "N/A"}</td>
                          <td>{formatUptime(h.uptime_24h_percent)}</td>
                          <td>
                            {h.connectivity_score !== null
                              ? `${h.connectivity_score.toFixed(0)}%`
                              : "N/A"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

