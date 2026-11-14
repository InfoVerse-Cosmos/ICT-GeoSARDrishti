import { useMissionStore } from "@/store/useMissionStore.js";

// Top Mission Bar (SRS §4.2.1): NISAR identity, dual-AOI selector, status pills.
export default function TopTelemetryBar({ onOpenProvenance }) {
  const { aois, activeAoiId, setActiveAoi, timeline, activeDate, connection, fallbackActive, timelineMeta, audienceMode, setAudienceMode } =
    useMissionStore();

  const current = timeline.find((t) => t.date === activeDate) || timeline[timeline.length - 1];
  const pol = current?.polarization || timelineMeta.polarization || "HH+HV";
  const singlePol = timelineMeta.single_pol_mode || pol === "HH";

  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-grid bg-panel px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="rounded bg-nasa px-2 py-1 text-xs font-bold text-white">NASA–ISRO</span>
        <span className="telemetry-mono text-sm font-semibold text-cyan">NISAR · GeoSAR Drishti</span>
      </div>

      <div className="flex gap-1" role="group" aria-label="Audience mode">
        {["simple", "scientific"].map((mode) => <button key={mode} aria-pressed={audienceMode === mode} onClick={() => setAudienceMode(mode)} className={`rounded border px-2 py-1 text-xs ${audienceMode === mode ? "border-cyan font-bold text-cyan" : "border-grid text-slate-300"}`}>{mode === "simple" ? "Simple" : "Scientific"}</button>)}
      </div>
      {/* Dual-AOI selector */}
      <select
        aria-label="Area of interest"
        value={activeAoiId}
        onChange={(e) => setActiveAoi(e.target.value)}
        className="rounded border border-grid bg-orbital px-2 py-1 text-xs telemetry-mono"
      >
        {aois.map((a) => (
          <option key={a.aoi_id} value={a.aoi_id}>
            {a.aoi_id === "aoi_assam_majuli" ? "Majuli–Kaziranga [Assam]" : "Kanhan–Pench [Nagpur]"}
          </option>
        ))}
      </select>

      <div className="flex flex-1 flex-wrap items-center gap-2 text-[11px] telemetry-mono">
        {audienceMode === "scientific" && <>
        <Pill
          label={current?.granule_id ? `GRANULE ${shortGranule(current.granule_id)}` : "GRANULE —"}
          title={current?.granule_id}
        />
        <Pill label={current?.track_frame ? `T/F ${current.track_frame}` : "T/F —"} />
        <Pill label={singlePol ? "SINGLE-POL HH" : pol} tone={singlePol ? "isro" : "nasa"} />
        </>}
        <Pill
          label={current?.maturity || "PROVISIONAL"}
          tone={current?.maturity === "VALIDATED" ? "cyan" : "isro"}
        />
        {audienceMode === "scientific" && timelineMeta.fallback_plan && <Pill label={`PLAN ${timelineMeta.fallback_plan}`} title="SRS §3.3 fallback ladder" />}
        {timelineMeta.synthetic_test_data && <Pill label="SYNTHETIC TEST DATA" tone="alert" />}
      </div>

      <ConnectionPill connection={connection} fallbackActive={fallbackActive} />
      <button
        onClick={onOpenProvenance}
        className="rounded border border-grid px-2 py-1 text-xs text-slate-300 hover:text-cyan"
      >
        Provenance
      </button>
    </header>
  );
}

// Real granule IDs are ~100 chars; keep the identifying middle part in the pill.
function shortGranule(id) {
  if (!id || id.length <= 28) return id;
  const m = id.match(/GCOV_(\d{3}_\d{3}_[AD]_\d{3}).*?_(\d{8})T/);
  return m ? `${m[1]} · ${m[2]}` : `${id.slice(0, 24)}…`;
}

function Pill({ label, tone, title }) {
  const tones = {
    nasa: "bg-nasa/40 text-cyan",
    cyan: "bg-cyan/20 text-cyan",
    isro: "bg-isro/20 text-isro",
    alert: "bg-alert/20 text-alert",
  };
  return (
    <span title={title} className={`rounded px-2 py-0.5 ${tones[tone] || "bg-orbital text-slate-300"}`}>
      {label}
    </span>
  );
}

function ConnectionPill({ connection, fallbackActive }) {
  const map = {
    LIVE_API: ["LIVE API", "bg-emerald-600/30 text-emerald-300"],
    LOCAL_CACHE: ["LOCAL CACHE", "bg-cyan/20 text-cyan"],
    OFFLINE: ["OFFLINE MIRROR", "bg-isro/20 text-isro"],
    CONNECTING: ["ESTABLISHING UPLINK…", "bg-slate-700 text-slate-300 animate-pulse"],
  };
  const [label, cls] = map[connection] || map.CONNECTING;
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] telemetry-mono ${cls}`}>
      {label}
      {fallbackActive && connection !== "OFFLINE" ? " · FALLBACK" : ""}
    </span>
  );
}
