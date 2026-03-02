import axios from "axios";

const api = axios.create({
  baseURL: "/",
  headers: { "Content-Type": "application/json" },
  timeout: 60000,
});

/**
 * POST /api/v1/query — run the AgroMind agent pipeline.
 * @param {{ query: string, district?: string, crop?: string, language?: string, session_id?: string }} payload
 */
export async function postQuery(payload) {
  const { data } = await api.post("/api/v1/query", payload);
  return data;
}

/**
 * GET /health — aggregate health status for all backing services.
 */
export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}
