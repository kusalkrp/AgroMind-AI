import React, { useEffect, useState } from "react";
import QueryPanel from "../components/QueryPanel.jsx";
import DistrictMap from "../components/DistrictMap.jsx";
import { getHealth } from "../api/client.js";

/**
 * Dashboard — two-column layout:
 *   Left  60%: QueryPanel (query form + results)
 *   Right 40%: DistrictMap (interactive Sri Lanka map)
 *
 * Nav bar shows title + live health dot (green=ok, red=degraded/down).
 */
export default function Dashboard() {
  const [healthStatus, setHealthStatus] = useState("unknown"); // ok | degraded | unknown
  const [selectedDistrict, setSelectedDistrict] = useState("");

  // Poll health every 30 s
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

  const dotColor =
    healthStatus === "ok"
      ? "bg-green-400"
      : healthStatus === "degraded"
      ? "bg-red-400"
      : "bg-yellow-400";

  return (
    <div className="flex flex-col h-screen">
      {/* ── Nav bar ── */}
      <nav className="bg-green-700 text-white px-6 py-3 flex items-center justify-between shadow">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold tracking-tight">AgroMind AI</span>
          <span className="text-green-200 text-sm hidden sm:block">
            Sri Lanka Agricultural Intelligence
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`w-3 h-3 rounded-full ${dotColor} shadow-sm`}
            title={`API status: ${healthStatus}`}
          />
          <span className="text-green-100 capitalize">{healthStatus}</span>
        </div>
      </nav>

      {/* ── Main content ── */}
      <main className="flex flex-1 overflow-hidden">
        {/* Left: Query panel (60%) */}
        <section className="w-3/5 flex flex-col p-5 overflow-y-auto border-r border-gray-200 bg-white">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            Ask your agricultural question
          </h2>
          <QueryPanel
            selectedDistrict={selectedDistrict}
            onDistrictChange={setSelectedDistrict}
          />
        </section>

        {/* Right: District map (40%) */}
        <section className="w-2/5 flex flex-col p-5 bg-gray-50">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            District Map
            {selectedDistrict && (
              <span className="ml-2 text-sm font-normal text-green-600">
                — {selectedDistrict}
              </span>
            )}
          </h2>
          <div className="flex-1 rounded-lg overflow-hidden shadow border border-gray-200">
            <DistrictMap
              selectedDistrict={selectedDistrict}
              onDistrictClick={setSelectedDistrict}
            />
          </div>
          <p className="text-xs text-gray-400 mt-2 text-center">
            Click a district pin to auto-select it in the query form.
          </p>
        </section>
      </main>
    </div>
  );
}
