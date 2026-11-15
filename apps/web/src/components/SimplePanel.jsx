import { useMissionStore } from "@/store/useMissionStore.js";
import { PLAIN_LAYER_HINT, SIMPLE_CAVEAT, plainClickSummary, plainLayerLabel } from "@/plain.js";

// Simple (layman) right-drawer panel. Replaces the Scientist tabs with a plain
// "what you're looking at" guide, a one-click report button, and a plain-language
// result for the clicked spot — no dB, thresholds, granules or polarization.
export default function SimplePanel({ onOpenReport }) {
  const { activeLayer, clickedPixel, timeline, evidenceCard, narrating } = useMissionStore();
  const summary = plainClickSummary(clickedPixel);
  const hasData = timeline.length > 0;

  return (
    <div className="space-y-4 text-sm">
      <section className="rounded border border-grid bg-orbital p-3">
        <h3 className="mb-1 font-semibold text-cyan">Read the full report</h3>
        <p className="mb-2 text-[13px] text-slate-300">
          A plain-language summary of where water was, how long it stayed, what changed, and which roads
          or settlements to inspect.
        </p>
        <button
          onClick={onOpenReport}
          className="w-full rounded bg-nasa px-3 py-2 text-sm font-semibold text-white hover:bg-nasa/80"
        >
          📊 View analysis report
        </button>
      </section>

      <section>
        <h3 className="mb-1 telemetry-mono text-[11px] uppercase tracking-wide text-cyan">
          You're viewing: {plainLayerLabel(activeLayer)}
        </h3>
        <p className="text-[13px] text-slate-300">{PLAIN_LAYER_HINT[activeLayer] || ""}</p>
      </section>

      <section>
        <h3 className="mb-1 telemetry-mono text-[11px] uppercase tracking-wide text-cyan">This spot</h3>
        {!clickedPixel ? (
          <p className="text-[13px] text-slate-400">
            {hasData
              ? "Tap anywhere inside the highlighted box to see what the radar found there."
              : "No data loaded for this area yet."}
          </p>
        ) : (
          <div className="rounded border border-grid bg-orbital p-3">
            <p className="text-[14px] text-slate-100">{summary}</p>
            {clickedPixel.lat != null && (
              <p className="mt-1 telemetry-mono text-[10px] text-slate-500">
                {clickedPixel.lat.toFixed(4)}°, {clickedPixel.lon.toFixed(4)}°
              </p>
            )}
            {evidenceCard?.narration ? (
              <p className="mt-2 border-t border-grid pt-2 text-[13px] text-slate-200" data-testid="ai-explanation">
                {evidenceCard.narration}
                <span className="mt-1 block text-[10px] italic text-slate-500">Plain-words explanation written by AI ({evidenceCard.narration_model || "LLM"}) from the radar numbers.</span>
              </p>
            ) : narrating ? (
              <p className="mt-2 border-t border-grid pt-2 text-[12px] italic text-slate-400" role="status">Writing a plain explanation…</p>
            ) : null}
          </div>
        )}
      </section>

      <p className="border-t border-grid pt-2 text-[11px] italic text-slate-400">{SIMPLE_CAVEAT}</p>
    </div>
  );
}
