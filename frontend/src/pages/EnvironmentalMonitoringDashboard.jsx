import { useEffect, useState, useMemo } from "react";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from "recharts";

// AQI calculation function
function calculateAQI(pm25, pm10, co2) {
  // Simplified AQI calculation (0-500 scale)
  // In production, use official AQI formulas
  let aqi = 0;
  
  if (pm25) {
    // PM2.5 AQI (simplified)
    if (pm25 <= 12) aqi = Math.max(aqi, (pm25 / 12) * 50);
    else if (pm25 <= 35.4) aqi = Math.max(aqi, 50 + ((pm25 - 12) / 23.4) * 50);
    else if (pm25 <= 55.4) aqi = Math.max(aqi, 100 + ((pm25 - 35.4) / 20) * 50);
    else if (pm25 <= 150.4) aqi = Math.max(aqi, 150 + ((pm25 - 55.4) / 95) * 100);
    else aqi = Math.max(aqi, 250 + ((pm25 - 150.4) / 99.6) * 150);
  }
  
  if (pm10) {
    // PM10 AQI (simplified)
    if (pm10 <= 54) aqi = Math.max(aqi, (pm10 / 54) * 50);
    else if (pm10 <= 154) aqi = Math.max(aqi, 50 + ((pm10 - 54) / 100) * 50);
    else if (pm10 <= 254) aqi = Math.max(aqi, 100 + ((pm10 - 154) / 100) * 50);
    else if (pm10 <= 354) aqi = Math.max(aqi, 150 + ((pm10 - 254) / 100) * 100);
    else aqi = Math.max(aqi, 250 + ((pm10 - 354) / 146) * 150);
  }
  
  return Math.min(500, Math.round(aqi));
}

function getAQICategory(aqi) {
  if (aqi <= 50) return { label: "Good", color: "#10b981", level: "good" };
  if (aqi <= 100) return { label: "Moderate", color: "#facc15", level: "moderate" };
  if (aqi <= 150) return { label: "Unhealthy for Sensitive", color: "#f97316", level: "unhealthy_sensitive" };
  if (aqi <= 200) return { label: "Unhealthy", color: "#ef4444", level: "unhealthy" };
  if (aqi <= 300) return { label: "Very Unhealthy", color: "#991b1b", level: "very_unhealthy" };
  return { label: "Hazardous", color: "#7c2d12", level: "hazardous" };
}

