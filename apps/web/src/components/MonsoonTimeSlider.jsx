import { useMissionStore } from "@/store/useMissionStore.js";

// Bottom monsoon time-series dock (SRS §4.2.3): ticks, maturity badges,
// and the explicit 27 Jul – 10 Aug acquisition-gap hatch band.
const GAP_START = "2026-07-27";
const GAP_END = "2026-08-10";

export default function MonsoonTimeSlider() {
  const { timeline, activeDate, setActiveDate } = useMissionStore();

  return (
    <div className="border-t border-grid bg-panel px-4 py-3">
      <div className="mb-1 flex items-center justify-between text-[11px] telemetry-mono text-slate-400">
        <span>MONSOON ACQUISITION TIMELINE · JUN–NOV 2026</span>
        <span className="acq-gap rounded px-2 py-0.5 text-slate-200">
          SENSOR ACQUISITION GAP (27 JUL – 10 AUG)
        </span>
      </div>

      <div className="relative flex items-center gap-1">
        {timeline.length === 0 && (
          <span className="telemetry-mono text-xs text-slate-500">No acquisitions loaded.</span>
        )}
        {timeline.map((t) => {
          const inGap = t.date > GAP_START && t.date < GAP_END;
          const active = t.date === activeDate;
          return (
            <button
              key={t.date}
              onClick={() => setActiveDate(t.date)}
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
            </button>
          );
        })}
      </div>
    </div>
  );
}
