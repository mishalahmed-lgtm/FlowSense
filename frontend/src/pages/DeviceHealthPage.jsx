import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

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
  const [batteryTrendExpanded, setBatteryTrendExpanded] = useState(false);
  const [batteryDaysFilter, setBatteryDaysFilter] = useState(10);
  const [batteryFilterMode, setBatteryFilterMode] = useState("days"); // "days" or "dateRange"
  const [batteryFromDate, setBatteryFromDate] = useState("");
  const [batteryToDate, setBatteryToDate] = useState("");

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
  }, [token, statusFilter]);

  const loadBatteryTrend = async (deviceId, days, fromDate = null, toDate = null) => {
    try {
      // Ensure deviceId is a number (the database ID, not the string identifier)
      const numericDeviceId = typeof deviceId === 'string' ? parseInt(deviceId, 10) : deviceId;
      if (isNaN(numericDeviceId)) {
        console.error("Invalid device ID:", deviceId);
        setBatteryTrend(null);
        return;
      }
      
      const params = {};
      if (fromDate && toDate) {
        // Use date range - calculate days from the range
        const from = new Date(fromDate);
        const to = new Date(toDate);
        const diffTime = Math.abs(to - from);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        params.days = Math.max(diffDays, 1);
      } else {
        params.days = days;
      }
      
      const batteryResp = await api.get(`/devices/${numericDeviceId}/health/battery-trend`, {
        params
      });
      
      if (batteryResp.data && batteryResp.data.data_points && batteryResp.data.data_points.length > 0) {
        let filteredData = batteryResp.data.data_points;
        
        // Filter by date range if specified
        if (fromDate && toDate) {
          const from = new Date(fromDate);
          const to = new Date(toDate);
          to.setHours(23, 59, 59, 999); // Include the entire end date
          
          filteredData = filteredData.filter((point) => {
            const pointDate = new Date(point.timestamp);
            return pointDate >= from && pointDate <= to;
          });
        }
        
        // Group by date and keep only the latest reading per date
        const groupedByDate = {};
        filteredData.forEach((point) => {
          const dateKey = new Date(point.timestamp).toDateString();
          if (!groupedByDate[dateKey] || new Date(point.timestamp) > new Date(groupedByDate[dateKey].timestamp)) {
            groupedByDate[dateKey] = point;
          }
        });
        
        const uniqueDataPoints = Object.values(groupedByDate).sort((a, b) => 
          new Date(a.timestamp) - new Date(b.timestamp)
        );
        
        setBatteryTrend({ ...batteryResp.data, data_points: uniqueDataPoints });
      } else {
        // No data available
        setBatteryTrend({ data_points: [] });
      }
    } catch (err) {
      console.error("Error loading battery trend:", err);
      // Battery trend might not be available
      setBatteryTrend({ data_points: [] });
    }
  };

  const handleViewDetails = async (device) => {
    setSelectedDevice(device);
    setShowDetails(true);
    setBatteryTrendExpanded(false); // Reset expanded state for new device
    setBatteryFilterMode("days"); // Reset to days filter
    // Set default date range (last 10 days)
    const toDate = new Date();
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - 10);
    setBatteryToDate(toDate.toISOString().split('T')[0]);
    setBatteryFromDate(fromDate.toISOString().split('T')[0]);
    
    try {
      // Load health history
      const historyResp = await api.get(`/devices/${device.device_id}/health/history`, {
        params: { hours: 168 } // 7 days
      });
      setDeviceHistory(historyResp.data);
      
      // Load battery trend
      await loadBatteryTrend(device.device_id, batteryDaysFilter);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load device details");
    }
  };

  const handleBatteryFilterChange = async () => {
    if (selectedDevice) {
      if (batteryFilterMode === "dateRange" && batteryFromDate && batteryToDate) {
        await loadBatteryTrend(selectedDevice.device_id, null, batteryFromDate, batteryToDate);
      } else {
        await loadBatteryTrend(selectedDevice.device_id, batteryDaysFilter);
      }
    }
  };

  const handleBatteryDaysFilterChange = async (days) => {
    setBatteryDaysFilter(days);
    setBatteryFilterMode("days");
    if (selectedDevice) {
      await loadBatteryTrend(selectedDevice.device_id, days);
    }
  };

  const handleBatteryDateRangeChange = async () => {
    if (batteryFromDate && batteryToDate) {
      setBatteryFilterMode("dateRange");
      await handleBatteryFilterChange();
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
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Device Health Monitoring</h1>
          <p className="page-header__subtitle">
            Uptime, connectivity, and battery trends across your devices
          </p>
        </div>
        <div className="page-header__actions" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
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
          <button className="btn btn--secondary" onClick={loadDevices}>
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      <div className="card">
        <div className="table-wrapper">
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
                      className="btn btn--sm btn--secondary"
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
            <div className="form-group" style={{ marginBottom: "var(--space-6)" }}>
              <h3 style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>Current Status</h3>
              <div className="form-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-4)" }}>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Status
                  </div>
                  <span className={getStatusBadge(selectedDevice.current_status)} style={{ fontSize: "var(--font-size-sm)" }}>
                    {selectedDevice.current_status}
                  </span>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Last Seen
                  </div>
                  <div style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                    {formatTimeAgo(selectedDevice.last_seen_at)}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    First Seen
                  </div>
                  <div style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-medium)", color: "var(--color-text-primary)" }}>
                  {selectedDevice.first_seen_at
                      ? new Date(selectedDevice.first_seen_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
                    : "N/A"}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Last Calculated
                  </div>
                  <div style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                  {selectedDevice.calculated_at
                    ? formatTimeAgo(selectedDevice.calculated_at)
                    : "N/A"}
                  </div>
                </div>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: "var(--space-6)" }}>
              <h3 style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>Uptime Metrics</h3>
              <div className="form-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-4)" }}>
                <div style={{ 
                  padding: "var(--space-5)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)",
                  textAlign: "center"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-3)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    24 Hours
                  </div>
                  <div style={{ fontSize: "var(--font-size-3xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-primary)" }}>
                    {formatUptime(selectedDevice.uptime_24h_percent)}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-5)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)",
                  textAlign: "center"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-3)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    7 Days
                  </div>
                  <div style={{ fontSize: "var(--font-size-3xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-primary)" }}>
                    {formatUptime(selectedDevice.uptime_7d_percent)}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-5)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)",
                  textAlign: "center"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-3)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    30 Days
                  </div>
                  <div style={{ fontSize: "var(--font-size-3xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-primary)" }}>
                    {formatUptime(selectedDevice.uptime_30d_percent)}
                  </div>
                </div>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: "var(--space-6)" }}>
              <h3 style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>Connectivity Metrics</h3>
              <div className="form-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-4)" }}>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Connectivity Score
                  </div>
                  <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-text-primary)" }}>
                  {selectedDevice.connectivity_score !== null
                    ? `${selectedDevice.connectivity_score.toFixed(1)}%`
                    : "N/A"}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Messages (24h)
                  </div>
                  <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-text-primary)" }}>
                    {selectedDevice.message_count_24h || 0}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Messages (7d)
                  </div>
                  <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-text-primary)" }}>
                    {selectedDevice.message_count_7d || 0}
                  </div>
                </div>
                <div style={{ 
                  padding: "var(--space-4)", 
                  backgroundColor: "var(--color-bg-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--color-border-light)"
                }}>
                  <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                    Avg Interval
                  </div>
                  <div style={{ fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)" }}>
                  {selectedDevice.avg_message_interval_seconds
                      ? `${(selectedDevice.avg_message_interval_seconds / 60).toFixed(1)} min`
                    : "N/A"}
                  </div>
                </div>
              </div>
            </div>

            {selectedDevice.last_battery_level !== null && (
              <div className="form-group" style={{ marginBottom: "var(--space-6)" }}>
                <h3 style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-lg)", fontWeight: "var(--font-weight-semibold)" }}>Battery Status</h3>
                <div className="form-grid" style={{ gridTemplateColumns: selectedDevice.estimated_battery_days_remaining ? "repeat(3, 1fr)" : "repeat(2, 1fr)", gap: "var(--space-6)" }}>
                  <div style={{ 
                    padding: "var(--space-4)", 
                    backgroundColor: "var(--color-bg-secondary)", 
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border-light)"
                  }}>
                    <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                      Current Level
                    </div>
                    <div style={{ fontSize: "var(--font-size-3xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-success-text)" }}>
                      {selectedDevice.last_battery_level.toFixed(1)}%
                    </div>
                  </div>
                  <div style={{ 
                    padding: "var(--space-4)", 
                    backgroundColor: "var(--color-bg-secondary)", 
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border-light)"
                  }}>
                    <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                      Trend
                    </div>
                    <div style={{ fontSize: "var(--font-size-xl)", fontWeight: "var(--font-weight-semibold)", color: "var(--color-text-primary)", textTransform: "capitalize" }}>
                      {selectedDevice.battery_trend || "N/A"}
                    </div>
                  </div>
                  {selectedDevice.estimated_battery_days_remaining && (
                    <div style={{ 
                      padding: "var(--space-4)", 
                      backgroundColor: "var(--color-bg-secondary)", 
                      borderRadius: "var(--radius-lg)",
                      border: "1px solid var(--color-border-light)"
                    }}>
                      <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: "var(--font-weight-medium)" }}>
                        Days Remaining
                      </div>
                      <div style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)", color: "var(--color-text-primary)" }}>
                        {selectedDevice.estimated_battery_days_remaining}
                        <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "var(--font-weight-normal)", color: "var(--color-text-secondary)", marginLeft: "var(--space-1)" }}>days</span>
                      </div>
                    </div>
                  )}
                </div>
                {batteryTrend && (
                  <div style={{ 
                    marginTop: "var(--space-6)", 
                    padding: "var(--space-5)",
                    backgroundColor: "var(--color-bg-secondary)",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border-light)"
                  }}>
                    <div>
                      <div style={{ 
                        display: "flex", 
                        alignItems: "center", 
                        justifyContent: "space-between",
                        marginBottom: "var(--space-4)",
                        paddingBottom: "var(--space-4)",
                        borderBottom: "1px solid var(--color-border-light)"
                      }}>
                        <button
                          onClick={() => setBatteryTrendExpanded(!batteryTrendExpanded)}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "var(--space-2)",
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            color: "var(--color-text-primary)",
                            fontSize: "var(--font-size-base)",
                            fontWeight: "var(--font-weight-semibold)",
                          }}
                        >
                          <span>Battery History</span>
                          <div style={{ 
                            display: "flex", 
                            alignItems: "center", 
                            justifyContent: "center",
                            width: "32px",
                            height: "32px",
                            borderRadius: "var(--radius-md)",
                            backgroundColor: batteryTrendExpanded ? "var(--color-bg-app)" : "transparent",
                            transition: "all 0.2s ease"
                          }}>
                            <Icon name={batteryTrendExpanded ? "chevron-up" : "chevron-down"} size={18} />
                          </div>
                        </button>
                      </div>
                      
                      {/* Filter Section - Only show when expanded */}
                      {batteryTrendExpanded && (
                        <div style={{ marginBottom: "var(--space-5)" }}>
                          <div style={{ 
                            display: "flex", 
                            gap: "var(--space-2)",
                            padding: "var(--space-1)",
                            backgroundColor: "var(--color-bg-app)",
                            borderRadius: "var(--radius-md)",
                            marginBottom: "var(--space-4)",
                            width: "fit-content"
                          }}>
                            <button
                              onClick={() => {
                                setBatteryFilterMode("days");
                                handleBatteryDaysFilterChange(batteryDaysFilter);
                              }}
                              style={{
                                padding: "var(--space-2) var(--space-4)",
                                border: "none",
                                borderRadius: "var(--radius-sm)",
                                cursor: "pointer",
                                fontSize: "var(--font-size-sm)",
                                fontWeight: "var(--font-weight-medium)",
                                backgroundColor: batteryFilterMode === "days" ? "var(--color-primary)" : "transparent",
                                color: batteryFilterMode === "days" ? "white" : "var(--color-text-secondary)",
                                transition: "all 0.2s ease"
                              }}
                            >
                              Quick Select
                            </button>
                            <button
                              onClick={() => setBatteryFilterMode("dateRange")}
                              style={{
                                padding: "var(--space-2) var(--space-4)",
                                border: "none",
                                borderRadius: "var(--radius-sm)",
                                cursor: "pointer",
                                fontSize: "var(--font-size-sm)",
                                fontWeight: "var(--font-weight-medium)",
                                backgroundColor: batteryFilterMode === "dateRange" ? "var(--color-primary)" : "transparent",
                                color: batteryFilterMode === "dateRange" ? "white" : "var(--color-text-secondary)",
                                transition: "all 0.2s ease"
                              }}
                            >
                              Custom Range
                            </button>
                          </div>
                          
                          {batteryFilterMode === "days" ? (
                            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                              {[7, 10, 14, 30].map((days) => (
                                <button
                                  key={days}
                                  onClick={() => handleBatteryDaysFilterChange(days)}
                                  style={{
                                    padding: "var(--space-2) var(--space-4)",
                                    border: `2px solid ${batteryDaysFilter === days ? "var(--color-primary)" : "var(--color-border-medium)"}`,
                                    borderRadius: "var(--radius-md)",
                                    cursor: "pointer",
                                    fontSize: "var(--font-size-sm)",
                                    fontWeight: "var(--font-weight-medium)",
                                    backgroundColor: batteryDaysFilter === days ? "rgba(59, 130, 246, 0.1)" : "var(--color-bg-app)",
                                    color: batteryDaysFilter === days ? "var(--color-primary)" : "var(--color-text-primary)",
                                    transition: "all 0.2s ease"
                                  }}
                                >
                                  Last {days} days
                                </button>
                              ))}
                            </div>
                          ) : (
                            <div style={{ 
                              display: "flex", 
                              flexDirection: "column",
                              gap: "var(--space-3)",
                              padding: "var(--space-4)",
                              backgroundColor: "var(--color-bg-app)",
                              borderRadius: "var(--radius-md)"
                            }}>
                              <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", fontWeight: "var(--font-weight-medium)" }}>
                                Select Date Range
                              </div>
                              <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
                                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                                  <label style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                                    From Date
                                  </label>
                                  <input
                                    type="date"
                                    className="form-input"
                                    value={batteryFromDate}
                                    onChange={(e) => {
                                      setBatteryFromDate(e.target.value);
                                      if (e.target.value && batteryToDate) {
                                        handleBatteryDateRangeChange();
                                      }
                                    }}
                                    style={{ 
                                      fontSize: "var(--font-size-sm)",
                                      padding: "var(--space-2) var(--space-3)"
                                    }}
                                  />
                                </div>
                                <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-tertiary)", marginTop: "var(--space-4)" }}>→</div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                                  <label style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                                    To Date
                                  </label>
                                  <input
                                    type="date"
                                    className="form-input"
                                    value={batteryToDate}
                                    onChange={(e) => {
                                      setBatteryToDate(e.target.value);
                                      if (batteryFromDate && e.target.value) {
                                        handleBatteryDateRangeChange();
                                      }
                                    }}
                                    style={{ 
                                      fontSize: "var(--font-size-sm)",
                                      padding: "var(--space-2) var(--space-3)"
                                    }}
                                  />
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    {batteryTrendExpanded && (
                      <div>
                        {batteryTrend.data_points && batteryTrend.data_points.length > 0 ? (
                          <>
                            <div style={{ 
                              marginBottom: "var(--space-5)", 
                              height: "280px",
                              padding: "var(--space-4)",
                              backgroundColor: "var(--color-bg-app)",
                              borderRadius: "var(--radius-md)"
                            }}>
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart
                                  data={batteryTrend.data_points.map((point) => ({
                                    date: new Date(point.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
                                    fullDate: new Date(point.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
                                    battery: parseFloat(point.battery_level.toFixed(1)),
                                    timestamp: point.timestamp,
                                  }))}
                                  margin={{ top: 10, right: 10, left: -20, bottom: 10 }}
                                >
                              <defs>
                                <linearGradient id="batteryGradient" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                              <XAxis
                                dataKey="date"
                                tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
                                stroke="rgba(255,255,255,0.1)"
                                tickLine={false}
                              />
                              <YAxis
                                domain={[0, 100]}
                                tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
                                stroke="rgba(255,255,255,0.1)"
                                tickLine={false}
                                label={{ 
                                  value: "Battery Level (%)", 
                                  angle: -90, 
                                  position: "insideLeft", 
                                  fill: "var(--color-text-tertiary)",
                                  style: { textAnchor: 'middle', fontSize: 11 }
                                }}
                              />
                              <Tooltip
                                contentStyle={{
                                  backgroundColor: "var(--color-bg-card)",
                                  border: "1px solid var(--color-border-medium)",
                                  borderRadius: "var(--radius-md)",
                                  padding: "var(--space-3)",
                                  boxShadow: "var(--shadow-lg)"
                                }}
                                labelStyle={{ 
                                  color: "var(--color-text-primary)", 
                                  fontWeight: "var(--font-weight-semibold)",
                                  marginBottom: "var(--space-2)"
                                }}
                                itemStyle={{
                                  color: "var(--color-success-text)",
                                  fontWeight: "var(--font-weight-medium)"
                                }}
                                formatter={(value) => [`${value}%`, 'Battery']}
                                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullDate || label}
                              />
                              <Line
                                type="monotone"
                                dataKey="battery"
                                stroke="#10b981"
                                strokeWidth={3}
                                dot={{ fill: "#10b981", r: 5, strokeWidth: 2, stroke: "var(--color-bg-app)" }}
                                activeDot={{ r: 7, strokeWidth: 2 }}
                                fill="url(#batteryGradient)"
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                            <>
                              <div style={{ 
                                fontSize: "var(--font-size-sm)", 
                                color: "var(--color-text-secondary)", 
                                marginBottom: "var(--space-3)",
                                fontWeight: "var(--font-weight-medium)"
                              }}>
                                Showing {batteryTrend.data_points.length} {batteryTrend.data_points.length === 1 ? 'reading' : 'readings'}
                              </div>
                              <div style={{ 
                                display: "grid", 
                                gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
                                gap: "var(--space-3)"
                              }}>
                                {batteryTrend.data_points.map((point, idx) => {
                                  const batteryLevel = point.battery_level;
                                  const batteryColor = batteryLevel > 50 ? "var(--color-success-text)" : batteryLevel > 20 ? "var(--color-warning-text)" : "var(--color-error-text)";
                                  const dateObj = new Date(point.timestamp);
                                  return (
                                    <div key={idx} style={{ 
                                      display: "flex", 
                                      alignItems: "center",
                                      justifyContent: "space-between",
                                      padding: "var(--space-3)",
                                      backgroundColor: "var(--color-bg-app)",
                                      borderRadius: "var(--radius-md)",
                                      border: "1px solid rgba(255,255,255,0.05)"
                                    }}>
                                      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
                                        <span style={{ 
                                          fontSize: "var(--font-size-sm)", 
                                          color: "var(--color-text-primary)",
                                          fontWeight: "var(--font-weight-medium)"
                                        }}>
                                          {dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                                        </span>
                                        <span style={{ 
                                          fontSize: "var(--font-size-xs)", 
                                          color: "var(--color-text-tertiary)"
                                        }}>
                                          {dateObj.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}
                                        </span>
                                      </div>
                                      <span style={{ 
                                        fontSize: "var(--font-size-xl)", 
                                        fontWeight: "var(--font-weight-bold)", 
                                        color: batteryColor
                                      }}>
                                        {point.battery_level.toFixed(1)}%
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </>
                          </>
                        ) : (
                          <div style={{
                            padding: "var(--space-8)",
                            textAlign: "center",
                            backgroundColor: "var(--color-bg-app)",
                            borderRadius: "var(--radius-md)"
                          }}>
                            <div style={{ fontSize: "var(--font-size-3xl)", marginBottom: "var(--space-3)" }}>📊</div>
                            <p style={{ 
                              fontSize: "var(--font-size-base)", 
                              color: "var(--color-text-primary)",
                              fontWeight: "var(--font-weight-medium)",
                              margin: 0,
                              marginBottom: "var(--space-2)"
                            }}>
                              No Battery Data Available
                            </p>
                            <p style={{ 
                              fontSize: "var(--font-size-sm)", 
                              color: "var(--color-text-tertiary)",
                              margin: 0
                            }}>
                              No battery readings found for the selected time period. Try selecting a different date range.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

          </div>
        )}
      </Modal>
    </div>
  );
}

