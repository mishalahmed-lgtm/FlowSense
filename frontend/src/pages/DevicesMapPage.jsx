import { useEffect, useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { createApiClient } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import Breadcrumbs from "../components/Breadcrumbs.jsx";
import BackButton from "../components/BackButton.jsx";
import Icon from "../components/Icon.jsx";
import "leaflet/dist/leaflet.css";
import "./DevicesMapPage.css";
import L from "leaflet";

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
        map.setView([highlighted.latitude, highlighted.longitude], 16);
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

export default function DevicesMapPage() {
  const { token, isTenantAdmin, user } = useAuth();
  const api = useMemo(() => createApiClient(token), [token]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [devices, setDevices] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterProtocol, setFilterProtocol] = useState("all");
  const [selectedDeviceId, setSelectedDeviceId] = useState(null);
  
  useEffect(() => {
    if (!token) return;
    loadDevices();
    const interval = setInterval(loadDevices, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [token]);
  
  const loadDevices = async () => {
    try {
      setError(null);
      const response = await api.get("/maps/devices");
      setDevices(response.data || []);
    } catch (err) {
      console.error("Failed to load devices:", err);
      setError(err.response?.data?.detail || "Failed to load device locations");
    } finally {
      setLoading(false);
    }
  };
  
  // Filter devices based on search query, status, and protocol
  const filteredDevices = useMemo(() => {
    let filtered = devices;
    
    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      filtered = filtered.filter(device => 
        device.device_name?.toLowerCase().includes(query) ||
        device.device_id?.toLowerCase().includes(query)
      );
    }
    
    // Status filter
    if (filterStatus !== "all") {
      filtered = filtered.filter(device => 
        filterStatus === "active" ? device.status === "active" : device.status === "inactive"
      );
    }
    
    // Protocol filter (if we have protocol info in device data)
    // Note: The maps API might not return protocol, so this might need adjustment
    if (filterProtocol !== "all") {
      // This will be implemented if protocol data is available
      // For now, we'll skip protocol filtering if not available
    }
    
    return filtered;
  }, [devices, searchQuery, filterStatus, filterProtocol]);
  
  // Get unique protocols from devices (if available)
  const protocols = useMemo(() => {
    // Extract protocols from devices if available
    // This might need to be adjusted based on actual data structure
    return [];
  }, [devices]);
  
  const devicesWithLocation = useMemo(() => 
    filteredDevices.filter(d => d.latitude && d.longitude),
    [filteredDevices]
  );
  const devicesWithoutLocation = useMemo(() => 
    filteredDevices.filter(d => !d.latitude || !d.longitude),
    [filteredDevices]
  );
  
  // Get search suggestions
  const searchSuggestions = useMemo(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) return [];
    const query = searchQuery.toLowerCase().trim();
    return devices
      .filter(device => 
        device.device_name?.toLowerCase().includes(query) ||
        device.device_id?.toLowerCase().includes(query)
      )
      .slice(0, 5);
  }, [devices, searchQuery]);
  
  const handleDeviceSelect = (deviceId) => {
    setSelectedDeviceId(deviceId);
    setSearchQuery("");
    // Scroll to map if needed
    setTimeout(() => {
      const mapElement = document.querySelector('.leaflet-container');
      if (mapElement) {
        mapElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);
  };
  
  // Default center (Riyadh, Saudi Arabia)
  const defaultCenter = [24.7136, 46.6753];
  const defaultZoom = 13;
  
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
  
  if (!isTenantAdmin) {
    return (
      <div className="page">
        <div className="page__header">
          <Breadcrumbs items={[{ label: "Maps", path: "/maps" }]} />
        </div>
        <div className="card">
          <div className="card__body" style={{ textAlign: "center", padding: "var(--space-8)" }}>
            <Icon name="alert" size={48} style={{ opacity: 0.3 }} />
            <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-secondary)" }}>
              Access denied. This page is only available for tenant administrators.
            </p>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="page">
      <div className="page__header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
          <div>
            <Breadcrumbs items={[{ label: "Device Map", path: "/maps" }]} />
            <h1 className="page__title">Device Map</h1>
            <p className="page__subtitle">
              View all your devices on an interactive map
            </p>
          </div>
          <BackButton />
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
            Loading device locations...
          </p>
        </div>
      ) : (
        <>
          {/* Stats Summary */}
          <div className="metrics-grid" style={{ marginBottom: "var(--space-6)", gridTemplateColumns: "repeat(3, 1fr)" }}>
            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Total Devices</span>
                <Icon name="devices" size="lg" />
              </div>
              <div className="metric-card__value">{devices.length}</div>
            </div>
            
            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">On Map</span>
                <Icon name="map" size="lg" />
              </div>
              <div className="metric-card__value">{devicesWithLocation.length}</div>
              <div className="metric-card__footer">
                {devicesWithLocation.length > 0 && (
                  <span style={{ color: "var(--color-success)" }}>
                    {Math.round((devicesWithLocation.length / devices.length) * 100)}% with location
                  </span>
                )}
              </div>
            </div>
            
            <div className="metric-card">
              <div className="metric-card__header">
                <span className="metric-card__label">Active Devices</span>
                <Icon name="check-circle" size="lg" />
              </div>
              <div className="metric-card__value">
                {filteredDevices.filter(d => d.status === "active").length}
              </div>
            </div>
          </div>
          
          {/* Filters Section */}
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)", flexWrap: "wrap" }}>
              {/* Search */}
              <div className="search-bar" style={{ position: "relative", flex: "1", minWidth: "200px" }}>
                <span className="search-bar__icon">
                  <Icon name="search" size={18} />
                </span>
                <input
                  type="text"
                  className="search-bar__input"
                  placeholder="Search devices..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setSelectedDeviceId(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      setSearchQuery("");
                      setSelectedDeviceId(null);
                    } else if (e.key === "Enter" && searchSuggestions.length > 0) {
                      handleDeviceSelect(searchSuggestions[0].device_id);
                    }
                  }}
                />
                {searchQuery && (
                  <button
                    onClick={() => {
                      setSearchQuery("");
                      setSelectedDeviceId(null);
                    }}
                    style={{
                      position: "absolute",
                      right: "var(--space-2)",
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      padding: "var(--space-1)",
                      display: "flex",
                      alignItems: "center",
                      color: "var(--color-text-secondary)",
                    }}
                  >
                    <Icon name="x" size="sm" />
                  </button>
                )}
                
                {/* Search Suggestions Dropdown */}
                {searchQuery.trim().length >= 2 && searchSuggestions.length > 0 && (
                  <div style={{
                    position: "absolute",
                    top: "100%",
                    left: 0,
                    right: 0,
                    marginTop: "var(--space-1)",
                    background: "var(--color-bg-primary)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius-md)",
                    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
                    zIndex: 1000,
                    maxHeight: "300px",
                    overflowY: "auto",
                  }}>
                    {searchSuggestions.map((device) => (
                      <div
                        key={device.device_id}
                        onClick={() => handleDeviceSelect(device.device_id)}
                        style={{
                          padding: "var(--space-3)",
                          cursor: "pointer",
                          borderBottom: "1px solid var(--color-border)",
                          transition: "background-color 0.2s",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = "var(--color-bg-secondary)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = "transparent";
                        }}
                      >
                        <div style={{ 
                          fontWeight: "var(--font-weight-semibold)",
                          marginBottom: "var(--space-1)",
                          color: "var(--color-text-primary)"
                        }}>
                          {device.device_name}
                        </div>
                        <div style={{ 
                          fontSize: "var(--font-size-sm)",
                          color: "var(--color-text-secondary)"
                        }}>
                          {device.device_id}
                        </div>
                        <div style={{ 
                          fontSize: "var(--font-size-xs)",
                          marginTop: "var(--space-1)",
                          color: device.status === "active" ? "var(--color-success)" : "var(--color-error)"
                        }}>
                          {device.status === "active" ? "● Active" : "● Inactive"}
                          {device.latitude && device.longitude && " • Has location"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Status Filter */}
              <select
                className="filter-select"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
              >
                <option value="all">All Status</option>
                <option value="active">Online</option>
                <option value="inactive">Offline</option>
              </select>

              {/* Protocol Filter - Only show if protocols are available */}
              {protocols.length > 0 && (
                <select
                  className="filter-select"
                  value={filterProtocol}
                  onChange={(e) => setFilterProtocol(e.target.value)}
                >
                  <option value="all">All Protocols</option>
                  {protocols.map((protocol) => (
                    <option key={protocol} value={protocol}>
                      {protocol}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
          
          {/* Map */}
          <div className="card" style={{ marginBottom: "var(--space-6)" }}>
            <div className="card__header">
              <h3 className="card__title">
                Device Locations
                {(searchQuery || filterStatus !== "all" || filterProtocol !== "all") && (
                  <span style={{ 
                    fontSize: "var(--font-size-sm)",
                    fontWeight: "var(--font-weight-normal)",
                    color: "var(--color-text-secondary)",
                    marginLeft: "var(--space-2)"
                  }}>
                    ({devicesWithLocation.length} {devicesWithLocation.length === 1 ? 'device' : 'devices'} found)
                  </span>
                )}
              </h3>
            </div>
            <div className="card__body" style={{ padding: 0 }}>
              <div style={{ height: "600px", width: "100%", position: "relative" }}>
                {devicesWithLocation.length > 0 ? (
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
                    <MapBounds devices={devicesWithLocation} highlightDeviceId={selectedDeviceId} />
                    {devicesWithLocation.map((device) => (
                      <Marker
                        key={device.device_id}
                        position={[device.latitude, device.longitude]}
                        icon={device.status === "active" ? activeIcon : inactiveIcon}
                        eventHandlers={{
                          click: () => {
                            setSelectedDeviceId(device.device_id);
                          }
                        }}
                      >
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
                      </Marker>
                    ))}
                  </MapContainer>
                ) : (
                  <div style={{ 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center", 
                    height: "100%",
                    flexDirection: "column",
                    color: "var(--color-text-secondary)"
                  }}>
                    <Icon name="map" size={64} style={{ opacity: 0.3, marginBottom: "var(--space-4)" }} />
                    <p>No devices with location data available</p>
                    <p style={{ fontSize: "var(--font-size-sm)", marginTop: "var(--space-2)" }}>
                      Devices need to send latitude/longitude in their telemetry payloads
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Devices without location */}
          {devicesWithoutLocation.length > 0 && (
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">Devices Without Location Data</h3>
              </div>
              <div className="card__body">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "var(--space-4)" }}>
                  {devicesWithoutLocation.map((device) => (
                    <div
                      key={device.device_id}
                      style={{
                        padding: "var(--space-4)",
                        border: "1px solid var(--color-border)",
                        borderRadius: "var(--radius-md)",
                        background: "var(--color-bg-secondary)",
                      }}
                    >
                      <div style={{ fontWeight: "var(--font-weight-semibold)", marginBottom: "var(--space-1)" }}>
                        {device.device_name}
                      </div>
                      <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-secondary)", marginBottom: "var(--space-2)" }}>
                        {device.device_id}
                      </div>
                      <div style={{ fontSize: "var(--font-size-sm)" }}>
                        <span style={{ 
                          color: device.status === "active" ? "var(--color-success)" : "var(--color-error)",
                          fontWeight: "var(--font-weight-semibold)"
                        }}>
                          {device.status === "active" ? "● Active" : "● Inactive"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

