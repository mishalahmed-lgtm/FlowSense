import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import DeviceRulesPanel from "../components/DeviceRulesPanel.jsx";

export default function DeviceRulesPage() {
  const { deviceId } = useParams();
  const { token, isTenantAdmin } = useAuth();
  const navigate = useNavigate();
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
        const found = devicesResp.data.find((d) => d.device_id === deviceId);
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
      <section className="page__primary">
        <div className="section-header">
          <div>
            <h2>Configure Rules</h2>
            {device && (
              <p className="muted">
                Device: <strong>{device.name || device.device_id}</strong>
              </p>
            )}
          </div>
          <button
            type="button"
            className="secondary"
            onClick={() => navigate("/devices")}
          >
            Back to device
          </button>
        </div>
        {error && <p className="error-message">{error}</p>}
        {device && (
          <DeviceRulesPanel
            api={api}
            deviceId={device.device_id}
            deviceType={deviceType}
          />
        )}
      </section>
    </div>
  );
}


