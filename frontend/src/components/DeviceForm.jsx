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
      tenant_id: Number(userTenantId || formState.tenant_id),
      // For tenant users, always keep devices active
      is_active: userTenantId ? true : formState.is_active,
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
        <label className="form-label form-label--required">Device Type</label>
        <select
          className="form-select"
          value={formState.device_type_id}
          onChange={(event) => handleChange("device_type_id", event.target.value)}
          required
        >
          <option value="">Select device type...</option>
          {deviceTypes.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name} ({type.protocol})
            </option>
          ))}
        </select>
      </div>

      {userTenantId ? (
        <>
          {/* Hide tenant selector for tenant users and lock to their tenant */}
          <input type="hidden" value={userTenantId} />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              padding: "var(--space-4)",
              backgroundColor: "var(--color-bg-secondary)",
              borderRadius: "var(--radius-lg)",
              marginTop: "var(--space-2)",
            }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "999px",
                backgroundColor: "var(--color-success-text)",
              }}
            ></span>
            <span
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-primary)",
              }}
            >
              Device will be active for your tenant
            </span>
          </div>
        </>
      ) : (
        <>
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
        </>
      )}

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


