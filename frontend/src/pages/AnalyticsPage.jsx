import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import Tabs from "../components/Tabs.jsx";
import Modal from "../components/Modal.jsx";

export default function AnalyticsPage() {
  const { token, isTenantAdmin, hasModule } = useAuth();
  const api = createApiClient(token);
  
  const [activeTab, setActiveTab] = useState("insights");
  const [devices, setDevices] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Pattern analysis
  const [patternResults, setPatternResults] = useState([]);
  const [analyzingPatterns, setAnalyzingPatterns] = useState(false);
  
  // Correlation analysis
  const [correlationResults, setCorrelationResults] = useState([]);
  const [analyzingCorrelations, setAnalyzingCorrelations] = useState(false);
  const [correlationForm, setCorrelationForm] = useState({
    device1: "",
    device2: "",
    field1: "",
    field2: ""
  });
  
  // ML Training
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [trainingModel, setTrainingModel] = useState(false);
  const [trainForm, setTrainForm] = useState({
    name: "",
    model_type: "anomaly_detection",
    algorithm: "isolation_forest",
    device_ids: [],
    days: 30
  });

  // Only tenant admins with analytics module can access
  if (!isTenantAdmin || !hasModule("analytics")) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page requires analytics module access.</p>
        </div>
      </div>
    );
  }

  const loadData = async () => {
    try {
      setLoading(true);
      const [devicesRes, predictionsRes, modelsRes] = await Promise.all([
        api.get("/admin/devices"),
        api.get("/analytics/predictions", { params: { limit: 20 } }),
        api.get("/analytics/models")
      ]);
      
      setDevices(devicesRes.data);
      setPredictions(predictionsRes.data);
      setModels(modelsRes.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load analytics data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!token) return;
    loadData();
    
    // Auto-refresh every 60 seconds
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [token]);

  const handleAnalyzePatterns = async () => {
    if (devices.length === 0) {
      setError("No devices available for analysis");
      return;
    }
    
    try {
      setAnalyzingPatterns(true);
      setError(null);
      const resp = await api.post("/analytics/analyze-patterns", {
        device_ids: devices.map(d => d.device_id),
        analysis_type: "occupancy",
        days: 7
      });
      setPatternResults(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to analyze patterns");
    } finally {
      setAnalyzingPatterns(false);
    }
  };

  const handleAnalyzeCorrelations = async () => {
    if (!correlationForm.device1 || !correlationForm.device2 || !correlationForm.field1 || !correlationForm.field2) {
      setError("Please select both devices and fields");
      return;
    }
    
    try {
      setAnalyzingCorrelations(true);
      setError(null);
      const resp = await api.post("/analytics/analyze-correlations", {
        device_ids: [correlationForm.device1, correlationForm.device2],
        field_keys: [correlationForm.field1, correlationForm.field2],
        days: 7
      });
      setCorrelationResults(resp.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to analyze correlations");
    } finally {
      setAnalyzingCorrelations(false);
    }
  };

  const handleTrainModel = async (e) => {
    e.preventDefault();
    if (trainForm.device_ids.length === 0) {
      setError("Please select at least one device");
      return;
    }
    
    try {
      setTrainingModel(true);
      setError(null);
      await api.post("/analytics/train-model", trainForm);
      setShowTrainModal(false);
      setTrainForm({ name: "", model_type: "anomaly_detection", algorithm: "isolation_forest", device_ids: [], days: 30 });
      await loadData();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to train model");
    } finally {
      setTrainingModel(false);
    }
  };

  const tabs = [
    { id: "insights", label: "Insights" },
    { id: "patterns", label: "Pattern Analysis" },
    { id: "correlations", label: "Correlations" },
    { id: "ml", label: "ML Models" },
  ];

  if (loading && devices.length === 0) {
    return (
      <div className="page">
        <div className="card">
          <p>Loading analytics data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Analytics", path: "/analytics" }]} />
      
      <div className="page-header">
        <h1>Analytics Engine</h1>
        <p className="text-muted">Real-time insights, pattern analysis, and predictive maintenance</p>
      </div>

      {error && (
        <div className="card card--error">
          <p className="text-error">{error}</p>
        </div>
      )}

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Insights Tab - Shows automatic predictions */}
      {activeTab === "insights" && (
        <div className="card">
          <h2>Predictive Maintenance Insights</h2>
          <p className="text-muted">ML model predictions (automatically generated in backend)</p>
          
          {predictions.length === 0 ? (
            <p className="text-muted">No predictions yet. Train an ML model to generate predictions.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Prediction Type</th>
                  <th>Value</th>
                  <th>Confidence</th>
                  <th>Predicted At</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((pred) => (
                  <tr key={pred.device_id + pred.predicted_at}>
                    <td>{pred.device_name}</td>
                    <td>{pred.prediction_type}</td>
                    <td>
                      {pred.prediction_type === "failure_probability"
                        ? `${(pred.predicted_value * 100).toFixed(1)}%`
                        : pred.predicted_value?.toFixed(2)}
                    </td>
                    <td>{pred.confidence ? `${(pred.confidence * 100).toFixed(0)}%` : "N/A"}</td>
                    <td>{new Date(pred.predicted_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Pattern Analysis Tab */}
      {activeTab === "patterns" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h2>Usage Pattern Analysis</h2>
            <button
              className="btn btn-primary"
              onClick={handleAnalyzePatterns}
              disabled={analyzingPatterns || devices.length === 0}
            >
              {analyzingPatterns ? "Analyzing..." : "Analyze Patterns"}
            </button>
          </div>
          <p className="text-muted">Analyze occupancy, traffic, and energy consumption patterns</p>
          
          {patternResults.length === 0 ? (
            <p className="text-muted">Click "Analyze Patterns" to analyze your devices.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Analysis Type</th>
                  <th>Peak Hour</th>
                  <th>Trend</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {patternResults.map((result, idx) => (
                  <tr key={idx}>
                    <td>{result.device_name}</td>
                    <td>{result.analysis_type}</td>
                    <td>{result.peak_times?.hour !== null ? `Hour ${result.peak_times.hour}` : "N/A"}</td>
                    <td>
                      <span className={`badge ${
                        result.trends?.overall === "increasing" ? "badge--warning" :
                        result.trends?.overall === "decreasing" ? "badge--info" :
                        "badge--secondary"
                      }`}>
                        {result.trends?.overall || "N/A"}
                      </span>
                    </td>
                    <td><small>{result.summary}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Correlations Tab */}
      {activeTab === "correlations" && (
        <div className="card">
          <h2>Multi-Sensor Correlation Analysis</h2>
          <p className="text-muted">Find relationships between different devices/sensors</p>
          
          <div className="form-group" style={{ marginBottom: "16px" }}>
            <label>Device 1</label>
            <select
              className="form-control"
              value={correlationForm.device1}
              onChange={(e) => setCorrelationForm({ ...correlationForm, device1: e.target.value })}
            >
              <option value="">Select device...</option>
              {devices.map(d => <option key={d.device_id} value={d.device_id}>{d.name}</option>)}
            </select>
          </div>
          
          <div className="form-group" style={{ marginBottom: "16px" }}>
            <label>Field 1 (from Device 1)</label>
            <input
              type="text"
              className="form-control"
              value={correlationForm.field1}
              onChange={(e) => setCorrelationForm({ ...correlationForm, field1: e.target.value })}
              placeholder="e.g., temperature, battery.soc"
            />
          </div>
          
          <div className="form-group" style={{ marginBottom: "16px" }}>
            <label>Device 2</label>
            <select
              className="form-control"
              value={correlationForm.device2}
              onChange={(e) => setCorrelationForm({ ...correlationForm, device2: e.target.value })}
            >
              <option value="">Select device...</option>
              {devices.filter(d => d.device_id !== correlationForm.device1).map(d => (
                <option key={d.device_id} value={d.device_id}>{d.name}</option>
              ))}
            </select>
          </div>
          
          <div className="form-group" style={{ marginBottom: "16px" }}>
            <label>Field 2 (from Device 2)</label>
            <input
              type="text"
              className="form-control"
              value={correlationForm.field2}
              onChange={(e) => setCorrelationForm({ ...correlationForm, field2: e.target.value })}
              placeholder="e.g., temperature, battery.soc"
            />
          </div>
          
          <button
            className="btn btn-primary"
            onClick={handleAnalyzeCorrelations}
            disabled={analyzingCorrelations}
          >
            {analyzingCorrelations ? "Analyzing..." : "Analyze Correlation"}
          </button>
          
          {correlationResults.length > 0 && (
            <div style={{ marginTop: "24px" }}>
              <h3>Results</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Device 1</th>
                    <th>Device 2</th>
                    <th>Correlation</th>
                    <th>Type</th>
                    <th>Insights</th>
                  </tr>
                </thead>
                <tbody>
                  {correlationResults.map((result, idx) => (
                    <tr key={idx}>
                      <td>{result.device1_id}</td>
                      <td>{result.device2_id}</td>
                      <td><strong>{result.correlation_coefficient.toFixed(3)}</strong></td>
                      <td>
                        <span className={`badge ${
                          result.correlation_type === "positive" ? "badge--success" :
                          result.correlation_type === "negative" ? "badge--error" :
                          "badge--secondary"
                        }`}>
                          {result.correlation_type}
                        </span>
                      </td>
                      <td><small>{result.insights}</small></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ML Models Tab */}
      {activeTab === "ml" && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h2>Machine Learning Models</h2>
            <button className="btn btn-primary" onClick={() => setShowTrainModal(true)}>
              Train New Model
            </button>
          </div>
          <p className="text-muted">ML models are trained in the backend. Once trained, they automatically generate predictions.</p>
          
          {models.length === 0 ? (
            <p className="text-muted">No ML models yet. Train a model to get started.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Model Name</th>
                  <th>Type</th>
                  <th>Algorithm</th>
                  <th>Accuracy</th>
                  <th>Status</th>
                  <th>Trained</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <tr key={model.id}>
                    <td>{model.name}</td>
                    <td>{model.model_type}</td>
                    <td>{model.algorithm}</td>
                    <td>
                      {model.training_accuracy !== null
                        ? `${(model.training_accuracy * 100).toFixed(1)}%`
                        : "N/A"}
                    </td>
                    <td>
                      <span className={model.is_trained ? "badge badge--success" : "badge badge--secondary"}>
                        {model.is_trained ? "Trained" : "Not Trained"}
                      </span>
                    </td>
                    <td>
                      {model.trained_at
                        ? new Date(model.trained_at).toLocaleDateString()
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Train Model Modal */}
      <Modal
        isOpen={showTrainModal}
        onClose={() => setShowTrainModal(false)}
        title="Train ML Model (Backend Only)"
      >
        <form onSubmit={handleTrainModel}>
          <div className="form-group">
            <label>Model Name</label>
            <input
              type="text"
              className="form-control"
              value={trainForm.name}
              onChange={(e) => setTrainForm({ ...trainForm, name: e.target.value })}
              required
              placeholder="e.g., Smart Bench Anomaly Detection"
            />
          </div>

          <div className="form-group">
            <label>Model Type</label>
            <select
              className="form-control"
              value={trainForm.model_type}
              onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}
            >
              <option value="anomaly_detection">Anomaly Detection</option>
              <option value="failure_prediction">Failure Prediction</option>
            </select>
          </div>

          <div className="form-group">
            <label>Algorithm</label>
            <select
              className="form-control"
              value={trainForm.algorithm}
              onChange={(e) => setTrainForm({ ...trainForm, algorithm: e.target.value })}
            >
              <option value="isolation_forest">Isolation Forest</option>
              <option value="random_forest">Random Forest</option>
            </select>
          </div>

          <div className="form-group">
            <label>Select Devices</label>
            <div style={{ maxHeight: "200px", overflowY: "auto", border: "1px solid #ddd", padding: "8px" }}>
              {devices.map((device) => (
                <label key={device.id} style={{ display: "block", marginBottom: "8px" }}>
                  <input
                    type="checkbox"
                    checked={trainForm.device_ids.includes(device.device_id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setTrainForm({
                          ...trainForm,
                          device_ids: [...trainForm.device_ids, device.device_id],
                        });
                      } else {
                        setTrainForm({
                          ...trainForm,
                          device_ids: trainForm.device_ids.filter(id => id !== device.device_id),
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
            <label>Training Data Range (days)</label>
            <input
              type="number"
              className="form-control"
              value={trainForm.days}
              onChange={(e) => setTrainForm({ ...trainForm, days: parseInt(e.target.value) || 30 })}
              min="7"
              max="365"
            />
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={() => setShowTrainModal(false)}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={trainingModel || !trainForm.name || trainForm.device_ids.length === 0}>
              {trainingModel ? "Training..." : "Train Model (Backend)"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
