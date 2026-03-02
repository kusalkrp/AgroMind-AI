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

/**
 * Build 4-week price data from current price + trend string.
 * Used when the LLM returns a text forecast instead of structured data.
 */
function buildForecastData(currentPrice, trend) {
  const base = parseFloat(currentPrice) || 0;
  if (base === 0) return null;

  const delta =
    trend === "rising" ? 0.03 : trend === "falling" ? -0.03 : 0.01;

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

  // Prefer structured array; fall back to building from price+trend
  let data = null;
  if (Array.isArray(forecast) && forecast.length > 0 && forecast[0].price != null) {
    data = forecast.map((d, i) => ({ week: `Wk ${i + 1}`, price: d.price }));
  } else {
    data = buildForecastData(currentPrice, trend);
  }

  const trendColor =
    trend === "rising" ? "#16a34a" : trend === "falling" ? "#dc2626" : "#d97706";

  return (
    <div className="mt-4 p-3 bg-white border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700">Market Price Forecast</h3>
        <div className="flex items-center gap-2 text-xs">
          {currentPrice > 0 && (
            <span className="font-semibold text-gray-800">
              LKR {currentPrice}/kg
            </span>
          )}
          {trend && (
            <span
              className="px-2 py-0.5 rounded-full capitalize font-medium"
              style={{ background: `${trendColor}20`, color: trendColor }}
            >
              {trend}
            </span>
          )}
        </div>
      </div>

      {data ? (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data} margin={{ top: 4, right: 16, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(v) => [`LKR ${v}`, "Price"]}
              contentStyle={{ fontSize: 12 }}
            />
            {currentPrice > 0 && (
              <ReferenceLine
                y={parseFloat(currentPrice)}
                stroke="#94a3b8"
                strokeDasharray="4 4"
                label={{ value: "now", position: "insideTopRight", fontSize: 10, fill: "#94a3b8" }}
              />
            )}
            <Line
              type="monotone"
              dataKey="price"
              stroke={trendColor}
              strokeWidth={2}
              dot={{ r: 4, fill: trendColor }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        typeof forecast === "string" && forecast && (
          <p className="text-xs text-gray-600">{forecast}</p>
        )
      )}

      {bestTime && (
        <p className="text-xs text-gray-500 mt-2">
          <span className="font-medium">Best time to sell:</span> {bestTime}
        </p>
      )}
    </div>
  );
}
