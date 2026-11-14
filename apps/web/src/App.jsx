import { useCallback, useEffect, useRef, useState } from "react";
import { api, loadFallbackManifest } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";
import TopTelemetryBar from "@/components/TopTelemetryBar.jsx";
import MapWorkspace from "@/components/MapWorkspace.jsx";
import MonsoonTimeSlider from "@/components/MonsoonTimeSlider.jsx";
import PixelTrajectoryChart from "@/components/PixelTrajectoryChart.jsx";
import EvidenceCardPanel from "@/components/EvidenceCardPanel.jsx";
import ExposureTable from "@/components/ExposureTable.jsx";
import ProvenanceModal from "@/components/ProvenanceModal.jsx";
import ScenePanel from "@/components/ScenePanel.jsx";

const RETRY_MS = 5000;

function metaFrom(src) {
  if (!src) return {};
  const keys = [
    "polarization", "single_pol_mode", "track_frame", "fallback_plan", "reference_date",
    "synthetic_test_data", "season_summary", "data_pack_ready",
  ];
  return Object.fromEntries(keys.filter((k) => k in src).map((k) => [k, src[k]]));
}

export default function App() {
  const { activeAoiId, connection, setAois, setTimeline, setConnection, setFallbackActive } = useMissionStore();
  const [tab, setTab] = useState("metrics"); // metrics | trajectory | exposure
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [uplink, setUplink] = useState({ establishing: true, attempt: 0 });
  const offlineMirror = useRef(null);

  // Boot: health + AOI directory. While the backend is cold-starting we show the uplink
  // banner, serve the bundled offline mirror, and keep retrying (SRS §7.2 rule 3).
  const boot = useCallback(async () => {
    const health = await api.health();
    if (health.status === "unavailable") {
      if (!offlineMirror.current) offlineMirror.current = await loadFallbackManifest();
      if (offlineMirror.current) {
        setConnection("OFFLINE");
        setAois(offlineMirror.current.aois || []);
      }
      setUplink((u) => ({ establishing: true, attempt: u.attempt + 1 }));
      return false;
    }
    offlineMirror.current = null;
    setConnection(health.source_mode === "LIVE_API" ? "LIVE_API" : "LOCAL_CACHE");
    const aoisRes = await api.listAois();
    setFallbackActive(Boolean(aoisRes.fallback_active));
    setAois(aoisRes.data?.aois || []);
    setUplink({ establishing: false, attempt: 0 });
    return true;
  }, [setAois, setConnection, setFallbackActive]);

  useEffect(() => {
    let timer;
    let cancelled = false;
    const loop = async () => {
      const ok = await boot();
      if (!ok && !cancelled) timer = setTimeout(loop, RETRY_MS);
    };
    loop();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [boot]);

  // Load timeline whenever the AOI (or connection mode) changes.
  useEffect(() => {
    (async () => {
      if (connection === "OFFLINE" && offlineMirror.current) {
        const a = (offlineMirror.current.aois || []).find((x) => x.aoi_id === activeAoiId);
        setTimeline(a?.timeline || [], metaFrom(a));
        return;
      }
      if (connection === "CONNECTING") return;
      const res = await api.timeline(activeAoiId);
      setTimeline(res.data?.timeline || [], metaFrom(res.data));
    })();
  }, [activeAoiId, connection, setTimeline]);

  return (
    <div className="flex h-full flex-col bg-orbital text-slate-200">
      <TopTelemetryBar onOpenProvenance={() => setProvenanceOpen(true)} />
      {uplink.establishing && (
        <div
          role="status"
          className="flex items-center justify-center gap-2 border-b border-grid bg-isro/15 py-1 text-[11px] telemetry-mono text-isro"
        >
          <span className="h-2 w-2 animate-pulse rounded-full bg-isro" />
          ESTABLISHING TELEMETRY UPLINK…
          {uplink.attempt > 0 && (
            <span className="text-slate-400">
              retry #{uplink.attempt} · {connection === "OFFLINE" ? "serving bundled offline mirror" : "waiting for API"}
            </span>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* Center: map + time slider */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <MapWorkspace onPixelInspected={() => setTab("trajectory")} />
          </div>
          <MonsoonTimeSlider />
        </main>

        {/* Right telemetry & evidence drawer */}
        <aside className="flex w-[400px] flex-col border-l border-grid bg-panel">
          <nav className="flex border-b border-grid text-xs telemetry-mono">
            {[
              ["metrics", "SCENE & VALIDATION"],
              ["trajectory", "PIXEL TRAJECTORY"],
              ["exposure", "INSPECTION LOG"],
            ].map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex-1 px-3 py-2 ${
                  tab === id ? "bg-nasa/30 text-cyan" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {tab === "metrics" && <ScenePanel />}
            {tab === "trajectory" && (
              <>
                <PixelTrajectoryChart />
                <EvidenceCardPanel />
              </>
            )}
            {tab === "exposure" && <ExposureTable />}
          </div>
        </aside>
      </div>

      <ProvenanceModal open={provenanceOpen} onClose={() => setProvenanceOpen(false)} />
    </div>
  );
}
