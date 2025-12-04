import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const UTILITY_KINDS = [
  { value: "electricity", label: "Electricity" },
  { value: "gas", label: "Gas" },
  { value: "water", label: "Water" },
];

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

export default function UtilityBillingPage() {
  const { token } = useAuth();
  const api = createApiClient(token);

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const [utilityKind, setUtilityKind] = useState("electricity");
  const [fromDate, setFromDate] = useState(formatDateInput(yesterday));
  const [toDate, setToDate] = useState(formatDateInput(today));
  const [viewMode, setViewMode] = useState("per-device"); // "per-device" or "consolidated"
  const [selectedDevice, setSelectedDevice] = useState(""); // "" means all devices
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
        
        // Add optional device filter
        if (selectedDevice) {
          params.device_id = parseInt(selectedDevice);
        }
        
        // Fetch per-device consumption
        const response = await api.get("/admin/utility/consumption/preview", { params });
        setRows(response.data || []);
        setConsolidatedRows([]);
      } else {
        // Fetch consolidated (per-tenant) consumption for ALL utility types
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
            // Silently skip utilities with no data
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
    // Load devices for filters
    loadDevices();
    // Auto-run initial report
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

  // Filter devices based on utility type and device type
  const getRelevantDevices = () => {
    return devices.filter((device) => {
      const deviceTypeName = device.device_type?.name || "";
      
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

  const totalAmount = viewMode === "per-device"
    ? rows.map((r) => r.amount ?? 0).reduce((sum, v) => sum + v, 0)
    : consolidatedRows.map((r) => r.total_amount ?? 0).reduce((sum, v) => sum + v, 0);

  const handleDownloadPdf = async () => {
    setError(null);
    setDownloading(true);
    
    try {
      let endpoint, params, filename;
      
      if (viewMode === "consolidated") {
        // For consolidated view, use the all-utilities endpoint
        endpoint = "/admin/utility/reports/all-utilities-billing.pdf";
        params = {
          from_date: fromDate,
          to_date: toDate,
          show_device_breakdown: true,
        };
        filename = `all_utilities_billing_${fromDate}_${toDate}.pdf`;
      } else {
        // For per-device view, use the single-utility endpoint
        endpoint = "/admin/utility/reports/billing.pdf";
        params = {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDate,
        };
        
        // Add optional device filter
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

  return (
    <div className="page">
      <div className="section-header">
        <h2>Utility Billing & Consumption</h2>
      </div>

      <section className="card" id="utility-billing">
        <h3 style={{ marginTop: 0, marginBottom: "1.25rem", fontSize: "1.125rem", fontWeight: 600, color: "#334155" }}>
          Report Filters
        </h3>
        
        {/* View Mode Toggle */}
        <div className="form-group" style={{ marginBottom: "1.5rem" }}>
          <label style={{ display: "block", marginBottom: "0.5rem", fontWeight: 500 }}>Report Type</label>
          <div style={{ display: "flex", gap: "1rem" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input
                type="radio"
                value="per-device"
                checked={viewMode === "per-device"}
                onChange={(e) => setViewMode(e.target.value)}
              />
              <span>Per-Device (Detailed)</span>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
              <input
                type="radio"
                value="consolidated"
                checked={viewMode === "consolidated"}
                onChange={(e) => setViewMode(e.target.value)}
              />
              <span>Consolidated (Per-Tenant Summary)</span>
            </label>
          </div>
        </div>
        
        <div className="form-grid">
          {viewMode === "per-device" && (
            <>
              <div className="form-group">
                <label htmlFor="utilityKind">Utility Type</label>
                <select
                  id="utilityKind"
                  value={utilityKind}
                  onChange={(e) => {
                    setUtilityKind(e.target.value);
                    setSelectedDevice(""); // Reset device when utility type changes
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
                <label htmlFor="device">Device (Optional)</label>
                <select
                  id="device"
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
            </>
          )}

          <div className="form-group">
            <label htmlFor="fromDate">From Date</label>
            <input
              id="fromDate"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="toDate">To Date</label>
            <input
              id="toDate"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
            />
          </div>
        </div>

        {error && <p className="error-message">{error}</p>}

        <div className="form-actions">
          <button
            type="button"
            onClick={runReport}
            disabled={loading || downloading}
          >
            {loading ? "⏳ Running Report..." : "📊 Run Report"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={handleDownloadPdf}
            disabled={loading || downloading}
          >
            {downloading ? "📄 Downloading..." : "📄 Download PDF"}
          </button>
        </div>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0, marginBottom: "1.25rem", fontSize: "1.125rem", fontWeight: 600, color: "#334155" }}>
          {viewMode === "per-device" ? "Per-Device Consumption Report" : "Consolidated Tenant Report"}
        </h3>
        <div className="table-wrapper">
          {loading && (
            <p className="muted">Loading consumption data...</p>
          )}
          {!loading && viewMode === "per-device" && rows.length === 0 && (
            <div style={{ padding: "2rem", textAlign: "center" }}>
              <p className="muted" style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>
                No consumption data found for the selected period and utility type.
              </p>
              {utilityKind === "water" && (
                <p className="muted" style={{ fontSize: "0.9rem", color: "#94a3b8" }}>
                  💡 No water meters are currently configured in the system.
                </p>
              )}
            </div>
          )}
          {!loading && viewMode === "consolidated" && consolidatedRows.length === 0 && (
            <div style={{ padding: "2rem", textAlign: "center" }}>
              <p className="muted" style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>
                No consumption data found for the selected period and utility type.
              </p>
            </div>
          )}
          
          {/* Per-Device Table */}
          {!loading && viewMode === "per-device" && rows.length > 0 && (
            <>
              <table>
                <thead>
                  <tr>
                    <th>Tenant</th>
                    <th>Device</th>
                    <th>Index Key</th>
                    <th>Start Index</th>
                    <th>End Index</th>
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
                        <div style={{ fontWeight: 500 }}>{row.device_name || row.device_external_id}</div>
                        {row.device_name && (
                          <div style={{ fontSize: "0.85rem", color: "#64748b" }}>{row.device_external_id}</div>
                        )}
                      </td>
                      <td style={{ fontSize: "0.875rem", color: "#64748b" }}>{row.index_key}</td>
                      <td>{row.start_index?.toFixed(2) ?? "—"}</td>
                      <td>{row.end_index?.toFixed(2) ?? "—"}</td>
                      <td style={{ fontWeight: 600 }}>
                        {row.consumption != null ? row.consumption.toFixed(2) : "—"}
                      </td>
                      <td>{row.unit}</td>
                      <td style={{ fontSize: "0.875rem" }}>
                        {row.rate_per_unit != null
                          ? `${row.currency} ${row.rate_per_unit.toFixed(4)}`
                          : "—"}
                      </td>
                      <td style={{ fontWeight: 600, color: "#0f172a" }}>
                        {row.amount != null
                          ? `${row.currency} ${row.amount.toFixed(2)}`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="section-footer">
                <p>
                  Total Amount:{" "}
                  <strong>
                    {rows[0]?.currency || "USD"} {totalAmount.toFixed(2)}
                  </strong>
                </p>
              </div>
            </>
          )}
          
          {/* Consolidated Table */}
          {!loading && viewMode === "consolidated" && consolidatedRows.length > 0 && (
            <>
              <table>
                <thead>
                  <tr>
                    <th>Tenant</th>
                    <th>Utility</th>
                    <th>Devices</th>
                    <th>Total Consumption</th>
                    <th>Unit</th>
                    <th>Rate</th>
                    <th>Total Amount</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {consolidatedRows.map((row, index) => (
                    <tr key={`${row.tenant_id}-${row.utility_kind}-${index}`}>
                      <td style={{ fontWeight: 600 }}>{row.tenant_name}</td>
                      <td style={{ 
                        textTransform: "capitalize", 
                        fontWeight: 500,
                        color: row.utility_kind === "electricity" ? "#f59e0b" : row.utility_kind === "gas" ? "#3b82f6" : "#10b981"
                      }}>
                        {row.utility_kind}
                      </td>
                      <td style={{ textAlign: "center" }}>{row.device_count}</td>
                      <td style={{ fontWeight: 600, fontSize: "1rem" }}>
                        {row.total_consumption.toFixed(2)}
                      </td>
                      <td>{row.unit}</td>
                      <td style={{ fontSize: "0.875rem" }}>
                        {row.currency} {row.rate_per_unit.toFixed(4)}
                      </td>
                      <td style={{ fontWeight: 600, color: "#0f172a", fontSize: "1.05rem" }}>
                        {row.currency} {row.total_amount.toFixed(2)}
                      </td>
                      <td>
                        <details style={{ cursor: "pointer" }}>
                          <summary style={{ color: "#3b82f6", fontWeight: 500 }}>
                            View Devices ({row.devices.length})
                          </summary>
                          <div style={{ marginTop: "0.75rem", paddingLeft: "1rem", borderLeft: "2px solid #e2e8f0" }}>
                            {row.devices.map((device) => (
                              <div key={device.device_id} style={{ padding: "0.5rem 0", borderBottom: "1px solid #f1f5f9" }}>
                                <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>
                                  {device.device_name || device.device_external_id}
                                </div>
                                <div style={{ fontSize: "0.8rem", color: "#64748b" }}>
                                  Consumption: {device.consumption != null ? device.consumption.toFixed(2) : "—"} | 
                                  Amount: {device.amount != null ? `${row.currency} ${device.amount.toFixed(2)}` : "—"}
                                </div>
                              </div>
                            ))}
                          </div>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="section-footer">
                <p>
                  Grand Total (All Utilities):{" "}
                  <strong>
                    {consolidatedRows[0]?.currency || "USD"} {totalAmount.toFixed(2)}
                  </strong>
                </p>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}


