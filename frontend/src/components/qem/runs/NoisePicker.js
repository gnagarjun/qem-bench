import { Plus, X } from "lucide-react";

export default function NoisePicker({ levels, value, onChange }) {
  const presets = value.filter((n) => n.gate_multiplier === 1 && n.readout_multiplier === 1).map((n) => n.base);
  const customs = value.filter((n) => !(n.gate_multiplier === 1 && n.readout_multiplier === 1));
  const togglePreset = (b) => onChange(presets.includes(b) ? value.filter((n) => !(n.base === b && n.gate_multiplier === 1 && n.readout_multiplier === 1))
    : [...value, { base: b, gate_multiplier: 1, readout_multiplier: 1 }]);
  const setCustom = (i, k, v) => {
    const c = customs.map((n, j) => (j === i ? { ...n, [k]: k === "base" ? v : Number(v) } : n));
    onChange([...value.filter((n) => presets.includes(n.base) && n.gate_multiplier === 1 && n.readout_multiplier === 1), ...c]);
  };
  const keepPresets = value.filter((n) => n.gate_multiplier === 1 && n.readout_multiplier === 1);
  return (
    <div className="flex flex-col gap-2">
      <span className="overline">Noise levels</span>
      <div className="flex flex-wrap gap-1.5" data-testid="run-noise-presets">
        {levels.map((l) => (
          <button type="button" key={l.name} data-testid={`run-noise-${l.name}`} data-active={presets.includes(l.name)} className="togglechip"
            title={`p1=${l.p1}, p2=${l.p2}, readout ${l.readout_p01}/${l.readout_p10}${l.thermal ? ", T1/T2 relaxation" : ""}`} onClick={() => togglePreset(l.name)}>
            {l.name.replace("_", " ")}
          </button>
        ))}
      </div>
      {customs.map((n, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 text-sm" data-testid={`run-noise-custom-${i}`}>
          <select className="qselect" data-testid={`run-noise-custom-base-${i}`} value={n.base} onChange={(e) => setCustom(i, "base", e.target.value)}>
            {levels.map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}
          </select>
          <span className="text-slate-400">gate ×</span>
          <input type="number" min="0" max="10" step="0.25" className="qselect w-20" data-testid={`run-noise-custom-gate-${i}`} value={n.gate_multiplier} onChange={(e) => setCustom(i, "gate_multiplier", e.target.value)} />
          <span className="text-slate-400">readout ×</span>
          <input type="number" min="0" max="10" step="0.25" className="qselect w-20" data-testid={`run-noise-custom-readout-${i}`} value={n.readout_multiplier} onChange={(e) => setCustom(i, "readout_multiplier", e.target.value)} />
          <button type="button" className="text-slate-400 hover:text-rose-400" data-testid={`run-noise-custom-remove-${i}`} onClick={() => onChange([...keepPresets, ...customs.filter((_, j) => j !== i)])}><X size={16} /></button>
        </div>
      ))}
      <button type="button" className="btn self-start text-xs" data-testid="run-noise-add-custom" onClick={() => onChange([...value, { base: "moderate", gate_multiplier: 2, readout_multiplier: 1 }])}>
        <Plus size={14} /> Scaled noise level
      </button>
    </div>
  );
}
