import React, { useState } from "react";
import { postQuery } from "../api/client.js";
import AgentTrace from "./AgentTrace.jsx";
import ConfidenceBar from "./ConfidenceBar.jsx";
import MarketChart from "./MarketChart.jsx";
import RiskChart from "./RiskChart.jsx";

const DISTRICTS = [
  "Colombo", "Kandy", "Galle", "Jaffna", "Anuradhapura",
  "Polonnaruwa", "Kurunegala", "Ratnapura", "Matara", "Badulla",
];

const CROPS = ["paddy", "maize", "tea", "rubber", "coconut", "vegetables", "banana"];

/**
 * QueryPanel — main query form + result display.
 * Props:
 *   selectedDistrict {string}  — district selected from the map
 *   onDistrictChange {fn}      — callback when user changes district in form
 */
export default function QueryPanel({ selectedDistrict, onDistrictChange }) {
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState(selectedDistrict || "");
  const [crop, setCrop] = useState("");
  const [language, setLanguage] = useState("english");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Sync district from map clicks
  React.useEffect(() => {
    if (selectedDistrict) setDistrict(selectedDistrict);
  }, [selectedDistrict]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await postQuery({
        query: query.trim(),
        district: district || undefined,
        crop: crop || undefined,
        language,
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function handleDistrictChange(val) {
    setDistrict(val);
    onDistrictChange && onDistrictChange(val);
  }

  return (
    <div className="flex flex-col h-full">
      {/* ── Query form ── */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Your question
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            placeholder="e.g. What fertilizer should I use for paddy in Kandy?"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-green-400 resize-none"
          />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">District</label>
            <select
              value={district}
              onChange={(e) => handleDistrictChange(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">Any</option>
              {DISTRICTS.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Crop</label>
            <select
              value={crop}
              onChange={(e) => setCrop(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">Any</option>
              {CROPS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Language</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm
                         focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="english">English</option>
              <option value="sinhala">Sinhala</option>
              <option value="tamil">Tamil</option>
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-300
                     text-white font-semibold py-2 px-4 rounded-lg transition-colors text-sm"
        >
          {loading ? "Thinking…" : "Ask AgroMind"}
        </button>
      </form>

      {/* ── Error ── */}
      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* ── Result ── */}
      {result && (
        <div className="mt-4 flex-1 overflow-y-auto space-y-3">
          {/* Answer */}
          <div className="p-4 bg-white border border-green-200 rounded-lg shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold px-2 py-0.5 bg-green-100 text-green-700 rounded-full capitalize">
                {result.intent || "general"}
              </span>
              {result.cache_hit && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-600 rounded-full">
                  cached
                </span>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                {result.response_time_ms?.toFixed(0)} ms
              </span>
            </div>
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {result.answer}
            </p>
          </div>

          {/* Confidence bar */}
          <ConfidenceBar score={result.confidence} riskLevel={result.risk_level} />

          {/* Risk chart */}
          <RiskChart riskAssessment={result.risk_assessment} />

          {/* Market chart */}
          <MarketChart marketInsight={result.market_insight} />

          {/* Citations */}
          {result.citations?.length > 0 && (
            <div className="text-xs text-gray-500">
              <span className="font-semibold">Sources: </span>
              {result.citations.join(" · ")}
            </div>
          )}

          {/* Agent trace */}
          <AgentTrace trace={result.reasoning_trace} />
        </div>
      )}
    </div>
  );
}
