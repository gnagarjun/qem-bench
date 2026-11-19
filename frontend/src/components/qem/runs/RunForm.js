import { useState } from "react";
import { toast } from "sonner";
import { Play } from "lucide-react";
import { runsApi, apiError } from "@/lib/runs";
import { METHOD_LABEL } from "@/lib/qem";
import ToggleChips from "@/components/qem/runs/ToggleChips";
import NoisePicker from "@/components/qem/runs/NoisePicker";

const INIT = {
  name: "", instances: ["bell_cx", "ghz_4", "qaoa_n4_p1"], noise: [{ base: "moderate", gate_multiplier: 1, readout_multiplier: 1 }],
  shots: [1024, 4096], methods: ["baseline", "readout", "zne_linear", "combined_linear"], comparisons: ["A", "B"],
  repetitions: 10, zne_scales: "1-3-5", folding: "global", seed: "",
};

export default function RunForm({ opts, busy, onStarted }) {
  const [f, setF] = useState(INIT);
  const [sending, setSending] = useState(false);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const noiseKeys = new Set(f.noise.map((n) => (n.gate_multiplier === 1 && n.readout_multiplier === 1 ? n.base : `${n.base}_g${n.gate_multiplier}_r${n.readout_multiplier}`)));
  const units = f.instances.length * noiseKeys.size * f.shots.length * (Number(f.repetitions) || 0);
  const tooBig = units > opts.max_units;
  const valid = f.instances.length && f.noise.length && f.shots.length && f.comparisons.length && f.repetitions >= 2 && f.repetitions <= 100 && !tooBig;
  const submit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const run = await runsApi.start({ ...f, repetitions: Number(f.repetitions), seed: f.seed === "" ? null : Number(f.seed) });
      toast.success("Simulation started");
      onStarted(run.run_id);
    } catch (x) {
      toast.error(apiError(x));
    } finally {
      setSending(false);
    }
  };
  const inst = opts.instances.map((i) => ({ value: i.name, label: i.name, title: `${i.family}, ${i.n_qubits} qubits` }));
  return (
    <form onSubmit={submit} className="card p-5 space-y-5" data-testid="run-form">
      <div className="font-display text-xl font-semibold">New simulation run</div>
      <ToggleChips id="run-instances" label="Circuits" options={inst} value={f.instances} onChange={set("instances")} />
      <NoisePicker levels={opts.noise} value={f.noise} onChange={set("noise")} />
      <ToggleChips id="run-shots" label="Shots per circuit" options={opts.shots.map((s) => ({ value: s, label: s.toLocaleString() }))} value={f.shots} onChange={set("shots")} />
      <ToggleChips id="run-methods" label="Mitigation methods (baseline always included)" options={opts.methods.map((m) => ({ value: m, label: METHOD_LABEL[m] }))} value={f.methods} onChange={set("methods")} locked={["baseline"]} />
      <ToggleChips id="run-comparisons" label="Accounting rules" options={[{ value: "A", label: "A · equal primary shots" }, { value: "B", label: "B · equal total budget" }]} value={f.comparisons} onChange={set("comparisons")} />
      <div className="flex flex-wrap gap-4 items-end">
        <Field label="Repetitions (2–100)"><input type="number" min="2" max="100" className="qselect w-24" data-testid="run-repetitions-input" value={f.repetitions} onChange={(e) => set("repetitions")(e.target.value)} /></Field>
        <Field label="ZNE scale factors"><select className="qselect" data-testid="run-zne-scales-select" value={f.zne_scales} onChange={(e) => set("zne_scales")(e.target.value)}>{Object.keys(opts.zne_presets).map((k) => <option key={k} value={k}>{k.replaceAll("-", ", ")}</option>)}</select></Field>
        <Field label="Folding"><select className="qselect" data-testid="run-folding-select" value={f.folding} onChange={(e) => set("folding")(e.target.value)}><option value="global">global</option><option value="local">local</option></select></Field>
        <Field label="Seed (optional)"><input type="number" min="0" className="qselect w-32" placeholder="random" data-testid="run-seed-input" value={f.seed} onChange={(e) => set("seed")(e.target.value)} /></Field>
        <Field label="Run name"><input className="qselect w-56" maxLength={80} placeholder="e.g. high-noise GHZ check" data-testid="run-name-input" value={f.name} onChange={(e) => set("name")(e.target.value)} /></Field>
      </div>
      <div className="flex flex-wrap items-center gap-4 pt-1">
        <button type="submit" className="btn btn-primary" data-testid="run-start-button" disabled={!valid || sending || busy}><Play size={14} /> {busy ? "A run is in progress" : sending ? "Starting…" : "Start simulation"}</button>
        <span className={`num text-xs ${tooBig ? "text-rose-400" : "text-slate-400"}`} data-testid="run-size-estimate">
          {units.toLocaleString()} condition-repetitions{tooBig ? ` · over the ${opts.max_units.toLocaleString()} limit` : ` · roughly ${Math.max(5, Math.round(units * 0.006 + 4))}s+`}
        </span>
      </div>
    </form>
  );
}

const Field = ({ label, children }) => <label className="flex flex-col gap-1"><span className="overline">{label}</span>{children}</label>;
