// Plain-language helpers for Simple (layman) mode. No SAR jargon — no dB, Otsu,
// ΔHH, polarization or track/frame. Every wording keeps the project's honest
// framing: a radar-derived water indication for inspection, never a flood claim.

export const SIMPLE_CAVEAT =
  "Radar-based water indication for inspection — not a confirmed flood, depth, or damage.";

// Layers a layman sees, in plain words. Scientist mode keeps the full LAYERS list.
export const SIMPLE_LAYER_IDS = ["open_water", "flooded_veg", "hydroperiod"];

export const PLAIN_LAYER_LABELS = {
  open_water: "Open water",
  flooded_veg: "Water hidden under plants",
  hydroperiod: "Repeatedly wet areas",
};

export const PLAIN_LAYER_HINT = {
  open_water: "Clearly visible water on the latest pass.",
  flooded_veg: "Water the radar sees beneath trees and crops.",
  hydroperiod: "Darker = wet on more satellite passes.",
};

export function plainLayerLabel(id) {
  return PLAIN_LAYER_LABELS[id] || id;
}

// One-line "what happened here" for a clicked pixel, from the inspect telemetry.
export function plainClickSummary(cp) {
  if (!cp) return null;
  if (cp.status === "outside_aoi") {
    return "That point is outside the studied area. Click inside the highlighted box.";
  }
  if (cp.status === "loading") return "Reading the satellite history for this spot…";

  const hp = cp.hydroperiod || {};
  const m = hp.m;
  const n = hp.n;
  if (n == null || n === 0) {
    return "No clear NISAR water reading at this spot (outside the radar swath or masked).";
  }
  const passes = n === 1 ? "pass" : "passes";
  if (!m) {
    return `This spot stayed dry in all ${n} satellite ${passes}.`;
  }

  let tail;
  if (m === n && n > 1) tail = "water in every pass — a consistently wet area.";
  else if (m >= 3) tail = "a frequently-wet area.";
  else tail = "an occasionally-wet area.";

  let line = `Water seen in ${m} of ${n} satellite ${passes} — ${tail}`;
  if (hp.m_flooded_veg) line += " Some of it was hidden under plants.";
  return line;
}
