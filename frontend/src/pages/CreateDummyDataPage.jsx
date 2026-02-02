import { useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { createDummyAlerts, createDummyFOTAJobs, createAllDummyData } from "../utils/createDummySmartLPGData.js";
import Icon from "../components/Icon.jsx";

/**
 * Temporary page to create dummy data for SmartLPG tenant
 * This can be accessed via direct URL or added to admin menu
 */
export default function CreateDummyDataPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // Only allow SmartLPG tenant
  if (user?.tenant_id !== 3) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">This page is only available for SmartLPG tenant.</p>
        </div>
      </div>
    );
  }

  const handleCreateAlerts = async () => {
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      const alertResults = await createDummyAlerts();
      setResults({ alerts: alertResults });
    } catch (err) {
      setError(err.message || "Failed to create alerts");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateFOTA = async () => {
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      const fotaResults = await createDummyFOTAJobs();
      setResults({ fotaJobs: fotaResults });
    } catch (err) {
      setError(err.message || "Failed to create FOTA jobs");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAll = async () => {
    setLoading(true);
    setError(null);
    setResults(null);
    
    try {
      const allResults = await createAllDummyData();
      setResults(allResults);
    } catch (err) {
      setError(err.message || "Failed to create dummy data");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-header__title">
          <Icon name="database" size={32} />
          Create Dummy Data
        </h1>
        <p className="page-header__subtitle">
          Generate sample alerts and FOTA jobs for SmartLPG tenant
        </p>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      <div className="card">
        <div className="card__header">
          <h3 className="card__title">Create Dummy Data</h3>
        </div>
        <div className="card__body">
          <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap" }}>
            <button
              className="btn btn--primary"
              onClick={handleCreateAlerts}
              disabled={loading}
            >
              <Icon name="alert" size={18} />
              Create 5 Alerts
            </button>
            
            <button
              className="btn btn--primary"
              onClick={handleCreateFOTA}
              disabled={loading}
            >
              <Icon name="firmware" size={18} />
              Create 5 FOTA Jobs
            </button>
            
            <button
              className="btn btn--secondary"
              onClick={handleCreateAll}
              disabled={loading}
            >
              <Icon name="database" size={18} />
              Create All (Alerts + FOTA)
            </button>
          </div>

          {loading && (
            <div style={{ marginTop: "var(--space-4)", textAlign: "center" }}>
              <p className="text-muted">Creating dummy data...</p>
            </div>
          )}

          {results && (
            <div style={{ marginTop: "var(--space-6)" }}>
              <h4 style={{ marginBottom: "var(--space-3)" }}>Results:</h4>
              
              {results.alerts && (
                <div style={{ marginBottom: "var(--space-4)" }}>
                  <h5>Alerts:</h5>
                  <ul>
                    {results.alerts.map((result, idx) => (
                      <li key={idx} style={{ color: result.success ? "var(--color-success-500)" : "var(--color-error-500)" }}>
                        {result.success ? "✅" : "❌"} {result.title || result.name} {result.id ? `(ID: ${result.id})` : ""}
                        {result.error && <span className="text-muted"> - {result.error}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {results.fotaJobs && (
                <div>
                  <h5>FOTA Jobs:</h5>
                  <ul>
                    {results.fotaJobs.map((result, idx) => (
                      <li key={idx} style={{ color: result.success ? "var(--color-success-500)" : "var(--color-error-500)" }}>
                        {result.success ? "✅" : "❌"} {result.name} {result.id ? `(ID: ${result.id})` : ""}
                        {result.error && <span className="text-muted"> - {result.error}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
