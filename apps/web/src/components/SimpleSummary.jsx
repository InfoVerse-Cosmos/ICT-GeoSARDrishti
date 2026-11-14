import { useMissionStore } from "@/store/useMissionStore.js";

export default function SimpleSummary({ compact = false }) {
  const { timeline, activeDate, timelineMeta, clickedPixel, evidenceCard, evidenceLoading } = useMissionStore();
  const metrics = timeline.find((entry) => entry.date === activeDate)?.metrics;
  const summary = metrics?.open_water_km2 != null
    ? `On ${activeDate}, radar indicated ${metrics.open_water_km2} km² of open water in this area.`
    : "Water results are not available yet for the selected date.";
  if (compact) return <p className="border-b border-grid bg-panel px-4 py-2 text-sm" role="status">{summary}</p>;
  return <section className="space-y-3 text-sm"><h2 className="font-semibold">Water overview</h2><p>{summary}</p>
    {timelineMeta.synthetic_test_data && <p className="text-isro">SYNTHETIC TEST DATA — not a NISAR observation.</p>}
    <p>Blue shows water. Orange shows newly-flooded indications in places where water is historically uncommon; it does not establish when flooding began.</p>
    <p className="text-slate-300">This is a radar-derived indication for field inspection, not a confirmed flood-depth measurement. Inspection candidates only — never a damage claim.</p>
    <h3 className="font-semibold">Selected location</h3>
    {clickedPixel?.status === "loading" || evidenceLoading ? <div role="status" className="animate-pulse rounded bg-grid p-3">Loading location results...</div> : !clickedPixel ? <p>Select a location on the map or enter coordinates to inspect it.</p> : <>
      <p className="telemetry-mono">{clickedPixel.lat?.toFixed(4)}, {clickedPixel.lon?.toFixed(4)}</p>
      {clickedPixel.warning && <p>{clickedPixel.warning}</p>}
      {evidenceCard ? <>{evidenceCard.data_notice && <p className="text-isro">{evidenceCard.data_notice}</p>}<p>{evidenceCard.monsoon_persistence}</p><p>Confidence: {evidenceCard.confidence}</p><p>{evidenceCard.caveat}</p></> : <p>Location results are unavailable.</p>}
    </>}
  </section>;
}
