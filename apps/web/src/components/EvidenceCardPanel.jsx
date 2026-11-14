import { useMissionStore } from "@/store/useMissionStore.js";

// Plain-language Radar Evidence Card (SRS §4.2 Tab 2, §7.3).
export default function EvidenceCardPanel() {
  const { clickedPixel, evidenceCard } = useMissionStore();

  if (!clickedPixel) {
    return (
      <div className="telemetry-mono text-xs text-slate-500">
        Click a location on the map to generate its radar evidence card.
      </div>
    );
  }
  if (clickedPixel.status === "loading") {
    return <div className="telemetry-mono text-xs text-slate-400 animate-pulse">Sampling NISAR pixel stack…</div>;
  }
  if (clickedPixel.status === "outside_aoi") {
    return <div className="telemetry-mono text-xs text-isro">{clickedPixel.warning}</div>;
  }

  const card = evidenceCard;

  return (
    <div className="space-y-2 text-sm">
      <h3 className="telemetry-mono text-xs uppercase tracking-wide text-cyan">Radar Evidence Card</h3>
      {!card ? (
        <p className="telemetry-mono text-xs text-slate-500">
          {clickedPixel.warning || "Evidence card unavailable (data pack pending Phase 2)."}
        </p>
      ) : (
        <div className="space-y-2 rounded border border-grid bg-orbital p-3" data-testid="evidence-card">
          {card.data_notice && <p className="telemetry-mono text-[11px] text-alert">{card.data_notice}</p>}
          <Row k="Location" v={card.location} mono />
          <Row k="Hydrological Regime (GMM)" v={card.hydrological_regime} />
          <Row k="Monsoon Persistence (Hydroperiod)" v={card.monsoon_persistence} />
          <Row k="Radar Physics Evidence" v={card.radar_physics_evidence} />
          <Row k="Land Cover & Historical Context" v={card.land_cover_context} />
          <Row k="Confidence" v={card.confidence} />
          {card.narration && <Row k={`Plain-language narration (AI: ${card.narration_model || "LLM"}, numbers from radar pack)`} v={card.narration} />}
          <p className="border-t border-grid pt-2 text-[11px] italic text-slate-400">{card.caveat}</p>
          <span className="telemetry-mono text-[10px] text-slate-500">
            {card.mode === "llm_grounded"
              ? `explained by AI (${card.narration_model || "LLM"}) · every number computed from NISAR`
              : "explained by built-in physics template · AI narrator off or unavailable, numbers identical"}
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
