import React, { useState, useRef, useEffect } from "react";
import { postQuery } from "../api/client.js";
import AgentTrace from "./AgentTrace.jsx";
import ConfidenceBar from "./ConfidenceBar.jsx";
import MarketChart from "./MarketChart.jsx";
import RiskChart from "./RiskChart.jsx";
import DistrictMap from "./DistrictMap.jsx";
import { marked } from "marked";
import DOMPurify from "dompurify";
import "./QueryPanel.css";

const DISTRICTS = [
  "Colombo", "Kandy", "Galle", "Jaffna", "Anuradhapura",
  "Polonnaruwa", "Kurunegala", "Ratnapura", "Matara", "Badulla",
];

const CROPS = ["paddy", "maize", "tea", "rubber", "coconut", "vegetables", "banana"];

export default function QueryPanel({ healthStatus }) {
  const [query, setQuery] = useState("");
  const [district, setDistrict] = useState("");
  const [crop, setCrop] = useState("");
  const [language, setLanguage] = useState("english");
  
  const [loading, setLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!query.trim()) return;

    const currentQuery = query.trim();
    const tempId = Date.now();
    setChatHistory(prev => [{
       id: tempId,
       query: currentQuery, 
       timestamp: new Date(), 
       loading: true 
    }, ...prev]);
    
    setQuery("");
    setLoading(true);

    try {
      const start = performance.now();
      const data = await postQuery({
        query: currentQuery,
        district: district || undefined,
        crop: crop || undefined,
        language,
      });
      const end = performance.now();
      
      data.time_ms = Math.round(end - start);

      setChatHistory(prev => prev.map(item => 
        item.id === tempId ? { ...item, data, loading: false } : item
      ));
    } catch (err) {
      setChatHistory(prev => prev.map(item => 
        item.id === tempId ? { ...item, error: err.message || "Request failed", loading: false } : item
      ));
    } finally {
      setLoading(false);
    }
  }

  function renderMarkdown(text) {
    if (!text) return { __html: "" };
    try {
      const html = marked.parse(text);
      return { __html: DOMPurify.sanitize(html) };
    } catch {
      return { __html: text };
    }
  }

  // Attempt to parse confidence score, which might be `confidence` or `confidence_score`
  function getScore(data) {
    if (!data) return 0;
    return typeof data.confidence === 'number' ? data.confidence : (data.confidence_score || 0);
  }

  return (
    <div className="query-panel-root">
       <div className="config-grid">
          <div className="card">
             <div className="card-header pb-0">
               <h3 className="card-title">Settings</h3>
             </div>
             <form onSubmit={handleSubmit} className="settings-form">
                <div className="form-group">
                   <label>Your Question</label>
                   <textarea 
                     value={query} 
                     onChange={e => setQuery(e.target.value)}
                     className="dark-input custom-scrollbar" 
                     placeholder="e.g. Current paddy risks..." 
                     rows={2} 
                     onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }}
                   />
                </div>
                
                <div className="form-group">
                   <label>Target District</label>
                   <select value={district} onChange={e => setDistrict(e.target.value)} className="dark-input">
                       <option value="">Island Wide</option>
                       {DISTRICTS.map(d => <option key={d} value={d}>{d}</option>)}
                   </select>
                </div>

                <div className="form-row">
                   <div className="form-group half">
                      <label>Crop Type</label>
                      <select value={crop} onChange={e => setCrop(e.target.value)} className="dark-input">
                         <option value="">Any</option>
                         {CROPS.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                   </div>
                   <div className="form-group half">
                      <label>Language</label>
                      <select value={language} onChange={e => setLanguage(e.target.value)} className="dark-input">
                         <option value="english">English</option>
                         <option value="sinhala">Sinhala</option>
                         <option value="tamil">Tamil</option>
                      </select>
                   </div>
                </div>

                <div className="form-action">
                   <button type="submit" disabled={loading || !query.trim()} className="indigo-btn">
                      {loading ? "Analyzing..." : "Generate Analysis"}
                   </button>
                </div>
             </form>
          </div>

          <div className="card">
             <div className="card-header border-b-0 pb-0">
               <h3 className="card-title">Context Summary</h3>
             </div>
             <div className="summary-content">
                 <div className="summary-stats">
                    <div className="stat-row">
                       <span className="stat-label">Active Region</span>
                       <span className="stat-value">{district || "island-wide"}</span>
                    </div>
                    <div className="stat-row">
                       <span className="stat-label">Target Crop</span>
                       <span className="stat-value">{crop || "multiple"}</span>
                    </div>
                    <div className="stat-row highlight-row">
                       <span className="stat-label blue-col">System Health</span>
                       <span className={`stat-value ${healthStatus === 'ok' ? 'blue-val' : ''}`} style={healthStatus !== 'ok' ? {color: "var(--risk-high)"} : {}}>
                          {healthStatus === 'ok' ? 'Online' : 'Degraded'}
                       </span>
                    </div>
                 </div>

                 <div className="map-embed-wrapper">
                    <DistrictMap selectedDistrict={district} onDistrictClick={setDistrict} />
                 </div>
             </div>
          </div>
       </div>

       <div className="card mt-2rem">
          <div className="card-header inline-header">
             <span className="header-icon">📅</span>
             <h3 className="card-title inline-title">Analyzed Queries</h3>
          </div>
          
          <div className="results-list">
             {chatHistory.length === 0 ? (
                <div className="empty-results">No queries analyzed yet.</div>
             ) : (
                chatHistory.map((item) => (
                   <div key={item.id} className="result-item">
                      <div className="result-row-top">
                         <div className="result-title-group">
                            <h4>{item.query}</h4>
                            <span className="result-meta">
                               {item.timestamp.toLocaleDateString()} · {item.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                            </span>
                         </div>
                         
                         <div className="result-stats-group">
                            <span className="result-time">{item.loading ? "Running..." : `${item.data?.time_ms || 0} ms`}</span>
                            <span className="cost-pill">
                               {item.loading ? "--" : (item.error ? "Error" : `${Math.round(getScore(item.data)*100)}% Conf`)}
                            </span>
                         </div>
                      </div>

                      {!item.loading && !item.error && item.data && (
                         <div className="result-content">
                            <div 
                               className="answer-text markdown-body" 
                               dangerouslySetInnerHTML={renderMarkdown(item.data.answer)} 
                            />
                            
                            <div className="chart-grid">
                               {item.data.risk_assessment && <RiskChart riskAssessment={item.data.risk_assessment} />}
                               {item.data.market_insight && <MarketChart marketInsight={item.data.market_insight} />}
                            </div>

                            <ConfidenceBar score={getScore(item.data)} riskLevel={item.data.risk_level} />
                            <AgentTrace trace={item.data.reasoning_trace} />
                            
                            {item.data.citations?.length > 0 && (
                              <div className="citations-block">
                                <strong>Sources:</strong> {item.data.citations.join(" · ")}
                              </div>
                            )}
                         </div>
                      )}

                      {!item.loading && item.error && (
                         <div className="result-content">
                            <p className="error-text">⚠️ {item.error}</p>
                         </div>
                      )}
                   </div>
                ))
             )}
          </div>
       </div>
    </div>
  );
}
