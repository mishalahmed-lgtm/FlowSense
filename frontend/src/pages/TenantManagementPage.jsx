import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";

export default function TenantManagementPage() {
  const { token, isAdmin } = useAuth();
  const api = createApiClient(token);

  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingTenant, setEditingTenant] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    code: "",
    is_active: true,
  });

  useEffect(() => {
    loadTenants();
  }, []);

  const loadTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get("/admin/tenants");
      setTenants(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load tenants");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingTenant(null);
    setFormData({ name: "", code: "", is_active: true });
    setShowModal(true);
  };

  const handleEdit = (tenant) => {
    setEditingTenant(tenant);
    setFormData({
      name: tenant.name,
      code: tenant.code,
      is_active: tenant.is_active,
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    try {
      if (editingTenant) {
        await api.put(`/admin/tenants/${editingTenant.id}`, formData);
      } else {
        await api.post("/admin/tenants", formData);
      }
      setShowModal(false);
      loadTenants();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to save tenant");
    }
  };

  const handleDelete = async (tenant) => {
    if (
      !window.confirm(
        `Are you sure you want to delete tenant "${tenant.name}"? This action cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.delete(`/admin/tenants/${tenant.id}`);
      loadTenants();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete tenant");
    }
  };

  if (!isAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Admin access required to manage tenants.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Admin Portal", path: "/admin" },
          { label: "Tenant Management" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Tenant Management</h1>
          <p className="page-header__subtitle">
            Create and manage tenant organizations
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--primary" onClick={handleCreate}>
            + Add Tenant
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
          <p>Loading tenants...</p>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrapper">
            <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Status</th>
                <th>Devices</th>
                <th>Users</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tenants.map((tenant) => (
                <tr key={tenant.id}>
                  <td>{tenant.name}</td>
                  <td>
                    <code>{tenant.code}</code>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        tenant.is_active ? "badge--success" : "badge--error"
                      }`}
                    >
                      {tenant.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>{tenant.device_count}</td>
                  <td>{tenant.user_count}</td>
                  <td>{new Date(tenant.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => handleEdit(tenant)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => handleDelete(tenant)}
                      disabled={tenant.device_count > 0 || tenant.user_count > 0}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {tenants.length === 0 && (
                <tr>
                  <td colSpan="7" style={{ textAlign: "center" }}>
                    No tenants found. Click "Add Tenant" to create one.
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
        title={editingTenant ? "Edit Tenant" : "Create Tenant"}
        onClose={() => setShowModal(false)}
      >
          <div className="form">
            <div className="form-group">
              <label className="form-label">Tenant Name *</label>
              <input
                className="form-input"
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="e.g., Acme Corporation"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Tenant Code *</label>
              <input
                className="form-input"
                type="text"
                value={formData.code}
                onChange={(e) =>
                  setFormData({ ...formData, code: e.target.value })
                }
                placeholder="e.g., ACME"
                required
                disabled={!!editingTenant}
              />
              <small className="form-help">
                Unique identifier for the tenant. Cannot be changed after creation.
              </small>
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
                disabled={!formData.name || !formData.code}
              >
                {editingTenant ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </Modal>
    </div>
  );
}

