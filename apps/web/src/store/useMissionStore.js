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

export const useMissionStore = create((set) => ({
  aois: [],
  activeAoiId: "aoi_assam_majuli",
  timeline: [],
  timelineMeta: EMPTY_META,
  activeDate: null,
  compareDate: null, // before/after comparison date (null = off)
  compareMix: 0.5, // 0 = only "before", 1 = only "after"
  activeLayer: "open_water",
  showExposure: true,
  basemap: "dark", // dark | satellite | street | terrain | nasa
  clickedPixel: null, // { lat, lon, ...telemetry }
  evidenceCard: null,
  exposure: null, // { geojson, ranked, ... }
  flyTo: null, // { center: [lon, lat], zoom, ts }
  playing: false,
  connection: "CONNECTING", // LIVE_API | LOCAL_CACHE | OFFLINE | CONNECTING
  fallbackActive: false,

  setAois: (aois) => set({ aois }),
  setActiveAoi: (activeAoiId) =>
    set({ activeAoiId, clickedPixel: null, evidenceCard: null, exposure: null, compareDate: null, playing: false }),
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
