import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { runsApi, noiseLabel } from "@/lib/runs";
import { fmt, pct, METHOD_LABEL, METHOD_COLOR } from "@/lib/qem";
import Select from "@/components/qem/Select";

const OUT_CLS = { better_practical: "text-emerald-400", better_marginal: "text-emerald-300/70", worse_practical: "text-rose-400", worse_marginal: "text-rose-300/70" };

export default function RunResults({ run }) {
  const s = run.spec;
  const [f, setF] = useState({ comparison: s.comparisons[0], shots_per_circuit: String(s.shots[s.shots.length - 1]), noise: null, instance: null, method: null });
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v }));
  const cond = useQuery({ queryKey: ["run-cond", run.run_id, f], queryFn: () => runsApi.conditions(run.run_id, f) });
  const tests = useQuery({ queryKey: ["run-tests", run.run_id, f.comparison], queryFn: () => runsApi.tests(run.run_id, { comparison: f.comparison }) });
  return (
    <div className="space-y-5" data-testid="run-results">
      <div className="flex flex-wrap gap-3 items-end">
        <Select id="run-res-comparison-select" label="Accounting" value={f.comparison} onChange={set("comparison")} options={s.comparisons} allLabel={null} />
        <Select id="run-res-shots-select" label="Shots / circuit" value={f.shots_per_circuit} onChange={set("shots_per_circuit")} options={s.shots.map(String)} />
        <Select id="run-res-instance-select" label="Circuit" value={f.instance} onChange={set("instance")} options={s.instances} />
        <Select id="run-res-noise-select" label="Noise" value={f.noise} onChange={set("noise")} options={s.noise.map(noiseLabel)} />
        <Select id="run-res-method-select" label="Method" value={f.method} onChange={set("method")} options={s.methods.map((m) => ({ value: m, label: METHOD_LABEL[m] }))} />
      </div>
      <div>
        <div className="overline mb-2">Wilcoxon tests vs baseline (accounting {f.comparison}, BH-corrected)</div>
        <div className="flex flex-wrap gap-3" data-testid="run-res-outcome-counts">
          {Object.entries(tests.data?.outcome_counts || {}).map(([k, v]) => (
            <div key={k} className="card px-4 py-3"><div className="overline">{k.replaceAll("_", " ")}</div><div className={`num text-xl font-semibold ${OUT_CLS[k] || ""}`}>{v}</div></div>
          ))}
        </div>
      </div>
      <div className="overline" data-testid="run-res-row-count">{cond.data ? `${cond.data.total} conditions (primary observable)` : "loading…"}</div>
      <div className="card overflow-auto max-h-[520px]">
        <table className="qtable" data-testid="run-res-conditions-table">
          <thead><tr>{["Circuit", "Noise", "N", "Method", "Mean", "Ideal", "Bias", "RMSE [95% CI]", "Total shots", "ΔRMSE"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{(cond.data?.rows || []).map((r, i) => (
            <tr key={i} data-testid="run-res-condition-row">
              <td>{r.instance}</td><td>{r.noise}</td><td className="num">{r.shots_per_circuit}</td>
              <td><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: METHOD_COLOR[r.method] }} />{METHOD_LABEL[r.method]}</td>
              <td className="num">{fmt(r.mean, 4)}</td><td className="num">{fmt(r.ideal, 4)}</td><td className="num">{fmt(r.bias, 3)}</td>
              <td className="num">{fmt(r.rmse, 3)} <span className="text-slate-500">[{fmt(r.rmse_ci_lo, 2)}, {fmt(r.rmse_ci_hi, 2)}]</span></td>
              <td className="num">{Math.round(r.total_shots).toLocaleString()}</td>
              <td className={`num ${r.rel_rmse_change < 0 ? "text-emerald-400" : r.rel_rmse_change > 0 ? "text-rose-400" : ""}`}>{r.method === "baseline" ? "–" : pct(r.rel_rmse_change)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
