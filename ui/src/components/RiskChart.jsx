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
import "./Charts.css";

const SEVERITY_VALUE = { low: 1, medium: 2, high: 3 };
const SEVERITY_COLOR = { low: "#10b981", medium: "#f59e0b", high: "#ef4444" }; // Using the CSS variables functionally

export default function RiskChart({ riskAssessment }) {
  if (!riskAssessment) return null;

  const { overall_risk_level, risk_factors = [], disease_threats = [], pest_threats = [] } = riskAssessment;

  const chartData = risk_factors.slice(0, 6).map((f) => ({
    name: f.factor?.length > 16 ? f.factor.slice(0, 16) + "…" : f.factor,
    fullName: f.factor,
    value: SEVERITY_VALUE[f.severity] || 1,
    severity: f.severity || "low",
    mitigation: f.mitigation,
  }));

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="custom-tooltip glass-panel-heavy">
          <p className="tooltip-title text-gradient">{data.fullName}</p>
          <p className="tooltip-severity">Severity: <span className={`risk-badge ${data.severity}`}>{data.severity}</span></p>
          {data.mitigation && <p className="tooltip-mitigation text-secondary text-xs mt-1">{data.mitigation}</p>}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="chart-container glass-panel">
      <div className="chart-header">
        <h3>Risk Factors Breakdown</h3>
      </div>

      {chartData.length > 0 && (
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height={160}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
              <XAxis
                type="number"
                domain={[0, 3]}
                ticks={[1, 2, 3]}
                tickFormatter={(v) => ["", "Low", "Med", "High"][v]}
                tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
              />
              <YAxis 
                type="category" 
                dataKey="name" 
                tick={{ fill: "var(--text-secondary)", fontSize: 11 }} 
                width={85} 
                axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                tickLine={false}
              />
              <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} content={<CustomTooltip />} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={16}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={SEVERITY_COLOR[entry.severity]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {(disease_threats.length > 0 || pest_threats.length > 0) && (
        <div className="threat-tags-container">
          {disease_threats.slice(0, 3).map((t) => (
            <span key={t} className="threat-tag disease">🦠 {t}</span>
          ))}
          {pest_threats.slice(0, 3).map((t) => (
            <span key={t} className="threat-tag pest">🐛 {t}</span>
          ))}
        </div>
      )}
    </div>
  );
}