export default function EnvironmentalMonitoringDashboard() {
  const { token, isTenantAdmin } = useAuth();
  const api = useMemo(() => createApiClient(token), [token]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [timeRange, setTimeRange] = useState("24h");
  const [envData, setEnvData] = useState({
    airQuality: {
      pm25: null,
      pm10: null,
      co2: null,
      aqi: null,
    },
    weather: {
      temperature: null,
      humidity: null,
    },
    noise: {
      level: null,
      peak: null,
    },
    trends: {
      pm25: [],
      pm10: [],
      temperature: [],
      humidity: [],
      noise: [],
    },
    sensorStatus: [],
  });

  useEffect(() => {
    if (!token) return;
    loadEnvironmentalData();
    const interval = setInterval(loadEnvironmentalData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [token, timeRange]);

  const loadEnvironmentalData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Get all devices for the tenant
      const devicesResp = await api.get("/admin/devices", { params: { limit: 1000 } });
      // Handle paginated response format
      const devices = Array.isArray(devicesResp.data) 
        ? devicesResp.data 
        : (devicesResp.data?.devices || []);

      // Filter environmental sensors by device name patterns and telemetry fields
      // Since Murabba devices all use generic "MQTT" device type, we detect by name/fields
      const airQualitySensors = devices.filter(d => {
        const nameLower = (d.name || d.device_id || "").toLowerCase();
        const deviceIdLower = (d.device_id || "").toLowerCase();
        return nameLower.includes("bench") || nameLower.includes("air quality") || 
               nameLower.includes("environmental") || nameLower.includes("smartbench") ||
               deviceIdLower.includes("sm1-rp") || deviceIdLower.includes("smartbench");
      });
      const weatherSensors = devices.filter(d => {
        const nameLower = (d.name || d.device_id || "").toLowerCase();
        const deviceIdLower = (d.device_id || "").toLowerCase();
        return nameLower.includes("weather") || nameLower.includes("bench") || 
               nameLower.includes("washroom") || nameLower.includes("kiosk") ||
               deviceIdLower.includes("sm1-rp") || deviceIdLower.includes("sw-rp") ||
               deviceIdLower.includes("dk_mp") || deviceIdLower.includes("smartbench");
      });
      const noiseSensors = devices.filter(d => {
        const nameLower = (d.name || d.device_id || "").toLowerCase();
        const deviceIdLower = (d.device_id || "").toLowerCase();
        return nameLower.includes("noise") || nameLower.includes("an-rp") ||
               deviceIdLower.includes("an-rp");
      });

      // Get latest telemetry for each sensor type
      const airQualityValues = { pm25: [], pm10: [], co2: [] };
      const weatherValues = { temperature: [], humidity: [] };
      const noiseValues = { level: [], peak: [] };

      // Load latest data for air quality sensors
      console.log("Air quality sensors found:", airQualitySensors.map(s => s.device_id));
      for (const sensor of airQualitySensors.slice(0, 5)) {
        try {
          const latestResp = await api.get(`/dashboard/devices/${sensor.device_id}/latest`);
          const data = latestResp.data?.data || {};
          console.log(`Air quality sensor ${sensor.device_id} data:`, data);
          
          // Try different field name patterns (including nested environment object)
          if (data.pm25 !== undefined && data.pm25 !== null) {
            airQualityValues.pm25.push(data.pm25);
            console.log(`  Found pm25: ${data.pm25}`);
          }
          if (data.pm10 !== undefined && data.pm10 !== null) {
            airQualityValues.pm10.push(data.pm10);
            console.log(`  Found pm10: ${data.pm10}`);
          }
          if (data.environment?.pm25 !== undefined && data.environment.pm25 !== null) {
            airQualityValues.pm25.push(data.environment.pm25);
            console.log(`  Found environment.pm25: ${data.environment.pm25}`);
          }
          if (data.environment?.pm10 !== undefined && data.environment.pm10 !== null) {
            airQualityValues.pm10.push(data.environment.pm10);
            console.log(`  Found environment.pm10: ${data.environment.pm10}`);
          }
          if (data.co2 !== undefined && data.co2 !== null) {
            airQualityValues.co2.push(data.co2);
            console.log(`  Found co2: ${data.co2}`);
          }
          if (data.environment?.co2 !== undefined && data.environment.co2 !== null) {
            airQualityValues.co2.push(data.environment.co2);
            console.log(`  Found environment.co2: ${data.environment.co2}`);
          }
          // Also check for VOC as air quality indicator
          if (data.voc_ppm !== undefined && data.voc_ppm !== null) {
            airQualityValues.co2.push(data.voc_ppm);
            console.log(`  Found voc_ppm: ${data.voc_ppm}`);
          }
        } catch (err) {
          console.warn(`Failed to load data for air quality sensor ${sensor.device_id}:`, err);
        }
      }
      console.log("Air quality values collected:", airQualityValues);

      // Load latest data for weather sensors
      console.log("Weather sensors found:", weatherSensors.map(s => s.device_id));
      for (const sensor of weatherSensors.slice(0, 10)) {
        try {
          const latestResp = await api.get(`/dashboard/devices/${sensor.device_id}/latest`);
          const data = latestResp.data?.data || {};
          console.log(`Weather sensor ${sensor.device_id} data:`, data);
          
          // Try different temperature field patterns
          if (data.temperature !== undefined && data.temperature !== null) {
            weatherValues.temperature.push(data.temperature);
            console.log(`  Found temperature: ${data.temperature}`);
          }
          if (data.temperature_c !== undefined && data.temperature_c !== null) {
            weatherValues.temperature.push(data.temperature_c);
            console.log(`  Found temperature_c: ${data.temperature_c}`);
          }
          if (data.environment?.temperature !== undefined && data.environment.temperature !== null) {
            weatherValues.temperature.push(data.environment.temperature);
            console.log(`  Found environment.temperature: ${data.environment.temperature}`);
          }
          
          // Try different humidity field patterns
          if (data.humidity !== undefined && data.humidity !== null) {
            weatherValues.humidity.push(data.humidity);
            console.log(`  Found humidity: ${data.humidity}`);
          }
          if (data.humidity_percent !== undefined && data.humidity_percent !== null) {
            weatherValues.humidity.push(data.humidity_percent);
            console.log(`  Found humidity_percent: ${data.humidity_percent}`);
          }
          if (data.environment?.humidity !== undefined && data.environment.humidity !== null) {
            weatherValues.humidity.push(data.environment.humidity);
            console.log(`  Found environment.humidity: ${data.environment.humidity}`);
          }
        } catch (err) {
          console.warn(`Failed to load data for weather sensor ${sensor.device_id}:`, err);
        }
      }
      console.log("Weather values collected:", weatherValues);

      // Load latest data for noise sensors
      console.log("Noise sensors found:", noiseSensors.map(s => s.device_id));
      for (const sensor of noiseSensors.slice(0, 10)) {
        try {
          const latestResp = await api.get(`/dashboard/devices/${sensor.device_id}/latest`);
          const data = latestResp.data?.data || {};
          console.log(`Noise sensor ${sensor.device_id} data:`, data);
          
          if (data.noise_level_db !== undefined && data.noise_level_db !== null) {
            noiseValues.level.push(data.noise_level_db);
            console.log(`  Found noise_level_db: ${data.noise_level_db}`);
          }
          if (data.noise_peak_db !== undefined && data.noise_peak_db !== null) {
            noiseValues.peak.push(data.noise_peak_db);
            console.log(`  Found noise_peak_db: ${data.noise_peak_db}`);
          }
        } catch (err) {
          console.warn(`Failed to load data for noise sensor ${sensor.device_id}:`, err);
        }
      }
      console.log("Noise values collected:", noiseValues);

      // Calculate averages
      const avgPM25 = airQualityValues.pm25.length > 0 
        ? airQualityValues.pm25.reduce((a, b) => a + b, 0) / airQualityValues.pm25.length 
        : null;
      const avgPM10 = airQualityValues.pm10.length > 0 
        ? airQualityValues.pm10.reduce((a, b) => a + b, 0) / airQualityValues.pm10.length 
        : null;
      const avgCO2 = airQualityValues.co2.length > 0 
        ? airQualityValues.co2.reduce((a, b) => a + b, 0) / airQualityValues.co2.length 
        : null;
      const avgTemp = weatherValues.temperature.length > 0 
        ? weatherValues.temperature.reduce((a, b) => a + b, 0) / weatherValues.temperature.length 
        : null;
      const avgHumidity = weatherValues.humidity.length > 0 
        ? weatherValues.humidity.reduce((a, b) => a + b, 0) / weatherValues.humidity.length 
        : null;
      const avgNoise = noiseValues.level.length > 0 
        ? noiseValues.level.reduce((a, b) => a + b, 0) / noiseValues.level.length 
        : null;
      const peakNoise = noiseValues.peak.length > 0 
        ? Math.max(...noiseValues.peak) 
        : null;

      // Calculate AQI
      const aqi = (avgPM25 || avgPM10) ? calculateAQI(avgPM25, avgPM10, avgCO2) : null;

      // Load historical trends for charts
      const today = new Date();
      const fromDate = new Date(today);
      
      if (timeRange === "24h") {
        fromDate.setHours(today.getHours() - 24);
      } else if (timeRange === "7d") {
        fromDate.setDate(today.getDate() - 7);
      } else if (timeRange === "30d") {
        fromDate.setDate(today.getDate() - 30);
      }

      const fromDateStr = fromDate.toISOString().slice(0, 10);
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);
      const toDateStr = tomorrow.toISOString().slice(0, 10);

      const trends = {
        pm25: [],
        pm10: [],
        temperature: [],
        humidity: [],
        noise: [],
      };

      // Load PM2.5 history from air quality sensors
      for (const sensor of airQualitySensors.slice(0, 1)) {
        try {
          const readingsResp = await api.get(`/dashboard/devices/${sensor.device_id}/readings`, {
            params: {
              key: "environment.pm25",
              from_date: fromDateStr,
              to_date: toDateStr,
              limit: 100,
            },
          });
          const pm25Readings = readingsResp.data || [];
          trends.pm25 = pm25Readings.map(r => ({
            time: new Date(r.timestamp).getTime(),
            value: r.value,
          })).sort((a, b) => a.time - b.time);

          const pm10Resp = await api.get(`/dashboard/devices/${sensor.device_id}/readings`, {
            params: {
              key: "environment.pm10",
              from_date: fromDateStr,
              to_date: toDateStr,
              limit: 100,
            },
          });
          const pm10Readings = pm10Resp.data || [];
          trends.pm10 = pm10Readings.map(r => ({
            time: new Date(r.timestamp).getTime(),
            value: r.value,
          })).sort((a, b) => a.time - b.time);
        } catch (err) {
          console.warn(`Failed to load PM history for ${sensor.device_id}:`, err);
        }
      }

      // Load temperature/humidity history from weather sensors
      for (const sensor of weatherSensors.slice(0, 1)) {
        try {
          const tempResp = await api.get(`/dashboard/devices/${sensor.device_id}/readings`, {
            params: {
              key: sensor.device_id === "SM1-RP" ? "environment.temperature" : "temperature_c",
              from_date: fromDateStr,
              to_date: toDateStr,
              limit: 100,
            },
          });
          const tempReadings = tempResp.data || [];
          trends.temperature = tempReadings.map(r => ({
            time: new Date(r.timestamp).getTime(),
            value: r.value,
          })).sort((a, b) => a.time - b.time);

          const humidityResp = await api.get(`/dashboard/devices/${sensor.device_id}/readings`, {
            params: {
              key: sensor.device_id === "SM1-RP" ? "environment.humidity" : "humidity_percent",
              from_date: fromDateStr,
              to_date: toDateStr,
              limit: 100,
            },
          });
          const humidityReadings = humidityResp.data || [];
          trends.humidity = humidityReadings.map(r => ({
            time: new Date(r.timestamp).getTime(),
            value: r.value,
          })).sort((a, b) => a.time - b.time);
        } catch (err) {
          console.warn(`Failed to load weather history for ${sensor.device_id}:`, err);
        }
      }

      // Load noise history
      for (const sensor of noiseSensors.slice(0, 1)) {
        try {
          const noiseResp = await api.get(`/dashboard/devices/${sensor.device_id}/readings`, {
            params: {
              key: "noise_level_db",
              from_date: fromDateStr,
              to_date: toDateStr,
              limit: 100,
            },
          });
          const noiseReadings = noiseResp.data || [];
          trends.noise = noiseReadings.map(r => ({
            time: new Date(r.timestamp).getTime(),
            value: r.value,
          })).sort((a, b) => a.time - b.time);
        } catch (err) {
          console.warn(`Failed to load noise history for ${sensor.device_id}:`, err);
        }
      }

      setEnvData({
        airQuality: {
          pm25: avgPM25,
          pm10: avgPM10,
          co2: avgCO2,
          aqi,
        },
        weather: {
          temperature: avgTemp,
          humidity: avgHumidity,
        },
        noise: {
          level: avgNoise,
          peak: peakNoise,
        },
        trends,
        sensorStatus: [
          { type: "Air Quality", count: airQualitySensors.length, active: airQualitySensors.filter(d => d.is_active).length },
          { type: "Weather", count: weatherSensors.length, active: weatherSensors.filter(d => d.is_active).length },
          { type: "Noise", count: noiseSensors.length, active: noiseSensors.filter(d => d.is_active).length },
        ],
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load environmental data");
    } finally {
      setLoading(false);
    }
  };

  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="card">
          <p className="text-error">Access denied. This page is only available to tenant users.</p>
        </div>
      </div>
    );
  }

  const aqiInfo = envData.airQuality.aqi ? getAQICategory(envData.airQuality.aqi) : null;

  return (
    <div className="page">
      <Breadcrumbs
        items={[
          { label: "Dashboard", path: "/dashboard" },
          { label: "Environmental Monitoring" },
        ]}
      />

      <div className="page-header">
        <div className="page-header__title-section">
          <div style={{ marginBottom: "var(--space-3)" }}>
            <BackButton />
          </div>
          <h1 className="page-header__title">Environmental Monitoring Dashboard</h1>
          <p className="page-header__subtitle">
            Real-time air quality, weather, and noise monitoring across the park
          </p>
        </div>
        <div className="page-header__actions">
          <select
            className="form-select"
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            style={{ minWidth: "120px" }}
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="badge badge--error" style={{ display: "block", padding: "var(--space-4)", marginBottom: "var(--space-6)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="card" style={{ textAlign: "center", padding: "var(--space-8)" }}>
          <Icon name="activity" size={48} style={{ opacity: 0.3 }} />
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)" }}>
            Loading environmental data...
          </p>
        </div>
      ) : (
        <>
          {/* Air Quality Index Card */}
          {envData.airQuality.aqi !== null && (
            <div className="card" style={{ marginBottom: "var(--space-6)", background: `linear-gradient(135deg, ${aqiInfo.color}15 0%, ${aqiInfo.color}05 100%)`, border: `2px solid ${aqiInfo.color}40` }}>
              <div className="card__body" style={{ textAlign: "center", padding: "var(--space-8)" }}>
                <div style={{ fontSize: "var(--font-size-4xl)", fontWeight: "var(--font-weight-bold)", color: aqiInfo.color, marginBottom: "var(--space-2)" }}>
                  {envData.airQuality.aqi}
                </div>
                <div style={{ fontSize: "var(--font-size-xl)", fontWeight: "var(--font-weight-semibold)", color: aqiInfo.color, marginBottom: "var(--space-4)" }}>
                  Air Quality Index: {aqiInfo.label}
                </div>
                <div style={{ display: "flex", justifyContent: "center", gap: "var(--space-6)", flexWrap: "wrap" }}>
                  {envData.airQuality.pm25 !== null && (
                    <div>
                      <div className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>PM2.5</div>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{envData.airQuality.pm25.toFixed(1)} μg/m³</div>
                    </div>
                  )}
                  {envData.airQuality.pm10 !== null && (
                    <div>
                      <div className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>PM10</div>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{envData.airQuality.pm10.toFixed(1)} μg/m³</div>
                    </div>
                  )}
                  {envData.airQuality.co2 !== null && (
                    <div>
                      <div className="text-muted" style={{ fontSize: "var(--font-size-xs)" }}>CO₂</div>
                      <div style={{ fontWeight: "var(--font-weight-semibold)" }}>{envData.airQuality.co2.toFixed(1)} ppm</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Summary Metrics */}
          <div className="metrics-grid" style={{ marginBottom: "var(--space-6)", gridTemplateColumns: "repeat(4, 1fr)" }}>
            {envData.weather.temperature !== null && (
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Temperature</span>
                  <Icon name="activity" size="lg" />
                </div>
                <div className="metric-card__value">
                  {envData.weather.temperature.toFixed(1)}
                  <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> °C</span>
                </div>
                {envData.weather.humidity !== null && (
                  <div className="metric-card__footer">
                    Humidity: {envData.weather.humidity.toFixed(1)}%
                  </div>
                )}
              </div>
            )}

            {envData.noise.level !== null && (
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Noise Level</span>
                  <Icon name="alert" size="lg" />
                </div>
                <div className="metric-card__value">
                  {envData.noise.level.toFixed(1)}
                  <span style={{ fontSize: "var(--font-size-sm)", fontWeight: "normal" }}> dB</span>
                </div>
                {envData.noise.peak !== null && (
                  <div className="metric-card__footer">
                    Peak: {envData.noise.peak.toFixed(1)} dB
                  </div>
                )}
              </div>
            )}

            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Active Sensors</span>
                <Icon name="devices" size="lg" />
              </div>
              <div className="metric-card__value">
                {envData.sensorStatus.reduce((sum, s) => sum + s.active, 0)}
              </div>
              <div className="metric-card__footer">
                Total: {envData.sensorStatus.reduce((sum, s) => sum + s.count, 0)} sensors
              </div>
            </div>

            {envData.airQuality.aqi !== null && (
              <div className="metric-card">
                <div className="metric-card__header">
                  <span className="metric-card__label">Air Quality Status</span>
                  <Icon name="activity" size="lg" />
                </div>
                <div className="metric-card__value" style={{ color: aqiInfo.color }}>
                  {aqiInfo.label}
                </div>
                <div className="metric-card__footer">
                  AQI: {envData.airQuality.aqi}
                </div>
              </div>
            )}
          </div>

          {/* Environmental History Chart */}
          {(envData.trends.pm25.length > 0 || envData.trends.temperature.length > 0 || envData.trends.noise.length > 0) && (
            <div className="card" style={{ marginBottom: "var(--space-6)" }}>
              <div className="card__header">
                <h3 className="card__title">Environmental Trends</h3>
              </div>
              <div className="card__body">
                <ResponsiveContainer width="100%" height={400}>
                  <AreaChart data={(() => {
                    // Combine all time series into a single dataset
                    const timeMap = new Map();
                    
                    // Add PM2.5 data
                    envData.trends.pm25.forEach(point => {
                      const key = point.time;
                      if (!timeMap.has(key)) {
                        timeMap.set(key, { timestamp: point.time, time: new Date(point.time).toLocaleTimeString() });
                      }
                      timeMap.get(key).pm25 = point.value;
                    });
                    
                    // Add PM10 data
                    envData.trends.pm10.forEach(point => {
                      const key = point.time;
                      if (!timeMap.has(key)) {
                        timeMap.set(key, { timestamp: point.time, time: new Date(point.time).toLocaleTimeString() });
                      }
                      timeMap.get(key).pm10 = point.value;
                    });
                    
                    // Add temperature data
                    envData.trends.temperature.forEach(point => {
                      const key = point.time;
                      if (!timeMap.has(key)) {
                        timeMap.set(key, { timestamp: point.time, time: new Date(point.time).toLocaleTimeString() });
                      }
                      timeMap.get(key).temperature = point.value;
                    });
                    
                    // Add humidity data
                    envData.trends.humidity.forEach(point => {
                      const key = point.time;
                      if (!timeMap.has(key)) {
                        timeMap.set(key, { timestamp: point.time, time: new Date(point.time).toLocaleTimeString() });
                      }
                      timeMap.get(key).humidity = point.value;
                    });
                    
                    // Add noise data
                    envData.trends.noise.forEach(point => {
                      const key = point.time;
                      if (!timeMap.has(key)) {
                        timeMap.set(key, { timestamp: point.time, time: new Date(point.time).toLocaleTimeString() });
                      }
                      timeMap.get(key).noise = point.value;
                    });
                    
                    return Array.from(timeMap.values()).sort((a, b) => 
                      a.timestamp - b.timestamp
                    );
                  })()}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis 
                      dataKey="time" 
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    {envData.trends.pm25.length > 0 && (
                      <Area 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="pm25" 
                        stroke="#facc15" 
                        fill="#facc15" 
                        fillOpacity={0.3}
                        name="PM2.5 (μg/m³)"
                      />
                    )}
                    {envData.trends.pm10.length > 0 && (
                      <Area 
                        yAxisId="left"
                        type="monotone" 
                        dataKey="pm10" 
                        stroke="#f97316" 
                        fill="#f97316" 
                        fillOpacity={0.3}
                        name="PM10 (μg/m³)"
                      />
                    )}
                    {envData.trends.temperature.length > 0 && (
                      <Area 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="temperature" 
                        stroke="#3b82f6" 
                        fill="#3b82f6" 
                        fillOpacity={0.3}
                        name="Temperature (°C)"
                      />
                    )}
                    {envData.trends.humidity.length > 0 && (
                      <Area 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="humidity" 
                        stroke="#10b981" 
                        fill="#10b981" 
                        fillOpacity={0.3}
                        name="Humidity (%)"
                      />
                    )}
                    {envData.trends.noise.length > 0 && (
                      <Area 
                        yAxisId="right"
                        type="monotone" 
                        dataKey="noise" 
                        stroke="#ef4444" 
                        fill="#ef4444" 
                        fillOpacity={0.3}
                        name="Noise (dB)"
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Sensor Status Grid */}
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div className="card__header">
              <h3 className="card__title">Sensor Status</h3>
            </div>
            <div className="card__body">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "var(--space-4)" }}>
                {envData.sensorStatus.map((status) => (
                  <div
                    key={status.type}
                    style={{
                      padding: "var(--space-4)",
                      backgroundColor: "var(--color-bg-secondary)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--color-border-light)",
                    }}
                  >
                    <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-2)" }}>
                      {status.type}
                    </div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)" }}>
                      <span style={{ fontSize: "var(--font-size-2xl)", fontWeight: "var(--font-weight-bold)" }}>
                        {status.active}
                      </span>
                      <span className="text-muted" style={{ fontSize: "var(--font-size-sm)" }}>
                        / {status.count}
                      </span>
                    </div>
                    <div style={{ marginTop: "var(--space-2)" }}>
                      <span className={`badge ${status.active === status.count ? "badge--success" : "badge--warning"}`}>
                        {status.active === status.count ? "All Active" : `${status.count - status.active} Offline`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Placeholder for Historical Trends */}
          {envData.trends.pm25.length === 0 && (
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">Historical Trends</h3>
              </div>
              <div className="card__body">
                <div style={{ textAlign: "center", padding: "var(--space-8)", color: "var(--color-text-secondary)" }}>
                  <Icon name="trending" size={48} style={{ opacity: 0.3, marginBottom: "var(--space-3)" }} />
                  <p>Historical trend charts will appear here once time-series data is available.</p>
                  <p style={{ fontSize: "var(--font-size-sm)", marginTop: "var(--space-2)" }}>
                    Data aggregation for {timeRange} period
                  </p>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

