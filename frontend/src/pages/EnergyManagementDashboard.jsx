import { useEffect, useState, useMemo } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, PieChart, Pie, Cell } from "recharts";

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
  const [energyData, setEnergyData] = useState({
    realtime: {},
    totals: {},
    trends: {},
    topConsumers: [],
    costBreakdown: [],
  });

  useEffect(() => {
    if (!token) return;
    loadEnergyData();
    const interval = setInterval(loadEnergyData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [token, timeRange]);

  const loadEnergyData = async () => {
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

      const fromDateStr = fromDate.toISOString().slice(0, 10);
      const toDateStr = today.toISOString().slice(0, 10);

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
          utilityConsumption.push(...(response.data || []));
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
          totals[utility].consumption += item.consumption || 0;
          totals[utility].cost += item.amount || 0;
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
          deviceData.consumption += item.consumption || 0;
          deviceData.cost += item.amount || 0;
        }
      });

      // Top consumers
      const topConsumers = Array.from(deviceMap.values())
        .sort((a, b) => b.consumption - a.consumption)
        .slice(0, 10);

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
  };

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
            Track energy consumption from all devices (lighting, benches, sensors, meters) and utility usage (gas, water)
          </p>
        </div>
        <div className="page-header__actions">
          <select
            className="form-select"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            style={{ minWidth: "120px" }}
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
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
          <div className="metrics-grid" style={{ marginBottom: "var(--space-6)" }}>
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

            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Gas Consumption</span>
                <Icon name="flame" size="lg" />
              </div>
              <div className="metric-card__value">
                {energyData.totals.gas?.consumption?.toFixed(2) || "0.00"}
                <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> units</span>
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
                Period: {timeRange}
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
              <div className="card__header">
                <h3 className="card__title">Top Energy Consumers</h3>
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
                      {energyData.topConsumers.map((device, idx) => (
                        <tr key={`${device.device_id}-${device.utility_kind}-${idx}`}>
                          <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                            {device.device_name}
                          </td>
                          <td>
                            <span className="badge" style={{ 
                              backgroundColor: `${UTILITY_COLORS[device.utility_kind] || "#6b7280"}20`,
                              color: UTILITY_COLORS[device.utility_kind] || "#6b7280",
                              borderColor: UTILITY_COLORS[device.utility_kind] || "#6b7280"
                            }}>
                              {device.utility_kind}
                            </span>
                          </td>
                          <td>{device.consumption.toFixed(2)}</td>
                          <td style={{ fontWeight: "var(--font-weight-semibold)", color: "var(--color-success-text)" }}>
                            {device.currency} {device.cost.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Link to Detailed Billing Report */}
          <div className="card" style={{ marginTop: "var(--space-6)" }}>
            <div className="card__body" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ marginBottom: "var(--space-2)" }}>Detailed Billing Reports</h3>
                <p className="text-muted" style={{ margin: 0 }}>
                  View detailed consumption reports and download PDF invoices
                </p>
              </div>
              <a href="/utility/billing" className="btn btn--primary">
                <Icon name="file" size={18} />
                <span>View Billing Reports</span>
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

