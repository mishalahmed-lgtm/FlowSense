import { useEffect, useState } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Modal from "../components/Modal.jsx";
import Icon from "../components/Icon.jsx";
import BackButton from "../components/BackButton.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";

export default function AnalyticsPage() {
  const { token, isTenantAdmin, hasModule } = useAuth();
  const api = createApiClient(token);
  
  const [activeTab, setActiveTab] = useState("overview");
  const [devices, setDevices] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [patternResults, setPatternResults] = useState([]);
  const [analyzingPatterns, setAnalyzingPatterns] = useState(false);
  const [expandedDevices, setExpandedDevices] = useState(new Set());
  
  const [correlationResults, setCorrelationResults] = useState([]);
  const [analyzingCorrelations, setAnalyzingCorrelations] = useState(false);
  const [correlationForm, setCorrelationForm] = useState({
    device1: "",
    device2: "",
    field1: "",
    field2: ""
  });
  
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [trainingModel, setTrainingModel] = useState(false);
  const [trainForm, setTrainForm] = useState({
    name: "",
    model_type: "anomaly_detection",
    algorithm: "isolation_forest",
    device_ids: [],
    days: 30
  });

  if (!isTenantAdmin || !hasModule("analytics")) {
    return (
      <div className="page page--centered">
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

  const activeDevices = devices.filter(d => d.is_active).length;
  const anomaliesCount = predictions.filter(p => p.prediction_type === "anomaly").length;
  const highRiskCount = predictions.filter(p => p.prediction_type === "failure_probability" && p.predicted_value > 0.7).length;

  if (loading && devices.length === 0) {
    return (
      <div className="page page--centered">
        <div className="card">
          <p style={{ color: "var(--color-text-secondary)" }}>Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <Breadcrumbs items={[{ label: "Analytics", path: "/analytics" }]} />
      
      {/* Header */}
      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Analytics</h1>
          <p className="page-header__subtitle">
            Video analytics configurations, counters, and insights
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn-icon" onClick={loadData} title="Refresh">
            <Icon name="refresh" size={18} />
          </button>
        </div>
      </div>

      {/* Overview Metrics */}
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--primary">
              <Icon name="settings" size={24} />
            </div>
          </div>
          <div className="metric-card__label">Active Configs</div>
          <div className="metric-card__value">{devices.length}</div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--success">
              <Icon name="check" size={24} />
            </div>
          </div>
          <div className="metric-card__label">Working</div>
          <div className="metric-card__value">{activeDevices}</div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--warning">
              <Icon name="users" size={24} />
            </div>
          </div>
          <div className="metric-card__label">Anomalies Detected</div>
          <div className="metric-card__value">{anomaliesCount > 0 ? anomaliesCount : "N/A"}</div>
        </div>

        <div className="metric-card">
          <div className="metric-card__header">
            <div className="metric-card__icon metric-card__icon--error">
              <Icon name="car" size={24} />
            </div>
          </div>
          <div className="metric-card__label">High Risk Devices</div>
          <div className="metric-card__value">{highRiskCount > 0 ? highRiskCount : "N/A"}</div>
        </div>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        {["overview", "patterns", "correlations", "models"].map(tab => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? "tab--active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="grid grid--2">
          {/* Detection Trends Card */}
          <div className="card" style={{ 
            background: "linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%)",
            border: "1px solid var(--color-border-light)"
          }}>
            <div className="card__header">
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <div style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "rgba(59, 130, 246, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <Icon name="trending" size={20} style={{ color: "var(--color-primary-400)" }} />
                </div>
                <h3 className="card__title">Detection Trends</h3>
              </div>
            </div>
            <div className="card__body">
              <div style={{ 
                height: "200px", 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center",
                color: "var(--color-text-tertiary)"
              }}>
                <div style={{ textAlign: "center" }}>
                  <div style={{ marginBottom: "var(--space-4)", opacity: 0.2 }}>
                    <Icon name="activity" size={48} />
                  </div>
                  <p style={{ fontSize: "var(--font-size-sm)" }}>No data available</p>
                </div>
              </div>
            </div>
          </div>

          {/* Activity Card */}
          <div className="card" style={{ 
            background: "linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%)",
            border: "1px solid var(--color-border-light)"
          }}>
            <div className="card__header">
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <div style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "rgba(16, 185, 129, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <Icon name="activity" size={20} style={{ color: "var(--color-success-text)" }} />
                </div>
                <h3 className="card__title">Motion Activity</h3>
              </div>
            </div>
            <div className="card__body">
              <div style={{ 
                height: "200px", 
                display: "flex", 
                alignItems: "center", 
                justifyContent: "center",
                color: "var(--color-text-tertiary)"
              }}>
                <div style={{ textAlign: "center" }}>
                  <div style={{ marginBottom: "var(--space-4)", opacity: 0.2 }}>
                    <Icon name="activity" size={48} />
                  </div>
                  <p style={{ fontSize: "var(--font-size-sm)" }}>No data available</p>
                </div>
              </div>
            </div>
          </div>

          {/* Predictions Table */}
          <div className="card" style={{ 
            gridColumn: "1 / -1",
            background: "linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, transparent 100%)",
            border: "1px solid var(--color-border-light)"
          }}>
            <div className="card__header">
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <div style={{
                  width: "40px",
                  height: "40px",
                  borderRadius: "var(--radius-md)",
                  backgroundColor: "rgba(139, 92, 246, 0.15)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}>
                  <Icon name="trending" size={20} style={{ color: "var(--color-info-text)" }} />
                </div>
                <div>
                <h3 className="card__title">Predictive Insights</h3>
                  <p style={{ 
                    fontSize: "var(--font-size-xs)",
                    color: "var(--color-text-tertiary)",
                    margin: 0,
                    marginTop: "var(--space-1)"
                  }}>
                    ML-powered predictions and forecasts
                  </p>
                </div>
              </div>
            </div>
            {predictions.length === 0 ? (
              <div style={{ 
                padding: "var(--space-12)", 
                textAlign: "center", 
                color: "var(--color-text-tertiary)" 
              }}>
                <div style={{ marginBottom: "var(--space-4)", opacity: 0.2 }}>
                  <Icon name="cpu" size={64} />
                </div>
                <h4 style={{ 
                  fontSize: "var(--font-size-base)",
                  fontWeight: "var(--font-weight-semibold)",
                  color: "var(--color-text-primary)",
                  marginBottom: "var(--space-2)"
                }}>
                  No predictions yet
                </h4>
                <p style={{ fontSize: "var(--font-size-sm)" }}>
                  Train an ML model to generate predictions and insights
                </p>
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Device</th>
                      <th>Type</th>
                      <th>Value</th>
                      <th>Confidence</th>
                      <th>Predicted At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions.slice(0, 10).map((pred, idx) => (
                      <tr key={idx} style={{ transition: "background-color 0.2s ease" }}>
                        <td style={{ fontWeight: "var(--font-weight-medium)" }}>
                          {pred.device_name || pred.device_id}
                        </td>
                        <td>
                          <span className="badge badge--info">
                            {pred.prediction_type}
                          </span>
                        </td>
                        <td style={{ 
                          fontWeight: "var(--font-weight-semibold)",
                          color: pred.prediction_type === "failure_probability" && pred.predicted_value > 0.7 
                            ? "var(--color-error-text)" 
                            : "var(--color-text-primary)"
                        }}>
                          {pred.prediction_type === "failure_probability"
                            ? `${(pred.predicted_value * 100).toFixed(1)}%`
                            : pred.predicted_value?.toFixed(2)}
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                            <div style={{ 
                              width: "60px", 
                              height: "8px", 
                              backgroundColor: "var(--color-bg-secondary)", 
                              borderRadius: "var(--radius-full)", 
                              overflow: "hidden" 
                            }}>
                              <div style={{ 
                                width: `${(pred.confidence || 0) * 100}%`, 
                                height: "100%", 
                                backgroundColor: pred.confidence > 0.7 ? "var(--color-success-bright)" : "var(--color-warning-bright)",
                                transition: "width 0.3s ease"
                              }}></div>
                            </div>
                            <span style={{ 
                              fontSize: "var(--font-size-xs)",
                              fontWeight: "var(--font-weight-medium)",
                              minWidth: "40px"
                            }}>
                              {pred.confidence ? `${(pred.confidence * 100).toFixed(0)}%` : "—"}
                            </span>
                          </div>
                        </td>
                        <td style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-tertiary)" }}>
                          {new Date(pred.predicted_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Pattern Analysis Tab */}
      {activeTab === "patterns" && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ 
            padding: "var(--space-6)",
            background: "linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%)",
            borderBottom: "1px solid var(--color-border-light)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "var(--space-4)" }}>
            <div>
                <h2 style={{ 
                  fontSize: "var(--font-size-2xl)", 
                  fontWeight: "var(--font-weight-bold)",
                  color: "var(--color-text-primary)",
                  marginBottom: "var(--space-2)"
                }}>
                  Usage Pattern Analysis
                </h2>
                <p style={{ 
                  color: "var(--color-text-secondary)",
                  fontSize: "var(--font-size-sm)",
                  margin: 0
                }}>
                  Analyze occupancy, traffic, and energy consumption patterns across your devices
                </p>
            </div>
            <button
              className="btn btn--primary"
              onClick={handleAnalyzePatterns}
              disabled={analyzingPatterns || devices.length === 0}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-3) var(--space-5)",
                  fontSize: "var(--font-size-base)",
                  fontWeight: "var(--font-weight-semibold)"
                }}
              >
                {analyzingPatterns ? (
                  <>
                    <Icon name="activity" size={18} />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Icon name="trending" size={18} />
                    <span>Run Analysis</span>
                  </>
                )}
            </button>
            </div>
          </div>
          
          {patternResults.length === 0 ? (
            <div style={{ 
              padding: "var(--space-16)", 
              textAlign: "center", 
              color: "var(--color-text-tertiary)" 
            }}>
              <div style={{ 
                marginBottom: "var(--space-6)", 
                opacity: 0.2,
                display: "inline-block"
              }}>
                <Icon name="trending" size={80} />
              </div>
              <h3 style={{ 
                fontSize: "var(--font-size-lg)",
                fontWeight: "var(--font-weight-semibold)",
                color: "var(--color-text-primary)",
                marginBottom: "var(--space-2)"
              }}>
                Ready to Analyze Patterns
              </h3>
              <p style={{ 
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-secondary)",
                marginBottom: "var(--space-6)"
              }}>
                Click "Run Analysis" to discover usage patterns and trends across your devices
              </p>
            </div>
          ) : (
            <div style={{ padding: "var(--space-6)", display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              {patternResults.map((result, idx) => {
                const deviceKey = result.device_id || idx;
                const isExpanded = expandedDevices.has(deviceKey);
                
                const formatHour = (hour) => {
                  if (hour === null || hour === undefined) return "N/A";
                  const period = hour >= 12 ? "PM" : "AM";
                  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
                  return `${displayHour}:00 ${period}`;
                };

                const formatDay = (day) => {
                  if (day === null || day === undefined) return null;
                  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
                  return days[day] || `Day ${day}`;
                };

                const peakHour = result.peak_times?.hour;
                const peakDay = result.peak_times?.day;
                const trend = result.trends?.overall || "stable";
                const trendIcon = trend === "increasing" ? "↑" : trend === "decreasing" ? "↓" : "→";
                const trendColor = trend === "increasing" ? "var(--color-success-text)" : trend === "decreasing" ? "var(--color-warning-text)" : "var(--color-text-secondary)";

                return (
                  <div 
                    key={idx} 
                    style={{ 
                      border: "1px solid var(--color-border-medium)",
                      borderRadius: "var(--radius-lg)",
                      backgroundColor: "var(--color-bg-primary)",
                      overflow: "hidden",
                      transition: "all 0.3s ease",
                      boxShadow: isExpanded ? "var(--shadow-lg)" : "var(--shadow-sm)"
                    }}
                  >
                    {/* Collapsible Header */}
                    <button
                      onClick={() => {
                        const newExpanded = new Set(expandedDevices);
                        if (isExpanded) {
                          newExpanded.delete(deviceKey);
                        } else {
                          newExpanded.add(deviceKey);
                        }
                        setExpandedDevices(newExpanded);
                      }}
                      style={{
                        width: "100%",
                        padding: "var(--space-5)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background-color 0.2s ease"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = "transparent";
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flex: 1 }}>
                        <div style={{
                          width: "48px",
                          height: "48px",
                          borderRadius: "var(--radius-md)",
                          backgroundColor: trend === "increasing" ? "rgba(16, 185, 129, 0.15)" : trend === "decreasing" ? "rgba(245, 158, 11, 0.15)" : "rgba(59, 130, 246, 0.15)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: "var(--font-size-xl)",
                          color: trendColor,
                          fontWeight: "var(--font-weight-bold)"
                        }}>
                          {trendIcon}
                        </div>
                        <div style={{ flex: 1 }}>
                          <h3 style={{ 
                            fontSize: "var(--font-size-lg)", 
                            fontWeight: "var(--font-weight-semibold)",
                            color: "var(--color-text-primary)",
                            marginBottom: "var(--space-1)"
                          }}>
                            {result.device_name || result.device_id}
                          </h3>
                          <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                            <span className="badge badge--info" style={{ fontSize: "var(--font-size-xs)" }}>
                              {result.analysis_type || "Pattern Analysis"}
                        </span>
                            <span style={{ 
                              fontSize: "var(--font-size-xs)",
                              color: "var(--color-text-tertiary)"
                            }}>
                              {peakHour !== null && peakHour !== undefined && `Peak: ${formatHour(peakHour)}`}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div style={{ 
                        display: "flex", 
                        alignItems: "center", 
                        gap: "var(--space-2)",
                        color: "var(--color-text-secondary)"
                      }}>
                        <span style={{ 
                          fontSize: "var(--font-size-sm)",
                          color: trendColor,
                          fontWeight: "var(--font-weight-semibold)",
                          textTransform: "capitalize"
                        }}>
                          {trend}
                        </span>
                        <div style={{
                          width: "24px",
                          height: "24px",
                          borderRadius: "var(--radius-sm)",
                          backgroundColor: isExpanded ? "var(--color-primary-600)" : "var(--color-bg-secondary)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          transition: "all 0.2s ease"
                        }}>
                          <Icon 
                            name={isExpanded ? "chevron-up" : "chevron-down"} 
                            size={16} 
                          />
                        </div>
                      </div>
                    </button>

                    {/* Collapsible Content */}
                    {isExpanded && (
                      <div style={{ 
                        padding: "0 var(--space-5) var(--space-5)",
                        borderTop: "1px solid var(--color-border-light)",
                        animation: "slideDown 0.3s ease"
                      }}>
                        <div style={{ 
                          display: "grid", 
                          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                          gap: "var(--space-4)",
                          marginTop: "var(--space-4)",
                          marginBottom: "var(--space-4)"
                        }}>
                          {peakHour !== null && peakHour !== undefined && (
                            <div style={{ 
                              padding: "var(--space-4)",
                              backgroundColor: "var(--color-bg-secondary)",
                              borderRadius: "var(--radius-lg)",
                              border: "1px solid var(--color-border-light)"
                            }}>
                              <div style={{ 
                                fontSize: "var(--font-size-xs)", 
                                color: "var(--color-text-tertiary)",
                                marginBottom: "var(--space-2)",
                                textTransform: "uppercase",
                                letterSpacing: "0.5px",
                                fontWeight: "var(--font-weight-medium)"
                              }}>
                                Peak Usage Time
                              </div>
                              <div style={{ 
                                fontSize: "var(--font-size-2xl)", 
                                fontWeight: "var(--font-weight-bold)",
                                color: "var(--color-primary-400)",
                                marginBottom: "var(--space-1)"
                              }}>
                                {formatHour(peakHour)}
                              </div>
                              {peakDay !== null && peakDay !== undefined && (
                                <div style={{ 
                                  fontSize: "var(--font-size-sm)", 
                                  color: "var(--color-text-secondary)"
                                }}>
                                  {formatDay(peakDay)}
                                </div>
                              )}
                            </div>
                          )}

                          <div style={{ 
                            padding: "var(--space-4)",
                            backgroundColor: "var(--color-bg-secondary)",
                            borderRadius: "var(--radius-lg)",
                            border: "1px solid var(--color-border-light)"
                          }}>
                            <div style={{ 
                              fontSize: "var(--font-size-xs)", 
                              color: "var(--color-text-tertiary)",
                              marginBottom: "var(--space-2)",
                              textTransform: "uppercase",
                              letterSpacing: "0.5px",
                              fontWeight: "var(--font-weight-medium)"
                            }}>
                              Trend Direction
                            </div>
                            <div style={{ 
                              fontSize: "var(--font-size-2xl)", 
                              fontWeight: "var(--font-weight-bold)",
                              color: trendColor,
                              textTransform: "capitalize"
                            }}>
                              {trend}
                            </div>
                            <div style={{ 
                              fontSize: "var(--font-size-xs)",
                              color: "var(--color-text-secondary)",
                              marginTop: "var(--space-1)"
                            }}>
                              {trend === "increasing" ? "Growing usage" : trend === "decreasing" ? "Declining usage" : "Stable pattern"}
                            </div>
                          </div>
                        </div>

                        {result.insights && (
                          <div style={{ 
                            padding: "var(--space-5)",
                            backgroundColor: "var(--color-bg-secondary)",
                            borderRadius: "var(--radius-lg)",
                            border: "1px solid var(--color-border-light)",
                            marginTop: "var(--space-4)"
                          }}>
                            <div style={{ 
                              display: "flex",
                              alignItems: "center",
                              gap: "var(--space-2)",
                              marginBottom: "var(--space-4)"
                            }}>
                              <Icon name="activity" size={20} style={{ color: "var(--color-primary-400)" }} />
                              <h4 style={{ 
                                fontSize: "var(--font-size-base)", 
                                fontWeight: "var(--font-weight-semibold)",
                                color: "var(--color-text-primary)",
                                margin: 0
                              }}>
                                Key Insights
                              </h4>
                            </div>
                            <div style={{ 
                              fontSize: "var(--font-size-sm)", 
                              color: "var(--color-text-secondary)",
                              lineHeight: "var(--line-height-relaxed)",
                              display: "flex",
                              flexDirection: "column",
                              gap: "var(--space-3)"
                            }}>
                              {result.insights.trend && (
                                <div style={{ 
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "var(--space-2)"
                                }}>
                                  <span style={{ color: trendColor, fontSize: "var(--font-size-lg)" }}>•</span>
                                  <div>
                                    Overall trend is <strong style={{ color: trendColor }}>{trend}</strong> over the analysis period
                                  </div>
                                </div>
                              )}
                              {peakHour !== null && peakHour !== undefined && (
                                <div style={{ 
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "var(--space-2)"
                                }}>
                                  <span style={{ color: "var(--color-primary-400)", fontSize: "var(--font-size-lg)" }}>•</span>
                                  <div>
                                    Highest activity occurs at <strong style={{ color: "var(--color-text-primary)" }}>{formatHour(peakHour)}</strong>
                                  </div>
                                </div>
                              )}
                              {result.summary && !result.summary.includes("Hour") && (
                                <div style={{ 
                                  display: "flex",
                                  alignItems: "flex-start",
                                  gap: "var(--space-2)"
                                }}>
                                  <span style={{ color: "var(--color-info-text)", fontSize: "var(--font-size-lg)" }}>•</span>
                                  <div>{result.summary}</div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Correlations Tab */}
      {activeTab === "correlations" && (
        <div className="card">
          <div className="card__header">
            <div>
              <h2 className="card__title">Multi-Sensor Correlation</h2>
              <p className="card__subtitle">Find relationships between different devices and sensors</p>
            </div>
          </div>
          
          <div className="form" style={{ maxWidth: "600px" }}>
            <div className="form-group">
              <label className="form-label">Device 1</label>
              <select
                className="form-select"
                value={correlationForm.device1}
                onChange={(e) => setCorrelationForm({ ...correlationForm, device1: e.target.value })}
              >
                <option value="">Select device...</option>
                {devices.map(d => <option key={d.device_id} value={d.device_id}>{d.name || d.device_id}</option>)}
              </select>
            </div>
            
            <div className="form-group">
              <label className="form-label">Field 1</label>
              <input
                type="text"
                className="form-input"
                value={correlationForm.field1}
                onChange={(e) => setCorrelationForm({ ...correlationForm, field1: e.target.value })}
                placeholder="e.g., temperature, battery.soc"
              />
            </div>
            
            <div className="form-group">
              <label className="form-label">Device 2</label>
              <select
                className="form-select"
                value={correlationForm.device2}
                onChange={(e) => setCorrelationForm({ ...correlationForm, device2: e.target.value })}
              >
                <option value="">Select device...</option>
                {devices.filter(d => d.device_id !== correlationForm.device1).map(d => (
                  <option key={d.device_id} value={d.device_id}>{d.name || d.device_id}</option>
                ))}
              </select>
            </div>
            
            <div className="form-group">
              <label className="form-label">Field 2</label>
              <input
                type="text"
                className="form-input"
                value={correlationForm.field2}
                onChange={(e) => setCorrelationForm({ ...correlationForm, field2: e.target.value })}
                placeholder="e.g., temperature, battery.soc"
              />
            </div>
            
            <button
              className="btn btn--primary"
              onClick={handleAnalyzeCorrelations}
              disabled={analyzingCorrelations}
            >
              {analyzingCorrelations ? "Analyzing..." : "Analyze Correlation"}
            </button>
          </div>
          
          {correlationResults.length > 0 && (
            <div style={{ marginTop: "var(--space-8)" }}>
              <h3 style={{ marginBottom: "var(--space-4)", fontSize: "var(--font-size-lg)" }}>Results</h3>
              <div className="table-wrapper">
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
                        <td style={{ fontFamily: "var(--font-family-mono)", fontSize: "var(--font-size-xs)" }}>
                          {result.device1_id}
                        </td>
                        <td style={{ fontFamily: "var(--font-family-mono)", fontSize: "var(--font-size-xs)" }}>
                          {result.device2_id}
                        </td>
                        <td>
                          <strong style={{ color: "var(--color-primary-400)" }}>
                            {result.correlation_coefficient.toFixed(3)}
                          </strong>
                        </td>
                        <td>
                          <span className={`badge ${
                            result.correlation_type === "positive" ? "badge--success" :
                            result.correlation_type === "negative" ? "badge--error" :
                            "badge--neutral"
                          }`}>
                            {result.correlation_type}
                          </span>
                        </td>
                        <td style={{ fontSize: "var(--font-size-xs)", color: "var(--color-text-secondary)" }}>
                          {result.insights}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ML Models Tab */}
      {activeTab === "models" && (
        <div>
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div className="card__header">
              <div>
                <h2 className="card__title">Machine Learning Models</h2>
                <p className="card__subtitle">Train and deploy ML models for anomaly detection and predictive maintenance</p>
              </div>
              <button className="btn btn--primary" onClick={() => setShowTrainModal(true)}>
                Train New Model
              </button>
            </div>
          </div>

          {models.length === 0 ? (
            <div className="card" style={{ textAlign: "center", padding: "var(--space-12)" }}>
              <div style={{ marginBottom: "var(--space-4)", opacity: 0.3 }}>
                <Icon name="cpu" size={64} />
              </div>
              <h3 style={{ marginBottom: "var(--space-2)", color: "var(--color-text-secondary)" }}>
                No ML models yet
              </h3>
              <p style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-6)" }}>
                Train your first model to enable predictive analytics
              </p>
              <button className="btn btn--primary" onClick={() => setShowTrainModal(true)}>
                Train First Model
              </button>
            </div>
          ) : (
            <div className="grid grid--auto-fit">
              {models.map((model) => (
                <div key={model.id} className="card">
                  <div style={{ marginBottom: "var(--space-4)" }}>
                    <span className={`badge ${model.is_trained ? "badge--success" : "badge--neutral"}`}>
                      <span className="badge__dot"></span>
                      {model.is_trained ? "Trained" : "Not Trained"}
                    </span>
                  </div>
                  
                  <h3 className="card__title" style={{ marginBottom: "var(--space-3)" }}>
                    {model.name}
                  </h3>
                  
                  <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--color-text-tertiary)" }}>Type:</span>
                      <span className="badge badge--info">{model.model_type}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--color-text-tertiary)" }}>Algorithm:</span>
                      <span>{model.algorithm}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "var(--color-text-tertiary)" }}>Accuracy:</span>
                      <span style={{ color: "var(--color-success-bright)" }}>
                        {model.training_accuracy !== null ? `${(model.training_accuracy * 100).toFixed(1)}%` : "N/A"}
                      </span>
                    </div>
                    {model.trained_at && (
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--color-text-tertiary)" }}>Trained:</span>
                        <span style={{ fontSize: "var(--font-size-xs)" }}>
                          {new Date(model.trained_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Train Model Modal */}
      {showTrainModal && (
        <Modal title="Train ML Model" onClose={() => setShowTrainModal(false)}>
          <form onSubmit={handleTrainModel} className="form">
            <div className="form-group">
              <label className="form-label form-label--required">Model Name</label>
              <input
                type="text"
                className="form-input"
                value={trainForm.name}
                onChange={(e) => setTrainForm({ ...trainForm, name: e.target.value })}
                required
                placeholder="e.g., Smart Bench Anomaly Detection"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Model Type</label>
              <select
                className="form-select"
                value={trainForm.model_type}
                onChange={(e) => setTrainForm({ ...trainForm, model_type: e.target.value })}
              >
                <option value="anomaly_detection">Anomaly Detection</option>
                <option value="failure_prediction">Failure Prediction</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Algorithm</label>
              <select
                className="form-select"
                value={trainForm.algorithm}
                onChange={(e) => setTrainForm({ ...trainForm, algorithm: e.target.value })}
              >
                <option value="isolation_forest">Isolation Forest</option>
                <option value="random_forest">Random Forest</option>
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
              <label className="form-label">Training Data Range (days)</label>
              <input
                type="number"
                className="form-input"
                value={trainForm.days}
                onChange={(e) => setTrainForm({ ...trainForm, days: parseInt(e.target.value) || 30 })}
                min="7"
                max="365"
              />
            </div>

            <div className="modal__footer">
              <button type="button" className="btn btn--secondary" onClick={() => setShowTrainModal(false)}>
                Cancel
              </button>
              <button 
                type="submit" 
                className="btn btn--primary" 
                disabled={trainingModel || !trainForm.name || trainForm.device_ids.length === 0}
              >
                {trainingModel ? "Training..." : "Train Model"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
