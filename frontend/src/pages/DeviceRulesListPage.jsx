import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";

export default function DeviceRulesListPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !user?.tenant_id) return;
    
    loadRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user?.tenant_id]);

  const loadRules = async () => {
    try {
      setLoading(true);
      console.log("Loading rules for tenant:", user?.tenant_id);
      
      // For SmartLPG tenant (tenant_id = 3), load from Firebase
      if (user?.tenant_id === 3) {
        console.log("🔥 Loading device rules from Firebase for SmartLPG tenant");
        try {
          const { getDeviceRulesFromFirebase } = await import("../services/smartLPGFirebaseService.js");
          const firebaseRules = await getDeviceRulesFromFirebase();
          console.log("✅ Loaded rules from Firebase:", firebaseRules);
          setRules(firebaseRules || []);
          setError(null);
        } catch (fbErr) {
          console.error("❌ Firebase error:", fbErr);
          setError("Failed to load rules from Firebase: " + (fbErr.message || "Unknown error"));
          setRules([]);
        }
      } else {
        // For other tenants, empty for now
        setRules([]);
      }
    } catch (err) {
      console.error("❌ loadRules error:", err);
      setError(err.message || "Failed to load device rules");
      setRules([]);
    } finally {
      setLoading(false);
    }
  };

  // Only tenant admins can access
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
          { label: "Devices", path: "/devices" },
          { label: "Device Rules", path: "/devices/rules" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Device Rules</h1>
          <p className="page-header__subtitle">
            Configure automation, routing, and transformation rules for your devices
          </p>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Rules Table */}
      <div className="card">
        {loading ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">Loading device rules...</p>
          </div>
        ) : rules.length === 0 ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">No device rules found.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id || Math.random()}>
                    <td>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{rule.name || "Unnamed Rule"}</div>
                    </td>
                    <td>
                      <span className="badge badge--info">
                        {rule.rule_type ? String(rule.rule_type).toUpperCase() : "AUTOMATION"}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${rule.is_active ? "badge--success" : "badge--neutral"}`}>
                        {rule.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
