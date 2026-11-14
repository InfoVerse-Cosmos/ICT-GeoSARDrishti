import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/api/client.js";
import { useMissionStore, LAYERS } from "@/store/useMissionStore.js";

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
  const run = () => {
    if (map.getLayer("basemap")) map.removeLayer("basemap");
    if (map.getSource("basemap")) map.removeSource("basemap");
    map.addSource("basemap", {
      type: "raster",
      tiles: def.tiles,
      tileSize: 256,
      maxzoom: def.maxzoom || 19,
      attribution: def.attribution,
    });
    // Keep the basemap beneath the SAR overlay and AOI boundary.
    const beforeId = ["active-overlay-layer", "aoi-boundary-line"].find((l) => map.getLayer(l));
    map.addLayer({ id: "basemap", type: "raster", source: "basemap" }, beforeId);
  };
  if (map.isStyleLoaded()) run();
  else map.once("load", run);
}

// Center MapLibre GL JS viewport (SRS §4.2.2): basemap + raster overlays + pixel click.
export default function MapWorkspace() {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const {
    aois, activeAoiId, activeLayer, activeDate, basemap,
    setActiveLayer, setBasemap, setClickedPixel, setEvidenceCard,
  } = useMissionStore();

  const aoi = aois.find((a) => a.aoi_id === activeAoiId);

  // Init map once (just a dark background; the basemap effect adds tiles).
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {},
        layers: [{ id: "bg", type: "background", paint: { "background-color": "#0B0F19" } }],
      },
      center: [94.1, 26.9],
      zoom: 9,
    });

    mapRef.current.on("click", async (e) => {
      const { lat, lng } = e.lngLat;
      const res = await api.inspect(useMissionStore.getState().activeAoiId, lat.toFixed(4), lng.toFixed(4));
      setClickedPixel({ lat, lon: lng, ...(res.data || {}), status: res.status, warning: res.warning });
      if (res.status === "ok") {
        const card = await api.evidenceCard({ aoi_id: res.aoi_id, lat, lon: lng, telemetry: res.data });
        setEvidenceCard(card.data?.card || null);
      } else {
        setEvidenceCard(null);
      }
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [setClickedPixel, setEvidenceCard]);

  // Apply / switch basemap.
  useEffect(() => {
    if (mapRef.current) applyBasemap(mapRef.current, basemap);
  }, [basemap]);

  // Fit to AOI bounds + draw boundary box.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !aoi?.bounds) return;
    const [w, s, e, n] = aoi.bounds;
    map.fitBounds([[w, s], [e, n]], { padding: 40, duration: 600 });

    const draw = () => {
      const boundary = {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
      };
      if (map.getSource("aoi-boundary")) {
        map.getSource("aoi-boundary").setData(boundary);
      } else {
        map.addSource("aoi-boundary", { type: "geojson", data: boundary });
        map.addLayer({
          id: "aoi-boundary-line",
          type: "line",
          source: "aoi-boundary",
          paint: { "line-color": "#38BDF8", "line-width": 2, "line-dasharray": [2, 1] },
        });
      }
    };
    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [aoi]);

  // Swap the active RGBA overlay image source.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !aoi?.bounds) return;
    const [w, s, e, n] = aoi.bounds;
    const url = api.layerPngUrl(activeAoiId, activeLayer, activeDate);
    const coords = [[w, n], [e, n], [e, s], [w, s]];

    const apply = () => {
      if (map.getSource("active-overlay")) {
        map.getSource("active-overlay").updateImage({ url, coordinates: coords });
      } else {
        map.addSource("active-overlay", { type: "image", url, coordinates: coords });
        map.addLayer({ id: "active-overlay-layer", type: "raster", source: "active-overlay", paint: { "raster-opacity": 0.75 } });
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [activeAoiId, activeLayer, activeDate, aoi]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {/* Layer toggles (top-left) */}
      <div className="absolute left-3 top-3 space-y-1 rounded border border-grid bg-panel/90 p-2 text-xs telemetry-mono">
        {LAYERS.map((l) => (
          <button
            key={l.id}
            onClick={() => setActiveLayer(l.id)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1 ${
              activeLayer === l.id ? "bg-nasa/40 text-cyan" : "text-slate-300 hover:bg-grid"
            }`}
          >
            <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: l.color }} />
            {l.label}
          </button>
        ))}
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
    </div>
  );
}
