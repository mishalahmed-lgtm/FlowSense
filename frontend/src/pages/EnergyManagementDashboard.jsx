import { useEffect, useState, useMemo, useCallback } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { createApiClient } from "../api/client.js";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import { saveToCache, loadFromCache, getCacheKey, clearCache } from "../utils/pageCache.js";
import { isSmartLPGTenant } from "../utils/tenantHelpers.js";
import { fetchSmartLPGDataForDashboard, calculateGasConsumption } from "../services/smartLPGDataMapper.js";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, PieChart, Pie, Cell } from "recharts";
import { generateDummyEnergyData } from "../utils/dummyData.js";

const UTILITY_COLORS = {
  electricity: "#facc15",
  gas: "#f97316",
  water: "#3b82f6",
  irrigation: "#10b981",
};

// Map country codes and names to currency
const COUNTRY_TO_CURRENCY = {
  SA: "SAR",
  "SAUDI ARABIA": "SAR",
  AE: "AED",
  "UNITED ARAB EMIRATES": "AED",
  US: "USD",
  "UNITED STATES": "USD",
  GB: "GBP",
  "UNITED KINGDOM": "GBP",
};

export default function EnergyManagementDashboard() {
  const { token, isTenantAdmin, user } = useAuth();
  const api = useMemo(() => createApiClient(token), [token]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState("24h"); // 24h, 7d, 30d
  const [dateRange, setDateRange] = useState({ from: null, to: null, label: "" });
  const [topConsumersLimit, setTopConsumersLimit] = useState(10);
  const [energyData, setEnergyData] = useState({
    realtime: {},
    totals: {},
    trends: {},
    topConsumers: [],
    costBreakdown: [],
  });

  const loadEnergyData = useCallback(async (forceRefresh = false) => {
    // For Firebase tenants (tenant_id = 2 or 3), clear old cache and always generate fresh data
    if (user?.tenant_id === 2 || user?.tenant_id === 3) {
      const oldCacheKey = getCacheKey('energy_data', { timeRange, tenant_id: user?.tenant_id });
      clearCache(oldCacheKey);
      console.log(`🔥 [ENERGY] Cleared old cache for tenant_id = ${user?.tenant_id} to show updated numbers`);
      forceRefresh = true;
    }
    
    // Try to load from cache first
    const cacheKey = getCacheKey('energy_data', { timeRange, tenant_id: user?.tenant_id });
    
    if (!forceRefresh) {
      const cachedData = loadFromCache(cacheKey);
      if (cachedData) {
        console.log("📦 Using cached energy data");
        setEnergyData(cachedData.energyData);
        setDateRange(cachedData.dateRange);
        setLoading(false);
        return;
      }
    }
    
    setLoading(true);
    setError(null);
    try {
      const today = new Date();
      const fromDate = new Date(today);
      
      if (timeRange === "24h") {
        fromDate.setHours(today.getHours() - 24);
      } else if (timeRange === "7d") {
        fromDate.setDate(today.getDate() - 7);
      } else if (timeRange === "30d") {
        fromDate.setDate(today.getDate() - 30);
      }
      
      const hours = timeRange === "24h" ? 24 : timeRange === "7d" ? 168 : 720;
      
      // For Firebase tenants, use appropriate data source
      const isSmartLPG = isSmartLPGTenant(user?.tenant_id);
      
      if (isSmartLPG) {
        console.log("🔥 [ENERGY] Loading SmartLPG gas consumption data...");
        const smartLPGData = await fetchSmartLPGDataForDashboard();
        
        if (smartLPGData.success && smartLPGData.tekelekDevices) {
          // Calculate gas consumption for all Tekelek devices
          const gasData = smartLPGData.tekelekDevices.map(device => {
            const consumption = calculateGasConsumption(device);
            return {
              device_id: device.device_id,
              device_name: device.name,
              utility_kind: "gas",
              consumption: parseFloat(consumption.monthly_consumption_kg),
              cost: parseFloat(consumption.monthly_cost_aed),
              currency: "AED"
            };
          });
          
          // Calculate totals
          const totalConsumption = gasData.reduce((sum, d) => sum + d.consumption, 0);
          const totalCost = gasData.reduce((sum, d) => sum + d.cost, 0);
          
          // Generate trends (hourly data)
          const trends = [];
          for (let i = hours - 1; i >= 0; i--) {
            const timestamp = new Date(Date.now() - i * 60 * 60 * 1000);
            trends.push({
              timestamp: timestamp.toISOString(),
              consumption: totalConsumption / hours,
              cost: totalCost / hours
            });
          }
          
          setEnergyData({
            realtime: {
              power_w: 0,
              voltage_v: 0,
              current_a: 0
            },
            totals: {
              electricity: { consumption: 0, cost: 0, currency: "AED" },
              gas: {
                consumption: totalConsumption,
                cost: totalCost,
                currency: "AED"
              },
              water: { consumption: 0, cost: 0, currency: "AED" }
            },
            trends: trends,
            topConsumers: gasData.sort((a, b) => b.consumption - a.consumption).slice(0, 10),
            costBreakdown: [{ name: "Gas", value: totalCost, color: UTILITY_COLORS.gas }]
          });
          
          const cacheKey = getCacheKey('energy_data', { timeRange, tenant_id: user?.tenant_id });
          saveToCache(cacheKey, { energyData: { totals: { gas: { consumption: totalConsumption, cost: totalCost, currency: "AED" } } }, dateRange: { from: '', to: '', label: '' } });
          
          setLoading(false);
          setError(null);
          console.log(`✅ [ENERGY] SmartLPG gas data loaded: ${gasData.length} devices, ${totalConsumption.toFixed(2)} kg, ${totalCost.toFixed(2)} AED`);
          return;
        } else {
          console.error("❌ SmartLPG data load failed or no Tekelek devices");
          setError("Failed to load SmartLPG gas consumption data");
          setLoading(false);
          return;
        }
      }
      
      // For tenant_id = 2 (not SmartLPG), use dummy energy data (NO FIREBASE FETCH)
      if (user?.tenant_id === 2) {
        console.log("🔥 [ENERGY] Generating dummy energy data for tenant_id = 2 (instant)");
        
        // Generate dummy data based on fixed device count (no Firebase fetch needed)
        const dummyDeviceCount = 2000;
        const dummyDevices = Array.from({ length: dummyDeviceCount }, (_, i) => ({
          device_id: `device_${i + 1}`,
          name: `Device ${i + 1}`,
        }));
        
        const dummyEnergy = generateDummyEnergyData(dummyDevices, hours);
        console.log("✅ [ENERGY] Generated data instantly");
        console.log("📊 [ENERGY] Total consumption:", dummyEnergy.summary.total_consumption_kwh, "kWh");
        console.log("📊 [ENERGY] Total cost:", dummyEnergy.summary.total_cost, "SAR");
        console.log("📊 [ENERGY] Hours:", hours, "| Expected total:", hours <= 24 ? 200 : hours <= 168 ? 2000 : 4000);
        console.log("📊 [ENERGY] topConsumers sample:", dummyEnergy.topConsumers?.[0]);
        
        // Ensure topConsumers has correct structure
        const topConsumers = (dummyEnergy.topConsumers || []).map(device => ({
          device_id: device.device_id || `device_${Math.random()}`,
          device_name: device.device_name || device.name || `Device ${Math.random()}`,
          utility_kind: device.utility_kind || 'electricity',
          consumption: device.consumption ?? device.total_kwh ?? 0,
          cost: device.cost ?? 0,
          currency: device.currency || "SAR",
        }));
        
        try {
          const energyDataObj = {
            realtime: {
              power_w: dummyEnergy.summary.avg_power_w,
              voltage_v: 220,
              current_a: Math.round(dummyEnergy.summary.avg_power_w / 220 * 100) / 100,
            },
            totals: {
              electricity: {
                consumption: dummyEnergy.summary.total_consumption_kwh * 0.6,
                cost: dummyEnergy.summary.total_cost * 0.65,
                currency: "SAR",
              },
              gas: {
                consumption: dummyEnergy.summary.total_consumption_kwh * 0.25,
                cost: dummyEnergy.summary.total_cost * 0.20,
                currency: "SAR",
              },
              water: {
                consumption: dummyEnergy.summary.total_consumption_kwh * 0.15,
                cost: dummyEnergy.summary.total_cost * 0.15,
                currency: "SAR",
              },
            },
            trends: dummyEnergy.trends || [],
            topConsumers: topConsumers,
            costBreakdown: dummyEnergy.costBreakdown || [],
          };
          
          setEnergyData(energyDataObj);
          
          // Save to cache
          const cacheKey = getCacheKey('energy_data', { timeRange, tenant_id: user?.tenant_id });
          saveToCache(cacheKey, { energyData: energyDataObj, dateRange: { from: '', to: '', label: '' } });
          
          setLoading(false);
          setError(null);
          return;
        } catch (err) {
          console.error("❌ [ENERGY] Failed to generate dummy data:", err);
          setError("Failed to generate energy data");
          setLoading(false);
          return;
        }
      }

      const fromDateStr = fromDate.toISOString().slice(0, 10);
      // Add 1 day to today for toDateStr since backend uses exclusive end date (< period_end)
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);
      const toDateStr = tomorrow.toISOString().slice(0, 10);

      // Store current period label for display
      const fmtOpts = { year: "numeric", month: "short", day: "numeric" };
      const label = `${fromDate.toLocaleDateString(undefined, fmtOpts)} – ${today.toLocaleDateString(undefined, fmtOpts)}`;
      setDateRange({ from: fromDateStr, to: toDateStr, label });

      // Load energy consumption from ALL devices (not just utility meters)
      let allDevicesEnergy = [];
      try {
        const energyResponse = await api.get("/admin/utility/energy/all-devices", {
          params: {
            from_date: fromDateStr,
            to_date: toDateStr,
          },
        });
        allDevicesEnergy = energyResponse.data || [];
      } catch (err) {
        console.warn("Failed to load all-devices energy data:", err);
      }

      // Also load consumption data for utilities (gas, water) from utility meters
      const utilities = ["gas", "water"];
      const utilityConsumption = [];
      
      for (const utility of utilities) {
        try {
          const response = await api.get("/admin/utility/consumption/preview", {
            params: {
              utility_kind: utility,
              from_date: fromDateStr,
              to_date: toDateStr,
            },
          });
          const data = response.data || [];
          console.log(`${utility} consumption data (${data.length} items):`, data);
          if (data.length > 0) {
            console.log(`First ${utility} item:`, JSON.stringify(data[0], null, 2));
          }
          utilityConsumption.push(...data);
        } catch (err) {
          console.warn(`Failed to load ${utility} data:`, err);
        }
      }

      // Determine default currency from tenant country or API response
      let defaultCurrency = "USD";
      
      // Check for placeholder entry first (device_id === 0 or device_external_id === "__currency_placeholder__")
      const placeholderEntry = allDevicesEnergy.find(item => 
        item.device_id === 0 || item.device_external_id === "__currency_placeholder__"
      );
      
      if (placeholderEntry && placeholderEntry.currency) {
        defaultCurrency = placeholderEntry.currency;
        console.log("Using currency from placeholder:", defaultCurrency);
      }
      // Then try to get currency from actual API responses
      else if (allDevicesEnergy.length > 0 && allDevicesEnergy[0].currency) {
        defaultCurrency = allDevicesEnergy[0].currency;
        console.log("Using currency from first energy entry:", defaultCurrency);
      } else if (utilityConsumption.length > 0 && utilityConsumption[0].currency) {
        defaultCurrency = utilityConsumption[0].currency;
        console.log("Using currency from utility consumption:", defaultCurrency);
      } else {
        // If no data, try to get tenant info from user profile
        try {
          const userResp = await api.get("/admin/users/me");
          if (userResp.data?.tenant_id) {
            // Try to get tenant details
            try {
              const tenantResp = await api.get("/admin/tenants");
              const tenant = tenantResp.data?.find(t => t.id === userResp.data.tenant_id);
              if (tenant?.country) {
                const countryUpper = tenant.country.toUpperCase();
                if (COUNTRY_TO_CURRENCY[countryUpper]) {
                  defaultCurrency = COUNTRY_TO_CURRENCY[countryUpper];
                  console.log("Using currency from tenant country:", defaultCurrency, "for country:", tenant.country);
                }
              }
            } catch (tenantErr) {
              console.warn("Could not fetch tenant list:", tenantErr);
            }
          }
        } catch (err) {
          console.warn("Failed to fetch user/tenant info for currency:", err);
        }
      }

      // Hard override for Murabba tenant (tenant_id === 3) so you always see SAR
      // This is a safety net in case backend metadata is missing
      if (user?.tenant_id === 3 && defaultCurrency === "USD") {
        defaultCurrency = "SAR";
        console.log("Overriding currency to SAR for Murabba tenant (tenant_id=3)");
      }
      
      console.log("Final determined currency:", defaultCurrency);

      // Calculate totals
      const totals = {
        electricity: { consumption: 0, cost: 0, currency: defaultCurrency },
        gas: { consumption: 0, cost: 0, currency: defaultCurrency },
        water: { consumption: 0, cost: 0, currency: defaultCurrency },
      };

      const deviceMap = new Map();
      const costBreakdown = [];

      // Aggregate electricity from all devices
      // Filter out placeholder entries (device_id === 0 or device_external_id === "__currency_placeholder__")
      const realEnergyData = allDevicesEnergy.filter(item => 
        item.device_id !== 0 && item.device_external_id !== "__currency_placeholder__"
      );
      
      // Currency should already be set from defaultCurrency above, but ensure it's applied
      // This is a safety check in case the placeholder wasn't found
      const foundPlaceholder = allDevicesEnergy.find(item => 
        item.device_id === 0 || item.device_external_id === "__currency_placeholder__"
      );
      if (foundPlaceholder && foundPlaceholder.currency) {
        totals.electricity.currency = foundPlaceholder.currency;
        totals.gas.currency = foundPlaceholder.currency;
        totals.water.currency = foundPlaceholder.currency;
      }
      
      realEnergyData.forEach((item) => {
        totals.electricity.consumption += item.total_energy_kwh || 0;
        totals.electricity.cost += item.cost || 0;
        // Use currency from API if available, otherwise keep default
        if (item.currency) {
          totals.electricity.currency = item.currency;
        }

        // Track per-device consumption (skip placeholder entries)
        if (item.device_id === 0) return;
        
        const key = `${item.device_id}-electricity`;
        if (!deviceMap.has(key)) {
          deviceMap.set(key, {
            device_id: item.device_id,
            device_name: item.device_name || item.device_external_id,
            utility_kind: "electricity",
            consumption: 0,
            cost: 0,
            currency: item.currency,
          });
        }
        const deviceData = deviceMap.get(key);
        deviceData.consumption += item.total_energy_kwh || 0;
        deviceData.cost += item.cost || 0;
      });

      // Aggregate gas and water from utility meters
      utilityConsumption.forEach((item) => {
        const utility = item.utility_kind;
        if (totals[utility]) {
          // Handle null/undefined consumption values
          const consumption = (item.consumption !== null && item.consumption !== undefined) ? item.consumption : 0;
          const amount = (item.amount !== null && item.amount !== undefined) ? item.amount : 0;
          totals[utility].consumption += consumption;
          totals[utility].cost += amount;
          // Use currency from API if available, otherwise keep default
          if (item.currency) {
            totals[utility].currency = item.currency;
          }

          // Track per-device consumption
          const key = `${item.device_id}-${utility}`;
          if (!deviceMap.has(key)) {
            deviceMap.set(key, {
              device_id: item.device_id,
              device_name: item.device_name || item.device_external_id,
              utility_kind: utility,
              consumption: 0,
              cost: 0,
              currency: item.currency,
            });
          }
          const deviceData = deviceMap.get(key);
          deviceData.consumption += (item.consumption !== null && item.consumption !== undefined) ? item.consumption : 0;
          deviceData.cost += (item.amount !== null && item.amount !== undefined) ? item.amount : 0;
        }
      });

      // Top consumers (we'll apply the limit later in render based on user selection)
      const topConsumers = Array.from(deviceMap.values())
        .sort((a, b) => b.consumption - a.consumption);

      // Cost breakdown for pie chart
      Object.keys(totals).forEach((utility) => {
        if (totals[utility].cost > 0) {
          costBreakdown.push({
            name: utility.charAt(0).toUpperCase() + utility.slice(1),
            value: totals[utility].cost,
            color: UTILITY_COLORS[utility] || "#6b7280",
          });
        }
      });

      // Get latest real-time values from aggregated data
      const realtime = {
        electricity: totals.electricity.consumption,
        gas: totals.gas.consumption,
        water: totals.water.consumption,
      };

      setEnergyData({
        realtime,
        totals,
        trends: {}, // Would need time-series aggregation
        topConsumers,
        costBreakdown,
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load energy data");
    } finally {
      setLoading(false);
    }
  }, [timeRange, user, api]); // Add dependencies for useCallback

  // Load data on mount and when filters change
  useEffect(() => {
    if (!token || !user) return;
    loadEnergyData();
    // Refresh every 2 hours
    const interval = setInterval(() => loadEnergyData(true), 2 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [token, timeRange, user, loadEnergyData]);

  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }

  const totalCost = Object.values(energyData.totals).reduce((sum, util) => sum + (util.cost || 0), 0);
  const totalConsumption = Object.values(energyData.totals).reduce((sum, util) => sum + (util.consumption || 0), 0);
  // Get currency from totals - should be set from API/placeholder
  const currency = energyData.totals.electricity?.currency || 
                   energyData.totals.gas?.currency || 
                   energyData.totals.water?.currency || 
                   "USD";
  
  console.log("Display currency:", currency, "totals:", energyData.totals);

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Dashboard", path: "/dashboard" },
          { label: "Energy Management" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Energy Management Dashboard</h1>
          <p className="page-header__subtitle">
            Live view of energy usage and cost across all devices for the selected period.
          </p>
          {dateRange.label && (
            <p className="text-muted" style={{ marginTop: "var(--space-1)", fontSize: "var(--font-size-sm)" }}>
              Showing data for <strong>{dateRange.label}</strong>
            </p>
          )}
        </div>
        <div className="page-header__actions">
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              {[
                { id: "24h", label: "Last 24 Hours" },
                { id: "7d", label: "Last 7 Days" },
                { id: "30d", label: "Last 30 Days" },
              ].map((range) => (
                <button
                  key={range.id}
                  type="button"
                  className={`btn btn--ghost${timeRange === range.id ? " btn--primary" : ""}`}
                  onClick={() => setTimeRange(range.id)}
                >
                  {range.label}
                </button>
              ))}
            </div>
            <a href="/utility/billing" className="btn btn--primary">
              <Icon name="file" size={18} />
              <span>View Billing Reports</span>
            </a>
          </div>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
          <Icon name="activity" size={48} style={{ opacity: 0.3 }} />
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)" }}>
            Loading energy data...
          </p>
        </div>
      ) : (
        <>
          {/* Summary Metrics */}
          <div className="metrics-grid" style={{ marginBottom: "var(--space-6)", gridTemplateColumns: `repeat(${isSmartLPG ? 2 : 4}, 1fr)` }}>
            {/* Only show electricity card if not SmartLPG tenant or if it has consumption */}
            {(!isSmartLPG || (energyData.totals.electricity?.consumption > 0)) && (
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Energy Consumption</span>
                  <Icon name="zap" size="lg" />
                </div>
                <div className="metric-card__value">
                  {energyData.totals.electricity?.consumption?.toFixed(2) || "0.00"}
                  <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> kWh</span>
                </div>
                <div className="metric-card__footer">
                  Cost: {currency} {energyData.totals.electricity?.cost?.toFixed(2) || "0.00"}
                  <span style={{ fontSize: "var(--font-size-xs)", marginLeft: "var(--space-2)", opacity: 0.7 }}>
                    (All devices)
                  </span>
                </div>
              </div>
            )}

            {/* Only show water card if not SmartLPG tenant or if it has consumption */}
            {(!isSmartLPG || (energyData.totals.water?.consumption > 0)) && (
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Water Usage</span>
                  <Icon name="droplet" size="lg" />
                </div>
                <div className="metric-card__value">
                  {energyData.totals.water?.consumption?.toFixed(2) || "0.00"}
                  <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> m³</span>
                </div>
                <div className="metric-card__footer">
                  Cost: {currency} {energyData.totals.water?.cost?.toFixed(2) || "0.00"}
                </div>
              </div>
            )}

            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Gas Consumption</span>
                <Icon name="flame" size="lg" />
              </div>
              <div className="metric-card__value">
                {energyData.totals.gas?.consumption?.toFixed(2) || "0.00"}
                <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> {isSmartLPG ? "kg" : "units"}</span>
              </div>
              <div className="metric-card__footer">
                Cost: {currency} {energyData.totals.gas?.cost?.toFixed(2) || "0.00"}
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Total Cost</span>
                <Icon name="utility" size="lg" />
              </div>
              <div className="metric-card__value text-success" style={{ fontSize: "var(--font-size-2xl)" }}>
                {currency} {totalCost.toFixed(2)}
              </div>
              <div className="metric-card__footer">
                {dateRange.label ? `Period: ${dateRange.label}` : `Period: ${timeRange}`}
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-6)", marginBottom: "var(--space-6)" }}>
            {/* Cost Breakdown Pie Chart */}
            {energyData.costBreakdown.length > 0 && (
              <div className="card">
                <div className="card__header">
                  <h3 className="card__title">Cost Breakdown</h3>
                </div>
                <div className="card__body">
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={energyData.costBreakdown}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {energyData.costBreakdown.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => `${currency} ${Number(value).toFixed(2)}`} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Consumption Comparison Bar Chart */}
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">Consumption by Utility Type</h3>
              </div>
              <div className="card__body">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={[
                    { name: "Electricity", value: energyData.totals.electricity?.consumption || 0, unit: "kWh" },
                    { name: "Gas", value: energyData.totals.gas?.consumption || 0, unit: "units" },
                    { name: "Water", value: energyData.totals.water?.consumption || 0, unit: "m³" },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value, name, props) => [`${value.toFixed(2)} ${props.payload.unit}`, "Consumption"]} />
                    <Bar dataKey="value" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Top Energy Consumers */}
          {energyData.topConsumers.length > 0 && (
            <div className="card">
              <div className="card__header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 className="card__title">Top Energy Consumers</h3>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <label className="form-label" style={{ margin: 0, fontSize: "var(--font-size-sm)", whiteSpace: "nowrap" }}>
                    Show top
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    className="form-input"
                    value={topConsumersLimit}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      if (!Number.isNaN(val) && val >= 1) {
                        const clamped = Math.max(1, Math.min(val, 100));
                        setTopConsumersLimit(clamped);
                      } else if (e.target.value === "") {
                        // Allow empty input while typing
                        return;
                      }
                    }}
                    onBlur={(e) => {
                      // Ensure a valid value on blur if input is empty or invalid
                      const val = parseInt(e.target.value, 10);
                      if (Number.isNaN(val) || val < 1) {
                        setTopConsumersLimit(10);
                      }
                    }}
                    style={{ width: "72px", padding: "var(--space-2) var(--space-4)", textAlign: "left" }}
                  />
                  <span className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>
                    devices
                  </span>
                </div>
              </div>
              <div className="card__body">
                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Device</th>
                        <th>Utility Type</th>
                        <th>Consumption</th>
                        <th>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {energyData.topConsumers.slice(0, topConsumersLimit).map((device, idx) => {
                        const consumption = device.consumption ?? device.total_kwh ?? 0;
                        const cost = device.cost ?? 0;
                        const currency = device.currency ?? "SAR";
                        const utilityKind = device.utility_kind || "electricity";
                        
                        return (
                          <tr key={`${device.device_id}-${utilityKind}-${idx}`}>
                          <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                              {device.device_name || device.device_id || `Device ${idx + 1}`}
                          </td>
                          <td>
                            <span className="badge" style={{ 
                                backgroundColor: `${UTILITY_COLORS[utilityKind] || "#6b7280"}20`,
                                color: UTILITY_COLORS[utilityKind] || "#6b7280",
                                borderColor: UTILITY_COLORS[utilityKind] || "#6b7280"
                            }}>
                                {utilityKind}
                            </span>
                          </td>
                            <td>{typeof consumption === 'number' ? consumption.toFixed(2) : '0.00'}</td>
                          <td style={{ fontWeight: "var(--font-weight-semibold)", color: "var(--color-success-text)" }}>
                              {currency} {typeof cost === 'number' ? cost.toFixed(2) : '0.00'}
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* (Billing link moved up into header actions for quick access) */}
        </>
      )}
    </div>
  );
}

