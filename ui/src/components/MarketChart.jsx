import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import "./Charts.css";

function buildForecastData(currentPrice, trend) {
  const base = parseFloat(currentPrice) || 0;
  if (base === 0) return null;

  const delta = trend === "rising" ? 0.03 : trend === "falling" ? -0.03 : 0.01;

  return [1, 2, 3, 4].map((week) => ({
    week: `Wk ${week}`,
    price: parseFloat((base * (1 + delta * week)).toFixed(2)),
  }));
}

export default function MarketChart({ marketInsight }) {
  if (!marketInsight) return null;

  const {
    current_price_lkr_per_kg: currentPrice,
    price_trend: trend,
    price_forecast_next_4_weeks: forecast,
    best_selling_time: bestTime,
  } = marketInsight;

  let data = null;
  if (Array.isArray(forecast) && forecast.length > 0 && forecast[0].price != null) {
    data = forecast.map((d, i) => ({ week: `Wk ${i + 1}`, price: d.price }));
  } else {
    data = buildForecastData(currentPrice, trend);
  }

  const trendColor = trend === "rising" ? "#10b981" : trend === "falling" ? "#ef4444" : "#f59e0b";

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip glass-panel-heavy">
          <p className="tooltip-title">{label}</p>
          <p className="tooltip-price" style={{ color: trendColor }}>
            LKR {payload[0].value.toFixed(2)} / kg
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-container glass-panel">
      <div className="chart-header">
        <h3>Market Price Forecast</h3>
        <div className="chart-meta">
          {currentPrice > 0 && <span className="current-price badge">LKR {currentPrice}/kg 🏷️</span>}
          {trend && <span className={`trend-badge badge ${trend}`}>{trend} {trend === 'rising' ? '↗' : trend === 'falling' ? '↘' : '→'}</span>}
        </div>
      </div>

      {data ? (
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={data} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis 
                dataKey="week" 
                tick={{ fill: "var(--text-muted)", fontSize: 11 }} 
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
              />
              <YAxis 
                tick={{ fill: "var(--text-muted)", fontSize: 11 }} 
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
                domain={['auto', 'auto']}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "transparent", stroke: "rgba(255,255,255,0.1)", strokeWidth: 1 }} />
              
              {currentPrice > 0 && (
                <ReferenceLine
                  y={parseFloat(currentPrice)}
                  stroke="var(--text-muted)"
                  strokeDasharray="4 4"
                  label={{ value: "Current", position: "insideTopRight", fill: "var(--text-muted)", fontSize: 10 }}
                />
              )}
              
              <Line
                type="monotone"
                dataKey="price"
                stroke={trendColor}
                strokeWidth={3}
                dot={{ r: 4, fill: "var(--bg-base)", stroke: trendColor, strokeWidth: 2 }}
                activeDot={{ r: 6, fill: trendColor, stroke: "var(--bg-base)", strokeWidth: 2 }}
                animationDuration={1500}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        typeof forecast === "string" && forecast && (
          <p className="fallback-text">{forecast}</p>
        )
      )}

      {bestTime && (
        <div className="chart-footer">
          <span className="footer-label">Actionable Insight:</span> 
          <span className="footer-value">{bestTime}</span>
        </div>
      )}
    </div>
  );
}
