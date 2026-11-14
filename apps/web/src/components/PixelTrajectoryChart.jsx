import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useMissionStore } from "@/store/useMissionStore.js";

const CLASS_COLOUR = { open_water: "#0284C7", flooded_veg: "#10B981", dry: "#64748B", nodata: "#334155" };
const CLASS_LABEL = { open_water: "open", flooded_veg: "f-veg", dry: "dry", nodata: "n/a" };

// Pixel click HH/HV dB trajectory (SRS §4.2 Tab 2).
export default function PixelTrajectoryChart() {
  const { clickedPixel } = useMissionStore();

  if (!clickedPixel) {
    return (
      <p className="mb-3 telemetry-mono text-xs text-slate-400">
        Click inside the cyan AOI boundary to plot its HH/HV dB trajectory.
      </p>
    );
  }
  if (clickedPixel.status === "loading") return <div role="status" className="mb-3 h-48 animate-pulse rounded bg-grid p-3 text-sm">Loading pixel trajectory...</div>;
  if (clickedPixel.status === "outside_aoi") return null;

  const dates = clickedPixel.dates || [];
  const classes = clickedPixel.classes || [];
  const data = dates.map((d, i) => ({
    date: String(d).slice(5),
    HH: clickedPixel.hh_db?.[i] ?? null,
    HV: clickedPixel.hv_db?.[i] ?? null,
    ratio:
      clickedPixel.hh_db?.[i] != null && clickedPixel.hv_db?.[i] != null
        ? +(clickedPixel.hh_db[i] - clickedPixel.hv_db[i]).toFixed(2)
        : null,
  }));
  const hp = clickedPixel.hydroperiod || {};
  const owThreshold = clickedPixel.open_water_threshold_db ?? -16;

  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between telemetry-mono text-xs text-slate-400">
        <span>
          {clickedPixel.lat?.toFixed(4)}°, {clickedPixel.lon?.toFixed(4)}° · γ⁰ (dB)
        </span>
        {hp.n ? (
          <span className="text-cyan">
            wet {hp.m}/{hp.n} obs
          </span>
        ) : null}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
          <CartesianGrid stroke="#1E293B" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fill: "#94A3B8", fontSize: 10 }} />
          <YAxis tick={{ fill: "#94A3B8", fontSize: 10 }} domain={["auto", "auto"]} />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1E293B", fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine
            y={owThreshold}
            stroke="#0284C7"
            strokeDasharray="4 2"
            label={{ value: `open-water τ ${owThreshold.toFixed(1)} dB`, fill: "#0284C7", fontSize: 9 }}
          />
          {clickedPixel.hh_baseline_db != null && (
            <ReferenceLine
              y={clickedPixel.hh_baseline_db}
              stroke="#FF671F"
              strokeDasharray="2 2"
              label={{ value: `dry ref ${clickedPixel.reference_date?.slice(5) || ""}`, fill: "#FF671F", fontSize: 9 }}
            />
          )}
          <Line type="monotone" dataKey="HH" stroke="#38BDF8" dot={{ r: 3 }} connectNulls />
          <Line type="monotone" dataKey="HV" stroke="#F59E0B" dot={{ r: 3 }} connectNulls />
          <Line type="monotone" dataKey="ratio" name="HH−HV" stroke="#10B981" strokeDasharray="3 3" dot={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {classes.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1 telemetry-mono text-xs">
          {dates.map((d, i) => (
            <span
              key={d}
              className="rounded px-1"
              style={{ backgroundColor: `${CLASS_COLOUR[classes[i]] || "#334155"}55`, color: "#E2E8F0" }}
              title={`${d}: ${classes[i]}`}
            >
              {String(d).slice(5)} {CLASS_LABEL[classes[i]] || classes[i]}
            </span>
          ))}
        </div>
      )}
      {data.length === 0 && (
        <p className="telemetry-mono text-xs text-slate-400">
          No trajectory yet — pixel cube is generated in Phase 2.
        </p>
      )}
    </div>
  );
}
