import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";

export default function DeviceRulesListPage() {
  const { token, isTenantAdmin, user } = useAuth();
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
    rule_type: "automation",
    condition: { field: "", operator: ">", value: "" },
    action: "log",
    action_params: {},
    is_active: true,
  });

  // Only tenant admins can access
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires tenant admin access.</p>
        </div>
      </div>
    );
  }

  const generateDummyRules = (deviceList) => {
    // Generate rules for just a few devices (5-8 rules total)
    const ruleTypes = ["automation", "routing", "transformation", "filtering"];
    const actions = ["log", "forward", "transform", "alert", "discard"];
    const operators = [">", ">=", "<", "<=", "==", "!="];
    const fields = ["temperature", "humidity", "battery", "pressure", "level"];
    
    const dummyRules = [];
    const selectedDevices = deviceList.slice(0, 5); // Use first 5 devices
    
    selectedDevices.forEach((device, idx) => {
      const ruleType = ruleTypes[idx % ruleTypes.length];
      const field = fields[idx % fields.length];
      const operator = operators[idx % operators.length];
      const value = idx === 0 ? "30" : idx === 1 ? "80" : idx === 2 ? "20" : idx === 3 ? "100" : "50";
      
      dummyRules.push({
        id: `rule_${idx + 1}`,
        name: `${ruleType.charAt(0).toUpperCase() + ruleType.slice(1)} Rule for ${device.name || device.device_id}`,
        description: `Automated ${ruleType} rule for device monitoring`,
        device_id: device.device_id,
        device_name: device.name || device.device_id,
        rule_type: ruleType,
        condition: {
          field: `payload.${field}`,
          operator: operator,
          value: value,
        },
        action: actions[idx % actions.length],
        action_params: {},
        is_active: idx < 3, // First 3 active, rest inactive
        created_at: new Date(Date.now() - (idx * 24 * 60 * 60 * 1000)).toISOString(),
        updated_at: new Date(Date.now() - (idx * 12 * 60 * 60 * 1000)).toISOString(),
      });
    });
    
    return dummyRules;
  };

  const loadRules = async () => {
    try {
      setLoading(true);
      
      // For tenant_id = 3 (SmartLPG), load from Firebase
      if (user?.tenant_id === 3) {
        console.log("🔥 Loading device rules from Firebase for SmartLPG tenant");
        const { getDeviceRulesFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        const firebaseRules = await getDeviceRulesFromFirebase();
        setRules(firebaseRules);
        setError(null);
        setLoading(false);
        return;
      }
      
      // For tenant_id = 2, use dummy data
      if (user?.tenant_id === 2) {
        console.log("🔥 Generating dummy device rules for tenant_id = 2");
        // If devices not loaded yet, create dummy devices for rules
        const devicesForRules = devices.length > 0 
          ? devices 
          : Array.from({ length: 5 }, (_, i) => ({
              device_id: `device_${i + 1}`,
              name: `Device ${i + 1}`,
            }));
        const dummyRules = generateDummyRules(devicesForRules);
        setRules(dummyRules);
        setError(null);
        setLoading(false);
        return;
      }
      
      // For other tenants, try to load from API (if endpoint exists)
      try {
        const response = await api.get("/devices/rules");
        setRules(response.data || []);
      } catch (apiErr) {
        // If endpoint doesn't exist, use empty array
        console.warn("Device rules API not available, using empty list");
        setRules([]);
      }
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load device rules");
      setRules([]);
    } finally {
      setLoading(false);
    }
  };

  const loadDevices = async () => {
    try {
      // For tenant_id = 3 (SmartLPG), use Firebase devices
      if (user?.tenant_id === 3) {
        const { fetchSmartLPGDataForDashboard } = await import("../services/smartLPGDataMapper.js");
        const firebaseData = await fetchSmartLPGDataForDashboard();
        if (firebaseData.success && firebaseData.devices) {
          setDevices(firebaseData.devices);
          return;
        }
      }
      
      // For tenant_id = 2, use Firebase devices
      if (user?.tenant_id === 2) {
        const { fetchFirebaseDataForDashboard } = await import("../services/firebaseDataMapper.js");
        const firebaseData = await fetchFirebaseDataForDashboard();
        if (firebaseData.success && firebaseData.devices) {
          setDevices(firebaseData.devices.slice(0, 10)); // Use first 10 devices
          return;
        }
      }
      
      // For other tenants, use API
      const response = await api.get("/admin/devices");
      const devicesData = response.data?.devices || (Array.isArray(response.data) ? response.data : []);
      setDevices(devicesData);
    } catch (err) {
      console.error("Failed to load devices:", err);
      setDevices([]);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadDevices();
  }, [token, user]);

  useEffect(() => {
    if (devices.length > 0 || (user?.tenant_id === 2 && devices.length === 0)) {
      loadRules();
    }
  }, [devices.length, user]);

  const openModal = (rule = null) => {
    if (rule) {
      setSelectedRule(rule);
      setFormState({
        name: rule.name || "",
        description: rule.description || "",
        device_id: rule.device_id || null,
        rule_type: rule.rule_type || "automation",
        condition: rule.condition || { field: "", operator: ">", value: "" },
        action: rule.action || "log",
        action_params: rule.action_params || {},
        is_active: rule.is_active ?? true,
      });
    } else {
      setSelectedRule(null);
      setFormState({
        name: "",
        description: "",
        device_id: null,
        rule_type: "automation",
        condition: { field: "", operator: ">", value: "" },
        action: "log",
        action_params: {},
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

      // For tenant_id = 3 (SmartLPG), save to Firebase
      if (user?.tenant_id === 3) {
        const { saveDeviceRuleToFirebase } = await import("../services/smartLPGFirebaseService.js");
        
        const ruleToSave = {
          ...payload,
          id: selectedRule?.id,
          device_name: devices.find(d => d.device_id === payload.device_id)?.name || (payload.device_id ? `Device ${payload.device_id}` : "All Devices"),
          created_at: selectedRule?.created_at || new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        
        await saveDeviceRuleToFirebase(ruleToSave);
        setSuccessMessage(selectedRule ? "Device rule updated successfully" : "Device rule created successfully");
        await loadRules();
        setTimeout(() => {
          closeModal();
        }, 1500);
        return;
      }
      
      // For tenant_id = 2, just update local state (dummy data)
      if (user?.tenant_id === 2) {
        if (selectedRule) {
          // Update existing rule
          setRules(rules.map(r => r.id === selectedRule.id ? { ...selectedRule, ...payload } : r));
          setSuccessMessage("Device rule updated successfully");
        } else {
          // Create new rule
          const newRule = {
            id: `rule_${Date.now()}`,
            ...payload,
            device_name: devices.find(d => d.device_id === payload.device_id)?.name || `Device ${payload.device_id}`,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          setRules([...rules, newRule]);
          setSuccessMessage("Device rule created successfully");
        }
        
        setTimeout(() => {
          closeModal();
        }, 1500);
        return;
      }
      
      // For other tenants, use API
      if (selectedRule) {
        await api.put(`/devices/rules/${selectedRule.id}`, payload);
        setSuccessMessage("Device rule updated successfully");
      } else {
        await api.post("/devices/rules", payload);
        setSuccessMessage("Device rule created successfully");
      }
      
      await loadRules();
      setTimeout(() => {
        closeModal();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save device rule");
    }
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm("Are you sure you want to delete this device rule?")) {
      return;
    }
    try {
      // For tenant_id = 3 (SmartLPG), delete from Firebase
      if (user?.tenant_id === 3) {
        const { deleteDeviceRuleFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        await deleteDeviceRuleFromFirebase(ruleId);
        setSuccessMessage("Device rule deleted successfully");
        await loadRules();
        return;
      }
      
      // For tenant_id = 2, just update local state
      if (user?.tenant_id === 2) {
        setRules(rules.filter(r => r.id !== ruleId));
        setSuccessMessage("Device rule deleted successfully");
        return;
      }
      
      // For other tenants, use API
      await api.delete(`/devices/rules/${ruleId}`);
      setSuccessMessage("Device rule deleted successfully");
      await loadRules();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete device rule");
    }
  };

  const getRuleTypeBadgeClass = (type) => {
    switch (type) {
      case "automation": return "badge--info";
      case "routing": return "badge--success";
      case "transformation": return "badge--warning";
      case "filtering": return "badge--neutral";
      default: return "badge--neutral";
    }
  };

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Devices", path: "/devices" },
          { label: "Device Rules", path: "/devices/rules" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Device Rules</h1>
          <p className="page-header__subtitle">
            Configure automation, routing, and transformation rules for your devices
          </p>
        </div>
        <div className="page-header__actions">
          <button
            className="btn btn--primary"
            onClick={() => openModal()}
          >
            <Icon name="plus" size={18} />
            Create Device Rule
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
            <p className="text-muted">Loading device rules...</p>
          </div>
        ) : rules.length === 0 ? (
          <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
            <p className="text-muted">No device rules found. Create your first device rule to get started.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Device</th>
                  <th>Type</th>
                  <th>Condition</th>
                  <th>Action</th>
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
                      {rule.device_name || rule.device_id || "All Devices"}
                    </td>
                    <td>
                      <span className={`badge ${getRuleTypeBadgeClass(rule.rule_type)}`}>
                        {rule.rule_type.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <code style={{ fontSize: "var(--font-size-xs)" }}>
                        {rule.condition?.field} {rule.condition?.operator} {rule.condition?.value}
                      </code>
                    </td>
                    <td>
                      <span className="badge badge--info">{rule.action}</span>
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
      <Modal isOpen={showModal} onClose={closeModal} title={selectedRule ? "Edit Device Rule" : "Create Device Rule"}>
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label form-label--required">Name</label>
            <input
              type="text"
              className="form-input"
              value={formState.name || ""}
              onChange={(e) => {
                e.stopPropagation();
                setFormState({ ...formState, name: e.target.value });
              }}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              value={formState.description || ""}
              onChange={(e) => {
                e.stopPropagation();
                setFormState({ ...formState, description: e.target.value });
              }}
              rows={3}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Device (optional - leave empty for all devices)</label>
            <select
              className="form-select"
              value={formState.device_id || ""}
              onChange={(e) => setFormState({ ...formState, device_id: e.target.value || null })}
            >
              <option value="">All Devices</option>
              {devices.map((device) => (
                <option key={device.device_id || device.id} value={device.device_id || device.id}>
                  {device.name || device.device_id}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label form-label--required">Rule Type</label>
            <select
              className="form-select"
              value={formState.rule_type}
              onChange={(e) => setFormState({ ...formState, rule_type: e.target.value })}
              required
            >
              <option value="automation">Automation</option>
              <option value="routing">Routing</option>
              <option value="transformation">Transformation</option>
              <option value="filtering">Filtering</option>
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
                  value={formState.condition?.field || ""}
                  onChange={(e) => {
                    e.stopPropagation();
                    setFormState({
                      ...formState,
                      condition: { ...formState.condition, field: e.target.value }
                    });
                  }}
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
                  value={formState.condition?.value || ""}
                  onChange={(e) => {
                    e.stopPropagation();
                    setFormState({
                      ...formState,
                      condition: { ...formState.condition, value: e.target.value }
                    });
                  }}
                  required
                />
              </div>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label form-label--required">Action</label>
            <select
              className="form-select"
              value={formState.action}
              onChange={(e) => setFormState({ ...formState, action: e.target.value })}
              required
            >
              <option value="log">Log</option>
              <option value="forward">Forward</option>
              <option value="transform">Transform</option>
              <option value="alert">Alert</option>
              <option value="discard">Discard</option>
            </select>
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

