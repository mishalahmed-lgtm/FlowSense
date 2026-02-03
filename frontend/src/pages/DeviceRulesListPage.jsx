import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import Modal from "../components/Modal.jsx";

export default function DeviceRulesListPage() {
  const { isTenantAdmin, user, token } = useAuth();
  
  const [rules, setRules] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [selectedRule, setSelectedRule] = useState(null);
  const [formState, setFormState] = useState({
    name: "",
    description: "",
    device_id: null,
    rule_type: "automation",
    condition: { field: "", operator: ">", value: "" },
    action: "log",
    is_active: true,
  });

  const loadDevices = async () => {
    if (!user || !token) return;
    
    try {
      if (user?.tenant_id === 3) {
        const { fetchSmartLPGDataForDashboard } = await import("../services/smartLPGDataMapper.js");
        const smartLPGData = await fetchSmartLPGDataForDashboard();
        if (smartLPGData.success && smartLPGData.devices) {
          setDevices(smartLPGData.devices);
        }
      }
    } catch (err) {
      console.error("Error loading devices:", err);
    }
  };

  const loadRules = async () => {
    if (!user || !token) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
        setError(null);
      
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
    loadDevices();
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

  const formatAction = (action) => {
    if (!action) return "log";
    if (typeof action === "string") return action;
    if (typeof action === "object") {
      // If action is an object, try to get type or action property
      return action.type || action.action || "log";
    }
    return "log";
  };

  const openModal = (rule = null) => {
    if (rule) {
      setSelectedRule(rule);
      setFormState({
        name: rule.name || "",
        description: rule.description || "",
        device_id: rule.device_id || null,
        rule_type: rule.rule_type || "automation",
        condition: rule.condition || { field: "", operator: ">", value: "" },
        action: formatAction(rule.action),
        is_active: rule.is_active ?? true,
      });
    } else {
      setSelectedRule(null);
      setFormState({
        name: "",
        description: "",
        device_id: null,
        rule_type: "automation",
        condition: { field: "", operator: ">", value: "" },
        action: "log",
        is_active: true,
      });
    }
    setShowModal(true);
    setError(null);
    setSuccessMessage(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedRule(null);
    setError(null);
    setSuccessMessage(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
        const payload = {
          ...formState,
        device_id: formState.device_id || null,
        rule_type: formState.rule_type || "automation",
        action: formState.action || "log",
        is_active: formState.is_active ?? true,
          condition: {
          field: formState.condition.field || "",
          operator: formState.condition.operator || ">",
          value: formState.condition.value || "",
          },
        };

      if (user?.tenant_id === 3) {
        const { saveDeviceRuleToFirebase } = await import("../services/smartLPGFirebaseService.js");
        
        const ruleToSave = {
            ...payload,
          id: selectedRule?.id,
          device_name: devices.find(d => d.device_id === payload.device_id)?.name || (payload.device_id ? `Device ${payload.device_id}` : "All Devices"),
          created_at: selectedRule?.created_at || new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
        
        await saveDeviceRuleToFirebase(ruleToSave);
        setSuccessMessage(selectedRule ? "Device rule updated successfully" : "Device rule created successfully");
        await loadRules();
        setTimeout(() => {
          closeModal();
        }, 1500);
      }
    } catch (err) {
      console.error("Error saving rule:", err);
      setError(err.response?.data?.detail || err.message || "Failed to save device rule");
    }
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm("Are you sure you want to delete this device rule?")) {
      return;
    }
    
    try {
      if (user?.tenant_id === 3) {
        const { deleteDeviceRuleFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        await deleteDeviceRuleFromFirebase(ruleId);
        setSuccessMessage("Device rule deleted successfully");
        await loadRules();
        setTimeout(() => setSuccessMessage(null), 3000);
      }
    } catch (err) {
      console.error("Error deleting rule:", err);
      setError(err.message || "Failed to delete device rule");
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
            onClick={() => openModal()}
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

      {successMessage && (
        <div className="badge badge--success" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {successMessage}
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
                          <span className="badge badge--info">{formatAction(rule.action)}</span>
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
                          onClick={() => openModal(rule)}
                        >
                              <Icon name="edit" size={14} />
                        </button>
                        <button
                              className="btn btn--xs btn--danger"
                              title="Delete Rule"
                          onClick={() => handleDelete(rule.id)}
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

      {/* Create/Edit Modal */}
      <Modal 
        isOpen={showModal} 
        onClose={closeModal} 
        title={selectedRule ? "Edit Device Rule" : "Create Device Rule"}
      >
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label form-label--required">Name</label>
            <input
              type="text"
              className="form-input"
              value={formState.name}
              onChange={(e) => setFormState({ ...formState, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              value={formState.description}
              onChange={(e) => setFormState({ ...formState, description: e.target.value })}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Device</label>
            <select
              className="form-select"
              value={formState.device_id || ""}
              onChange={(e) => setFormState({ ...formState, device_id: e.target.value || null })}
            >
              <option value="">All Devices</option>
              {devices.map((device) => (
                <option key={device.device_id} value={device.device_id}>
                  {device.device_id} - {device.name || "Unnamed Device"}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label form-label--required">Rule Type</label>
            <select
              className="form-select"
              value={formState.rule_type}
              onChange={(e) => setFormState({ ...formState, rule_type: e.target.value })}
              required
            >
              <option value="automation">Automation</option>
              <option value="routing">Routing</option>
              <option value="transformation">Transformation</option>
              <option value="filtering">Filtering</option>
            </select>
          </div>

          <div style={{ border: "1px solid var(--color-border-light)", padding: "var(--space-4)", borderRadius: "var(--radius-md)", marginBottom: "var(--space-4)" }}>
            <h4 style={{ marginBottom: "var(--space-3)" }}>Condition</h4>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label form-label--required">Field</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., payload.level_cm"
                  value={formState.condition?.field || ""}
                  onChange={(e) => setFormState({
                    ...formState,
                    condition: { ...formState.condition, field: e.target.value }
                  })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label form-label--required">Operator</label>
                <select
                  className="form-select"
                  value={formState.condition?.operator || ">"}
                  onChange={(e) => setFormState({
                    ...formState,
                    condition: { ...formState.condition, operator: e.target.value }
                  })}
                  required
                >
                  <option value=">">&gt;</option>
                  <option value=">=">&gt;=</option>
                  <option value="<">&lt;</option>
                  <option value="<=">&lt;=</option>
                  <option value="==">==</option>
                  <option value="!=">!=</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label form-label--required">Value</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., 50"
                  value={formState.condition?.value || ""}
                  onChange={(e) => setFormState({
                    ...formState,
                    condition: { ...formState.condition, value: e.target.value }
                  })}
                  required
                />
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label form-label--required">Action</label>
            <select
              className="form-select"
              value={formState.action}
              onChange={(e) => setFormState({ ...formState, action: e.target.value })}
              required
            >
              <option value="log">Log</option>
              <option value="alert">Alert</option>
              <option value="forward">Forward</option>
              <option value="transform">Transform</option>
              <option value="discard">Discard</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
            <input
              type="checkbox"
              checked={formState.is_active}
              onChange={(e) => setFormState({ ...formState, is_active: e.target.checked })}
                style={{ marginRight: "var(--space-2)", cursor: "pointer" }}
            />
              Active
            </label>
          </div>

          {error && (
            <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
              {error}
            </div>
          )}

          {successMessage && (
            <div className="badge badge--success" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
              {successMessage}
            </div>
          )}

          <div className="form-actions">
            <button type="button" className="btn btn--secondary" onClick={closeModal}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary">
              {selectedRule ? "Update Rule" : "Create Rule"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
