import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceRulesPanel from "../components/DeviceRulesPanel.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Icon from "../components/Icon.jsx";

export default function DeviceRulesPage() {
  const { deviceId } = useParams();
  const { token, isTenantAdmin } = useAuth();
  const api = createApiClient(token);

  const [device, setDevice] = useState(null);
  const [deviceType, setDeviceType] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !isTenantAdmin) {
      return;
    }

    const load = async () => {
      try {
        const [devicesResp, typesResp] = await Promise.all([
          api.get("/admin/devices"),
          api.get("/admin/device-types"),
        ]);
        // Handle paginated response format
        const devices = Array.isArray(devicesResp.data) 
          ? devicesResp.data 
          : (devicesResp.data?.devices || []);
        
        const found = devices.find((d) => d.device_id === deviceId);
        if (!found) {
          setError("Device not found");
          return;
        }
        setDevice(found);
        const dt = typesResp.data.find((t) => t.id === found.device_type_id);
        setDeviceType(dt || null);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load device or device type");
      }
    };

    load();
  }, [token, api, deviceId]);

  return (
    <div className="page">
      <Breadcrumbs items={[
        { label: "Devices", path: "/devices" },
        { label: device ? (device.name || device.device_id) : "Device", path: `/devices/${deviceId}/dashboard` },
        { label: "Rules", path: `/devices/${deviceId}/rules` }
      ]} />
      
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Configure Rules</h1>
          <p className="page-header__subtitle">
            {device ? `Device: ${device.name || device.device_id}` : "Define automation and routing rules for your device"}
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Rules Panel */}
      {device && (
        <DeviceRulesPanel
          api={api}
          deviceId={device.device_id}
          deviceType={deviceType}
        />
      )}
    </div>
  );
}


