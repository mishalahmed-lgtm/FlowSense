import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Tabs from "../components/Tabs.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Collapsible from "../components/Collapsible.jsx";

const UTILITY_KINDS = [
  { value: "electricity", label: "Electricity", icon: "⚡", color: "var(--color-warning-500)" },
  { value: "gas", label: "Gas", icon: "🔥", color: "var(--color-primary-500)" },
  { value: "water", label: "Water", icon: "💧", color: "var(--color-success-500)" },
];

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

export default function UtilityBillingPage() {
  const { token, isTenantAdmin } = useAuth();
  const api = createApiClient(token);

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const [utilityKind, setUtilityKind] = useState("electricity");
  const [fromDate, setFromDate] = useState(formatDateInput(yesterday));
  const [toDate, setToDate] = useState(formatDateInput(today));
  const [viewMode, setViewMode] = useState("per-device");
  const [selectedDevice, setSelectedDevice] = useState("");
  const [devices, setDevices] = useState([]);
  const [rows, setRows] = useState([]);
  const [consolidatedRows, setConsolidatedRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const runReport = async () => {
    setLoading(true);
    setError(null);
    
    try {
      if (viewMode === "per-device") {
        const params = {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDate,
        };
        
        if (selectedDevice) {
          params.device_id = parseInt(selectedDevice);
        }
        
        const response = await api.get("/admin/utility/consumption/preview", { params });
        setRows(response.data || []);
        setConsolidatedRows([]);
      } else {
        const allUtilities = ["electricity", "gas", "water"];
        const allResults = [];
        
        for (const utility of allUtilities) {
          try {
            const response = await api.get("/admin/utility/consumption/consolidated", {
              params: {
                utility_kind: utility,
                from_date: fromDate,
                to_date: toDate,
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
    runReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      // device.device_type is a string, not an object
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

  // Only tenant admins can access utility billing page
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }

  const totalAmount = viewMode === "per-device"
    ? rows.map((r) => r.amount ?? 0).reduce((sum, v) => sum + v, 0)
    : consolidatedRows.map((r) => r.total_amount ?? 0).reduce((sum, v) => sum + v, 0);

  const handleDownloadPdf = async () => {
    setError(null);
    setDownloading(true);
    
    try {
      let endpoint, params, filename;
      
      if (viewMode === "consolidated") {
        endpoint = "/admin/utility/reports/all-utilities-billing.pdf";
        params = {
          from_date: fromDate,
          to_date: toDate,
          show_device_breakdown: true,
        };
        filename = `all_utilities_billing_${fromDate}_${toDate}.pdf`;
      } else {
        endpoint = "/admin/utility/reports/billing.pdf";
        params = {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDate,
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
        <div>
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div className="card__header">
              <h3 className="card__title">Report Filters</h3>
            </div>
            <div className="card__body">
              <div className="form" style={{ gap: "var(--space-4)" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-4)" }}>
                  <div className="form-group">
                    <label className="form-label">Utility Type</label>
                    <select
                      className="form-select"
                      value={utilityKind}
                      onChange={(e) => {
                        setUtilityKind(e.target.value);
                        setSelectedDevice("");
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
                    <label className="form-label">Device (Optional)</label>
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
                    <label className="form-label">From Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">To Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                    />
                  </div>
                </div>

                <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
                  <button className="btn btn--secondary" onClick={runReport} disabled={loading || downloading}>
                    {loading ? "⏳ Running..." : "📊 Run Report"}
                  </button>
                  <button className="btn btn--primary" onClick={handleDownloadPdf} disabled={loading || downloading || rows.length === 0}>
                    {downloading ? "📄 Downloading..." : "📄 Download PDF"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="card" style={{ borderColor: "var(--color-error-500)", marginBottom: "var(--space-6)" }}>
              <p className="text-error">{error}</p>
            </div>
          )}

          <div className="card">
            <div className="card__header">
              <h3 className="card__title">Consumption Report</h3>
            </div>
            <div className="card__body">
              {loading && (
                <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                  <p className="text-muted">Loading consumption data...</p>
                </div>
              )}
              {!loading && rows.length === 0 && (
                <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                  <p className="text-muted">No consumption data found for the selected period.</p>
                  {utilityKind === "water" && (
                    <p className="text-muted" style={{ fontSize: "var(--font-size-sm)", marginTop: "var(--space-2)" }}>
                      💡 No water meters are currently configured.
                    </p>
                  )}
                </div>
              )}
              {!loading && rows.length > 0 && (
                <>
                  <div className="table-wrapper">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Tenant</th>
                          <th>Device</th>
                          <th>Index Key</th>
                          <th>Start</th>
                          <th>End</th>
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
                            <td><code style={{ fontSize: "var(--font-size-xs)" }}>{row.index_key}</code></td>
                            <td>{row.start_index?.toFixed(2) ?? "—"}</td>
                            <td>{row.end_index?.toFixed(2) ?? "—"}</td>
                            <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                              {row.consumption != null ? row.consumption.toFixed(2) : "—"}
                            </td>
                            <td>{row.unit}</td>
                            <td className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                              {row.rate_per_unit != null
                                ? `${row.currency} ${row.rate_per_unit.toFixed(4)}`
                                : "—"}
                            </td>
                            <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-base)" }}>
                              {row.amount != null
                                ? `${row.currency} ${row.amount.toFixed(2)}`
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="card__footer">
                    <p style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>
                      Total Amount: <strong>{rows[0]?.currency || "USD"} {totalAmount.toFixed(2)}</strong>
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "consolidated",
      label: "Consolidated Report",
      content: (
        <div>
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div className="card__header">
              <h3 className="card__title">Report Filters</h3>
            </div>
            <div className="card__body">
              <div className="form" style={{ gap: "var(--space-4)" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-4)" }}>
                  <div className="form-group">
                    <label className="form-label">From Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">To Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                    />
                  </div>
                </div>

                <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
                  <button className="btn btn--secondary" onClick={runReport} disabled={loading || downloading}>
                    {loading ? "⏳ Running..." : "📊 Run Report"}
                  </button>
                  <button className="btn btn--primary" onClick={handleDownloadPdf} disabled={loading || downloading || consolidatedRows.length === 0}>
                    {downloading ? "📄 Downloading..." : "📄 Download PDF"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="card" style={{ borderColor: "var(--color-error-500)", marginBottom: "var(--space-6)" }}>
              <p className="text-error">{error}</p>
            </div>
          )}

          <div className="card">
            <div className="card__header">
              <h3 className="card__title">Consolidated Tenant Report</h3>
            </div>
            <div className="card__body">
              {loading && (
                <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                  <p className="text-muted">Loading consumption data...</p>
                </div>
              )}
              {!loading && consolidatedRows.length === 0 && (
                <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                  <p className="text-muted">No consumption data found for the selected period.</p>
                </div>
              )}
              {!loading && consolidatedRows.length > 0 && (
                <>
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
                                <span className="badge" style={{ backgroundColor: `${utilityInfo?.color}20`, color: utilityInfo?.color }}>
                                  {utilityInfo?.icon} {row.utility_kind}
                                </span>
                              </td>
                              <td style={{ textAlign: "center" }}>{row.device_count}</td>
                              <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                                {row.total_consumption.toFixed(2)}
                              </td>
                              <td>{row.unit}</td>
                              <td className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                                {row.currency} {row.rate_per_unit.toFixed(4)}
                              </td>
                              <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)" }}>
                                {row.currency} {row.total_amount.toFixed(2)}
                              </td>
                              <td>
                                <Collapsible title={`View Devices (${row.devices.length})`}>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                                    {row.devices.map((device) => (
                                      <div key={device.device_id} style={{ padding: "var(--space-3)", backgroundColor: "var(--color-gray-50)", borderRadius: "var(--radius-md)" }}>
                                        <div style={{ fontWeight: "var(--font-weight-semibold)", fontSize: "var(--font-size-sm)" }}>
                                          {device.device_name || device.device_external_id}
                                        </div>
                                        <div className="text-muted" style={{ fontSize: "var(--font-size-xs)", marginTop: "var(--space-1)" }}>
                                          Consumption: {device.consumption != null ? device.consumption.toFixed(2) : "—"} {row.unit} | 
                                          Amount: {device.amount != null ? `${row.currency} ${device.amount.toFixed(2)}` : "—"}
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
                  <div className="card__footer">
                    <p style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>
                      Grand Total (All Utilities): <strong>{consolidatedRows[0]?.currency || "USD"} {totalAmount.toFixed(2)}</strong>
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Utility Billing", path: "/utility/billing" }]} />

      <div style={{ marginBottom: "var(--space-8)" }}>
        <h1 style={{ marginBottom: "var(--space-2)", fontSize: "var(--font-size-3xl)" }}>
          Utility Billing & Consumption
        </h1>
        <p className="text-muted">
          Generate reports and invoices for utility consumption across all devices
        </p>
      </div>

      <Tabs tabs={tabs} defaultTab={viewMode} onChange={setViewMode} />
    </div>
  );
}
