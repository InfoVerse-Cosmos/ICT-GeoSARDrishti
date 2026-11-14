import { useMissionStore } from "@/store/useMissionStore.js";

// Top Mission Bar (SRS §4.2.1): NISAR identity, dual-AOI selector, status pills.
export default function TopTelemetryBar({ onOpenProvenance }) {
  const { aois, activeAoiId, setActiveAoi, timeline, activeDate, connection, fallbackActive } =
    useMissionStore();

  const current = timeline.find((t) => t.date === activeDate) || timeline[timeline.length - 1];

  return (
    <header className="flex items-center gap-4 border-b border-grid bg-panel px-4 py-2">
      <div className="flex items-center gap-2">
        <span className="rounded bg-nasa px-2 py-1 text-xs font-bold text-white">NASA–ISRO</span>
        <span className="telemetry-mono text-sm font-semibold text-cyan">NISAR · GeoSAR Drishti</span>
      </div>

      {/* Dual-AOI selector */}
      <select
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

      <div className="flex flex-1 items-center gap-2 text-[11px] telemetry-mono">
        <Pill label={current?.granule_id ? `GRANULE ${current.granule_id}` : "GRANULE —"} />
        <Pill label={current?.track_frame ? `T/F ${current.track_frame}` : "T/F —"} />
        <Pill label={current?.polarization || "HH+HV"} tone="nasa" />
        <Pill
          label={current?.maturity || "PROVISIONAL"}
          tone={current?.maturity === "VALIDATED" ? "cyan" : "isro"}
        />
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

function Pill({ label, tone }) {
  const tones = { nasa: "bg-nasa/40 text-cyan", cyan: "bg-cyan/20 text-cyan", isro: "bg-isro/20 text-isro" };
  return <span className={`rounded px-2 py-0.5 ${tones[tone] || "bg-orbital text-slate-300"}`}>{label}</span>;
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
