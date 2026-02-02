import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Tabs from "../components/Tabs.jsx";
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
  const { isTenantAdmin, user } = useAuth();

  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const [fromDate, setFromDate] = useState(formatDateInput(thirtyDaysAgo));
  const [toDate, setToDate] = useState(formatDateInput(today));
  const [selectedDevice, setSelectedDevice] = useState("");
  const [rows, setRows] = useState([]);
  const [consolidatedRows, setConsolidatedRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasRun, setHasRun] = useState(false);

  const runPerDeviceReport = () => {
    setLoading(true);
    setError(null);
    setHasRun(true);
    
    setTimeout(() => {
      // Generate dummy per-device data
      const dummyRows = Array.from({ length: 50 }, (_, i) => ({
        tenant_id: user?.tenant_id || 3,
        tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
        device_id: `device_${i + 1}`,
        device_external_id: `device_${i + 1}`,
        device_name: `Device ${i + 1}`,
        utility_kind: "gas",
        index_key: `gas_meter_${i + 1}`,
        period_start: fromDate,
        period_end: toDate,
        start_index: null,
        end_index: null,
        consumption: Math.round((Math.random() * 500 + 100) * 100) / 100,
        unit: "L",
        rate_per_unit: 3.0,
        currency: "AED",
        amount: Math.round((Math.random() * 1500 + 300) * 100) / 100,
      }));
      
      setRows(dummyRows);
      setConsolidatedRows([]);
      setLoading(false);
    }, 500);
  };

  const runConsolidatedReport = () => {
    setLoading(true);
    setError(null);
    setHasRun(true);
    
    setTimeout(() => {
      // Generate dummy consolidated data
      const consolidated = [
        {
          tenant_id: user?.tenant_id || 3,
          tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
          utility_kind: "electricity",
          period_start: fromDate,
          period_end: toDate,
          total_consumption: 125000.50,
          unit: "kWh",
          total_cost: 62500.25,
          currency: "AED",
          device_count: 2000,
        },
        {
          tenant_id: user?.tenant_id || 3,
          tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
          utility_kind: "gas",
          period_start: fromDate,
          period_end: toDate,
          total_consumption: 52000.75,
          unit: "L",
          total_cost: 156002.25,
          currency: "AED",
          device_count: 2000,
        },
        {
          tenant_id: user?.tenant_id || 3,
          tenant_name: user?.tenant_id === 3 ? "SmartLPG" : "Demo Tenant",
          utility_kind: "water",
          period_start: fromDate,
          period_end: toDate,
          total_consumption: 31000.00,
          unit: "m³",
          total_cost: 31000.00,
          currency: "AED",
          device_count: 2000,
        },
      ];
      
      setConsolidatedRows(consolidated);
      setRows([]);
      setLoading(false);
    }, 500);
  };

  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires tenant admin access.</p>
        </div>
      </div>
    );
  }

  const totalConsumption = consolidatedRows.reduce((sum, r) => sum + (r.total_consumption || 0), 0);
  const totalAmount = consolidatedRows.reduce((sum, r) => sum + (r.total_cost || 0), 0);
  const deviceCount = consolidatedRows.length > 0 ? consolidatedRows[0].device_count : 0;
  const currency = consolidatedRows[0]?.currency || "AED";

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Utility", path: "/utility/billing" },
          { label: "Billing", path: "/utility/billing" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">
            <Icon name="utility" size={32} />
            Utility Billing
          </h1>
          <p className="page-header__subtitle">
            Generate consumption reports and billing statements for {user?.tenant_id === 3 ? "SmartLPG" : "your"} devices
          </p>
        </div>
      </div>

      <Tabs
        tabs={[
          {
            id: "per-device",
            label: "Per-Device Report",
            content: (
              <>
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
                            <Icon name="devices" size={16} />
                            Device (Optional)
                          </label>
                          <select
                            className="form-select"
                            value={selectedDevice}
                            onChange={(e) => setSelectedDevice(e.target.value)}
                          >
                            <option value="">All Devices</option>
                            {Array.from({ length: 50 }, (_, i) => (
                              <option key={`device_${i + 1}`} value={`device_${i + 1}`}>
                                Device {i + 1}
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
                          onClick={runPerDeviceReport} 
                          disabled={loading}
                        >
                          <Icon name="activity" size={18} />
                          {loading ? "Running..." : "Run Report"}
                        </button>
                        <button 
                          className="btn btn--primary" 
                          disabled={loading || rows.length === 0}
                        >
                          <Icon name="download" size={18} />
                          Download PDF
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
                    {error}
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
                  </div>
                )}

                {!loading && rows.length > 0 && (
                  <div className="card">
                    <div className="card__header">
                      <h3 className="card__title">
                        <Icon name="file" size={20} /> Per-Device Billing Report
                      </h3>
                    </div>
                    <div className="card__body">
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Tenant</th>
                              <th>Device</th>
                              <th>Index Key</th>
                              <th>Consumption</th>
                              <th>Unit</th>
                              <th>Rate</th>
                              <th>Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.slice(0, 50).map((row) => (
                              <tr key={`${row.device_id}`}>
                                <td>{row.tenant_name}</td>
                                <td>
                                  <div style={{ fontWeight: "var(--font-weight-semibold)" }}>
                                    {row.device_name || row.device_external_id}
                                  </div>
                                </td>
                                <td>
                                  <code className="badge badge--neutral" style={{ fontSize: "var(--font-size-xs)" }}>
                                    {row.index_key}
                                  </code>
                                </td>
                                <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                                  {row.consumption.toFixed(2)}
                                </td>
                                <td><span className="badge badge--info">{row.unit}</span></td>
                                <td className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                                  {row.currency} {row.rate_per_unit.toFixed(4)}
                                </td>
                                <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)", color: "var(--color-success-500)" }}>
                                  {row.currency} {row.amount.toFixed(2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ),
          },
          {
            id: "consolidated",
            label: "Consolidated Report",
            content: (
              <>
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
                          onClick={runConsolidatedReport} 
                          disabled={loading}
                        >
                          <Icon name="activity" size={18} />
                          {loading ? "Running..." : "Run Report"}
                        </button>
                        <button 
                          className="btn btn--primary" 
                          disabled={loading || consolidatedRows.length === 0}
                        >
                          <Icon name="download" size={18} />
                          Download PDF
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {error && (
                  <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
                    {error}
                  </div>
                )}

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
                        {consolidatedRows.length}
                      </div>
                    </div>
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
                  </div>
                )}

                {!loading && consolidatedRows.length > 0 && (
                  <div className="card">
                    <div className="card__header">
                      <h3 className="card__title">
                        <Icon name="file" size={20} /> Consolidated Tenant Report
                      </h3>
                    </div>
                    <div className="card__body">
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Tenant</th>
                              <th>Utility</th>
                              <th>Devices</th>
                              <th>Consumption</th>
                              <th>Unit</th>
                              <th>Total Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {consolidatedRows.map((row) => (
                              <tr key={row.utility_kind}>
                                <td>{row.tenant_name}</td>
                                <td>
                                  <span className="badge badge--info">
                                    {row.utility_kind.charAt(0).toUpperCase() + row.utility_kind.slice(1)}
                                  </span>
                                </td>
                                <td>{row.device_count}</td>
                                <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                                  {row.total_consumption.toFixed(2)}
                                </td>
                                <td><span className="badge badge--neutral">{row.unit}</span></td>
                                <td style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-lg)", color: "var(--color-success-500)" }}>
                                  {row.currency} {row.total_cost.toFixed(2)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}
              </>
            ),
          },
        ]}
      />
    </div>
  );
}
