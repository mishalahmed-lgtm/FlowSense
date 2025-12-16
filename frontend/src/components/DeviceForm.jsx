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

  const currentDeviceType = deviceTypes.find((dt) => dt.id === Number(formState.device_type_id));
  const currentProtocol = currentDeviceType?.protocol;

  const handleChange = (field, value) => {
    setFormState((prev) => ({ ...prev, [field]: value }));
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

  const submitForm = (event) => {
    event.preventDefault();
    onSubmit({
      ...formState,
      device_type_id: Number(formState.device_type_id),
      tenant_id: Number(formState.tenant_id),
    });
  };

  return (
    <form className="card form" onSubmit={submitForm}>
      <h3>{initialDevice ? "Edit Device" : "Create Device"}</h3>
      <label>
        Device ID
        <input
          type="text"
          value={formState.device_id}
          disabled={Boolean(initialDevice)}
          onChange={(event) => handleChange("device_id", event.target.value)}
          required
        />
      </label>
      <label>
        Name
        <input
          type="text"
          value={formState.name}
          onChange={(event) => handleChange("name", event.target.value)}
        />
      </label>
      <label>
        Device Type
        <select
          value={formState.device_type_id}
          onChange={(event) => handleChange("device_type_id", event.target.value)}
          required
        >
          <option value="">Select type</option>
          {deviceTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name} ({type.protocol})
            </option>
          ))}
        </select>
      </label>
      {userTenantId ? (
        // Tenant admins - hide tenant selector, auto-set their tenant_id
        <input type="hidden" value={userTenantId} />
      ) : (
        // Admins - show tenant selector
        <label>
          Tenant
          <select
            value={formState.tenant_id}
            onChange={(event) => handleChange("tenant_id", event.target.value)}
            required
          >
            <option value="">Select tenant</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="checkbox">
        <input
          type="checkbox"
          checked={formState.is_active}
          onChange={(event) => handleChange("is_active", event.target.checked)}
        />
        Active
      </label>

      {currentProtocol && (
        <ProtocolFields
          protocol={currentProtocol}
          metadata={formState.metadata}
          onChange={handleMetadataChange}
        />
      )}

      <div className="form-actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit">{initialDevice ? "Save Changes" : "Create Device"}</button>
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
      tenant_id: userTenantId || "", // Auto-set tenant_id for tenant admins
      is_active: true,
      metadata: cloneMetadata(),
    };
  }

  return {
    device_id: device.device_id,
    name: device.name || "",
    device_type_id: device.device_type_id || device.device_type?.id || "",
    tenant_id: device.tenant_id || userTenantId || "",
    is_active: device.is_active,
    metadata: cloneMetadata(device.metadata),
  };
}


