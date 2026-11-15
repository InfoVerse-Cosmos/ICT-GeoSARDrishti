"use client";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { isWebglAvailable } from "@/lib/webgl.js";
const SAT = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg";
function style() {
  return {
    version: 8,
    sources: {
      sat: {
        type: "raster",
        tiles: [SAT],
        tileSize: 256,
        maxzoom: 16,
        attribution: "Sentinel-2 cloudless \xA9 EOX IT Services"
      }
    },
    layers: [{ id: "sat", type: "raster", source: "sat" }]
  };
}
function HeroTerrain() {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const spin = useRef(true);
  const raf = useRef(null);
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    if (!isWebglAvailable()) return; // no WebGL: keep the gradient backdrop, don't crash the hero
    let map;
    try {
      map = new maplibregl.Map({
        container: ref.current,
        style: style(),
        center: [79, 24],
        // India / Himalaya facing us
        zoom: 2.75,
        pitch: 0,
        bearing: 0,
        maxPitch: 85,
        attributionControl: { compact: true },
        dragRotate: true
      });
    } catch {
      return;
    }
    map.scrollZoom.disable();
    spin.current = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    mapRef.current = map;
    const step = () => {
      if (spin.current && !document.hidden) {
        const c = map.getCenter();
        map.setCenter([c.lng + 0.12, c.lat]);
      }
      raf.current = requestAnimationFrame(step);
    };
    const stop = () => {
      spin.current = false;
    };
    map.on("load", () => {
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      raf.current = requestAnimationFrame(step);
    });
    map.on("mousedown", stop);
    map.on("touchstart", stop);
    map.on("wheel", stop);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
      map.remove();
      mapRef.current = null;
    };
  }, []);
  return <div
    ref={ref}
    className="absolute inset-0"
    style={{
      background: "radial-gradient(circle at 50% 42%, #0a1733 0%, #070c1a 45%, #04060d 100%)"
    }}
    role="img"
    aria-label="Interactive satellite overview of Earth"
  />;
}
export {
  HeroTerrain
};
