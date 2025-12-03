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
  const { token, isBootstrapping, bootstrapError } = useAuth();
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

  // Load device and dashboard config
  useEffect(() => {
    if (!token || isBootstrapping || bootstrapError) {
      console.log("Skipping dashboard load - no token yet", { token, isBootstrapping, bootstrapError });
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
        const initialLayout = existingConfig.layout || [];
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
  }, [token, isBootstrapping, bootstrapError, api, deviceId]);

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

  const handleLayoutChange = (newLayout) => {
    setLayout(newLayout);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await api.post(`/dashboard/devices/${deviceId}/dashboard`, {
        config: { widgets, layout },
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

  console.log("Render state:", { isBootstrapping, bootstrapError, loading, widgets: widgets?.length, device: device?.device_id });

  if (isBootstrapping) {
    return (
      <div className="page page--centered">
        <p>Loading…</p>
      </div>
    );
  }

  if (bootstrapError) {
    return (
      <div className="page page--centered">
        <p className="error-message">{bootstrapError}</p>
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
      <section className="page__primary">
        <div className="section-header">
          <div>
            <h2>Dashboard: {device?.name || deviceId}</h2>
            <p className="muted">
              {editMode ? "Drag widgets to arrange your dashboard" : "Live telemetry dashboard"}
            </p>
          </div>
          <div className="section-header__actions">
            {!editMode && (
              <button type="button" onClick={() => setEditMode(true)}>
                Edit Dashboard
              </button>
            )}
            {editMode && (
              <>
                <button type="button" className="secondary" onClick={() => setEditMode(false)}>
                  Cancel
                </button>
                <button type="button" className="primary" disabled={saving} onClick={handleSave}>
                  {saving ? "Saving..." : "Save Dashboard"}
                </button>
              </>
            )}
            <button type="button" className="secondary" onClick={() => navigate("/devices")}>
              Back to Devices
            </button>
          </div>
        </div>

        {error && <p className="error-message">{error}</p>}
        {successMessage && <p className="success-message">{successMessage}</p>}

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

          <div className="dashboard-canvas">
            {!widgets || widgets.length === 0 ? (
              <div className="empty-dashboard">
                <p>No widgets yet.</p>
                {editMode && <p>Click on a widget from the library to add it.</p>}
              </div>
            ) : (
              <ResponsiveGridLayout
                className="dashboard-grid"
                layouts={{ lg: layout }}
                breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                rowHeight={60}
                onLayoutChange={handleLayoutChange}
                isDraggable={editMode}
                isResizable={editMode}
                compactType="vertical"
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
      </section>
    </div>
  );
}
