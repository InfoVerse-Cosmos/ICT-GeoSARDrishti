import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/api/client.js";
import { LAYERS, REGIME_LEGEND, useMissionStore } from "@/store/useMissionStore.js";
import { SIMPLE_LAYER_IDS, plainLayerLabel } from "@/plain.js";

const EMPTY_FC = { type: "FeatureCollection", features: [] };
const OVERLAY_OPACITY = 0.85;

// Key-free basemaps (all verified to serve tiles without an API key).
// "nasa" = NASA EOSDIS GIBS Blue Marble — a real NASA earth backdrop (coarse, great for overview).
export const BASEMAPS = {
  dark: {
    label: "Dark",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Tiles © Esri — Esri, HERE, Garmin",
    maxzoom: 16,
  },
  satellite: {
    label: "Satellite",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
    maxzoom: 19,
  },
  street: {
    label: "Street",
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    attribution: "© OpenStreetMap contributors",
    maxzoom: 19,
  },
  terrain: {
    label: "Terrain",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Tiles © Esri — Esri, USGS, NOAA",
    maxzoom: 19,
  },
  nasa: {
    label: "NASA Blue Marble",
    tiles: ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"],
    attribution: "Imagery © NASA EOSDIS GIBS",
    maxzoom: 8,
  },
};

function applyBasemap(map, id) {
  const def = BASEMAPS[id] || BASEMAPS.dark;
  if (map.getLayer("basemap")) map.removeLayer("basemap");
  if (map.getSource("basemap")) map.removeSource("basemap");
  map.addSource("basemap", {
    type: "raster",
    tiles: def.tiles,
    tileSize: 256,
    maxzoom: def.maxzoom || 19,
    attribution: def.attribution,
  });
  // Keep the basemap directly above the background, beneath every SAR / vector layer.
  const beforeId = map.getStyle().layers.find((l) => l.id !== "bg" && l.id !== "basemap")?.id;
  map.addLayer({ id: "basemap", type: "raster", source: "basemap" }, beforeId);
}

