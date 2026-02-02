import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { isSmartLPGTenant } from "../utils/tenantHelpers.js";
import Icon from "./Icon.jsx";

const CUSTOM_FIELD_VALUE = "__custom_field__";

const initialFormState = {
  name: "",
  priority: 100,
  is_active: true,
  conditionFieldChoice: CUSTOM_FIELD_VALUE,
  conditionFieldCustom: "",
  conditionOperator: ">",
  conditionValue: "50",
  actionPreset: "alert",
  alertTitle: "",
  alertMessage: "",
  alertPriority: "medium",
  deviceCommand: "",
  deviceCommandTopic: "",
  deviceCommandQos: 1,
  webhookUrl: "",
  webhookMethod: "POST",
  webhookHeaders: "",
  webhookBody: "",
  flagStatus: "ALERT",
  customRouteTopic: "",
  customMutateField: "payload.status",
  customMutateValue: "ALERT",
  stopAfter: true,
  ruleType: "event", // "event" or "scheduled"
  cronSchedule: "",
};

const actionPresets = [
  { value: "alert", label: "Create Alert" },
  { value: "device_command", label: "Send Device Command" },
  { value: "webhook", label: "Call Webhook" },
  { value: "ignore", label: "Ignore this reading" },
  { value: "flag_warning", label: "Mark device as warning" },
  { value: "close_valve", label: "Close the valve" },
  { value: "open_valve", label: "Open the valve" },
  { value: "custom_route", label: "Advanced: send to another feed" },
  { value: "custom_mutate", label: "Advanced: set a field value" },
];

