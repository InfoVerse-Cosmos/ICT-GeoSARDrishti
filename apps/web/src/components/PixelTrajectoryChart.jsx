import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { useMissionStore } from "@/store/useMissionStore.js";

// Pixel click HH/HV dB trajectory (SRS §4.2 Tab 2).
export default function PixelTrajectoryChart() {
  const { clickedPixel } = useMissionStore();

  if (!clickedPixel) {
    return (
      <p className="telemetry-mono text-xs text-slate-500">
        Click inside the cyan AOI boundary to plot its HH/HV dB trajectory.
      </p>
    );
  }
  if (clickedPixel.status === "outside_aoi") {
    return <p className="telemetry-mono text-xs text-isro">{clickedPixel.warning}</p>;
  }

  const dates = clickedPixel.dates || [];
  const data = dates.map((d, i) => ({
    date: String(d).slice(5),
    HH: clickedPixel.hh_db?.[i] ?? null,
    HV: clickedPixel.hv_db?.[i] ?? null,
  }));

  return (
    <div className="mb-3">
      <div className="mb-1 telemetry-mono text-[11px] text-slate-400">
        {clickedPixel.lat?.toFixed(4)}°, {clickedPixel.lon?.toFixed(4)}° · γ⁰ backscatter (dB)
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: -20 }}>
          <CartesianGrid stroke="#1E293B" strokeDasharray="3 3" />
          <XAxis dataKey="date" tick={{ fill: "#94A3B8", fontSize: 10 }} />
          <YAxis tick={{ fill: "#94A3B8", fontSize: 10 }} unit="" />
          <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1E293B", fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={-16} stroke="#0284C7" strokeDasharray="4 2" label={{ value: "open-water ~ -16 dB", fill: "#0284C7", fontSize: 9 }} />
          <Line type="monotone" dataKey="HH" stroke="#38BDF8" dot={{ r: 2 }} />
          <Line type="monotone" dataKey="HV" stroke="#F59E0B" dot={{ r: 2 }} />
        </LineChart>
      </ResponsiveContainer>
      {data.length === 0 && (
        <p className="telemetry-mono text-[11px] text-slate-500">
          No trajectory yet — pixel cube is generated in Phase 2.
        </p>
      )}
    </div>
  );
}
