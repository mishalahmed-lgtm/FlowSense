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
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const runReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get("/admin/utility/consumption/preview", {
        params: {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDate,
        },
      });
      setRows(response.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load utility consumption");
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Auto-run initial report
    runReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalAmount = rows
    .map((r) => r.amount ?? 0)
    .reduce((sum, v) => sum + v, 0);

  const handleDownloadPdf = async () => {
    setError(null);
    setDownloading(true);
    try {
      const response = await api.get("/admin/utility/reports/billing.pdf", {
        params: {
          utility_kind: utilityKind,
          from_date: fromDate,
          to_date: toDate,
        },
        responseType: "blob",
      });

      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `utility_billing_${utilityKind}_${fromDate}_${toDate}.pdf`;
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
        <div className="form-grid">
          <div className="form-group">
            <label htmlFor="utilityKind">Utility Type</label>
            <select
              id="utilityKind"
              value={utilityKind}
              onChange={(e) => setUtilityKind(e.target.value)}
            >
              {UTILITY_KINDS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

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
          Consumption Report
        </h3>
        <div className="table-wrapper">
          {rows.length === 0 && loading && (
            <p className="muted">Loading consumption data...</p>
          )}
          {rows.length === 0 && !loading && (
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
            {rows.length > 0 && (
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
          </div>
        </section>
      )}
    </div>
  );
}


