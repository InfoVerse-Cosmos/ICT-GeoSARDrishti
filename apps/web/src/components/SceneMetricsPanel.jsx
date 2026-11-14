import { useEffect, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// Tab 1 — Scene & Validation Metrics (SRS §4.2 Tab 1):
// area per class, valid-pixel %, OPERA DSWx-S1 inter-sensor agreement %, JRC anomaly.
// Area/pixel metrics come from the per-date manifest entry once Phase 2 fills them;
// agreement + limitations come from /provenance.
export default function SceneMetricsPanel() {
  const { activeAoiId, activeDate, timeline } = useMissionStore();
  const [prov, setProv] = useState(null);

  useEffect(() => {
    (async () => {
      const res = await api.provenance(activeAoiId);
      setProv(res.data || null);
    })();
  }, [activeAoiId]);

  const current = timeline.find((t) => t.date === activeDate) || timeline[timeline.length - 1];
  const metrics = current?.metrics || null; // { open_water_km2, flooded_veg_km2, dry_km2, valid_pixel_pct, jrc_unusual_km2 }

  return (
    <div className="space-y-4 text-sm">
      <div>
        <h3 className="mb-1 telemetry-mono text-xs uppercase tracking-wide text-cyan">Scene Metrics</h3>
        <div className="telemetry-mono text-xs text-slate-400">
          {current ? `${current.date} · ${current.maturity || "PROVISIONAL"}` : "No date selected"}
        </div>
        {metrics ? (
          <table className="mt-2 w-full text-xs telemetry-mono">
            <tbody>
              <AreaRow color="#0284C7" label="Open Water" km2={metrics.open_water_km2} />
              <AreaRow color="#10B981" label="Flooded Vegetation" km2={metrics.flooded_veg_km2} />
              <AreaRow color="#64748B" label="Dry / Other" km2={metrics.dry_km2} />
            </tbody>
          </table>
        ) : (
          <p className="mt-2 telemetry-mono text-xs text-slate-400">
            Per-class area metrics are computed in Phase 2 (scripts/02) and written into the manifest.
          </p>
        )}
        {metrics?.valid_pixel_pct != null && (
          <div className="mt-1 telemetry-mono text-xs text-slate-300">
            Valid pixels: <span className="text-cyan">{metrics.valid_pixel_pct}%</span>
          </div>
        )}
      </div>

      <div>
        <h3 className="mb-1 telemetry-mono text-xs uppercase tracking-wide text-cyan">Validation</h3>
        <Metric
          label="OPERA DSWx-S1 agreement"
          value={prov?.opera_dswx_agreement_pct != null ? `${prov.opera_dswx_agreement_pct}%` : "— (Phase 2)"}
          hint="inter-sensor agreement, not ground-truth accuracy"
        />
        <Metric
          label="JRC 'unusual' open water"
          value={metrics?.jrc_unusual_km2 != null ? `${metrics.jrc_unusual_km2} km²` : "— (Phase 2)"}
          hint="open water where JRC historical occurrence < 20%"
        />
        <Metric
          label="ΔHH double-bounce threshold"
          value={
            prov?.delta_hh_params
              ? `≥ ${prov.delta_hh_params.min_delta_hh_db} dB (ΔRatio ≥ ${prov.delta_hh_params.min_delta_ratio_db} dB)`
              : "≥ 3.0 dB"
          }
        />
      </div>

      {prov?.limitations?.length > 0 && (
        <div>
          <h3 className="mb-1 telemetry-mono text-xs uppercase tracking-wide text-cyan">Limitations</h3>
          <ul className="list-disc space-y-1 pl-4 text-xs text-slate-400">
            {prov.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function AreaRow({ color, label, km2 }) {
  return (
    <tr className="border-t border-grid">
      <td className="py-1">
        <span className="mr-2 inline-block h-2 w-2 rounded-sm align-middle" style={{ backgroundColor: color }} />
        {label}
      </td>
      <td className="py-1 text-right text-slate-200">{km2 != null ? `${km2} km²` : "—"}</td>
    </tr>
  );
}

function Metric({ label, value, hint }) {
  return (
    <div className="mt-1">
      <div className="flex items-baseline justify-between">
        <span className="telemetry-mono text-xs text-slate-400">{label}</span>
        <span className="telemetry-mono text-cyan">{value}</span>
      </div>
      {hint && <div className="text-xs italic text-slate-400">{hint}</div>}
    </div>
  );
}
