import React, { useState } from "react";

/**
 * AgentTrace — numbered list of reasoning steps.
 * Collapsed to 3 steps by default; "Show all" toggle expands.
 */
export default function AgentTrace({ trace = [] }) {
  const [expanded, setExpanded] = useState(false);

  if (trace.length === 0) return null;

  const visible = expanded ? trace : trace.slice(0, 3);

  return (
    <div className="mt-4 border border-gray-200 rounded-lg p-3 bg-gray-50">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Agent Reasoning Trace</h3>
      <ol className="space-y-1">
        {visible.map((step, i) => (
          <li key={i} className="flex gap-2 text-xs text-gray-600">
            <span className="flex-shrink-0 w-5 h-5 bg-green-100 text-green-700 rounded-full flex items-center justify-center font-bold text-[10px]">
              {i + 1}
            </span>
            <span className="leading-relaxed">{step}</span>
          </li>
        ))}
      </ol>
      {trace.length > 3 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-xs text-green-600 hover:underline"
        >
          {expanded ? "Show less" : `Show all ${trace.length} steps`}
        </button>
      )}
    </div>
  );
}
