import { useEffect, useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { createApiClient } from "../api/client.js";
import Icon from "./Icon.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import "./DeviceMapView.css";

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

// Custom marker icons
const activeIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const inactiveIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Component to auto-fit map bounds to markers
function MapBounds({ devices, highlightDeviceId }) {
  const map = useMap();
  
  useEffect(() => {
    if (devices.length === 0) return;
    
    const validDevices = devices.filter(d => d.latitude && d.longitude);
    if (validDevices.length === 0) return;
    
    // If highlighting a specific device, center on it
    if (highlightDeviceId) {
      const highlighted = validDevices.find(d => d.device_id === highlightDeviceId);
      if (highlighted) {
        map.setView([highlighted.latitude, highlighted.longitude], 15);
        return;
      }
    }
    
    if (validDevices.length === 1) {
      map.setView([validDevices[0].latitude, validDevices[0].longitude], 15);
    } else {
      const bounds = L.latLngBounds(
        validDevices.map(d => [d.latitude, d.longitude])
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [devices, highlightDeviceId, map]);
  
  return null;
}

export default function DeviceMapView({ 
  deviceIds = null, 
  highlightDeviceId = null, 
  height = "400px",
  showPopup = true 
}) {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Use auth context token so this works everywhere in the app
  const { token } = useAuth();
  const api = useMemo(() => createApiClient(token), [token]);
  
  useEffect(() => {
    if (!token) return;
    loadDevices();
  }, [token, deviceIds]);
  
  const loadDevices = async () => {
    try {
      setError(null);
      const response = await api.get("/maps/devices");
      let allDevices = response.data || [];
      
      // Filter by deviceIds if provided
      if (deviceIds && deviceIds.length > 0) {
        allDevices = allDevices.filter(d => deviceIds.includes(d.device_id));
      }
      
      setDevices(allDevices);
    } catch (err) {
      console.error("Failed to load devices:", err);
      setError(err.response?.data?.detail || "Failed to load device locations");
    } finally {
      setLoading(false);
    }
  };
  
  const formatLastSeen = (lastSeen) => {
    if (!lastSeen) return "Never";
    const date = new Date(lastSeen);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
    return `${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
  };
  
  const devicesWithLocation = devices.filter(d => d.latitude && d.longitude);
  const defaultCenter = [24.6600, 46.7200]; // Murabba, Riyadh
  const defaultZoom = 13;
  
  if (loading) {
    return (
      <div style={{ 
        height, 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center",
        background: "var(--color-bg-secondary)",
        borderRadius: "var(--radius-md)"
      }}>
        <Icon name="activity" size={32} style={{ opacity: 0.3 }} />
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={{ 
        height, 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center",
        background: "var(--color-bg-secondary)",
        borderRadius: "var(--radius-md)",
        color: "var(--color-error)"
      }}>
        {error}
      </div>
    );
  }
  
  if (devicesWithLocation.length === 0) {
    return (
      <div style={{ 
        height, 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center",
        flexDirection: "column",
        background: "var(--color-bg-secondary)",
        borderRadius: "var(--radius-md)",
        color: "var(--color-text-secondary)"
      }}>
        <Icon name="map" size={48} style={{ opacity: 0.3, marginBottom: "var(--space-2)" }} />
        <p>No devices with location data</p>
      </div>
    );
  }
  
  return (
    <div style={{ height, width: "100%", position: "relative", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        style={{ height: "100%", width: "100%", zIndex: 1 }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapBounds devices={devicesWithLocation} highlightDeviceId={highlightDeviceId} />
        {devicesWithLocation.map((device) => (
          <Marker
            key={device.device_id}
            position={[device.latitude, device.longitude]}
            icon={device.device_id === highlightDeviceId ? activeIcon : (device.status === "active" ? activeIcon : inactiveIcon)}
          >
            {showPopup && (
              <Popup maxWidth={300}>
                <div 
                  style={{ 
                    width: "280px",
                    height: "350px",
                    overflowY: "auto",
                    overflowX: "hidden",
                    color: "#1a1a1a",
                    paddingRight: "12px",
                    paddingLeft: "4px",
                    boxSizing: "border-box"
                  }}
                  className="popup-scrollable"
                >
                  <h4 style={{ 
                    margin: "0 0 var(--space-3) 0", 
                    fontSize: "var(--font-size-lg)", 
                    fontWeight: "var(--font-weight-bold)",
                    color: "#000000"
                  }}>
                    {device.device_name}
                  </h4>
                  
                  <div style={{ 
                    display: "flex", 
                    flexDirection: "column", 
                    gap: "var(--space-2)",
                    marginBottom: "var(--space-3)"
                  }}>
                    <div>
                      <span style={{ 
                        fontSize: "11px", 
                        color: "#666666",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        fontWeight: "var(--font-weight-semibold)"
                      }}>
                        Device ID
                      </span>
                      <div style={{ 
                        fontSize: "var(--font-size-sm)", 
                        fontWeight: "var(--font-weight-semibold)",
                        marginTop: "4px",
                        color: "#1a1a1a"
                      }}>
                        {device.device_id}
                      </div>
                    </div>
                    
                    <div>
                      <span style={{ 
                        fontSize: "11px", 
                        color: "#666666",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        fontWeight: "var(--font-weight-semibold)"
                      }}>
                        Status
                      </span>
                      <div style={{ marginTop: "4px" }}>
                        <span style={{ 
                          color: device.status === "active" ? "#10b981" : "#ef4444",
                          fontWeight: "var(--font-weight-bold)",
                          fontSize: "var(--font-size-sm)"
                        }}>
                          {device.status === "active" ? "● Active" : "● Inactive"}
                        </span>
                      </div>
                    </div>
                    
                    <div>
                      <span style={{ 
                        fontSize: "11px", 
                        color: "#666666",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        fontWeight: "var(--font-weight-semibold)"
                      }}>
                        Last Seen
                      </span>
                      <div style={{ 
                        fontSize: "var(--font-size-sm)", 
                        marginTop: "4px",
                        color: "#1a1a1a",
                        fontWeight: "var(--font-weight-medium)"
                      }}>
                        {formatLastSeen(device.last_seen)}
                      </div>
                    </div>
                    
                    {device.latitude && device.longitude && (
                      <div>
                        <span style={{ 
                          fontSize: "11px", 
                          color: "#666666",
                          textTransform: "uppercase",
                          letterSpacing: "0.5px",
                          fontWeight: "var(--font-weight-semibold)"
                        }}>
                          Location
                        </span>
                        <div style={{ 
                          fontSize: "var(--font-size-sm)", 
                          marginTop: "4px",
                          fontFamily: "monospace",
                          color: "#1a1a1a",
                          fontWeight: "var(--font-weight-medium)"
                        }}>
                          {device.latitude.toFixed(4)}, {device.longitude.toFixed(4)}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {device.latest_data && Object.keys(device.latest_data).length > 0 && (
                    <div style={{ 
                      marginTop: "var(--space-3)", 
                      paddingTop: "var(--space-3)", 
                      borderTop: "1px solid #e5e5e5"
                    }}>
                      <p style={{ 
                        margin: "0 0 var(--space-2) 0", 
                        fontSize: "11px", 
                        color: "#666666",
                        textTransform: "uppercase",
                        letterSpacing: "0.5px",
                        fontWeight: "var(--font-weight-bold)"
                      }}>
                        Key Metrics
                      </p>
                      <div style={{ 
                        display: "flex", 
                        flexDirection: "column", 
                        gap: "var(--space-1)",
                        fontSize: "var(--font-size-xs)"
                      }}>
                        {Object.entries(device.latest_data)
                          .filter(([key]) => 
                            !['deviceId', 'timestamp', 'latitude', 'longitude', 'access_token', 'token'].includes(key) &&
                            device.latest_data[key] !== null &&
                            device.latest_data[key] !== undefined &&
                            typeof device.latest_data[key] !== 'object'
                          )
                          .slice(0, 5)
                          .map(([key, value]) => (
                            <div key={key} style={{ 
                              display: "flex", 
                              justifyContent: "space-between",
                              padding: "var(--space-1) 0",
                              borderBottom: "1px solid #f0f0f0"
                            }}>
                              <span style={{ color: "#666666", fontWeight: "var(--font-weight-medium)" }}>
                                {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:
                              </span>
                              <span style={{ 
                                fontWeight: "var(--font-weight-semibold)",
                                color: "#000000"
                              }}>
                                {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              </Popup>
            )}
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

