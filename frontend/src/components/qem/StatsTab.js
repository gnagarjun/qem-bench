import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get, fmt, pct, METHOD_LABEL, METHOD_COLOR } from "@/lib/qem";
import Select from "@/components/qem/Select";

const OUTCOME_CLS = { better_practical: "text-emerald-400", better_marginal: "text-emerald-300/70", worse_practical: "text-rose-400", worse_marginal: "text-rose-300/70" };

export default function StatsTab({ filters }) {
  const [f, setF] = useState({ comparison: "B", shots_per_circuit: "256", noise: null, method: null, reference: "baseline", outcome: null });
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const q = useQuery({ queryKey: ["tests", f], queryFn: () => get("/tests", { ...f, limit: 400 }) });
  const counts = q.data?.outcome_counts || {};
  return (
    <div className="space-y-6" data-testid="statistical-tests-tab">
      <div className="card p-4 flex flex-wrap gap-3 items-end">
        <Select id="stat-comparison-select" label="Accounting" value={f.comparison} onChange={set("comparison")} options={[{ value: "A", label: "A · equal primary" }, { value: "B", label: "B · equal budget" }]} />
        <Select id="stat-shots-select" label="Shots / circuit" value={f.shots_per_circuit} onChange={set("shots_per_circuit")} options={filters.shots_per_circuit.map(String)} />
        <Select id="stat-noise-select" label="Noise" value={f.noise} onChange={set("noise")} options={["low", "moderate", "high"]} />
        <Select id="stat-method-select" label="Method" value={f.method} onChange={set("method")} options={filters.method.filter((m) => m !== "baseline").map((m) => ({ value: m, label: METHOD_LABEL[m] }))} />
        <Select id="stat-reference-select" label="Reference" value={f.reference} onChange={set("reference")} options={["baseline", "readout", "zne_linear", "zne_richardson"].map((m) => ({ value: m, label: METHOD_LABEL[m] }))} allLabel={null} />
        <Select id="stat-outcome-select" label="Outcome" value={f.outcome} onChange={set("outcome")} options={["better_practical", "better_marginal", "no_significant_difference", "worse_marginal", "worse_practical"]} />
      </div>
      <div className="flex flex-wrap gap-3" data-testid="stat-outcome-counts">
        {Object.entries(counts).map(([k, v]) => (
          <div key={k} className="card px-4 py-3"><div className="overline">{k.replaceAll("_", " ")}</div><div className={`num text-xl font-semibold ${OUTCOME_CLS[k] || ""}`}>{v}</div></div>
        ))}
      </div>
      <p className="text-xs text-slate-400 max-w-3xl">Two-sided Wilcoxon signed-rank tests on paired absolute errors (30 repetitions). q = Benjamini–Hochberg over all {">"}12k tests. r = matched-pairs rank-biserial (negative means the method has smaller errors). "Practical" means |ΔRMSE| ≥ 10%. η = relative error reduction per relative extra shot cost; μ = shot-normalised improvement factor (Russo et al. 2023).</p>
      <div className="card overflow-auto max-h-[620px]">
        <table className="qtable" data-testid="stat-comparison-table">
          <thead><tr>{["Instance", "Noise", "N", "Method", "vs", "ΔRMSE", "ΔMSE [95% CI]", "p", "q (BH)", "r", "η", "μ", "Outcome"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{(q.data?.rows || []).map((r, i) => (
            <tr key={i} data-testid="stat-row">
              <td>{r.instance}</td><td>{r.noise}</td><td className="num">{r.shots_per_circuit}</td>
              <td><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: METHOD_COLOR[r.method] }} />{METHOD_LABEL[r.method]}</td>
              <td className="text-slate-400">{METHOD_LABEL[r.reference]}</td>
              <td className="num">{pct(r.rel_rmse_change)}</td>
              <td className="num">{fmt(r.mse_diff, 2)} <span className="text-slate-500">[{fmt(r.mse_diff_ci_lo, 2)}, {fmt(r.mse_diff_ci_hi, 2)}]</span></td>
              <td className="num">{fmt(r.p_wilcoxon, 2)}</td><td className="num">{fmt(r.q_bh, 2)}</td><td className="num">{fmt(r.rank_biserial, 2)}</td>
              <td className="num">{fmt(r.eta, 2)}</td><td className="num">{fmt(r.improvement_factor_mu, 3)}</td>
              <td className={`num text-xs ${OUTCOME_CLS[r.outcome] || "text-slate-400"}`}>{r.outcome}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}
