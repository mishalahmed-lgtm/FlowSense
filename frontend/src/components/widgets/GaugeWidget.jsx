import PropTypes from "prop-types";
import Icon from "../Icon.jsx";
import "./widgets.css";

export default function GaugeWidget({ title, value, unit, min = 0, max = 100 }) {
  const numericValue = typeof value === "number" ? value : min;
  const clamped = Math.min(max, Math.max(min, numericValue));
  const percentage = max === min ? 0 : ((clamped - min) / (max - min)) * 100;

  // Color zones: green (0-60%), yellow (60-80%), red (80-100%)
  let color = "#10b981"; // green
  if (percentage > 80) color = "#ef4444"; // red
  else if (percentage > 60) color = "#f59e0b"; // yellow

  return (
    <div className="widget-content gauge-widget">
      <div className="widget-title">
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "var(--radius-md)",
          background: `linear-gradient(135deg, ${color} 0%, ${color}dd 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 12px ${color}40`
        }}>
          <Icon name="activity" size={18} style={{ color: "#ffffff" }} />
        </div>
        <span>{title}</span>
      </div>
      <div className="gauge-display">
        <svg viewBox="0 0 200 120" className="gauge-svg">
          {/* Background arc */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="20"
            strokeLinecap="round"
          />
          {/* Value arc */}
          <path
            d="M 20 100 A 80 80 0 0 1 180 100"
            fill="none"
            stroke={color}
            strokeWidth="20"
            strokeLinecap="round"
            strokeDasharray={`${(percentage / 100) * 251.2} 251.2`}
          />
          {/* Center text */}
          <text x="100" y="85" textAnchor="middle" className="gauge-value">
            {typeof value === "number" ? value.toFixed(1) : "—"}
          </text>
          <text x="100" y="105" textAnchor="middle" className="gauge-unit">
            {unit || ""}
          </text>
        </svg>
      </div>
      <div className="gauge-range">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

GaugeWidget.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number,
  unit: PropTypes.string,
  min: PropTypes.number,
  max: PropTypes.number,
};

