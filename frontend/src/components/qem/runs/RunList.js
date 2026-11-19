const CLS = { running: "chip-part", completed: "chip-sup", failed: "chip-not", cancelled: "chip-not" };

const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

export default function RunList({ runs, loading, selected, onSelect }) {
  if (loading) return <div className="card p-5 overline animate-pulse" data-testid="run-list-loading">Loading runs…</div>;
  if (!runs.length) return <div className="card p-5 text-sm text-slate-400" data-testid="run-list-empty">No custom runs yet. Saved published results remain in the other tabs.</div>;
  return (
    <div className="card overflow-auto max-h-[520px]" data-testid="run-list">
      <table className="qtable">
        <thead><tr>{["Run", "Started (UTC)", "Status", "Design", "Time"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.run_id} data-testid={`run-list-row-${r.run_id}`} onClick={() => onSelect(r.run_id)}
              className={`cursor-pointer ${selected === r.run_id ? "bg-sky-400/10" : ""}`}>
              <td className="font-medium">{r.name}</td>
              <td className="num text-slate-400">{r.created_at.slice(0, 19).replace("T", " ")}</td>
              <td><span className={`chip ${CLS[r.status]}`} data-testid={`run-status-${r.run_id}`}>{r.status}</span></td>
              <td className="text-slate-400 text-xs">{plural(r.spec.instances.length, "circuit")} · {plural(r.spec.noise.length, "noise level")} · {plural(r.spec.shots.length, "budget")} · {plural(r.spec.repetitions, "rep")}</td>
              <td className="num">{r.wall_s ? `${r.wall_s.toFixed(1)}s` : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
