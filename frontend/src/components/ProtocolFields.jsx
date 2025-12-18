const protocolFieldConfig = {
  HTTP: [
    {
      group: "http_settings",
      name: "payload_mode",
      label: "Payload Template",
      type: "select",
      options: [
        { label: "Use default JSON", value: "default" },
        { label: "Provide custom JSON", value: "custom" },
      ],
    },
    {
      group: "http_settings",
      name: "payload_template",
      label: "Custom JSON (optional)",
      type: "textarea",
      placeholder: '{"device_id":"{{device_id}}","data":{{payload}}}',
      condition: (groupData) => groupData.payload_mode === "custom",
    },
    {
      group: "http_settings",
      name: "rate_limit",
      label: "Max msgs / min",
      type: "number",
      min: 1,
    },
  ],
  MQTT: [
    { group: "mqtt_settings", name: "topic", label: "Topic Pattern", placeholder: "devices/+/telemetry" },
    { group: "mqtt_settings", name: "qos", label: "QoS", type: "number" },
    { group: "mqtt_settings", name: "broker", label: "Broker Override", placeholder: "mqtt.example.com:1883" },
  ],
  TCP_HEX: [
    { group: "tcp_settings", name: "parser", label: "Parser", placeholder: "dingtek_dc41x" },
    { group: "tcp_settings", name: "notes", label: "Notes", type: "textarea" },
  ],
};

export default function ProtocolFields({ protocol, metadata, onChange }) {
  const fields = protocolFieldConfig[protocol];

  if (!fields) {
    return null;
  }

  const handleFieldChange = (group, name, value) => {
    const updatedGroup = { ...(metadata[group] || {}), [name]: value };
    onChange(group, updatedGroup);
  };

  const renderField = (field) => {
    const groupData = metadata[field.group] || {};
    if (field.condition && !field.condition(groupData)) {
      return null;
    }

    const currentValue = groupData[field.name] ?? "";
    const inputId = `${field.group}-${field.name}`;

    const commonProps = {
      value: currentValue,
      placeholder: field.placeholder,
      onChange: (event) => handleFieldChange(field.group, field.name, event.target.value),
    };

    if (field.type === "textarea") {
      return (
        <div className="form-group" key={`${field.group}.${field.name}`}>
          <label className="form-label" htmlFor={inputId}>
            {field.label}
          </label>
          <textarea id={inputId} className="form-textarea" {...commonProps} />
        </div>
      );
    }

    if (field.type === "select") {
      return (
        <div className="form-group" key={`${field.group}.${field.name}`}>
          <label className="form-label" htmlFor={inputId}>
            {field.label}
          </label>
          <select id={inputId} className="form-select" {...commonProps}>
            {field.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      );
    }

    return (
      <div className="form-group" key={`${field.group}.${field.name}`}>
        <label className="form-label" htmlFor={inputId}>
          {field.label}
        </label>
        <input
          id={inputId}
          className="form-input"
          type={field.type || "text"}
          min={field.min}
          {...commonProps}
        />
      </div>
    );
  };

  return (
    <div className="protocol-fields">
      <h4 className="protocol-fields__title">{protocol} Settings</h4>
      <div className={protocol === "MQTT" ? "form-grid" : "form"}>
        {fields.map(renderField)}
      </div>
    </div>
  );
}


