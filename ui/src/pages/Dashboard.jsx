import React, { useEffect, useState } from "react";
import QueryPanel from "../components/QueryPanel.jsx";
import { getHealth } from "../api/client.js";
import "./Dashboard.css"; 

export default function Dashboard() {
  const [healthStatus, setHealthStatus] = useState("unknown");

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const data = await getHealth();
        if (!cancelled) setHealthStatus(data.status || "ok");
      } catch {
        if (!cancelled) setHealthStatus("degraded");
      }
    }

    checkHealth();
    const id = setInterval(checkHealth, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="dashboard-container">
      {/* Top Nav */}
      <nav className="top-nav">
        <div className="nav-profile">
          <div className="nav-avatar">A</div>
          <div className="nav-info">
            <span className="nav-name">Demo User</span>
            <span className="nav-status">demo@example.com</span>
          </div>
        </div>
        <button className="nav-disconnect">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Disconnect
        </button>
      </nav>

      {/* Hero Header */}
      <header className="hero-section">
        <div className="hero-icon-box">
          <span className="hero-icon" style={{color: "var(--accent-primary)"}}>🌾</span>
        </div>
        <h1 className="hero-title">
          The Agricultural Intelligence<br/>Dashboard
        </h1>
        <p className="hero-subtitle">
          Revenge for crop uncertainty. Calculate the exact risks of your farming decisions and generate intelligence reports to soothe your soul.
        </p>
      </header>

      {/* Main Content Component */ }
      <main className="main-container">
        <QueryPanel healthStatus={healthStatus} />
      </main>
    </div>
  );
}
