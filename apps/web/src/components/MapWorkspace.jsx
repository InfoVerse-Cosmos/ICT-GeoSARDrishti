import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/api/client.js";
import { useMissionStore, LAYERS } from "@/store/useMissionStore.js";

// Center MapLibre GL JS viewport (SRS §4.2.2): raster overlays + pixel click.
export default function MapWorkspace() {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const { aois, activeAoiId, activeLayer, activeDate, setActiveLayer, setClickedPixel, setEvidenceCard } =
    useMissionStore();

  const aoi = aois.find((a) => a.aoi_id === activeAoiId);

  // Init map once.
  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
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
      {/* Layer toggles */}
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
    </div>
  );
}
