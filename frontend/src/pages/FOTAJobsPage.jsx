import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Modal from "../components/Modal.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";

export default function FOTAJobsPage() {
  const { token, isTenantAdmin, hasModule } = useAuth();
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
      const response = await api.get("/fota/jobs");
      setJobs(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load FOTA jobs");
    }
  };

  const loadDevices = async () => {
    try {
      const response = await api.get("/admin/devices");
      setDevices(response.data);
    } catch (err) {
      console.error("Failed to load devices:", err);
    }
  };

  const loadFirmwareVersions = async () => {
    try {
      const response = await api.get("/fota/firmwares");
      const allVersions = [];
      for (const firmware of response.data) {
        const versionsResp = await api.get(`/fota/firmwares/${firmware.id}/versions`);
        for (const version of versionsResp.data) {
          allVersions.push({
            ...version,
            firmware_name: firmware.name,
            device_type_id: firmware.device_type_id,
          });
        }
      }
      setFirmwareVersions(allVersions);
    } catch (err) {
      console.error("Failed to load firmware versions:", err);
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
      const payload = {
        name: formData.name,
        firmware_version_id: parseInt(formData.firmware_version_id),
        device_ids: formData.device_ids.map(id => parseInt(id)),
      };
      if (formData.scheduled_at) {
        payload.scheduled_at = formData.scheduled_at;
      }
      await api.post("/fota/jobs", payload);
      setShowCreateModal(false);
      setFormData({ name: "", firmware_version_id: "", device_ids: [], scheduled_at: "" });
      await loadJobs();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create FOTA job");
    }
  };

  const handleViewJobDetails = async (jobId) => {
    try {
      const response = await api.get(`/fota/jobs/${jobId}`);
      setSelectedJob(response.data);
      setShowJobDetails(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load job details");
    }
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
              <label className="form-label form-label--required">Select Devices</label>
              <div style={{ 
                maxHeight: "200px", 
                overflowY: "auto", 
                border: "1px solid var(--color-border-medium)", 
                borderRadius: "var(--radius-lg)", 
                padding: "var(--space-4)", 
                backgroundColor: "var(--color-bg-secondary)" 
              }}>
                {devices.map((device) => (
                  <label key={device.id} style={{ 
                    display: "flex", 
                    alignItems: "center", 
                    gap: "var(--space-2)", 
                    marginBottom: "var(--space-3)", 
                    cursor: "pointer" 
                  }}>
                    <input
                      type="checkbox"
                      checked={formData.device_ids.includes(device.id.toString())}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            device_ids: [...formData.device_ids, device.id.toString()],
                          });
                        } else {
                          setFormData({
                            ...formData,
                            device_ids: formData.device_ids.filter(id => id !== device.id.toString()),
                          });
                        }
                      }}
                      style={{ cursor: "pointer" }}
                    />
                    <span>{device.name || device.device_id}</span>
                    <span className="badge badge--neutral" style={{ marginLeft: "auto" }}>
                      {device.protocol}
                    </span>
                  </label>
                ))}
              </div>
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
                  {selectedJob.devices?.length || 0} devices
                </div>
              </div>
            </div>
            
            {selectedJob.devices && selectedJob.devices.length > 0 && (
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
                      {selectedJob.devices.map((device) => (
                        <tr key={device.device_id}>
                          <td>{device.device_name || `Device ${device.device_id}`}</td>
                          <td>
                            <code style={{ fontSize: "var(--font-size-xs)" }}>
                              {device.current_version || selectedJob.firmware_version?.version || "Unknown"}
                            </code>
                          </td>
                          <td>
                            <code style={{ fontSize: "var(--font-size-xs)" }}>
                              {device.target_version || selectedJob.firmware_version?.version || "N/A"}
                            </code>
                          </td>
                          <td>
                            <span className={`badge ${getStatusBadge(device.status)}`}>
                              {device.status}
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
