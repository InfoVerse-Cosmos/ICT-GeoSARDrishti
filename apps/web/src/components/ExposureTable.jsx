import { useEffect, useState } from "react";
import { api } from "@/api/client.js";
import { useMissionStore } from "@/store/useMissionStore.js";

// OSM inspection-candidates log (SRS §4.2 Tab 3, §5.5).
export default function ExposureTable() {
  const { activeAoiId } = useMissionStore();
  const [rows, setRows] = useState([]);
  const [note, setNote] = useState("");

  useEffect(() => {
    (async () => {
      const res = await api.exposure(activeAoiId);
      setRows(res.data?.ranked || []);
      setNote(res.warning || res.data?.note || "");
    })();
  }, [activeAoiId]);

  return (
    <div>
      <h3 className="mb-2 telemetry-mono text-xs uppercase tracking-wide text-cyan">
        Ground Inspection Candidates
      </h3>
      <p className="mb-2 text-[11px] italic text-slate-400">
        Roads &amp; settlements wet on ≥3 NISAR observations. Inspection candidates only — never a damage claim.
      </p>
      {rows.length === 0 ? (
        <p className="telemetry-mono text-xs text-slate-500">{note || "No candidates loaded yet."}</p>
      ) : (
        <table className="w-full text-left text-xs telemetry-mono">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1">Name</th>
              <th>Kind</th>
              <th className="text-right">Wet M/N</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-grid hover:bg-grid/50">
                <td className="py-1">{r.name}</td>
                <td>{r.kind}</td>
                <td className="text-right text-alert">
                  {r.wet_observations}/{r.total_observations}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
