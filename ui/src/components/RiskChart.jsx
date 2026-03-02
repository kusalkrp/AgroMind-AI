import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const SEVERITY_VALUE = { low: 1, medium: 2, high: 3 };
const SEVERITY_COLOR = { low: "#16a34a", medium: "#d97706", high: "#dc2626" };
const LEVEL_COLOR = { low: "text-green-600 bg-green-50", medium: "text-yellow-600 bg-yellow-50", high: "text-red-600 bg-red-50" };

export default function RiskChart({ riskAssessment }) {
  if (!riskAssessment) return null;

  const { overall_risk_level, risk_factors = [], disease_threats = [], pest_threats = [] } = riskAssessment;

  // Build bar chart data from risk_factors
  const chartData = risk_factors.slice(0, 6).map((f) => ({
    name: f.factor?.length > 16 ? f.factor.slice(0, 16) + "…" : f.factor,
    fullName: f.factor,
    value: SEVERITY_VALUE[f.severity] || 1,
    severity: f.severity || "low",
    mitigation: f.mitigation,
  }));

  const levelClass = LEVEL_COLOR[overall_risk_level] || LEVEL_COLOR.low;

  return (
    <div className="mt-4 p-3 bg-white border border-gray-200 rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-sm font-semibold text-gray-700">Risk Assessment</h3>
        {overall_risk_level && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-semibold capitalize ${levelClass}`}>
            {overall_risk_level} risk
          </span>
        )}
      </div>

      {/* Risk factors bar chart */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={130}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 16, left: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
            <XAxis
              type="number"
              domain={[0, 3]}
              ticks={[1, 2, 3]}
              tickFormatter={(v) => ["", "Low", "Med", "High"][v]}
              tick={{ fontSize: 10 }}
            />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
            <Tooltip
              formatter={(_, __, props) => [
                props.payload.severity,
                props.payload.fullName,
              ]}
              contentStyle={{ fontSize: 11 }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={SEVERITY_COLOR[entry.severity] || "#94a3b8"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}

      {/* Threat tags */}
      {(disease_threats.length > 0 || pest_threats.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {disease_threats.slice(0, 3).map((t) => (
            <span key={t} className="text-xs px-1.5 py-0.5 bg-red-50 text-red-600 rounded">
              {t}
            </span>
          ))}
          {pest_threats.slice(0, 3).map((t) => (
            <span key={t} className="text-xs px-1.5 py-0.5 bg-orange-50 text-orange-600 rounded">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
