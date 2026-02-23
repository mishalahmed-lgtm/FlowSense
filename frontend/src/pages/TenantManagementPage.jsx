import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";
import BackButton from "../components/BackButton.jsx";

// Comprehensive list of countries
const COUNTRIES = [
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria",
  "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan",
  "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
  "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica",
  "Croatia", "Cuba", "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt",
  "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon",
  "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana",
  "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel",
  "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan",
  "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
  "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia",
  "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal",
  "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan",
  "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar",
  "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia",
  "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa",
  "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan",
  "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
  "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
  "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
].sort();

export default function TenantManagementPage() {
  const { token, isAdmin } = useAuth();
  const api = createApiClient(token);

  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingTenant, setEditingTenant] = useState(null);
  const [countrySearch, setCountrySearch] = useState("");
  const [showCountryDropdown, setShowCountryDropdown] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    code: "",
    country: "",
    is_active: true,
    contact_email: "",
    contact_phone: "",
    business_address: "",
    timezone: "UTC",
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
    setFormData({ 
      name: "", 
      code: "", 
      country: "", 
      is_active: true,
      contact_email: "",
      contact_phone: "",
      business_address: "",
      timezone: "UTC",
    });
    setCountrySearch("");
    setShowCountryDropdown(false);
    setShowModal(true);
  };

  const handleEdit = (tenant) => {
    setEditingTenant(tenant);
    const country = tenant.country || "";
    setFormData({
      name: tenant.name,
      code: tenant.code,
      country: country,
      is_active: tenant.is_active,
      contact_email: tenant.contact_email || "",
      contact_phone: tenant.contact_phone || "",
      business_address: tenant.business_address || "",
      timezone: tenant.timezone || "UTC",
    });
    setCountrySearch(country);
    setShowCountryDropdown(false);
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
                <th>Country</th>
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
                    {tenant.country ? (
                      <span className="badge badge--info">{tenant.country}</span>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
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
                  <td colSpan="8" style={{ textAlign: "center" }}>
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

            <div className="form-group" style={{ position: "relative" }}>
              <label className="form-label">Country *</label>
              <div style={{ position: "relative" }}>
                <input
                  className="form-input"
                  type="text"
                  value={countrySearch}
                  onChange={(e) => {
                    const value = e.target.value;
                    setCountrySearch(value);
                    setShowCountryDropdown(true);
                    // Update formData if exact match found
                    if (COUNTRIES.includes(value)) {
                      setFormData({ ...formData, country: value });
                    } else {
                      setFormData({ ...formData, country: "" });
                    }
                  }}
                  onFocus={() => setShowCountryDropdown(true)}
                  onBlur={() => {
                    // Delay to allow click on dropdown item
                    setTimeout(() => setShowCountryDropdown(false), 200);
                  }}
                  placeholder="Type to search country..."
                  required
                  style={{ paddingRight: "40px" }}
                />
                <span
                  style={{
                    position: "absolute",
                    right: "12px",
                    top: "50%",
                    transform: "translateY(-50%)",
                    pointerEvents: "none",
                    color: "var(--color-text-tertiary)",
                  }}
                >
                  ▼
                </span>
                {showCountryDropdown && (
                  <div
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      backgroundColor: "var(--color-bg-secondary)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-md)",
                      maxHeight: "200px",
                      overflowY: "auto",
                      zIndex: 1000,
                      marginTop: "4px",
                      boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
                    }}
                  >
                    {COUNTRIES.filter((country) =>
                      country.toLowerCase().includes(countrySearch.toLowerCase())
                    ).length > 0 ? (
                      COUNTRIES.filter((country) =>
                        country.toLowerCase().includes(countrySearch.toLowerCase())
                      ).map((country) => (
                        <div
                          key={country}
                          onClick={() => {
                            setCountrySearch(country);
                            setFormData({ ...formData, country: country });
                            setShowCountryDropdown(false);
                          }}
                          style={{
                            padding: "var(--space-3) var(--space-4)",
                            cursor: "pointer",
                            borderBottom: "1px solid var(--color-border)",
                            backgroundColor:
                              formData.country === country
                                ? "var(--color-primary)"
                                : "transparent",
                            color:
                              formData.country === country
                                ? "var(--color-text-inverse)"
                                : "var(--color-text-primary)",
                          }}
                          onMouseEnter={(e) => {
                            if (formData.country !== country) {
                              e.target.style.backgroundColor = "var(--color-bg-tertiary)";
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (formData.country !== country) {
                              e.target.style.backgroundColor = "transparent";
                            }
                          }}
                        >
                          {country}
                        </div>
                      ))
                    ) : (
                      <div
                        style={{
                          padding: "var(--space-3) var(--space-4)",
                          color: "var(--color-text-tertiary)",
                          textAlign: "center",
                        }}
                      >
                        No countries found
                      </div>
                    )}
                  </div>
                )}
              </div>
              <small className="form-help">
                Country for accurate utility billing rate calculations
              </small>
            </div>

            <div className="form-group">
              <label className="form-label">Primary Contact Email</label>
              <input
                className="form-input"
                type="email"
                value={formData.contact_email}
                onChange={(e) =>
                  setFormData({ ...formData, contact_email: e.target.value })
                }
                placeholder="e.g., contact@example.com"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Primary Contact Phone</label>
              <input
                className="form-input"
                type="tel"
                value={formData.contact_phone}
                onChange={(e) =>
                  setFormData({ ...formData, contact_phone: e.target.value })
                }
                placeholder="e.g., +1 234 567 8900"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Business Address</label>
              <textarea
                className="form-input"
                value={formData.business_address}
                onChange={(e) =>
                  setFormData({ ...formData, business_address: e.target.value })
                }
                placeholder="Street address, City, State, ZIP Code"
                rows={3}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Timezone</label>
              <select
                className="form-select"
                value={formData.timezone}
                onChange={(e) =>
                  setFormData({ ...formData, timezone: e.target.value })
                }
              >
                <option value="UTC">UTC (Coordinated Universal Time)</option>
                <option value="America/New_York">America/New_York (EST/EDT)</option>
                <option value="America/Chicago">America/Chicago (CST/CDT)</option>
                <option value="America/Denver">America/Denver (MST/MDT)</option>
                <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                <option value="Europe/London">Europe/London (GMT/BST)</option>
                <option value="Europe/Paris">Europe/Paris (CET/CEST)</option>
                <option value="Europe/Berlin">Europe/Berlin (CET/CEST)</option>
                <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                <option value="Asia/Riyadh">Asia/Riyadh (AST)</option>
                <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                <option value="Asia/Shanghai">Asia/Shanghai (CST)</option>
                <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
                <option value="Australia/Sydney">Australia/Sydney (AEDT/AEST)</option>
              </select>
              <small className="form-help">
                Timezone for billing periods, reports, and scheduling
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
                disabled={!formData.name || !formData.code || !formData.country}
              >
                {editingTenant ? "Update" : "Create"}
              </button>
            </div>
          </div>
        </Modal>
    </div>
  );
}

