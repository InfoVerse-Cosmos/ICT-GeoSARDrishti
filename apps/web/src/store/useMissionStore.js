// Global mission state: active AOI, selected date, active layer, clicked pixel.
import { create } from "zustand";

export const LAYERS = [
  { id: "open_water", label: "Open Water", color: "#0284C7", dated: true },
  { id: "flooded_veg", label: "Flooded Vegetation", color: "#10B981", dated: true },
  { id: "hydroperiod", label: "Hydroperiod (M/N)", color: "#F59E0B", dated: false },
  { id: "gmm_regimes", label: "GMM Regimes", color: "#38BDF8", dated: false },
  { id: "jrc_anomaly", label: "JRC Anomaly", color: "#EF4444", dated: false },
  { id: "context_layers", label: "Regional Context", color: "#A78BFA", dated: false },
];

export const REGIME_LEGEND = [
  ["Permanent River / Deep Channel", "#1E3A8A"],
  ["Seasonal Open Floodplain / Beel", "#0284C7"],
  ["Seasonally Flooded Canopy / Tall Grassland", "#10B981"],
  ["Seasonal Paddy-Like Inundation Cycle", "#F59E0B"],
  ["Stable Dry Upland / Levee", "#94A3B8"],
];

export const EMPTY_META = {
  polarization: "HH+HV",
  single_pol_mode: false,
  track_frame: null,
  fallback_plan: null,
  reference_date: null,
  synthetic_test_data: false,
  season_summary: null,
  data_pack_ready: false,
};

// Dual-audience view (Simple = layman default, Scientist = full console).
// Persisted so a reload keeps the chosen audience.
const AUDIENCE_KEY = "geosar.audienceMode";
function readAudience() {
  try {
    const v = localStorage.getItem(AUDIENCE_KEY);
    return v === "scientist" || v === "scientific" ? "scientific" : "simple";
  } catch {
    return "simple";
  }
}
function persistAudience(mode) {
  try {
    localStorage.setItem(AUDIENCE_KEY, mode);
  } catch {
    /* ignore (private mode / SSR) */
  }
}
const INITIAL_AUDIENCE = readAudience();

export const useMissionStore = create((set) => ({
  layerOpacity: 0.85,
  evidenceLoading: false,
  aois: [],
  audienceMode: INITIAL_AUDIENCE, // simple | scientific
  activeAoiId: "", // set from the AOI list the API actually serves (never a hardcoded area)
  timeline: [],
  timelineMeta: EMPTY_META,
  activeDate: null,
  compareDate: null, // before/after comparison date (null = off)
  compareMix: 0.5, // 0 = only "before", 1 = only "after"
  activeLayer: "open_water",
  showExposure: true,
  // Simple mode defaults to the satellite backdrop (recognisable to anyone);
  // Scientist mode keeps the original dark telemetry basemap.
  basemap: INITIAL_AUDIENCE === "simple" ? "satellite" : "dark", // dark | satellite | street | terrain | nasa
  clickedPixel: null, // { lat, lon, ...telemetry }
  evidenceCard: null,
  exposure: null, // { geojson, ranked, ... }
  flyTo: null, // { center: [lon, lat], zoom, ts }
  playing: false,
  connection: "CONNECTING", // LIVE_API | LOCAL_CACHE | OFFLINE | CONNECTING
  fallbackActive: false,

  setLayerOpacity: (layerOpacity) => set({ layerOpacity }),
  setEvidenceLoading: (evidenceLoading) => set({ evidenceLoading }),
  // Only areas the backend really has data for are listed; keep the selection valid.
  setAois: (aois) =>
    set((s) => ({
      aois,
      activeAoiId: aois.some((a) => a.aoi_id === s.activeAoiId) ? s.activeAoiId : aois[0]?.aoi_id ?? "",
    })),
  // Switching audience also swaps the default basemap and resets Simple mode to a
  // plain result layer so a layman never lands on a scientist-only overlay.
  setAudienceMode: (audienceMode) =>
    set((s) => {
      audienceMode = audienceMode === "scientist" ? "scientific" : audienceMode;
      persistAudience(audienceMode);
      const next = { audienceMode, compareDate: null };
      if (audienceMode === "simple") {
        if (s.basemap === "dark") next.basemap = "satellite";
        if (!["open_water", "flooded_veg", "hydroperiod"].includes(s.activeLayer)) {
          next.activeLayer = "open_water";
        }
      } else if (s.basemap === "satellite") {
        next.basemap = "dark";
      }
      return next;
    }),
  setActiveAoi: (activeAoiId) =>
    set({ activeAoiId, evidenceLoading: false, clickedPixel: null, evidenceCard: null, exposure: null, compareDate: null, playing: false }),
  setTimeline: (timeline, meta = {}) =>
    set({
      timeline,
      timelineMeta: { ...EMPTY_META, ...meta },
      activeDate: timeline.length ? timeline[timeline.length - 1].date : null,
    }),
  setActiveDate: (activeDate) => set({ activeDate }),
  setCompareDate: (compareDate) => set({ compareDate }),
  setCompareMix: (compareMix) => set({ compareMix }),
  setActiveLayer: (activeLayer) => set({ activeLayer }),
  setShowExposure: (showExposure) => set({ showExposure }),
  setBasemap: (basemap) => set({ basemap }),
  setClickedPixel: (clickedPixel) => set({ clickedPixel }),
  setEvidenceCard: (evidenceCard) => set({ evidenceCard }),
  setExposure: (exposure) => set({ exposure }),
  setFlyTo: (center, zoom = 13) => set({ flyTo: { center, zoom, ts: Date.now() } }),
  setPlaying: (playing) => set({ playing }),
  setConnection: (connection) => set({ connection }),
  setFallbackActive: (fallbackActive) => set({ fallbackActive }),
}));
