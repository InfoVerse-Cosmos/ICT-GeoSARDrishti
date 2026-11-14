import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
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

import ErrorBoundary from "@/components/ErrorBoundary.jsx";
import SimpleSummary from "@/components/SimpleSummary.jsx";

const RETRY_MS = 5000;
const LandingLayout = lazy(() => import("@/components/landing/LandingLayout.jsx"));

function metaFrom(src) {
  if (!src) return {};
  const keys = [
    "polarization", "single_pol_mode", "track_frame", "fallback_plan", "reference_date",
    "synthetic_test_data", "season_summary", "data_pack_ready",
  ];
  return Object.fromEntries(keys.filter((k) => k in src).map((k) => [k, src[k]]));
}

function MissionApp() {
  const [workspaceTheme] = useState(() => {
    try { return localStorage.getItem("geosar-landing-theme") === "dark" ? "dark" : "light"; }
    catch { return "light"; }
  });
  const { audienceMode, activeAoiId, connection, setAois, setTimeline, setConnection, setFallbackActive } = useMissionStore();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tab, setTab] = useState("metrics"); // metrics | trajectory | exposure
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [uplink, setUplink] = useState({ establishing: true, attempt: 0 });
  const offlineMirror = useRef(null);

  // Boot: health + AOI directory. While the backend is cold-starting we show the uplink
  // banner, serve the bundled offline mirror, and keep retrying (SRS §7.2 rule 3).
  const boot = useCallback(async () => {
    const health = await api.health();
    if (health.status === "unavailable" || health.source_mode === "CLIENT_FALLBACK") {
      if (!offlineMirror.current) offlineMirror.current = await loadFallbackManifest();
      setConnection("OFFLINE");
      if (offlineMirror.current) {
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
    <div data-theme={workspaceTheme} className="mission-workspace flex min-h-full lg:h-full flex-col bg-orbital text-slate-200">
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

      {audienceMode === "simple" && <SimpleSummary compact />}
      <button className="border-b border-grid px-4 py-2 text-left text-sm lg:hidden" aria-expanded={drawerOpen} aria-controls="mission-drawer" onClick={() => setDrawerOpen(!drawerOpen)}>{drawerOpen ? "Close details" : "Open details"}</button>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Center: map + time slider */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-[420px] flex-1 lg:min-h-0">
            <MapWorkspace onPixelInspected={() => { setTab("trajectory"); setDrawerOpen(true); }} />
          </div>
          <MonsoonTimeSlider />
        </main>

        {/* Right telemetry & evidence drawer */}
        <aside id="mission-drawer" className={`${drawerOpen ? "flex" : "hidden"} max-h-[65vh] w-full shrink-0 flex-col border-t border-grid bg-panel lg:flex lg:max-h-none lg:w-[360px] lg:border-l lg:border-t-0 xl:w-[420px]`}>
          {audienceMode === "scientific" && <nav className="flex border-b border-grid text-xs telemetry-mono">
            {[
              ["metrics", "SCENE & VALIDATION"],
              ["trajectory", "PIXEL TRAJECTORY"],
              ["exposure", "INSPECTION LOG"],
            ].map(([id, label]) => (
              <button
                aria-pressed={tab === id}
                key={id}
                onClick={() => setTab(id)}
                className={`flex-1 px-3 py-2 ${
                  tab === id ? "border-b-2 border-cyan bg-nasa/30 font-bold text-cyan" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {label}
              </button>
            ))}
          </nav>}
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <ErrorBoundary key={`${audienceMode}-${tab}`} >
            {audienceMode === "simple" ? <SimpleSummary /> : <>
            {tab === "metrics" && <ScenePanel />}
            {tab === "trajectory" && (
              <>
                <PixelTrajectoryChart />
                <EvidenceCardPanel />
              </>
            )}
            {tab === "exposure" && <ExposureTable />}
            </>}
            </ErrorBoundary>
          </div>
        </aside>
      </div>

      <ProvenanceModal open={provenanceOpen} onClose={() => setProvenanceOpen(false)} />
    </div>
  );
}

export default function App() {
  const [exploring, setExploring] = useState(() => window.location.hash === "#/explore" || window.location.pathname.replace(/\/$/, "").endsWith("/explore"));
  useEffect(() => {
    const navigate = () => {
      setExploring(window.location.hash === "#/explore");
      if (window.location.hash.startsWith("#/")) window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, []);
  return <ErrorBoundary>{exploring ? <MissionApp /> : <Suspense fallback={<div className="p-8 text-slate-300">Loading GeoSAR Drishti…</div>}><LandingLayout /></Suspense>}</ErrorBoundary>;
}
