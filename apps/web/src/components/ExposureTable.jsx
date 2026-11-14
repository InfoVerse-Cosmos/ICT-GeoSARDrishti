import { useMemo, useState } from "react";
import { useMissionStore } from "@/store/useMissionStore.js";

// Tab 3 — OSM inspection-candidates log (SRS §4.2.4, §5.5): sortable, click to fly the map.
const COLUMNS = [
  ["name", "Name"],
  ["kind", "Kind"],
  ["wet_observations", "Wet M/N"],
];

export default function ExposureTable() {
  const { exposure, setFlyTo } = useMissionStore();
  const [sort, setSort] = useState({ key: "wet_observations", dir: -1 });
  const [kind, setKind] = useState("all");

  const rows = exposure?.ranked || [];
  const kinds = useMemo(() => ["all", ...new Set(rows.map((r) => r.kind).filter(Boolean))], [rows]);
  const sorted = useMemo(() => {
    const filtered = kind === "all" ? rows : rows.filter((r) => r.kind === kind);
    return [...filtered].sort((a, b) => {
      const va = a[sort.key] ?? "";
      const vb = b[sort.key] ?? "";
      return (va > vb ? 1 : va < vb ? -1 : 0) * sort.dir;
    });
  }, [rows, sort, kind]);

  const note = exposure?.warning || exposure?.note || "";

  return (
    <div>
      <h3 className="mb-2 telemetry-mono text-xs uppercase tracking-wide text-cyan">Ground Inspection Candidates</h3>
      <p className="mb-2 text-xs italic text-slate-400">
        {exposure?.note ||
          "Roads & settlements wet on ≥3 NISAR observations. Inspection candidates only — never a damage claim."}
      </p>
      {rows.length === 0 ? (
        <p className="telemetry-mono text-xs text-slate-400">{note || "No candidates loaded yet."}</p>
      ) : (
        <>
          <div className="mb-2 flex items-center gap-2 text-xs telemetry-mono text-slate-400">
            <span>{sorted.length} candidates</span>
            <select
              aria-label="Filter by kind"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
              className="ml-auto rounded border border-grid bg-orbital px-1"
            >
              {kinds.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <table className="w-full text-left text-xs telemetry-mono">
            <thead className="text-slate-400">
              <tr>
                {COLUMNS.map(([key, label]) => (
                  <th
                    key={key}
                    className={`cursor-pointer select-none py-1 hover:text-cyan ${key === "wet_observations" ? "text-right" : ""}`}
                    onClick={() => setSort((s) => ({ key, dir: s.key === key ? -s.dir : key === "wet_observations" ? -1 : 1 }))}
                  >
                    {label} {sort.key === key ? (sort.dir === 1 ? "▲" : "▼") : ""}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => r.center && setFlyTo(r.center, 14)}
                  title={r.wet_dates?.length ? `wet on ${r.wet_dates.join(", ")}` : undefined}
                  className={`border-t border-grid ${r.center ? "cursor-pointer hover:bg-grid/50" : ""}`}
                >
                  <td className="py-1">{r.name}</td>
                  <td>{r.kind}</td>
                  <td className="text-right text-alert">
                    {r.wet_observations}/{r.total_observations}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-400">
            {exposure?.source ? `Source: ${exposure.source}. ` : ""}© OpenStreetMap contributors. Click a row to fly the map.
          </p>
        </>
      )}
    </div>
  );
}
