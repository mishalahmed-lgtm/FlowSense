import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceTable from "../components/DeviceTable.jsx";
import DeviceForm from "../components/DeviceForm.jsx";
import Modal from "../components/Modal.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";

export default function DevicesPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [devices, setDevices] = useState([]);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterProtocol, setFilterProtocol] = useState("all");

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
      
      // Tenant admins don't need to load all tenants - they only work with their own tenant
      // The backend will automatically filter devices by tenant_id
      setTenants([]);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load reference data");
    }
  };

  useEffect(() => {
    if (!token) {
      return;
    }
    loadDevices();
    loadReferenceData();
  }, [token]);
  
  // Only tenant admins can access devices page
  if (!isTenantAdmin) {
    return (
      <div className="page">
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
      // Tenant admins can only create devices for their own tenant
      const payload = {
        ...formValues,
        tenant_id: user.tenant_id, // Force tenant_id to user's tenant
        auto_generate_key: true,
      };
      const response = await api.post("/admin/devices", payload);
      setSuccessMessage("Device created successfully");
      setError(null);
      loadDevices();
      setTimeout(() => {
        closeModal();
      }, 1500);
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
      setTimeout(() => {
        closeModal();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update device");
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    if (!window.confirm("Are you sure you want to delete this device? This action cannot be undone.")) {
      return;
    }
    try {
      await api.delete(`/admin/devices/${deviceId}`);
      setSuccessMessage("Device deleted successfully");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete device");
    }
  };

  const handleRotateKey = async (deviceId) => {
    if (!window.confirm("Are you sure you want to rotate the provisioning key? The old key will no longer work.")) {
      return;
    }
    try {
      await api.post(`/admin/devices/${deviceId}/rotate-key`);
      setSuccessMessage("Provisioning key rotated successfully");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to rotate provisioning key");
    }
  };

  const filteredDevices = devices.filter((device) => {
    if (filterStatus !== "all" && device.is_active !== (filterStatus === "active")) {
      return false;
    }
    if (filterProtocol !== "all") {
      const deviceProtocol = device.protocol?.toLowerCase() || "";
      const filterProtocolLower = filterProtocol.toLowerCase();
      // Handle TCP protocol matching - TCP devices might be stored as "TCP" or "TCP_HEX"
      if (filterProtocolLower === "tcp") {
        if (!deviceProtocol.includes("tcp")) {
          return false;
        }
      } else if (deviceProtocol !== filterProtocolLower) {
        return false;
      }
    }
    return true;
  });

  const activeCount = devices.filter((d) => d.is_active).length;
  const inactiveCount = devices.length - activeCount;

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Devices", path: "/devices" }]} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-8)" }}>
        <div>
          <h1 style={{ marginBottom: "var(--space-2)", fontSize: "var(--font-size-3xl)" }}>
            Device Management
          </h1>
          <p className="text-muted">
            Manage and monitor your IoT devices ({devices.length} total, {activeCount} active)
          </p>
        </div>
        <button className="btn btn--primary" onClick={() => openModal()}>
          + New Device
        </button>
      </div>

      {error && !showModal && (
        <div className="card" style={{ borderColor: "var(--color-error-500)", marginBottom: "var(--space-6)" }}>
          <p className="text-error">{error}</p>
        </div>
      )}

      {successMessage && !showModal && (
        <div className="card" style={{ borderColor: "var(--color-success-500)", marginBottom: "var(--space-6)" }}>
          <p className="text-success">{successMessage}</p>
        </div>
      )}

      {/* Filters */}
      <div className="card" style={{ marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", alignItems: "center" }}>
          <div className="form-group" style={{ minWidth: "150px" }}>
            <label className="form-label">Status</label>
            <select
              className="form-select"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
          <div className="form-group" style={{ minWidth: "150px" }}>
            <label className="form-label">Protocol</label>
            <select
              className="form-select"
              value={filterProtocol}
              onChange={(e) => setFilterProtocol(e.target.value)}
            >
              <option value="all">All Protocols</option>
              <option value="HTTP">HTTP</option>
              <option value="MQTT">MQTT</option>
              <option value="TCP">TCP</option>
            </select>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <span className="text-muted">Showing {filteredDevices.length} of {devices.length}</span>
          </div>
        </div>
      </div>

      {/* Device Table */}
      <div className="card">
        <DeviceTable
          devices={filteredDevices}
          onEdit={(device) => openModal(device)}
          onDelete={handleDeleteDevice}
          onRotateKey={handleRotateKey}
        />
      </div>

      {/* Device Form Modal */}
      <Modal
        isOpen={showModal}
        onClose={closeModal}
        title={selectedDevice ? "Edit Device" : "Add New Device"}
        footer={
          <>
            <button className="btn btn--secondary" onClick={closeModal}>
              Cancel
            </button>
            {selectedDevice?.device_id && (
              <>
                <button
                  className="btn btn--secondary"
                  onClick={() => {
                    closeModal();
                    navigate(`/devices/${selectedDevice.device_id}/rules`);
                  }}
                >
                  Configure Rules
                </button>
                <button
                  className="btn btn--secondary"
                  onClick={() => {
                    closeModal();
                    navigate(`/devices/${selectedDevice.device_id}/dashboard`);
                  }}
                >
                  View Dashboard
                </button>
              </>
            )}
          </>
        }
      >
        {error && (
          <div style={{ marginBottom: "var(--space-4)", padding: "var(--space-3)", backgroundColor: "var(--color-error-50)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-error-200)" }}>
            <p className="text-error" style={{ margin: 0 }}>{error}</p>
          </div>
        )}
        {successMessage && (
          <div style={{ marginBottom: "var(--space-4)", padding: "var(--space-3)", backgroundColor: "var(--color-success-50)", borderRadius: "var(--radius-md)", border: "1px solid var(--color-success-200)" }}>
            <p className="text-success" style={{ margin: 0 }}>{successMessage}</p>
          </div>
        )}
        <DeviceForm
          initialDevice={selectedDevice}
          deviceTypes={deviceTypes}
          tenants={tenants}
          userTenantId={user?.tenant_id}
          onSubmit={selectedDevice ? handleUpdateDevice : handleCreateDevice}
          onCancel={closeModal}
        />
      </Modal>
    </div>
  );
}
