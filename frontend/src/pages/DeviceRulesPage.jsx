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
  const { token, isTenantAdmin, user } = useAuth();
  const api = createApiClient(token);

  const [device, setDevice] = useState(null);
  const [deviceType, setDeviceType] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);

  useEffect(() => {
    if (!token || !isTenantAdmin) {
      return;
    }

    const load = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // For tenant_id = 2 or 3, use Firebase devices
        if (user?.tenant_id === 2 || user?.tenant_id === 3) {
          try {
            const isSmartLPG = user?.tenant_id === 3;
            const mapper = isSmartLPG 
              ? await import("../services/smartLPGDataMapper.js")
              : await import("../services/firebaseDataMapper.js");
            const fetchFunction = isSmartLPG 
              ? mapper.fetchSmartLPGDataForDashboard 
              : mapper.fetchFirebaseDataForDashboard;
            const firebaseData = await fetchFunction();
            
            if (firebaseData.success && firebaseData.devices) {
              const found = firebaseData.devices.find((d) => d.device_id === deviceId);
              if (found) {
                setDevice({
                  ...found,
                  device_type_id: found.device_type_id || 1,
                });
                setDeviceType(null); // No device types in Firebase, but that's OK
                setLoading(false);
                return;
              }
            }
          } catch (fbErr) {
            console.warn("Firebase load failed, continuing:", fbErr);
          }
        }
        
        // For other tenants or fallback, use API
      try {
        const [devicesResp, typesResp] = await Promise.all([
          api.get("/admin/devices"),
            api.get("/admin/device-types").catch(() => ({ data: [] })), // Don't fail if types endpoint doesn't exist
        ]);
          
        // Handle paginated response format
        const devices = Array.isArray(devicesResp.data) 
          ? devicesResp.data 
          : (devicesResp.data?.devices || []);
        
        const found = devices.find((d) => d.device_id === deviceId);
          if (found) {
        setDevice(found);
            const dt = typesResp.data?.find((t) => t.id === found.device_type_id);
        setDeviceType(dt || null);
          } else {
            // Device not found, but still show rules panel with deviceId
            setDevice({
              device_id: deviceId,
              name: `Device ${deviceId}`,
              device_type_id: 1,
            });
            setDeviceType(null);
          }
        } catch (apiErr) {
          // If API fails, still show rules panel with deviceId
          console.warn("API load failed, showing rules panel anyway:", apiErr);
          setDevice({
            device_id: deviceId,
            name: `Device ${deviceId}`,
            device_type_id: 1,
          });
          setDeviceType(null);
        }
      } catch (err) {
        console.error("Failed to load device:", err);
        // Don't set error - still show rules panel
        setDevice({
          device_id: deviceId,
          name: `Device ${deviceId}`,
          device_type_id: 1,
        });
        setDeviceType(null);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [token, api, deviceId, user]);

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
        <div className="page-header__actions">
          <button 
            type="button"
            className="btn btn--primary"
            onClick={() => setShowAddRuleModal(true)}
          >
            <Icon name="plus" size={18} />
            <span>Add Rule</span>
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Rules Panel - Always show, even if device not fully loaded */}
      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <p className="text-muted">Loading device information...</p>
        </div>
      ) : (
        <DeviceRulesPanel
          api={api}
          deviceId={deviceId}
          deviceType={deviceType}
          showModal={showAddRuleModal}
          setShowModal={setShowAddRuleModal}
        />
      )}
    </div>
  );
}


