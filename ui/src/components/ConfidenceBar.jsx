import React from "react";

/**
 * ConfidenceBar — progress bar showing confidence score.
 * Width = score * 100%. Color by risk level: green/yellow/red.
 */
export default function ConfidenceBar({ score = 0, riskLevel = "low" }) {
  const pct = Math.round(score * 100);

  const colorClass =
    riskLevel === "high"
      ? "bg-red-500"
      : riskLevel === "medium"
      ? "bg-yellow-400"
      : "bg-green-500";

  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Confidence</span>
        <span>{pct}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs mt-1 capitalize text-gray-500">
        Risk level: <span className="font-semibold">{riskLevel}</span>
      </p>
    </div>
  );
}
