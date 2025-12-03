import PropTypes from "prop-types";
import "./widgets.css";

export default function BatteryWidget({ title, value, min = 0, max = 100 }) {
  const numericValue = typeof value === "number" ? value : min;
  const clamped = Math.min(max, Math.max(min, numericValue));
  const percentage = max === min ? 0 : ((clamped - min) / (max - min)) * 100;

  // Color based on battery level
  let fillColor = "#10b981"; // green
  if (percentage < 20) fillColor = "#ef4444"; // red (critical)
  else if (percentage < 40) fillColor = "#f59e0b"; // orange (low)

  return (
    <div className="widget-content battery-widget">
      <div className="widget-title">{title}</div>
      <div className="battery-display">
        <svg viewBox="0 0 140 80" className="battery-svg">
          {/* Battery body */}
          <rect
            x="10"
            y="20"
            width="100"
            height="40"
            rx="5"
            fill="none"
            stroke="#d1d5db"
            strokeWidth="3"
          />
          
          {/* Battery terminal */}
          <rect x="110" y="30" width="10" height="20" rx="2" fill="#9ca3af" />

          {/* Battery fill */}
          <rect
            x="15"
            y="25"
            width={(percentage / 100) * 90}
            height="30"
            rx="3"
            fill={fillColor}
          />

          {/* Shine effect */}
          <rect
            x="15"
            y="25"
            width={(percentage / 100) * 90 * 0.3}
            height="10"
            rx="2"
            fill="white"
            opacity="0.3"
          />

          {/* Warning icon if low */}
          {percentage < 20 && (
            <text x="55" y="48" fontSize="20" fill="#ef4444" textAnchor="middle">
              ⚠
            </text>
          )}
        </svg>
        <div className="battery-value">
          {typeof value === "number" ? value.toFixed(0) : "—"}
          <span className="battery-unit">%</span>
        </div>
      </div>
    </div>
  );
}

BatteryWidget.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number,
  min: PropTypes.number,
  max: PropTypes.number,
};

