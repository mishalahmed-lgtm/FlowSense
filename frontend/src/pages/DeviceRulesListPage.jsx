import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";

export default function DeviceRulesListPage() {
  const { isTenantAdmin, user, token } = useAuth();
  const navigate = useNavigate();
  
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadRules = async () => {
    // Don't load if user is not available yet
    if (!user || !token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // For SmartLPG tenant, try to load from Firebase
      if (user?.tenant_id === 3) {
        try {
          const { getDeviceRulesFromFirebase } = await import("../services/smartLPGFirebaseService.js");
          const firebaseRules = await getDeviceRulesFromFirebase();
          console.log("✅ Loaded rules:", firebaseRules);
          setRules(firebaseRules || []);
        } catch (err) {
          console.error("❌ Firebase error:", err);
          setError("Failed to load rules from Firebase: " + (err.message || "Unknown error"));
          setRules([]);
        }
      } else {
        setRules([]);
      }
    } catch (err) {
      console.error("❌ Error loading rules:", err);
      setError("Failed to load device rules: " + (err.message || "Unknown error"));
      setRules([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    console.log("🔄 DeviceRulesListPage useEffect, user:", user, "token:", !!token);
    loadRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.tenant_id, token]);

  const getRuleTypeBadgeClass = (type) => {
    if (!type) return "badge--neutral";
    switch (String(type).toLowerCase()) {
      case "automation": return "badge--info";
      case "routing": return "badge--success";
      case "transformation": return "badge--warning";
      case "filtering": return "badge--neutral";
      default: return "badge--neutral";
    }
  };

  // Only tenant admins can access - check AFTER all hooks
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires tenant admin access.</p>
        </div>
      </div>
    );
  }

  // Safety check - if still loading user
  if (!user) {
    return (
      <div className="page">
        <div className="card">
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">Loading...</p>
          </div>
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
        <div className="page-header__actions">
          <button
            className="btn btn--primary"
            onClick={() => navigate("/devices")}
          >
            <Icon name="plus" size={18} />
            Create Device Rule
          </button>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Rules Table */}
      <div className="card">
        <div className="card__header">
          <h3 className="card__title">
            <Icon name="list" size={20} /> All Device Rules
          </h3>
        </div>
        <div className="card__body">
          {loading ? (
            <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
              <p className="text-muted">Loading device rules...</p>
            </div>
          ) : rules.length === 0 ? (
            <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
              <Icon name="inbox" size={48} style={{ opacity: 0.3 }} />
              <h3 style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)", fontSize: "var(--font-size-lg)" }}>
                No Device Rules Found
              </h3>
              <p className="text-muted" style={{ marginTop: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                Create your first device rule to get started
              </p>
            </div>
          ) : (
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Device</th>
                    <th>Type</th>
                    <th>Condition</th>
                    <th>Action</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule, index) => {
                    const ruleId = rule.id || `rule_${index}`;
                    return (
                      <tr key={ruleId}>
                        <td>
                          <div style={{ fontWeight: "var(--font-weight-semibold)" }}>
                            {rule.name || "Unnamed Rule"}
                          </div>
                          {rule.description && (
                            <div className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>
                              {rule.description}
                            </div>
                          )}
                        </td>
                        <td>
                          {rule.device_name || rule.device_id || "All Devices"}
                        </td>
                        <td>
                          <span className={`badge ${getRuleTypeBadgeClass(rule.rule_type)}`}>
                            {rule.rule_type ? String(rule.rule_type).toUpperCase() : "AUTOMATION"}
                          </span>
                        </td>
                        <td>
                          <code style={{ fontSize: "var(--font-size-xs)" }}>
                            {String(rule.condition?.field || "")} {String(rule.condition?.operator || "")} {String(rule.condition?.value || "")}
                          </code>
                        </td>
                        <td>
                          <span className="badge badge--info">{String(rule.action || "log")}</span>
                        </td>
                        <td>
                          <span className={`badge ${rule.is_active ? "badge--success" : "badge--neutral"}`}>
                            {rule.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "var(--space-2)" }}>
                            <button
                              className="btn btn--xs btn--secondary"
                              title="Edit Rule"
                            >
                              <Icon name="edit" size={14} />
                            </button>
                            <button
                              className="btn btn--xs btn--danger"
                              title="Delete Rule"
                            >
                              <Icon name="trash" size={14} />
                            </button>
                          </div>
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
    </div>
  );
}
