import { useEffect, useState } from "react";
import ProtocolFields from "./ProtocolFields.jsx";

const baseMetadata = {
  http_settings: {
    payload_mode: "default",
    payload_template: "",
    rate_limit: 120,
  },
  mqtt_settings: {},
  tcp_settings: {},
  extras: {},
};

const cloneMetadata = (metadata = {}) =>
  JSON.parse(JSON.stringify({ ...baseMetadata, ...metadata }));

export default function DeviceForm({
  initialDevice,
  deviceTypes,
  tenants,
  userTenantId,
  onSubmit,
  onCancel,
}) {
  const [formState, setFormState] = useState(() => buildInitialState(initialDevice, userTenantId));

  useEffect(() => {
    setFormState(buildInitialState(initialDevice, userTenantId));
  }, [initialDevice, userTenantId]);

  // Get unique protocols (only the ones user wants)
  const allowedProtocols = ['MQTT', 'HTTP', 'TCP', 'LoRaWAN', 'DALI', 'Modbus_TCP'];
  const protocolDisplayMap = {
    'Modbus_TCP': 'Modbus'
  };
  
  const uniqueProtocols = [...new Set(deviceTypes
    .filter(dt => allowedProtocols.includes(dt.protocol))
    .map(dt => dt.protocol)
  )].sort();

  // Map protocol to device type ID (prefer generic device types like "MQTT", "HTTP", "TCP" over specific ones)
  const protocolToDeviceTypeId = {};
  const genericDeviceTypeNames = ['MQTT', 'HTTP', 'TCP', 'LoRaWAN', 'DALI', 'Modbus_TCP'];
  
  // First pass: find generic device types
  deviceTypes.forEach(dt => {
    if (allowedProtocols.includes(dt.protocol) && genericDeviceTypeNames.includes(dt.name)) {
      protocolToDeviceTypeId[dt.protocol] = dt.id;
    }
  });
  
  // Second pass: fill in any missing protocols with first available device type
  deviceTypes.forEach(dt => {
    if (allowedProtocols.includes(dt.protocol) && !protocolToDeviceTypeId[dt.protocol]) {
      protocolToDeviceTypeId[dt.protocol] = dt.id;
    }
  });

  const currentDeviceType = deviceTypes.find((dt) => dt.id === Number(formState.device_type_id));
  const currentProtocol = currentDeviceType?.protocol;

  const handleChange = (field, value) => {
    if (field === 'protocol') {
      // When protocol is selected, automatically set the device_type_id
      const deviceTypeId = protocolToDeviceTypeId[value] || '';
      setFormState((prev) => ({ 
        ...prev, 
        protocol: value,
        device_type_id: deviceTypeId 
      }));
    } else {
      setFormState((prev) => ({ ...prev, [field]: value }));
    }
  };

  const handleMetadataChange = (group, data) => {
    setFormState((prev) => ({
      ...prev,
      metadata: {
        ...prev.metadata,
        [group]: data,
      },
    }));
  };

  const handleAccessTokenChange = (value) => {
    setFormState((prev) => ({
      ...prev,
      metadata: {
        ...prev.metadata,
        access_token: value,
      },
    }));
  };

  const submitForm = (event) => {
    event.preventDefault();
    
    // Validate access token is provided
    if (!formState.metadata?.access_token || formState.metadata.access_token.trim() === "") {
      alert("Access Token is required. Please enter an access token for secure device connection.");
      return;
    }
    
    onSubmit({
      ...formState,
      device_type_id: Number(formState.device_type_id),
      tenant_id: Number(userTenantId || formState.tenant_id),
      is_active: formState.is_active, // Use the checkbox value (defaults to false)
    });
  };

  return (
    <form className="form" onSubmit={submitForm}>
      <div className="form-group">
        <label className="form-label form-label--required">Device ID</label>
        <input
          type="text"
          className="form-input"
          value={formState.device_id}
          disabled={Boolean(initialDevice)}
          onChange={(event) => handleChange("device_id", event.target.value)}
          placeholder="Enter unique device identifier"
          required
        />
      </div>

      <div className="form-group">
        <label className="form-label">Name</label>
        <input
          type="text"
          className="form-input"
          value={formState.name}
          onChange={(event) => handleChange("name", event.target.value)}
          placeholder="Enter device name (optional)"
        />
      </div>

      <div className="form-group">
        <label className="form-label form-label--required">Protocol</label>
        <select
          className="form-select"
          value={currentProtocol || ""}
          onChange={(event) => handleChange("protocol", event.target.value)}
          required
        >
          <option value="">Select protocol...</option>
          {uniqueProtocols.map((protocol) => (
            <option key={protocol} value={protocol}>
              {protocolDisplayMap[protocol] || protocol}
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label form-label--required">Access Token</label>
        <input
          type="text"
          className="form-input"
          value={formState.metadata?.access_token || ""}
          onChange={(event) => handleAccessTokenChange(event.target.value)}
          placeholder="Enter access token for secure connection"
          required
        />
        <small style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", marginTop: "var(--space-1)", display: "block" }}>
          Required: Token for device authentication. Devices must include this token when connecting.
        </small>
      </div>

      {userTenantId ? (
        <>
          {/* Hide tenant selector for tenant users and lock to their tenant */}
          <input type="hidden" value={userTenantId} />
        </>
      ) : (
        <div className="form-group">
          <label className="form-label form-label--required">Tenant</label>
          <select
            className="form-select"
            value={formState.tenant_id}
            onChange={(event) => handleChange("tenant_id", event.target.value)}
            required
          >
            <option value="">Select tenant...</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-4)",
          backgroundColor: "var(--color-bg-secondary)",
          borderRadius: "var(--radius-lg)",
        }}
      >
        <input
          type="checkbox"
          id="device-active"
          checked={formState.is_active}
          onChange={(event) => handleChange("is_active", event.target.checked)}
          style={{ cursor: "pointer" }}
        />
        <label
          htmlFor="device-active"
          style={{
            cursor: "pointer",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-primary)",
            margin: 0,
          }}
        >
          Device is active
        </label>
      </div>

      {currentProtocol && (
        <ProtocolFields
          protocol={currentProtocol}
          metadata={formState.metadata}
          onChange={handleMetadataChange}
        />
      )}

      <div className="modal__footer">
        <button type="button" className="btn btn--secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className="btn btn--primary">
          {initialDevice ? "Save Changes" : "Create Device"}
        </button>
      </div>
    </form>
  );
}

function buildInitialState(device, userTenantId) {
  if (!device) {
    return {
      device_id: "",
      name: "",
      device_type_id: "",
      protocol: "",
      tenant_id: userTenantId || "", // Auto-set tenant_id for tenant admins
      is_active: false, // Default to inactive
      metadata: cloneMetadata(),
    };
  }

  return {
    device_id: device.device_id,
    name: device.name || "",
    device_type_id: device.device_type_id || device.device_type?.id || "",
    protocol: device.device_type?.protocol || "",
    tenant_id: device.tenant_id || userTenantId || "",
    is_active: device.is_active ?? false, // Default to false if not set
    metadata: cloneMetadata(device.metadata),
  };
}


