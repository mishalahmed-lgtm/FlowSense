import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Responsive, WidthProvider } from "react-grid-layout";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import GaugeWidget from "../components/widgets/GaugeWidget.jsx";
import NumberWidget from "../components/widgets/NumberWidget.jsx";
import LineChartWidget from "../components/widgets/LineChartWidget.jsx";
import ThermometerWidget from "../components/widgets/ThermometerWidget.jsx";
import TankWidget from "../components/widgets/TankWidget.jsx";
import BatteryWidget from "../components/widgets/BatteryWidget.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Collapsible from "../components/Collapsible.jsx";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./DeviceDashboardPage.css";

const ResponsiveGridLayout = WidthProvider(Responsive);

const WIDGET_LIBRARY = [
  {
    id: "tank-level",
    type: "tank",
    title: "Tank Level",
    field: "level",
    unit: "%",
    min: 0,
    max: 100,
    icon: "🪣",
  },
  {
    id: "thermometer-temperature",
    type: "thermometer",
    title: "Temperature",
    field: "temperature",
    unit: "°C",
    min: -20,
    max: 50,
    icon: "🌡️",
  },
  {
    id: "battery-widget",
    type: "battery",
    title: "Battery Level",
    field: "battery",
    min: 0,
    max: 100,
    icon: "🔋",
  },
  {
    id: "gauge-level",
    type: "gauge",
    title: "Level Gauge",
    field: "level",
    unit: "%",
    min: 0,
    max: 100,
    icon: "📊",
  },
  {
    id: "gauge-pressure",
    type: "gauge",
    title: "Pressure Gauge",
    field: "pressure",
    unit: "bar",
    min: 0,
    max: 3,
    icon: "⚡",
  },
  {
    id: "number-pressure",
    type: "number",
    title: "Pressure (Number)",
    field: "pressure",
    unit: "bar",
    icon: "🔢",
  },
  {
    id: "chart-level",
    type: "chart",
    title: "Level History",
    field: "level",
    unit: "%",
    icon: "📈",
  },
  {
    id: "chart-temperature",
    type: "chart",
    title: "Temperature History",
    field: "temperature",
    unit: "°C",
    icon: "📉",
  },
];

