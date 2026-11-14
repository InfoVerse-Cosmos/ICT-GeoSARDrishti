import { useEffect, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// One-click Analysis Report shown in-place (SRS §4.2). Plain-language summary for
// the current AOI, grounded strictly in backend numbers (hydroperiod, class areas,
// before/after change, exposure) with the honest caveat and a provenance footer.
export default function ReportModal({ open, onClose }) {
  const { activeAoiId, audienceMode } = useMissionStore();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setReport(null);
    setLoading(true);
    (async () => {
      const res = await api.report(activeAoiId);
      setReport(res.data || null);
      setLoading(false);
    })();
  }, [open, activeAoiId]);

  if (!open) return null;

  const scientist = audienceMode === "scientific" || audienceMode === "scientist";
  const r = report;
  const hp = r?.hydroperiod;
  const change = r?.change;
  const exposure = r?.exposure;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label="Analysis report"
        className="max-h-[88vh] w-[720px] overflow-y-auto rounded-lg border border-grid bg-panel p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-cyan">Analysis Report</h2>
            <p className="text-sm text-slate-300">{r?.name || activeAoiId}</p>
            {r?.date_range?.first && (
              <p className="text-[11px] telemetry-mono text-slate-500">
                NISAR observations {r.date_range.first} → {r.date_range.last} · {r.dates?.length || 0} passes
              </p>
            )}
          </div>
          <button onClick={onClose} aria-label="Close report" className="text-slate-400 hover:text-slate-200">
            ✕
          </button>
        </div>

        {r?.synthetic_test_data && (
          <p className="mb-3 rounded border border-alert/60 bg-alert/10 p-2 telemetry-mono text-xs text-alert">
            SYNTHETIC TEST DATA — pipeline test pack, not a real NISAR observation.
          </p>
        )}

        {loading && <p className="telemetry-mono text-sm text-slate-400 animate-pulse">Building report…</p>}

        {!loading && r && !r.data_pack_ready && (
          <p className="rounded border border-grid bg-orbital p-3 text-sm text-slate-300">
            {r.message || "The full data pack for this area has not been generated yet."}
          </p>
        )}

        {!loading && r && r.data_pack_ready && (
          <div className="space-y-4 text-sm text-slate-200">
            {/* Where water was */}
            <Section title="Where water was">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Stat label="Water seen at least once" value={hp.ever_wet_km2} unit="km²" tone="text-water" />
                <Stat label="Open water (ever)" value={hp.ever_open_water_km2} unit="km²" tone="text-water" />
                <Stat label="Water under plants (ever)" value={hp.ever_flooded_veg_km2} unit="km²" tone="text-fveg" />
              </div>
            </Section>

            {/* Hydroperiod */}
            <Section title="How long water stayed (hydroperiod)">
              <p className="mb-2 text-slate-300">
                Persistence is counted as <strong>M of N</strong> valid NISAR observations, not days flooded.
                Each location was seen {hp.n_min === hp.n_max ? hp.n_max : `${hp.n_min}–${hp.n_max}`} time
                {hp.n_max === 1 ? "" : "s"}.
              </p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Stat
                  label={`Wet on ${hp.repeatedly_wet_threshold}+ passes`}
                  value={hp.repeatedly_wet_km2}
                  unit="km²"
                  tone="text-paddy"
                />
                <Stat label="Wet on every pass (M=N)" value={hp.wet_every_observation_km2} unit="km²" tone="text-cyan" />
                <Stat label="Most passes wet at one spot" value={hp.max_wet_observations} unit={`/ ${hp.n_max}`} />
              </div>
            </Section>

            {/* What changed */}
            <Section title="What changed between passes">
              {change?.primary ? (
                <>
                  <p>
                    Open water went from{" "}
                    <span className="telemetry-mono text-water">{change.primary.before_open_water_km2} km²</span> on{" "}
                    {change.primary.before_date} to{" "}
                    <span className="telemetry-mono text-water">{change.primary.after_open_water_km2} km²</span> on{" "}
                    {change.primary.after_date} (
                    <span className={change.primary.delta_open_water_km2 <= 0 ? "text-fveg" : "text-alert"}>
                      {change.primary.delta_open_water_km2 > 0 ? "+" : ""}
                      {change.primary.delta_open_water_km2} km²
                    </span>
                    ).
                  </p>
                  <p className="mt-1 text-[11px] italic text-slate-400">{change.note}</p>
                </>
              ) : (
                <p className="text-slate-400">{change?.note}</p>
              )}
            </Section>

            {/* Inspection candidates */}
            <Section title="Roads & settlements to inspect">
              {exposure?.count > 0 ? (
                <>
                  <p className="mb-1 text-slate-300">
                    {exposure.count} road/settlement candidate{exposure.count === 1 ? "" : "s"} wet on{" "}
                    {exposure.threshold}+ passes — inspection candidates only, never a damage claim.
                  </p>
                  <ul className="list-disc space-y-0.5 pl-5 text-[13px]">
                    {exposure.top.map((e, i) => (
                      <li key={i}>
                        {e.name} <span className="text-slate-500">({e.kind})</span> —{" "}
                        <span className="telemetry-mono text-alert">
                          wet {e.wet_observations}/{e.total_observations}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-slate-400">
                  No road/settlement inspection candidates were extracted for this area in this run
                  {exposure?.available ? "" : " (OpenStreetMap lookup was not available offline)"}. This is
                  honestly reported as no data, not as "nothing is at risk".
                </p>
              )}
            </Section>

            {scientist && r.classes?.regimes_km2 && Object.keys(r.classes.regimes_km2).length > 0 && (
              <Section title="Hydrological regimes (GMM, unsupervised)">
                <ul className="space-y-0.5 text-[13px]">
                  {Object.entries(r.classes.regimes_km2).map(([name, km2]) => (
                    <li key={name} className="flex justify-between">
                      <span className="text-slate-300">{name}</span>
                      <span className="telemetry-mono">{km2 ?? "—"} km²</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {scientist && r.classes?.per_date?.length > 0 && (
              <Section title="Open water per observation">
                <table className="w-full text-left text-[12px] telemetry-mono">
                  <thead className="text-slate-500">
                    <tr>
                      <th className="py-1">Date</th>
                      <th>Track/Frame</th>
                      <th>Maturity</th>
                      <th className="text-right">Open water</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.classes.per_date.map((d) => (
                      <tr key={d.date} className="border-t border-grid">
                        <td className="py-1">{d.date}</td>
                        <td>{d.track_frame || "—"}</td>
                        <td>{d.maturity || "—"}</td>
                        <td className="text-right text-water">{d.open_water_km2 ?? "—"} km²</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-1 text-[10px] text-slate-500">{r.classes.per_date[0]?.method}</p>
              </Section>
            )}

            {/* Honest caveat */}
            <p className="rounded border border-isro/40 bg-isro/10 p-2 text-[12px] italic text-slate-200">
              {r.caveat}
            </p>

            {/* Provenance footer */}
            <ProvenanceFooter prov={r.provenance} dates={r.dates} scientist={scientist} />
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h3 className="mb-1 telemetry-mono text-[11px] uppercase tracking-wide text-cyan">{title}</h3>
      {children}
    </section>
  );
}

function Stat({ label, value, unit = "", tone = "text-slate-100" }) {
  return (
    <div className="rounded border border-grid bg-orbital px-2 py-1">
      <div className="text-[10px] text-slate-500">{label}</div>
      <div className={`telemetry-mono text-base ${tone}`}>
        {value ?? "—"} <span className="text-[11px] text-slate-400">{value != null && unit}</span>
      </div>
    </div>
  );
}

function ProvenanceFooter({ prov, dates, scientist }) {
  if (!prov) return null;
  return (
    <footer className="border-t border-grid pt-2 text-[11px] text-slate-400">
      <div className="telemetry-mono text-[10px] uppercase tracking-wide text-slate-500">Provenance</div>
      <p className="mt-1">
        NISAR L2 GCOV · track/frame {prov.track_frame || "—"} · dry reference {prov.reference_date || "—"} ·{" "}
        {dates?.length || 0} dates ({dates?.[0]} → {dates?.[dates.length - 1]})
      </p>
      {scientist && prov.delta_hh_params && (
        <p className="mt-1 telemetry-mono">
          thresholds: ΔHH ≥ {prov.delta_hh_params.min_delta_hh_db} dB · ΔRatio ≥{" "}
          {prov.delta_hh_params.min_delta_ratio_db} dB
          {prov.opera_dswx_agreement_pct != null
            ? ` · OPERA agreement ${prov.opera_dswx_agreement_pct}% (inter-sensor, not ground-truth)`
            : ""}
        </p>
      )}
      {prov.granules?.length > 0 && (
        <details className="mt-1">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-300">
            {prov.granules.length} source granule{prov.granules.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 break-all telemetry-mono text-[10px] text-slate-500">
            {prov.granules.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </details>
      )}
    </footer>
  );
}
