[1mdiff --git a/apps/web/src/App.jsx b/apps/web/src/App.jsx[m
[1mindex c01e539..209152e 100644[m
[1m--- a/apps/web/src/App.jsx[m
[1m+++ b/apps/web/src/App.jsx[m
[36m@@ -10,6 +10,9 @@[m [mimport ExposureTable from "@/components/ExposureTable.jsx";[m
 import ProvenanceModal from "@/components/ProvenanceModal.jsx";[m
 import ScenePanel from "@/components/ScenePanel.jsx";[m
 [m
[32m+[m[32mimport ErrorBoundary from "@/components/ErrorBoundary.jsx";[m
[32m+[m[32mimport SimpleSummary from "@/components/SimpleSummary.jsx";[m
[32m+[m
 const RETRY_MS = 5000;[m
 [m
 function metaFrom(src) {[m
[36m@@ -21,8 +24,9 @@[m [mfunction metaFrom(src) {[m
   return Object.fromEntries(keys.filter((k) => k in src).map((k) => [k, src[k]]));[m
 }[m
 [m
[31m-export default function App() {[m
[31m-  const { activeAoiId, connection, setAois, setTimeline, setConnection, setFallbackActive } = useMissionStore();[m
[32m+[m[32mfunction MissionApp() {[m
[32m+[m[32m  const { audienceMode, activeAoiId, connection, setAois, setTimeline, setConnection, setFallbackActive } = useMissionStore();[m
[32m+[m[32m  const [drawerOpen, setDrawerOpen] = useState(false);[m
   const [tab, setTab] = useState("metrics"); // metrics | trajectory | exposure[m
   const [provenanceOpen, setProvenanceOpen] = useState(false);[m
   const [uplink, setUplink] = useState({ establishing: true, attempt: 0 });[m
[36m@@ -32,10 +36,10 @@[m [mexport default function App() {[m
   // banner, serve the bundled offline mirror, and keep retrying (SRS §7.2 rule 3).[m
   const boot = useCallback(async () => {[m
     const health = await api.health();[m
[31m-    if (health.status === "unavailable") {[m
[32m+[m[32m    if (health.status === "unavailable" || health.source_mode === "CLIENT_FALLBACK") {[m
       if (!offlineMirror.current) offlineMirror.current = await loadFallbackManifest();[m
[32m+[m[32m      setConnection("OFFLINE");[m
       if (offlineMirror.current) {[m
[31m-        setConnection("OFFLINE");[m
         setAois(offlineMirror.current.aois || []);[m
       }[m
       setUplink((u) => ({ establishing: true, attempt: u.attempt + 1 }));[m
[36m@@ -79,7 +83,7 @@[m [mexport default function App() {[m
   }, [activeAoiId, connection, setTimeline]);[m
 [m
   return ([m
[31m-    <div className="flex h-full flex-col bg-orbital text-slate-200">[m
[32m+[m[32m    <div className="flex min-h-full lg:h-full flex-col bg-orbital text-slate-200">[m
       <TopTelemetryBar onOpenProvenance={() => setProvenanceOpen(true)} />[m
       {uplink.establishing && ([m
         <div[m
[36m@@ -96,35 +100,40 @@[m [mexport default function App() {[m
         </div>[m
       )}[m
 [m
[31m-      <div className="flex min-h-0 flex-1">[m
[32m+[m[32m      {audienceMode === "simple" && <SimpleSummary compact />}[m
[32m+[m[32m      <button className="border-b border-grid px-4 py-2 text-left text-sm lg:hidden" aria-expanded={drawerOpen} aria-controls="mission-drawer" onClick={() => setDrawerOpen(!drawerOpen)}>{drawerOpen ? "Close details" : "Open details"}</button>[m
[32m+[m[32m      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">[m
         {/* Center: map + time slider */}[m
         <main className="flex min-w-0 flex-1 flex-col">[m
[31m-          <div className="min-h-0 flex-1">[m
[31m-            <MapWorkspace onPixelInspected={() => setTab("trajectory")} />[m
[32m+[m[32m          <div className="min-h-[420px] flex-1 lg:min-h-0">[m
[32m+[m[32m            <MapWorkspace onPixelInspected={() => { setTab("trajectory"); setDrawerOpen(true); }} />[m
           </div>[m
           <MonsoonTimeSlider />[m
         </main>[m
 [m
         {/* Right telemetry & evidence drawer */}[m
[31m-        <aside className="flex w-[400px] flex-col border-l border-grid bg-panel">[m
[31m-          <nav className="flex border-b border-grid text-xs telemetry-mono">[m
[32m+[m[32m        <aside id="mission-drawer" className={`${drawerOpen ? "flex" : "hidden"} max-h-[65vh] w-full shrink-0 flex-col border-t border-grid bg-panel lg:flex lg:max-h-none lg:w-[360px] lg:border-l lg:border-t-0 xl:w-[420px]`}>[m
[32m+[m[32m          {audienceMode === "scientific" && <nav className="flex border-b border-grid text-xs telemetry-mono">[m
             {[[m
               ["metrics", "SCENE & VALIDATION"],[m
               ["trajectory", "PIXEL TRAJECTORY"],[m
               ["exposure", "INSPECTION LOG"],[m
             ].map(([id, label]) => ([m
               <button[m
[32m+[m[32m                aria-pressed={tab === id}[m
                 key={id}[m
                 onClick={() => setTab(id)}[m
                 className={`flex-1 px-3 py-2 ${[m
[31m-                  tab === id ? "bg-nasa/30 text-cyan" : "text-slate-400 hover:text-slate-200"[m
[32m+[m[32m                  tab === id ? "border-b-2 border-cyan bg-nasa/30 font-bold text-cyan" : "text-slate-400 hover:text-slate-200"[m
                 }`}[m
               >[m
                 {label}[m
               </button>[m
             ))}[m
[31m-          </nav>[m
[32m+[m[32m          </nav>}[m
           <div className="min-h-0 flex-1 overflow-y-auto p-3">[m
[32m+[m[32m            <ErrorBoundary key={`${audienceMode}-${tab}`} >[m
[32m+[m[32m            {audienceMode === "simple" ? <SimpleSummary /> : <>[m
             {tab === "metrics" && <ScenePanel />}[m
             {tab === "trajectory" && ([m
               <>[m
[36m@@ -133,6 +142,8 @@[m [mexport default function App() {[m
               </>[m
             )}[m
             {tab === "exposure" && <ExposureTable />}[m
[32m+[m[32m            </>}[m
[32m+[m[32m            </ErrorBoundary>[m
           </div>[m
         </aside>[m
       </div>[m
[36m@@ -141,3 +152,5 @@[m [mexport default function App() {[m
     </div>[m
   );[m
 }[m
[32m+[m
[32m+[m[32mexport default function App() { return <ErrorBoundary><MissionApp /></ErrorBoundary>; }[m
