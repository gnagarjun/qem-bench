import { METHOD_COLOR, METHOD_LABEL, pct, fmt } from "@/lib/qem";

const CHIP = { SUPPORTED: "chip-sup", "PARTIALLY SUPPORTED": "chip-part", "NOT SUPPORTED": "chip-not" };
const HTEXT = {
  H1: "Readout mitigation reduces bias when measurement errors dominate.",
  H2: "ZNE helps at moderate noise but deteriorates at high noise or small budgets.",
  H3: "Combined mitigation can beat both components, at higher cost.",
  H4: "Greater depth makes accurate estimation harder (pooled test).",
  H5: "Somewhere, unmitigated execution is as good at equal budget.",
};

function Metric({ label, value, sub, id }) {
  return (
    <div className="card p-5 rise transition-colors hover:border-sky-500/40" data-testid={id}>
      <div className="overline">{label}</div>
      <div className="num text-2xl font-semibold mt-2">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

function hDetail(k, h) {
  if (k === "H1") return `${pct(h.fraction_significantly_better)} of ${h.n_conditions} readout-dominated conditions significantly better`;
  if (k === "H2") return `moderate N≥4096: ${pct(h["fraction_better_moderate_N>=4096"])} better; N=256: ${pct(h.fraction_better_by_shots?.["256"])}; noise component ${h.noise_component_supported ? "observed" : "NOT observed"}`;
  if (k === "H3") return `better than both: A ${pct(h.A?.fraction_better_than_both)}, B ${pct(h.B?.fraction_better_than_both)}`;
  if (k === "H4") return `pooled ρ: ${Object.entries(h.by_noise || {}).map(([n, v]) => `${n} ${fmt(v.spearman_rho_n2q_vs_abs_bias, 2)}`).join(", ")}`;
  if (k === "H5") return `${pct(h.fraction_no_method_better)} of ${h.n_conditions} equal-budget conditions: no method better`;
  return "";
}

export default function OverviewTab({ overview }) {
  const s = overview.standard;
  const p = overview.pilot;
  const hyp = s.hypotheses || {};
  const rows = (s.core_method_summary || []).filter((r) => r.method !== "baseline");
  return (
    <div className="space-y-10" data-testid="overview-tab">
      <section className="rise">
        <div className="overline">Primary research question</div>
        <h2 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-2 max-w-4xl">
          How do error-mitigation methods trade accuracy against uncertainty, sampling overhead and cost?
        </h2>
        <p className="text-slate-400 mt-3 max-w-3xl text-sm leading-relaxed">
          Baseline, readout mitigation, zero-noise extrapolation and their combination were compared on Bell, GHZ and QAOA circuits.
          Two accounting rules were used: <b className="text-slate-200">A</b> equal primary shots, and <b className="text-slate-200">B</b> equal total budget including calibration.
        </p>
      </section>
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric id="metric-raw-rows" label="Raw estimates" value={s.n_raw_rows?.toLocaleString()} sub={`${s.n_failed_rows} failed rows (failures are kept, never dropped)`} />
        <Metric id="metric-conditions" label="Conditions" value={s.n_conditions?.toLocaleString()} sub={`${s.repetitions?.join(",")} repetitions each`} />
        <Metric id="metric-tests" label="Paired tests" value={s.n_tests?.toLocaleString()} sub="Wilcoxon, BH-FDR controlled" />
        <Metric id="metric-mode-equivalence" label="Exact vs per-shot Aer" value={pct(p.mode_equivalence?.["fraction_mean_differs_q<0.05"])} sub={`of ${p.mode_equivalence?.n_conditions} pilot conditions differ (q<0.05)`} />
      </section>
      <section>
        <h3 className="font-display text-xl font-semibold mb-4">Pre-specified hypotheses</h3>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {["H1", "H2", "H3", "H4", "H5"].map((k, i) => (
            <div key={k} className="card p-5 rise flex flex-col gap-3" style={{ animationDelay: `${i * 60}ms` }} data-testid={`hypothesis-card-${k.toLowerCase()}`}>
              <div className="flex items-center justify-between">
                <span className="font-display text-lg font-bold">{k}</span>
                <span className={`chip ${CHIP[hyp[k]?.verdict] || "chip-part"}`} data-testid={`hypothesis-verdict-${k.toLowerCase()}`}>{hyp[k]?.verdict}</span>
              </div>
              <p className="text-sm text-slate-300">{HTEXT[k]}</p>
              <p className="num text-xs text-slate-400">{hDetail(k, hyp[k] || {})}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="card overflow-x-auto" data-testid="core-summary-table">
        <div className="p-5 pb-3"><h3 className="font-display text-xl font-semibold">Core grid summary vs baseline</h3>
          <p className="text-xs text-slate-400 mt-1">Medians across 12 instances × observables × 3 noise levels × 7 budgets. "Better/worse" means BH q&lt;0.05.</p></div>
        <table className="qtable">
          <thead><tr><th>Comparison</th><th>Method</th><th>Median ΔRMSE</th><th>Sig. better</th><th>Sig. worse</th><th>Median overhead</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.comparison + r.method}>
              <td className="num">{r.comparison}</td>
              <td><span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: METHOD_COLOR[r.method] }} />{METHOD_LABEL[r.method]}</td>
              <td className="num">{pct(r.median_rel_rmse_change)}</td><td className="num">{pct(r.frac_better)}</td>
              <td className="num">{pct(r.frac_worse)}</td><td className="num">{fmt(r.sampling_overhead)}×</td>
            </tr>))}</tbody>
        </table>
      </section>
    </div>
  );
}
