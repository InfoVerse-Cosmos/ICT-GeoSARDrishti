// Global mission state: active AOI, selected date, active layer, clicked pixel.
import { create } from "zustand";

export const LAYERS = [
  { id: "open_water", label: "Open Water", color: "#0284C7" },
  { id: "flooded_veg", label: "Flooded Vegetation", color: "#10B981" },
  { id: "hydroperiod", label: "Hydroperiod (M/N)", color: "#F59E0B" },
  { id: "gmm_regimes", label: "GMM Regimes", color: "#38BDF8" },
  { id: "jrc_anomaly", label: "JRC Anomaly", color: "#EF4444" },
];

export const useMissionStore = create((set) => ({
  aois: [],
  activeAoiId: "aoi_assam_majuli",
  timeline: [],
  activeDate: null,
  activeLayer: "open_water",
  clickedPixel: null, // { lat, lon, ...telemetry }
  evidenceCard: null,
  connection: "CONNECTING", // LIVE_API | LOCAL_CACHE | OFFLINE | CONNECTING
  fallbackActive: false,

  setAois: (aois) => set({ aois }),
  setActiveAoi: (activeAoiId) => set({ activeAoiId, clickedPixel: null, evidenceCard: null }),
  setTimeline: (timeline) =>
    set({ timeline, activeDate: timeline.length ? timeline[timeline.length - 1].date : null }),
  setActiveDate: (activeDate) => set({ activeDate }),
  setActiveLayer: (activeLayer) => set({ activeLayer }),
  setClickedPixel: (clickedPixel) => set({ clickedPixel }),
  setEvidenceCard: (evidenceCard) => set({ evidenceCard }),
  setConnection: (connection) => set({ connection }),
  setFallbackActive: (fallbackActive) => set({ fallbackActive }),
}));
