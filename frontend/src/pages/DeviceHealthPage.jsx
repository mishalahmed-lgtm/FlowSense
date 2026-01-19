import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { generateDummyHealthData, generateDummyHealthSummary } from "../utils/dummyData.js";
import { saveToCache, loadFromCache, getCacheKey } from "../utils/pageCache.js";

export default function DeviceHealthPage() {
  const { token, isTenantAdmin, hasModule, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  // Check cache first to determine initial loading state
  const initialCache = useMemo(() => {
    const cacheKey = getCacheKey('health_page', { tenant_id: user?.tenant_id });
    return loadFromCache(cacheKey);
  }, [user?.tenant_id]);
  
  const [devices, setDevices] = useState(initialCache?.devices || []);
  const [allDevices, setAllDevices] = useState(initialCache?.allDevices || []); // Store all devices for client-side filtering
  const [loading, setLoading] = useState(!initialCache);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [limitFilter, setLimitFilter] = useState(50);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [deviceHistory, setDeviceHistory] = useState([]);
  const [batteryTrend, setBatteryTrend] = useState(null);
  const [batteryTrendExpanded, setBatteryTrendExpanded] = useState(false);
  const [batteryDaysFilter, setBatteryDaysFilter] = useState(10);
  const [batteryFilterMode, setBatteryFilterMode] = useState("days"); // "days" or "dateRange"
  const [batteryFromDate, setBatteryFromDate] = useState("");
  const [batteryToDate, setBatteryToDate] = useState("");
  const [healthSummary, setHealthSummary] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

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

  const loadHealthSummary = async (healthDevices = null) => {
    try {
      // For Firebase tenants, generate dummy summary from device data (NO PostgreSQL calls)
      const { usesFirebase } = await import("../utils/tenantHelpers");
      if (usesFirebase(user?.tenant_id)) {
        if (healthDevices) {
          console.log("📊 Generating dummy health summary for tenant_id = 2");
          const dummySummary = generateDummyHealthSummary(healthDevices);
          setHealthSummary(dummySummary);
          return;
        }
        // If no devices provided, return empty summary (will be set when devices load)
        return;
      }
      
      // Only call PostgreSQL for other tenants
      const response = await api.get("/devices/health/summary");
      setHealthSummary(response.data);
    } catch (err) {
      console.error("Failed to load health summary:", err);
    }
  };

  const loadDevices = async (forceRefresh = false) => {
    // Check cache first
    const cacheKey = getCacheKey('health_page', { tenant_id: user?.tenant_id });
    
    if (!forceRefresh) {
      const cached = loadFromCache(cacheKey);
      if (cached) {
        console.log("📦 Using cached health page data");
        setAllDevices(cached.allDevices);
        setDevices(cached.devices);
        setHealthSummary(cached.healthSummary);
        setLoading(false);
        return;
      }
    }
    
    try {
      setLoading(true);
      const allDevicesMap = new Map();
      
      // For Firebase tenants, load devices from Firebase
      const { isSmartLPGTenant } = await import("../utils/tenantHelpers");
      const isSmartLPG = isSmartLPGTenant(user?.tenant_id);
      
      if (user?.tenant_id === 2 || isSmartLPG) {
        console.log(`🔥 Loading devices from Firebase for tenant_id = ${user?.tenant_id} health page...`);
        try {
          const mapperModule = isSmartLPG ? "../services/smartLPGDataMapper" : "../services/firebaseDataMapper";
          const fetchFunction = isSmartLPG ? "fetchSmartLPGDataForDashboard" : "fetchFirebaseDataForDashboard";
          const mapper = await import(mapperModule);
          const fetchFirebaseDataForDashboard = mapper[fetchFunction];
          const firebaseData = await fetchFirebaseDataForDashboard();
          
          if (firebaseData.success && firebaseData.devices) {
            console.log(`✅ Loaded ${firebaseData.devices.length} devices from Firebase`);
            
            // Add Firebase devices to map
            firebaseData.devices.forEach(device => {
              allDevicesMap.set(device.device_id, device);
            });
            
            // Generate dummy health data for Firebase devices
            const finalDevices = Array.from(allDevicesMap.values());
            const dummyHealthData = generateDummyHealthData(finalDevices);
            
            // Merge dummy health data
            const devicesWithHealth = finalDevices.map((device, idx) => ({
              ...device,
              ...dummyHealthData[idx],
            }));
            
            console.log("✅ Applied dummy health data to Firebase devices");
            setAllDevices(devicesWithHealth);
            
            // Load summary
            loadHealthSummary(devicesWithHealth);
            
            setLoading(false);
            setError(null);
            return;
          }
        } catch (firebaseErr) {
          console.error("Failed to load Firebase devices:", firebaseErr);
          // Continue to regular backend if Firebase fails
        }
      }
      
      // Skip PostgreSQL calls for tenant_id = 2 (Firebase only)
      if (user?.tenant_id === 2) {
        console.log("⚠️ Skipping PostgreSQL calls for tenant_id = 2");
        return;
      }
      
      // Step 1: Fetch ALL devices from /admin/devices using pagination
      // The endpoint supports up to 1000 per page, so we need multiple requests
      try {
        let page = 1;
        let hasMore = true;
        const limit = 1000; // Max per page
        
        while (hasMore) {
          // Try cache endpoint first (only for page 1, fallback to regular for other pages)
          let devicesResponse;
          if (page === 1) {
            try {
              devicesResponse = await api.get("/cache/devices", { 
                params: { page: 1 } 
              });
              // Transform cache response
              if (devicesResponse.data && devicesResponse.data.devices) {
                const transformedDevices = devicesResponse.data.devices.map(device => {
                  const payload = device.payload || {};
                  return {
                    id: device.device_id,
                    device_id: device.device_id,
                    name: payload.name || device.device_id,
                    is_active: payload.is_active !== false,
                  };
                });
                devicesResponse.data = {
                  devices: transformedDevices,
                  total: devicesResponse.data.total || 0,
                  page: 1,
                  totalPages: Math.ceil((devicesResponse.data.total || 0) / limit),
                };
              }
            } catch (cacheErr) {
              // Fallback to regular endpoint
              if (cacheErr.response?.status === 404) {
                devicesResponse = await api.get("/admin/devices", { 
                  params: { limit, page } 
          });
              } else {
                throw cacheErr;
              }
            }
          } else {
            // For pages > 1, use regular endpoint (cache only has page 1)
            devicesResponse = await api.get("/admin/devices", { 
              params: { limit, page } 
            });
          }
          
          // Handle paginated response
          const responseData = devicesResponse.data;
          const devicesList = Array.isArray(responseData) 
            ? responseData 
            : (responseData?.devices || []);
          
          const total = responseData?.total || responseData?.totalDeviceCount || devicesList.length;
          const currentPage = responseData?.page || page;
          const totalPages = responseData?.totalPages || Math.ceil(total / limit);
          
          console.log(`Loading page ${currentPage}/${totalPages}: ${devicesList.length} devices`);
          
          // Create basic device entries
          devicesList.forEach((device) => {
            if (device && device.device_id) {
              // Use device_identifier as the key for matching with health data
              const deviceIdentifier = device.device_id;
              allDevicesMap.set(deviceIdentifier, {
                id: device.id, // Store numeric ID for API calls
                device_id: device.device_id,
                device_name: device.name || device.device_id,
                device_identifier: deviceIdentifier,
                current_status: device.is_active ? "online" : "offline",
                last_seen_at: null,
                uptime_24h_percent: null,
                uptime_7d_percent: null,
                uptime_30d_percent: null,
                connectivity_score: null,
                last_battery_level: null,
                message_count_24h: 0,
                message_count_7d: 0,
                avg_message_interval_seconds: null,
                battery_trend: null,
                estimated_battery_days_remaining: null,
              });
            }
          });
          
          // Check if there are more pages
          if (currentPage >= totalPages || devicesList.length < limit) {
            hasMore = false;
          } else {
            page++;
          }
        }
        
        console.log(`Loaded ${allDevicesMap.size} devices from /admin/devices (all pages)`);
      } catch (err) {
        console.error("Failed to load devices from /admin/devices:", err);
        console.error("Error details:", err.response?.data || err.message);
        // If /admin/devices fails, try cache/health, then regular health endpoint as fallback
        try {
          let response;
          try {
            // Try cache health endpoint first
            response = await api.get("/cache/health", {});
            // Transform cache response
            if (response.data && response.data.devices) {
              const healthDevices = response.data.devices.map(device => ({
                device_id: device.device_id,
                device_identifier: device.device_id,
                device_name: device.payload?.name || device.device_id,
                current_status: device.health?.status || "offline",
                last_seen_at: device.health?.last_seen_at || null,
                last_battery_level: device.telemetry?.battery || null,
              }));
              response.data = healthDevices;
            }
          } catch (cacheErr) {
            // Fallback to regular health endpoint
            if (cacheErr.response?.status === 404) {
              response = await api.get("/devices/health", {});
            } else {
              throw cacheErr;
            }
          }
          const healthDevices = response.data || [];
          console.log(`Fallback: Loaded ${healthDevices.length} devices from /devices/health`);
          healthDevices.forEach((healthDevice) => {
            if (healthDevice && healthDevice.device_identifier) {
              allDevicesMap.set(healthDevice.device_identifier, {
                ...healthDevice,
                id: healthDevice.device_id,
              });
            }
          });
        } catch (healthErr) {
          console.error("Failed to load devices from health endpoint as fallback:", healthErr);
        }
      }
      
      // Step 2: Fetch health data and merge it
      // Health endpoint is limited to 100 per request, so we try different status filters
      // But we already have all devices from /admin/devices, so we just try to enrich with health data
      const statusFilters = ["online", "offline", "degraded"];
      
      for (const status of statusFilters) {
        try {
          const params = { status };
          const response = await api.get("/devices/health", { params });
          const healthDevices = response.data || [];
          
          console.log(`Loaded ${healthDevices.length} devices with health status: ${status}`);
          
          // Merge health data into existing devices
          // Health response uses device_identifier (string) to identify devices
          healthDevices.forEach((healthDevice) => {
            if (healthDevice && healthDevice.device_identifier) {
              const existing = allDevicesMap.get(healthDevice.device_identifier);
              if (existing) {
                // Update with health data, preserving the numeric id if we have it
                Object.assign(existing, {
                  ...healthDevice,
                  id: existing.id || healthDevice.device_id, // Preserve numeric id
                });
              } else {
                // Add new device with health data (shouldn't happen if /admin/devices worked)
                allDevicesMap.set(healthDevice.device_identifier, {
                  ...healthDevice,
                  id: healthDevice.device_id,
                });
              }
            }
          });
        } catch (err) {
          console.warn(`Failed to load health data with status ${status}:`, err);
        }
      }
      
      // Also try without status filter to get any remaining devices
      try {
        // Try cache health endpoint first
        let response;
        try {
          response = await api.get("/cache/health", {});
          // Transform cache response
          if (response.data && response.data.devices) {
            response.data = response.data.devices.map(device => ({
              device_id: device.device_id,
              device_identifier: device.device_id,
              device_name: device.payload?.name || device.device_id,
              current_status: device.health?.status || "offline",
              last_seen_at: device.health?.last_seen_at || null,
              last_battery_level: device.telemetry?.battery || null,
            }));
          }
        } catch (cacheErr) {
          // Fallback to regular endpoint
          if (cacheErr.response?.status === 404) {
            response = await api.get("/devices/health", {});
          } else {
            throw cacheErr;
          }
        }
        const healthDevices = response.data || [];
        console.log(`Loaded ${healthDevices.length} devices from /devices/health (no filter)`);
        
        healthDevices.forEach((healthDevice) => {
          if (healthDevice && healthDevice.device_identifier) {
            const existing = allDevicesMap.get(healthDevice.device_identifier);
            if (existing) {
              // Only update if we don't already have health data
              if (!existing.uptime_24h_percent && !existing.connectivity_score) {
                Object.assign(existing, {
                  ...healthDevice,
                  id: existing.id || healthDevice.device_id,
                });
              }
            } else {
              allDevicesMap.set(healthDevice.device_identifier, {
                ...healthDevice,
                id: healthDevice.device_id,
              });
            }
          }
        });
      } catch (err) {
        console.warn("Failed to load health data (no filter):", err);
      }
      
      const finalDevices = Array.from(allDevicesMap.values());
      
      // Ensure we have at least some devices - if not, show error
      if (finalDevices.length === 0) {
        console.error("No devices loaded at all!");
        setError("No devices found. Please check your connection and try again.");
        setAllDevices([]);
      } else {
        console.log(`✅ Total devices loaded: ${finalDevices.length}`);
        console.log(`   Devices with health data: ${finalDevices.filter(d => d.uptime_24h_percent !== null || d.connectivity_score !== null).length}`);
        
        // For tenant_id = 2 OR if no health data, generate dummy health data
        if (user?.tenant_id === 2 || finalDevices.every(d => !d.uptime_24h_percent)) {
          console.log("📊 Generating dummy health data for devices (tenant_id = 2 or missing health data)");
          const dummyHealthData = generateDummyHealthData(finalDevices);
          
          // Merge dummy health data with devices
          finalDevices = finalDevices.map((device, idx) => ({
            ...device,
            ...dummyHealthData[idx],
          }));
          
          console.log("✅ Applied dummy health data to", finalDevices.length, "devices");
        }
        
        setAllDevices(finalDevices);
        
        // Load summary with the health devices
        loadHealthSummary(finalDevices);
        
        setError(null);
        
        // Save to cache
        const cacheKey = getCacheKey('health_page', { tenant_id: user?.tenant_id });
        saveToCache(cacheKey, { allDevices: devicesArray, devices: devicesArray, healthSummary });
      }
    } catch (err) {
      console.error("Error loading devices:", err);
      const errorMessage = err.response?.data?.detail || err.message || "Failed to load device health data";
      setError(errorMessage);
      setAllDevices([]);
    } finally {
      setLoading(false);
    }
  };

  // Load devices once on mount and when token changes
  useEffect(() => {
    if (!token || !user) return;
    loadDevices(); // This now calls loadHealthSummary internally with device data
    // Refresh every 2 hours
    const interval = setInterval(() => loadDevices(true), 2 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [token, user]);

  // Apply search filter and pagination
  useEffect(() => {
    try {
      // Ensure allDevices is an array
      if (!Array.isArray(allDevices)) {
        setDevices([]);
        return;
      }

      let filtered = [...allDevices];

      // Apply search filter
      if (searchQuery && searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        filtered = filtered.filter((device) => {
          if (!device) return false;
          // Check multiple possible field names
          const deviceName = String(device.device_name || device.name || "").toLowerCase();
          const deviceId = String(device.device_id || device.device_identifier || "").toLowerCase();
          // Also check if query matches any part of the device identifier
          return deviceName.includes(query) || 
                 deviceId.includes(query) ||
                 deviceId.replace(/[^a-z0-9]/gi, "").includes(query.replace(/[^a-z0-9]/gi, ""));
        });
      }

      // Apply status filter
      if (statusFilter !== "all") {
        filtered = filtered.filter((device) => {
          if (!device) return false;
          return device.current_status === statusFilter;
        });
      }

      // Calculate pagination
      const totalPages = Math.max(1, Math.ceil(filtered.length / limitFilter));
      const startIndex = Math.max(0, (currentPage - 1) * limitFilter);
      const endIndex = Math.min(startIndex + limitFilter, filtered.length);
      const paginatedDevices = filtered.slice(startIndex, endIndex);

      setDevices(paginatedDevices);
    } catch (err) {
      console.error("Error filtering devices:", err);
      setDevices([]);
    }
  }, [allDevices, searchQuery, limitFilter, currentPage, statusFilter]);

  // Reset to page 1 if current page is beyond available pages (separate effect to avoid loop)
  useEffect(() => {
    try {
      if (!Array.isArray(allDevices)) {
        if (currentPage > 1) setCurrentPage(1);
        return;
      }

      let filtered = [...allDevices];

      if (searchQuery && searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        filtered = filtered.filter((device) => {
          if (!device) return false;
          const deviceName = String(device.device_name || device.name || "").toLowerCase();
          const deviceId = String(device.device_id || device.device_identifier || "").toLowerCase();
          // Also check if query matches any part of the device identifier (remove special chars)
          return deviceName.includes(query) || 
                 deviceId.includes(query) ||
                 deviceId.replace(/[^a-z0-9]/gi, "").includes(query.replace(/[^a-z0-9]/gi, ""));
        });
      }

      if (statusFilter !== "all") {
        filtered = filtered.filter((device) => {
          if (!device) return false;
          return device.current_status === statusFilter;
        });
      }

      const totalPages = Math.max(1, Math.ceil(filtered.length / limitFilter));
      if (currentPage > totalPages && totalPages > 0) {
        setCurrentPage(1);
      }
    } catch (err) {
      console.error("Error resetting page:", err);
    }
  }, [allDevices, searchQuery, limitFilter, statusFilter]); // Note: currentPage NOT in deps

  const loadBatteryTrend = async (deviceId, days, fromDate = null, toDate = null) => {
    try {
      if (!deviceId) {
        console.warn("No device ID provided for battery trend");
        setBatteryTrend(null);
        return;
      }
      
      // For tenant admins, use device_identifier (string) directly
      // The backend endpoint handles string device_id for tenant admins
      const deviceIdParam = deviceId; // Use as-is (string for tenant admins)
      
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
      
      const batteryResp = await api.get(`/devices/${deviceIdParam}/health/battery-trend`, {
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
    try {
      if (!device) {
        console.error("No device provided to handleViewDetails");
        return;
      }
      
      setSelectedDevice(device);
      setShowDetails(true);
      setBatteryTrendExpanded(false); // Reset expanded state for new device
      setBatteryFilterMode("days"); // Reset to days filter
      setDetailsError(null); // Clear previous errors
      setDeviceHistory([]); // Clear previous history
      setBatteryTrend(null); // Clear previous battery trend
      // Set default date range (last 10 days)
      const toDate = new Date();
      const fromDate = new Date();
      fromDate.setDate(fromDate.getDate() - 10);
      setBatteryToDate(toDate.toISOString().split('T')[0]);
      setBatteryFromDate(fromDate.toISOString().split('T')[0]);
      
      setLoadingDetails(true);
      // For tenant admins, use device_identifier (string) instead of numeric id
      // The backend endpoint handles string device_id for tenant admins
      const deviceId = device.device_identifier || device.device_id;
      
      if (!deviceId) {
        throw new Error("Device ID not found");
      }
      
      // Load health history (don't fail if this errors)
      try {
        const historyResp = await api.get(`/devices/${deviceId}/health/history`, {
          params: { hours: 168 } // 7 days
        });
        setDeviceHistory(historyResp.data || []);
      } catch (historyErr) {
        console.warn("Failed to load health history:", historyErr);
        setDeviceHistory([]);
      }
      
      // Load battery trend (don't fail if this errors)
      try {
        await loadBatteryTrend(deviceId, batteryDaysFilter);
      } catch (batteryErr) {
        console.warn("Failed to load battery trend:", batteryErr);
        setBatteryTrend({ data_points: [] });
      }
    } catch (err) {
      console.error("Error in handleViewDetails:", err);
      setDetailsError(err.message || "Failed to open device details");
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleBatteryFilterChange = async () => {
    if (selectedDevice) {
      const deviceId = selectedDevice.device_identifier || selectedDevice.device_id;
      if (batteryFilterMode === "dateRange" && batteryFromDate && batteryToDate) {
        await loadBatteryTrend(deviceId, null, batteryFromDate, batteryToDate);
      } else {
        await loadBatteryTrend(deviceId, batteryDaysFilter);
      }
    }
  };

  const handleBatteryDaysFilterChange = async (days) => {
    setBatteryDaysFilter(days);
    setBatteryFilterMode("days");
    if (selectedDevice) {
      const deviceId = selectedDevice.device_identifier || selectedDevice.device_id;
      await loadBatteryTrend(deviceId, days);
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
        <div className="page-header__actions" style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="text"
            className="form-input"
            placeholder="Search devices..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1); // Reset to first page when search changes
            }}
            style={{ minWidth: "200px", maxWidth: "300px" }}
          />
          <select
            className="form-select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1); // Reset to first page when filter changes
            }}
            style={{ width: "auto" }}
          >
            <option value="all">All Status</option>
            <option value="online">Online</option>
            <option value="degraded">Degraded</option>
            <option value="offline">Offline</option>
          </select>
          <select
            className="form-select"
            value={limitFilter}
            onChange={(e) => {
              setLimitFilter(Number(e.target.value));
              setCurrentPage(1); // Reset to first page when limit changes
            }}
            style={{ minWidth: "120px" }}
          >
            <option value="10">Show 10</option>
            <option value="25">Show 25</option>
            <option value="50">Show 50</option>
            <option value="100">Show 100</option>
            <option value="200">Show 200</option>
            <option value="500">Show 500</option>
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

      {healthSummary && (
        <div className="card" style={{ marginBottom: "var(--space-6)" }}>
          <h3 style={{ marginBottom: "var(--space-4)" }}>Health Summary</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-4)" }}>
            <div>
              <div className="text-muted" style={{ fontSize: "0.875rem" }}>Online Devices</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#10b981" }}>{healthSummary.online_count || 0}</div>
            </div>
            <div>
              <div className="text-muted" style={{ fontSize: "0.875rem" }}>Offline Devices</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#ef4444" }}>{healthSummary.offline_count || 0}</div>
            </div>
            <div>
              <div className="text-muted" style={{ fontSize: "0.875rem" }}>Unhealthy Devices</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "#f97316" }}>{healthSummary.unhealthy_count || 0}</div>
            </div>
            <div>
              <div className="text-muted" style={{ fontSize: "0.875rem" }}>Total Devices</div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold" }}>{healthSummary.total_count || 0}</div>
            </div>
          </div>
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
                  {loading ? "Loading..." : `No devices found${searchQuery ? ` matching "${searchQuery}"` : ""}${statusFilter !== "all" ? ` with status "${statusFilter}"` : ""}`}
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
        
        {/* Pagination Controls */}
        {(() => {
          if (!Array.isArray(allDevices) || allDevices.length === 0) return null;
          
          let filtered = [...allDevices];
          
          if (searchQuery && searchQuery.trim()) {
            const query = searchQuery.toLowerCase().trim();
            filtered = filtered.filter((device) => {
              if (!device) return false;
              const deviceName = String(device.device_name || device.name || "").toLowerCase();
              const deviceId = String(device.device_id || device.device_identifier || "").toLowerCase();
              // Also check if query matches any part of the device identifier (remove special chars)
              return deviceName.includes(query) || 
                     deviceId.includes(query) ||
                     deviceId.replace(/[^a-z0-9]/gi, "").includes(query.replace(/[^a-z0-9]/gi, ""));
            });
          }
          
          if (statusFilter !== "all") {
            filtered = filtered.filter((device) => {
              if (!device) return false;
              return device.current_status === statusFilter;
            });
          }
          
          const filteredCount = filtered.length;
          
          if (filteredCount === 0) return null; // Don't show pagination if no results
          
          const totalPages = Math.max(1, Math.ceil(filteredCount / limitFilter));
          const startIndex = filteredCount > 0 ? (currentPage - 1) * limitFilter + 1 : 0;
          const endIndex = Math.min(currentPage * limitFilter, filteredCount);
          
          // Always show pagination if there are results
          return (
            <div style={{ 
              display: "flex", 
              justifyContent: "space-between", 
              alignItems: "center",
              marginTop: "var(--space-6)",
              paddingTop: "var(--space-4)",
              borderTop: "1px solid var(--color-border-light)"
            }}>
              <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>
                Showing {startIndex} to {endIndex} of {filteredCount} devices
                {filteredCount !== allDevices.length && (
                  <span style={{ marginLeft: "var(--space-2)", color: "var(--color-text-tertiary)" }}>
                    (filtered from {allDevices.length} total)
                  </span>
                )}
              </div>
              {totalPages > 1 && (
                <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                  <button
                    className="btn btn--sm btn--secondary"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                    style={{ opacity: currentPage === 1 ? 0.5 : 1, cursor: currentPage === 1 ? "not-allowed" : "pointer" }}
                  >
                    First
                  </button>
                  <button
                    className="btn btn--sm btn--secondary"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    style={{ opacity: currentPage === 1 ? 0.5 : 1, cursor: currentPage === 1 ? "not-allowed" : "pointer" }}
                  >
                    Previous
                  </button>
                  <span style={{ 
                    padding: "var(--space-2) var(--space-4)",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-primary)",
                    fontWeight: "var(--font-weight-medium)"
                  }}>
                    Page {currentPage} of {totalPages}
                  </span>
                  <button
                    className="btn btn--sm btn--secondary"
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    style={{ opacity: currentPage === totalPages ? 0.5 : 1, cursor: currentPage === totalPages ? "not-allowed" : "pointer" }}
                  >
                    Next
                  </button>
                  <button
                    className="btn btn--sm btn--secondary"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                    style={{ opacity: currentPage === totalPages ? 0.5 : 1, cursor: currentPage === totalPages ? "not-allowed" : "pointer" }}
                  >
                    Last
                  </button>
                </div>
              )}
              {totalPages === 1 && (
                <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-tertiary)" }}>
                  Page 1 of 1
                </div>
              )}
            </div>
          );
        })()}
      </div>

      {/* Device Details Modal */}
      <Modal
        isOpen={showDetails}
        onClose={() => {
          setShowDetails(false);
          setSelectedDevice(null);
          setDeviceHistory([]);
          setBatteryTrend(null);
          setDetailsError(null);
        }}
        title={selectedDevice ? `Health Details: ${selectedDevice.device_name}` : ""}
      >
        {loadingDetails ? (
          <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
            <p>Loading device details...</p>
          </div>
        ) : detailsError ? (
          <div>
            <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
              {detailsError}
            </div>
            {selectedDevice && (
              <div style={{ padding: "var(--space-4)" }}>
                <p style={{ marginBottom: "var(--space-2)" }}>Device: {selectedDevice.device_name || selectedDevice.device_id}</p>
                <p style={{ color: "var(--color-text-tertiary)", fontSize: "var(--font-size-sm)" }}>
                  Some data may not be available. Please try again later.
                </p>
              </div>
            )}
          </div>
        ) : selectedDevice ? (
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
        ) : (
          <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
            <p>No device selected</p>
          </div>
        )}
      </Modal>
    </div>
  );
}

