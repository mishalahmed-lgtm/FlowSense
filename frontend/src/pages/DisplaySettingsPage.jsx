import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext.jsx";
import { isSmartLPGTenant } from "../utils/tenantHelpers.js";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import { createApiClient } from "../api/client.js";
import { getDisplaySettingsFromFirebase, saveDisplaySettingsToFirebase } from "../services/smartLPGFirebaseService.js";
import { fetchSmartLPGDataForDashboard } from "../services/smartLPGDataMapper.js";

const DEFAULT_FIELDS = [
  { key: "level", label: "Level", defaultDecimals: 2 },
  { key: "level_cm", label: "Level (cm)", defaultDecimals: 1 },
  { key: "lpg_tank_level", label: "LPG Tank Level", defaultDecimals: 2 },
  { key: "temperature", label: "Temperature", defaultDecimals: 1 },
  { key: "tmp", label: "Temperature (tmp)", defaultDecimals: 1 },
  { key: "pressure", label: "Pressure", defaultDecimals: 2 },
  { key: "battery", label: "Battery", defaultDecimals: 1 },
  { key: "battery_volt", label: "Battery Voltage", defaultDecimals: 2 },
  { key: "flow_rate", label: "Flow Rate", defaultDecimals: 2 },
  { key: "total_consumption", label: "Total Consumption", defaultDecimals: 2 },
  { key: "humidity", label: "Humidity", defaultDecimals: 1 },
  { key: "signal_rssi", label: "Signal RSSI", defaultDecimals: 0 },
];

