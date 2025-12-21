import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
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
    device_id: null,
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
      const response = await api.get("/alerts/rules");
      setRules(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load alert rules");
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      const response = await api.get("/admin/devices");
      setDevices(response.data);
    } catch (err) {
      console.error("Failed to load devices:", err);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadRules();
    loadDevices();
  }, [token]);

  const openModal = (rule = null) => {
    if (rule) {
      setSelectedRule(rule);
      setFormState({
        name: rule.name || "",
        description: rule.description || "",
        device_id: rule.device_id || null,
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
        device_id: null,
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
        condition: {
          field: formState.condition.field,
          operator: formState.condition.operator,
          value: formState.condition.value,
        },
      };

      if (selectedRule) {
        await api.put(`/alerts/rules/${selectedRule.id}`, payload);
        setSuccessMessage("Alert rule updated successfully");
      } else {
        await api.post("/alerts/rules", payload);
        setSuccessMessage("Alert rule created successfully");
      }
      
      await loadRules();
      setTimeout(() => {
        closeModal();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save alert rule");
    }
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm("Are you sure you want to delete this alert rule?")) {
      return;
    }
    try {
      await api.delete(`/alerts/rules/${ruleId}`);
      setSuccessMessage("Alert rule deleted successfully");
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete alert rule");
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
        <div className="page-header__actions">
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
                        ? devices.find(d => d.id === rule.device_id)?.name || `Device ${rule.device_id}`
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
            <label className="form-label">Device (optional - leave empty for tenant-wide rule)</label>
            <select
              className="form-select"
              value={formState.device_id || ""}
              onChange={(e) => setFormState({ ...formState, device_id: e.target.value ? parseInt(e.target.value) : null })}
            >
              <option value="">All Devices (Tenant-wide)</option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name || device.device_id}
                </option>
              ))}
            </select>
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

