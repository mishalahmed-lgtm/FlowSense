import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceForm from "../components/DeviceForm.jsx";
import Modal from "../components/Modal.jsx";
import Icon from "../components/Icon.jsx";

export default function DevicesPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [devices, setDevices] = useState([]);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterProtocol, setFilterProtocol] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState("grid"); // 'grid' or 'list'

  const loadDevices = async () => {
    try {
      const response = await api.get("/admin/devices");
      setDevices(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load devices");
    }
  };

  const loadReferenceData = async () => {
    try {
      const typesResponse = await api.get("/admin/device-types");
      setDeviceTypes(typesResponse.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load reference data");
    }
  };

  useEffect(() => {
    if (!token) return;
    loadDevices();
    loadReferenceData();
  }, [token]);
  
  if (!isTenantAdmin) {
    return (
      <div className="page page--centered">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }

  const openModal = (device = null) => {
    setSelectedDevice(device);
    setShowModal(true);
    setError(null);
    setSuccessMessage(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedDevice(null);
    setError(null);
    setSuccessMessage(null);
  };

  const handleCreateDevice = async (formValues) => {
    try {
      const payload = {
        ...formValues,
        tenant_id: user.tenant_id,
        auto_generate_key: true,
      };
      await api.post("/admin/devices", payload);
      setSuccessMessage("Device created successfully");
      setError(null);
      loadDevices();
      setTimeout(() => closeModal(), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create device");
    }
  };

  const handleUpdateDevice = async (formValues) => {
    try {
      await api.put(`/admin/devices/${formValues.device_id}`, formValues);
      setSuccessMessage("Device updated successfully");
      setError(null);
      loadDevices();
      setTimeout(() => closeModal(), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update device");
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm("Delete this device? This cannot be undone.")) return;
    try {
      await api.delete(`/admin/devices/${deviceId}`);
      setSuccessMessage("Device deleted");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete device");
    }
  };

  const handleRotateKey = async (deviceId) => {
    if (!window.confirm("Rotate provisioning key? The old key will stop working.")) return;
    try {
      await api.post(`/admin/devices/${deviceId}/rotate-key`);
      setSuccessMessage("Key rotated successfully");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to rotate key");
    }
  };

  const filteredDevices = devices.filter((device) => {
    if (searchQuery && !device.device_id.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !(device.name || "").toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (filterStatus !== "all" && device.is_active !== (filterStatus === "active")) {
      return false;
    }
    if (filterProtocol !== "all") {
      const deviceProtocol = device.protocol?.toLowerCase() || "";
      const filterProtocolLower = filterProtocol.toLowerCase();
      if (filterProtocolLower === "tcp") {
        if (!deviceProtocol.includes("tcp")) return false;
      } else if (deviceProtocol !== filterProtocolLower) {
        return false;
      }
    }
    return true;
  });

  const activeCount = devices.filter((d) => d.is_active).length;
  const offlineCount = devices.length - activeCount;

  const protocols = [...new Set(devices.map(d => d.protocol).filter(Boolean))];

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <h1 className="page-header__title">Devices</h1>
          <p className="page-header__subtitle">
            Manage and monitor your IoT devices
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn-icon" onClick={() => loadDevices()} title="Refresh">
            <Icon name="refresh" size={18} />
          </button>
          <button className="btn btn--primary" onClick={() => openModal()}>
            <Icon name="plus" size={18} />
            <span>Add Device</span>
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--primary">
              <Icon name="devices" size={24} />
            </div>
          </div>
          <div className="metric-card__label">TOTAL DEVICES</div>
          <div className="metric-card__value">{devices.length}</div>
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            {devices.length} Active
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--success">
              <Icon name="check" size={24} />
            </div>
          </div>
          <div className="metric-card__label">ONLINE</div>
          <div className="metric-card__value">{activeCount}</div>
          <div className="metric-card__trend metric-card__trend--up">
            <Icon name="trending" size={12} /> Active now
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--error">
              <Icon name="warning" size={24} />
            </div>
          </div>
          <div className="metric-card__label">OFFLINE</div>
          <div className="metric-card__value">{offlineCount}</div>
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            Needs attention
          </div>
        </div>
      </div>

      {/* Filters Section */}
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flexWrap: "wrap" }}>
          {/* Search */}
          <div className="search-bar">
            <span className="search-bar__icon">
              <Icon name="search" size={18} />
            </span>
            <input
              type="text"
              className="search-bar__input"
              placeholder="Search devices..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Status Filter */}
          <select
            className="filter-select"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="active">Online</option>
            <option value="inactive">Offline</option>
          </select>

          {/* Protocol Filter */}
          <select
            className="filter-select"
            value={filterProtocol}
            onChange={(e) => setFilterProtocol(e.target.value)}
          >
            <option value="all">All Protocols</option>
            {protocols.map((protocol) => (
              <option key={protocol} value={protocol}>
                {protocol}
              </option>
            ))}
          </select>

          <div style={{ marginLeft: "auto", display: "flex", gap: "var(--space-2)" }}>
            <button
              className={`btn-icon ${viewMode === "grid" ? "active" : ""}`}
              onClick={() => setViewMode("grid")}
              title="Grid View"
              style={viewMode === "grid" ? { backgroundColor: "var(--color-bg-tertiary)" } : {}}
            >
              <Icon name="grid" size={18} />
            </button>
            <button
              className={`btn-icon ${viewMode === "list" ? "active" : ""}`}
              onClick={() => setViewMode("list")}
              title="List View"
              style={viewMode === "list" ? { backgroundColor: "var(--color-bg-tertiary)" } : {}}
            >
              <Icon name="list" size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      {error && !showModal && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}
      {successMessage && !showModal && (
        <div className="badge badge--success" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {successMessage}
        </div>
      )}

      {/* Devices Display */}
      {viewMode === "grid" ? (
        <div className="grid grid--auto-fit">
          {filteredDevices.map((device) => (
            <div
              key={device.id}
              className="card card--interactive"
              onClick={() => navigate(`/devices/dashboard/${device.device_id}`)}
              style={{ cursor: "pointer" }}
            >
              <div style={{ position: "absolute", top: "var(--space-4)", right: "var(--space-4)" }}>
                <span className={`badge ${device.is_active ? "badge--success" : "badge--neutral"}`}>
                  <span className="badge__dot"></span>
                  {device.is_active ? "Online" : "Offline"}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "64px", height: "64px", borderRadius: "var(--radius-xl)", backgroundColor: "var(--color-bg-secondary)", margin: "0 auto var(--space-4)" }}>
                <Icon name="devices" size={32} />
              </div>

              <h3 className="card__title" style={{ textAlign: "center", marginBottom: "var(--space-2)" }}>
                {device.name || device.device_id}
              </h3>
              <p style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", textAlign: "center", marginBottom: "var(--space-4)" }}>
                {device.device_id}
              </p>

              <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "center", flexWrap: "wrap" }}>
                <span className="badge badge--info">{device.protocol}</span>
                <span className="badge badge--neutral">{device.device_type}</span>
              </div>

              <div className="card__footer" style={{ marginTop: "var(--space-4)" }}>
                <button
                  className="btn btn--sm btn--ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    openModal(device);
                  }}
                >
                  Edit
                </button>
                <button
                  className="btn btn--sm btn--danger"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteDevice(device.device_id);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Device ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Protocol</th>
                <th>Tenant</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDevices.map((device) => (
                <tr
                  key={device.id}
                  onClick={() => navigate(`/devices/dashboard/${device.device_id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>
                    <span className={`badge ${device.is_active ? "badge--success" : "badge--neutral"}`}>
                      <span className="badge__dot"></span>
                      {device.is_active ? "Online" : "Offline"}
                    </span>
                  </td>
                  <td style={{ fontFamily: "var(--font-family-mono)", fontSize: "var(--font-size-xs)" }}>
                    {device.device_id}
                  </td>
                  <td>{device.name || "—"}</td>
                  <td><span className="badge badge--neutral">{device.device_type}</span></td>
                  <td><span className="badge badge--info">{device.protocol}</span></td>
                  <td>{device.tenant}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: "flex", gap: "var(--space-2)" }}>
                      <button
                        className="btn btn--sm btn--ghost"
                        onClick={() => openModal(device)}
                      >
                        Edit
                      </button>
                      <button
                        className="btn btn--sm btn--ghost"
                        onClick={() => handleRotateKey(device.device_id)}
                      >
                        🔑 Key
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        onClick={() => handleDeleteDevice(device.device_id)}
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

      {/* No Results */}
      {filteredDevices.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <div style={{ marginBottom: "var(--space-4)", opacity: 0.3 }}>
            <Icon name="devices" size={64} />
          </div>
          <h3 style={{ marginBottom: "var(--space-2)", color: "var(--color-text-secondary)" }}>
            No devices found
          </h3>
          <p style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-6)" }}>
            {searchQuery || filterStatus !== "all" || filterProtocol !== "all"
              ? "Try adjusting your filters"
              : "Get started by adding your first device"}
          </p>
          {!searchQuery && filterStatus === "all" && filterProtocol === "all" && (
            <button className="btn btn--primary" onClick={() => openModal()}>
              <Icon name="plus" size={18} />
              <span>Add First Device</span>
            </button>
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <Modal
          title={selectedDevice ? "Edit Device" : "Create New Device"}
          onClose={closeModal}
        >
          <DeviceForm
            initialDevice={selectedDevice}
            deviceTypes={deviceTypes}
            tenants={[]}
            userTenantId={user?.tenant_id}
            onSubmit={selectedDevice ? handleUpdateDevice : handleCreateDevice}
            onCancel={closeModal}
          />
        </Modal>
      )}
    </div>
  );
}
