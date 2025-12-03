import { useState } from "react";

export default function DeviceTable({ devices, onEdit, onDelete, onRotateKey }) {
  const [pendingDeleteId, setPendingDeleteId] = useState(null);

  if (!devices.length) {
    return <p className="muted">No devices registered yet.</p>;
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
      <table>
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
                <td>{device.device_id}</td>
                <td>{device.name || "—"}</td>
                <td>{device.protocol}</td>
                <td>{device.tenant}</td>
                <td>
                  <span
                    className={`status ${
                      device.is_active ? "status--ok" : "status--off"
                    }`}
                  >
                    {device.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="provisioning-key-cell">
                  {device.provisioning_key?.key || "—"}
                  {device.provisioning_key && (
                    <button
                      type="button"
                      onClick={() => onRotateKey(device.device_id)}
                    >
                      Rotate
                    </button>
                  )}
                </td>
                <td>
                  <div className="table-actions">
                    {!isConfirming && (
                      <>
                        <button type="button" onClick={() => onEdit(device)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => startDelete(device.device_id)}
                        >
                          Delete
                        </button>
                      </>
                    )}
                    {isConfirming && (
                      <div className="delete-confirm-inline">
                        <span>Delete this device?</span>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => confirmDelete(device.device_id)}
                        >
                          Yes
                        </button>
                        <button
                          type="button"
                          className="secondary"
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