export default function DeviceDashboardPage() {
  const { deviceId } = useParams();
  const { token, isTenantAdmin } = useAuth();
  
  // Only tenant admins can access device dashboard page
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }
  const navigate = useNavigate();
  const api = useMemo(() => createApiClient(token), [token]);

  const [device, setDevice] = useState(null);
  const [widgets, setWidgets] = useState([]);
  const [layout, setLayout] = useState([]);
  const [telemetryData, setTelemetryData] = useState({});
  const [historyData, setHistoryData] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [showReadings, setShowReadings] = useState(false);
  const [readingsExpanded, setReadingsExpanded] = useState(false);
  const [readings, setReadings] = useState([]);
  const [readingsLoading, setReadingsLoading] = useState(false);
  const [readingsError, setReadingsError] = useState(null);
  const [readingsFilter, setReadingsFilter] = useState({
    key: "",
    limit: 10,
    fromDate: "",
    toDate: "",
    detectAnomalies: true,
  });
  const [availableKeys, setAvailableKeys] = useState([]);

  // Load device and dashboard config
  useEffect(() => {
    if (!token) {
      console.log("Skipping dashboard load - no token yet");
      return;
    }

    const load = async () => {
      console.log("Loading dashboard for device:", deviceId);
      setLoading(true);
      setError(null);
      try {
        const [devicesResp, dashResp] = await Promise.all([
          api.get("/admin/devices"),
          api.get(`/dashboard/devices/${deviceId}/dashboard`),
        ]);
        console.log("Dashboard API responses:", { devices: devicesResp.data.length, dashboard: dashResp.data });
        const found = devicesResp.data.find((d) => d.device_id === deviceId);
        if (!found) {
          setError("Device not found");
          setLoading(false);
          return;
        }
        setDevice(found);

        const existingConfig = dashResp.data.config || { widgets: [], layout: [] };
        console.log("Dashboard config from backend:", existingConfig);
        // Start with empty dashboard - user adds widgets from library
        const initialWidgets = existingConfig.widgets || [];
        let initialLayout = existingConfig.layout || [];
        
        // Ensure layout items have proper structure
        if (initialLayout.length > 0) {
          initialLayout = initialLayout.map((item) => ({
            ...item,
            x: Number(item.x) || 0,
            y: Number(item.y) || 0,
            w: Number(item.w) || 4,
            h: Number(item.h) || 3,
          }));
        }
        
        console.log("Setting initial widgets:", initialWidgets.length, "layout:", initialLayout.length);
        setWidgets(initialWidgets);
        setLayout(initialLayout);

        // Load latest telemetry
        setTelemetryData(dashResp.data.latest?.data || {});
        console.log("Dashboard loaded successfully");
      } catch (err) {
        console.error("Dashboard load error:", err);
        setError(err.response?.data?.detail || "Failed to load dashboard");
      } finally {
        console.log("Setting loading to false");
        setLoading(false);
      }
    };

    load();
  }, [token, api, deviceId]);

  // Auto-refresh telemetry data every 10 seconds (smooth, no layout flash)
  useEffect(() => {
    if (!deviceId || !device) return;

    const refreshData = async () => {
      try {
        const resp = await api.get(`/dashboard/devices/${deviceId}/latest`);
        setTelemetryData(resp.data.data || {});
      } catch (err) {
        console.error("Failed to refresh telemetry:", err);
      }
    };

    const interval = setInterval(refreshData, 10000);
    return () => clearInterval(interval);
  }, [api, deviceId, device]);

  // Load history data for chart widgets
  const loadHistory = useCallback(
    async (field) => {
      if (!deviceId) return;
      try {
        const resp = await api.get(`/dashboard/devices/${deviceId}/history`, {
          params: { key: field, minutes: 60 },
        });
        setHistoryData((prev) => ({ ...prev, [field]: resp.data.points || [] }));
      } catch (err) {
        console.error(`Failed to load history for ${field}:`, err);
      }
    },
    [api, deviceId]
  );

  // Load history for all chart widgets
  useEffect(() => {
    if (!widgets || widgets.length === 0) return;
    const chartWidgets = widgets.filter((w) => w.type === "chart");
    chartWidgets.forEach((w) => loadHistory(w.field));
  }, [widgets, loadHistory]);

  // Load available keys for filter dropdown
  useEffect(() => {
    if (!deviceId || !device) return;
    const loadKeys = async () => {
      try {
        // Get all unique keys from recent readings
        const resp = await api.get(`/dashboard/devices/${deviceId}/readings`, {
          params: { limit: 100 },
        });
        const keys = [...new Set(resp.data.map((r) => r.key))].sort();
        setAvailableKeys(keys);
      } catch (err) {
        console.error("Failed to load available keys:", err);
      }
    };
    loadKeys();
  }, [api, deviceId, device]);

  // Load readings when component mounts (will be shown/hidden by Collapsible)
  useEffect(() => {
    if (!deviceId) return;
    
    const loadReadings = async () => {
      setReadingsLoading(true);
      setReadingsError(null);
      try {
        const params = {
          limit: readingsFilter.limit,
          detect_anomalies: readingsFilter.detectAnomalies,
        };
        if (readingsFilter.key) {
          params.key = readingsFilter.key;
        }
        if (readingsFilter.fromDate) {
          params.from_date = readingsFilter.fromDate;
        }
        if (readingsFilter.toDate) {
          params.to_date = readingsFilter.toDate;
        }
        
        const resp = await api.get(`/dashboard/devices/${deviceId}/readings`, { params });
        setReadings(resp.data);
      } catch (err) {
        setReadingsError(err.response?.data?.detail || "Failed to load readings");
      } finally {
        setReadingsLoading(false);
      }
    };
    
    loadReadings();
  }, [deviceId, readingsFilter, api]);

  const handleAddWidget = (libraryWidget) => {
    const newId = `widget-${Date.now()}`;
    const newWidget = { ...libraryWidget, id: newId };
    const newLayoutItem = {
      i: newId,
      x: (layout.length * 4) % 12,
      y: Infinity, // Add to bottom
      w: libraryWidget.type === "chart" ? 6 : 4,
      h: libraryWidget.type === "chart" ? 4 : 3,
    };
    setWidgets((prev) => [...prev, newWidget]);
    setLayout((prev) => [...prev, newLayoutItem]);
  };

  const handleRemoveWidget = (widgetId) => {
    console.log("handleRemoveWidget called with:", widgetId);
    setWidgets((prev) => {
      const filtered = prev.filter((w) => w.id !== widgetId);
      console.log("Widgets after remove:", filtered.length);
      return filtered;
    });
    setLayout((prev) => {
      const filtered = prev.filter((l) => l.i !== widgetId);
      console.log("Layout after remove:", filtered.length);
      return filtered;
    });
  };

  const handleLayoutChange = (currentLayout, allLayouts) => {
    // Save the layout for the current breakpoint (lg)
    setLayout(currentLayout);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      // Ensure layout is properly formatted before saving
      const layoutToSave = layout.map((item) => ({
        ...item,
        // Ensure x, y, w, h are numbers
        x: Number(item.x) || 0,
        y: Number(item.y) || 0,
        w: Number(item.w) || 4,
        h: Number(item.h) || 3,
      }));
      
      await api.post(`/dashboard/devices/${deviceId}/dashboard`, {
        config: { widgets, layout: layoutToSave },
      });
      setSuccessMessage("Dashboard saved");
      setEditMode(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save dashboard");
    } finally {
      setSaving(false);
    }
  };

  const renderWidget = (widget) => {
    const value = telemetryData[widget.field];
    const history = historyData[widget.field];

    switch (widget.type) {
      case "gauge":
        return (
          <GaugeWidget
            title={widget.title}
            value={value}
            unit={widget.unit}
            min={widget.min}
            max={widget.max}
          />
        );
      case "number":
        return <NumberWidget title={widget.title} value={value} unit={widget.unit} />;
      case "thermometer":
        return (
          <ThermometerWidget
            title={widget.title}
            value={value}
            unit={widget.unit}
            min={widget.min}
            max={widget.max}
          />
        );
      case "tank":
        return (
          <TankWidget
            title={widget.title}
            value={value}
            unit={widget.unit}
            min={widget.min}
            max={widget.max}
          />
        );
      case "battery":
        return (
          <BatteryWidget
            title={widget.title}
            value={value}
            min={widget.min}
            max={widget.max}
          />
        );
      case "chart":
        return (
          <LineChartWidget
            title={widget.title}
            data={history}
            dataKey={widget.field}
            unit={widget.unit}
          />
        );
      default:
        return <div>Unknown widget type</div>;
    }
  };

  console.log("Render state:", { loading, widgets: widgets?.length, device: device?.device_id });
  
  // Only tenant admins can access device dashboard page
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page page--centered">
        <p>Loading dashboard…</p>
      </div>
    );
  }

  return (
    <div className="page dashboard-page">
      <Breadcrumbs
        items={[
          { label: "Devices", path: "/devices" },
          { label: device?.name || deviceId || "Dashboard", path: `/devices/${deviceId}/dashboard` },
        ]}
      />

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-6)", marginBottom: "var(--space-6)" }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ marginBottom: "var(--space-2)", fontSize: "var(--font-size-3xl)" }}>
            {device?.name || deviceId}
          </h1>
          <p className="text-muted">
            {editMode ? "Drag widgets to arrange your dashboard" : "Live telemetry dashboard"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
          {/* Device Readings Toggle Button - Top Right */}
          <button
            className="btn btn--secondary"
            type="button"
            onClick={() => setReadingsExpanded(!readingsExpanded)}
          >
            {readingsExpanded ? "📊 Hide Readings" : "📊 Show Readings"}
          </button>
          {!editMode && (
            <button className="btn btn--secondary" type="button" onClick={() => setEditMode(true)}>
              ✏️ Edit Dashboard
            </button>
          )}
          {editMode && (
            <>
              <button className="btn btn--secondary" type="button" onClick={() => setEditMode(false)}>
                Cancel
              </button>
              <button className="btn btn--primary" type="button" disabled={saving} onClick={handleSave}>
                {saving ? "Saving..." : "💾 Save Dashboard"}
              </button>
            </>
          )}
          <button className="btn btn--ghost" type="button" onClick={() => navigate("/devices")}>
            ← Back to Devices
          </button>
        </div>
      </div>

      {/* Device Readings Section - Expanded in Middle */}
      {readingsExpanded && (
        <div className="card" style={{ marginBottom: "var(--space-6)" }}>
          <div className="card__header">
            <h3 className="card__title">Device Readings</h3>
          </div>
          <div className="card__body">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
            <p className="text-muted" style={{ margin: 0 }}>
              View historical telemetry data with filtering and anomaly detection
            </p>

            {/* Filters */}
            <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-gray-50)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-light)" }}>
              <div className="form" style={{ gap: "var(--space-4)" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
                  <div className="form-group">
                    <label className="form-label">Field Key</label>
                    <select
                      className="form-select"
                      value={readingsFilter.key}
                      onChange={(e) => setReadingsFilter({ ...readingsFilter, key: e.target.value })}
                    >
                      <option value="">All Fields</option>
                      {availableKeys.map((key) => (
                        <option key={key} value={key}>
                          {key}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Limit</label>
                    <input
                      className="form-input"
                      type="number"
                      min="1"
                      max="1000"
                      value={readingsFilter.limit}
                      onChange={(e) => setReadingsFilter({ ...readingsFilter, limit: parseInt(e.target.value) || 10 })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">From Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={readingsFilter.fromDate}
                      onChange={(e) => setReadingsFilter({ ...readingsFilter, fromDate: e.target.value })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">To Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={readingsFilter.toDate}
                      onChange={(e) => setReadingsFilter({ ...readingsFilter, toDate: e.target.value })}
                    />
                  </div>
                </div>
                <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
                  <input
                    type="checkbox"
                    id="detect-anomalies"
                    checked={readingsFilter.detectAnomalies}
                    onChange={(e) => setReadingsFilter({ ...readingsFilter, detectAnomalies: e.target.checked })}
                    style={{ width: "auto" }}
                  />
                  <label htmlFor="detect-anomalies" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
                    Detect Anomalies
                  </label>
                </div>
              </div>
            </div>

            {/* Readings Table */}
            {readingsLoading && (
              <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                <p className="text-muted">Loading readings...</p>
              </div>
            )}
            {readingsError && (
              <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-error-50)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-error-200)" }}>
                <p className="text-error" style={{ margin: 0 }}>{readingsError}</p>
              </div>
            )}
            {!readingsLoading && !readingsError && (
              <>
                {readings.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "var(--space-8)", backgroundColor: "var(--color-gray-50)", borderRadius: "var(--radius-md)" }}>
                    <p className="text-muted" style={{ margin: 0 }}>No readings found for the selected filters.</p>
                  </div>
                ) : (
                  <>
                    <div className="table-wrapper">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Timestamp</th>
                            <th>Field</th>
                            <th>Value</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {readings.map((reading, idx) => (
                            <tr
                              key={`${reading.timestamp}-${reading.key}-${idx}`}
                              className={reading.is_anomaly ? "anomaly-row" : ""}
                            >
                              <td style={{ whiteSpace: "nowrap" }}>{new Date(reading.timestamp).toLocaleString()}</td>
                              <td>
                                <code style={{ fontSize: "var(--font-size-xs)", backgroundColor: "var(--color-gray-100)", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                                  {reading.key}
                                </code>
                              </td>
                              <td style={{ fontWeight: reading.is_anomaly ? "var(--font-weight-semibold)" : "var(--font-weight-normal)", fontFamily: "var(--font-family-mono)" }}>
                                {reading.value !== null && reading.value !== undefined
                                  ? typeof reading.value === "number"
                                    ? reading.value.toFixed(2)
                                    : String(reading.value)
                                  : "—"}
                              </td>
                              <td>
                                {reading.is_anomaly ? (
                                  <span className="badge badge--warning" title={reading.anomaly_reason || "Anomaly detected"}>
                                    ⚠️ Anomaly
                                  </span>
                                ) : (
                                  <span className="badge badge--success">✓ Normal</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {readings.filter((r) => r.is_anomaly).length > 0 && (
                      <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-warning-50)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-warning-200)" }}>
                        <p style={{ margin: 0, fontSize: "var(--font-size-sm)" }}>
                          <strong>⚠️ Found {readings.filter((r) => r.is_anomaly).length} anomaly/anomalies</strong> in the displayed readings.
                        </p>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
        </div>
      )}

      {error && (
          <div className="card" style={{ borderColor: "var(--color-error-500)", marginBottom: "var(--space-6)" }}>
            <p className="text-error">{error}</p>
          </div>
        )}
        {successMessage && (
          <div className="card" style={{ borderColor: "var(--color-success-500)", marginBottom: "var(--space-6)" }}>
            <p className="text-success">{successMessage}</p>
          </div>
        )}

        <div className="card">
          <div className="dashboard-container">
            {editMode && (
              <div className="widget-library">
                <h3>Widget Library</h3>
                <p className="muted">Click to add widgets to your dashboard</p>
                <div className="widget-library__grid">
                  {WIDGET_LIBRARY.map((widget) => (
                    <div
                      key={widget.id}
                      className="widget-library__item"
                      onClick={() => handleAddWidget(widget)}
                    >
                      <span className="widget-library__icon">{widget.icon}</span>
                      <span className="widget-library__title">{widget.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="dashboard-canvas" style={{ width: "100%" }}>
            {!widgets || widgets.length === 0 ? (
              <div className="empty-dashboard">
                <p>No widgets yet.</p>
                {editMode && <p>Click on a widget from the library to add it.</p>}
              </div>
            ) : (
              <ResponsiveGridLayout
                className="dashboard-grid"
                layouts={{ lg: layout, md: layout, sm: layout, xs: layout, xxs: layout }}
                breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                cols={{ lg: 12, md: 12, sm: 12, xs: 12, xxs: 12 }}
                rowHeight={60}
                onLayoutChange={handleLayoutChange}
                isDraggable={editMode}
                isResizable={editMode}
                compactType={null}
                preventCollision={true}
                margin={[16, 16]}
                useCSSTransforms={true}
                measureBeforeMount={false}
              >
                  {widgets.map((widget) => (
                    <div key={widget.id} className="dashboard-grid__item">
                      {editMode && (
                        <button
                          className="widget-remove-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemoveWidget(widget.id);
                          }}
                        >
                          ×
                        </button>
                      )}
                      {renderWidget(widget)}
                    </div>
                  ))}
              </ResponsiveGridLayout>
            )}
            </div>
          </div>
        </div>
    </div>
  );
}
