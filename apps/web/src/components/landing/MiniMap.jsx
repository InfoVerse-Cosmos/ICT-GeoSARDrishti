"use client";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
const SAT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const W = 77.99024;
const S = 19.9922;
const E = 78.50819;
const N = 20.50816;
const COORDS = [
  [W, N],
  [E, N],
  [E, S],
  [W, S]
];
function style() {
  return {
    version: 8,
    sources: {
      sat: {
        type: "raster",
        tiles: [SAT],
        tileSize: 256,
        maxzoom: 19,
        attribution: "Imagery \xA9 Esri"
      }
    },
    layers: [{ id: "sat", type: "raster", source: "sat" }]
  };
}
function MiniMap({
  overlay,
  opacity = 0.92,
  bearing = -14
}) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: style(),
      center: [(W + E) / 2, (S + N) / 2],
      zoom: 9.15,
      pitch: 38,
      bearing,
      attributionControl: { compact: true },
      dragRotate: true
    });
    map.scrollZoom.disable();
    mapRef.current = map;
    map.on("load", () => {
      map.addSource("sar", { type: "image", url: overlay, coordinates: COORDS });
      map.addLayer({
        id: "sar",
        type: "raster",
        source: "sar",
        paint: { "raster-opacity": opacity, "raster-fade-duration": 0 }
      });
      map.addSource("aoi", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [[[W, S], [E, S], [E, N], [W, N], [W, S]]]
          }
        }
      });
      map.addLayer({
        id: "aoi",
        type: "line",
        source: "aoi",
        paint: { "line-color": "#22d3ee", "line-width": 1.5, "line-dasharray": [2, 1] }
      });
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [overlay, opacity, bearing]);
  return <div ref={ref} className="absolute inset-0" />;
}
export {
  MiniMap
};
