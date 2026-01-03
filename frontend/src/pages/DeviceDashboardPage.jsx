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
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import DeviceMapView from "../components/DeviceMapView.jsx";
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
    icon: "droplet",
  },
  {
    id: "thermometer-temperature",
    type: "thermometer",
    title: "Temperature",
    field: "temperature",
    unit: "°C",
    min: -20,
    max: 50,
    icon: "activity",
  },
  {
    id: "battery-widget",
    type: "battery",
    title: "Battery Level",
    field: "battery",
    min: 0,
    max: 100,
    icon: "zap",
  },
  {
    id: "gauge-level",
    type: "gauge",
    title: "Level Gauge",
    field: "level",
    unit: "%",
    min: 0,
    max: 100,
    icon: "trending",
  },
  {
    id: "gauge-pressure",
    type: "gauge",
    title: "Pressure Gauge",
    field: "pressure",
    unit: "bar",
    min: 0,
    max: 3,
    icon: "alert",
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
    icon: "trending",
  },
  {
    id: "chart-temperature",
    type: "chart",
    title: "Temperature History",
    field: "temperature",
    unit: "°C",
    icon: "📉",
  },
  // Smart Bench – common widgets
  {
    id: "bench-env-temperature",
    type: "thermometer",
    title: "Outdoor Temperature",
    field: "environment.temperature",
    unit: "°C",
    min: -20,
    max: 60,
    icon: "activity",
  },
  {
    id: "bench-env-co2",
    type: "number",
    title: "Carbon Dioxide Level (Air Quality)",
    field: "environment.co2",
    unit: "",
    icon: "analytics",
  },
  {
    id: "bench-env-pm25",
    type: "number",
    title: "Fine Dust Level (Air Quality)",
    field: "environment.pm25",
    unit: "",
    icon: "activity",
  },
  {
    id: "bench-battery-soc",
    type: "battery",
    title: "Battery Charge Level",
    field: "battery.soc",
    min: 0,
    max: 100,
    icon: "zap",
  },
  {
    id: "bench-occupancy-total",
    type: "number",
    title: "Number of Seats Used",
    field: "occupancy.total",
    unit: "",
    icon: "users",
  },
  {
    id: "bench-charging-power",
    type: "number",
    title: "Charging Power (USB/Wireless)",
    field: "charging.powerW",
    unit: "W",
    icon: "zap",
  },
  {
    id: "bench-chart-temperature",
    type: "chart",
    title: "Outdoor Temperature History",
    field: "environment.temperature",
    unit: "°C",
    icon: "trending",
  },
  {
    id: "bench-chart-battery-soc",
    type: "chart",
    title: "Battery Charge History",
    field: "battery.soc",
    unit: "%",
    icon: "activity",
  },
];

