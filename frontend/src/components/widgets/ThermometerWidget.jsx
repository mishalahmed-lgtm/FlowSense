import PropTypes from "prop-types";
import Icon from "../Icon.jsx";
import "./widgets.css";

export default function ThermometerWidget({ title, value, unit = "°C", min = -20, max = 50 }) {
  const numericValue = typeof value === "number" ? value : min;
  const clamped = Math.min(max, Math.max(min, numericValue));
  const percentage = max === min ? 0 : ((clamped - min) / (max - min)) * 100;

  // Color based on temperature
  let mercuryColor = "#3b82f6"; // blue (cold)
  if (clamped > 30) mercuryColor = "#ef4444"; // red (hot)
  else if (clamped > 20) mercuryColor = "#f59e0b"; // orange (warm)

  return (
    <div className="widget-content thermometer-widget">
      <div className="widget-title">
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "var(--radius-md)",
          background: `linear-gradient(135deg, ${mercuryColor} 0%, ${mercuryColor}dd 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 12px ${mercuryColor}40`
        }}>
          <Icon name="activity" size={18} style={{ color: "#ffffff" }} />
        </div>
        <span>{title}</span>
      </div>
      <div className="thermometer-display">
        <svg viewBox="0 0 80 200" className="thermometer-svg">
          {/* Outer tube */}
          <rect
            x="25"
            y="20"
            width="30"
            height="140"
            rx="15"
            fill="none"
            stroke="#d1d5db"
            strokeWidth="2"
          />
          
          {/* Scale marks */}
          {[0, 25, 50, 75, 100].map((mark) => {
            const y = 160 - (mark / 100) * 140;
            return (
              <g key={mark}>
                <line x1="20" y1={y} x2="25" y2={y} stroke="#9ca3af" strokeWidth="1" />
                <line x1="55" y1={y} x2="60" y2={y} stroke="#9ca3af" strokeWidth="1" />
              </g>
            );
          })}

          {/* Mercury reservoir (bulb) */}
          <circle cx="40" cy="175" r="15" fill={mercuryColor} />
          <circle cx="40" cy="175" r="15" fill="none" stroke="#d1d5db" strokeWidth="2" />

          {/* Mercury column */}
          <rect
            x="30"
            y={160 - (percentage / 100) * 140}
            width="20"
            height={(percentage / 100) * 140 + 15}
            fill={mercuryColor}
            rx="10"
          />

          {/* Inner tube overlay for 3D effect */}
          <rect
            x="28"
            y="20"
            width="8"
            height="140"
            fill="white"
            opacity="0.3"
            rx="4"
          />
        </svg>
        <div className="thermometer-value">
          {typeof value === "number" ? value.toFixed(1) : "—"}
          <span className="thermometer-unit">{unit}</span>
        </div>
      </div>
      <div className="thermometer-range">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

ThermometerWidget.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number,
  unit: PropTypes.string,
  min: PropTypes.number,
  max: PropTypes.number,
};

