import PropTypes from "prop-types";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import "./widgets.css";

export default function LineChartWidget({ title, data, dataKey, unit }) {
  // data should be an array of { ts: "...", value: number }
  const chartData = (data || []).map((point) => ({
    time: new Date(point.ts).toLocaleTimeString(),
    value: point.value,
  }));

  return (
    <div className="widget-content linechart-widget">
      <div className="widget-title">{title}</div>
      {chartData.length === 0 ? (
        <p className="muted">No historical data</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData}>
            <XAxis dataKey="time" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

LineChartWidget.propTypes = {
  title: PropTypes.string.isRequired,
  data: PropTypes.array,
  dataKey: PropTypes.string,
  unit: PropTypes.string,
};

