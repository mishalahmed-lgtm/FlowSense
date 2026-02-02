import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";

export default function UtilityBillingPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const api = createApiClient(token);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rows, setRows] = useState([]);

  const runReport = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // For SmartLPG tenant (tenant_id = 3), generate dummy data
      if (user?.tenant_id === 3) {
        console.log("🔥 Generating utility billing data for SmartLPG tenant");
        
        // Generate 10 dummy devices with billing data
        const dummyRows = Array.from({ length: 10 }, (_, i) => ({
          device_id: `device_${i + 1}`,
          device_name: `Device ${i + 1}`,
          consumption: Math.random() * 1000,
          unit: "L",
          amount: Math.random() * 3000,
          currency: "AED",
        }));
        
        setRows(dummyRows);
      } else {
        setRows([]);
      }
    } catch (err) {
      console.error("Error:", err);
      setError(err.message || "Failed to load utility consumption");
      setRows([]);
    } finally {
      setLoading(false);
    }
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
            Generate consumption reports and billing statements
          </p>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      <div className="card">
        <div className="card__header">
          <h3 className="card__title">Generate Report</h3>
        </div>
        <div className="card__body">
          <button 
            className="btn btn--primary" 
            onClick={runReport} 
            disabled={loading}
          >
            <Icon name="activity" size={18} />
            {loading ? "Running..." : "Run Report"}
          </button>
        </div>
      </div>

      {loading && (
        <div className="card">
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">Loading...</p>
          </div>
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="card">
          <div className="card__header">
            <h3 className="card__title">Billing Report</h3>
          </div>
          <div className="card__body">
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Consumption</th>
                    <th>Unit</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.device_id}>
                      <td>{row.device_name}</td>
                      <td>{row.consumption.toFixed(2)}</td>
                      <td><span className="badge badge--info">{row.unit}</span></td>
                      <td style={{ fontWeight: "var(--font-weight-bold)", color: "var(--color-success-500)" }}>
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
    </div>
  );
}
