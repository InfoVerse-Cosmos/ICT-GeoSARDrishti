import { useEffect } from "react";
import { useMissionStore } from "@/store/useMissionStore.js";

// Bottom monsoon time-series dock (SRS §4.2.3): animated playback, ticks, maturity
// badges, and the explicit 27 Jul – 10 Aug acquisition-gap hatch band.
const GAP_START = "2026-07-27";
const GAP_END = "2026-08-10";
const SEASON_START = "2026-06-01";
const SEASON_END = "2026-11-30";
const STEP_MS = 1400;

const dayOf = (d) => new Date(`${d}T00:00:00Z`).getTime();
const pct = (d) => ((dayOf(d) - dayOf(SEASON_START)) / (dayOf(SEASON_END) - dayOf(SEASON_START))) * 100;

export default function MonsoonTimeSlider() {
  const { timeline, activeDate, setActiveDate, playing, setPlaying, timelineMeta } = useMissionStore();

  // Animation: advance one acquisition every STEP_MS, loop at the end.
  useEffect(() => {
    if (!playing || timeline.length < 2) return undefined;
    const id = setInterval(() => {
      const { timeline: tl, activeDate: cur } = useMissionStore.getState();
      const i = tl.findIndex((t) => t.date === cur);
      setActiveDate(tl[(i + 1) % tl.length].date);
    }, STEP_MS);
    return () => clearInterval(id);
  }, [playing, timeline, setActiveDate]);

  return (
    <div className="border-t border-grid bg-panel px-4 py-3">
      <div className="mb-1 flex items-center justify-between gap-2 text-[11px] telemetry-mono text-slate-400">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPlaying(!playing)}
            disabled={timeline.length < 2}
            aria-label={playing ? "Pause monsoon animation" : "Play monsoon animation"}
            className="rounded border border-grid px-2 py-0.5 text-isro hover:bg-grid disabled:opacity-40"
          >
            {playing ? "❚❚ PAUSE" : "▶ PLAY"}
          </button>
          <span>MONSOON ACQUISITION TIMELINE · JUN–NOV 2026</span>
          {timelineMeta.track_frame && <span className="text-slate-500">TRACK/FRAME {timelineMeta.track_frame}</span>}
        </div>
        <span className="acq-gap rounded px-2 py-0.5 text-slate-200">SENSOR ACQUISITION GAP (27 JUL – 10 AUG)</span>
      </div>

      {/* Season ruler: June–November with the hatched gap band and acquisition ticks. */}
      <div className="relative mb-2 h-3 rounded bg-orbital" aria-hidden="true">
        <div
          className="acq-gap absolute top-0 h-3"
          style={{ left: `${pct(GAP_START)}%`, width: `${pct(GAP_END) - pct(GAP_START)}%` }}
        />
        {timeline.map((t) => (
          <div
            key={t.date}
            className={`absolute top-0 h-3 w-0.5 ${t.date === activeDate ? "bg-isro" : t.maturity === "VALIDATED" ? "bg-cyan" : "bg-slate-400"}`}
            style={{ left: `${pct(t.date)}%` }}
          />
        ))}
        {["JUN", "JUL", "AUG", "SEP", "OCT", "NOV"].map((mth, i) => (
          <span key={mth} className="absolute -bottom-0 text-[8px] text-slate-600" style={{ left: `${(i / 6) * 100}%` }}>
            {mth}
          </span>
        ))}
      </div>

      <div className="relative flex flex-wrap items-center gap-1">
        {timeline.length === 0 && (
          <span className="telemetry-mono text-xs text-slate-500">No acquisitions loaded.</span>
        )}
        {timeline.map((t) => {
          const inGap = t.date > GAP_START && t.date < GAP_END;
          const active = t.date === activeDate;
          return (
            <button
              key={t.date}
              onClick={() => {
                setPlaying(false);
                setActiveDate(t.date);
              }}
              title={`${t.date} · ${t.maturity || "PROVISIONAL"}`}
              className={`flex flex-col items-center rounded px-2 py-1 text-[10px] telemetry-mono transition ${
                active ? "bg-isro/30 text-isro" : "text-slate-400 hover:bg-grid"
              } ${inGap ? "acq-gap" : ""}`}
            >
              <span
                className={`mb-1 h-2 w-2 rounded-full ${
                  t.maturity === "VALIDATED" ? "bg-cyan" : "bg-isro"
                }`}
              />
              {t.date.slice(5)}
              <span className="text-[8px] text-slate-500">{(t.maturity || "PROVISIONAL").slice(0, 4)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
