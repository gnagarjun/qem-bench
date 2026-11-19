import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get, fmt, pct, METHOD_LABEL, METHOD_COLOR } from "@/lib/qem";
import Select from "@/components/qem/Select";

export default function ExplorerTab({ filters }) {
  const [f, setF] = useState({ block: "core", noise: "moderate", comparison: "A", shots_per_circuit: "4096", instance: null, method: null });
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const q = useQuery({ queryKey: ["conditions", f], queryFn: () => get("/conditions", { ...f, limit: 500 }) });
  return (
    <div className="space-y-6" data-testid="condition-explorer-tab">
      <div className="card p-4 flex flex-wrap gap-3 items-end" data-testid="explorer-filter-bar">
        <Select id="filter-block-select" label="Block" value={f.block} onChange={set("block")} options={filters.block} />
        <Select id="filter-circuit-family-select" label="Instance" value={f.instance} onChange={set("instance")} options={filters.instance} />
        <Select id="filter-noise-level-select" label="Noise" value={f.noise} onChange={set("noise")} options={filters.noise} />
        <Select id="filter-shots-select" label="Shots / circuit" value={f.shots_per_circuit} onChange={set("shots_per_circuit")} options={filters.shots_per_circuit.map(String)} />
        <Select id="filter-method-select" label="Method" value={f.method} onChange={set("method")} options={filters.method.map((m) => ({ value: m, label: METHOD_LABEL[m] }))} />
        <div className="flex flex-col gap-1">
          <span className="overline">Accounting</span>
          <div className="flex gap-1">
            {["A", "B"].map((c) => (
              <button key={c} data-testid={`filter-comparison-toggle-${c.toLowerCase()}`} data-active={f.comparison === c} className="tabbtn border border-white/10" onClick={() => set("comparison")(c)}>
                {c === "A" ? "A · equal primary shots" : "B · equal total budget"}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="overline" data-testid="explorer-row-count">{q.data ? `${q.data.total} conditions (primary observable)` : "loading…"}</div>
      <div className="card overflow-auto max-h-[640px]">
        <table className="qtable" data-testid="condition-explorer-table">
          <thead><tr>{["Instance", "Noise", "N", "Method", "Mean", "Ideal", "Bias", "RMSE [95% CI]", "Total shots", "Overhead", "ΔRMSE", "Var ratio"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {(q.data?.rows || []).map((r, i) => (
              <tr key={i} data-testid="condition-row">
                <td>{r.instance}</td><td>{r.noise}</td><td className="num">{r.shots_per_circuit}</td>
                <td><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: METHOD_COLOR[r.method] }} />{METHOD_LABEL[r.method]}</td>
                <td className="num">{fmt(r.mean, 4)}</td><td className="num">{fmt(r.ideal, 4)}</td><td className="num">{fmt(r.bias, 3)}</td>
                <td className="num">{fmt(r.rmse, 3)} <span className="text-slate-500">[{fmt(r.rmse_ci_lo, 2)}, {fmt(r.rmse_ci_hi, 2)}]</span></td>
                <td className="num">{Math.round(r.total_shots).toLocaleString()}</td><td className="num">{fmt(r.sampling_overhead, 3)}×</td>
                <td className={`num ${r.rel_rmse_change < 0 ? "text-emerald-400" : r.rel_rmse_change > 0 ? "text-rose-400" : ""}`}>{r.method === "baseline" ? "–" : pct(r.rel_rmse_change)}</td>
                <td className="num">{fmt(r.variance_ratio, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
