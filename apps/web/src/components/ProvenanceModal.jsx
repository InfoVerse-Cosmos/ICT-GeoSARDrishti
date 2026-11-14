import { useEffect, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// Provenance modal (SRS §4.2, §7.1 /provenance + /nisar/earthdata-live).
export default function ProvenanceModal({ open, onClose }) {
  const { activeAoiId, aois } = useMissionStore();
  const [prov, setProv] = useState(null);
  const [live, setLive] = useState(null);
  const [liveLoading, setLiveLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLive(null);
    (async () => {
      const res = await api.provenance(activeAoiId);
      setProv(res.data || null);
    })();
  }, [open, activeAoiId]);

  if (!open) return null;

  const checkLive = async () => {
    setLiveLoading(true);
    const bounds = aois.find((a) => a.aoi_id === activeAoiId)?.bounds;
    const res = await api.earthdataLive((bounds || [93.9, 26.75, 94.3, 27.05]).join(","), activeAoiId);
    setLive(res);
    setLiveLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Scientific provenance"
        className="max-h-[85vh] w-[640px] overflow-y-auto rounded border border-grid bg-panel p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="telemetry-mono text-sm text-cyan">Scientific Provenance · {activeAoiId}</h2>
          <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        {!prov ? (
          <p className="telemetry-mono text-xs text-slate-500">Loading provenance…</p>
        ) : (
          <div className="space-y-3 text-xs">
            {prov.synthetic_test_data && (
              <p className="rounded border border-alert/60 bg-alert/10 p-2 telemetry-mono text-alert">
                SYNTHETIC TEST DATA — not a NISAR observation.
              </p>
            )}
            <Section title="Stack">
              <span className="telemetry-mono">
                track/frame {prov.track_frame || "—"} · plan {prov.fallback_plan || "—"} · dry reference{" "}
                {prov.reference_date || "—"}
              </span>
            </Section>
            <Section title="OPERA DSWx inter-sensor agreement">
              <span className="telemetry-mono text-cyan">
                {prov.opera_dswx_agreement_pct ?? "—"}% (inter-sensor agreement, not ground-truth accuracy)
              </span>
            </Section>
            <Section title="ΔHH double-bounce parameters">
              <span className="telemetry-mono">
                min ΔHH ≥ {prov.delta_hh_params?.min_delta_hh_db} dB · min ΔRatio ≥ {prov.delta_hh_params?.min_delta_ratio_db} dB
              </span>
            </Section>
            {prov.otsu_thresholds && Object.keys(prov.otsu_thresholds).length > 0 && (
              <Section title="Dynamic Otsu thresholds (per scene)">
                <ul className="telemetry-mono text-slate-300">
                  {Object.entries(prov.otsu_thresholds).map(([d, t]) => (
                    <li key={d}>{d}: τHH {t.hh_db} dB{t.hv_db != null ? ` · τHV ${t.hv_db} dB` : ""}</li>
                  ))}
                </ul>
              </Section>
            )}
            {prov.calibration_check && (
              <Section title="PROVISIONAL → VALIDATED calibration check">
                <span className="telemetry-mono">
                  {prov.calibration_check.provisional_date} → {prov.calibration_check.validated_date}: median{" "}
                  {prov.calibration_check.channel} offset {prov.calibration_check.median_offset_db} dB over{" "}
                  {prov.calibration_check.stable_pixels} stable px{" "}
                  {prov.calibration_check.within_1db ? "(within ±1 dB)" : "(> 1 dB — correct before ΔHH)"}
                </span>
              </Section>
            )}
            {prov.masks && (
              <Section title="Masks">
                <ul className="list-disc pl-4 text-slate-300">
                  {Object.entries(prov.masks).map(([k, v]) => <li key={k}>{k}: {v}</li>)}
                </ul>
              </Section>
            )}
            <Section title="Granules">
              <ul className="break-all telemetry-mono text-slate-300">
                {(prov.granules || []).length === 0 ? <li>— (locked in Phase 1)</li> : prov.granules.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </Section>
            {prov.context_sources?.length > 0 && (
              <Section title="Regional context sources">
                <ul className="list-disc pl-4 text-slate-300">
                  {prov.context_sources.map((s) => <li key={s}>{s}</li>)}
                </ul>
              </Section>
            )}
            <Section title="Limitations">
              <ul className="list-disc space-y-1 pl-4 text-slate-300">
                {(prov.limitations || []).map((l, i) => <li key={i}>{l}</li>)}
              </ul>
            </Section>
            <Section title="Live NASA Earthdata (CMR) check">
              <button
                onClick={checkLive}
                disabled={liveLoading}
                className="rounded border border-grid px-2 py-1 text-cyan hover:bg-grid disabled:opacity-50"
              >
                {liveLoading ? "Querying CMR…" : "Query NASA CMR now"}
              </button>
              {live && (
                <div className="mt-2 telemetry-mono text-[11px] text-slate-300">
                  <div>
                    source: <span className="text-cyan">{live.source_mode}</span> · granules: {live.data?.granule_count ?? 0}
                  </div>
                  {live.warning && <div className="text-isro">{live.warning}</div>}
                  <ul className="mt-1 max-h-32 overflow-y-auto break-all">
                    {(live.data?.granules || []).slice(0, 10).map((g) => (
                      <li key={g.id}>{g.date} · {g.maturity} · {g.id}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="telemetry-mono text-[10px] uppercase tracking-wide text-slate-500">{title}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}
