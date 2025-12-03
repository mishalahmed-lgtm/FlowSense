import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceTable from "../components/DeviceTable.jsx";
import DeviceForm from "../components/DeviceForm.jsx";

export default function DevicesPage() {
  const { token, isBootstrapping, bootstrapError } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const api = createApiClient(token);
  const [devices, setDevices] = useState([]);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [messageContext, setMessageContext] = useState("list");
  const [showForm, setShowForm] = useState(false);

  const loadDevices = async () => {
    try {
      const response = await api.get("/admin/devices");
      setDevices(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load devices");
      setMessageContext("list");
    }
  };

  const loadReferenceData = async () => {
    try {
      const [typesResponse, tenantsResponse] = await Promise.all([
        api.get("/admin/device-types"),
        api.get("/admin/tenants"),
      ]);
      setDeviceTypes(typesResponse.data);
      setTenants(tenantsResponse.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load reference data");
      setMessageContext("form");
    }
  };

  useEffect(() => {
    if (!token || isBootstrapping || bootstrapError) {
      return;
    }
    loadDevices();
    loadReferenceData();
  }, [token, isBootstrapping, bootstrapError]);

  useEffect(() => {
    if (location.hash === "#add-device") {
      setShowForm(true);
      return;
    }
    if (!selectedDevice) {
      setShowForm(false);
    }
  }, [location.hash, selectedDevice]);

  const openForm = () => {
    setShowForm(true);
    navigate("/devices#add-device");
  };

  const closeForm = () => {
    setShowForm(false);
    setSelectedDevice(null);
    navigate("/devices");
  };

  const handleCreateDevice = async (formValues) => {
    try {
      const response = await api.post("/admin/devices", {
        ...formValues,
        auto_generate_key: true,
      });
      const created = response.data;
      setSuccessMessage("Device created");
      setMessageContext("form");
      setSelectedDevice(created);
      // Ensure form stays open on the newly created device
      setShowForm(true);
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create device");
      setMessageContext("form");
    }
  };

  const handleUpdateDevice = async (formValues) => {
    try {
      await api.put(`/admin/devices/${formValues.device_id}`, formValues);
      setSuccessMessage("Device updated");
      setMessageContext("form");
      setSelectedDevice(null);
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to update device");
      setMessageContext("form");
    }
  };

  const handleDeleteDevice = async (deviceId) => {
    try {
      await api.delete(`/admin/devices/${deviceId}`);
      setSuccessMessage("Device deleted");
      setMessageContext("list");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete device");
      setMessageContext("list");
    }
  };

  const handleRotateKey = async (deviceId) => {
    try {
      await api.post(`/admin/devices/${deviceId}/rotate-key`);
      setSuccessMessage("Provisioning key rotated");
      setMessageContext("list");
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to rotate provisioning key");
      setMessageContext("list");
    }
  };

  const currentFormDevice = selectedDevice;
  const currentDeviceTypeId = currentFormDevice
    ? Number(
        currentFormDevice.device_type_id ??
          currentFormDevice.device_type?.id ??
          currentFormDevice.device_type_id,
      )
    : null;
  const currentDeviceType = deviceTypes.find((type) => type.id === currentDeviceTypeId);

  const isFormVisible = showForm || Boolean(selectedDevice);

  return (
    <div className={`page ${isFormVisible ? "page--form" : "page--split"}`}>
      {!isFormVisible && (
        <section className="page__primary" id="devices-list">
          <div className="section-header">
            <h2>Devices</h2>
            <button
              type="button"
              onClick={() => {
                setSelectedDevice(null);
                openForm();
              }}
            >
              + New Device
            </button>
          </div>
          {messageContext === "list" && (
            <>
              {error && <p className="error-message">{error}</p>}
              {successMessage && <p className="success-message">{successMessage}</p>}
            </>
          )}
          <DeviceTable
            devices={devices}
            onEdit={(device) => {
              setSelectedDevice(device);
              openForm();
            }}
            onDelete={handleDeleteDevice}
            onRotateKey={handleRotateKey}
          />
        </section>
      )}
      {isFormVisible && (
        <section className="page__form" id="add-device">
          <div className="page__form-grid">
            <div className="card">
              <div className="section-header">
                <h2>{currentFormDevice ? "Edit Device" : "Add Device"}</h2>
                <button type="button" className="secondary" onClick={closeForm}>
                  Back to list
                </button>
              </div>
              {messageContext === "form" && (
                <>
                  {error && <p className="error-message">{error}</p>}
                  {successMessage && <p className="success-message">{successMessage}</p>}
                </>
              )}
              <DeviceForm
                initialDevice={currentFormDevice}
                deviceTypes={deviceTypes}
                tenants={tenants}
                onSubmit={currentFormDevice ? handleUpdateDevice : handleCreateDevice}
                onCancel={closeForm}
              />
              {currentFormDevice?.device_id ? (
                <div className="form-actions form-actions--split">
                  <button
                    type="button"
                    onClick={() =>
                      navigate(`/devices/${currentFormDevice.device_id}/rules`)
                    }
                  >
                    Configure Rules
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      navigate(`/devices/${currentFormDevice.device_id}/dashboard`)
                    }
                    className="secondary"
                  >
                    Create Dashboard
                  </button>
                </div>
              ) : (
                <p className="muted">
                  Save the device first, then you can configure rules and create a dashboard.
                </p>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}


