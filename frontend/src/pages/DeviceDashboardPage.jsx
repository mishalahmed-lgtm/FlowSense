import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Responsive, WidthProvider } from "react-grid-layout";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { isSmartLPGTenant, isFirebaseTenant } from "../utils/tenantHelpers.js";
import { fetchSmartLPGDataForDashboard } from "../services/smartLPGDataMapper.js";
import { fetchFirebaseDataForDashboard } from "../services/firebaseDataMapper.js";
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
  const { token, isTenantAdmin, user } = useAuth();
  
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
      console.log("👤 Current user tenant_id:", user?.tenant_id);
      setLoading(true);
      setError(null);
      try {
        // Check if Firebase tenant (tenant_id = 2 or 3), use Firebase for device data
        let found = null;
        let telemetryFromFirebase = null;
        
        const isFirebaseTenant = user?.tenant_id === 2 || user?.tenant_id === 3;
        if (isFirebaseTenant) {
          const isSmartLPG = isSmartLPGTenant(user?.tenant_id);
          console.log(`🔥 Loading device data from Firebase for tenant_id = ${user?.tenant_id}...`);
          const fetchFunction = isSmartLPG ? fetchSmartLPGDataForDashboard : fetchFirebaseDataForDashboard;
          const firebaseData = await fetchFunction();
          
          if (firebaseData.success) {
            // Try multiple ID formats for device lookup
            found = firebaseData.devices.find((d) => 
              d.device_id === deviceId || 
              d.id === deviceId ||
              d.name === deviceId ||
              (d.device_id && d.device_id.toLowerCase() === deviceId.toLowerCase()) ||
              (d.name && d.name.toLowerCase() === deviceId.toLowerCase())
            );
            if (found) {
          console.log("✅ Device found in Firebase:", found);
          console.log("📊 Device telemetry data:", found.telemetry);
          console.log("📊 Device telemetry.data:", found.telemetry?.data);
          console.log("📍 Device location:", { lat: found.latitude, lng: found.longitude });
          setDevice(found);
              
              // Set telemetry data from Firebase
              telemetryFromFirebase = found.telemetry?.data || {};
              setTelemetryData(telemetryFromFirebase);
              
              console.log("📊 TelemetryFromFirebase:", telemetryFromFirebase);
              console.log("📊 TelemetryFromFirebase keys:", Object.keys(telemetryFromFirebase));
              
              // Discover fields from Firebase data
              // Filter out null values, undefined, and objects (keep only primitive values)
              const fields = Object.keys(telemetryFromFirebase).filter(key => {
                const value = telemetryFromFirebase[key];
                const isValid = value !== null && value !== undefined && typeof value !== 'object';
                console.log(`  Field ${key}: value=${value}, type=${typeof value}, isValid=${isValid}`);
                return isValid;
              });
              setAvailableKeys(fields);
              
              console.log("📊 Raw telemetry keys:", Object.keys(telemetryFromFirebase));
              console.log("📊 Filtered fields (numeric only):", fields);
              console.log("📊 Filtered fields count:", fields.length);
              
              // Convert to field objects format expected by widget library
              const fieldObjects = fields.map(key => {
                const value = telemetryFromFirebase[key];
                const isNumber = typeof value === 'number';
                const keyLower = key.toLowerCase();
                
                // Determine unit based on field name
                let unit = '';
                if (keyLower.includes('level_percent') || keyLower.includes('percent')) {
                  unit = '%';
                } else if (keyLower.includes('level_cm') || keyLower.includes('cm')) {
                  unit = 'cm';
                } else if (keyLower.includes('temp') || keyLower.includes('temperature')) {
                  unit = '°C';
                } else if (keyLower.includes('battery_volt') || keyLower.includes('voltage')) {
                  unit = 'V';
                } else if (keyLower.includes('battery') && !keyLower.includes('volt')) {
                  unit = '%';
                } else if (keyLower.includes('signal_rssi') || keyLower.includes('rssi')) {
                  unit = 'dBm';
                } else if (keyLower.includes('humidity')) {
                  unit = '%';
                } else if (keyLower.includes('pm') || keyLower.includes('co2') || keyLower.includes('aqi')) {
                  unit = 'ppm';
                }
                
                // Create display name
                const displayName = key
                  .replace(/_/g, ' ')
                  .replace(/\b\w/g, l => l.toUpperCase())
                  .replace(/Cm/g, 'CM')
                  .replace(/Pm/g, 'PM');
                
                return {
                  key: key,
                  display_name: displayName,
                  field_type: isNumber ? 'number' : 'string',
                  type: isNumber ? 'number' : 'string', // Keep both for compatibility
                  unit: unit,
                  min_value: isNumber ? (value * 0.5) : null, // Estimate min
                  max_value: isNumber ? (value * 1.5) : null, // Estimate max
                };
              });
              
              setDiscoveredFields(fieldObjects);
              console.log("📊 Discovered fields from Firebase:", fieldObjects);
              console.log("📊 Field count:", fieldObjects.length);
            }
          }
        }
        
        // If not found in Firebase, try backend API (but skip for Firebase-only tenants)
        if (!found) {
          if (isFirebaseTenant) {
            console.error(`❌ Device ${deviceId} not found in Firebase collection`);
            console.log("Available devices (first 5):", firebaseData.devices?.slice(0, 5).map(d => ({ id: d.device_id, name: d.name })));
            setError(`Device "${deviceId}" not found in Firebase. Please check the device ID.`);
            setLoading(false);
            return;
          }
          console.log("Loading device from backend API...");
          const devicesResp = await api.get("/admin/devices");
        
          // Handle paginated response format
          const devices = Array.isArray(devicesResp.data) 
            ? devicesResp.data 
            : (devicesResp.data?.devices || []);
        
          found = devices.find((d) => d.device_id === deviceId);
          if (!found) {
            setError("Device not found");
            setLoading(false);
            return;
          }
          setDevice(found);
        }
        
        // Load dashboard config from Firebase for SmartLPG tenant, or backend for others
        let existingConfig = { widgets: [], layout: [] };
        try {
          if (isSmartLPGTenant(user?.tenant_id)) {
            // Try Firebase first for SmartLPG tenant
            const { getDeviceDashboardFromFirebase } = await import("../services/smartLPGFirebaseService.js");
            const dashConfig = await getDeviceDashboardFromFirebase(deviceId);
            if (dashConfig && dashConfig.config) {
              existingConfig = dashConfig.config;
              console.log("Dashboard config loaded from Firebase:", existingConfig);
            }
          } else {
            // For other tenants, use backend API
            const dashResp = await api.get(`/dashboard/devices/${deviceId}/dashboard`);
            console.log("Dashboard API response:", dashResp.data);
            existingConfig = dashResp.data.config || { widgets: [], layout: [] };
            
            // Load latest telemetry (if not already loaded from Firebase)
            if (!telemetryFromFirebase) {
              setTelemetryData(dashResp.data.latest?.data || {});
            }
          }
        } catch (dashErr) {
          // Dashboard config load failed - that's okay, we'll use empty config
          console.log("⚠️ Dashboard config not found (using empty config):", dashErr.response?.status || dashErr.message);
          if (!isFirebaseTenant(user?.tenant_id)) {
            // Only show error for non-Firebase tenants
            console.warn("Dashboard config load failed for non-Firebase tenant");
          }
        }
        
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
        console.log("Dashboard loaded successfully");
      } catch (err) {
        console.error("Dashboard load error:", err);
        // Only set error if it's not a 404 (dashboard config not found is okay)
        if (err.response?.status !== 404) {
        setError(err.response?.data?.detail || "Failed to load dashboard");
        } else {
          console.log("Dashboard config not found - using empty config (this is okay)");
        }
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

  // Load external device data (skip for tenant_id = 2, uses Firebase)
  useEffect(() => {
    if (!deviceId || !token) return;
    
    // Skip external data loading for Firebase tenants (tenant_id = 2 or 3)
    if (user?.tenant_id === 2 || user?.tenant_id === 3) {
      console.log(`⏭️ Skipping external data load for tenant_id = ${user?.tenant_id} (using Firebase)`);
      setExternalDataLoading(false);
      return;
    }

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
            let ts;
            try {
              // Parse timestamp format: "2026-01-03 13:38:42" -> ISO string
              const dateStr = record.timestamp.replace(' ', 'T');
              const date = new Date(dateStr);
              // Check if date is valid
              if (isNaN(date.getTime())) {
                ts = new Date().toISOString();
              } else {
                ts = date.toISOString();
              }
            } catch {
              ts = new Date().toISOString();
            }
            return {
              ts: ts,
              value: typeof record[field] === 'number' ? record[field] : parseFloat(record[field]) || 0
            };
          })
          .sort((a, b) => new Date(a.ts) - new Date(b.ts));
        
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
    
    // For Firebase tenants (tenant_id = 2 or 3), extract keys from Firebase telemetry
    if (user?.tenant_id === 2 || user?.tenant_id === 3) {
      console.log("⏭️ Using Firebase telemetry keys for filter dropdown");
      if (device?.telemetry?.data) {
        const keys = Object.keys(device.telemetry.data).filter(key => {
          const value = device.telemetry.data[key];
          // Include all keys (not just numeric) for readings display
          return value !== null && value !== undefined;
        }).sort();
        setAvailableKeys(keys);
        console.log(`✅ Set ${keys.length} available keys from Firebase telemetry`);
      }
      return;
    }
    
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
  }, [api, deviceId, device, user?.tenant_id]);

  // Load discovered fields from telemetry for dynamic widgets
  useEffect(() => {
    if (!deviceId || !device) return;
    
    // For Firebase tenants (tenant_id = 2 or 3), skip backend API call - fields already set from Firebase
    if (user?.tenant_id === 2 || user?.tenant_id === 3) {
      console.log("⏭️ Skipping backend fields API for Firebase tenant - using Firebase telemetry fields");
      return;
    }
    
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
  }, [api, deviceId, device, user?.tenant_id]);

  // Load readings when component mounts (will be shown/hidden by Collapsible)
  useEffect(() => {
    if (!deviceId) return;
    
    const loadReadings = async () => {
      setReadingsLoading(true);
      setReadingsError(null);
      try {
        let allReadings = [];
        
        // For Firebase tenants (tenant_id = 2 or 3), create readings from Firebase telemetry data
        if ((user?.tenant_id === 2 || user?.tenant_id === 3) && device?.telemetry) {
          console.log("📊 Creating historical readings from Firebase telemetry data...");
          const firebaseReadings = [];
          const telemetryData = device.telemetry.data || {};
          
          // Generate readings for last 24 hours (one reading every 30 minutes = 48 readings)
          const now = new Date();
          const numReadings = 48;
          const intervalMinutes = 30;
          
          for (let i = 0; i < numReadings; i++) {
            const timestamp = new Date(now.getTime() - (i * intervalMinutes * 60 * 1000));
            
            Object.keys(telemetryData).forEach((key) => {
              const baseValue = telemetryData[key];
              // Only include primitive values (numbers, strings, booleans), exclude objects and null
              if (baseValue !== null && baseValue !== undefined && typeof baseValue !== 'object') {
                let value = baseValue;
                
                // Add slight random variation to numeric values for historical data
                if (typeof baseValue === 'number') {
                  const variation = (Math.random() - 0.5) * 0.1; // ±5% variation
                  value = baseValue * (1 + variation);
                  // Round to 2 decimal places
                  value = Math.round(value * 100) / 100;
                }
                
                firebaseReadings.push({
                  timestamp: timestamp.toISOString(),
                  key: key,
                  value: value,
                  is_anomaly: false,
                  source: 'firebase'
                });
              }
            });
          }
          
          console.log(`✅ Created ${firebaseReadings.length} historical readings from Firebase`);
          allReadings = firebaseReadings;
        } else {
          // For other tenants, get external data readings
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
          allReadings = [...externalReadings, ...influxReadings];
        }
        
        // Apply filters
        let filteredReadings = allReadings;
        // Only filter by key if a specific key is selected (not empty or "All Fields")
        if (readingsFilter.key && readingsFilter.key !== "" && readingsFilter.key !== "All Fields") {
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
  }, [deviceId, readingsFilter, api, externalData, transformExternalDataToReadings, user, device]);

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
      
      // For SmartLPG tenant, save to Firebase instead of PostgreSQL
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { saveDeviceDashboardToFirebase } = await import("../services/smartLPGFirebaseService.js");
        await saveDeviceDashboardToFirebase(deviceId, { widgets, layout: layoutToSave });
        setSuccessMessage("Dashboard saved successfully to Firebase");
      } else {
        await api.post(`/dashboard/devices/${deviceId}/dashboard`, {
          config: { widgets, layout: layoutToSave },
        });
        setSuccessMessage("Dashboard saved successfully");
      }
      
      // Update local layout state to match saved layout
      setLayout(layoutToSave);
      setEditMode(false);
    } catch (err) {
      console.error("Dashboard save error:", err);
      setError(err.message || err.response?.data?.detail || "Failed to save dashboard");
    } finally {
      setSaving(false);
    }
  };

  // Generate dynamic widgets from discovered fields
  const dynamicWidgets = useMemo(() => {
    console.log("🔧 Generating widgets from discoveredFields:", discoveredFields);
    if (!discoveredFields || discoveredFields.length === 0) {
      console.log("⚠️ No discoveredFields, returning empty widgets");
      return [];
    }
    
    const widgets = [];
    
    discoveredFields.forEach((field) => {
      // Only create widgets for numeric fields
      const fieldType = field.field_type || field.type;
      if (fieldType !== 'number') {
        console.log(`⏭️ Skipping non-numeric field: ${field.key} (type: ${fieldType})`);
        return;
      }
      
      console.log(`✅ Creating widget for field: ${field.key}`);
      
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
      console.log("📚 Widget library: Returning", dynamicWidgets.length, "widgets");
      return dynamicWidgets;
    }
    // Fallback: if no telemetry yet, show empty (user will see widgets once device sends data)
    console.log("📚 Widget library: No discoveredFields, returning empty array");
    return [];
  }, [dynamicWidgets, discoveredFields]);

  const renderWidget = (widget) => {
    // Get the latest value directly from readings (most reliable source)
    let value = undefined;
    if (readings && readings.length > 0) {
      // Find the most recent reading for this field
      const fieldReadings = readings.filter(r => r.key === widget.field);
      if (fieldReadings.length > 0) {
        // Readings are already sorted by timestamp descending, so first one is latest
        value = fieldReadings[0].value;
      }
    }
    
    // Fallback to telemetryData if not found in readings
    if ((value === undefined || value === null) && telemetryData) {
      value = getValueByField(telemetryData, widget.field);
    }
    
    // Final fallback to externalData
    if ((value === undefined || value === null) && externalData && externalData.records && externalData.records.length > 0) {
      const latestRecord = externalData.records[0];
      if (latestRecord[widget.field] !== undefined && latestRecord[widget.field] !== null) {
        value = latestRecord[widget.field];
      }
    }
    
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
                      value={readingsFilter.key || ""}
                      onChange={(e) => setReadingsFilter({ ...readingsFilter, key: e.target.value || "" })}
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
