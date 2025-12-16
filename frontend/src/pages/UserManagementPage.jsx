import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";

const AVAILABLE_MODULES = ["devices", "dashboards", "utility", "rules", "alerts"];

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
  });

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
    });
    setShowModal(true);
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: "", // Don't pre-fill password
      full_name: user.full_name || "",
      role: user.role,
      tenant_id: user.tenant_id || "",
      enabled_modules: user.enabled_modules || [],
      is_active: user.is_active,
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      const payload = { ...formData };
      
      // Convert tenant_id to number or null
      payload.tenant_id = payload.tenant_id ? parseInt(payload.tenant_id) : null;
      
      // Don't send password if it's empty (when editing)
      if (editingUser && !payload.password) {
        delete payload.password;
      }

      if (editingUser) {
        await api.put(`/admin/users/${editingUser.id}`, payload);
      } else {
        await api.post("/admin/users", payload);
      }
      setShowModal(false);
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to save user");
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
      loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete user");
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

      <div className="section-header">
        <h1>User Management</h1>
        <button className="btn btn--primary" onClick={handleCreate}>
          + Add User
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--color-error-500)" }}>
          <p className="text-error">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="card">
          <p>Loading users...</p>
        </div>
      ) : (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Full Name</th>
                <th>Role</th>
                <th>Tenant</th>
                <th>Modules</th>
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
              />
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
                  (!editingUser && !formData.password) ||
                  (formData.role === "tenant_admin" && !formData.tenant_id)
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

