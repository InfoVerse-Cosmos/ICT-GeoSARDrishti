import { useEffect, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// Provenance modal (SRS §4.2.4 ProvenanceModal, §7.1 /provenance).
export default function ProvenanceModal({ open, onClose }) {
  const { activeAoiId } = useMissionStore();
  const [prov, setProv] = useState(null);

  useEffect(() => {
    if (!open) return;
    (async () => {
      const res = await api.provenance(activeAoiId);
      setProv(res.data || null);
    })();
  }, [open, activeAoiId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[80vh] w-[560px] overflow-y-auto rounded border border-grid bg-panel p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="telemetry-mono text-sm text-cyan">Scientific Provenance · {activeAoiId}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        {!prov ? (
          <p className="telemetry-mono text-xs text-slate-500">Loading provenance…</p>
        ) : (
          <div className="space-y-3 text-xs">
            <Section title="OPERA DSWx-S1 inter-sensor agreement">
              <span className="telemetry-mono text-cyan">
                {prov.opera_dswx_agreement_pct ?? "—"}% (inter-sensor agreement, not ground-truth accuracy)
              </span>
            </Section>
            <Section title="ΔHH double-bounce parameters">
              <span className="telemetry-mono">
                min ΔHH ≥ {prov.delta_hh_params?.min_delta_hh_db} dB · min ΔRatio ≥ {prov.delta_hh_params?.min_delta_ratio_db} dB
              </span>
            </Section>
            <Section title="Granules">
              <ul className="telemetry-mono text-slate-300">
                {(prov.granules || []).length === 0 ? <li>— (locked in Phase 1)</li> : prov.granules.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </Section>
            <Section title="Limitations">
              <ul className="list-disc space-y-1 pl-4 text-slate-300">
                {(prov.limitations || []).map((l, i) => <li key={i}>{l}</li>)}
              </ul>
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
