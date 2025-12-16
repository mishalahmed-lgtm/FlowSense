import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function DeviceTable({ devices, onEdit, onDelete, onRotateKey }) {
  const navigate = useNavigate();
  const [pendingDeleteId, setPendingDeleteId] = useState(null);

  if (!devices.length) {
    return (
      <div style={{ textAlign: "center", padding: "var(--space-12)" }}>
        <p className="text-muted" style={{ fontSize: "var(--font-size-lg)" }}>
          No devices found. Create your first device to get started.
        </p>
      </div>
    );
  }

  const startDelete = (deviceId) => {
    setPendingDeleteId(deviceId);
  };

  const cancelDelete = () => {
    setPendingDeleteId(null);
  };

  const confirmDelete = (deviceId) => {
    setPendingDeleteId(null);
    onDelete(deviceId);
  };

  return (
    <div className="table-wrapper">
      <table className="table">
        <thead>
          <tr>
            <th>Device ID</th>
            <th>Name</th>
            <th>Protocol</th>
            <th>Tenant</th>
            <th>Status</th>
            <th>Provisioning Key</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => {
            const isConfirming = pendingDeleteId === device.device_id;
            return (
              <tr key={device.id}>
                <td>
                  <code style={{ fontSize: "var(--font-size-xs)" }}>{device.device_id}</code>
                </td>
                <td>
                  {device.has_dashboard ? (
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => navigate(`/devices/${device.device_id}/dashboard`)}
                      title="View dashboard"
                      style={{ padding: 0, fontWeight: "var(--font-weight-semibold)", color: "var(--color-primary-600)" }}
                    >
                      {device.name || device.device_id}
                    </button>
                  ) : (
                    <span style={{ fontWeight: "var(--font-weight-medium)" }}>
                      {device.name || "—"}
                    </span>
                  )}
                </td>
                <td>
                  <span className="badge badge--neutral">{device.protocol}</span>
                </td>
                <td>{device.tenant}</td>
                <td>
                  <div className="status-indicator">
                    <span
                      className={`status-indicator__dot ${
                        device.is_active ? "status-indicator__dot--active" : "status-indicator__dot--inactive"
                      }`}
                    />
                    <span>{device.is_active ? "Active" : "Inactive"}</span>
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <code style={{ fontSize: "var(--font-size-xs)", maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {device.provisioning_key?.key || "—"}
                    </code>
                    {device.provisioning_key && (
                      <button
                        className="btn btn--sm btn--ghost"
                        type="button"
                        onClick={() => onRotateKey(device.device_id)}
                        title="Rotate provisioning key"
                      >
                        Rotate
                      </button>
                    )}
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    {!isConfirming && (
                      <>
                        <button
                          className="btn btn--sm btn--secondary"
                          type="button"
                          onClick={() => onEdit(device)}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn--sm btn--danger"
                          type="button"
                          onClick={() => startDelete(device.device_id)}
                        >
                          Delete
                        </button>
                      </>
                    )}
                    {isConfirming && (
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                        <span className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>
                          Delete?
                        </span>
                        <button
                          className="btn btn--sm btn--danger"
                          type="button"
                          onClick={() => confirmDelete(device.device_id)}
                        >
                          Yes
                        </button>
                        <button
                          className="btn btn--sm btn--secondary"
                          type="button"
                          onClick={cancelDelete}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