// Center MapLibre GL JS viewport (SRS §4.2.2): switchable basemap, RGBA overlays per date,
// before/after comparison, OSM inspection candidates, regional context, pixel click -> evidence.
export default function MapWorkspace({ onPixelInspected }) {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const inspectedCb = useRef(onPixelInspected);
  inspectedCb.current = onPixelInspected;

  const {
    aois, activeAoiId, activeLayer, activeDate, compareDate, compareMix, timeline, showExposure,
    exposure, clickedPixel, flyTo, connection, basemap, audienceMode,
    setActiveLayer, setClickedPixel, setEvidenceCard, setExposure, setCompareDate, setCompareMix, setShowExposure,
    setBasemap,
  } = useMissionStore();

  const simple = audienceMode === "simple";
  const aoi = aois.find((a) => a.aoi_id === activeAoiId);
  const available = LAYERS.filter(
    (l) => (!aoi?.layers || aoi.layers.includes(l.id)) && (!simple || SIMPLE_LAYER_IDS.includes(l.id)),
  );
  const layerDef = LAYERS.find((l) => l.id === activeLayer) || LAYERS[0];
  const isRaster = layerDef.id !== "context_layers";

  // ---- helpers ------------------------------------------------------------------
  // NB: map.isStyleLoaded() is false while tiles stream in, and "load" fires only once,
  // so we keep our own ready flag + queue instead of map.once("load").
  // Keyed: a later call with the same key replaces the queued one (avoids aborted image loads).
  const readyRef = useRef(false);
  const queueRef = useRef(new Map());
  const lastImageRef = useRef({});
  const whenReady = (fn, key = Symbol("once")) => {
    const map = mapRef.current;
    if (!map) return;
    if (readyRef.current) fn(map);
    else queueRef.current.set(key, fn);
  };

  const upsertGeojson = (map, id, data) => {
    if (map.getSource(id)) map.getSource(id).setData(data);
    else map.addSource(id, { type: "geojson", data });
  };

  // ---- init map once ---------------------------------------------------------------
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      // Just a dark background; the basemap effect adds tiles (Dark / Satellite / Street / Terrain / NASA).
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "bg", type: "background", paint: { "background-color": "#0B0F19" } }],
      },
      center: [94.1, 26.9],
      zoom: 9,
    });
    map.on("load", () => {
      readyRef.current = true;
      const pending = [...queueRef.current.values()];
      queueRef.current = new Map();
      pending.forEach((fn) => fn(map));
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

    map.on("click", async (e) => {
      const { lat, lng } = e.lngLat;
      const aoiId = useMissionStore.getState().activeAoiId;
      setClickedPixel({ lat, lon: lng, status: "loading" });
      setEvidenceCard(null);
      inspectedCb.current?.();
      const res = await api.inspect(aoiId, lat.toFixed(5), lng.toFixed(5));
      setClickedPixel({ ...(res.data || {}), lat, lon: lng, status: res.status, warning: res.warning });
      if (res.status === "ok") {
        const payload = { aoi_id: res.aoi_id, lat, lon: lng, telemetry: res.data };
        // 1) instant deterministic card, 2) upgrade with the LLM wording if/when it arrives
        const card = await api.evidenceCard(payload);
        setEvidenceCard(card.data?.card || null);
        const llm = await api.evidenceCard(payload, { narrate: true });
        const stillSame = useMissionStore.getState().clickedPixel?.lat === lat;
        if (stillSame && llm.data?.card?.mode === "llm_grounded") setEvidenceCard(llm.data.card);
      }
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
      queueRef.current = new Map();
      lastImageRef.current = {};
    };
  }, [setClickedPixel, setEvidenceCard]);

  // ---- basemap switch (via the ready-queue, so it never races the map "load") ----------
  useEffect(() => {
    whenReady((map) => applyBasemap(map, basemap), "basemap");
  }, [basemap]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- AOI boundary + fit ------------------------------------------------------------
  useEffect(() => {
    if (!aoi?.bounds) return;
    const [w, s, e, n] = aoi.bounds;
    whenReady((map) => {
      map.fitBounds([[w, s], [e, n]], { padding: 40, duration: 600 });
      upsertGeojson(map, "aoi-boundary", {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
      });
      if (!map.getLayer("aoi-boundary-line")) {
        map.addLayer({
          id: "aoi-boundary-line", type: "line", source: "aoi-boundary",
          paint: { "line-color": "#38BDF8", "line-width": 2, "line-dasharray": [2, 1] },
        });
      }
    }, "aoi");
    if (!available.find((l) => l.id === activeLayer)) setActiveLayer(available[0]?.id || "open_water");
  }, [aoi]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- raster overlays (active + optional "before" comparison) ------------------------
  useEffect(() => {
    if (!aoi?.bounds) return;
    const [w, s, e, n] = aoi.bounds;
    const coords = [[w, n], [e, n], [e, s], [w, s]];
    const dated = layerDef.dated;
    const afterUrl = api.layerPngUrl(activeAoiId, activeLayer, dated ? activeDate : null);
    const beforeUrl = compareDate ? api.layerPngUrl(activeAoiId, activeLayer, dated ? compareDate : null) : null;

    whenReady((map) => {
      const setImage = (id, url, opacity, beforeId) => {
        if (!url || !isRaster || connection === "OFFLINE") {
          if (map.getLayer(`${id}-layer`)) map.removeLayer(`${id}-layer`);
          if (map.getSource(id)) map.removeSource(id);
          delete lastImageRef.current[id];
          return;
        }
        const sig = `${url}|${coords.flat().join(",")}`;
        if (map.getSource(id)) {
          if (lastImageRef.current[id] !== sig) map.getSource(id).updateImage({ url, coordinates: coords });
        } else {
          map.addSource(id, { type: "image", url, coordinates: coords });
          map.addLayer(
            { id: `${id}-layer`, type: "raster", source: id, paint: { "raster-fade-duration": 0 } },
            map.getLayer(beforeId) ? beforeId : undefined,
          );
        }
        lastImageRef.current[id] = sig;
        map.setPaintProperty(`${id}-layer`, "raster-opacity", opacity);
      };
      const comparing = Boolean(compareDate) && dated;
      setImage("compare-overlay", comparing ? beforeUrl : null, (1 - compareMix) * OVERLAY_OPACITY, "aoi-boundary-line");
      setImage("active-overlay", afterUrl, comparing ? compareMix * OVERLAY_OPACITY : OVERLAY_OPACITY, "aoi-boundary-line");
    }, "overlays");
  }, [activeAoiId, activeLayer, activeDate, compareDate, compareMix, aoi, connection]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- OSM inspection candidates (shared with the Inspection Log tab) -----------------
  useEffect(() => {
    if (connection === "OFFLINE" || connection === "CONNECTING") return;
    let cancelled = false;
    (async () => {
      const res = await api.exposure(activeAoiId);
      if (!cancelled) setExposure(res.data ? { ...res.data, warning: res.warning } : null);
    })();
    return () => {
      cancelled = true;
    };
  }, [activeAoiId, connection, setExposure]);

  useEffect(() => {
    whenReady((map) => {
      upsertGeojson(map, "exposure", showExposure && exposure?.geojson ? exposure.geojson : EMPTY_FC);
      if (!map.getLayer("exposure-lines")) {
        map.addLayer({
          id: "exposure-lines", type: "line", source: "exposure",
          filter: ["==", ["geometry-type"], "LineString"],
          paint: { "line-color": "#EF4444", "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 14, 4] },
        });
        map.addLayer({
          id: "exposure-points", type: "circle", source: "exposure",
          filter: ["!=", ["geometry-type"], "LineString"],
          paint: { "circle-color": "#EF4444", "circle-radius": 5, "circle-stroke-color": "#fff", "circle-stroke-width": 1 },
        });
      }
    });
  }, [exposure, showExposure]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- regional context layer (vector) -----------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let data = EMPTY_FC;
      if (activeLayer === "context_layers" && connection !== "OFFLINE") {
        const res = await api.context(activeAoiId);
        data = res.data?.geojson || EMPTY_FC;
      }
      if (cancelled) return;
      whenReady((map) => {
        upsertGeojson(map, "context", data);
        if (!map.getLayer("context-fill")) {
          map.addLayer({ id: "context-fill", type: "fill", source: "context", paint: { "fill-color": "#A78BFA", "fill-opacity": 0.15 } });
          map.addLayer({ id: "context-line", type: "line", source: "context", paint: { "line-color": "#A78BFA", "line-width": 1.5 } });
        }
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [activeAoiId, activeLayer, connection]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- clicked pixel marker -------------------------------------------------------------
  useEffect(() => {
    whenReady((map) => {
      const data = clickedPixel
        ? { type: "Feature", geometry: { type: "Point", coordinates: [clickedPixel.lon, clickedPixel.lat] } }
        : EMPTY_FC;
      upsertGeojson(map, "clicked", data);
      if (!map.getLayer("clicked-point")) {
        map.addLayer({
          id: "clicked-point", type: "circle", source: "clicked",
          paint: { "circle-radius": 7, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": "#F47216", "circle-stroke-width": 3 },
        });
      }
    });
  }, [clickedPixel]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- fly to (from Inspection Log) -------------------------------------------------------
  useEffect(() => {
    if (flyTo?.center) mapRef.current?.flyTo({ center: flyTo.center, zoom: flyTo.zoom, duration: 1200 });
  }, [flyTo]);

  const otherDates = timeline.filter((t) => t.date !== activeDate);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" data-testid="map" />

      {/* Layer toggles */}
      <div className="absolute left-3 top-3 w-56 space-y-1 rounded border border-grid bg-panel/90 p-2 text-xs telemetry-mono">
        {available.map((l) => (
          <button
            key={l.id}
            onClick={() => setActiveLayer(l.id)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1 ${
              activeLayer === l.id ? "bg-nasa/40 text-cyan" : "text-slate-300 hover:bg-grid"
            }`}
          >
            <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: l.color }} />
            {simple ? plainLayerLabel(l.id) : l.label}
            {!l.dated && !simple && <span className="ml-auto text-[9px] text-slate-500">SEASON</span>}
          </button>
        ))}
        <label className="flex items-center gap-2 border-t border-grid px-2 pt-2 text-slate-300">
          <input type="checkbox" checked={showExposure} onChange={(e) => setShowExposure(e.target.checked)} />
          <span className="h-3 w-3 rounded-sm bg-alert" /> Inspection candidates
        </label>

        {/* Before / after comparison */}
        {layerDef.dated && (
          <div className="space-y-1 border-t border-grid px-2 pt-2 text-slate-300">
            <div className="text-[10px] uppercase text-slate-500">Before / after</div>
            <select
              aria-label="Compare with date"
              value={compareDate || ""}
              onChange={(e) => setCompareDate(e.target.value || null)}
              className="w-full rounded border border-grid bg-orbital px-1 py-0.5"
            >
              <option value="">off</option>
              {otherDates.map((t) => (
                <option key={t.date} value={t.date}>before: {t.date}</option>
              ))}
            </select>
            {compareDate && (
              <>
                <input
                  aria-label="Before/after mix"
                  type="range" min="0" max="1" step="0.05" value={compareMix}
                  onChange={(e) => setCompareMix(Number(e.target.value))}
                  className="w-full accent-isro"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>{compareDate}</span>
                  <span>{activeDate}</span>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Basemap switcher (bottom-left) */}
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-1 rounded border border-grid bg-panel/90 p-1 text-[10px] telemetry-mono">
        <span className="px-1 py-1 text-slate-500">BASEMAP</span>
        {Object.entries(BASEMAPS).map(([id, d]) => (
          <button
            key={id}
            onClick={() => setBasemap(id)}
            className={`rounded px-2 py-1 ${
              basemap === id ? "bg-isro/30 text-isro" : "text-slate-300 hover:bg-grid"
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <Legend layer={activeLayer} simple={simple} />
    </div>
  );
}

function Legend({ layer, simple }) {
  let body = null;
  if (simple) {
    if (layer === "hydroperiod") {
      body = (
        <>
          <div className="h-2 w-40 rounded" style={{ background: "linear-gradient(90deg,#FDE68A,#C2410C)" }} />
          <div className="flex justify-between text-[10px] text-slate-400"><span>wet once</span><span>wet every pass</span></div>
          <div className="mt-1">Darker = water seen on more satellite passes.</div>
        </>
      );
    } else if (layer === "flooded_veg") {
      body = <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-fveg" />Water hidden under plants</div>;
    } else {
      body = <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-water" />Open water (seen from space)</div>;
    }
    return (
      <div className="absolute right-3 top-3 max-w-xs space-y-1 rounded border border-grid bg-panel/90 p-2 text-[11px] text-slate-300">
        {body}
      </div>
    );
  }
  if (layer === "hydroperiod") {
    body = (
      <>
        <div className="h-2 w-40 rounded" style={{ background: "linear-gradient(90deg,#FDE68A,#C2410C)" }} />
        <div className="flex justify-between text-[10px] text-slate-400"><span>wet 1 obs</span><span>wet every obs (M=N)</span></div>
      </>
    );
  } else if (layer === "gmm_regimes") {
    body = REGIME_LEGEND.map(([name, c]) => (
      <div key={name} className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm" style={{ background: c }} />{name}</div>
    ));
  } else if (layer === "flooded_veg") {
    body = (
      <>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-fveg" />Possible flooded vegetation (HH surge ≥ +3 dB vs dry reference)</div>
        <div className="flex items-center gap-2 text-slate-500"><span className="h-2 w-2 rounded-sm bg-paddy" />Paddy-like: only when ESA WorldCover is loaded</div>
      </>
    );
  } else if (layer === "jrc_anomaly") {
    body = (
      <>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-alert" />Unusual open water (JRC &lt; 20%)</div>
        <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-water" />Historically normal open water</div>
      </>
    );
  } else if (layer === "context_layers") {
    body = <div>Official GSDA / CGWB context — not a SAR detection</div>;
  } else {
    body = <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-sm bg-water" />Open water (HH &amp; HV below Otsu τ)</div>;
  }
  return (
    <div className="absolute right-3 top-3 max-w-xs space-y-1 rounded border border-grid bg-panel/90 p-2 text-[11px] telemetry-mono text-slate-300">
      {body}
    </div>
  );
}