// Helper to support nested field paths like "battery.soc"
function getValueByField(data, field) {
  if (!data || !field) return undefined;
  if (!field.includes(".")) {
    return data[field];
  }
  return field.split(".").reduce((acc, part) => {
    if (acc && typeof acc === "object" && part in acc) {
      return acc[part];
    }
    return undefined;
  }, data);
}

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
  const [showMap, setShowMap] = useState(false);
  const [externalData, setExternalData] = useState(null);
  const [externalDataLoading, setExternalDataLoading] = useState(false);
  const [externalDataError, setExternalDataError] = useState(null);
  const [readingsFilter, setReadingsFilter] = useState({
    key: "",
    limit: 10,
    fromDate: "",
    toDate: "",
    detectAnomalies: true,
  });
  const [availableKeys, setAvailableKeys] = useState([]);
  const [discoveredFields, setDiscoveredFields] = useState([]);

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
        console.log("Dashboard API responses:", { devices: devicesResp.data, dashboard: dashResp.data });
        
        // Handle paginated response format
        const devices = Array.isArray(devicesResp.data) 
          ? devicesResp.data 
          : (devicesResp.data?.devices || []);
        
        const found = devices.find((d) => d.device_id === deviceId);
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

  // Transform external data records into readings format
  const transformExternalDataToReadings = useCallback((externalData) => {
    if (!externalData || !externalData.records || !Array.isArray(externalData.records)) {
      return [];
    }

    const readings = [];
    externalData.records.forEach((record) => {
      // Convert each field in the record to a reading
      Object.keys(record).forEach((key) => {
        if (key !== 'timestamp' && record[key] !== null && record[key] !== undefined) {
          // Parse timestamp - format: "2026-01-03 13:38:42"
          let timestamp;
          try {
            timestamp = new Date(record.timestamp.replace(' ', 'T')).toISOString();
          } catch {
            timestamp = new Date().toISOString();
          }

          readings.push({
            timestamp: timestamp,
            key: key,
            value: record[key],
            is_anomaly: false,
            source: 'external'
          });
        }
      });
    });

    // Sort by timestamp descending (newest first)
    return readings.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, []);

  // Load external device data
  useEffect(() => {
    if (!deviceId || !token) return;

    const loadExternalData = async () => {
      setExternalDataLoading(true);
      setExternalDataError(null);
      try {
        const resp = await api.get(`/admin/devices/${deviceId}/external-data`);
        const data = resp.data.data;
        setExternalData(data);
        
        // Transform external data records to readings format
        const externalReadings = transformExternalDataToReadings(data);
        
        // Update telemetry data with latest external data values
        if (data && data.records && data.records.length > 0) {
          const latestRecord = data.records[0]; // Most recent record
          setTelemetryData((prevTelemetry) => {
            const updatedTelemetry = { ...prevTelemetry };
            Object.keys(latestRecord).forEach((key) => {
              if (key !== 'timestamp') {
                updatedTelemetry[key] = latestRecord[key];
              }
            });
            return updatedTelemetry;
          });
        }
        
        // Update available keys to include external data fields
        if (externalReadings.length > 0) {
          const externalKeys = [...new Set(externalReadings.map(r => r.key))];
          setAvailableKeys((prev) => {
            const combined = [...new Set([...prev, ...externalKeys])];
            return combined.sort();
          });
          
          // Also add external data fields to discoveredFields for widget library
          if (data && data.records && data.records.length > 0) {
            const latestRecord = data.records[0];
            const externalFields = [];
            
            Object.keys(latestRecord).forEach((key) => {
              if (key !== 'timestamp' && latestRecord[key] !== null && latestRecord[key] !== undefined) {
                const value = latestRecord[key];
                const isNumeric = typeof value === 'number';
                
                // Get all values for this field from all records to calculate min/max
                const allValues = data.records
                  .map(r => r[key])
                  .filter(v => v !== null && v !== undefined && typeof v === 'number');
                
                const fieldMetadata = {
                  key: key,
                  display_name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                  field_type: isNumeric ? 'number' : 'string',
                  unit: '',
                  min_value: allValues.length > 0 ? Math.min(...allValues) : null,
                  max_value: allValues.length > 0 ? Math.max(...allValues) : null,
                  sample_value: value,
                };
                
                externalFields.push(fieldMetadata);
              }
            });
            
            // Merge external fields with discovered fields
            setDiscoveredFields((prev) => {
              const existingKeys = new Set(prev.map(f => f.key));
              const newFields = externalFields.filter(f => !existingKeys.has(f.key));
              return [...prev, ...newFields];
            });
          }
        }
      } catch (err) {
        // Only show error if it's not a 503 (service unavailable) - that's expected if API not configured
        if (err.response?.status !== 503) {
          setExternalDataError(err.response?.data?.detail || "Failed to load external data");
        }
        setExternalData(null);
      } finally {
        setExternalDataLoading(false);
      }
    };

    loadExternalData();
  }, [deviceId, token, api, transformExternalDataToReadings]);

  // Load history data for chart widgets
  const loadHistory = useCallback(
    async (field) => {
      if (!deviceId) return;
      
      // First, try to get history from external data
      if (externalData && externalData.records && Array.isArray(externalData.records)) {
        const externalHistory = externalData.records
          .filter(record => record[field] !== null && record[field] !== undefined)
          .map(record => {
            let timestamp;
            try {
              timestamp = new Date(record.timestamp.replace(' ', 'T')).getTime();
            } catch {
              timestamp = new Date().getTime();
            }
            return {
              timestamp: timestamp,
              value: record[field]
            };
          })
          .sort((a, b) => a.timestamp - b.timestamp);
        
        if (externalHistory.length > 0) {
          setHistoryData((prev) => ({ ...prev, [field]: externalHistory }));
          return; // Use external data history
        }
      }
      
      // Fallback to InfluxDB if external data doesn't have this field
      try {
        const resp = await api.get(`/dashboard/devices/${deviceId}/history`, {
          params: { key: field, minutes: 60 },
        });
        setHistoryData((prev) => ({ ...prev, [field]: resp.data.points || [] }));
      } catch (err) {
        console.error(`Failed to load history for ${field}:`, err);
      }
    },
    [api, deviceId, externalData]
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

  // Load discovered fields from telemetry for dynamic widgets
  useEffect(() => {
    if (!deviceId || !device) return;
    const loadFields = async () => {
      try {
        const resp = await api.get(`/dashboard/devices/${deviceId}/fields`);
        const backendFields = resp.data || [];
        
        // Merge with existing discoveredFields to preserve external data fields
        setDiscoveredFields((prev) => {
          const existingKeys = new Set(backendFields.map(f => f.key));
          const externalFields = prev.filter(f => !existingKeys.has(f.key));
          return [...backendFields, ...externalFields];
        });
      } catch (err) {
        console.error("Failed to load discovered fields:", err);
      }
    };
    loadFields();
  }, [api, deviceId, device]);

  // Load readings when component mounts (will be shown/hidden by Collapsible)
  useEffect(() => {
    if (!deviceId) return;
    
    const loadReadings = async () => {
      setReadingsLoading(true);
      setReadingsError(null);
      try {
        // Get external data readings
        const externalReadings = externalData ? transformExternalDataToReadings(externalData) : [];
        
        // Try to get InfluxDB readings (optional - may fail if InfluxDB unavailable)
        let influxReadings = [];
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
          influxReadings = resp.data || [];
        } catch (err) {
          // InfluxDB unavailable - that's okay, we'll use external data only
          console.log("InfluxDB readings unavailable, using external data only");
        }
        
        // Merge external and InfluxDB readings
        const allReadings = [...externalReadings, ...influxReadings];
        
        // Apply filters
        let filteredReadings = allReadings;
        if (readingsFilter.key) {
          filteredReadings = filteredReadings.filter(r => r.key === readingsFilter.key);
        }
        if (readingsFilter.fromDate) {
          const fromDate = new Date(readingsFilter.fromDate);
          filteredReadings = filteredReadings.filter(r => new Date(r.timestamp) >= fromDate);
        }
        if (readingsFilter.toDate) {
          const toDate = new Date(readingsFilter.toDate);
          toDate.setHours(23, 59, 59, 999); // End of day
          filteredReadings = filteredReadings.filter(r => new Date(r.timestamp) <= toDate);
        }
        
        // Sort by timestamp descending and limit
        filteredReadings.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        filteredReadings = filteredReadings.slice(0, readingsFilter.limit);
        
        setReadings(filteredReadings);
      } catch (err) {
        setReadingsError(err.response?.data?.detail || "Failed to load readings");
      } finally {
        setReadingsLoading(false);
      }
    };
    
    loadReadings();
  }, [deviceId, readingsFilter, api, externalData, transformExternalDataToReadings]);

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
    // Ensure all layout items have valid positions and don't overlap
    const sanitizedLayout = currentLayout.map((item) => ({
      ...item,
      x: Math.max(0, Number(item.x) || 0),
      y: Math.max(0, Number(item.y) || 0),
      w: Math.max(1, Math.min(12, Number(item.w) || 4)),
      h: Math.max(1, Number(item.h) || 3),
    }));
    
    // Remove any layout items that don't have corresponding widgets
    const widgetIds = new Set(widgets.map(w => w.id));
    const filteredLayout = sanitizedLayout.filter(item => widgetIds.has(item.i));
    
    setLayout(filteredLayout);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);
    try {
      // Ensure layout is properly formatted and synchronized with widgets
      const widgetIds = new Set(widgets.map(w => w.id));
      
      // Remove any layout items without corresponding widgets
      let layoutToSave = layout.filter(item => widgetIds.has(item.i));
      
      // Ensure all widgets have layout items
      widgets.forEach(widget => {
        const existingLayout = layoutToSave.find(item => item.i === widget.id);
        if (!existingLayout) {
          // Add missing layout item
          const maxY = layoutToSave.length > 0 
            ? Math.max(...layoutToSave.map(item => item.y + item.h))
            : 0;
          layoutToSave.push({
            i: widget.id,
            x: (layoutToSave.length * 4) % 12,
            y: maxY,
            w: widget.type === "chart" ? 6 : 4,
            h: widget.type === "chart" ? 4 : 3,
          });
        }
      });
      
      // Sanitize and ensure no overlaps
      layoutToSave = layoutToSave.map((item, index) => {
        // Ensure valid bounds
        const sanitized = {
          ...item,
          x: Math.max(0, Math.min(11, Number(item.x) || 0)),
          y: Math.max(0, Number(item.y) || 0),
          w: Math.max(1, Math.min(12, Number(item.w) || 4)),
          h: Math.max(1, Number(item.h) || 3),
        };
        
        // Ensure widget doesn't overflow grid
        if (sanitized.x + sanitized.w > 12) {
          sanitized.x = Math.max(0, 12 - sanitized.w);
        }
        
        return sanitized;
      });
      
      // Compact layout to remove gaps
      layoutToSave.sort((a, b) => {
        if (a.y !== b.y) return a.y - b.y;
        return a.x - b.x;
      });
      
      await api.post(`/dashboard/devices/${deviceId}/dashboard`, {
        config: { widgets, layout: layoutToSave },
      });
      
      // Update local layout state to match saved layout
      setLayout(layoutToSave);
      setSuccessMessage("Dashboard saved successfully");
      setEditMode(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save dashboard");
    } finally {
      setSaving(false);
    }
  };

  // Generate dynamic widgets from discovered fields
  const dynamicWidgets = useMemo(() => {
    if (!discoveredFields || discoveredFields.length === 0) return [];
    
    const widgets = [];
    
    discoveredFields.forEach((field) => {
      // Only create widgets for numeric fields
      if (field.field_type !== 'number') return;
      
      const baseId = `dynamic-${field.key.replace(/\./g, '-')}`;
      
      // Determine sensible min/max for widgets based on semantics or discovered values
      let min = field.min_value ?? 0;
      let max = field.max_value ?? 100;
      
      const keyLower = (field.key || "").toLowerCase();
      const nameLower = (field.display_name || "").toLowerCase();

      if (field.unit === "%") {
        min = 0;
        max = 100;
      } else if (field.unit === "°C") {
        min = field.min_value ?? -20;
        max = field.max_value ?? 50;
      } else if (field.min_value !== null && field.max_value !== null) {
        // Add 10% padding to discovered range
        const range = field.max_value - field.min_value;
        min = Math.floor(field.min_value - range * 0.1);
        max = Math.ceil(field.max_value + range * 0.1);
      }

      // Choose a single "most relevant" widget type per field
      let type = "number";
      let icon = "analytics";

      if (
        field.unit === "%" ||
        keyLower.includes("level") ||
        keyLower.includes("soc") ||
        nameLower.includes("level")
      ) {
        type = "gauge";
        icon = "trending";
      } else if (
        field.unit === "°C" ||
        keyLower.includes("temp") ||
        nameLower.includes("temp")
      ) {
        type = "thermometer";
        icon = "activity";
      }

      // Add primary widget (gauge/thermometer/number)
      widgets.push({
        id: `${baseId}-primary`,
        type,
        title: field.display_name,
        field: field.key,
        unit: field.unit || "",
        min,
        max,
        icon,
        isDynamic: true,
      });

      // Also add a chart widget for history visualization
      widgets.push({
        id: `${baseId}-chart`,
        type: "chart",
        title: `${field.display_name} History`,
        field: field.key,
        unit: field.unit || "",
        icon: "trending",
        isDynamic: true,
      });
    });
    
    return widgets;
  }, [discoveredFields]);

  // Only show widgets that match the device's actual telemetry fields
  const allWidgetLibrary = useMemo(() => {
    // If we have discovered fields, only show dynamic widgets generated from device's actual fields
    if (discoveredFields && discoveredFields.length > 0) {
      return dynamicWidgets;
    }
    // Fallback: if no telemetry yet, show empty (user will see widgets once device sends data)
    return [];
  }, [dynamicWidgets, discoveredFields]);

  const renderWidget = (widget) => {
    const value = getValueByField(telemetryData, widget.field);
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
        <div className="card" style={{ padding: "var(--space-8)", textAlign: "center" }}>
          <div style={{ marginBottom: "var(--space-4)", opacity: 0.4 }}>
            <Icon name="activity" size={40} />
          </div>
          <p style={{ color: "var(--color-text-secondary)" }}>Loading device dashboard…</p>
        </div>
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

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton label="Back to Devices" to="/devices" />
          </div>
          <h1 className="page-header__title">{device?.name || deviceId}</h1>
          <p className="page-header__subtitle">
            Per-device telemetry dashboard with live widgets and recent readings
          </p>
        </div>
        <div className="page-header__actions" style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
          <button
            className="btn btn--secondary"
            type="button"
            onClick={() => setShowMap(!showMap)}
          >
            <Icon name="map" size={16} />
            <span>{showMap ? "Hide map" : "Show map"}</span>
          </button>
          <button
            className="btn btn--secondary"
            type="button"
            onClick={() => setReadingsExpanded(!readingsExpanded)}
          >
            <Icon name="inbox" size={16} />
            <span>{readingsExpanded ? "Hide readings" : "Show readings"}</span>
          </button>
          {!editMode && (
            <button className="btn btn--secondary" type="button" onClick={() => setEditMode(true)}>
              <Icon name="settings" size={16} />
              <span>Edit dashboard</span>
            </button>
          )}
          {editMode && (
            <>
              <button className="btn btn--ghost" type="button" onClick={() => setEditMode(false)}>
                Cancel
              </button>
              <button className="btn btn--primary" type="button" disabled={saving} onClick={handleSave}>
                <Icon name="download" size={16} />
                <span>{saving ? "Saving..." : "Save dashboard"}</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Device Map Section */}
      {showMap && (
        <div className="card" style={{ marginBottom: "var(--space-6)" }}>
          <div className="card__header">
            <h3 className="card__title">Device Location</h3>
          </div>
          <div className="card__body" style={{ padding: 0 }}>
            <DeviceMapView 
              deviceIds={[deviceId]} 
              highlightDeviceId={deviceId}
              height="400px"
              showPopup={true}
            />
          </div>
        </div>
      )}

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
            <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-bg-secondary)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-border-light)" }}>
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
              <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-error-bg)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-error-bright)" }}>
                <p className="text-error" style={{ margin: 0 }}>{readingsError}</p>
              </div>
            )}
            {!readingsLoading && !readingsError && (
              <>
                {readings.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "var(--space-8)", backgroundColor: "var(--color-bg-secondary)", borderRadius: "var(--radius-md)" }}>
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
                                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                  <code style={{ fontSize: "var(--font-size-xs)", backgroundColor: "var(--color-bg-secondary)", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                                    {reading.key}
                                  </code>
                                  {reading.source === 'external' && (
                                    <span className="badge badge--info" style={{ fontSize: "var(--font-size-xs)" }} title="From SmartTive API">
                                      External
                                    </span>
                                  )}
                                </div>
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
                                    <Icon name="warning" size={12} />
                                    <span style={{ marginLeft: "var(--space-1)" }}>Anomaly</span>
                                  </span>
                                ) : (
                                  <span className="badge badge--success">
                                    <Icon name="check" size={12} />
                                    <span style={{ marginLeft: "var(--space-1)" }}>Normal</span>
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {readings.filter((r) => r.is_anomaly).length > 0 && (
                      <div style={{ padding: "var(--space-4)", backgroundColor: "var(--color-warning-bg)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-warning-bright)" }}>
                        <p style={{ margin: 0, fontSize: "var(--font-size-sm)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                          <Icon name="warning" size={14} />
                          <span>
                            <strong>Found {readings.filter((r) => r.is_anomaly).length} anomaly/anomalies</strong> in the displayed readings.
                          </span>
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
          <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
            {error}
          </div>
        )}
        {successMessage && (
          <div className="badge badge--success" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
            {successMessage}
          </div>
        )}

        <div className="card">
          <div className="dashboard-container">
            {editMode && (
              <div className="widget-library">
                <div className="widget-library__header">
                  <h3 className="card__title">Widget library</h3>
                  <p className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                    Click to add modern cards to this device dashboard. Widgets are generated from your device telemetry fields.
                  </p>
                </div>
                {allWidgetLibrary.length === 0 ? (
                  <div className="widget-library__empty">
                    <p className="text-muted">No widgets available yet.</p>
                    <p className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>
                      Widgets will appear automatically once the device sends data. Make sure the device is active and sending telemetry.
                    </p>
                  </div>
                ) : (
                  <div className="widget-library__grid">
                    {allWidgetLibrary.map((widget) => (
                      <div
                        key={widget.id}
                        className="widget-library__item"
                        onClick={() => handleAddWidget(widget)}
                      >
                        <span className="widget-library__icon">
                          <Icon name={widget.icon || "activity"} size={16} />
                        </span>
                        <span className="widget-library__title">{widget.title}</span>
                        {widget.isDynamic && <span className="widget-library__pill">Live</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="dashboard-canvas" style={{ width: "100%" }}>
            {!widgets || widgets.length === 0 ? (
              <div className="empty-dashboard">
                <p>No widgets yet.</p>
                {editMode && (
                  <>
                    {allWidgetLibrary.length === 0 ? (
                      <p>Waiting for device telemetry... Widgets will appear automatically once the device sends data.</p>
                    ) : (
                      <p>Click on a widget from the library to add it.</p>
                    )}
                  </>
                )}
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
                draggableCancel=".widget-remove-btn"
                compactType={editMode ? null : "vertical"}
                preventCollision={true}
                margin={[16, 16]}
                useCSSTransforms={true}
                measureBeforeMount={false}
                allowOverlap={false}
              >
                  {widgets.map((widget) => (
                    <div key={widget.id} className="dashboard-grid__item">
                      {editMode && (
                        <button
                          className="widget-remove-btn"
                          type="button"
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
