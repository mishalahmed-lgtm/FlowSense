import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Modal from "../components/Modal.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import { isSmartLPGTenant, isFirebaseTenant } from "../utils/tenantHelpers.js";

export default function FOTAJobsPage() {
  const { token, isTenantAdmin, hasModule, user } = useAuth();
  const navigate = useNavigate();
  const api = createApiClient(token);
  
  const [jobs, setJobs] = useState([]);
  const [devices, setDevices] = useState([]);
  const [firmwareVersions, setFirmwareVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [showJobDetails, setShowJobDetails] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [deviceSearchQuery, setDeviceSearchQuery] = useState("");
  
  // Form state
  const [formData, setFormData] = useState({
    name: "",
    firmware_version_id: "",
    device_ids: [],
    scheduled_at: "",
  });

  // Only tenant admins with fota module can access
  if (!isTenantAdmin || !hasModule("fota")) {
    return (
      <div className="page page--centered">
        <div className="card">
          <p className="text-error">Access denied. This page requires FOTA module access.</p>
        </div>
      </div>
    );
  }

  const loadJobs = async () => {
    try {
      // For SmartLPG tenant, load from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { getFOTAJobsFromFirebase } = await import("../services/smartLPGFirebaseService.js");
        const jobs = await getFOTAJobsFromFirebase(user?.tenant_id);
        setJobs(jobs);
        setError(null);
        return;
      }
      
      // For other tenants, use backend API
      const response = await api.get("/fota/jobs");
      setJobs(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to load FOTA jobs");
    }
  };

  const loadDevices = async () => {
    try {
      // For Firebase tenants (tenant_id = 2 or 3), load from Firebase
      const isSmartLPG = isSmartLPGTenant(user?.tenant_id);
      const isFirebase = isFirebaseTenant(user?.tenant_id);
      
      if (isFirebase || isSmartLPG) {
        console.log(`🔥 [FOTA] Loading devices from Firebase for tenant_id = ${user?.tenant_id}...`);
        try {
          const mapper = isSmartLPG 
            ? await import("../services/smartLPGDataMapper.js")
            : await import("../services/firebaseDataMapper.js");
          const fetchFunction = isSmartLPG 
            ? mapper.fetchSmartLPGDataForDashboard 
            : mapper.fetchFirebaseDataForDashboard;
          const firebaseData = await fetchFunction();
          
          if (firebaseData.success && firebaseData.devices) {
            // Map Firebase devices to format expected by FOTA modal
            const mappedDevices = firebaseData.devices.map((device, index) => ({
              id: device.id || device.device_id || `firebase_${index}`,
              device_id: device.device_id || device.id,
              name: device.name || device.device_name || device.device_id,
              protocol: device.protocol || "HTTP",
              device_type: device.device_type || "",
              is_active: device.is_active !== false
            }));
            
            console.log(`✅ [FOTA] Loaded ${mappedDevices.length} devices from Firebase`);
            setDevices(mappedDevices);
            return;
          }
        } catch (fbErr) {
          console.error("❌ [FOTA] Firebase load failed:", fbErr);
          // Fall through to backend API
        }
      }
      
      // For other tenants or fallback, use backend API
      const response = await api.get("/admin/devices");
      // Handle paginated response
      const devicesData = response.data?.devices || (Array.isArray(response.data) ? response.data : []);
      setDevices(devicesData);
    } catch (err) {
      console.error("Failed to load devices:", err);
      setDevices([]); // Ensure devices is always an array
    }
  };

  const loadFirmwareVersions = async () => {
    try {
      const response = await api.get("/fota/firmwares");
      const allVersions = [];
      if (response.data && Array.isArray(response.data)) {
      for (const firmware of response.data) {
          try {
        const versionsResp = await api.get(`/fota/firmwares/${firmware.id}/versions`);
            if (versionsResp.data && Array.isArray(versionsResp.data)) {
        for (const version of versionsResp.data) {
          allVersions.push({
            ...version,
            firmware_name: firmware.name,
            device_type_id: firmware.device_type_id,
          });
              }
            }
          } catch (versionErr) {
            console.error(`Failed to load versions for firmware ${firmware.id}:`, versionErr);
          }
        }
      }
      setFirmwareVersions(allVersions);
    } catch (err) {
      console.error("Failed to load firmware versions:", err);
      setFirmwareVersions([]); // Ensure it's always an array
    }
  };

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    Promise.all([loadJobs(), loadDevices(), loadFirmwareVersions()]).finally(() => {
      setLoading(false);
    });
  }, [token]);

  const handleCreateJob = async (e) => {
    e.preventDefault();
    try {
      setError(null);
      
      // Validate device selection
      if (!formData.device_ids || formData.device_ids.length === 0) {
        setError("Please select at least one device");
        return;
      }
      
      const payload = {
        name: formData.name,
        firmware_version_id: parseInt(formData.firmware_version_id),
        device_ids: formData.device_ids.map(id => {
          // Try to parse as integer, but keep original if it fails (for Firebase device IDs)
          const parsed = parseInt(id);
          return isNaN(parsed) ? id : parsed;
        }),
        tenant_id: user?.tenant_id,
      };
      if (formData.scheduled_at) {
        payload.scheduled_at = formData.scheduled_at;
      }
      
      // For SmartLPG tenant, save to Firebase instead of PostgreSQL
      if (isSmartLPGTenant(user?.tenant_id)) {
        const { saveFOTAJobToFirebase } = await import("../services/smartLPGFirebaseService.js");
        const firmwareVersion = firmwareVersions.find(fv => fv.id === payload.firmware_version_id);
        if (!firmwareVersion) {
          setError("Firmware version not found");
          return;
        }
        
        const fotaJob = {
          name: payload.name,
          tenant_id: payload.tenant_id,
          firmware_version_id: payload.firmware_version_id,
          firmware_version: firmwareVersion.version,
          device_ids: payload.device_ids,
          device_count: payload.device_ids.length,
          status: payload.scheduled_at ? "scheduled" : "running",
          scheduled_at: payload.scheduled_at || null,
          started_at: payload.scheduled_at ? null : new Date().toISOString(),
          completed_at: null,
          created_by_user_id: user?.id || null,
        };
        
        await saveFOTAJobToFirebase(fotaJob);
        setShowCreateModal(false);
        setFormData({ name: "", firmware_version_id: "", device_ids: [], scheduled_at: "" });
        setDeviceSearchQuery("");
        await loadJobs();
        setError(null);
      } else {
      await api.post("/fota/jobs", payload);
      setShowCreateModal(false);
      setFormData({ name: "", firmware_version_id: "", device_ids: [], scheduled_at: "" });
      setDeviceSearchQuery("");
      await loadJobs();
      }
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || "Failed to create FOTA job";
      setError(errorMsg);
      console.error("FOTA job creation error:", err);
    }
  };

  const handleViewJobDetails = async (jobId) => {
    try {
      // For SmartLPG tenant, get job from Firebase
      if (isSmartLPGTenant(user?.tenant_id)) {
        // Find the job from the already loaded jobs
        const job = jobs.find(j => j.id === jobId);
        if (job) {
          setSelectedJob(job);
          setShowJobDetails(true);
        } else {
          setError("Job not found");
        }
      } else {
        // For other tenants, use backend API
        const response = await api.get(`/fota/jobs/${jobId}`);
        setSelectedJob(response.data);
        setShowJobDetails(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load job details");
    }
  };

  // Filter devices based on search query
  const getFilteredDevices = () => {
    if (!deviceSearchQuery.trim()) {
      return devices;
    }
    const query = deviceSearchQuery.toLowerCase();
    return devices.filter(device => {
      const name = (device.name || device.device_name || "").toLowerCase();
      const deviceId = (device.device_id || device.id || "").toLowerCase();
      return name.includes(query) || deviceId.includes(query);
    });
  };

  const getStatusBadge = (status) => {
    const badges = {
      completed: "badge--success",
      running: "badge--info",
      failed: "badge--error",
      cancelled: "badge--neutral",
      pending: "badge--warning",
    };
    return badges[status] || "badge--neutral";
  };

  if (loading) {
    return (
      <div className="page page--centered">
        <div className="card">
          <div style={{ marginBottom: "var(--space-4)", opacity: 0.3 }}>
            <Icon name="firmware" size={48} />
          </div>
          <p style={{ color: "var(--color-text-secondary)" }}>Loading firmware update jobs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Firmware Updates", path: "/fota/jobs" }]} />
      
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Firmware Updates</h1>
          <p className="page-header__subtitle">
            Manage over-the-air firmware update jobs
          </p>
        </div>
        <div className="page-header__actions">
          {isSmartLPGTenant(user?.tenant_id) && jobs.length === 0 && (
            <button
              className="btn btn--secondary"
              onClick={async () => {
                setSeeding(true);
                setError(null);
                try {
                  console.log("🌱 Starting FOTA jobs seeding...");
                  const seedModule = await import("../scripts/seedSmartLPGData.js");
                  const result = await seedModule.seedFOTAJobs();
                  console.log("✅ Seeding result:", result);
                  // Reload jobs after seeding
                  await loadJobs();
                  alert(`✅ Successfully seeded ${result.count} FOTA jobs!`);
                } catch (error) {
                  console.error("❌ Seeding error:", error);
                  setError("Failed to seed data: " + error.message);
                  alert("❌ Error seeding data: " + error.message);
                } finally {
                  setSeeding(false);
                }
              }}
              disabled={seeding}
            >
              {seeding ? "Seeding Data..." : "Seed Sample Data"}
            </button>
          )}
          <button className="btn-icon" onClick={loadJobs} title="Refresh">
            <Icon name="refresh" size={18} />
          </button>
          <button className="btn btn--primary" onClick={() => setShowCreateModal(true)}>
            <Icon name="plus" size={18} />
            <span>Create Update Job</span>
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Summary Cards */}
      <div className="metrics-grid" style={{ marginBottom: "var(--space-8)" }}>
        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--primary">
              <Icon name="firmware" size={24} />
            </div>
          </div>
          <div className="metric-card__label">TOTAL JOBS</div>
          <div className="metric-card__value">{jobs.filter(j => j.status !== "running" && j.status !== "failed").length}</div>
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            Active jobs
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--success">
              <Icon name="check" size={24} />
            </div>
          </div>
          <div className="metric-card__label">COMPLETED</div>
          <div className="metric-card__value">{jobs.filter(j => j.status === "completed").length}</div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--info">
              <Icon name="devices" size={24} />
            </div>
          </div>
          <div className="metric-card__label">TOTAL DEVICES</div>
          <div className="metric-card__value">{devices.length}</div>
          <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-2)" }}>
            Unique devices (note: devices may appear in multiple jobs)
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      {jobs.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
          <div style={{ marginBottom: "var(--space-4)", opacity: 0.3 }}>
            <Icon name="firmware" size={64} />
          </div>
          <h3 style={{ marginBottom: "var(--space-2)", color: "var(--color-text-secondary)" }}>
            No firmware update jobs yet
          </h3>
          <p style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-6)" }}>
            Create your first update job to manage device firmware
          </p>
          <button className="btn btn--primary" onClick={() => setShowCreateModal(true)}>
            <Icon name="plus" size={18} />
            <span>Create First Job</span>
          </button>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Job Name</th>
                <th>Firmware Version</th>
                <th>Devices</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.filter(job => job.status !== "running" && job.status !== "failed").map((job) => (
                <tr key={job.id}>
                  <td style={{ fontWeight: "var(--font-weight-semibold)" }}>{job.name}</td>
                  <td>
                    <code style={{ 
                      padding: "0.25rem 0.5rem", 
                      backgroundColor: "var(--color-bg-secondary)", 
                      borderRadius: "var(--radius-sm)",
                      fontSize: "var(--font-size-xs)"
                    }}>
                      {job.firmware_version?.version || "N/A"}
                    </code>
                  </td>
                  <td>{job.device_count || 0} devices</td>
                  <td>
                    <span className={`badge ${getStatusBadge(job.status)}`}>
                      {job.status}
                    </span>
                  </td>
                  <td style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)" }}>
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td>
                    <button
                      className="btn btn--sm btn--ghost"
                      onClick={() => handleViewJobDetails(job.id)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Job Modal */}
      {showCreateModal && (
        <Modal
          onClose={() => setShowCreateModal(false)}
          title="Create Firmware Update Job"
        >
          <form onSubmit={handleCreateJob} className="form">
            <div className="form-group">
              <label className="form-label form-label--required">Job Name</label>
              <input
                type="text"
                className="form-input"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Smart Bench v2.1 Update"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label form-label--required">Firmware Version</label>
              <select
                className="form-select"
                value={formData.firmware_version_id}
                onChange={(e) => setFormData({ ...formData, firmware_version_id: e.target.value })}
                required
              >
                <option value="">Select firmware version...</option>
                {firmwareVersions.map((fv) => (
                  <option key={fv.id} value={fv.id}>
                    {fv.firmware_name} - v{fv.version} {fv.is_recommended ? "(Recommended)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <div style={{ 
                display: "flex", 
                justifyContent: "space-between", 
                alignItems: "center",
                marginBottom: "var(--space-3)"
              }}>
                <label className="form-label form-label--required" style={{ marginBottom: 0 }}>
                  Select Devices
                </label>
                {devices && devices.length > 0 && (
                  <span style={{ 
                    fontSize: "var(--font-size-xs)", 
                    color: "var(--color-text-tertiary)",
                    fontWeight: "500"
                  }}>
                    {devices.length} total devices
                  </span>
                )}
              </div>
              {devices && devices.length > 0 ? (
                <>
                  {/* Enhanced Search input */}
                  <div style={{ 
                    marginBottom: "var(--space-4)", 
                    position: "relative" 
                  }}>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Type to search by device name or ID... (Press / to focus)"
                      value={deviceSearchQuery}
                      onChange={(e) => setDeviceSearchQuery(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          setDeviceSearchQuery("");
                          e.target.blur();
                        }
                      }}
                      style={{ 
                        paddingLeft: "var(--space-12)",
                        paddingRight: deviceSearchQuery ? "var(--space-10)" : "var(--space-4)",
                        fontSize: "var(--font-size-base)",
                        minHeight: "44px",
                        transition: "all 0.2s ease",
                        border: "2px solid var(--color-border-medium)"
                      }}
                      onFocus={(e) => {
                        e.target.style.borderColor = "var(--color-primary)";
                        e.target.style.boxShadow = "0 0 0 3px var(--color-primary-light)";
                      }}
                      onBlur={(e) => {
                        e.target.style.borderColor = "var(--color-border-medium)";
                        e.target.style.boxShadow = "none";
                      }}
                    />
                    <div style={{ 
                      position: "absolute", 
                      left: "var(--space-4)", 
                      top: "50%", 
                      transform: "translateY(-50%)",
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      pointerEvents: "none"
                    }}>
                      <Icon 
                        name="search" 
                        size={18} 
                        style={{ 
                          color: "var(--color-text-tertiary)"
                        }} 
                      />
                    </div>
                    {deviceSearchQuery && (
                      <button
                        type="button"
                        onClick={() => setDeviceSearchQuery("")}
                        aria-label="Clear search"
                        style={{
                          position: "absolute",
                          right: "var(--space-3)",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "var(--color-bg-tertiary)",
                          border: "none",
                          borderRadius: "var(--radius-full)",
                          cursor: "pointer",
                          padding: "var(--space-1)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "var(--color-text-secondary)",
                          transition: "all 0.2s ease",
                          width: "28px",
                          height: "28px"
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.background = "var(--color-error)";
                          e.currentTarget.style.color = "white";
                          e.currentTarget.style.transform = "translateY(-50%) scale(1.1)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = "var(--color-bg-tertiary)";
                          e.currentTarget.style.color = "var(--color-text-secondary)";
                          e.currentTarget.style.transform = "translateY(-50%) scale(1)";
                        }}
                      >
                        <Icon name="x" size={14} />
                      </button>
                    )}
                    {deviceSearchQuery && getFilteredDevices().length === 0 && (
                      <div style={{
                        position: "absolute",
                        right: deviceSearchQuery ? "var(--space-12)" : "var(--space-4)",
                        top: "50%",
                        transform: "translateY(-50%)",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-tertiary)",
                        pointerEvents: "none"
                      }}>
                        No results
                      </div>
                    )}
                  </div>
                  
                  {/* Enhanced Selection controls */}
                  <div style={{ 
                    display: "flex", 
                    gap: "var(--space-3)", 
                    marginBottom: "var(--space-4)",
                    flexWrap: "wrap",
                    alignItems: "center",
                    padding: "var(--space-4)",
                    backgroundColor: "var(--color-bg-secondary)",
                    borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--color-border-medium)",
                    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.1)"
                  }}>
                    <button
                      type="button"
                      className="btn btn--sm btn--primary"
                      onClick={() => {
                        const filtered = getFilteredDevices();
                        const allIds = filtered.map(d => (d.id || d.device_id || `device_${d.device_id}`).toString());
                        setFormData({
                          ...formData,
                          device_ids: [...new Set([...formData.device_ids, ...allIds])],
                        });
                      }}
                      style={{
                        fontWeight: "600",
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                        padding: "var(--space-2) var(--space-4)",
                        transition: "all 0.2s ease"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "translateY(-1px)";
                        e.currentTarget.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.15)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    >
                      <Icon name="check-circle" size={16} />
                      Select All ({getFilteredDevices().length})
                    </button>
                    <button
                      type="button"
                      className="btn btn--sm btn--secondary"
                      onClick={() => {
                        const filtered = getFilteredDevices();
                        const filteredIds = filtered.map(d => (d.id || d.device_id || `device_${d.device_id}`).toString());
                        setFormData({
                          ...formData,
                          device_ids: formData.device_ids.filter(id => !filteredIds.includes(id)),
                        });
                      }}
                      disabled={formData.device_ids.length === 0}
                      style={{
                        fontWeight: "600",
                        padding: "var(--space-2) var(--space-4)",
                        transition: "all 0.2s ease",
                        opacity: formData.device_ids.length === 0 ? 0.5 : 1,
                        cursor: formData.device_ids.length === 0 ? "not-allowed" : "pointer"
                      }}
                      onMouseEnter={(e) => {
                        if (formData.device_ids.length > 0) {
                          e.currentTarget.style.transform = "translateY(-1px)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                      }}
                    >
                      Deselect All
                    </button>
                    {formData.device_ids.length > 0 && (
                      <div style={{ 
                        marginLeft: "auto",
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                        padding: "var(--space-3) var(--space-4)",
                        backgroundColor: "var(--color-primary)",
                        borderRadius: "var(--radius-md)",
                        color: "white",
                        fontSize: "var(--font-size-sm)",
                        fontWeight: "700",
                        boxShadow: "0 2px 4px rgba(0, 0, 0, 0.1)",
                        transition: "all 0.2s ease"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "scale(1.05)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "scale(1)";
                      }}
                      >
                        <Icon name="check-circle" size={18} style={{ color: "white" }} />
                        <span>{formData.device_ids.length}</span>
                        <span style={{ opacity: 0.9, fontWeight: "500" }}>
                          {formData.device_ids.length === 1 ? "device" : "devices"} selected
                        </span>
                      </div>
                    )}
                    {deviceSearchQuery && (
                      <div style={{ 
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                        padding: "var(--space-2) var(--space-3)",
                        backgroundColor: "var(--color-bg-tertiary)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-secondary)",
                        fontWeight: "500"
                      }}>
                        <Icon name="filter" size={14} />
                        <span>
                          {getFilteredDevices().length} of {devices.length} devices
                        </span>
                      </div>
                    )}
                  </div>
                  
                  {/* Enhanced Device list */}
                  <div style={{ 
                    maxHeight: "400px", 
                    overflowY: "auto", 
                    overflowX: "hidden",
                    border: "2px solid var(--color-border-medium)", 
                    borderRadius: "var(--radius-lg)", 
                    padding: "var(--space-2)", 
                    backgroundColor: "var(--color-bg-secondary)",
                    boxShadow: "inset 0 2px 8px rgba(0, 0, 0, 0.08)"
                  }}
                  onScroll={(e) => {
                    // Add subtle shadow on scroll
                    if (e.target.scrollTop > 0) {
                      e.target.style.boxShadow = "inset 0 2px 8px rgba(0, 0, 0, 0.08), 0 -2px 8px rgba(0, 0, 0, 0.05)";
                    } else {
                      e.target.style.boxShadow = "inset 0 2px 8px rgba(0, 0, 0, 0.08)";
                    }
                  }}
                  >
                    {getFilteredDevices().length > 0 ? (
                      <>
                        {getFilteredDevices().map((device, index) => {
                          const deviceId = device.id || device.device_id || `device_${device.device_id}`;
                          const isSelected = formData.device_ids.includes(deviceId.toString());
                          return (
                            <label 
                              key={deviceId} 
                              style={{ 
                                display: "flex", 
                                alignItems: "center", 
                                gap: "var(--space-3)", 
                                padding: "var(--space-4)",
                                marginBottom: "var(--space-2)", 
                                cursor: "pointer",
                                borderRadius: "var(--radius-md)",
                                backgroundColor: isSelected 
                                  ? "var(--color-primary-light)" 
                                  : "var(--color-bg-primary)",
                                border: `2px solid ${isSelected ? "var(--color-primary)" : "transparent"}`,
                                transition: "all 0.15s ease",
                                position: "relative",
                                overflow: "hidden"
                              }}
                              onMouseEnter={(e) => {
                                if (!isSelected) {
                                  e.currentTarget.style.backgroundColor = "var(--color-bg-tertiary)";
                                  e.currentTarget.style.borderColor = "var(--color-border-medium)";
                                  e.currentTarget.style.transform = "translateX(4px)";
                                } else {
                                  e.currentTarget.style.transform = "translateX(2px)";
                                }
                              }}
                              onMouseLeave={(e) => {
                                if (!isSelected) {
                                  e.currentTarget.style.backgroundColor = "var(--color-bg-primary)";
                                  e.currentTarget.style.borderColor = "transparent";
                                }
                                e.currentTarget.style.transform = "translateX(0)";
                              }}
                            >
                              {/* Selection indicator */}
                              {isSelected && (
                                <div style={{
                                  position: "absolute",
                                  left: 0,
                                  top: 0,
                                  bottom: 0,
                                  width: "4px",
                                  backgroundColor: "var(--color-primary)"
                                }} />
                              )}
                              
                              <div style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                width: "24px",
                                height: "24px",
                                flexShrink: 0
                              }}>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => {
                                    if (e.target.checked) {
                                      setFormData({
                                        ...formData,
                                        device_ids: [...formData.device_ids, deviceId.toString()],
                                      });
                                    } else {
                                      setFormData({
                                        ...formData,
                                        device_ids: formData.device_ids.filter(id => id !== deviceId.toString()),
                                      });
                                    }
                                  }}
                                  style={{ 
                                    cursor: "pointer",
                                    width: "20px",
                                    height: "20px",
                                    accentColor: "var(--color-primary)",
                                    margin: 0
                                  }}
                                />
                              </div>
                              
                              <div style={{ 
                                flex: 1, 
                                display: "flex", 
                                flexDirection: "column", 
                                gap: "var(--space-1)",
                                minWidth: 0
                              }}>
                                <div style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "var(--space-2)"
                                }}>
                                  <span style={{ 
                                    fontWeight: isSelected ? "700" : "600",
                                    color: isSelected ? "var(--color-primary)" : "var(--color-text-primary)",
                                    fontSize: "var(--font-size-base)",
                                    transition: "all 0.15s ease"
                                  }}>
                                    {device.name || device.device_name || device.device_id}
                                  </span>
                                  {isSelected && (
                                    <Icon 
                                      name="check-circle" 
                                      size={16} 
                                      style={{ 
                                        color: "var(--color-primary)",
                                        flexShrink: 0
                                      }} 
                                    />
                                  )}
                                </div>
                                {device.device_id && (
                                  <span style={{ 
                                    fontSize: "var(--font-size-xs)", 
                                    color: "var(--color-text-tertiary)",
                                    fontFamily: "var(--font-family-mono)",
                                    opacity: 0.9,
                                    letterSpacing: "0.5px"
                                  }}>
                                    ID: {device.device_id}
                                  </span>
                                )}
                              </div>
                              
                              <span 
                                className="badge badge--neutral" 
                                style={{ 
                                  marginLeft: "auto",
                                  flexShrink: 0,
                                  fontSize: "var(--font-size-xs)",
                                  padding: "var(--space-2) var(--space-3)",
                                  fontWeight: "600",
                                  borderRadius: "var(--radius-sm)"
                                }}
                              >
                                {device.protocol || "HTTP"}
                              </span>
                            </label>
                          );
                        })}
                      </>
                    ) : (
                      <div style={{ 
                        textAlign: "center", 
                        padding: "var(--space-8) var(--space-4)",
                        color: "var(--color-text-secondary)"
                      }}>
                        <div style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: "64px",
                          height: "64px",
                          borderRadius: "var(--radius-full)",
                          backgroundColor: "var(--color-bg-tertiary)",
                          marginBottom: "var(--space-4)",
                          opacity: 0.6
                        }}>
                          <Icon name="search" size={32} style={{ 
                            color: "var(--color-text-tertiary)"
                          }} />
                        </div>
                        <p style={{ 
                          fontSize: "var(--font-size-base)",
                          marginBottom: "var(--space-2)",
                          fontWeight: "600",
                          color: "var(--color-text-primary)"
                        }}>
                          No devices found
                        </p>
                        <p style={{ 
                          fontSize: "var(--font-size-sm)",
                          color: "var(--color-text-tertiary)",
                          marginBottom: "var(--space-3)"
                        }}>
                          No devices match your search: <strong>"{deviceSearchQuery}"</strong>
                        </p>
                        <button
                          type="button"
                          className="btn btn--sm btn--ghost"
                          onClick={() => setDeviceSearchQuery("")}
                          style={{
                            fontSize: "var(--font-size-xs)"
                          }}
                        >
                          Clear search
                        </button>
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ 
                  padding: "var(--space-4)", 
                  border: "1px solid var(--color-border-medium)", 
                  borderRadius: "var(--radius-lg)", 
                  backgroundColor: "var(--color-bg-secondary)",
                  textAlign: "center",
                  color: "var(--color-text-secondary)"
                }}>
                  <Icon name="inbox" size={24} style={{ opacity: 0.5, marginBottom: "var(--space-2)" }} />
                  <p>No devices available. Please ensure devices are loaded.</p>
                </div>
              )}
            </div>

            <div className="form-group">
              <label className="form-label">Schedule (Optional)</label>
              <input
                type="datetime-local"
                className="form-input"
                value={formData.scheduled_at}
                onChange={(e) => setFormData({ ...formData, scheduled_at: e.target.value })}
              />
              <small style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginTop: "var(--space-1)", display: "block" }}>
                Leave empty to start immediately
              </small>
            </div>

            <div className="modal__footer">
              <button type="button" className="btn btn--secondary" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn--primary">
                Create Job
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Job Details Modal */}
      {showJobDetails && selectedJob && (
        <Modal
          onClose={() => setShowJobDetails(false)}
          title={`Job Details: ${selectedJob.name}`}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
            <div style={{ 
              display: "grid", 
              gridTemplateColumns: "1fr 1fr", 
              gap: "var(--space-4)",
              padding: "var(--space-4)",
              backgroundColor: "var(--color-bg-secondary)",
              borderRadius: "var(--radius-lg)"
            }}>
              <div>
                <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}>
                  Status
                </div>
                <span className={`badge ${getStatusBadge(selectedJob.status)}`}>
                  {selectedJob.status}
                </span>
              </div>
              <div>
                <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}>
                  Firmware Version
                </div>
                <code style={{ 
                  padding: "0.25rem 0.5rem", 
                  backgroundColor: "var(--color-bg-tertiary)", 
                  borderRadius: "var(--radius-sm)",
                  fontSize: "var(--font-size-xs)"
                }}>
                  {selectedJob.firmware_version?.version || "N/A"}
                </code>
              </div>
              <div>
                <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}>
                  Created
                </div>
                <div style={{ fontSize: "var(--font-size-sm)" }}>
                  {new Date(selectedJob.created_at).toLocaleString()}
                </div>
              </div>
              <div>
                <div style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}>
                  Devices
                </div>
                <div style={{ fontSize: "var(--font-size-sm)" }}>
                  {selectedJob.device_count || selectedJob.device_ids?.length || selectedJob.devices?.length || 0} devices
                </div>
              </div>
            </div>
            
            {((selectedJob.device_ids && selectedJob.device_ids.length > 0) || (selectedJob.devices && selectedJob.devices.length > 0)) && (
              <div>
                <h3 style={{ fontSize: "var(--font-size-base)", marginBottom: "var(--space-4)" }}>
                  Device Status
                </h3>
                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Device</th>
                        <th>Current Version</th>
                        <th>Target Version</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedJob.devices || selectedJob.device_ids?.map(id => ({ device_id: id })) || []).map((device, idx) => (
                        <tr key={device.device_id || device.id || idx}>
                          <td>{device.device_name || device.name || `Device ${device.device_id || device.id || idx + 1}`}</td>
                          <td>
                            <code style={{ fontSize: "var(--font-size-xs)" }}>
                              {device.current_version || selectedJob.firmware_version || selectedJob.firmware_version?.version || "Unknown"}
                            </code>
                          </td>
                          <td>
                            <code style={{ fontSize: "var(--font-size-xs)" }}>
                              {device.target_version || selectedJob.firmware_version || selectedJob.firmware_version?.version || "N/A"}
                            </code>
                          </td>
                          <td>
                            <span className={`badge ${getStatusBadge(device.status || selectedJob.status)}`}>
                              {device.status || selectedJob.status || "pending"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
