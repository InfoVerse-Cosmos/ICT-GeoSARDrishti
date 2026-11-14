import { useEffect, useState } from "react";
import { api, loadFallbackManifest } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";
import TopTelemetryBar from "@/components/TopTelemetryBar.jsx";
import MapWorkspace from "@/components/MapWorkspace.jsx";
import MonsoonTimeSlider from "@/components/MonsoonTimeSlider.jsx";
import PixelTrajectoryChart from "@/components/PixelTrajectoryChart.jsx";
import EvidenceCardPanel from "@/components/EvidenceCardPanel.jsx";
import ExposureTable from "@/components/ExposureTable.jsx";
import ProvenanceModal from "@/components/ProvenanceModal.jsx";

export default function App() {
  const {
    activeAoiId, setAois, setTimeline, setConnection, setFallbackActive,
  } = useMissionStore();
  const [tab, setTab] = useState("metrics"); // metrics | trajectory | exposure
  const [provenanceOpen, setProvenanceOpen] = useState(false);

  // Boot: health + AOI directory (with offline fallback).
  useEffect(() => {
    (async () => {
      const health = await api.health();
      setConnection(health.source_mode === "LIVE_API" ? "LIVE_API" : "LOCAL_CACHE");

      let aoisRes = await api.listAois();
      if (aoisRes.status === "unavailable") {
        const fb = await loadFallbackManifest();
        if (fb) {
          setConnection("OFFLINE");
          setAois(fb.aois || []);
          return;
        }
      }
      setFallbackActive(Boolean(aoisRes.fallback_active));
      setAois(aoisRes.data?.aois || []);
    })();
  }, [setAois, setConnection, setFallbackActive]);

  // Load timeline whenever the active AOI changes.
  useEffect(() => {
    (async () => {
      const res = await api.timeline(activeAoiId);
      setTimeline(res.data?.timeline || []);
    })();
  }, [activeAoiId, setTimeline]);

  return (
    <div className="flex h-full flex-col bg-orbital text-slate-200">
      <TopTelemetryBar onOpenProvenance={() => setProvenanceOpen(true)} />

      <div className="flex min-h-0 flex-1">
        {/* Center: map + time slider */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <MapWorkspace />
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
            {tab === "metrics" && <EvidenceCardPanel />}
            {tab === "trajectory" && (
              <>
                <PixelTrajectoryChart />
                <EvidenceCardPanel compact />
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
