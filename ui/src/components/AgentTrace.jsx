import React, { useState } from "react";
import "./AgentTrace.css";

export default function AgentTrace({ trace = [] }) {
  const [expanded, setExpanded] = useState(false);

  if (trace.length === 0) return null;

  const visible = expanded ? trace : trace.slice(0, 3);

  return (
    <div className="agent-trace-container glass-panel">
      <div className="trace-header">
        <span className="trace-icon">⚡</span>
        <h3>Reasoning Trace</h3>
      </div>
      
      <ol className="trace-list">
        {visible.map((step, i) => (
          <li key={i} className="trace-item animate-fade-in-up" style={{ animationDelay: `${i * 0.1}s` }}>
            <span className="step-number">{i + 1}</span>
            <span className="step-text">{step}</span>
          </li>
        ))}
      </ol>
      
      {trace.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="trace-toggle-btn"
        >
          {expanded ? "Collapse steps" : `View all ${trace.length} steps`}
        </button>
      )}
    </div>
  );
}
