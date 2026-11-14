// Fetch wrapper with timeout, retry, and envelope-safe parsing (SRS §7.2, §7.3).
// The backend always returns the standard envelope, so the UI never reads undefined.

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_V1 = `${API_BASE}/api/v1`;

const EMPTY_ENVELOPE = {
  status: "unavailable",
  aoi_id: null,
  source_mode: "CLIENT_FALLBACK",
  fallback_active: true,
  warning: "Backend unreachable. Showing bundled fallback.",
  data: null,
};

async function request(path, { method = "GET", body, timeoutMs = 6000, retries = 1 } = {}) {
  const url = `${API_V1}${path}`;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      clearTimeout(timer);
      if (attempt === retries) {
        // Final failure: try bundled static fallback for the AOI directory.
        return { ...EMPTY_ENVELOPE, warning: `${EMPTY_ENVELOPE.warning} (${err.message})` };
      }
      await new Promise((r) => setTimeout(r, 800));
    }
  }
  return EMPTY_ENVELOPE;
}

export async function loadFallbackManifest() {
  try {
    const res = await fetch("/fallback_data/manifest.json");
    return await res.json();
  } catch {
    return null;
  }
}

export const api = {
  base: API_BASE,
  health: () => request("/health"),
  listAois: () => request("/aois"),
  timeline: (aoiId) => request(`/aois/${aoiId}/timeline`),
  earthdataLive: (bbox, aoiId) =>
    request(
      `/nisar/earthdata-live?bbox=${encodeURIComponent(bbox)}${aoiId ? `&aoi_id=${encodeURIComponent(aoiId)}` : ""}`,
      { timeoutMs: 8000, retries: 0 },
    ),
  context: (aoiId) => request(`/aois/${aoiId}/context`),
  layerPngUrl: (aoiId, layerId, date) =>
    `${API_V1}/layers/${aoiId}/${layerId}.png${date ? `?date=${date}` : ""}`,
  inspect: (aoiId, lat, lon) => request(`/aois/${aoiId}/inspect?lat=${lat}&lon=${lon}`),
  evidenceCard: (payload) => request("/evidence-card", { method: "POST", body: payload, timeoutMs: 4000 }),
  exposure: (aoiId) => request(`/aois/${aoiId}/exposure`),
  provenance: (aoiId) => request(`/aois/${aoiId}/provenance`),
};
