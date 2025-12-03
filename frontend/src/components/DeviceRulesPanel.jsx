import { useEffect, useState } from "react";

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
  alertTopic: "alerts.high_temperature",
  alertMessage: "Notify operators",
  flagStatus: "ALERT",
  customRouteTopic: "",
  customMutateField: "payload.status",
  customMutateValue: "ALERT",
  stopAfter: true,
};

const actionPresets = [
  { value: "alert", label: "Send alert notification" },
  { value: "ignore", label: "Ignore this reading" },
  { value: "flag_warning", label: "Mark device as warning" },
  { value: "close_valve", label: "Close the valve" },
  { value: "open_valve", label: "Open the valve" },
  { value: "custom_route", label: "Advanced: send to another feed" },
  { value: "custom_mutate", label: "Advanced: set a field value" },
];

export default function DeviceRulesPanel({ api, deviceId, deviceType }) {
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
    const options = extractFieldOptions(deviceType);
    setFieldOptions(options);
    setFormState((prev) => ({
      ...prev,
      conditionFieldChoice: options[0]?.value || CUSTOM_FIELD_VALUE,
    }));
  }, [deviceType?.id]);

  const loadRules = async () => {
    if (!deviceId) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.get(`/admin/devices/${deviceId}/rules`);
      setRules(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load rules");
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
          type: "route",
          topic: (formState.alertTopic || `alerts.${deviceId}`).trim(),
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
      const action = buildAction();
      await api.post(`/admin/devices/${deviceId}/rules`, {
        name: formState.name || "Untitled rule",
        priority: Number(formState.priority) || 100,
        is_active: Boolean(formState.is_active),
        condition,
        action,
      });
      setSuccess("Rule created");
      setFormState((prev) => ({
        ...initialFormState,
        conditionFieldChoice: fieldOptions[0]?.value || CUSTOM_FIELD_VALUE,
      }));
      loadRules();
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
      await api.delete(`/admin/devices/${deviceId}/rules/${rule.id}`);
      setSuccess("Rule deleted");
      loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete rule");
    }
  };

  return (
    <section className="rules-panel">
      <div className="rules-panel__content">
        <div className="rules-card">
          <div className="section-header">
            <div>
              <h3>Rule Engine</h3>
              <p className="muted">Define per-device automation and routing</p>
            </div>
            <button type="button" className="secondary" onClick={loadRules} disabled={isLoading}>
              Refresh
            </button>
          </div>
          {error && <p className="error-message">{error}</p>}
          {success && <p className="success-message">{success}</p>}
          {isLoading ? (
            <p>Loading rules…</p>
          ) : rules.length === 0 ? (
            <p className="muted">No rules configured yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Priority</th>
                  <th>Action</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rules.map((rule) => (
                  <tr key={rule.id}>
                    <td>{rule.name}</td>
                    <td>{rule.priority}</td>
                    <td>{describeAction(rule.action)}</td>
                    <td>
                      <span className={`status ${rule.is_active ? "status--ok" : "status--off"}`}>
                        {rule.is_active ? "Active" : "Paused"}
                      </span>
                    </td>
                    <td className="table-actions">
                      <button type="button" className="secondary" onClick={() => toggleRule(rule)}>
                        {rule.is_active ? "Disable" : "Enable"}
                      </button>
                      <button type="button" className="danger" onClick={() => deleteRule(rule)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
      <form className="rules-form card form" onSubmit={handleCreateRule}>
        <h4>Create Rule</h4>
          <label>
            Name
            <input
              type="text"
              value={formState.name}
              onChange={(event) => handleInputChange("name", event.target.value)}
              placeholder="High temperature route"
              required
            />
          </label>
          <label>
            Priority
            <input
              type="number"
              value={formState.priority}
              onChange={(event) => handleInputChange("priority", event.target.value)}
              min={1}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={formState.is_active}
              onChange={(event) => handleInputChange("is_active", event.target.checked)}
            />
            Active
          </label>
          <div className="field-picker">
            <label>
              When field
              <select
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
            </label>
            {formState.conditionFieldChoice === CUSTOM_FIELD_VALUE && (
              <label>
                Custom field name
                <input
                  type="text"
                  value={formState.conditionFieldCustom}
                  placeholder="payload.temperature"
                  onChange={(event) => handleInputChange("conditionFieldCustom", event.target.value)}
                  required
                />
              </label>
            )}
          </div>
          <label>
            Operator
            <select
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
          </label>
          <label>
            Compare to
            <input
              type="text"
              value={formState.conditionValue}
              onChange={(event) => handleInputChange("conditionValue", event.target.value)}
              required
            />
          </label>
          <label>
            Action
            <select
              value={formState.actionPreset}
              onChange={(event) => handleInputChange("actionPreset", event.target.value)}
            >
              {actionPresets.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {formState.actionPreset === "alert" && (
            <>
              <label>
                Alert feed
                <input
                  type="text"
                  value={formState.alertTopic}
                  placeholder="alerts.high_temperature"
                  onChange={(event) => handleInputChange("alertTopic", event.target.value)}
                />
              </label>
              <label>
                Alert note
                <input
                  type="text"
                  value={formState.alertMessage}
                  placeholder="Example: Notify on-call engineer"
                  onChange={(event) => handleInputChange("alertMessage", event.target.value)}
                />
              </label>
            </>
          )}
          {formState.actionPreset === "flag_warning" && (
            <label>
              Status label
              <input
                type="text"
                value={formState.flagStatus}
                onChange={(event) => handleInputChange("flagStatus", event.target.value)}
              />
            </label>
          )}
          {formState.actionPreset === "custom_route" && (
            <label>
              Feed / topic name
              <input
                type="text"
                value={formState.customRouteTopic}
                placeholder="alerts.low_pressure"
                onChange={(event) => handleInputChange("customRouteTopic", event.target.value)}
                required
              />
            </label>
          )}
          {formState.actionPreset === "custom_mutate" && (
            <>
              <label>
                Field to update
                <input
                  type="text"
                  value={formState.customMutateField}
                  placeholder="payload.status"
                  onChange={(event) => handleInputChange("customMutateField", event.target.value)}
                  required
                />
              </label>
              <label>
                New value
                <input
                  type="text"
                  value={formState.customMutateValue}
                  onChange={(event) => handleInputChange("customMutateValue", event.target.value)}
                  required
                />
              </label>
            </>
          )}
          <label className="checkbox">
            <input
              type="checkbox"
              checked={formState.stopAfter}
              onChange={(event) => handleInputChange("stopAfter", event.target.checked)}
            />
            Stop evaluating additional rules
          </label>
        <button type="submit">Add Rule</button>
      </form>
    </section>
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


