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
  TCP: [
    { group: "tcp_settings", name: "parser", label: "Parser", placeholder: "dingtek_dc41x" },
    { group: "tcp_settings", name: "notes", label: "Notes", type: "textarea" },
  ],
  TCP_HEX: [
    { group: "tcp_settings", name: "parser", label: "Parser", placeholder: "dingtek_dc41x" },
    { group: "tcp_settings", name: "notes", label: "Notes", type: "textarea" },
  ],
  "NB-IOT": [
    { group: "nbiot_settings", name: "apn", label: "APN", placeholder: "internet" },
    { group: "nbiot_settings", name: "band", label: "Band", placeholder: "B20" },
  ],
  "NB-IOT/CAT-M1": [
    { group: "nbiot_settings", name: "apn", label: "APN", placeholder: "internet" },
    { group: "nbiot_settings", name: "band", label: "Band", placeholder: "B20" },
  ],
  LORAWAN: [
    { group: "lorawan_settings", name: "dev_eui", label: "DevEUI", placeholder: "0000000000000000" },
    { group: "lorawan_settings", name: "app_key", label: "App Key", placeholder: "00000000000000000000000000000000" },
    { group: "lorawan_settings", name: "frequency_plan", label: "Frequency Plan", placeholder: "EU868" },
  ],
  DALI: [
    { group: "dali_settings", name: "bus_address", label: "Bus Address", placeholder: "0-63" },
    { group: "dali_settings", name: "group_address", label: "Group Address", placeholder: "0-15" },
  ],
  MODBUS_TCP: [
    { group: "modbus_settings", name: "slave_id", label: "Slave ID", placeholder: "1" },
    { group: "modbus_settings", name: "register_map", label: "Register Map", type: "textarea", placeholder: "JSON register mapping" },
  ],
  COAP: [
    { group: "coap_settings", name: "server_uri", label: "Server URI", placeholder: "coap://example.com" },
    { group: "coap_settings", name: "port", label: "Port", placeholder: "5683" },
  ],
  WEBSOCKET: [
    { group: "websocket_settings", name: "server_url", label: "Server URL", placeholder: "ws://example.com:8080" },
    { group: "websocket_settings", name: "reconnect_interval", label: "Reconnect Interval (ms)", type: "number", placeholder: "5000" },
  ],
};

export default function ProtocolFields({ protocol, metadata, onChange }) {
  if (!protocol) {
    return null;
  }

  // Normalize protocol name (handle variations like "NB-IoT" vs "NB-IOT")
  const normalizedProtocol = protocol.toUpperCase().replace(/[-\s]/g, '');
  const protocolVariations = [
    protocol, // Original
    protocol.toUpperCase(), // Uppercase
    normalizedProtocol, // Normalized
    protocol.replace(/[-\s]/g, '_'), // With underscores
    protocol.replace(/[-\s]/g, ''), // No dashes/spaces
  ];

  // Try to find fields using various protocol name formats
  let fields = null;
  for (const variant of protocolVariations) {
    if (protocolFieldConfig[variant]) {
      fields = protocolFieldConfig[variant];
      break;
    }
  }

  // Also try direct lookup with common variations
  if (!fields) {
    const protocolMap = {
      'NB-IOT': 'NB-IOT',
      'NB-IOT/CAT-M1': 'NB-IOT/CAT-M1',
      'NB-IoT': 'NB-IOT',
      'NB-IoT/CAT-M1': 'NB-IOT/CAT-M1',
      'LORAWAN': 'LORAWAN',
      'LoRaWAN': 'LORAWAN',
      'MODBUS_TCP': 'MODBUS_TCP',
      'Modbus_TCP': 'MODBUS_TCP',
      'Modbus TCP': 'MODBUS_TCP',
      'COAP': 'COAP',
      'CoAP': 'COAP',
      'WEBSOCKET': 'WEBSOCKET',
      'WebSocket': 'WEBSOCKET',
    };
    const mappedProtocol = protocolMap[protocol] || protocol;
    fields = protocolFieldConfig[mappedProtocol];
  }

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


