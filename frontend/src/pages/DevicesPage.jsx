import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceForm from "../components/DeviceForm.jsx";
import Modal from "../components/Modal.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import DeviceMapView from "../components/DeviceMapView.jsx";

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
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(50); // Show 50 devices per page
  const [totalDeviceCount, setTotalDeviceCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [totalActiveCount, setTotalActiveCount] = useState(0);
  const [totalInactiveCount, setTotalInactiveCount] = useState(0);

  const loadDevices = async (pageNum = currentPage) => {
    try {
      console.log(`Loading devices (page ${pageNum})...`);
      const params = {
        page: pageNum,
        limit: itemsPerPage,
      };
      
      // Add server-side filters
      if (searchQuery) {
        params.search = searchQuery;
      }
      if (filterStatus !== "all") {
        params.status = filterStatus === "active" ? "active" : "inactive";
      }
      if (filterProtocol !== "all") {
        params.protocol = filterProtocol;
      }
      
      const response = await api.get("/admin/devices", { params });
      const data = response.data;
      
      // Handle both old format (array) and new format (paginated object)
      if (Array.isArray(data)) {
        // Old format - backward compatibility
        setDevices(data);
        setTotalDeviceCount(data.length);
        setTotalPages(Math.ceil(data.length / itemsPerPage));
        // Calculate active/inactive from current page
        const active = data.filter((d) => d.is_active).length;
        const inactive = data.filter((d) => !d.is_active).length;
        setTotalActiveCount(active);
        setTotalInactiveCount(inactive);
      } else if (data && data.devices) {
        // New paginated format
        setDevices(data.devices || []);
        setTotalDeviceCount(data.total || 0);
        setTotalPages(data.total_pages || 1);
        setTotalActiveCount(data.total_active ?? 0);
        setTotalInactiveCount(data.total_inactive ?? 0);
        if (data.page && data.page !== currentPage) {
          setCurrentPage(data.page);
        }
      } else {
        setDevices([]);
        setTotalDeviceCount(0);
        setTotalPages(1);
        setTotalActiveCount(0);
        setTotalInactiveCount(0);
      }
      
      console.log(`Loaded ${data.devices?.length || data.length || 0} devices (page ${data.page || currentPage}, total: ${data.total || totalDeviceCount})`);
      setError(null);
    } catch (err) {
      console.error("Error loading devices:", err);
      setError(err.response?.data?.detail || "Failed to load devices");
      setDevices([]); // Clear devices on error
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

  // With server-side pagination, devices are already filtered and paginated
  // Calculate active/offline counts from current page (for display only)
  // Note: For accurate totals across all pages, we'd need a separate stats endpoint
  // Use total counts from API (for all devices) instead of just current page
  // The API provides total_active and total_inactive counts
  const activeCount = totalActiveCount; // Total active devices across all pages
  const offlineCount = totalInactiveCount; // Total offline devices across all pages
  
  // Reset to page 1 when filters change and reload
  useEffect(() => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    } else {
      loadDevices(1);
    }
  }, [searchQuery, filterStatus, filterProtocol]);
  
  // Load devices when page changes
  useEffect(() => {
    loadDevices(currentPage);
  }, [currentPage]);
  
  // For display, use devices directly (already paginated from server)
  const displayDevices = devices;

  const protocols = [...new Set(devices.map(d => d.protocol).filter(Boolean))];

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Devices", path: "/devices" }]} />
      
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
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
          <div className="metric-card__value">{totalDeviceCount || devices.length}</div>
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            Showing {devices.length} of {totalDeviceCount || devices.length}
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
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            Active now
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
            <button
              className={`btn-icon ${viewMode === "map" ? "active" : ""}`}
              onClick={() => setViewMode("map")}
              title="Map View"
              style={viewMode === "map" ? { backgroundColor: "var(--color-bg-tertiary)" } : {}}
            >
              <Icon name="map" size={18} />
            </button>
          </div>
        </div>
        
        {/* Pagination - Moved to top */}
        {totalPages > 1 && (
          <div style={{ marginTop: "var(--space-4)", paddingTop: "var(--space-4)", borderTop: "1px solid var(--color-border)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
            <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)" }}>
              Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, totalDeviceCount)} of {totalDeviceCount} devices
            </div>
            <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
              <button
                className="btn btn--secondary btn--sm"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                <Icon name="chevron-left" size={16} />
                Previous
              </button>
              <div style={{ padding: "0 var(--space-4)", fontSize: "var(--font-size-sm)" }}>
                Page {currentPage} of {totalPages}
              </div>
              <button
                className="btn btn--secondary btn--sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <Icon name="chevron-right" size={16} />
              </button>
            </div>
          </div>
        )}
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
      {viewMode === "map" ? (
        <div className="card" style={{ marginBottom: "var(--space-6)" }}>
          <div className="card__header">
            <h3 className="card__title">Device Locations</h3>
            <p className="text-muted" style={{ margin: "var(--space-2) 0 0 0", fontSize: "var(--font-size-sm)" }}>
              Showing {devices.length} device{devices.length !== 1 ? "s" : ""} on map
            </p>
          </div>
          <div className="card__body" style={{ padding: 0 }}>
            <DeviceMapView 
              deviceIds={devices.map(d => d.device_id)}
              height="600px"
              showPopup={true}
            />
          </div>
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid--auto-fit">
          {displayDevices.map((device) => (
            <div
              key={device.id}
              className="card card--interactive"
              onClick={() => navigate(`/devices/${device.device_id}/dashboard`)}
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
                    navigate(`/devices/${device.device_id}/rules`);
                  }}
                  title="Configure Rules"
                >
                  <Icon name="code" size={14} />
                  Rules
                </button>
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
              {displayDevices.map((device) => (
                <tr
                  key={device.id}
                  onClick={() => navigate(`/devices/${device.device_id}/dashboard`)}
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
                        onClick={() => navigate(`/devices/${device.device_id}/rules`)}
                        title="Configure Rules"
                      >
                        <Icon name="code" size={14} />
                        Rules
                      </button>
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
      {devices.length === 0 && !error && (
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