export default function DisplaySettingsPage() {
  const { user, token } = useAuth();
  const api = createApiClient(token);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [selectedProtocol, setSelectedProtocol] = useState("");
  const [selectedDeviceType, setSelectedDeviceType] = useState("");
  const [deviceTypeFields, setDeviceTypeFields] = useState([]);
  const [loadingFields, setLoadingFields] = useState(false);
  const [settings, setSettings] = useState({
    fieldSettings: {},
    deviceTypeSettings: {}, // Settings per device type: { "deviceTypeName": { fieldSettings: {} } }
    defaultDecimals: 2,
  });

  useEffect(() => {
    if (!isSmartLPGTenant(user?.tenant_id)) {
      setError("Display settings are only available for SmartLPG tenant");
      setLoading(false);
      return;
    }

    loadDeviceTypes();
    loadSettings();
  }, [user?.tenant_id]);

  useEffect(() => {
    if (selectedProtocol) {
      setSelectedDeviceType(""); // Reset device type when protocol changes
      setDeviceTypeFields([]);
    }
  }, [selectedProtocol]);

  useEffect(() => {
    if (selectedDeviceType) {
      loadFieldsForDeviceType(selectedDeviceType);
    } else {
      setDeviceTypeFields([]);
    }
  }, [selectedDeviceType]);

  const loadDeviceTypes = async () => {
    try {
      // For SmartLPG, get actual device types from Firebase devices
      const firebaseData = await fetchSmartLPGDataForDashboard();
      if (firebaseData.success && firebaseData.devices) {
        // Extract unique device types from actual devices
        const deviceTypeMap = new Map();
        firebaseData.devices.forEach(device => {
          const deviceTypeName = device.device_type;
          if (deviceTypeName && deviceTypeName.trim()) {
            if (!deviceTypeMap.has(deviceTypeName)) {
              deviceTypeMap.set(deviceTypeName, {
                id: deviceTypeMap.size + 1,
                name: deviceTypeName,
                protocol: device.protocol || "NB-IoT",
                description: `${deviceTypeName} device`,
              });
            }
          }
        });
        
        const actualDeviceTypes = Array.from(deviceTypeMap.values());
        setDeviceTypes(actualDeviceTypes);
        console.log(`✅ Loaded ${actualDeviceTypes.length} device types from Firebase devices:`, actualDeviceTypes.map(dt => dt.name));
        
        // Also get protocols from backend API for protocol dropdown
        try {
          const response = await api.get("/admin/device-types");
          if (response.data && Array.isArray(response.data)) {
            // Protocols are already extracted from device types above
            return;
          }
        } catch (apiErr) {
          console.warn("Failed to load device types from API:", apiErr);
        }
      } else {
        // Fallback: try API
        const response = await api.get("/admin/device-types");
        if (response.data && Array.isArray(response.data)) {
          setDeviceTypes(response.data);
          console.log(`✅ Loaded ${response.data.length} device types from API`);
        }
      }
    } catch (err) {
      console.error("Failed to load device types:", err);
      // Use defaults if everything fails
      setDeviceTypes([
        { id: 1, name: "Tekelek", protocol: "NB-IoT", description: "Tekelek LPG meter" },
        { id: 2, name: "ASCO", protocol: "NB-IoT", description: "ASCO valve" },
        { id: 3, name: "HTTP", protocol: "HTTP", description: "Generic HTTP device" },
        { id: 4, name: "MQTT", protocol: "MQTT", description: "Generic MQTT device" },
      ]);
    }
  };

  // Get unique protocols from device types (for protocol dropdown)
  const uniqueProtocols = [...new Set(deviceTypes.map(dt => dt.protocol).filter(Boolean))].sort();
  
  // Get device types filtered by selected protocol (for device type dropdown)
  const filteredDeviceTypes = selectedProtocol 
    ? deviceTypes.filter(dt => dt.protocol === selectedProtocol)
    : deviceTypes;
  
  // Sort device types by name for better UX
  const sortedDeviceTypes = [...filteredDeviceTypes].sort((a, b) => a.name.localeCompare(b.name));

  const loadFieldsForDeviceType = async (deviceTypeName) => {
    setLoadingFields(true);
    try {
      const fields = [];
      
      // Method 1: Extract fields from device type schema_definition
      const deviceType = deviceTypes.find(dt => dt.name === deviceTypeName);
      if (deviceType?.schema_definition) {
        const schema = typeof deviceType.schema_definition === 'string' 
          ? JSON.parse(deviceType.schema_definition) 
          : deviceType.schema_definition;
        
        if (schema.properties) {
          Object.keys(schema.properties).forEach(key => {
            const prop = schema.properties[key];
            const fieldType = prop.type || 'string';
            if (fieldType === 'number' || fieldType === 'integer') {
              fields.push({
                key: key,
                label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                type: fieldType,
                defaultDecimals: fieldType === 'integer' ? 0 : 2,
              });
            }
          });
        }
      }

      // Method 2: If no schema fields, try to get fields from actual devices of this type
      if (fields.length === 0) {
        try {
          const firebaseData = await fetchSmartLPGDataForDashboard();
          if (firebaseData.success && firebaseData.devices) {
            // Find devices of this type
            const devicesOfType = firebaseData.devices.filter(d => 
              d.device_type === deviceTypeName || 
              d.device_type?.includes(deviceTypeName) ||
              deviceTypeName.includes(d.device_type)
            );
            
            // Extract unique fields from telemetry data
            const fieldSet = new Set();
            devicesOfType.forEach(device => {
              if (device.telemetry?.data) {
                Object.keys(device.telemetry.data).forEach(key => {
                  const value = device.telemetry.data[key];
                  if (value !== null && value !== undefined && typeof value !== 'object') {
                    fieldSet.add(key);
                  }
                });
              }
            });

            // Convert to field objects
            Array.from(fieldSet).forEach(key => {
              const sampleDevice = devicesOfType.find(d => d.telemetry?.data?.[key] !== undefined);
              const sampleValue = sampleDevice?.telemetry?.data?.[key];
              const isNumber = typeof sampleValue === 'number';
              
              if (isNumber) {
                fields.push({
                  key: key,
                  label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                  type: 'number',
                  defaultDecimals: Number.isInteger(sampleValue) ? 0 : 2,
                });
              }
            });
          }
        } catch (fbErr) {
          console.warn("Failed to load fields from Firebase devices:", fbErr);
        }
      }

      // If still no fields, use common defaults based on device type name
      if (fields.length === 0) {
        const deviceTypeLower = deviceTypeName.toLowerCase();
        if (deviceTypeLower.includes('lpg') || deviceTypeLower.includes('tank') || deviceTypeLower.includes('meter')) {
          fields.push(
            { key: "level", label: "Level", type: "number", defaultDecimals: 2 },
            { key: "level_cm", label: "Level (cm)", type: "number", defaultDecimals: 1 },
            { key: "lpg_tank_level", label: "LPG Tank Level", type: "number", defaultDecimals: 2 },
            { key: "temperature", label: "Temperature", type: "number", defaultDecimals: 1 },
            { key: "pressure", label: "Pressure", type: "number", defaultDecimals: 2 },
            { key: "battery", label: "Battery", type: "number", defaultDecimals: 1 },
          );
        } else if (deviceTypeLower.includes('valve')) {
          fields.push(
            { key: "state", label: "State", type: "string", defaultDecimals: 0 },
            { key: "battery", label: "Battery", type: "number", defaultDecimals: 1 },
          );
        } else if (deviceTypeLower.includes('gps') || deviceTypeLower.includes('tracker')) {
          fields.push(
            { key: "latitude", label: "Latitude", type: "number", defaultDecimals: 6 },
            { key: "longitude", label: "Longitude", type: "number", defaultDecimals: 6 },
            { key: "speed", label: "Speed", type: "number", defaultDecimals: 1 },
          );
        }
      }

      setDeviceTypeFields(fields);
      console.log(`✅ Loaded ${fields.length} fields for device type "${deviceTypeName}"`);
    } catch (err) {
      console.error("Failed to load fields for device type:", err);
      setError(err.message || "Failed to load fields");
    } finally {
      setLoadingFields(false);
    }
  };

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const savedSettings = await getDisplaySettingsFromFirebase(user.tenant_id);
      
      if (savedSettings) {
        setSettings({
          fieldSettings: savedSettings.fieldSettings || {},
          deviceTypeSettings: savedSettings.deviceTypeSettings || {},
          defaultDecimals: savedSettings.defaultDecimals || 2,
        });
      } else {
        setSettings({
          fieldSettings: {},
          deviceTypeSettings: {},
          defaultDecimals: 2,
        });
      }
    } catch (err) {
      console.error("Failed to load display settings:", err);
      setError(err.message || "Failed to load display settings");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      await saveDisplaySettingsToFirebase(user.tenant_id, settings);
      setSuccessMessage("Display settings saved successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      console.error("Failed to save display settings:", err);
      setError(err.message || "Failed to save display settings");
    } finally {
      setSaving(false);
    }
  };

  const updateFieldSetting = (fieldKey, property, value) => {
    if (selectedDeviceType) {
      // Update per-device-type settings
      setSettings(prev => ({
        ...prev,
        deviceTypeSettings: {
          ...prev.deviceTypeSettings,
          [selectedDeviceType]: {
            ...prev.deviceTypeSettings[selectedDeviceType],
            fieldSettings: {
              ...(prev.deviceTypeSettings[selectedDeviceType]?.fieldSettings || {}),
              [fieldKey]: {
                ...(prev.deviceTypeSettings[selectedDeviceType]?.fieldSettings?.[fieldKey] || {}),
                [property]: value,
              },
            },
          },
        },
      }));
    } else {
      // Update global settings
      setSettings(prev => ({
        ...prev,
        fieldSettings: {
          ...prev.fieldSettings,
          [fieldKey]: {
            ...prev.fieldSettings[fieldKey],
            [property]: value,
          },
        },
      }));
    }
  };

  const addCustomField = () => {
    const fieldKey = prompt("Enter field key (e.g., 'custom_field'):");
    if (!fieldKey || !fieldKey.trim()) return;

    const key = fieldKey.trim();
    if (settings.fieldSettings[key]) {
      setError(`Field "${key}" already exists`);
      return;
    }

    setSettings(prev => ({
      ...prev,
      fieldSettings: {
        ...prev.fieldSettings,
        [key]: {
          decimals: prev.defaultDecimals,
          visible: true,
          displayName: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        },
      },
    }));
  };

  const removeCustomField = (fieldKey) => {
    if (DEFAULT_FIELDS.find(f => f.key === fieldKey)) {
      setError("Cannot remove default fields");
      return;
    }

    setSettings(prev => {
      const newFieldSettings = { ...prev.fieldSettings };
      delete newFieldSettings[fieldKey];
      return {
        ...prev,
        fieldSettings: newFieldSettings,
      };
    });
  };

  if (!isSmartLPGTenant(user?.tenant_id)) {
    return (
      <div className="page">
        <div className="page-header">
          <BackButton />
          <Breadcrumbs items={[{ label: "Display Settings" }]} />
        </div>
        <div className="card">
          <div className="alert alert--error">
            Display settings are only available for SmartLPG tenant.
          </div>
        </div>
      </div>
    );
  }

  // Get fields to display based on selected device type
  const getFieldsToDisplay = () => {
    if (selectedDeviceType) {
      // Show fields for selected device type
      return deviceTypeFields;
    } else {
      // Show global/default fields
      return [
        ...DEFAULT_FIELDS,
        ...Object.keys(settings.fieldSettings)
          .filter(key => !DEFAULT_FIELDS.find(f => f.key === key))
          .map(key => ({ key, label: settings.fieldSettings[key]?.displayName || key })),
      ];
    }
  };

  const getFieldSetting = (fieldKey) => {
    if (selectedDeviceType) {
      const deviceTypeSetting = settings.deviceTypeSettings[selectedDeviceType];
      return deviceTypeSetting?.fieldSettings?.[fieldKey] || {
        decimals: settings.defaultDecimals,
        visible: true,
        displayName: deviceTypeFields.find(f => f.key === fieldKey)?.label || fieldKey,
      };
    } else {
      return settings.fieldSettings[fieldKey] || {
        decimals: settings.defaultDecimals,
        visible: true,
        displayName: DEFAULT_FIELDS.find(f => f.key === fieldKey)?.label || fieldKey,
      };
    }
  };

  const allFields = getFieldsToDisplay();

  return (
    <div className="page">
      <div className="page-header">
        <BackButton />
        <Breadcrumbs items={[{ label: "Display Settings" }]} />
        <div className="page-header__actions">
          <button
            className="btn btn--primary"
            onClick={handleSave}
            disabled={saving || loading}
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert--error" style={{ marginBottom: "var(--space-4)" }}>
          {error}
        </div>
      )}

      {successMessage && (
        <div className="alert alert--success" style={{ marginBottom: "var(--space-4)" }}>
          {successMessage}
        </div>
      )}

      {loading ? (
        <div className="card">
          <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
            <Icon name="loading" size={32} />
            <p>Loading display settings...</p>
          </div>
        </div>
      ) : (
        <>
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <h2 className="card-title">Default Decimal Places</h2>
            <div className="form-group">
              <label className="form-label">
                Default number of decimal places for numeric fields
              </label>
              <input
                type="number"
                className="form-input"
                min="0"
                max="10"
                value={settings.defaultDecimals}
                onChange={(e) => setSettings(prev => ({
                  ...prev,
                  defaultDecimals: parseInt(e.target.value) || 0,
                }))}
              />
              <small className="form-help">
                This will be used for fields that don't have specific settings (0-10)
              </small>
            </div>
          </div>

          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <h2 className="card-title">Protocol & Device Type Selection</h2>
            
            <div className="form-group" style={{ marginBottom: "var(--space-4)" }}>
              <label className="form-label">Select Protocol (Optional)</label>
              <select
                className="form-select"
                value={selectedProtocol}
                onChange={(e) => setSelectedProtocol(e.target.value)}
              >
                <option value="">All Protocols</option>
                {uniqueProtocols.map((protocol) => (
                  <option key={protocol} value={protocol}>
                    {protocol}
                  </option>
                ))}
              </select>
              <small className="form-help">
                Protocol defines the communication method (HTTP, MQTT, TCP, etc.). Filter device types by protocol.
              </small>
            </div>

            <div className="form-group">
              <label className="form-label">Select Device Type</label>
              <select
                className="form-select"
                value={selectedDeviceType}
                onChange={(e) => setSelectedDeviceType(e.target.value)}
                disabled={selectedProtocol && sortedDeviceTypes.length === 0}
              >
                <option value="">All Fields (Global Settings)</option>
                {sortedDeviceTypes.map((dt) => (
                  <option key={dt.id || dt.name} value={dt.name}>
                    {dt.name}
                  </option>
                ))}
              </select>
              <small className="form-help">
                Device Type defines the specific device model/type. Select a device type to configure fields specific to that type. Select "All Fields" for global settings.
              </small>
            </div>

            {(selectedProtocol || selectedDeviceType) && (
              <div style={{ marginTop: "var(--space-4)", padding: "var(--space-3)", backgroundColor: "var(--color-bg-secondary)", borderRadius: "var(--radius-md)" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                  {selectedProtocol && (
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="info" size={16} />
                      <span style={{ fontSize: "var(--font-size-sm)" }}>
                        Protocol: <strong>{selectedProtocol}</strong>
                      </span>
                    </div>
                  )}
                  {selectedDeviceType && (
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                      <Icon name="info" size={16} />
                      <span style={{ fontSize: "var(--font-size-sm)" }}>
                        Device Type: <strong>{selectedDeviceType}</strong>
                        {selectedProtocol && (
                          <span style={{ color: "var(--color-text-secondary)", marginLeft: "var(--space-2)" }}>
                            ({selectedProtocol})
                          </span>
                        )}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-4)" }}>
              <h2 className="card-title">
                {selectedDeviceType ? `Field Display Settings - ${selectedDeviceType}` : "Field Display Settings (Global)"}
              </h2>
              {!selectedDeviceType && (
                <button
                  className="btn btn--secondary btn--sm"
                  onClick={addCustomField}
                >
                  <Icon name="plus" size={16} />
                  Add Custom Field
                </button>
              )}
            </div>

            {loadingFields ? (
              <div style={{ textAlign: "center", padding: "var(--space-8)" }}>
                <Icon name="loading" size={32} />
                <p>Loading fields for device type...</p>
              </div>
            ) : (
              <>
                <div style={{ overflowX: "auto" }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Field Key</th>
                        <th>Display Name</th>
                        <th>Decimal Places</th>
                        <th>Visible</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {allFields.map(field => {
                        const fieldSetting = getFieldSetting(field.key);

                        return (
                          <tr key={field.key}>
                            <td>
                              <code style={{ fontSize: "var(--font-size-sm)" }}>{field.key}</code>
                            </td>
                            <td>
                              <input
                                type="text"
                                className="form-input form-input--sm"
                                value={fieldSetting.displayName || field.key}
                                onChange={(e) => updateFieldSetting(field.key, "displayName", e.target.value)}
                                placeholder="Display name"
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                className="form-input form-input--sm"
                                min="0"
                                max="10"
                                value={fieldSetting.decimals ?? settings.defaultDecimals}
                                onChange={(e) => updateFieldSetting(field.key, "decimals", parseInt(e.target.value) || 0)}
                              />
                            </td>
                            <td>
                              <label className="checkbox">
                                <input
                                  type="checkbox"
                                  checked={fieldSetting.visible !== false}
                                  onChange={(e) => updateFieldSetting(field.key, "visible", e.target.checked)}
                                />
                                <span>Visible</span>
                              </label>
                            </td>
                            <td>
                              {!selectedDeviceType && !DEFAULT_FIELDS.find(f => f.key === field.key) && (
                                <button
                                  className="btn-icon btn-icon--danger"
                                  onClick={() => removeCustomField(field.key)}
                                  title="Remove field"
                                >
                                  <Icon name="trash" size={16} />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {allFields.length === 0 && (
                  <div style={{ textAlign: "center", padding: "var(--space-8)", color: "var(--color-text-tertiary)" }}>
                    {selectedDeviceType 
                      ? `No fields found for device type "${selectedDeviceType}". Fields will be discovered from device schemas or actual device data.`
                      : "No fields configured. Select a device type or add a custom field to get started."}
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