export default function DeviceRulesPanel({ api, deviceId, deviceType, showModal, setShowModal }) {
  const { user } = useAuth();
  const [rules, setRules] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [fieldOptions, setFieldOptions] = useState([]);
  const [formState, setFormState] = useState(initialFormState);

  useEffect(() => {
    if (!deviceId) {
      return;
    }
    loadRules();
  }, [deviceId]);

  useEffect(() => {
    if (!deviceId) return;
    
    const loadFieldOptions = async () => {
      let options = [];
      
      // For SmartLPG tenant (tenant_id = 3), skip backend API call
      if (user?.tenant_id === 3) {
        // Use common SmartLPG fields
        options = [
          { label: "Level CM (payload.level_cm)", value: "payload.level_cm" },
          { label: "Level Percent (payload.level_percent)", value: "payload.level_percent" },
          { label: "Temperature (payload.temperature)", value: "payload.temperature" },
          { label: "Battery (payload.battery)", value: "payload.battery" },
        ];
        setFieldOptions(options);
        setFormState((prev) => ({
          ...prev,
          conditionFieldChoice: options[0]?.value || CUSTOM_FIELD_VALUE,
        }));
        return;
      }
      
      // Always try to fetch from actual telemetry first (most accurate)
      if (deviceId && api) {
        try {
          const resp = await api.get(`/dashboard/devices/${deviceId}/fields`);
          if (resp.data && resp.data.length > 0) {
            const humanizeField = (value) => {
              return value
                .split(".")
                .slice(-1)[0]
                .replace(/_/g, " ")
                .replace(/\b\w/g, (letter) => letter.toUpperCase());
            };
            options = resp.data
              .filter(f => {
                const fieldType = f.field_type || f.type; // Support both field_type and type
                return fieldType === "number" || fieldType === "string" || fieldType === "boolean";
              })
              .map(f => ({
                label: f.display_name ? `${f.display_name} (${f.key})` : `${humanizeField(f.key)} (${f.key})`,
                value: f.key.startsWith("payload.") ? f.key : `payload.${f.key}`,
              }));
          }
        } catch (err) {
          console.error("Failed to load fields from telemetry:", err);
        }
      }
      
      // If no telemetry fields, try schema as fallback
      if (options.length === 0) {
        options = extractFieldOptions(deviceType);
      }
      
      // If still no fields, show a message but allow custom field entry
      if (options.length === 0) {
        console.warn("No payload fields found for device. User can enter custom field.");
        // Don't set default fields - let user enter custom field instead
      }
      
      setFieldOptions(options);
      setFormState((prev) => ({
        ...prev,
        conditionFieldChoice: options[0]?.value || CUSTOM_FIELD_VALUE,
      }));
    };
    
    loadFieldOptions();
  }, [deviceType?.id, deviceId, user?.tenant_id]);

  const loadRules = async () => {
    if (!deviceId) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      // For tenant_id = 3 (SmartLPG), generate static rules
      if (user?.tenant_id === 3) {
        console.log("🔥 Generating static rules for SmartLPG tenant");
        const staticRules = [
          {
            id: 1,
            device_id: deviceId,
            name: "Low Gas Level Alert",
            priority: 100,
            is_active: true,
            condition: {
              field: "payload.level_percent",
              operator: "<",
              value: 30
            },
            actions: [
              {
                type: "alert",
                config: {
                  title: "Gas Tank Low - Refill Required",
                  message: "Gas level is below 30%. Please schedule refill.",
                  priority: "critical"
                }
              }
            ],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 2,
            device_id: deviceId,
            name: "Device Offline Alert",
            priority: 90,
            is_active: true,
            condition: {
              field: "payload.status",
              operator: "==",
              value: "offline"
            },
            actions: [
              {
                type: "alert",
                config: {
                  title: "Device Offline",
                  message: "Device has gone offline. Please check connectivity.",
                  priority: "high"
                }
              }
            ],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          },
          {
            id: 3,
            device_id: deviceId,
            name: "Battery Low Warning",
            priority: 80,
            is_active: true,
            condition: {
              field: "payload.battery_volt",
              operator: "<",
              value: 3.3
            },
            actions: [
              {
                type: "alert",
                config: {
                  title: "Low Battery Warning",
                  message: "Device battery is below 3.3V. Consider replacing battery.",
                  priority: "medium"
                }
              }
            ],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ];
        setRules(staticRules);
        setIsLoading(false);
        return;
      }
      
      // For other tenants, use backend API
      const response = await api.get(`/admin/devices/${deviceId}/rules`);
      setRules(response.data || []);
    } catch (err) {
      // If 404 or endpoint doesn't exist, just show empty rules (user can create)
      if (err.response?.status === 404) {
        setRules([]);
        setError(null); // Don't show error for 404 - it's normal if no rules exist
      } else {
      setError(err.response?.data?.detail || "Failed to load rules");
        setRules([]); // Still allow creating rules even if load fails
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
  };

  const handleFieldChoice = (value) => {
    if (value === CUSTOM_FIELD_VALUE) {
      setFormState((prev) => ({ ...prev, conditionFieldChoice: value }));
    } else {
      setFormState((prev) => ({
        ...prev,
        conditionFieldChoice: value,
        conditionFieldCustom: "",
      }));
    }
  };

  const buildCondition = () => {
    const field =
      formState.conditionFieldChoice !== CUSTOM_FIELD_VALUE
        ? formState.conditionFieldChoice
        : formState.conditionFieldCustom.trim();

    if (!field) {
      throw new Error("Select a field or enter a custom one.");
    }

    return {
      field,
      op: formState.conditionOperator,
      value: coerceValue(formState.conditionValue),
    };
  };

  const buildAction = () => {
    const stop = Boolean(formState.stopAfter);
    switch (formState.actionPreset) {
      case "alert":
        return {
          type: "alert",
          title: formState.alertTitle || "Rule-triggered alert",
          message: formState.alertMessage || "A rule condition was met",
          priority: formState.alertPriority || "medium",
          stop,
        };
      case "device_command":
        if (!formState.deviceCommand) {
          throw new Error("Enter a device command.");
        }
        // Parse JSON if it's a JSON string, otherwise create simple command object
        let command;
        if (typeof formState.deviceCommand === 'string' && formState.deviceCommand.trim().startsWith('{')) {
          try {
            command = JSON.parse(formState.deviceCommand);
          } catch (e) {
            command = { "action": formState.deviceCommand };
          }
        } else {
          command = { "action": formState.deviceCommand };
        }
        return {
          type: "device_command",
          command: command,
          topic: formState.deviceCommandTopic || undefined,
          qos: formState.deviceCommandQos || 1,
          stop,
        };
      case "webhook":
        if (!formState.webhookUrl) {
          throw new Error("Enter a webhook URL.");
        }
        return {
          type: "webhook",
          url: formState.webhookUrl,
          method: formState.webhookMethod || "POST",
          headers: formState.webhookHeaders ? JSON.parse(formState.webhookHeaders) : {},
          body: formState.webhookBody ? JSON.parse(formState.webhookBody) : {},
          stop,
        };
      case "ignore":
        return {
          type: "drop",
          reason: formState.alertMessage || "Ignored by automation",
          stop,
        };
      case "flag_warning":
        return {
          type: "mutate",
          set: { "payload.status": formState.flagStatus || "WARNING" },
          stop,
        };
      case "close_valve":
        return {
          type: "mutate",
          set: { "payload.command": "CLOSE_VALVE" },
          stop,
        };
      case "open_valve":
        return {
          type: "mutate",
          set: { "payload.command": "OPEN_VALVE" },
          stop,
        };
      case "custom_route":
        if (!formState.customRouteTopic.trim()) {
          throw new Error("Choose a feed to send this alert to.");
        }
        return {
          type: "route",
          topic: formState.customRouteTopic.trim(),
          stop,
        };
      case "custom_mutate":
        if (!formState.customMutateField.trim()) {
          throw new Error("Select the field you want to update.");
        }
        return {
          type: "mutate",
          set: {
            [formState.customMutateField.trim()]: coerceValue(formState.customMutateValue),
          },
          stop,
        };
      default:
        throw new Error("Pick an action to perform.");
    }
  };

  const handleCreateRule = async (event) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      const condition = buildCondition();
      
      // Validate scheduled rule
      if (formState.ruleType === "scheduled" && !formState.cronSchedule.trim()) {
        throw new Error("Cron schedule is required for scheduled rules");
      }
      const action = buildAction();
      
      const ruleData = {
        name: formState.name || "Untitled rule",
        priority: Number(formState.priority) || 100,
        is_active: Boolean(formState.is_active),
        condition,
        action,
        device_id: deviceId,
      };
      
      // Add scheduled rule fields if applicable
      if (formState.ruleType === "scheduled") {
        ruleData.rule_type = "scheduled";
        ruleData.cron_schedule = formState.cronSchedule.trim();
      }
      
      // For SmartLPG tenant, save to Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { saveDeviceRuleToFirebase } = await import("../services/smartLPGFirebaseService.js");
        await saveDeviceRuleToFirebase(ruleData);
        setSuccess("Rule created");
        setFormState((prev) => ({
          ...initialFormState,
          conditionFieldChoice: fieldOptions[0]?.value || CUSTOM_FIELD_VALUE,
        }));
        loadRules();
        // Close modal after successful creation
        if (setShowModal) {
          setShowModal(false);
        }
        return;
      }
      
      await api.post(`/admin/devices/${deviceId}/rules`, ruleData);
      setSuccess("Rule created");
      setFormState((prev) => ({
        ...initialFormState,
        conditionFieldChoice: fieldOptions[0]?.value || CUSTOM_FIELD_VALUE,
      }));
      loadRules();
      // Close modal after successful creation
      if (setShowModal) {
        setShowModal(false);
      }
    } catch (err) {
      if (err instanceof Error && !err.response) {
        setError(err.message);
        return;
      }
      setError(err.response?.data?.detail || err.message || "Failed to create rule");
    }
  };

  const toggleRule = async (rule) => {
    setError(null);
    setSuccess(null);
    try {
      // For SmartLPG tenant, update in Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { saveDeviceRuleToFirebase } = await import("../services/smartLPGFirebaseService.js");
        await saveDeviceRuleToFirebase({
          ...rule,
          is_active: !rule.is_active,
        });
        setSuccess(`Rule ${rule.is_active ? "disabled" : "enabled"}`);
        loadRules();
        return;
      }
      
      await api.put(`/admin/devices/${deviceId}/rules/${rule.id}`, {
        is_active: !rule.is_active,
      });
      setSuccess(`Rule ${rule.is_active ? "disabled" : "enabled"}`);
      loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update rule");
    }
  };

  const deleteRule = async (rule) => {
    if (!confirm(`Delete rule "${rule.name}"?`)) {
      return;
    }
    setError(null);
    setSuccess(null);
    try {
      // For SmartLPG tenant, delete from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { deleteDeviceRuleFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        await deleteDeviceRuleFromFirebase(rule.id);
        setSuccess("Rule deleted");
        loadRules();
        return;
      }
      
      await api.delete(`/admin/devices/${deviceId}/rules/${rule.id}`);
      setSuccess("Rule deleted");
      loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete rule");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      {/* Rules List Card */}
      <div className="card">
        <div className="card__header">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <Icon name="code" size={20} />
            <h3 className="card__title">Rule Engine</h3>
          </div>
          <div className="card__header-actions">
            <button 
              type="button" 
              className="btn btn--secondary btn--sm" 
              onClick={loadRules} 
              disabled={isLoading}
            >
              <Icon name="refresh" size={16} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
        <div className="card__body">
          <p style={{ color: "var(--color-text-secondary)", marginBottom: "var(--space-4)" }}>
            Define per-device automation and routing
          </p>
          
          {error && (
            <div className="badge badge--error" style={{ display: "block", padding: "var(--space-3)", marginBottom: "var(--space-4)" }}>
              {error}
            </div>
          )}
          {success && (
            <div className="badge badge--success" style={{ display: "block", padding: "var(--space-3)", marginBottom: "var(--space-4)" }}>
              {success}
            </div>
          )}
          
          {isLoading ? (
            <div style={{ textAlign: "center", padding: "var(--space-8)", color: "var(--color-text-secondary)" }}>
              <Icon name="activity" size={32} />
              <p style={{ marginTop: "var(--space-3)" }}>Loading rules…</p>
            </div>
          ) : rules.length === 0 ? (
            <div style={{ textAlign: "center", padding: "var(--space-8)", color: "var(--color-text-tertiary)" }}>
              <Icon name="code" size={48} style={{ opacity: 0.3, marginBottom: "var(--space-3)" }} />
              <p style={{ marginBottom: "var(--space-2)" }}>No rules configured yet.</p>
              <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>
                Create your first rule using the form below to automate device behavior.
              </p>
            </div>
          ) : (
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Priority</th>
                    <th>Action</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id}>
                      <td style={{ fontWeight: "var(--font-weight-medium)" }}>{rule.name}</td>
                      <td>{rule.priority}</td>
                      <td>{describeAction(rule.action)}</td>
                      <td>
                        <span className={`badge ${rule.is_active ? "badge--success" : "badge--neutral"}`}>
                          <span className="badge__dot"></span>
                          {rule.is_active ? "Active" : "Paused"}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "var(--space-2)" }}>
                          <button 
                            type="button" 
                            className="btn btn--sm btn--ghost" 
                            onClick={() => toggleRule(rule)}
                          >
                            {rule.is_active ? "Disable" : "Enable"}
                          </button>
                          <button 
                            type="button" 
                            className="btn btn--sm btn--danger" 
                            onClick={() => deleteRule(rule)}
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
      </div>

      {/* Create Rule Form Modal */}
      {showModal && (
        <div 
          className="modal-overlay" 
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget && setShowModal) {
              setShowModal(false);
            }
          }}
        >
          <div 
            className="card" 
            style={{
              maxWidth: "800px",
              width: "90%",
              maxHeight: "90vh",
              overflowY: "auto",
              margin: "var(--space-6)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card__header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <Icon name="plus" size={20} />
                <h3 className="card__title">Create Rule</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowModal && setShowModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--color-text-primary)",
                  cursor: "pointer",
                  padding: "var(--space-2)",
                  fontSize: "var(--font-size-lg)",
                }}
              >
                <Icon name="x" size={20} />
              </button>
            </div>
            <form className="form" onSubmit={handleCreateRule} style={{ padding: "var(--space-6)" }}>
          <div className="form-group">
            <label className="form-label form-label--required">Name</label>
            <input
              type="text"
              className="form-input"
              value={formState.name}
              onChange={(event) => handleInputChange("name", event.target.value)}
              placeholder="High temperature route"
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Priority</label>
            <input
              type="number"
              className="form-input"
              value={formState.priority}
              onChange={(event) => handleInputChange("priority", event.target.value)}
              min={1}
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">
              <input
                type="checkbox"
                checked={formState.is_active}
                onChange={(event) => handleInputChange("is_active", event.target.checked)}
                style={{ marginRight: "var(--space-2)", cursor: "pointer" }}
              />
              Active
            </label>
          </div>
          
          <div className="form-group">
            <label className="form-label form-label--required">When field</label>
            <select
              className="form-select"
              value={formState.conditionFieldChoice}
              onChange={(event) => handleFieldChoice(event.target.value)}
            >
              {fieldOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
              <option value={CUSTOM_FIELD_VALUE}>Custom field…</option>
            </select>
          </div>
          
          {formState.conditionFieldChoice === CUSTOM_FIELD_VALUE && (
            <div className="form-group">
              <label className="form-label form-label--required">Custom field name</label>
              <input
                type="text"
                className="form-input"
                value={formState.conditionFieldCustom}
                placeholder="payload.temperature"
                onChange={(event) => handleInputChange("conditionFieldCustom", event.target.value)}
                required
              />
            </div>
          )}
          
          <div className="form-group">
            <label className="form-label form-label--required">Operator</label>
            <select
              className="form-select"
              value={formState.conditionOperator}
              onChange={(event) => handleInputChange("conditionOperator", event.target.value)}
            >
              <option value=">">&gt;</option>
              <option value=">=">&gt;=</option>
              <option value="<">&lt;</option>
              <option value="<=">&lt;=</option>
              <option value="==">Equals</option>
              <option value="!=">Not equals</option>
              <option value="contains">Contains</option>
              <option value="starts_with">Starts with</option>
              <option value="ends_with">Ends with</option>
            </select>
          </div>
          
          <div className="form-group">
            <label className="form-label form-label--required">Compare to</label>
            <input
              type="text"
              className="form-input"
              value={formState.conditionValue}
              onChange={(event) => handleInputChange("conditionValue", event.target.value)}
              required
            />
          </div>
          
          <div className="form-group">
            <label className="form-label form-label--required">Action</label>
            <select
              className="form-select"
              value={formState.actionPreset}
              onChange={(event) => handleInputChange("actionPreset", event.target.value)}
            >
              {actionPresets.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          {formState.actionPreset === "alert" && (
            <>
              <div className="form-group">
                <label className="form-label form-label--required">Alert Title</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.alertTitle || ""}
                  placeholder="High Temperature Alert"
                  onChange={(event) => handleInputChange("alertTitle", event.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Alert Message</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.alertMessage || ""}
                  placeholder="Temperature exceeded threshold"
                  onChange={(event) => handleInputChange("alertMessage", event.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Priority</label>
                <select
                  className="form-select"
                  value={formState.alertPriority || "medium"}
                  onChange={(event) => handleInputChange("alertPriority", event.target.value)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </>
          )}
          {formState.actionPreset === "device_command" && (
            <>
              <div className="form-group">
                <label className="form-label form-label--required">Command (JSON or simple string)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.deviceCommand || ""}
                  placeholder='{"action": "reboot"} or "reboot"'
                  onChange={(event) => handleInputChange("deviceCommand", event.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">MQTT Topic (optional, defaults to devices/{deviceId}/commands)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.deviceCommandTopic || ""}
                  placeholder={`devices/${deviceId}/commands`}
                  onChange={(event) => handleInputChange("deviceCommandTopic", event.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">QoS</label>
                <select
                  className="form-select"
                  value={formState.deviceCommandQos || 1}
                  onChange={(event) => handleInputChange("deviceCommandQos", parseInt(event.target.value))}
                >
                  <option value={0}>0 - At most once</option>
                  <option value={1}>1 - At least once</option>
                  <option value={2}>2 - Exactly once</option>
                </select>
              </div>
            </>
          )}
          {formState.actionPreset === "webhook" && (
            <>
              <div className="form-group">
                <label className="form-label form-label--required">Webhook URL</label>
                <input
                  type="url"
                  className="form-input"
                  value={formState.webhookUrl || ""}
                  placeholder="https://example.com/webhook"
                  onChange={(event) => handleInputChange("webhookUrl", event.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">HTTP Method</label>
                <select
                  className="form-select"
                  value={formState.webhookMethod || "POST"}
                  onChange={(event) => handleInputChange("webhookMethod", event.target.value)}
                >
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                  <option value="GET">GET</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Headers (JSON, optional)</label>
                <textarea
                  className="form-input"
                  value={formState.webhookHeaders || ""}
                  placeholder='{"Authorization": "Bearer token"}'
                  onChange={(event) => handleInputChange("webhookHeaders", event.target.value)}
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Body (JSON, optional - use {'{{'}field.path{'}}'} for variables)</label>
                <textarea
                  className="form-input"
                  value={formState.webhookBody || ""}
                  placeholder='{"device": "{{device.device_id}}", "value": "{{payload.temperature}}"}'
                  onChange={(event) => handleInputChange("webhookBody", event.target.value)}
                  rows={3}
                />
              </div>
            </>
          )}
          {formState.actionPreset === "flag_warning" && (
            <div className="form-group">
              <label className="form-label">Status label</label>
              <input
                type="text"
                className="form-input"
                value={formState.flagStatus}
                onChange={(event) => handleInputChange("flagStatus", event.target.value)}
              />
            </div>
          )}
          {formState.actionPreset === "custom_route" && (
            <div className="form-group">
              <label className="form-label form-label--required">Feed / topic name</label>
              <input
                type="text"
                className="form-input"
                value={formState.customRouteTopic}
                placeholder="alerts.low_pressure"
                onChange={(event) => handleInputChange("customRouteTopic", event.target.value)}
                required
              />
            </div>
          )}
          {formState.actionPreset === "custom_mutate" && (
            <>
              <div className="form-group">
                <label className="form-label form-label--required">Field to update</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.customMutateField}
                  placeholder="payload.status"
                  onChange={(event) => handleInputChange("customMutateField", event.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label form-label--required">New value</label>
                <input
                  type="text"
                  className="form-input"
                  value={formState.customMutateValue}
                  onChange={(event) => handleInputChange("customMutateValue", event.target.value)}
                  required
                />
              </div>
            </>
          )}
          <div className="form-group">
            <label className="form-label">Rule Type</label>
            <select
              className="form-select"
              value={formState.ruleType}
              onChange={(event) => handleInputChange("ruleType", event.target.value)}
            >
              <option value="event">Event-based (real-time)</option>
              <option value="scheduled">Scheduled (cron-based)</option>
            </select>
          </div>
          {formState.ruleType === "scheduled" && (
            <div className="form-group">
              <label className="form-label form-label--required">Cron Schedule</label>
              <input
                type="text"
                className="form-input"
                value={formState.cronSchedule}
                placeholder="0 */5 * * * (every 5 minutes)"
                onChange={(event) => handleInputChange("cronSchedule", event.target.value)}
                required
              />
              <small style={{ display: "block", marginTop: "var(--space-1)", color: "var(--color-text-tertiary)", fontSize: "var(--font-size-xs)" }}>
                Format: minute hour day month weekday (e.g., "0 */5 * * *" = every 5 minutes)
              </small>
            </div>
          )}
          <div className="form-group">
            <label className="form-label">
              <input
                type="checkbox"
                checked={formState.stopAfter}
                onChange={(event) => handleInputChange("stopAfter", event.target.checked)}
                style={{ marginRight: "var(--space-2)", cursor: "pointer" }}
              />
              Stop evaluating additional rules
            </label>
          </div>
          
              <div className="form-actions" style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end", marginTop: "var(--space-6)" }}>
                <button 
                  type="button" 
                  className="btn btn--secondary"
                  onClick={() => setShowModal && setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn--primary">
                  <Icon name="plus" size={18} />
                  <span>Add Rule</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function coerceValue(raw) {
  if (raw === undefined || raw === null) {
    return raw;
  }
  const trimmed = String(raw).trim();
  if (trimmed === "") {
    return "";
  }
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  const asNumber = Number(trimmed);
  if (!Number.isNaN(asNumber)) {
    return asNumber;
  }
  return trimmed;
}

function extractFieldOptions(deviceType) {
  const schema = deviceType?.schema_definition;
  const fields = [];
  if (schema && typeof schema === "object") {
    flattenSchema(schema, "payload", fields);
  }
  if (fields.length === 0) {
    fields.push(
      { label: "Liquid level (payload.level)", value: "payload.level" },
      { label: "Temperature (payload.temperature)", value: "payload.temperature" },
      { label: "Status (payload.status)", value: "payload.status" },
    );
  }
  return fields;
}

function flattenSchema(node, prefix, collector) {
  if (!node || typeof node !== "object") {
    return;
  }
  if (node.type === "object" && node.properties) {
    Object.entries(node.properties).forEach(([key, child]) => {
      const newPrefix = `${prefix}.${key}`;
      flattenSchema(child, newPrefix, collector);
    });
  } else {
    collector.push({
      label: `${humanize(prefix)} (${prefix})`,
      value: prefix,
    });
  }
}

function humanize(value) {
  return value
    .split(".")
    .slice(-1)[0]
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function describeAction(action) {
  if (!action) {
    return "—";
  }
  switch (action.type) {
    case "route":
      return `Alert → ${action.topic || "alerts"}`;
    case "drop":
      return "Ignore reading";
    case "mutate": {
      const target = action.set ? Object.keys(action.set)[0] : "payload";
      return `Update ${target}`;
    }
    default:
      return action.type;
  }
}


