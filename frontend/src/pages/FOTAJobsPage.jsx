import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Modal from "../components/Modal.jsx";

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
      <div className="page">
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

  const getStatusColor = (status) => {
    switch (status) {
      case "completed": return "text-success";
      case "running": return "text-info";
      case "failed": return "text-error";
      case "cancelled": return "text-muted";
      default: return "";
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="card">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Firmware Updates", path: "/fota/jobs" }]} />
      
      <div className="page-header">
        <h1>Firmware Update Jobs</h1>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          Create Update Job
        </button>
      </div>

      {error && (
        <div className="card card--error">
          <p className="text-error">{error}</p>
        </div>
      )}

      <div className="card">
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
            {jobs.length === 0 ? (
              <tr>
                <td colSpan="6" className="text-center text-muted">
                  No FOTA jobs found. Create one to get started.
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id}>
                  <td>{job.name}</td>
                  <td>{job.firmware_version?.version || "N/A"}</td>
                  <td>{job.device_count || 0}</td>
                  <td>
                    <span className={getStatusColor(job.status)}>
                      {job.status}
                    </span>
                  </td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleViewJobDetails(job.id)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Job Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create Firmware Update Job"
      >
        <form onSubmit={handleCreateJob}>
          <div className="form-group">
            <label>Job Name</label>
            <input
              type="text"
              className="form-control"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label>Firmware Version</label>
            <select
              className="form-control"
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
            <label>Select Devices</label>
            <div style={{ maxHeight: "200px", overflowY: "auto", border: "1px solid #ddd", padding: "8px" }}>
              {devices.map((device) => (
                <label key={device.id} style={{ display: "block", marginBottom: "8px" }}>
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
                  />
                  {device.name} ({device.device_id})
                </label>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Schedule (Optional)</label>
            <input
              type="datetime-local"
              className="form-control"
              value={formData.scheduled_at}
              onChange={(e) => setFormData({ ...formData, scheduled_at: e.target.value })}
            />
            <small className="text-muted">Leave empty to start immediately</small>
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Create Job
            </button>
          </div>
        </form>
      </Modal>

      {/* Job Details Modal */}
      <Modal
        isOpen={showJobDetails}
        onClose={() => setShowJobDetails(false)}
        title={`Job Details: ${selectedJob?.name}`}
      >
        {selectedJob && (
          <div>
            <div className="form-group">
              <strong>Status:</strong> <span className={getStatusColor(selectedJob.status)}>{selectedJob.status}</span>
            </div>
            <div className="form-group">
              <strong>Firmware Version:</strong> {selectedJob.firmware_version?.version || "N/A"}
            </div>
            <div className="form-group">
              <strong>Created:</strong> {new Date(selectedJob.created_at).toLocaleString()}
            </div>
            
            {selectedJob.devices && selectedJob.devices.length > 0 && (
              <div className="form-group">
                <strong>Device Status:</strong>
                <table className="table" style={{ marginTop: "8px" }}>
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
                        <td>{device.device_name || device.device_id}</td>
                        <td>{device.current_version || "Unknown"}</td>
                        <td>{device.target_version || "N/A"}</td>
                        <td>
                          <span className={getStatusColor(device.status)}>
                            {device.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

