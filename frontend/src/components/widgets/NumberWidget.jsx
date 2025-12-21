import PropTypes from "prop-types";
import Icon from "../Icon.jsx";
import "./widgets.css";

export default function NumberWidget({ title, value, unit }) {
  const displayValue =
    value !== null && value !== undefined
      ? typeof value === "number"
        ? value.toFixed(1)
        : String(value)
      : "—";

  return (
    <div className="widget-content number-widget">
      <div className="widget-title">
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "var(--radius-md)",
          background: "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)"
        }}>
          <Icon name="analytics" size={18} style={{ color: "#ffffff" }} />
        </div>
        <span>{title}</span>
      </div>
      <div className="number-display">
        <span className="number-value">{displayValue}</span>
        {unit && <span className="number-unit">{unit}</span>}
      </div>
    </div>
  );
}

NumberWidget.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  unit: PropTypes.string,
};

