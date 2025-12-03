import PropTypes from "prop-types";
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
      <div className="widget-title">{title}</div>
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

