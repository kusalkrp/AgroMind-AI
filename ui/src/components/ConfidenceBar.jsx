import React, { useEffect, useState } from "react";
import "./ConfidenceBar.css";

export default function ConfidenceBar({ score = 0, riskLevel = "low" }) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const pct = Math.round(score * 100);

  // Animate the bar filling up on mount
  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(pct), 100);
    return () => clearTimeout(timer);
  }, [pct]);

  return (
    <div className="confidence-container">
      <div className="confidence-header">
        <span className="confidence-label">AI Confidence</span>
        <span className={`confidence-value ${riskLevel}`}>{animatedScore}%</span>
      </div>
      
      <div className="progress-track glass-panel">
        <div 
          className={`progress-fill ${riskLevel}`}
          style={{ width: `${animatedScore}%` }}
        />
      </div>
      
      <div className="risk-footer">
        Assessed Risk Level: <span className={`risk-badge ${riskLevel}`}>{riskLevel}</span>
      </div>
    </div>
  );
}
