import { useEffect, useState, useMemo } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Tabs from "../components/Tabs.jsx";
import Collapsible from "../components/Collapsible.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import CompanyDetailsModal from "../components/CompanyDetailsModal.jsx";
import { generateBillingReport, preparePerDeviceReportData, prepareConsolidatedReportData } from "../utils/pdfReportGenerator.js";

const UTILITY_KINDS = [
  { value: "electricity", label: "Electricity", icon: "zap", color: "#facc15" },
  { value: "gas", label: "Gas", icon: "flame", color: "#f97316" },
  { value: "water", label: "Water", icon: "droplet", color: "#3b82f6" },
];

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

export default function UtilityBillingPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const api = createApiClient(token);

  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const [utilityKind, setUtilityKind] = useState("electricity");
  const [fromDate, setFromDate] = useState(formatDateInput(thirtyDaysAgo));
  const [toDate, setToDate] = useState(formatDateInput(today));
  const [viewMode, setViewMode] = useState("per-device");
  const [selectedDevice, setSelectedDevice] = useState("");
  const [devices, setDevices] = useState([]);
  const [rows, setRows] = useState([]);
  const [consolidatedRows, setConsolidatedRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [showCompanyModal, setShowCompanyModal] = useState(false);

  const runReport = async () => {
    setLoading(true);
    setError(null);
    setHasRun(true);
    
    try {
      // For tenant_id = 2 or 3 (SmartLPG), use dummy data
      if (user?.tenant_id === 2 || user?.tenant_id === 3) {
        console.log(`🔥 Generating utility billing data for tenant_id = ${user?.tenant_id}`);
        
        const isSmartLPG = user?.tenant_id === 3;
        
        if (isSmartLPG) {
          // For SmartLPG tenant, use same gas consumption calculation as Energy Dashboard
          const { fetchSmartLPGDataForDashboard, calculateGasConsumption } = await import("../services/smartLPGDataMapper.js");
          const smartLPGData = await fetchSmartLPGDataForDashboard();
          
          if (smartLPGData.success && smartLPGData.tekelekDevices) {
            // Calculate days between dates
            const fromDateObj = new Date(fromDate);
            const toDateObj = new Date(toDate);
            const daysDiff = Math.ceil((toDateObj - fromDateObj) / (1000 * 60 * 60 * 24));
            
            // Filter only active Tekelek devices (same as Energy Dashboard)
            const activeTekelekDevices = smartLPGData.tekelekDevices.filter(device => 
              device.is_active !== false && (device.current_status === 'online' || device.current_status === 'degraded')
            );
            
            console.log(`📊 [UTILITY] Using ${activeTekelekDevices.length} active Tekelek devices out of ${smartLPGData.tekelekDevices.length} total`);
            
            // Calculate gas consumption for all active Tekelek devices
            const gasData = activeTekelekDevices.map(device => {
              const consumption = calculateGasConsumption(device);
              // Scale monthly consumption to the report period
              const periodConsumption = (parseFloat(consumption.monthly_consumption_liters) / 30) * daysDiff;
              const periodCost = (parseFloat(consumption.monthly_cost_aed) / 30) * daysDiff;
              
              return {
                device_id: device.device_id,
                device_name: device.name,
                consumption: periodConsumption,
                cost: periodCost,
                currency: "AED",
                current_level_percent: consumption.current_level_percent
              };
            });
            
            if (viewMode === "per-device") {
              // Map to billing row format (show all devices, not just top 50)
              const mappedRows = gasData.sort((a, b) => b.consumption - a.consumption).map((device, idx) => {
                return {
                  tenant_id: 3,
                  tenant_name: "SmartLPG",
                  device_id: device.device_id,
                  device_external_id: device.device_id,
                  device_name: device.device_name,
                  utility_kind: "gas",
                  index_key: `gas_consumption_${idx}`,
                  period_start: fromDate,
                  period_end: toDate,
                  start_index: null,
                  end_index: null,
                  consumption: Math.round(device.consumption * 100) / 100,
                  unit: "L",
                  rate_per_unit: 3, // 3 AED per litre
                  currency: "AED",
                  amount: Math.round(device.cost * 100) / 100,
                  current_level_percent: device.current_level_percent,
                };
              });
              
              setRows(mappedRows);
              setConsolidatedRows([]);
            } else {
              // Consolidated view - only gas
              const totalConsumption = gasData.reduce((sum, d) => sum + d.consumption, 0);
              const totalCost = gasData.reduce((sum, d) => sum + d.cost, 0);
              
              const consolidatedRows = [
                {
                  tenant_id: 3,
                  tenant_name: "SmartLPG",
                  utility_kind: "gas",
                  period_start: fromDate,
                  period_end: toDate,
                  total_consumption: Math.round(totalConsumption * 100) / 100,
                  unit: "L",
                  rate_per_unit: 3, // 3 AED per litre
                  total_amount: Math.round(totalCost * 100) / 100,
                  total_cost: Math.round(totalCost * 100) / 100,
                  currency: "AED",
                  device_count: gasData.length, // Active devices count
                }
              ];
              
              setConsolidatedRows(consolidatedRows);
              setRows([]);
            }
            
            setLoading(false);
            return;
          }
        }
        
        // For tenant_id = 2, use dummy data
        // Calculate days between dates
        const fromDateObj = new Date(fromDate);
        const toDateObj = new Date(toDate);
        const daysDiff = Math.ceil((toDateObj - fromDateObj) / (1000 * 60 * 60 * 24));
        const hours = daysDiff * 24;
        
        // Generate dummy devices if needed
        const dummyDeviceCount = 2000;
        const dummyDevices = Array.from({ length: dummyDeviceCount }, (_, i) => ({
          device_id: `device_${i + 1}`,
          name: `Device ${i + 1}`,
        }));
        
        if (viewMode === "per-device") {
          // Generate dummy per-device billing data
          const { generateDummyEnergyData } = await import("../utils/dummyData.js");
          
          // If specific device selected, filter to just that device
          let devicesToUse = dummyDevices;
          if (selectedDevice && selectedDevice !== "") {
            devicesToUse = dummyDevices.filter(d => d.device_id === selectedDevice);
            console.log(`📊 Filtering to device: ${selectedDevice}`, devicesToUse);
          }
          
          const dummyEnergy = generateDummyEnergyData(devicesToUse, hours);
          
          // Store full totals for summary (matching energy dashboard)
          const fullTotalConsumption = dummyEnergy.summary.total_consumption_kwh;
          const fullTotalCost = dummyEnergy.summary.total_cost;
          
          // Map to billing row format (show top 50 devices, but totals use full data)
          const mappedRows = dummyEnergy.topConsumers.slice(0, selectedDevice ? 1 : 50).map((device, idx) => {
            const consumption = device.consumption || device.total_kwh || 0;
            const cost = device.cost || consumption * 0.5;
            return {
              tenant_id: user?.tenant_id || 2,
              tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
              device_id: device.device_id,
              device_external_id: device.device_id,
              device_name: device.device_name,
              utility_kind: device.utility_kind || "electricity",
              index_key: `energy_consumption_${idx}`,
              period_start: fromDate,
              period_end: toDate,
              start_index: null,
              end_index: null,
              consumption: Math.round(consumption * 100) / 100,
              unit: "kWh",
              rate_per_unit: consumption > 0 ? Math.round((cost / consumption) * 100) / 100 : 0.5,
              currency: "SAR",
              amount: Math.round(cost * 100) / 100,
              // Store full totals for summary calculation
              _fullTotalConsumption: fullTotalConsumption,
              _fullTotalCost: fullTotalCost,
            };
          });
          
          setRows(mappedRows);
          setConsolidatedRows([]);
        } else {
          // Generate dummy consolidated billing data
          const { generateDummyEnergyData } = await import("../utils/dummyData.js");
          const dummyEnergy = generateDummyEnergyData(dummyDevices, hours);
          
          console.log(`📊 Generating consolidated report, total devices: ${dummyDeviceCount}`);
          
          // Use same totals as energy dashboard for consistency
          const electricityConsumption = dummyEnergy.summary.total_consumption_kwh * 0.6;
          const gasConsumption = dummyEnergy.summary.total_consumption_kwh * 0.25;
          const waterConsumption = dummyEnergy.summary.total_consumption_kwh * 0.15;
          const electricityCost = dummyEnergy.summary.total_cost * 0.65;
          const gasCost = dummyEnergy.summary.total_cost * 0.20;
          const waterCost = dummyEnergy.summary.total_cost * 0.15;
          
          const consolidatedRows = [
            {
              tenant_id: user?.tenant_id || 2,
              tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
              utility_kind: "electricity",
              period_start: fromDate,
              period_end: toDate,
              total_consumption: Math.round(electricityConsumption * 100) / 100,
              unit: "kWh",
              total_cost: Math.round(electricityCost * 100) / 100,
              currency: "SAR",
              device_count: dummyDeviceCount,
            },
            {
              tenant_id: user?.tenant_id || 2,
              tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
              utility_kind: "gas",
              period_start: fromDate,
              period_end: toDate,
              total_consumption: Math.round(gasConsumption * 100) / 100,
              unit: "kWh",
              total_cost: Math.round(gasCost * 100) / 100,
              currency: "SAR",
              device_count: dummyDeviceCount,
            },
            {
              tenant_id: user?.tenant_id || 2,
              tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
              utility_kind: "water",
              period_start: fromDate,
              period_end: toDate,
              total_consumption: Math.round(waterConsumption * 100) / 100,
              unit: "m³",
              total_cost: Math.round(waterCost * 100) / 100,
              currency: "SAR",
              device_count: dummyDeviceCount,
            },
          ];
          
          setConsolidatedRows(consolidatedRows);
          setRows([]);
        }
        
        setLoading(false);
        return;
      }
      
      // For other tenants, use backend API
      if (viewMode === "per-device") {
        // Use all-devices energy aggregation as the billing source so that
        // any device publishing energy_consumption_w (and similar fields)
        // contributes to the report, not just traditional utility meters.
        
        // Add 1 day to toDate since backend uses exclusive end date (< period_end)
        const toDateObj = new Date(toDate);
        toDateObj.setDate(toDateObj.getDate() + 1);
        const toDateInclusive = toDateObj.toISOString().slice(0, 10);
        
        const energyResp = await api.get("/admin/utility/energy/all-devices", {
          params: {
            from_date: fromDate,
            to_date: toDateInclusive,
          },
        });

        const energyData = Array.isArray(energyResp.data) ? energyResp.data : [];

        // Filter out placeholder currency entry
        const realEnergy = energyData.filter(
          (item) =>
            item.device_id !== 0 &&
            item.device_external_id !== "__currency_placeholder__"
        );

        // Map energy aggregation shape → per-device billing row shape
        const mappedRows = realEnergy.map((item) => ({
          tenant_id: null,
          tenant_name: "",
          device_id: item.device_id,
          device_external_id: item.device_external_id,
          device_name: item.device_name,
          utility_kind: "electricity",
          index_key: item.power_field,
          period_start: item.period_start,
          period_end: item.period_end,
          start_index: null,
          end_index: null,
          // Use kWh as "consumption" and cost from backend
          consumption: item.total_energy_kwh,
          unit: "kWh",
          rate_per_unit:
            item.total_energy_kwh > 0
              ? item.cost / item.total_energy_kwh
              : null,
          currency: item.currency || "USD",
          amount: item.cost,
        }));

        setRows(mappedRows);
        setConsolidatedRows([]);
      } else {
        // Add 1 day to toDate since backend uses exclusive end date (< period_end)
        const toDateObj = new Date(toDate);
        toDateObj.setDate(toDateObj.getDate() + 1);
        const toDateInclusive = toDateObj.toISOString().slice(0, 10);
        
        const allUtilities = ["electricity", "gas", "water"];
        const allResults = [];
        
        for (const utility of allUtilities) {
          try {
            const response = await api.get("/admin/utility/consumption/consolidated", {
              params: {
                utility_kind: utility,
                from_date: fromDate,
                to_date: toDateInclusive,
              },
            });
            allResults.push(...(response.data || []));
          } catch (err) {
            console.warn(`No data for ${utility}:`, err.message);
          }
        }
        
        setConsolidatedRows(allResults);
        setRows([]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load utility consumption");
      setRows([]);
      setConsolidatedRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDevices();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const loadDevices = async () => {
    try {
      const response = await api.get("/admin/devices");
      // Extract devices array from paginated response
      const devicesData = response.data?.devices || (Array.isArray(response.data) ? response.data : []);
      setDevices(devicesData);
    } catch (err) {
      console.error("Failed to load devices:", err);
      setDevices([]); // Ensure devices is always an array
    }
  };
  
  // Ensure devices is always an array
  const safeDevices = useMemo(() => {
    try {
      if (!devices) return [];
      if (Array.isArray(devices)) return devices;
      if (devices?.devices && Array.isArray(devices.devices)) return devices.devices;
      return [];
    } catch (e) {
      console.error('Error computing safeDevices:', e);
      return [];
    }
  }, [devices]);

  const getRelevantDevices = () => {
    // For per-device reports, show all devices so users can select any device
    // The backend will filter based on which devices have utility billing data
    if (viewMode === "per-device") {
      return safeDevices;
    }
    
    // For consolidated reports, filter by device type if needed
    return safeDevices.filter((device) => {
      const deviceTypeName = (device.device_type || "").toLowerCase();
      
      if (utilityKind === "electricity") {
        return deviceTypeName.includes("comcore") || deviceTypeName.includes("ami") || deviceTypeName.includes("dlms") || deviceTypeName.includes("electricity") || deviceTypeName.includes("meter");
      } else if (utilityKind === "gas") {
        return deviceTypeName.includes("lpg") || deviceTypeName.includes("gas");
      } else if (utilityKind === "water") {
        return deviceTypeName.includes("water") || deviceTypeName.includes("meter");
      }
      
      return false;
    });
  };

  if (!isTenantAdmin) {
    return (
      <div className="page page--centered">
        <Icon name="alert" size={64} className="text-error" />
        <h2>Access Denied</h2>
        <p className="text-muted">This page is only available to tenant users.</p>
      </div>
    );
  }

  // For tenant_id = 2, use full totals from energy dashboard (not just visible rows)
  const totalConsumption = viewMode === "per-device"
    ? (rows[0]?._fullTotalConsumption ?? rows.map((r) => r.consumption ?? 0).reduce((sum, v) => sum + v, 0))
    : consolidatedRows.map((r) => r.total_consumption ?? 0).reduce((sum, v) => sum + v, 0);

  const totalAmount = viewMode === "per-device"
    ? (rows[0]?._fullTotalCost ?? rows.map((r) => r.amount ?? 0).reduce((sum, v) => sum + v, 0))
    : consolidatedRows.map((r) => r.total_cost ?? 0).reduce((sum, v) => sum + v, 0);

  const deviceCount = viewMode === "per-device"
    ? rows.length
    : consolidatedRows.reduce((sum, r) => sum + (r.device_count || 0), 0);

  const currency = (viewMode === "per-device" ? rows[0]?.currency : consolidatedRows[0]?.currency) || "SAR";

  // When using all-devices energy aggregation, there is no index-style
  // start/end reading, only total kWh. Detect that and hide Start/End.
  const hideIndexColumns =
    viewMode === "per-device" &&
    rows.length > 0 &&
    rows[0]?.start_index == null &&
    rows[0]?.end_index == null;

  const handleTabChange = (newTab) => {
    setViewMode(newTab);
    setHasRun(false);
    setError(null);
  };

  const handleDownloadPdf = async () => {
    setError(null);
    setDownloading(true);
    
    try {
      // For SmartLPG tenant (tenant_id = 3), use client-side PDF generation
      if (user?.tenant_id === 3) {
        let reportData;
        
        if (viewMode === "per-device") {
          // Prepare per-device report data
          reportData = preparePerDeviceReportData(rows, fromDate, toDate);
        } else {
          // Prepare consolidated report data
          reportData = prepareConsolidatedReportData(consolidatedRows, fromDate, toDate);
        }
        
        // Generate and open PDF in new window
        generateBillingReport(reportData);
        setDownloading(false);
        return;
      }
      
      // For other tenants, use backend PDF generation
      // Add 1 day to toDate since backend uses exclusive end date (< period_end)
      const toDateObj = new Date(toDate);
      toDateObj.setDate(toDateObj.getDate() + 1);
      const toDateInclusive = toDateObj.toISOString().slice(0, 10);
      
      let endpoint, params, filename;
      
      if (viewMode === "consolidated") {
        endpoint = "/admin/utility/reports/all-utilities-billing.pdf";
        params = {
          from_date: fromDate,
          to_date: toDateInclusive,
          show_device_breakdown: true,
        };
        filename = `all_utilities_billing_${fromDate}_${toDate}.pdf`;
      } else {
        endpoint = "/admin/utility/reports/billing.pdf";
        params = {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDateInclusive,
        };
        
        if (selectedDevice) {
          params.device_id = parseInt(selectedDevice);
        }
        
        filename = `utility_billing_${utilityKind}_${fromDate}_${toDate}.pdf`;
      }
      
      const response = await api.get(endpoint, {
        params,
        responseType: "blob",
      });

      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to download PDF report. Please try again.",
      );
    } finally {
      setDownloading(false);
    }
  };

  const tabs = [
    {
      id: "per-device",
      label: "Per-Device Report",
      content: (
        <>
          {/* Filters Card */}
          <div className="card">
            <div className="card__header">
              <h3 className="card__title">
                <Icon name="filter" size={20} /> Report Filters
              </h3>
            </div>
            <div className="card__body">
              <div className="form">
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">
                      <Icon name={UTILITY_KINDS.find(u => u.value === utilityKind)?.icon || "zap"} size={16} />
                      Utility Type
                    </label>
                    <select
                      className="form-select"
                      value={utilityKind}
                      onChange={(e) => {
                        setUtilityKind(e.target.value);
                        setSelectedDevice("");
                        setHasRun(false);
                      }}
                    >
                      {UTILITY_KINDS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      <Icon name="devices" size={16} />
                      Device (Optional)
                    </label>
                    <select
                      className="form-select"
                      value={selectedDevice}
                      onChange={(e) => setSelectedDevice(e.target.value)}
                    >
                      <option value="">All {utilityKind.charAt(0).toUpperCase() + utilityKind.slice(1)} Devices</option>
                      {(user?.tenant_id === 2 || user?.tenant_id === 3) ? (
                        // For Firebase tenants, show dummy device options
                        Array.from({ length: 50 }, (_, i) => (
                          <option key={`device_${i + 1}`} value={`device_${i + 1}`}>
                            Device {i + 1}
                          </option>
                        ))
                      ) : (
                        getRelevantDevices().map((device) => (
                          <option key={device.id} value={device.id}>
                            {device.name || device.device_id}
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      <Icon name="calendar" size={16} />
                      From Date
                    </label>
                    <input
                      className="form-input"
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      <Icon name="calendar" size={16} />
                      To Date
                    </label>
                    <input
                      className="form-input"
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-actions">
                  <button 
                    className="btn btn--secondary" 
                    onClick={runReport} 
                    disabled={loading || downloading}
                  >
                    <Icon name="activity" size={18} />
                    {loading ? "Running..." : "Run Report"}
                  </button>
                  <button 
                    className="btn btn--primary" 
                    onClick={handleDownloadPdf} 
                    disabled={loading || downloading || rows.length === 0}
                  >
                    <Icon name="download" size={18} />
                    {downloading ? "Downloading..." : "Download PDF"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
              {error}
            </div>
          )}

          {/* Summary Metrics (only show when data is loaded) */}
          {!loading && rows.length > 0 && (
            <div
              className="metrics-grid"
              style={{ gridTemplateColumns: "repeat(4, 1fr)", marginBottom: "var(--space-6)" }}
            >
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Devices</span>
                  <Icon name="devices" size="lg" />
                </div>
                <div className="metric-card__value">{deviceCount}</div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Consumption</span>
                  <Icon name={UTILITY_KINDS.find(u => u.value === utilityKind)?.icon || "zap"} size="lg" />
                </div>
                <div className="metric-card__value">
                  {totalConsumption.toFixed(2)} <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}>{rows[0]?.unit}</span>
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Amount</span>
                  <Icon name="utility" size="lg" />
                </div>
                <div className="metric-card__value text-success">
                  {currency} {totalAmount.toFixed(2)}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Date Range</span>
                  <Icon name="calendar" size="lg" />
                </div>
                <div className="metric-card__value" style={{ fontSize: "var(--font-size-sm)" }}>
                  {new Date(fromDate).toLocaleDateString()} - {new Date(toDate).toLocaleDateString()}
                </div>
              </div>
            </div>
          )}

          {/* Results Card */}
          <div className="card">
            <div className="card__header">
              <h3 className="card__title">
                <Icon name="file" size={20} /> Consumption Report
              </h3>
            </div>
            <div className="card__body">
              {!hasRun && !loading && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="filter" size={48} style={{ opacity: 0.3 }} />
                  <h3 style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--font-size-lg)" }}>
                    Ready to Generate Report
                  </h3>
                  <p className="text-muted" style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    Select your filters and click "Run Report" to view consumption data
                  </p>
                  <button 
                    className="btn btn--primary" 
                    onClick={runReport}
                    style={{ marginTop: "var(--space-3)" }}
                  >
                    <Icon name="activity" size={18} />
                    Run Report
                  </button>
                </div>
              )}
              
              {loading && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="activity" size={48} style={{ opacity: 0.3 }} />
                  <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)" }}>
                    Analyzing consumption data...
                  </p>
                </div>
              )}
              
              {hasRun && !loading && rows.length === 0 && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="inbox" size={48} style={{ opacity: 0.3 }} />
                  <h3 style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--font-size-lg)" }}>
                    No Consumption Data Found
                  </h3>
                  <p className="text-muted" style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    {utilityKind === "water" 
                      ? "No water meters are currently configured."
                      : "No consumption data found for the selected period."}
                  </p>
                </div>
              )}
              
              {!loading && rows.length > 0 && (
                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Tenant</th>
                        <th>Device</th>
                        <th>Index Key</th>
                        {!hideIndexColumns && <th>Start</th>}
                        {!hideIndexColumns && <th>End</th>}
                        <th>Consumption</th>
                        <th>Unit</th>
                        <th>Rate</th>
                        <th>Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={`${row.device_id}-${row.utility_kind}`}>
                          <td>{row.tenant_name}</td>
                          <td>
                            <div style={{ fontWeight: "var(--font-weight-semibold)" }}>
                              {row.device_name || row.device_external_id}
                            </div>
                            {row.device_name && (
                              <div className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                                {row.device_external_id}
                              </div>
                            )}
                          </td>
                          <td>
                            <code className="badge badge--neutral" style={{ fontSize: "var(--font-size-xs)" }}>
                              {row.index_key}
                            </code>
                          </td>
                          {!hideIndexColumns && (
                            <td>{row.start_index != null ? row.start_index.toFixed(2) : "—"}</td>
                          )}
                          {!hideIndexColumns && (
                            <td>{row.end_index != null ? row.end_index.toFixed(2) : "—"}</td>
                          )}
                          <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                            {row.consumption != null ? row.consumption.toFixed(2) : "—"}
                          </td>
                          <td><span className="badge badge--info">{row.unit}</span></td>
                          <td className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                            {row.rate_per_unit != null
                              ? `${row.currency} ${row.rate_per_unit.toFixed(4)}`
                              : "—"}
                          </td>
                          <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)", color: "var(--color-success-500)" }}>
                            {row.amount != null
                              ? `${row.currency} ${row.amount.toFixed(2)}`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      ),
    },
    {
      id: "consolidated",
      label: "Consolidated Report",
      content: (
        <>
          {/* Filters Card */}
          <div className="card">
            <div className="card__header">
              <h3 className="card__title">
                <Icon name="filter" size={20} /> Report Filters
              </h3>
            </div>
            <div className="card__body">
              <div className="form">
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label" htmlFor="fromDate">
                      <Icon name="calendar" size={16} />
                      <span>From Date</span>
                    </label>
                    <input
                      id="fromDate"
                      className="form-input"
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label" htmlFor="toDate">
                      <Icon name="calendar" size={16} />
                      <span>To Date</span>
                    </label>
                    <input
                      id="toDate"
                      className="form-input"
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-actions">
                  <button 
                    className="btn btn--secondary" 
                    onClick={runReport} 
                    disabled={loading || downloading}
                  >
                    <Icon name="activity" size={18} />
                    {loading ? "Running..." : "Run Report"}
                  </button>
                  <button 
                    className="btn btn--primary" 
                    onClick={handleDownloadPdf} 
                    disabled={loading || downloading || consolidatedRows.length === 0}
                  >
                    <Icon name="download" size={18} />
                    {downloading ? "Downloading..." : "Download PDF"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
              {error}
            </div>
          )}

          {/* Summary Metrics (only show when data is loaded) */}
          {!loading && consolidatedRows.length > 0 && (
            <div className="metrics-grid">
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Devices</span>
                  <Icon name="devices" size="lg" />
                </div>
                <div className="metric-card__value">{deviceCount}</div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Consumption</span>
                  <Icon name="trending" size="lg" />
                </div>
                <div className="metric-card__value">
                  {totalConsumption.toFixed(2)}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Total Amount</span>
                  <Icon name="utility" size="lg" />
                </div>
                <div className="metric-card__value text-success">
                  {currency} {totalAmount.toFixed(2)}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Utility Types</span>
                  <Icon name="database" size="lg" />
                </div>
                <div className="metric-card__value">
                  {[...new Set(consolidatedRows.map(r => r.utility_kind))].length}
                </div>
              </div>
            </div>
          )}

          {/* Results Card */}
          <div className="card">
            <div className="card__header">
              <h3 className="card__title">
                <Icon name="file" size={20} /> Consolidated Tenant Report
              </h3>
            </div>
            <div className="card__body">
              {!hasRun && !loading && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="filter" size={48} style={{ opacity: 0.3 }} />
                  <h3 style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--font-size-lg)" }}>
                    Ready to Generate Report
                  </h3>
                  <p className="text-muted" style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    Select date range and click "Run Report" to view consolidated data
                  </p>
                  <button 
                    className="btn btn--primary" 
                    onClick={runReport}
                    style={{ marginTop: "var(--space-3)" }}
                  >
                    <Icon name="activity" size={18} />
                    Run Report
                  </button>
                </div>
              )}
              
              {loading && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="activity" size={48} style={{ opacity: 0.3 }} />
                  <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)" }}>
                    Consolidating consumption data across all utilities...
                  </p>
                </div>
              )}
              
              {hasRun && !loading && consolidatedRows.length === 0 && (
                <div className="page--centered" style={{ padding: "var(--space-8) 0" }}>
                  <Icon name="inbox" size={48} style={{ opacity: 0.3 }} />
                  <h3 style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--font-size-lg)" }}>
                    No Consumption Data Found
                  </h3>
                  <p className="text-muted" style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    No consumption data found for the selected period.
                  </p>
                </div>
              )}
              
              {!loading && consolidatedRows.length > 0 && (
                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Tenant</th>
                        <th>Utility</th>
                        <th>Devices</th>
                        <th>Consumption</th>
                        <th>Unit</th>
                        <th>Rate</th>
                        <th>Total Amount</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {consolidatedRows.map((row, index) => {
                        const utilityInfo = UTILITY_KINDS.find(u => u.value === row.utility_kind);
                        return (
                          <tr key={`${row.tenant_id}-${row.utility_kind}-${index}`}>
                            <td style={{ fontWeight: "var(--font-weight-semibold)" }}>{row.tenant_name}</td>
                            <td>
                              <span className="badge" style={{ backgroundColor: `${utilityInfo?.color}20`, color: utilityInfo?.color, borderColor: utilityInfo?.color }}>
                                <Icon name={utilityInfo?.icon || "zap"} size={14} />
                                {row.utility_kind}
                              </span>
                            </td>
                            <td style={{ textAlign: "center", fontWeight: "var(--font-weight-semibold)" }}>
                              {row.device_count}
                            </td>
                            <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                              {row.total_consumption.toFixed(2)}
                            </td>
                            <td><span className="badge badge--info">{row.unit}</span></td>
                            <td className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                              {row.currency} {row.rate_per_unit.toFixed(4)}
                            </td>
                            <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)", color: "var(--color-success-text)" }}>
                              {row.currency} {row.total_amount.toFixed(2)}
                            </td>
                            <td>
                              <Collapsible title={
                                <span style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                                  <Icon name="eye" size={16} />
                                  View Devices ({row.devices.length})
                                </span>
                              }>
                                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-3)" }}>
                                  {row.devices.map((device) => (
                                    <div 
                                      key={device.device_id} 
                                      style={{ 
                                        padding: "var(--space-3)", 
                                        backgroundColor: "var(--color-bg-secondary)", 
                                        borderRadius: "var(--radius-md)",
                                        border: "1px solid var(--color-border)"
                                      }}
                                    >
                                      <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: "var(--font-size-sm)", marginBottom: "var(--space-2)" }}>
                                        <Icon name="devices" size={14} />
                                        {device.device_name || device.device_external_id}
                                      </div>
                                      <div className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                                        Consumption: <strong>{device.consumption != null ? device.consumption.toFixed(2) : "—"}</strong> {row.unit}
                                        {" | "}
                                        Amount: <strong style={{ color: "var(--color-success-text)" }}>
                                          {device.amount != null ? `${row.currency} ${device.amount.toFixed(2)}` : "—"}
                                        </strong>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </Collapsible>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </>
      ),
    },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Utility Billing & Consumption</h1>
          <p className="page-header__subtitle">
            Generate reports and invoices for utility consumption across all devices
          </p>
        </div>
        {user?.tenant_id === 3 && (
          <div className="page-header__actions">
            <button 
              className="btn btn--secondary"
              onClick={() => setShowCompanyModal(true)}
            >
              <Icon name="settings" size={18} />
              Company Details
            </button>
          </div>
        )}
      </div>

      <Breadcrumbs items={[{ label: "Utility Billing", path: "/utility/billing" }]} />

      <Tabs tabs={tabs} defaultTab={viewMode} onChange={handleTabChange} />
      
      {/* Company Details Modal */}
      <CompanyDetailsModal 
        isOpen={showCompanyModal} 
        onClose={() => setShowCompanyModal(false)} 
      />
    </div>
  );
}
