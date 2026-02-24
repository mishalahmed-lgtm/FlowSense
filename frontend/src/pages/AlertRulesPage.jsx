import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { isSmartLPGTenant } from "../utils/tenantHelpers.js";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";

export default function AlertRulesPage() {
  const { token, isTenantAdmin, hasModule, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
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
    scope: "tenant_wide", // "tenant_wide", "device_type", "specific_device"
    device_id: null,
    device_type: null,
    condition: { field: "", operator: ">", value: "" },
    priority: "medium",
    title_template: "",
    message_template: "",
    notify_email: true,
    notify_sms: false,
    notify_webhook: false,
    webhook_url: "",
    escalation_enabled: false,
    escalation_delay_minutes: 30,
    escalation_priority: null,
    aggregation_enabled: true,
    aggregation_window_minutes: 5,
    max_alerts_per_window: 10,
    is_active: true,
  });
  const [deviceSearchQuery, setDeviceSearchQuery] = useState("");

  // Only tenant admins with alerts module can access
  if (!isTenantAdmin || !hasModule("alerts")) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires alerts module access.</p>
        </div>
      </div>
    );
  }

  const loadRules = async () => {
    try {
      setLoading(true);
      
      // For SmartLPG tenant, load from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { getAlertRulesFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        const rules = await getAlertRulesFromFirebase(user?.tenant_id);
        setRules(rules);
        setError(null);
      } else {
      const response = await api.get("/alerts/rules");
      setRules(response.data);
      setError(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      // For SmartLPG tenant, load devices from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { fetchSmartLPGDataForDashboard } = await import("../services/smartLPGDataMapper.js");
        const deviceData = await fetchSmartLPGDataForDashboard();
        if (deviceData.success && deviceData.devices) {
          // Map Firebase devices to format expected by Alert Rules page
          const mappedDevices = deviceData.devices.map((device) => ({
            id: device.device_id || device.id,
            device_id: device.device_id || device.id,
            name: device.name || device.device_name || device.device_id,
            device_type: device.device_type || device.device_type_id || null,
          }));
          setDevices(mappedDevices);
          console.log(`✅ Loaded ${mappedDevices.length} devices from Firebase for Alert Rules`);
        }
      } else {
        const response = await api.get("/admin/devices");
        setDevices(response.data);
      }
    } catch (err) {
      console.error("Failed to load devices:", err);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadRules();
    loadDevices();
  }, [token]);

  // Get unique device types from devices
  const deviceTypes = Array.isArray(devices) 
    ? Array.from(new Set(devices.map(d => d.device_type).filter(Boolean))).sort()
    : [];
  
  // Filter devices based on search query
  const filteredDevices = Array.isArray(devices) 
    ? devices.filter(device => {
        if (!deviceSearchQuery) return true;
        const query = deviceSearchQuery.toLowerCase();
        return (
          (device.name || "").toLowerCase().includes(query) ||
          (device.device_id || "").toLowerCase().includes(query) ||
          (device.id || "").toLowerCase().includes(query)
        );
      })
    : [];

  const openModal = (rule = null) => {
    if (rule) {
      setSelectedRule(rule);
      // Determine scope based on rule
      let scope = "tenant_wide";
      if (rule.device_id) {
        scope = "specific_device";
      } else if (rule.device_type) {
        scope = "device_type";
      }
      
      setFormState({
        name: rule.name || "",
        description: rule.description || "",
        scope: scope,
        device_id: rule.device_id || null,
        device_type: rule.device_type || null,
        condition: rule.condition || { field: "", operator: ">", value: "" },
        priority: rule.priority || "medium",
        title_template: rule.title_template || "",
        message_template: rule.message_template || "",
        notify_email: rule.notify_email ?? true,
        notify_sms: rule.notify_sms ?? false,
        notify_webhook: rule.notify_webhook ?? false,
        webhook_url: rule.webhook_url || "",
        escalation_enabled: rule.escalation_enabled ?? false,
        escalation_delay_minutes: rule.escalation_delay_minutes || 30,
        escalation_priority: rule.escalation_priority || null,
        aggregation_enabled: rule.aggregation_enabled ?? true,
        aggregation_window_minutes: rule.aggregation_window_minutes || 5,
        max_alerts_per_window: rule.max_alerts_per_window || 10,
        is_active: rule.is_active ?? true,
      });
    } else {
      setSelectedRule(null);
      setFormState({
        name: "",
        description: "",
        scope: "tenant_wide",
        device_id: null,
        device_type: null,
        condition: { field: "", operator: ">", value: "" },
        priority: "medium",
        title_template: "",
        message_template: "",
        notify_email: true,
        notify_sms: false,
        notify_webhook: false,
        webhook_url: "",
        escalation_enabled: false,
        escalation_delay_minutes: 30,
        escalation_priority: null,
        aggregation_enabled: true,
        aggregation_window_minutes: 5,
        max_alerts_per_window: 10,
        is_active: true,
      });
    }
    setDeviceSearchQuery("");
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
      // Build payload based on scope
      const payload = {
        ...formState,
        tenant_id: user?.tenant_id,
        condition: {
          field: formState.condition.field,
          operator: formState.condition.operator,
          value: formState.condition.value,
        },
      };
      
      // Set device_id and device_type based on scope
      if (formState.scope === "tenant_wide") {
        payload.device_id = null;
        payload.device_type = null;
      } else if (formState.scope === "device_type") {
        payload.device_id = null;
        payload.device_type = formState.device_type;
      } else if (formState.scope === "specific_device") {
        // For SmartLPG, device_id is a string, not an integer
        payload.device_id = isSmartLPGTenant(user?.tenant_id) ? formState.device_id : (formState.device_id ? parseInt(formState.device_id) : null);
        payload.device_type = null;
      }
      
      // Remove scope from payload (it's just for UI)
      delete payload.scope;

      // For SmartLPG tenant, save to Firebase instead of PostgreSQL
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { saveAlertRuleToFirebase } = await import("../services/smartLPGFirebaseService.js");
        console.log(`💾 [ALERT RULES] Saving rule to Firebase:`, payload);
        try {
          if (selectedRule) {
            const result = await saveAlertRuleToFirebase({ ...payload, id: selectedRule.id });
            console.log(`✅ [ALERT RULES] Rule updated:`, result);
            setSuccessMessage("Alert rule updated successfully in Firebase");
          } else {
            const result = await saveAlertRuleToFirebase(payload);
            console.log(`✅ [ALERT RULES] Rule created:`, result);
            setSuccessMessage("Alert rule created successfully in Firebase");
          }
        } catch (saveError) {
          console.error(`❌ [ALERT RULES] Failed to save rule:`, saveError);
          throw saveError;
        }
      } else {
      if (selectedRule) {
        await api.put(`/alerts/rules/${selectedRule.id}`, payload);
        setSuccessMessage("Alert rule updated successfully");
      } else {
        await api.post("/alerts/rules", payload);
        setSuccessMessage("Alert rule created successfully");
        }
      }
      
      await loadRules();
      setTimeout(() => {
        closeModal();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to save alert rule");
    }
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm("Are you sure you want to delete this alert rule?")) {
      return;
    }
    try {
      // For SmartLPG tenant, delete from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { deleteAlertRuleFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        await deleteAlertRuleFromFirebase(ruleId);
        setSuccessMessage("Alert rule deleted successfully from Firebase");
      } else {
      await api.delete(`/alerts/rules/${ruleId}`);
      setSuccessMessage("Alert rule deleted successfully");
      }
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to delete alert rule");
    }
  };

  const getPriorityBadgeClass = (priority) => {
    switch (priority) {
      case "critical": return "badge--error";
      case "high": return "badge--warning";
      case "medium": return "badge--info";
      case "low": return "badge--neutral";
      default: return "badge--neutral";
    }
  };

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Alerts", path: "/alerts" },
          { label: "Alert Rules", path: "/alerts/rules" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Alert Rules</h1>
          <p className="page-header__subtitle">
            Configure rules that trigger alerts based on device telemetry
          </p>
        </div>
        <div className="page-header__actions" style={{ display: "flex", gap: "var(--space-2)" }}>
          {isSmartLPGTenant(user?.tenant_id) && (
            <button
              className="btn btn--secondary"
              onClick={async () => {
                try {
                  setError(null);
                  setSuccessMessage(null);
                  const { evaluateAlertRulesAndCreateAlerts } = await import("../services/smartLPGFirebaseService.js");
                  const result = await evaluateAlertRulesAndCreateAlerts(user?.tenant_id);
                  setSuccessMessage(`Evaluated ${result.evaluated} conditions, created ${result.created} alerts`);
                } catch (err) {
                  setError(err.message || "Failed to evaluate alert rules");
                }
              }}
            >
              Evaluate Rules & Create Alerts
            </button>
          )}
          <button
            className="btn btn--primary"
            onClick={() => openModal()}
          >
            + Create Alert Rule
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
        {loading ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">Loading alert rules...</p>
          </div>
        ) : rules.length === 0 ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">No alert rules found. Create your first alert rule to get started.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Device</th>
                  <th>Condition</th>
                  <th>Priority</th>
                  <th>Notifications</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{rule.name}</div>
                      {rule.description && (
                        <div className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>
                          {rule.description}
                        </div>
                      )}
                    </td>
                    <td>
                      {rule.device_id
                        ? devices.find(d => d.id === rule.device_id || d.device_id === rule.device_id)?.name || `Device ${rule.device_id}`
                        : rule.device_type
                        ? `Device Type: ${rule.device_type}`
                        : rule.tenant_id ? "Tenant-wide" : "Global"}
                    </td>
                    <td>
                      <code style={{ fontSize: "var(--font-size-xs)" }}>
                        {rule.condition?.field} {rule.condition?.operator} {rule.condition?.value}
                      </code>
                    </td>
                    <td>
                      <span className={`badge ${getPriorityBadgeClass(rule.priority)}`}>
                        {rule.priority.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
                        {rule.notify_email && <span className="badge badge--info">Email</span>}
                        {rule.notify_sms && <span className="badge badge--info">SMS</span>}
                        {rule.notify_webhook && <span className="badge badge--info">Webhook</span>}
                        {!rule.notify_email && !rule.notify_sms && !rule.notify_webhook && (
                          <span className="text-muted">None</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${rule.is_active ? "badge--success" : "badge--neutral"}`}>
                        {rule.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <button
                          className="btn btn--sm btn--secondary"
                          onClick={() => openModal(rule)}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn--sm btn--danger"
                          onClick={() => handleDelete(rule.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      <Modal isOpen={showModal} onClose={closeModal}>
        <form className="form" onSubmit={handleSubmit}>
          <h3 style={{ marginBottom: "var(--space-6)" }}>{selectedRule ? "Edit Alert Rule" : "Create Alert Rule"}</h3>

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
            <label className="form-label">Rule Scope</label>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer" }}>
                <input
                  type="radio"
                  name="scope"
                  value="tenant_wide"
                  checked={formState.scope === "tenant_wide"}
                  onChange={(e) => setFormState({ ...formState, scope: e.target.value, device_id: null, device_type: null })}
                />
                <span>Tenant-wide (All devices)</span>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer" }}>
                <input
                  type="radio"
                  name="scope"
                  value="device_type"
                  checked={formState.scope === "device_type"}
                  onChange={(e) => setFormState({ ...formState, scope: e.target.value, device_id: null })}
                />
                <span>Device Type</span>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", cursor: "pointer" }}>
                <input
                  type="radio"
                  name="scope"
                  value="specific_device"
                  checked={formState.scope === "specific_device"}
                  onChange={(e) => setFormState({ ...formState, scope: e.target.value, device_type: null })}
                />
                <span>Specific Device</span>
              </label>
            </div>
            
            {formState.scope === "device_type" && (
              <div className="form-group" style={{ marginTop: "var(--space-4)" }}>
                <label className="form-label">Device Type</label>
                <select
                  className="form-select"
                  value={formState.device_type || ""}
                  onChange={(e) => setFormState({ ...formState, device_type: e.target.value || null })}
                  required
                >
                  <option value="">Select device type...</option>
                  {deviceTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>
            )}
            
            {formState.scope === "specific_device" && (
              <div className="form-group" style={{ marginTop: "var(--space-4)" }}>
                <label className="form-label">Device</label>
                <div style={{ marginBottom: "var(--space-2)", position: "relative" }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Search devices by name or ID..."
                    value={deviceSearchQuery}
                    onChange={(e) => {
                      setDeviceSearchQuery(e.target.value);
                      // Clear device selection when search changes
                      if (e.target.value && formState.device_id) {
                        const selectedDevice = devices.find(d => d.id === formState.device_id || d.device_id === formState.device_id);
                        const deviceMatches = selectedDevice && (
                          (selectedDevice.name || "").toLowerCase().includes(e.target.value.toLowerCase()) ||
                          (selectedDevice.device_id || "").toLowerCase().includes(e.target.value.toLowerCase()) ||
                          (selectedDevice.id || "").toLowerCase().includes(e.target.value.toLowerCase())
                        );
                        if (!deviceMatches) {
                          setFormState({ ...formState, device_id: null });
                        }
                      }
                    }}
                    style={{
                      paddingLeft: "var(--space-10)",
                      paddingRight: deviceSearchQuery ? "var(--space-10)" : "var(--space-4)",
                    }}
                  />
                  <span style={{ position: "absolute", left: "var(--space-3)", top: "50%", transform: "translateY(-50%)", color: "var(--color-text-tertiary)" }}>🔍</span>
                  {deviceSearchQuery && (
                    <button
                      type="button"
                      onClick={() => {
                        setDeviceSearchQuery("");
                        setFormState({ ...formState, device_id: null });
                      }}
                      style={{
                        position: "absolute",
                        right: "var(--space-2)",
                        top: "50%",
                        transform: "translateY(-50%)",
                        background: "none",
                        border: "none",
                        color: "var(--color-text-tertiary)",
                        cursor: "pointer",
                        padding: "var(--space-1)",
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>
                <select
                  className="form-select"
                  value={formState.device_id || ""}
                  onChange={(e) => setFormState({ ...formState, device_id: e.target.value || null })}
                  required
                  style={{ 
                    maxHeight: "200px", 
                    overflowY: "auto",
                    width: "100%"
                  }}
                >
                  <option value="">Select a device...</option>
                  {filteredDevices.length > 0 ? (
                    filteredDevices.map((device) => (
                      <option key={device.id} value={device.id}>
                        {device.name || device.device_id} {device.device_id && device.device_id !== device.name ? `(${device.device_id})` : ""}
                      </option>
                    ))
                  ) : (
                    <option value="" disabled>No devices found</option>
                  )}
                </select>
                {filteredDevices.length === 0 && deviceSearchQuery && (
                  <small className="form-help" style={{ color: "var(--color-text-warning)", display: "block", marginTop: "var(--space-2)" }}>
                    No devices found matching "{deviceSearchQuery}"
                  </small>
                )}
                {filteredDevices.length > 0 && deviceSearchQuery && filteredDevices.length < devices.length && (
                  <small className="form-help" style={{ display: "block", marginTop: "var(--space-2)", color: "var(--color-text-tertiary)" }}>
                    Showing {filteredDevices.length} of {devices.length} devices
                  </small>
                )}
              </div>
            )}
          </div>

          <div style={{ border: "1px solid var(--color-border-light)", padding: "var(--space-4)", borderRadius: "var(--radius-md)" }}>
            <h4 style={{ marginBottom: "var(--space-3)" }}>Condition</h4>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label form-label--required">Field</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., payload.temperature"
                  value={formState.condition.field}
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
                  value={formState.condition.operator}
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
                  value={formState.condition.value}
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
            <label className="form-label form-label--required">Priority</label>
            <select
              className="form-select"
              value={formState.priority}
              onChange={(e) => setFormState({ ...formState, priority: e.target.value })}
              required
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label form-label--required">Alert Title Template</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., High Temperature Alert: {{payload.temperature}}°C"
              value={formState.title_template}
              onChange={(e) => setFormState({ ...formState, title_template: e.target.value })}
              required
            />
            <small className="text-muted" style={{ fontSize: "var(--font-size-xs)", marginTop: "var(--space-1)", display: "block" }}>Use {'{{'}field.path{'}}'} for variable substitution</small>
          </div>

          <div className="form-group">
            <label className="form-label">Alert Message Template</label>
            <textarea
              className="form-textarea"
              placeholder="e.g., Device {{device.name}} has temperature {{payload.temperature}}°C which exceeds threshold"
              value={formState.message_template}
              onChange={(e) => setFormState({ ...formState, message_template: e.target.value })}
              rows={3}
            />
          </div>

          <div style={{ border: "1px solid var(--color-border-light)", padding: "var(--space-4)", borderRadius: "var(--radius-md)" }}>
            <h4 style={{ marginBottom: "var(--space-3)" }}>Notification Channels</h4>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
              <input
                type="checkbox"
                id="notify_email"
                checked={formState.notify_email}
                onChange={(e) => setFormState({ ...formState, notify_email: e.target.checked })}
                style={{ width: "auto" }}
              />
              <label htmlFor="notify_email" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
                Email
              </label>
            </div>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
              <input
                type="checkbox"
                id="notify_sms"
                checked={formState.notify_sms}
                onChange={(e) => setFormState({ ...formState, notify_sms: e.target.checked })}
                style={{ width: "auto" }}
              />
              <label htmlFor="notify_sms" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
                SMS
              </label>
            </div>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
              <input
                type="checkbox"
                id="notify_webhook"
                checked={formState.notify_webhook}
                onChange={(e) => setFormState({ ...formState, notify_webhook: e.target.checked })}
                style={{ width: "auto" }}
              />
              <label htmlFor="notify_webhook" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
                Webhook
              </label>
            </div>
            {formState.notify_webhook && (
              <div className="form-group">
                <label className="form-label">Webhook URL</label>
                <input
                  type="url"
                  className="form-input"
                  value={formState.webhook_url}
                  onChange={(e) => setFormState({ ...formState, webhook_url: e.target.value })}
                  placeholder="https://example.com/webhook"
                />
              </div>
            )}
          </div>

          <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
            <input
              type="checkbox"
              id="is_active"
              checked={formState.is_active}
              onChange={(e) => setFormState({ ...formState, is_active: e.target.checked })}
              style={{ width: "auto" }}
            />
            <label htmlFor="is_active" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
              Active
            </label>
          </div>

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

