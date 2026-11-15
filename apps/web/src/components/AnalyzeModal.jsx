import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// "Analyse a new area": choose a place (click on the map, use my GPS location, or type coordinates) and a date
// range; the backend streams ONLY that window of the NISAR granules from NASA Earthdata Cloud (no 7 GB downloads),
// builds the pack, and the new area appears in the list.
const MAX_SPAN = 0.6;
const SIZES = { small: [0.1, 0.075, "Small (~22 x 17 km)"], medium: [0.2, 0.15, "Medium (~44 x 33 km)"], large: [0.275, 0.225, "Large (~60 x 50 km)"] };
const fmt = (n) => Number(n).toFixed(3);

function boxAround([lon, lat], size) {
  const [hw, hh] = SIZES[size];
  return { w: fmt(lon - hw), s: fmt(lat - hh), e: fmt(lon + hw), n: fmt(lat + hh) };
}

function etaText(sec) {
  if (sec == null) return "estimating time left…";
  if (sec <= 20) return "finishing up…";
  if (sec < 90) return "about 1 minute left";
  return `about ${Math.round(sec / 60)} minutes left`;
}

export default function AnalyzeModal({ open, onClose }) {
  const { mapBounds, pickedPoint, pickedBox, setPickedPoint, setPickMode, setAnalyzeBox, setFlyTo, setAois, setActiveAoi } = useMissionStore();
  const [box, setBox] = useState({ w: "", s: "", e: "", n: "" });
  const [size, setSize] = useState("medium");
  const [start, setStart] = useState("2026-07-01");
  const [end, setEnd] = useState("2026-11-30");
  const [name, setName] = useState("");
  const [info, setInfo] = useState(null);
  const [job, setJob] = useState(null);
  const [eta, setEta] = useState(null); // { value, at }
  const [left, setLeft] = useState(null);
  const [error, setError] = useState(null);
  const [note, setNote] = useState(null);
  const [query, setQuery] = useState("");
  const [places, setPlaces] = useState(null);
  const [searching, setSearching] = useState(false);
  const timer = useRef(null);
  const keepNote = useRef(false); // GPS / search set their own note; do not overwrite it with the generic one

  useEffect(() => {
    if (!open) return;
    setError(null);
    (async () => {
      const res = await api.analyzeInfo();
      setInfo(res.data || null);
      if (res.data?.running_job) poll(res.data.running_job);
    })();
    return () => clearTimeout(timer.current);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // A point was chosen on the map (or by GPS): build the area around it.
  useEffect(() => {
    if (!pickedPoint) return;
    setBox(boxAround(pickedPoint, size));
    if (keepNote.current) { keepNote.current = false; return; }
    setNote(`Area centred on ${pickedPoint[1].toFixed(3)}, ${pickedPoint[0].toFixed(3)}. Change the size or drag the map and pick again.`);
  }, [pickedPoint, size]);

  // A rectangle was dragged on the map.
  useEffect(() => {
    if (!pickedBox) return;
    const [w, s, e, n] = pickedBox;
    setBox({ w: fmt(w), s: fmt(s), e: fmt(e), n: fmt(n) });
    const km = ((e - w) * 111 * Math.cos(((s + n) / 2) * Math.PI / 180)).toFixed(0);
    setNote(`Area drawn on the map (about ${km} x ${((n - s) * 111).toFixed(0)} km). Drag again to redraw.`);
  }, [pickedBox]);

  // Live preview rectangle on the map while the dialog is open.
  useEffect(() => {
    const bbox = [box.w, box.s, box.e, box.n].map(Number);
    if (open && bbox.every(Number.isFinite) && box.w !== "") setAnalyzeBox(bbox);
    else setAnalyzeBox(null);
  }, [box, open, setAnalyzeBox]);

  // Countdown: re-baseline on every server estimate, tick down every second in between.
  useEffect(() => {
    if (!eta) return setLeft(null);
    const tick = () => setLeft(Math.max(0, eta.value - (Date.now() - eta.at) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [eta]);

  const poll = (id) => {
    clearTimeout(timer.current);
    const tickPoll = async () => {
      const res = await api.analyzeStatus(id);
      if (!res.data) return;
      setJob(res.data);
      setEta(res.data.eta_s == null ? null : { value: res.data.eta_s, at: Date.now() });
      if (res.data.status === "running") timer.current = setTimeout(tickPoll, 3000);
      else if (res.data.status === "done") await finish(res.data.aoi_id);
    };
    tickPoll();
  };

  const finish = async (aoiId) => {
    const list = await api.listAois();
    setAois(list.data?.aois || []);
    setActiveAoi(aoiId);
  };

  const search = async () => {
    setError(null);
    if (query.trim().length < 2) return;
    setSearching(true);
    const res = await api.geocode(query.trim());
    setSearching(false);
    const list = res.data?.results || [];
    setPlaces(list);
    if (!list.length) setError(res.warning || "No place found.");
  };

  const choosePlace = (p) => {
    const pt = [p.lon, p.lat];
    keepNote.current = true;
    setPickedPoint(pt);
    setFlyTo(pt, 10);
    setPlaces(null);
    setNote(`Area centred on ${p.name.split(",").slice(0, 2).join(",")}.`);
  };

  const pickOnMap = () => {
    setPickMode(true); // MapWorkspace shows the banner + crosshair; the next map click comes back here
    onClose();
  };

  const useMyLocation = () => {
    setError(null);
    if (!navigator.geolocation) return setError("This browser cannot share your location. Pick a place on the map instead.");
    setNote("Asking your browser for your location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const pt = [pos.coords.longitude, pos.coords.latitude];
        keepNote.current = true;
        setPickedPoint(pt);
        setFlyTo(pt, 9);
        setNote(`Using your location (accuracy about ${Math.round(pos.coords.accuracy)} m). Area centred on it.`);
      },
      (err) => {
        setNote(null);
        setError(err.code === 1 ? "Location permission was denied. Allow it in the browser address bar, or pick a place on the map." : "Could not get your location. Pick a place on the map instead.");
      },
      { enableHighAccuracy: false, timeout: 12000 },
    );
  };

  const useMapView = () => {
    if (!mapBounds) return;
    const [w, s, e, n] = mapBounds;
    setPickedPoint([(w + e) / 2, (s + n) / 2]);
  };

  const stopJob = async () => {
    if (!job?.job_id) return;
    clearTimeout(timer.current);
    const res = await api.analyzeStop(job.job_id);
    if (res.data) { setJob(res.data); setEta(null); }
  };

  const begin = async () => {
    setError(null);
    const bbox = [box.w, box.s, box.e, box.n].map(Number);
    if (bbox.some((v) => !Number.isFinite(v)) || box.w === "") return setError("Choose the area first: pick it on the map, use your location, or type coordinates.");
    const res = await api.analyzeStart({ bbox, start, end, name: name.trim() || null });
    if (!res.data || ["invalid_request", "no_token", "disabled"].includes(res.status)) return setError(res.warning || "Could not start.");
    setJob(res.data);
    poll(res.data.job_id);
  };

  if (!open) return null;
  const running = job?.status === "running";
  const stopped = job?.status === "cancelled";
  const btn = "rounded border border-grid px-3 py-1 text-sm hover:text-cyan disabled:opacity-50";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end bg-black/25 p-4 pt-20" onClick={onClose}>
      <div role="dialog" aria-label="Analyse a new area" className="max-h-[84vh] w-[440px] max-w-full overflow-y-auto rounded-lg border border-grid bg-panel p-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-2 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-cyan">Analyse a new area</h2>
            <p className="text-sm text-slate-300">Choose a place and a date range. We stream only that window of the NISAR radar data from NASA: no huge downloads.</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-slate-400 hover:text-slate-200">✕</button>
        </div>

        {info && info.enabled === false && (
          <p className="mb-3 rounded border border-isro/50 bg-isro/10 p-2 text-sm text-isro">Analysing new areas only works when the app runs on your own computer (it needs the local pipeline). It is switched off on this server.</p>
        )}
        {info && info.enabled !== false && !info.token_configured && (
          <p className="mb-3 rounded border border-isro/50 bg-isro/10 p-2 text-sm text-isro">NASA Earthdata token missing. Add <code>EARTHDATA_TOKEN</code> to <code>services/api/.env</code> (urs.earthdata.nasa.gov, Generate Token) and restart the backend.</p>
        )}

        <div className="space-y-3 text-sm">
          <div className="text-xs uppercase tracking-wide text-slate-400">1. Where?</div>
          <form className="flex gap-2" onSubmit={(ev) => { ev.preventDefault(); search(); }}>
            <input aria-label="Search a place" value={query} disabled={running} onChange={(ev) => setQuery(ev.target.value)} placeholder="Search a place, e.g. Kedarnath, Guwahati, Kosi river" className="min-w-0 flex-1 rounded border border-grid bg-orbital px-2 py-1 text-sm text-slate-200" />
            <button type="submit" disabled={running || searching} className={btn}>{searching ? "…" : "Search"}</button>
          </form>
          {places && places.length > 0 && (
            <ul className="max-h-40 overflow-y-auto rounded border border-grid text-xs" aria-label="Place results">
              {places.map((p, i) => (
                <li key={i}><button type="button" onClick={() => choosePlace(p)} className="block w-full px-2 py-1 text-left hover:bg-grid">{p.name}</button></li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <button onClick={pickOnMap} disabled={running} className={`${btn} border-cyan/60 text-cyan`}>📍 Draw on map</button>
            <button onClick={useMyLocation} disabled={running} className={btn}>◎ Use my location</button>
            <button onClick={useMapView} disabled={!mapBounds || running} className={btn}>Centre of map view</button>
          </div>
          <label className="block text-xs text-slate-400">Area size
            <select aria-label="Area size" value={size} disabled={running} onChange={(ev) => setSize(ev.target.value)} className="mt-1 w-full rounded border border-grid bg-orbital px-2 py-1 text-sm text-slate-200">
              {Object.entries(SIZES).map(([k, v]) => <option key={k} value={k}>{v[2]}</option>)}
            </select>
          </label>
          {note && <p className="text-xs text-slate-400">{note}</p>}
          <div className="grid grid-cols-4 gap-2">
            {[["w", "West"], ["s", "South"], ["e", "East"], ["n", "North"]].map(([k, label]) => (
              <label key={k} className="text-xs text-slate-400">{label}
                <input aria-label={label} type="number" step="any" disabled={running} value={box[k]} onChange={(ev) => setBox({ ...box, [k]: ev.target.value })} className="mt-1 w-full rounded border border-grid bg-orbital px-1 py-1 text-xs text-slate-200" />
              </label>
            ))}
          </div>

          <div className="text-xs uppercase tracking-wide text-slate-400">2. Which dates?</div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-400">From
              <input aria-label="From date" type="date" disabled={running} value={start} onChange={(ev) => setStart(ev.target.value)} className="mt-1 w-full rounded border border-grid bg-orbital px-2 py-1 text-sm text-slate-200" />
            </label>
            <label className="text-xs text-slate-400">To
              <input aria-label="To date" type="date" disabled={running} value={end} onChange={(ev) => setEnd(ev.target.value)} className="mt-1 w-full rounded border border-grid bg-orbital px-2 py-1 text-sm text-slate-200" />
            </label>
          </div>
          <p className="text-xs text-slate-500">A longer range gives more satellite passes (one every ~12 days) and a better dry reference, but takes longer (about 3 minutes per pass).</p>
          <label className="block text-xs text-slate-400">Name (optional)
            <input aria-label="Area name" type="text" disabled={running} value={name} onChange={(ev) => setName(ev.target.value)} maxLength={80} placeholder="e.g. Brahmaputra bend" className="mt-1 w-full rounded border border-grid bg-orbital px-2 py-1 text-sm text-slate-200" />
          </label>
          {error && <p role="alert" className="rounded border border-alert/50 bg-alert/10 p-2 text-alert">{error}</p>}
          <button onClick={begin} disabled={running || (info && (info.enabled === false || !info.token_configured))} className="rounded bg-nasa px-4 py-2 font-semibold text-white hover:bg-nasa/80 disabled:opacity-50">{running ? "Analysing…" : "Start analysis"}</button>
        </div>

        {job && (
          <div className="mt-4 space-y-2 rounded border border-grid bg-orbital p-3 text-sm" role="status">
            <div className="flex justify-between gap-2">
              <span className="font-semibold">{job.phase}</span>
              {job.status === "running" && <span className="text-xs text-cyan" title={`${job.elapsed_s}s elapsed`}>{etaText(left)}</span>}
            </div>
            {job.dates_total ? <div className="text-xs text-slate-400">Satellite passes streamed: {Math.min(job.dates_streamed, job.dates_total)} of {job.dates_total}</div> : null}
            <div className="h-2 overflow-hidden rounded bg-grid"><div className="h-2 bg-cyan transition-all" style={{ width: `${job.percent ?? 5}%` }} /></div>
            {job.status === "running" && (
              <button onClick={stopJob} className="rounded border border-alert/60 px-3 py-1 text-xs font-semibold text-alert hover:bg-alert/10">■ Stop analysis</button>
            )}
            {stopped && <p className="text-isro">Stopped. Nothing half-built was added; already streamed dates are kept, so a rerun is faster.</p>}
            {job.status === "done" && <p className="text-emerald-300">Done. The new area is selected on the map.</p>}
            {job.status === "error" && <p className="text-alert">Failed: {job.error || "see log below"}</p>}
            <details className="text-xs text-slate-400"><summary className="cursor-pointer">Log</summary><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">{(job.log_tail || []).join("\n")}</pre></details>
          </div>
        )}
        <p className="mt-3 text-[11px] italic text-slate-500">Radar-based water indication for inspection, not a confirmed flood, depth, or damage.</p>
      </div>
    </div>
  );
}