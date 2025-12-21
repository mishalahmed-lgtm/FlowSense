import PropTypes from "prop-types";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from "recharts";
import Icon from "../Icon.jsx";
import "./widgets.css";

export default function LineChartWidget({ title, data, dataKey, unit }) {
  // data should be an array of { ts: "...", value: number }
  const chartData = (data || []).map((point) => ({
    time: new Date(point.ts).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }),
    fullTime: new Date(point.ts).toLocaleString(),
    value: point.value,
  }));

  // Determine color based on value range (can be customized)
  const getColor = () => {
    if (unit === "°C") return "#f59e0b"; // Orange for temperature
    if (unit === "%") return "#10b981"; // Green for percentages
    return "#3b82f6"; // Blue default
  };

  const lineColor = getColor();

  return (
    <div className="widget-content linechart-widget" style={{
      background: "linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%)",
      border: "1px solid var(--color-border-light)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-lg)",
      padding: "var(--space-5)",
      transition: "all 0.3s ease"
    }}>
      <div style={{
        fontSize: "var(--font-size-base)",
        fontWeight: "var(--font-weight-semibold)",
        color: "var(--color-text-primary)",
        marginBottom: "var(--space-4)",
        display: "flex",
        alignItems: "center",
        gap: "var(--space-2)"
      }}>
        <div style={{
          width: "32px",
          height: "32px",
          borderRadius: "var(--radius-md)",
          background: `linear-gradient(135deg, ${lineColor} 0%, ${lineColor}dd 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 12px ${lineColor}40`
        }}>
          <Icon name="trending" size={18} style={{ color: "#ffffff" }} />
        </div>
        <span>{title}</span>
      </div>
      {chartData.length === 0 ? (
        <div style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-tertiary)",
          padding: "var(--space-8)"
        }}>
          <p style={{ margin: 0 }}>No historical data</p>
        </div>
      ) : (
        <div style={{ height: "220px", width: "100%" }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
              <defs>
                <linearGradient id={`gradient-${title.replace(/\s+/g, '-')}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={lineColor} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
                stroke="rgba(255,255,255,0.1)"
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--color-text-tertiary)", fontSize: 11 }}
                stroke="rgba(255,255,255,0.1)"
                tickLine={false}
                label={unit ? {
                  value: unit,
                  angle: -90,
                  position: "insideLeft",
                  fill: "var(--color-text-tertiary)",
                  style: { textAnchor: 'middle', fontSize: 11 }
                } : null}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--color-bg-card)",
                  border: "1px solid var(--color-border-medium)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-3)",
                  boxShadow: "var(--shadow-lg)"
                }}
                labelStyle={{
                  color: "var(--color-text-primary)",
                  fontWeight: "var(--font-weight-semibold)",
                  marginBottom: "var(--space-2)"
                }}
                itemStyle={{
                  color: lineColor,
                  fontWeight: "var(--font-weight-medium)"
                }}
                formatter={(value) => [`${value}${unit || ''}`, title]}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullTime || label}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={lineColor}
                strokeWidth={3}
                fill={`url(#gradient-${title.replace(/\s+/g, '-')})`}
                dot={{ fill: lineColor, r: 4, strokeWidth: 2, stroke: "var(--color-bg-card)" }}
                activeDot={{ r: 6, strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
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

