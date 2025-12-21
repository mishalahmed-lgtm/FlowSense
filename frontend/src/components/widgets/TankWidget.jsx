import PropTypes from "prop-types";
import Icon from "../Icon.jsx";
import "./widgets.css";

export default function TankWidget({ title, value, unit = "%", min = 0, max = 100 }) {
  const numericValue = typeof value === "number" ? value : min;
  const clamped = Math.min(max, Math.max(min, numericValue));
  const percentage = max === min ? 0 : ((clamped - min) / (max - min)) * 100;

  // Color zones
  let fillColor = "#10b981"; // green
  if (percentage < 20) fillColor = "#ef4444"; // red (low)
  else if (percentage < 40) fillColor = "#f59e0b"; // orange (medium-low)

  return (
    <div className="widget-content tank-widget">
      <div className="widget-title">
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "var(--radius-md)",
          background: `linear-gradient(135deg, ${fillColor} 0%, ${fillColor}dd 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 12px ${fillColor}40`
        }}>
          <Icon name="droplet" size={18} style={{ color: "#ffffff" }} />
        </div>
        <span>{title}</span>
      </div>
      <div className="tank-display">
        <div style={{ position: "relative", display: "inline-block" }}>
          <svg viewBox="0 0 120 160" className="tank-svg">
            {/* Tank outline */}
            <path
              d="M 30 20 L 30 120 Q 30 140 50 145 L 70 145 Q 90 140 90 120 L 90 20 Q 90 10 80 10 L 40 10 Q 30 10 30 20 Z"
              fill="none"
              stroke="#d1d5db"
              strokeWidth="3"
            />

            {/* Tank cap */}
            <rect x="35" y="5" width="50" height="10" rx="3" fill="#9ca3af" />
            
            {/* Liquid fill with gradient */}
            <defs>
              <linearGradient id={`tankGradient-${title}`} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={fillColor} stopOpacity="0.7" />
                <stop offset="50%" stopColor={fillColor} stopOpacity="0.9" />
                <stop offset="100%" stopColor={fillColor} stopOpacity="0.7" />
              </linearGradient>
            </defs>
            
            <clipPath id={`tankClip-${title}`}>
              <path d="M 32 22 L 32 120 Q 32 138 50 143 L 70 143 Q 88 138 88 120 L 88 22 Z" />
            </clipPath>

            <rect
              x="32"
              y={145 - (percentage / 100) * 123}
              width="56"
              height={(percentage / 100) * 123}
              fill={`url(#tankGradient-${title})`}
              clipPath={`url(#tankClip-${title})`}
            />

            {/* Level markers */}
            {[25, 50, 75].map((level) => (
              <line
                key={level}
                x1="32"
                y1={145 - (level / 100) * 123}
                x2="88"
                y2={145 - (level / 100) * 123}
                stroke="#e5e7eb"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
            ))}

            {/* Shine effect */}
            <ellipse cx="50" cy="50" rx="12" ry="20" fill="white" opacity="0.2" />
            
            {/* Percentage text inside tank */}
            <text
              x="60"
              y="85"
              textAnchor="middle"
              fontSize="24"
              fontWeight="700"
              fill="#ffffff"
              stroke="#111827"
              strokeWidth="0.5"
            >
              {typeof value === "number" ? value.toFixed(0) : "—"}
            </text>
            <text
              x="60"
              y="105"
              textAnchor="middle"
              fontSize="16"
              fill="#ffffff"
              stroke="#111827"
              strokeWidth="0.5"
            >
              {unit}
            </text>
          </svg>
        </div>
      </div>
    </div>
  );
}

TankWidget.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number,
  unit: PropTypes.string,
  min: PropTypes.number,
  max: PropTypes.number,
};

