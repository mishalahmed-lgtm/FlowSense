import { useEffect, useState } from "react";
import PropTypes from "prop-types";

export default function DeviceDashboard({ api, device }) {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadDashboard = async () => {
    if (!device?.device_id) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(
        `/dashboard/devices/${device.device_id}/dashboard`,
      );
      setDashboard(response.data);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device?.device_id]);

  if (!device?.device_id) {
    return null;
  }

  if (!dashboard && !error) {
    return (
      <div className="card muted-panel">
        <h4>Device Dashboard</h4>
        <p className="muted">Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card muted-panel">
        <h4>Device Dashboard</h4>
        <p className="error-message">{error}</p>
      </div>
    );
  }

  const widgets = dashboard?.config?.widgets || [];
  const data = dashboard?.latest?.data || {};
  const eventTimestamp = dashboard?.latest?.event_timestamp;

  return (
    <div className="card device-dashboard">
      <div className="section-header">
        <h3>Live Dashboard</h3>
        <div className="device-dashboard__meta">
          {eventTimestamp && (
            <span className="device-dashboard__timestamp">
              Device update: {new Date(eventTimestamp).toLocaleString()}
            </span>
          )}
          {lastRefresh && (
            <span className="device-dashboard__timestamp">
              Page refresh: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            type="button"
            className="secondary"
            onClick={loadDashboard}
            disabled={loading}
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>
      {widgets.length === 0 && (
        <p className="muted">No widgets configured for this device.</p>
      )}
      <div className="dashboard-grid">
        {widgets.map((widget) => (
          <DashboardWidget key={widget.id} widget={widget} data={data} />
        ))}
      </div>
    </div>
  );
}

DeviceDashboard.propTypes = {
  api: PropTypes.object.isRequired,
  device: PropTypes.object,
};

function DashboardWidget({ widget, data }) {
  const value = data?.[widget.field];

  if (widget.type === "gauge") {
    const min = widget.min ?? 0;
    const max = widget.max ?? 100;
    const numeric = typeof value === "number" ? value : null;
    const clamped =
      numeric === null ? min : Math.min(max, Math.max(min, numeric));
    const pct =
      max === min ? 0 : ((clamped - min) / (max - min)) * 100;

    return (
      <div className="dashboard-widget dashboard-widget--gauge">
        <div className="dashboard-widget__label">{widget.label || widget.field}</div>
        <div className="gauge">
          <div className="gauge__fill" style={{ width: `${pct}%` }} />
          <div className="gauge__value">
            {numeric !== null ? numeric : "—"}
            {widget.unit ? <span className="gauge__unit">{widget.unit}</span> : null}
          </div>
        </div>
      </div>
    );
  }

  // Default: simple stat card
  return (
    <div className="dashboard-widget dashboard-widget--stat">
      <div className="dashboard-widget__label">{widget.label || widget.field}</div>
      <div className="dashboard-widget__value">
        {value !== undefined && value !== null ? String(value) : "—"}
        {widget.unit ? <span className="dashboard-widget__unit">{widget.unit}</span> : null}
      </div>
    </div>
  );
}

DashboardWidget.propTypes = {
  widget: PropTypes.object.isRequired,
  data: PropTypes.object,
};


