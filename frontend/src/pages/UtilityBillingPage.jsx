import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Tabs from "../components/Tabs.jsx";
import Collapsible from "../components/Collapsible.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";

const UTILITY_KINDS = [
  { value: "electricity", label: "Electricity", icon: "zap", color: "#facc15" },
  { value: "gas", label: "Gas", icon: "flame", color: "#f97316" },
  { value: "water", label: "Water", icon: "droplet", color: "#3b82f6" },
];

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

export default function UtilityBillingPage() {
  const { token, isTenantAdmin } = useAuth();
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

  const runReport = async () => {
    setLoading(true);
    setError(null);
    setHasRun(true);
    
    try {
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
      setDevices(response.data || []);
    } catch (err) {
      console.error("Failed to load devices:", err);
    }
  };

  const getRelevantDevices = () => {
    return devices.filter((device) => {
      const deviceTypeName = device.device_type || "";
      
      if (utilityKind === "electricity") {
        return deviceTypeName.includes("Comcore AMI") || deviceTypeName.includes("Comcore DLMS");
      } else if (utilityKind === "gas") {
        return deviceTypeName.includes("LPG");
      } else if (utilityKind === "water") {
        return deviceTypeName.includes("Water");
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

  const totalAmount = viewMode === "per-device"
    ? rows.map((r) => r.amount ?? 0).reduce((sum, v) => sum + v, 0)
    : consolidatedRows.map((r) => r.total_amount ?? 0).reduce((sum, v) => sum + v, 0);

  const totalConsumption = viewMode === "per-device"
    ? rows.map((r) => r.consumption ?? 0).reduce((sum, v) => sum + v, 0)
    : consolidatedRows.map((r) => r.total_consumption ?? 0).reduce((sum, v) => sum + v, 0);

  const deviceCount = viewMode === "per-device"
    ? rows.length
    : consolidatedRows.reduce((sum, r) => sum + (r.device_count || 0), 0);

  const currency = (viewMode === "per-device" ? rows[0]?.currency : consolidatedRows[0]?.currency) || "USD";

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
                      {getRelevantDevices().map((device) => (
                        <option key={device.id} value={device.id}>
                          {device.name || device.device_id}
                        </option>
                      ))}
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
      </div>

      <Breadcrumbs items={[{ label: "Utility Billing", path: "/utility/billing" }]} />

      <Tabs tabs={tabs} defaultTab={viewMode} onChange={handleTabChange} />
    </div>
  );
}
