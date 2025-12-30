import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";

const AVAILABLE_MODULES = ["devices", "dashboards", "utility", "rules", "alerts", "fota", "health", "analytics"];

export default function UserManagementPage() {
  const { token, isAdmin } = useAuth();
  const api = createApiClient(token);

  const [users, setUsers] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "tenant_admin",
    tenant_id: "",
    enabled_modules: [],
    is_active: true,
    external_integration: null, // null = no integration, object = integration config
  });

  const [showExternalIntegration, setShowExternalIntegration] = useState(false);

  useEffect(() => {
    loadUsers();
    if (isAdmin) {
      loadTenants();
    }
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/admin/users");
      setUsers(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  const loadTenants = async () => {
    try {
      const resp = await api.get("/admin/tenants");
      setTenants(resp.data);
    } catch (err) {
      console.error("Failed to load tenants:", err);
    }
  };

  const handleCreate = () => {
    setEditingUser(null);
    setFormData({
      email: "",
      password: "",
      full_name: "",
      role: "tenant_admin",
      tenant_id: "",
      enabled_modules: [],
      is_active: true,
      external_integration: null,
    });
    setShowExternalIntegration(false);
    setShowModal(true);
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    const hasIntegration = user.external_integrations && user.external_integrations.length > 0;
    setFormData({
      email: user.email,
      password: "", // Don't pre-fill password
      full_name: user.full_name || "",
      role: user.role,
      tenant_id: user.tenant_id || "",
      enabled_modules: user.enabled_modules || [],
      is_active: user.is_active,
      external_integration: hasIntegration ? {
        name: user.external_integrations[0].name || "",
        description: user.external_integrations[0].description || "",
        allowed_endpoints: user.external_integrations[0].allowed_endpoints || [],
        endpoint_urls: user.external_integrations[0].endpoint_urls || {},
        webhook_url: user.external_integrations[0].webhook_url || "",
      } : null,
    });
    setShowExternalIntegration(hasIntegration);
    setShowModal(true);
  };

  const handleSave = async () => {
    // Client-side validation
    if (!editingUser && (!formData.password || formData.password.length < 6)) {
      setError("Password must be at least 6 characters");
      return;
    }
    
    if (formData.role === "tenant_admin" && !formData.tenant_id) {
      setError("Please select a tenant for tenant admin users");
      return;
    }

    // Validate external integration
    if (showExternalIntegration && formData.external_integration) {
      if (!formData.external_integration.allowed_endpoints || formData.external_integration.allowed_endpoints.length === 0) {
        setError("Please select at least one allowed endpoint for external integration");
        return;
      }
    }

    try {
      const payload = { ...formData };
      
      // Convert tenant_id to number or null
      payload.tenant_id = payload.tenant_id ? parseInt(payload.tenant_id) : null;
      
      // Don't send password if it's empty (when editing)
      if (editingUser && !payload.password) {
        delete payload.password;
      }

      // Handle external integration
      if (showExternalIntegration && formData.external_integration) {
        // Only include non-empty fields
        const integration = {};
        if (formData.external_integration.name) {
          integration.name = formData.external_integration.name;
        }
        if (formData.external_integration.description) {
          integration.description = formData.external_integration.description;
        }
        if (formData.external_integration.allowed_endpoints && formData.external_integration.allowed_endpoints.length > 0) {
          integration.allowed_endpoints = formData.external_integration.allowed_endpoints;
        }
        if (formData.external_integration.endpoint_urls && Object.keys(formData.external_integration.endpoint_urls).length > 0) {
          // Only include non-empty endpoint URLs
          const endpointUrls = {};
          Object.keys(formData.external_integration.endpoint_urls).forEach((key) => {
            if (formData.external_integration.endpoint_urls[key] && formData.external_integration.endpoint_urls[key].trim()) {
              endpointUrls[key] = formData.external_integration.endpoint_urls[key].trim();
            }
          });
          if (Object.keys(endpointUrls).length > 0) {
            integration.endpoint_urls = endpointUrls;
          }
        }
        if (formData.external_integration.webhook_url) {
          integration.webhook_url = formData.external_integration.webhook_url;
        }
        
        if (Object.keys(integration).length > 0) {
          payload.external_integration = integration;
        }
      } else {
        // If external integration is disabled, don't send it
        delete payload.external_integration;
      }

      if (editingUser) {
        await api.put(`/admin/users/${editingUser.id}`, payload);
      } else {
        await api.post("/admin/users", payload);
      }
      setShowModal(false);
      setError(null);
      loadUsers();
    } catch (err) {
      let errorMessage = "Failed to save user";
      
      if (err.response?.data) {
        const data = err.response.data;
        
        // Handle Pydantic validation errors
        if (Array.isArray(data.detail)) {
          const validationErrors = data.detail.map((e) => {
            if (e.type === "string_too_short") {
              return `${e.loc.join('.')}: ${e.msg}`;
            }
            return `${e.loc.join('.')}: ${e.msg}`;
          });
          errorMessage = validationErrors.join(", ");
        } else if (typeof data.detail === 'string') {
          errorMessage = data.detail;
        } else if (data.detail?.msg) {
          errorMessage = `${data.detail.loc?.join('.') || 'Field'}: ${data.detail.msg}`;
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    }
  };

  const handleDelete = async (user) => {
    if (
      !window.confirm(
        `Are you sure you want to delete user "${user.email}"? This action cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.delete(`/admin/users/${user.id}`);
      setError(null);
      loadUsers();
    } catch (err) {
      const errorMessage = err.response?.data?.detail || err.message || "Failed to delete user";
      const errorString = typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage);
      setError(errorString);
    }
  };

  const toggleModule = (module) => {
    setFormData((prev) => ({
      ...prev,
      enabled_modules: prev.enabled_modules.includes(module)
        ? prev.enabled_modules.filter((m) => m !== module)
        : [...prev.enabled_modules, module],
    }));
  };

  const toggleExternalEndpoint = (endpoint) => {
    setFormData((prev) => {
      const currentEndpoints = prev.external_integration?.allowed_endpoints || [];
      const newEndpoints = currentEndpoints.includes(endpoint)
        ? currentEndpoints.filter((e) => e !== endpoint)
        : [...currentEndpoints, endpoint];
      
      return {
        ...prev,
        external_integration: {
          ...prev.external_integration,
          name: prev.external_integration?.name || "",
          description: prev.external_integration?.description || "",
          webhook_url: prev.external_integration?.webhook_url || "",
          allowed_endpoints: newEndpoints,
        },
      };
    });
  };

  const updateExternalIntegrationField = (field, value) => {
    setFormData((prev) => ({
      ...prev,
      external_integration: {
        ...prev.external_integration,
        [field]: value,
        allowed_endpoints: prev.external_integration?.allowed_endpoints || [],
        endpoint_urls: prev.external_integration?.endpoint_urls || {},
      },
    }));
  };

  if (!isAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Admin access required to manage users.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Admin Portal", path: "/admin" },
          { label: "User Management" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">User Management</h1>
          <p className="page-header__subtitle">
            Manage user accounts, roles, and module access
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--primary" onClick={handleCreate}>
            + Add User
          </button>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="card">
          <p>Loading users...</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrapper">
            <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Full Name</th>
                <th>Role</th>
                <th>Tenant</th>
                <th>Modules</th>
                <th>External API</th>
                <th>Status</th>
                <th>Last Login</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.full_name || "-"}</td>
                  <td>
                    <span
                      className={`badge ${
                        user.role === "admin" ? "badge--primary" : "badge--secondary"
                      }`}
                    >
                      {user.role === "admin" ? "Admin" : "Tenant Admin"}
                    </span>
                  </td>
                  <td>{user.tenant_name || "-"}</td>
                  <td>
                    <small>{user.enabled_modules.length} modules</small>
                  </td>
                  <td>
                    {user.external_integrations && user.external_integrations.length > 0 ? (
                      <span className="badge badge--success" title={`API Key: ${user.external_integrations[0].api_key}`}>
                        Enabled
                      </span>
                    ) : (
                      <span className="badge badge--secondary">Disabled</span>
                    )}
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        user.is_active ? "badge--success" : "badge--error"
                      }`}
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    {user.last_login_at
                      ? new Date(user.last_login_at).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td>
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => handleEdit(user)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => handleDelete(user)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan="8" style={{ textAlign: "center" }}>
                    No users found. Click "Add User" to create one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      <Modal
        isOpen={showModal}
        title={editingUser ? "Edit User" : "Create User"}
        onClose={() => setShowModal(false)}
      >
          <div className="form">
            <div className="form-group">
              <label className="form-label">Email *</label>
              <input
                className="form-input"
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                placeholder="user@example.com"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                Password {editingUser ? "(leave blank to keep current)" : "*"}
              </label>
              <input
                className="form-input"
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                placeholder="Min. 6 characters"
                required={!editingUser}
                minLength={!editingUser ? 6 : undefined}
              />
              {!editingUser && formData.password && formData.password.length < 6 && (
                <small className="form-help" style={{ color: "var(--color-error-text)" }}>
                  Password must be at least 6 characters
                </small>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input
                className="form-input"
                type="text"
                value={formData.full_name}
                onChange={(e) =>
                  setFormData({ ...formData, full_name: e.target.value })
                }
                placeholder="John Doe"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Role *</label>
              <select
                className="form-select"
                value={formData.role}
                onChange={(e) =>
                  setFormData({ ...formData, role: e.target.value })
                }
              >
                <option value="admin">Admin</option>
                <option value="tenant_admin">Tenant Admin</option>
              </select>
            </div>

            {formData.role === "tenant_admin" && (
              <div className="form-group">
                <label className="form-label">Tenant *</label>
                <select
                  className="form-select"
                  value={formData.tenant_id}
                  onChange={(e) =>
                    setFormData({ ...formData, tenant_id: e.target.value })
                  }
                  required
                >
                  <option value="">Select a tenant</option>
                  {tenants.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name} ({tenant.code})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Enabled Modules</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-2)" }}>
                {AVAILABLE_MODULES.map((module) => (
                  <div
                    key={module}
                    style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
                  >
                    <input
                      type="checkbox"
                      id={`module-${module}`}
                      checked={formData.enabled_modules.includes(module)}
                      onChange={() => toggleModule(module)}
                      disabled={formData.role === "admin"}
                      style={{ width: "auto" }}
                    />
                    <label
                      htmlFor={`module-${module}`}
                      style={{ margin: 0, cursor: "pointer", textTransform: "capitalize" }}
                    >
                      {module}
                    </label>
                  </div>
                ))}
              </div>
              {formData.role === "admin" && (
                <small className="form-help">Admins have access to all modules</small>
              )}
            </div>

            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
                style={{ width: "auto" }}
              />
              <label htmlFor="is_active" className="form-label" style={{ margin: 0, cursor: "pointer" }}>
                Active
              </label>
            </div>

            {/* External Integration Section */}
            <div style={{ borderTop: "1px solid var(--color-border)", paddingTop: "var(--space-4)", marginTop: "var(--space-4)" }}>
              <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "var(--space-2)" }}>
                <input
                  type="checkbox"
                  id="enable_external_integration"
                  checked={showExternalIntegration}
                  onChange={(e) => {
                    setShowExternalIntegration(e.target.checked);
                    if (!e.target.checked) {
                      setFormData((prev) => ({ ...prev, external_integration: null }));
                    } else {
                      setFormData((prev) => ({
                        ...prev,
                      external_integration: {
                        name: "",
                        description: "",
                        allowed_endpoints: [],
                        endpoint_urls: {},
                        webhook_url: "",
                      },
                      }));
                    }
                  }}
                  style={{ width: "auto" }}
                />
                <label htmlFor="enable_external_integration" className="form-label" style={{ margin: 0, cursor: "pointer", fontWeight: "600" }}>
                  Enable External API Integration
                </label>
              </div>

              {showExternalIntegration && (
                <div style={{ marginTop: "var(--space-4)", paddingLeft: "var(--space-4)", borderLeft: "2px solid var(--color-primary)" }}>
                  <div className="form-group">
                    <label className="form-label">Integration Name</label>
                    <input
                      className="form-input"
                      type="text"
                      value={formData.external_integration?.name || ""}
                      onChange={(e) => updateExternalIntegrationField("name", e.target.value)}
                      placeholder="e.g., External System Integration"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-input"
                      value={formData.external_integration?.description || ""}
                      onChange={(e) => updateExternalIntegrationField("description", e.target.value)}
                      placeholder="Optional description for this integration"
                      rows={2}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Endpoint URLs *</label>
                    <small className="form-help" style={{ display: "block", marginBottom: "var(--space-2)" }}>
                      Specify custom endpoint URLs for each type. Leave empty to use default endpoints.
                    </small>
                    {["health", "data", "devices"].map((endpoint) => (
                      <div key={endpoint} style={{ marginBottom: "var(--space-3)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                          <input
                            type="checkbox"
                            id={`endpoint-${endpoint}`}
                            checked={formData.external_integration?.allowed_endpoints?.includes(endpoint) || false}
                            onChange={() => toggleExternalEndpoint(endpoint)}
                            style={{ width: "auto" }}
                          />
                          <label
                            htmlFor={`endpoint-${endpoint}`}
                            style={{ margin: 0, cursor: "pointer", textTransform: "capitalize", fontWeight: "500", minWidth: "80px" }}
                          >
                            {endpoint}:
                          </label>
                        </div>
                        {formData.external_integration?.allowed_endpoints?.includes(endpoint) && (
                          <input
                            className="form-input"
                            type="url"
                            value={formData.external_integration?.endpoint_urls?.[endpoint] || ""}
                            onChange={(e) => {
                              setFormData((prev) => ({
                                ...prev,
                                external_integration: {
                                  ...prev.external_integration,
                                  endpoint_urls: {
                                    ...prev.external_integration?.endpoint_urls,
                                    [endpoint]: e.target.value,
                                  },
                                },
                              }));
                            }}
                            placeholder={
                              endpoint === "health"
                                ? "https://example.com/api/health (optional - uses default if empty)"
                                : endpoint === "data"
                                ? "https://example.com/api/data (optional - uses default if empty)"
                                : "https://example.com/api/devices (optional - uses default if empty)"
                            }
                            style={{ marginLeft: "var(--space-6)" }}
                          />
                        )}
                        <small className="form-help" style={{ display: "block", marginLeft: "var(--space-6)", marginTop: "var(--space-1)" }}>
                          {endpoint === "health"
                            ? "Endpoint for device health data"
                            : endpoint === "data"
                            ? "Endpoint for telemetry/payload data"
                            : "Endpoint for device management"}
                        </small>
                      </div>
                    ))}
                  </div>

                  <div className="form-group">
                    <label className="form-label">Webhook URL</label>
                    <input
                      className="form-input"
                      type="url"
                      value={formData.external_integration?.webhook_url || ""}
                      onChange={(e) => updateExternalIntegrationField("webhook_url", e.target.value)}
                      placeholder="https://example.com/webhook"
                    />
                    <small className="form-help">Optional: URL to receive webhook notifications</small>
                  </div>

                  {editingUser && editingUser.external_integrations && editingUser.external_integrations.length > 0 && (
                    <div className="form-group" style={{ padding: "var(--space-3)", backgroundColor: "var(--color-bg-secondary)", borderRadius: "var(--radius-sm)" }}>
                      <label className="form-label" style={{ fontWeight: "600", marginBottom: "var(--space-2)" }}>
                        API Key
                      </label>
                      <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                        <code style={{ flex: 1, padding: "var(--space-2)", backgroundColor: "var(--color-bg)", borderRadius: "var(--radius-sm)", fontSize: "0.875rem" }}>
                          {editingUser.external_integrations[0].api_key}
                        </code>
                        <button
                          className="btn btn--ghost btn--sm"
                          onClick={() => {
                            navigator.clipboard.writeText(editingUser.external_integrations[0].api_key);
                            alert("API key copied to clipboard!");
                          }}
                        >
                          Copy
                        </button>
                      </div>
                      <small className="form-help" style={{ marginTop: "var(--space-2)", display: "block" }}>
                        Use this API key in the X-API-Key header when calling external endpoints
                      </small>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="form-actions">
              <button
                className="btn btn--secondary"
                onClick={() => setShowModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn--primary"
                onClick={handleSave}
                disabled={
                  !formData.email ||
                  (!editingUser && (!formData.password || formData.password.length < 6)) ||
                  (formData.role === "tenant_admin" && !formData.tenant_id) ||
                  (showExternalIntegration && (!formData.external_integration?.allowed_endpoints || formData.external_integration.allowed_endpoints.length === 0))
                }
              >
                {editingUser ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </Modal>
    </div>
  );
}

