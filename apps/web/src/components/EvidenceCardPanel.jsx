import { useMissionStore } from "@/store/useMissionStore.js";

// Plain-language Radar Evidence Card (SRS §4.2 Tab, §7.3).
export default function EvidenceCardPanel({ compact = false }) {
  const { clickedPixel, evidenceCard } = useMissionStore();

  if (!clickedPixel) {
    return (
      <div className="telemetry-mono text-xs text-slate-500">
        Click a location on the map to generate its radar evidence card.
      </div>
    );
  }
  if (clickedPixel.status === "outside_aoi") {
    return <div className="telemetry-mono text-xs text-isro">{clickedPixel.warning}</div>;
  }

  const card = evidenceCard;

  return (
    <div className="space-y-2 text-sm">
      {!compact && (
        <h3 className="telemetry-mono text-xs uppercase tracking-wide text-cyan">Radar Evidence Card</h3>
      )}
      {!card ? (
        <p className="telemetry-mono text-xs text-slate-500">
          {clickedPixel.warning || "Evidence card unavailable (data pack pending Phase 2)."}
        </p>
      ) : (
        <div className="space-y-2 rounded border border-grid bg-orbital p-3">
          <Row k="Location" v={card.location} mono />
          <Row k="Hydrological Regime (GMM)" v={card.hydrological_regime} />
          <Row k="Monsoon Persistence" v={card.monsoon_persistence} />
          <Row k="Radar Physics" v={card.radar_physics_evidence} />
          <Row k="Land Cover & Context" v={card.land_cover_context} />
          <Row k="Confidence" v={card.confidence} />
          {card.narration && <Row k="Narration" v={card.narration} />}
          <p className="border-t border-grid pt-2 text-[11px] italic text-slate-400">{card.caveat}</p>
          <span className="telemetry-mono text-[10px] text-slate-500">
            mode: {card.mode}
          </span>
        </div>
      )}
    </div>
  );
}

function Row({ k, v, mono }) {
  if (v === null || v === undefined) return null;
  return (
    <div>
      <div className="telemetry-mono text-[10px] uppercase tracking-wide text-slate-500">{k}</div>
      <div className={mono ? "telemetry-mono text-cyan" : "text-slate-200"}>{v}</div>
    </div>
  );
}
